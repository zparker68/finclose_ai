"""
finclose_ai/api/middleware.py
──────────────────────────────
FinClose AI — Request Middleware

1. Correlation IDs  — every request/response carries X-Request-ID
2. Request audit log — every API call recorded with user, endpoint, status, duration

The request audit log is separate from the pipeline audit log (AgentState.audit_log).
It tracks WHO called WHAT at the API boundary — the access control layer.

Audit entries are stored in memory and written to audit_requests.jsonl in the
project root so they survive a log rotation without losing history.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# ── Correlation ID context var (accessible anywhere in the request lifecycle) ─

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# ── Audit log file ─────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).parent.parent
_AUDIT_FILE = _PROJECT_ROOT / "audit_requests.jsonl"

_PROTECTED_PATHS = {"/run", "/demo", "/audit", "/sessions"}


def _extract_user_from_request(request: Request) -> str:
    """Best-effort username extraction without re-running full auth."""
    from jose import JWTError, jwt as _jwt
    from api.auth import ALGORITHM, _SECRET_KEY  # type: ignore[attr-defined]

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return "anonymous"
    token = auth_header.removeprefix("Bearer ").strip()
    try:
        payload = _jwt.decode(token, _SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub", "anonymous")
    except JWTError:
        return "invalid_token"


def _write_audit_entry(entry: dict) -> None:
    try:
        with open(_AUDIT_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass  # Never let audit logging crash the request


# ── In-memory store for /audit/requests endpoint ──────────────────────────────

request_audit_log: list[dict] = []
_MAX_MEMORY_ENTRIES = 500  # cap to avoid unbounded growth


# ── Middleware ────────────────────────────────────────────────────────────────

class CorrelationAndAuditMiddleware(BaseHTTPMiddleware):
    """
    Single middleware that handles both correlation IDs and request audit logging.
    Runs on every request.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # ── 1. Correlation ID ──────────────────────────────────────────────────
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(request_id)

        # ── 2. Time the request ────────────────────────────────────────────────
        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)

        # ── 3. Attach correlation ID to response ───────────────────────────────
        response.headers["X-Request-ID"] = request_id

        # ── 4. Audit log entry ─────────────────────────────────────────────────
        path = request.url.path
        # Skip noisy internal paths
        if not path.startswith(("/openapi", "/docs", "/redoc")):
            user = _extract_user_from_request(request)
            entry = {
                "request_id": request_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "method": request.method,
                "path": path,
                "user": user,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": (request.client.host if request.client else "unknown"),
            }
            request_audit_log.append(entry)
            if len(request_audit_log) > _MAX_MEMORY_ENTRIES:
                request_audit_log.pop(0)
            _write_audit_entry(entry)

        return response
