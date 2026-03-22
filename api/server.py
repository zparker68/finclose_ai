"""
finclose_ai/api/server.py
──────────────────────────
FinClose AI — FastAPI REST Layer

Exposes the 4-agent pipeline over HTTP for tooling, dashboards, or CI/CD integration.

Endpoints:
  POST /run                 — Run full pipeline on a query
  GET  /health              — Ollama + DB connectivity check
  GET  /demo/{task_type}    — Run a preset demo task (5 options)
  GET  /audit/{session_id}  — Retrieve past session result

Usage:
  uvicorn api.server:app --reload --port 8000
  # or from project root:
  python -m uvicorn api.server:app --reload
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.state import AgentState, SoxFlag, state_to_dict
from pipeline import run_pipeline

# ── App init ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FinClose AI",
    description="Multi-agent accounting automation — SOX-auditable, 100% local",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    requested_by: str = "api_user"
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
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str                  # "ok" | "degraded"
    ollama_ok: bool
    db_ok: bool
    model: str
    timestamp: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_ollama() -> bool:
    try:
        r = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            timeout=3,
        )
        return r.returncode == 0
    except Exception:
        return False


def _check_db() -> bool:
    try:
        from core.db_tools import get_chart_of_accounts
        result = get_chart_of_accounts()
        return bool(result.get("records"))
    except Exception:
        return False


def _state_to_response(state: AgentState) -> PipelineResponse:
    """Convert AgentState to API response schema."""
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
        error=state.errors[0] if state.errors else None,
    )


async def _run_pipeline_async(
    query: str,
    period: str,
    requested_by: str,
    model: Optional[str],
) -> AgentState:
    """Run the blocking pipeline in a thread pool to keep the event loop free."""
    if model:
        os.environ["FINCLOSE_MODEL"] = model

    return await asyncio.wait_for(
        asyncio.to_thread(run_pipeline, query, period, requested_by),
        timeout=300.0,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health():
    """Check Ollama connectivity and database accessibility."""
    ollama_ok, db_ok = await asyncio.gather(
        asyncio.to_thread(_check_ollama),
        asyncio.to_thread(_check_db),
    )
    model = os.environ.get("FINCLOSE_MODEL", "mistral")
    return HealthResponse(
        status="ok" if (ollama_ok and db_ok) else "degraded",
        ollama_ok=ollama_ok,
        db_ok=db_ok,
        model=model,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.post("/run", response_model=PipelineResponse, tags=["pipeline"])
async def run(req: RunRequest):
    """
    Run the full 4-agent pipeline (Planner → Retriever → Executor → Critic).

    Requires Ollama to be running locally. Returns a complete analysis with
    SOX flags, verdict, confidence score, and tamper-evident audit trail.
    """
    try:
        state = await _run_pipeline_async(
            query=req.query,
            period=req.period,
            requested_by=req.requested_by,
            model=req.model,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Pipeline timed out after 300s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    response = _state_to_response(state)

    # Store for later retrieval via /audit/{session_id}
    _session_store[state.session_id] = response.model_dump()

    return response


@app.get("/demo/{task_type}", response_model=PipelineResponse, tags=["pipeline"])
async def demo(task_type: str, period: str = "2024-12"):
    """
    Run a preset demo task. task_type must be one of:
    sox_scan, variance, reconciliation, accrual, salary_je
    """
    if task_type not in DEMO_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_type '{task_type}'. Choose from: {list(DEMO_TASKS.keys())}",
        )

    query = DEMO_TASKS[task_type]

    try:
        state = await _run_pipeline_async(
            query=query,
            period=period,
            requested_by="demo",
            model=None,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Pipeline timed out after 300s")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    response = _state_to_response(state)
    _session_store[state.session_id] = response.model_dump()

    return response


@app.get("/audit/{session_id}", tags=["audit"])
async def get_audit(session_id: str):
    """
    Retrieve the full result (including audit trail) for a past session.
    Sessions are stored in-memory — restart clears history.
    """
    if session_id not in _session_store:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Sessions are in-memory only.",
        )
    return _session_store[session_id]


@app.get("/sessions", tags=["audit"])
async def list_sessions():
    """List all session IDs currently in memory."""
    return {
        "count": len(_session_store),
        "sessions": [
            {
                "session_id": sid,
                "verdict": data.get("critic_verdict"),
                "sox_flag_count": len(data.get("sox_flags", [])),
                "period": data.get("period"),
                "processing_ms": data.get("processing_ms"),
            }
            for sid, data in _session_store.items()
        ],
    }


@app.get("/", tags=["ops"])
async def root():
    return {
        "service": "FinClose AI",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "demo_tasks": list(DEMO_TASKS.keys()),
    }
