"""
finclose_ai/api/server.py
──────────────────────────
FinClose AI — FastAPI REST Layer

Exposes the 4-agent pipeline over HTTP for tooling, dashboards, or CI/CD integration.

Endpoints:
  POST /run                   — Run full pipeline (admin only)
  GET  /health                — Ollama + DB connectivity check (public)
  GET  /demo/{task_type}      — Run a preset demo task (admin only)
  GET  /audit/{session_id}    — Retrieve past pipeline session (analyst+)
  GET  /audit/requests        — API-level request audit log (admin only)
  GET  /sessions              — List all pipeline sessions (analyst+)

Usage:
  uvicorn api.server:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
import subprocess
import sys
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.auth import TokenData, require_auth, require_role, router as auth_router
from api.middleware import CorrelationAndAuditMiddleware, request_audit_log
from core.state import AgentState, SoxFlag, state_to_dict
from pipeline import run_pipeline

# ── App init ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FinClose AI",
    description=(
        "Multi-agent accounting automation — SOX-auditable, 100% local.\n\n"
        "**Roles:**\n"
        "- `admin` — full access including pipeline execution\n"
        "- `analyst` — read-only access to sessions and audit logs\n\n"
        "All requests are logged to the API audit trail with user attribution."
    ),
    version="1.0.0",
)

# Order matters: CORS first, then our middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(CorrelationAndAuditMiddleware)

app.include_router(auth_router)

# In-memory session store (keyed by session_id)
_session_store: dict[str, dict] = {}

# ── Demo task presets ─────────────────────────────────────────────────────────

DEMO_TASKS: dict[str, str] = {
    "sox_scan":       "Scan all GL transactions for SOX violations and policy breaches",
    "variance":       "Run variance analysis for all accounts against budget thresholds",
    "reconciliation": "Review all open reconciliations and identify exceptions",
    "accrual":        "Validate the accrual schedule and confirm reversal entries",
    "salary_je":      "Generate salary accrual journal entry for December payroll",
}

# ── Request / Response schemas ────────────────────────────────────────────────

class RunRequest(BaseModel):
    query: str
    period: str = "2024-12"
    model: Optional[str] = None


class PipelineResponse(BaseModel):
    session_id: str
    critic_verdict: str
    confidence_score: float
    sox_flags: list[str]
    sox_flag_details: list[str]
    final_response: str
    audit_log: list[dict]
    task_type: str
    processing_ms: float
    period: str
    requested_by: str
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str          # "ok" | "degraded"
    ollama_ok: bool
    db_ok: bool
    model: str
    timestamp: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_ollama() -> bool:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False


def _check_db() -> bool:
    try:
        from core.db_tools import get_chart_of_accounts
        return bool(get_chart_of_accounts().get("records"))
    except Exception:
        return False


def _state_to_response(state: AgentState, requested_by: str) -> PipelineResponse:
    return PipelineResponse(
        session_id=state.session_id,
        critic_verdict=state.critic_verdict or "UNKNOWN",
        confidence_score=state.confidence_score,
        sox_flags=[f.value for f in state.sox_flags],
        sox_flag_details=state.sox_flag_details,
        final_response=state.final_response,
        audit_log=[dataclasses.asdict(e) for e in state.audit_log],
        task_type=state.task_type.value,
        processing_ms=state.processing_ms,
        period=state.period,
        requested_by=requested_by,
        error=state.errors[0] if state.errors else None,
    )


async def _run_pipeline_async(
    query: str, period: str, requested_by: str, model: Optional[str]
) -> AgentState:
    if model:
        os.environ["FINCLOSE_MODEL"] = model
    return await asyncio.wait_for(
        asyncio.to_thread(run_pipeline, query, period, requested_by),
        timeout=300.0,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    """Check Ollama connectivity and database accessibility. No auth required."""
    ollama_ok, db_ok = await asyncio.gather(
        asyncio.to_thread(_check_ollama),
        asyncio.to_thread(_check_db),
    )
    return HealthResponse(
        status="ok" if (ollama_ok and db_ok) else "degraded",
        ollama_ok=ollama_ok,
        db_ok=db_ok,
        model=os.environ.get("FINCLOSE_MODEL", "mistral"),
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.post("/run", response_model=PipelineResponse, tags=["pipeline"])
async def run(
    req: RunRequest,
    user: TokenData = Depends(require_role("admin")),
):
    """
    Run the full 4-agent pipeline (Planner → Retriever → Executor → Critic).

    **Requires admin role.** Pipeline run is attributed to the authenticated user
    and recorded in both the pipeline audit log and the API request audit trail.
    """
    try:
        state = await _run_pipeline_async(
            query=req.query,
            period=req.period,
            requested_by=user.username,
            model=req.model,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Pipeline timed out after 300s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    response = _state_to_response(state, requested_by=user.username)
    _session_store[state.session_id] = response.model_dump()
    return response


@app.get("/demo/{task_type}", response_model=PipelineResponse, tags=["pipeline"])
async def demo(
    task_type: str,
    period: str = "2024-12",
    user: TokenData = Depends(require_role("admin")),
):
    """
    Run a preset demo task. **Requires admin role.**

    `task_type` must be one of: `sox_scan`, `variance`, `reconciliation`, `accrual`, `salary_je`
    """
    if task_type not in DEMO_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_type '{task_type}'. Choose from: {list(DEMO_TASKS.keys())}",
        )
    try:
        state = await _run_pipeline_async(
            query=DEMO_TASKS[task_type],
            period=period,
            requested_by=user.username,
            model=None,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Pipeline timed out after 300s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    response = _state_to_response(state, requested_by=user.username)
    _session_store[state.session_id] = response.model_dump()
    return response


@app.get("/audit/requests", tags=["audit"])
async def get_request_audit(
    limit: int = 100,
    _user: TokenData = Depends(require_role("admin")),
):
    """
    API-level request audit log. **Requires admin role.**

    Returns every API call made to this server — user, endpoint, status code,
    duration, timestamp, correlation ID, and client IP.
    SOX-relevant: proves every action on financial data is attributable to an authenticated user.
    """
    entries = request_audit_log[-limit:]
    return {"count": len(entries), "entries": list(reversed(entries))}


@app.get("/audit/{session_id}", tags=["audit"])
async def get_audit(
    session_id: str,
    _user: TokenData = Depends(require_auth),
):
    """
    Retrieve the full pipeline result + agent audit trail for a session.
    Available to all authenticated users (analyst+).
    """
    if session_id not in _session_store:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )
    return _session_store[session_id]


@app.get("/sessions", tags=["audit"])
async def list_sessions(_user: TokenData = Depends(require_auth)):
    """
    List all pipeline sessions in memory. Available to all authenticated users (analyst+).
    """
    return {
        "count": len(_session_store),
        "sessions": [
            {
                "session_id": sid,
                "verdict": data.get("critic_verdict"),
                "sox_flag_count": len(data.get("sox_flags", [])),
                "period": data.get("period"),
                "processing_ms": data.get("processing_ms"),
                "requested_by": data.get("requested_by"),
            }
            for sid, data in _session_store.items()
        ],
    }


@app.get("/audit/{session_id}/export/pbc", tags=["audit"])
async def export_pbc(
    session_id: str,
    _user: TokenData = Depends(require_auth),
):
    """
    Export the pipeline result as a **PBC (Provided by Client) list**.

    PBC lists are the standard format external auditors request during audit season.
    Each audit trail entry maps to one PBC line item with: item number, description,
    preparer, date, status, supporting evidence hash, and SOX flags.

    Directly reduces manual labor during audit prep — auditors can import this list
    instead of requesting each item individually.
    """
    if session_id not in _session_store:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    data = _session_store[session_id]
    audit_entries = data.get("audit_log", [])

    pbc_items = []
    for i, entry in enumerate(audit_entries, start=1):
        pbc_items.append({
            "pbc_item":         i,
            "description":      f"[{entry.get('agent', '').upper()}] {entry.get('action', '')}",
            "period":           data.get("period"),
            "prepared_by":      data.get("requested_by", "system"),
            "prepared_date":    entry.get("timestamp", ""),
            "status":           "Complete" if not entry.get("sox_flags") else "Flagged — Requires Review",
            "sox_flags":        entry.get("sox_flags", []),
            "evidence_hash":    entry.get("input_hash", ""),
            "confidence":       entry.get("confidence", 1.0),
            "prompt_version":   entry.get("prompt_version", ""),
            "citations":        entry.get("citations", []),
            "notes":            entry.get("reasoning", ""),
        })

    return {
        "pbc_list_metadata": {
            "session_id":    session_id,
            "period":        data.get("period"),
            "prepared_by":   data.get("requested_by"),
            "critic_verdict": data.get("critic_verdict"),
            "sox_flag_count": len(data.get("sox_flags", [])),
            "exported_at":   datetime.utcnow().isoformat() + "Z",
            "system":        "FinClose AI v1.0.0",
            "note":          "This document constitutes a complete audit trail for the referenced period close activity.",
        },
        "item_count": len(pbc_items),
        "pbc_items":  pbc_items,
    }


@app.get("/metrics/summary", tags=["monitoring"])
async def metrics_summary(_user: TokenData = Depends(require_role("admin"))):
    """
    Aggregate pipeline performance stats. **Requires admin role.**

    Returns: total runs, avg/p95 latency, verdict distribution,
    SOX flag rate, confidence score avg + stddev.
    """
    from monitoring.metrics import get_summary
    return get_summary()


@app.get("/metrics/dashboard", tags=["monitoring"])
async def metrics_dashboard(_user: TokenData = Depends(require_role("admin"))):
    """
    Time-series data for the performance dashboard. **Requires admin role.**

    Returns confidence score history, latency history, verdict series,
    and SOX flag rate — ready for Plotly charts.
    """
    from monitoring.metrics import get_dashboard_data
    return get_dashboard_data()


@app.get("/", tags=["ops"])
async def root():
    return {
        "service": "FinClose AI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "demo_tasks": list(DEMO_TASKS.keys()),
        "roles": {"admin": "full access", "analyst": "read-only"},
    }
