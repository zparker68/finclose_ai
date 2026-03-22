"""
finclose_ai/core/state.py
─────────────────────────
Shared LangGraph state schema + enums used across all agents.
Every agent reads from and writes to AgentState — nothing is passed
through function arguments directly, keeping the graph side-effect free
and fully auditable (SOX requirement).
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from langchain_core.messages import BaseMessage


# ── Task Types ────────────────────────────────────────────────────────────────

class TaskType(str, Enum):
    RECONCILIATION    = "reconciliation"
    JOURNAL_ENTRY     = "journal_entry"
    VARIANCE_ANALYSIS = "variance_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    ACCRUAL_REVIEW    = "accrual_review"
    CLOSE_CHECKLIST   = "close_checklist"
    GENERAL_QUERY     = "general_query"


class AgentRole(str, Enum):
    PLANNER   = "planner"
    RETRIEVER = "retriever"
    EXECUTOR  = "executor"
    CRITIC    = "critic"


class SoxFlag(str, Enum):
    SELF_APPROVAL        = "SELF_APPROVAL"
    MISSING_APPROVER     = "MISSING_APPROVER"
    UNBALANCED_ENTRY     = "UNBALANCED_ENTRY"
    WEEKEND_POSTING      = "WEEKEND_POSTING"
    PRIOR_PERIOD_POSTING = "PRIOR_PERIOD_POSTING"
    ROUND_NUMBER_MANUAL  = "ROUND_NUMBER_MANUAL"
    THRESHOLD_BREACH     = "THRESHOLD_BREACH"
    UNUSUAL_ACCOUNT_COMBO = "UNUSUAL_ACCOUNT_COMBO"


# ── Audit Log Entry ───────────────────────────────────────────────────────────

@dataclass
class AuditEntry:
    """
    Immutable audit record written by every agent action.
    Satisfies SOX Section 302/404 documentation requirements:
    every decision is timestamped, attributed, and reasoned.
    """
    timestamp:   str
    agent:       str
    action:      str
    input_hash:  str        # SHA-256 of inputs — tamper detection
    reasoning:   str
    output:      str
    sox_flags:   list[str]  = field(default_factory=list)
    citations:   list[str]  = field(default_factory=list)
    confidence:  float      = 1.0


# ── Central State Schema ──────────────────────────────────────────────────────

@dataclass
class AgentState:
    """
    The single source of truth flowing through the LangGraph pipeline.

    Design principles:
    - Immutable inputs (user_query, period) — never modified after init
    - Append-only audit_log — agents ADD entries, never delete
    - Each agent writes only to its designated output field
    - sox_flags accumulated across all agents for final Critic review
    """

    # ── Immutable inputs ──────────────────────────────────────────────────────
    user_query:      str           = ""
    period:          str           = "2024-12"
    session_id:      str           = ""
    requested_by:    str           = "user"

    # ── Planner outputs ───────────────────────────────────────────────────────
    task_type:       TaskType      = TaskType.GENERAL_QUERY
    task_plan:       list[str]     = field(default_factory=list)
    relevant_tables: list[str]     = field(default_factory=list)
    routing_reason:  str           = ""

    # ── Retriever outputs ─────────────────────────────────────────────────────
    retrieved_data:  dict[str, Any] = field(default_factory=dict)
    policy_context:  list[str]      = field(default_factory=list)
    data_summary:    str            = ""

    # ── Executor outputs ──────────────────────────────────────────────────────
    analysis_result: str           = ""
    structured_output: dict        = field(default_factory=dict)
    journal_entries: list[dict]    = field(default_factory=list)
    narrative:       str           = ""

    # ── Critic outputs ────────────────────────────────────────────────────────
    sox_flags:       list[SoxFlag] = field(default_factory=list)
    sox_flag_details: list[str]    = field(default_factory=list)
    critic_verdict:  str           = ""          # APPROVED | FLAGGED | REJECTED
    confidence_score: float        = 0.0
    citations:       list[str]     = field(default_factory=list)

    # ── Cross-cutting ─────────────────────────────────────────────────────────
    messages:        list[BaseMessage] = field(default_factory=list)
    audit_log:       list[AuditEntry]  = field(default_factory=list)
    errors:          list[str]         = field(default_factory=list)
    final_response:  str               = ""
    processing_ms:   float             = 0.0


def state_to_dict(state: AgentState) -> dict:
    """Serialize state for JSON export / audit archive."""
    import dataclasses
    d = dataclasses.asdict(state)
    d["sox_flags"] = [f.value for f in state.sox_flags]
    d["task_type"] = state.task_type.value
    d["audit_log"] = [dataclasses.asdict(e) for e in state.audit_log]
    return d
