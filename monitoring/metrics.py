"""
finclose_ai/monitoring/metrics.py
───────────────────────────────────
Lightweight JSONL-based metrics tracker for the FinClose AI pipeline.

Every pipeline run writes one record to monitoring/metrics.jsonl.
The get_summary() function aggregates stats for dashboards or CI checks.

Usage:
    from monitoring.metrics import record_run, get_summary

    # After run_pipeline():
    record_run(state, model="mistral")

    # Aggregate stats:
    summary = get_summary()
    print(summary["avg_latency_ms"])
"""

from __future__ import annotations

import json
import os
import statistics
import uuid
from datetime import datetime
from typing import Any, Optional

# ── File path ─────────────────────────────────────────────────────────────────

_METRICS_DIR = os.path.dirname(__file__)
METRICS_FILE = os.path.join(_METRICS_DIR, "metrics.jsonl")


# ── Record a pipeline run ─────────────────────────────────────────────────────

def record_run(state: Any, model: str = "mistral") -> dict:
    """
    Append one metrics record for a completed pipeline run.

    Args:
        state:  Completed AgentState returned by run_pipeline()
        model:  Model name used (e.g. "mistral", "llama3.2:3b")

    Returns:
        The dict written to disk (for testing or logging).
    """
    # Extract per-agent latencies from audit log (each entry has a timestamp)
    agent_latencies = _extract_agent_latencies(state)

    record = {
        "run_id":          str(uuid.uuid4())[:8],
        "timestamp":       datetime.utcnow().isoformat() + "Z",
        "session_id":      getattr(state, "session_id", ""),
        "period":          getattr(state, "period", ""),
        "task_type":       getattr(state.task_type, "value", str(getattr(state, "task_type", ""))),
        "processing_ms":   round(getattr(state, "processing_ms", 0.0), 1),
        "confidence_score": round(getattr(state, "confidence_score", 0.0), 4),
        "sox_flag_count":  len(getattr(state, "sox_flags", [])),
        "sox_flags":       [f.value for f in getattr(state, "sox_flags", [])],
        "critic_verdict":  getattr(state, "critic_verdict", ""),
        "agent_latencies": agent_latencies,
        "model":           model,
        "error":           getattr(state, "errors", [None])[0] if getattr(state, "errors", []) else None,
    }

    _append_record(record)
    return record


def _extract_agent_latencies(state: Any) -> dict[str, float]:
    """
    Estimate per-agent latency from audit log timestamps.
    Audit entries have ISO timestamps — diff consecutive entries.
    Falls back to proportional split of processing_ms if parsing fails.
    """
    audit_log = getattr(state, "audit_log", [])
    if len(audit_log) < 2:
        total = getattr(state, "processing_ms", 0.0)
        return {"planner": total * 0.05, "retriever": total * 0.05,
                "executor": total * 0.85, "critic": total * 0.05}

    try:
        times = []
        for entry in audit_log:
            ts_str = entry.timestamp.rstrip("Z")
            ts = datetime.fromisoformat(ts_str)
            times.append((entry.agent, ts))

        latencies: dict[str, float] = {}
        total_ms = getattr(state, "processing_ms", 0.0)

        for i, (agent, ts) in enumerate(times):
            if i + 1 < len(times):
                delta = (times[i + 1][1] - ts).total_seconds() * 1000
                latencies[agent] = round(max(delta, 0), 1)
            else:
                # Last agent gets the remainder
                used = sum(latencies.values())
                latencies[agent] = round(max(total_ms - used, 0), 1)

        return latencies
    except Exception:
        total = getattr(state, "processing_ms", 0.0)
        return {"planner": round(total * 0.05, 1), "retriever": round(total * 0.05, 1),
                "executor": round(total * 0.85, 1), "critic": round(total * 0.05, 1)}


def _append_record(record: dict) -> None:
    os.makedirs(_METRICS_DIR, exist_ok=True)
    with open(METRICS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Load all records ──────────────────────────────────────────────────────────

def load_records() -> list[dict]:
    """Load all records from metrics.jsonl. Returns empty list if file missing."""
    if not os.path.exists(METRICS_FILE):
        return []
    records = []
    with open(METRICS_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


# ── Aggregate summary ─────────────────────────────────────────────────────────

def get_summary() -> dict:
    """
    Compute aggregate stats over all recorded runs.

    Returns dict with:
      total_runs, avg_latency_ms, p95_latency_ms,
      verdict_distribution, sox_flag_rate,
      avg_confidence, agent_avg_latencies
    """
    records = load_records()
    if not records:
        return {"total_runs": 0, "message": "No runs recorded yet."}

    latencies = [r["processing_ms"] for r in records]
    confidences = [r["confidence_score"] for r in records]
    verdict_counts: dict[str, int] = {}
    sox_flagged = 0

    for r in records:
        v = r.get("critic_verdict", "UNKNOWN")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        if r.get("sox_flag_count", 0) > 0:
            sox_flagged += 1

    # Per-agent averages
    agent_names = ["planner", "retriever", "executor", "critic"]
    agent_avg: dict[str, float] = {}
    for agent in agent_names:
        vals = [r["agent_latencies"].get(agent, 0) for r in records if "agent_latencies" in r]
        agent_avg[agent] = round(statistics.mean(vals), 1) if vals else 0.0

    n = len(records)
    sorted_lat = sorted(latencies)
    p95_idx = max(0, int(0.95 * n) - 1)

    return {
        "total_runs":           n,
        "avg_latency_ms":       round(statistics.mean(latencies), 1),
        "p95_latency_ms":       round(sorted_lat[p95_idx], 1),
        "verdict_distribution": {
            k: {"count": v, "pct": round(v / n * 100, 1)}
            for k, v in verdict_counts.items()
        },
        "sox_flag_rate":        round(sox_flagged / n * 100, 1),
        "avg_confidence":       round(statistics.mean(confidences), 4),
        "stddev_confidence":    round(statistics.stdev(confidences), 4) if n > 1 else 0.0,
        "agent_avg_latencies":  agent_avg,
    }


def get_dashboard_data() -> dict:
    """
    Return structured data ready for Streamlit/Plotly charts.

    Returns:
        {
          "latency_history":    [{timestamp, processing_ms}, ...],
          "verdict_series":     [{verdict, count}, ...],
          "confidence_history": [{timestamp, confidence_score}, ...],
          "sox_rate_history":   [{timestamp, has_flags}, ...],
          "task_type_counts":   [{task_type, count}, ...],
          "summary":            get_summary()
        }
    """
    records = load_records()

    latency_history = [
        {"timestamp": r["timestamp"], "processing_ms": r["processing_ms"]}
        for r in records
    ]

    confidence_history = [
        {"timestamp": r["timestamp"], "confidence_score": r["confidence_score"]}
        for r in records
    ]

    sox_rate_history = [
        {"timestamp": r["timestamp"], "has_flags": r["sox_flag_count"] > 0}
        for r in records
    ]

    verdict_counts: dict[str, int] = {}
    task_counts: dict[str, int] = {}
    for r in records:
        v = r.get("critic_verdict", "UNKNOWN")
        verdict_counts[v] = verdict_counts.get(v, 0) + 1
        t = r.get("task_type", "unknown")
        task_counts[t] = task_counts.get(t, 0) + 1

    return {
        "latency_history":    latency_history,
        "verdict_series":     [{"verdict": k, "count": v} for k, v in verdict_counts.items()],
        "confidence_history": confidence_history,
        "sox_rate_history":   sox_rate_history,
        "task_type_counts":   [{"task_type": k, "count": v} for k, v in task_counts.items()],
        "summary":            get_summary(),
    }
