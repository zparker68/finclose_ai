"""
finclose_ai/api/auth.py
────────────────────────
FinClose AI — JWT Authentication + RBAC Layer

Two built-in roles:
  admin   — full access (run pipeline, view all sessions, audit logs)
  analyst — read-only (health, audit retrieval, sessions list — no pipeline execution)

Credentials via environment variables:
  FINCLOSE_ADMIN_USER      / FINCLOSE_ADMIN_PASSWORD    (default: admin / finclose2024)
  FINCLOSE_ANALYST_USER    / FINCLOSE_ANALYST_PASSWORD  (default: analyst / analyst2024)
  FINCLOSE_JWT_SECRET      (default: random per process — set in .env for persistence)
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

# ── Config ────────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8-hour session

_SECRET_KEY: str = os.environ.get("FINCLOSE_JWT_SECRET", secrets.token_hex(32))

Role = Literal["admin", "analyst"]

# User registry — keyed by username, value is (hashed_password, role)
def _build_user_registry() -> dict[str, tuple[bytes, Role]]:
    admin_user = os.environ.get("FINCLOSE_ADMIN_USER", "admin")
    admin_pass = os.environ.get("FINCLOSE_ADMIN_PASSWORD", "finclose2024")
    analyst_user = os.environ.get("FINCLOSE_ANALYST_USER", "analyst")
    analyst_pass = os.environ.get("FINCLOSE_ANALYST_PASSWORD", "analyst2024")
    return {
        admin_user:   (bcrypt.hashpw(admin_pass.encode(), bcrypt.gensalt()),   "admin"),
        analyst_user: (bcrypt.hashpw(analyst_pass.encode(), bcrypt.gensalt()), "analyst"),
    }

_USERS: dict[str, tuple[bytes, Role]] = _build_user_registry()

# In-memory token denylist (logout support)
_revoked_tokens: set[str] = set()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    role: Role


class TokenData(BaseModel):
    username: str
    role: Role
    jti: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_access_token(username: str, role: Role) -> tuple[str, str]:
    """Create a signed JWT. Returns (token, jti)."""
    jti = secrets.token_hex(16)
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=ALGORITHM), jti


def _decode_token(token: str) -> TokenData:
    """Decode and validate a JWT. Raises HTTPException on any failure."""
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub", "")
        role: str = payload.get("role", "")
        jti: str = payload.get("jti", "")
        if not username or not jti or role not in ("admin", "analyst"):
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    if jti in _revoked_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked — please log in again",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenData(username=username, role=role, jti=jti)  # type: ignore[arg-type]


# ── Dependencies ──────────────────────────────────────────────────────────────

async def require_auth(token: Annotated[str, Depends(oauth2_scheme)]) -> TokenData:
    """Validates token and returns full TokenData (username + role)."""
    return _decode_token(token)


def require_role(required_role: Role):
    """
    FastAPI dependency factory for role-based access control.

    Usage:
        @app.post("/run")
        async def run(req: RunRequest, user: TokenData = Depends(require_role("admin"))):
    """
    async def _check(token_data: Annotated[TokenData, Depends(require_auth)]) -> TokenData:
        if token_data.role != required_role and token_data.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires '{required_role}' role — your role: '{token_data.role}'",
            )
        return token_data
    return _check


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """
    Authenticate and receive a Bearer token.

    Built-in accounts:
    - **admin** / finclose2024 — full pipeline access
    - **analyst** / analyst2024 — read-only access

    Use the token in all subsequent requests:
      `Authorization: Bearer <access_token>`
    """
    user_entry = _USERS.get(form.username)
    if not user_entry or not bcrypt.checkpw(form.password.encode(), user_entry[0]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    hashed_pw, role = user_entry
    token, _jti = _create_access_token(form.username, role)
    return TokenResponse(access_token=token, role=role)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Revoke the current Bearer token (server-side denylist).
    Subsequent requests with this token receive 401.
    """
    try:
        data = _decode_token(token)
        _revoked_tokens.add(data.jti)
    except HTTPException:
        pass  # Already invalid — treat as successful logout


@router.get("/me", tags=["auth"])
async def me(token_data: Annotated[TokenData, Depends(require_auth)]):
    """Return the currently authenticated user and their role."""
    return {"username": token_data.username, "role": token_data.role}
