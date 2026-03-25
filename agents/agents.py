"""
finclose_ai/agents/agents.py
─────────────────────────────
The four-agent pipeline powering FinClose AI.

Architecture:
  User Query
      │
  [PLANNER]   — Classifies task, selects tools, writes execution plan
      │
  [RETRIEVER] — Pulls data from DB tools + policy context
      │
  [EXECUTOR]  — Runs the accounting analysis, generates JEs / narratives
      │
  [CRITIC]    — SOX review, confidence scoring, citation audit
      │
  Final Response + Audit Log

Each agent:
  1. Reads from AgentState
  2. Calls the LLM with a role-specific system prompt
  3. Appends an AuditEntry to state.audit_log
  4. Writes ONLY to its designated state fields
  5. Returns the updated state (immutable pattern)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from core.state import AgentState, AgentRole, AuditEntry, SoxFlag, TaskType
from core import db_tools

# ── LLM Setup ─────────────────────────────────────────────────────────────────
# Uses Ollama running locally — zero data leaves the machine.
# Default: mistral (good balance of speed + reasoning on 8GB RAM)
# Swap to: llama3.2, qwen2.5, or any GGUF you have pulled.

def _llm(temperature: float = 0.1) -> ChatOllama:
    # Read env var at call time so model switching from the UI takes effect immediately
    model = os.environ.get("FINCLOSE_MODEL", "mistral")
    return ChatOllama(model=model, temperature=temperature)


def _hash_inputs(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(str(data), sort_keys=True).encode()
    ).hexdigest()[:16]


def _audit(agent: str, action: str, inputs: dict,
           reasoning: str, output: str,
           sox_flags: list[str] | None = None,
           citations: list[str] | None = None,
           confidence: float = 1.0) -> AuditEntry:
    return AuditEntry(
        timestamp=datetime.utcnow().isoformat() + "Z",
        agent=agent,
        action=action,
        input_hash=_hash_inputs(inputs),
        reasoning=reasoning,
        output=output,
        sox_flags=sox_flags or [],
        citations=citations or [],
        confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — PLANNER
# ═══════════════════════════════════════════════════════════════════════════════

PLANNER_SYSTEM = """You are the Planner Agent for FinClose AI, an enterprise accounting automation system.

Your job is to:
1. Classify the user's accounting task into one of these types:
   - reconciliation: account reconciliation, balance matching, sub-ledger tie-out
   - journal_entry: create, review, or validate journal entries
   - variance_analysis: budget vs actual, period-over-period comparison, expense analysis
   - anomaly_detection: flag unusual entries, SOX control violations, fraud indicators
   - accrual_review: review, validate, or generate accrual schedules
   - close_checklist: month-end close status, checklist progress
   - general_query: anything else

2. Write a step-by-step execution plan (3-5 steps) for the Executor agent.

3. List the database tables needed:
   Available tables: gl_transactions, trial_balance, reconciliations, recon_items,
   ap_invoices, ar_aging, accruals, variance_analysis, chart_of_accounts, policy_documents

Respond ONLY with valid JSON, exactly this structure:
{
  "task_type": "<type>",
  "routing_reason": "<one sentence explaining why>",
  "task_plan": ["step 1", "step 2", "step 3"],
  "relevant_tables": ["table1", "table2"],
  "policy_category": "<Financial Close|Revenue|null>"
}"""


def planner_agent(state: AgentState) -> AgentState:
    """
    Classifies the user query and produces a structured execution plan.
    Routes to the correct data tools and sets the agenda for downstream agents.
    """
    t0 = time.time()
    llm = _llm(temperature=0.0)

    prompt = f"""User query: "{state.user_query}"
Period: {state.period}

Classify and plan this accounting task."""

    try:
        response = llm.invoke([
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=prompt),
        ])

        raw = response.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:-1])

        # Extract JSON object even if LLM added preamble text
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            raw = json_match.group(0)

        plan = json.loads(raw)

        state.task_type = TaskType(plan.get("task_type", "general_query"))
        state.routing_reason = plan.get("routing_reason", "")
        state.task_plan = plan.get("task_plan", [])
        state.relevant_tables = plan.get("relevant_tables", [])

    except Exception as e:
        # Graceful degradation — fallback plan
        state.task_type = TaskType.GENERAL_QUERY
        state.routing_reason = f"Planner fallback due to: {e}"
        state.task_plan = ["Query data", "Analyze", "Summarize"]
        state.relevant_tables = ["gl_transactions", "trial_balance"]

    state.audit_log.append(_audit(
        agent=AgentRole.PLANNER.value,
        action="classify_and_plan",
        inputs={"query": state.user_query, "period": state.period},
        reasoning=state.routing_reason,
        output=f"Task: {state.task_type.value} | Steps: {len(state.task_plan)}",
        confidence=0.95,
    ))

    state.processing_ms += (time.time() - t0) * 1000
    return state


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 2 — RETRIEVER
# ═══════════════════════════════════════════════════════════════════════════════

def retriever_agent(state: AgentState) -> AgentState:
    """
    Pulls structured data from the enterprise system tool layer (Oracle/Blackline).
    Also retrieves relevant accounting policy text for RAG grounding.
    No LLM call — pure data retrieval for maximum auditability.
    """
    t0 = time.time()
    retrieved = {}
    citations = []

    # ── Data retrieval based on task type ─────────────────────────────────────
    task = state.task_type

    if task == TaskType.RECONCILIATION:
        result = db_tools.get_reconciliations(state.period)
        retrieved["reconciliations"] = result
        citations.append(f"Blackline | {result['record_count']} reconciliations | hash:{result['data_hash']}")

        tb = db_tools.get_trial_balance(state.period)
        retrieved["trial_balance"] = tb
        citations.append(f"Oracle GL Trial Balance | {tb['account_count']} accounts | hash:{tb['data_hash']}")

    elif task == TaskType.JOURNAL_ENTRY:
        gl = db_tools.get_gl_transactions(state.period)
        retrieved["gl_transactions"] = gl
        citations.append(f"Oracle Fusion GL | {gl['record_count']} transactions | hash:{gl['data_hash']}")

        accruals = db_tools.get_accruals(state.period)
        retrieved["accruals"] = accruals
        citations.append(f"Oracle GL Accruals | {accruals['total_accrual_amount']:,.0f} total")

    elif task == TaskType.VARIANCE_ANALYSIS:
        var = db_tools.get_variance_analysis(state.period)
        retrieved["variance_analysis"] = var
        citations.append(f"Oracle/HFM Variance | {var['threshold_breaches']} threshold breaches")

        tb = db_tools.get_trial_balance(state.period)
        retrieved["trial_balance"] = tb
        citations.append(f"Oracle GL Trial Balance | hash:{tb['data_hash']}")

    elif task == TaskType.ANOMALY_DETECTION:
        anomalies = db_tools.get_anomalous_entries(state.period)
        retrieved["anomalies"] = anomalies
        citations.append(f"Oracle GL Anomaly Scan | {anomalies['anomaly_count']} flagged entries")

        unbalanced = db_tools.get_unbalanced_entries(state.period)
        retrieved["unbalanced"] = unbalanced
        citations.append(f"Oracle GL Balance Check | {unbalanced['unbalanced_count']} imbalanced JEs")

    elif task == TaskType.ACCRUAL_REVIEW:
        accruals = db_tools.get_accruals(state.period)
        retrieved["accruals"] = accruals
        citations.append(f"Oracle GL Accruals | {len(accruals['records'])} entries | ${accruals['total_accrual_amount']:,.0f}")

        gl = db_tools.get_gl_transactions(state.period)
        retrieved["gl_transactions"] = gl
        citations.append(f"Oracle Fusion GL | hash:{gl['data_hash']}")

    else:
        # General — pull a broad snapshot
        tb = db_tools.get_trial_balance(state.period)
        retrieved["trial_balance"] = tb
        citations.append(f"Oracle GL Trial Balance | hash:{tb['data_hash']}")

        gl = db_tools.get_gl_transactions(state.period, limit=50)
        retrieved["gl_transactions"] = gl
        citations.append(f"Oracle Fusion GL | {gl['record_count']} transactions")

    # ── Always retrieve relevant policies (RAG grounding) ─────────────────────
    policy_result = db_tools.get_policy_documents()
    policy_context = []
    for doc in policy_result["records"]:
        # Truncate for context window — keep first 1500 chars of each policy
        excerpt = doc["content"][:1500].strip()
        policy_context.append(f"[{doc['doc_id']}] {doc['title']}:\n{excerpt}")
    citations.append(f"Policy Library | {len(policy_context)} documents retrieved")

    state.retrieved_data = retrieved
    state.policy_context = policy_context
    state.citations = citations

    # Build human-readable data summary for Executor prompt
    summary_parts = []
    for key, val in retrieved.items():
        if isinstance(val, dict):
            count = val.get("record_count") or val.get("account_count") or val.get("anomaly_count", "?")
            src   = val.get("source", key)
            summary_parts.append(f"  • {src}: {count} records retrieved")
    state.data_summary = "\n".join(summary_parts)

    state.audit_log.append(_audit(
        agent=AgentRole.RETRIEVER.value,
        action="retrieve_data",
        inputs={"task_type": task.value, "period": state.period},
        reasoning=f"Retrieved {len(retrieved)} datasets matching task type '{task.value}'",
        output=state.data_summary,
        citations=citations,
        confidence=1.0,
    ))

    state.processing_ms += (time.time() - t0) * 1000
    return state


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 3 — EXECUTOR
# ═══════════════════════════════════════════════════════════════════════════════

EXECUTOR_SYSTEM = """You are the Executor Agent for FinClose AI, an enterprise accounting automation system used by the Global Accounting team.

You perform financial close tasks with the precision of a Big 4 accountant and the analytical depth of a CFO.

Your responsibilities:
- Reconciliation: Identify and explain balance differences, categorize items by aging, recommend resolution
- Journal Entries: Generate properly formatted, balanced debit/credit entries with business purpose
- Variance Analysis: Quantify and explain budget vs. actual differences, flag threshold breaches (>10%), write CFO-ready narratives
- Anomaly Detection: Identify SOX control violations, unusual patterns, fraud indicators
- Accrual Review: Validate completeness, accuracy, and proper reversal setup

FORMATTING RULES:
- Be precise and quantitative — always cite specific dollar amounts
- Journal entries must always balance (total debits = total credits)
- Flag any SOX concerns with prefix [SOX FLAG]
- Reference policy documents when applicable: cite as [POL-XXX]
- Structure output with clear sections: SUMMARY | FINDINGS | RECOMMENDATIONS | JOURNAL ENTRIES (if applicable)
- Write as if this will be reviewed by external auditors

IMPORTANT: Base your analysis ONLY on the data provided. Never fabricate numbers."""


def _build_executor_prompt(state: AgentState) -> str:
    """Constructs the data-rich prompt for the Executor agent."""
    sections = [
        f"USER REQUEST: {state.user_query}",
        f"PERIOD: {state.period}",
        f"\nEXECUTION PLAN:\n" + "\n".join(f"  {i+1}. {s}" for i, s in enumerate(state.task_plan)),
        f"\nDATA RETRIEVED:\n{state.data_summary}",
    ]

    # Inject top datasets (truncated for context window)
    for key, dataset in state.retrieved_data.items():
        if isinstance(dataset, dict) and "records" in dataset:
            records = dataset["records"][:20]  # first 20 records
            sections.append(
                f"\n--- {dataset.get('source', key).upper()} ---\n"
                + json.dumps(records, indent=2, default=str)[:3000]
            )

    # Inject policy context
    if state.policy_context:
        sections.append("\n--- ACCOUNTING POLICIES (for grounding) ---")
        for ctx in state.policy_context[:2]:  # top 2 policies
            sections.append(ctx[:800])

    return "\n".join(sections)


def executor_agent(state: AgentState) -> AgentState:
    """
    Core analysis engine. Generates reconciliation findings, journal entries,
    variance narratives, or anomaly reports based on retrieved data.
    """
    t0 = time.time()
    llm = _llm(temperature=0.15)

    prompt = _build_executor_prompt(state)

    try:
        response = llm.invoke([
            SystemMessage(content=EXECUTOR_SYSTEM),
            HumanMessage(content=prompt),
        ])
        analysis = response.content.strip()
    except Exception as e:
        analysis = f"Executor error: {e}. Please verify Ollama is running: `ollama serve`"

    state.analysis_result = analysis
    state.narrative = analysis

    # Parse journal entries if present (look for debit/credit table markers)
    if "debit" in analysis.lower() and "credit" in analysis.lower():
        state.journal_entries = _extract_journal_entries(analysis)

    state.audit_log.append(_audit(
        agent=AgentRole.EXECUTOR.value,
        action=f"execute_{state.task_type.value}",
        inputs={"task_type": state.task_type.value, "data_keys": list(state.retrieved_data.keys())},
        reasoning=f"Executed {state.task_type.value} analysis using {len(state.retrieved_data)} datasets",
        output=analysis[:500] + "..." if len(analysis) > 500 else analysis,
        confidence=0.88,
    ))

    state.processing_ms += (time.time() - t0) * 1000
    return state


def _extract_journal_entries(text: str) -> list[dict]:
    """
    Best-effort extraction of journal entry lines from LLM output.
    Looks for patterns like 'Dr Account $amount' or table rows.
    """
    entries = []
    lines = text.split("\n")
    for line in lines:
        line_lower = line.lower().strip()
        if line_lower.startswith(("dr ", "cr ", "debit ", "credit ")):
            is_debit = line_lower.startswith(("dr ", "debit "))
            entries.append({
                "type": "Debit" if is_debit else "Credit",
                "description": line.strip(),
                "raw": line,
            })
    return entries


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 4 — CRITIC (SOX Review + Confidence Scoring)
# ═══════════════════════════════════════════════════════════════════════════════

CRITIC_SYSTEM = """You are the Critic Agent for FinClose AI — the final SOX compliance and quality gate.

Your role is to independently review the Executor's analysis and:

1. SOX CONTROL REVIEW — Check for:
   - Self-approval (same preparer and approver) → [SOX: SELF_APPROVAL]
   - Missing approver on manual entries → [SOX: MISSING_APPROVER]
   - Unbalanced journal entries (debits ≠ credits) → [SOX: UNBALANCED_ENTRY]
   - Weekend/holiday postings without approval → [SOX: WEEKEND_POSTING]
   - Prior period adjustments → [SOX: PRIOR_PERIOD_POSTING]
   - Round-number manual entries over $50K → [SOX: ROUND_NUMBER_MANUAL]
   - Approval threshold violations (per policy POL-001) → [SOX: THRESHOLD_BREACH]

2. ACCURACY REVIEW — Verify:
   - All dollar amounts cited match the source data
   - Journal entries balance (total debits = total credits)
   - Account codes are valid and pairings make sense
   - Percentages are mathematically correct

3. COMPLETENESS REVIEW — Check:
   - All material variances (>10%) have explanations
   - All reconciling differences >$50K are escalated
   - Policy citations are accurate

4. VERDICT — Issue one of:
   - APPROVED: Analysis is accurate, complete, and SOX-compliant
   - FLAGGED: Analysis is usable but has issues requiring management attention
   - REJECTED: Material errors or SOX violations requiring rework

Respond with:
VERDICT: [APPROVED|FLAGGED|REJECTED]
CONFIDENCE: [0.0-1.0]
SOX_FLAGS: [comma-separated list of flag codes, or NONE]
ISSUES: [bullet list of specific issues found, or "None identified"]
CITATIONS: [list of policy/data sources that support the review]
SUMMARY: [2-3 sentence summary of the review findings]"""


def critic_agent(state: AgentState) -> AgentState:
    """
    Independent SOX compliance review and quality gate.
    Reviews the Executor's output against policy and data — never trusts, always verifies.
    Issues APPROVED / FLAGGED / REJECTED verdict.
    """
    t0 = time.time()

    # Short-circuit if Executor failed — don't fabricate a verdict on error text
    if state.analysis_result.startswith("Executor error") or state.errors:
        err_msg = state.errors[0] if state.errors else state.analysis_result
        state.critic_verdict   = "REJECTED"
        state.confidence_score = 0.0
        state.sox_flags        = []
        state.sox_flag_details = []
        state.final_response   = (
            f"PIPELINE ERROR\n\n"
            f"The Executor agent could not complete analysis:\n{err_msg}\n\n"
            f"Verify Ollama is running: ollama serve && ollama pull mistral"
        )
        state.audit_log.append(_audit(
            agent=AgentRole.CRITIC.value,
            action="sox_review",
            inputs={"error": err_msg[:100]},
            reasoning="Executor failed — REJECTED without LLM review",
            output="Pipeline error — manual review required",
            confidence=0.0,
        ))
        state.processing_ms += (time.time() - t0) * 1000
        return state

    llm = _llm(temperature=0.0)  # Zero temperature — deterministic compliance review

    # Also run rule-based SOX checks on raw data (LLM-independent)
    rule_based_flags = _run_sox_rule_checks(state)

    prompt = f"""EXECUTOR ANALYSIS TO REVIEW:
{state.analysis_result[:3000]}

PERIOD: {state.period}
TASK TYPE: {state.task_type.value}

RULE-BASED SOX FINDINGS (already detected):
{json.dumps(rule_based_flags, indent=2)}

DATA SOURCES USED:
{chr(10).join(state.citations)}

Review the analysis for accuracy, SOX compliance, and completeness."""

    try:
        response = llm.invoke([
            SystemMessage(content=CRITIC_SYSTEM),
            HumanMessage(content=prompt),
        ])
        review = response.content.strip()
    except Exception as e:
        review = f"VERDICT: FLAGGED\nCONFIDENCE: 0.5\nSOX_FLAGS: NONE\nISSUES: Critic unavailable: {e}\nSUMMARY: Manual review required."

    # Parse structured critic response
    verdict     = _extract_field(review, "VERDICT",     "FLAGGED")
    confidence  = float(_extract_field(review, "CONFIDENCE", "0.75"))
    sox_raw     = _extract_field(review, "SOX_FLAGS",   "NONE")
    issues      = _extract_field(review, "ISSUES",      "None identified")
    summary     = _extract_field(review, "SUMMARY",     "Review complete.")

    state.critic_verdict   = verdict
    state.confidence_score = confidence

    # Build a detail map: flag_name → description (rule-based have richer detail)
    flag_detail_map: dict[str, str] = {}
    for rb in rule_based_flags:
        flag_detail_map[rb["flag"]] = rb["detail"]
    for llm_flag in [f.strip() for f in sox_raw.split(",") if f.strip() and f.strip() != "NONE"]:
        if llm_flag not in flag_detail_map:
            flag_detail_map[llm_flag] = "Detected by compliance review"

    # Build validated SoxFlag list and matching details in the same order
    state.sox_flags = []
    state.sox_flag_details = []
    for flag_str, detail in flag_detail_map.items():
        try:
            state.sox_flags.append(SoxFlag(flag_str))
            state.sox_flag_details.append(detail)
        except ValueError:
            pass  # Unknown flag type — skip

    # Build final response
    sox_block = ""
    if state.sox_flags:
        sox_block = f"\n\n⚠️  SOX FLAGS DETECTED: {', '.join(f.value for f in state.sox_flags)}"

    state.final_response = f"""### {state.task_type.value.upper().replace('_', ' ')} REPORT
**Period:** {state.period}  |  **Session:** {state.session_id}  |  **Prepared by:** {state.requested_by}

{state.analysis_result}

---

### CRITIC REVIEW

**Verdict:** {verdict}
**Confidence:** {confidence:.0%}
**Issues:** {issues}{sox_block}
**Summary:** {summary}

---

### DATA PROVENANCE

{chr(10).join(f'  [{i+1}] {c}' for i, c in enumerate(state.citations))}"""

    state.audit_log.append(_audit(
        agent=AgentRole.CRITIC.value,
        action="sox_review",
        inputs={"executor_output_hash": _hash_inputs({"text": state.analysis_result[:200]})},
        reasoning=f"Independent SOX review: {verdict} | {len(state.sox_flags)} flags",
        output=summary,
        sox_flags=[f.value for f in state.sox_flags],
        citations=state.citations,
        confidence=confidence,
    ))

    state.processing_ms += (time.time() - t0) * 1000
    return state


def _extract_field(text: str, field: str, default: str) -> str:
    """Extract a labeled field from structured LLM output."""
    for line in text.split("\n"):
        if line.strip().upper().startswith(field.upper() + ":"):
            return line.split(":", 1)[1].strip()
    return default


def _run_sox_rule_checks(state: AgentState) -> list[dict]:
    """
    Rule-based SOX control checks — deterministic, no LLM involved.
    These run independently of the LLM to provide objective compliance signals.
    """
    flags = []

    # Check anomaly data if retrieved
    if "anomalies" in state.retrieved_data:
        for record in state.retrieved_data["anomalies"].get("records", []):
            atype = record.get("anomaly_type")
            flag_map = {
                "self_approved":        SoxFlag.SELF_APPROVAL.value,
                "missing_approver":     SoxFlag.MISSING_APPROVER.value,
                "unbalanced_entry":     SoxFlag.UNBALANCED_ENTRY.value,
                "weekend_posting":      SoxFlag.WEEKEND_POSTING.value,
                "prior_period_posting": SoxFlag.PRIOR_PERIOD_POSTING.value,
                "round_number_manual":  SoxFlag.ROUND_NUMBER_MANUAL.value,
            }
            if atype in flag_map:
                flags.append({
                    "flag":    flag_map[atype],
                    "je_id":   record.get("je_id"),
                    "amount":  record.get("debit") or record.get("credit"),
                    "account": record.get("account_code"),
                    "detail":  f"{atype} on {record.get('je_id')} by {record.get('created_by')}",
                })

    # Check unbalanced entries
    if "unbalanced" in state.retrieved_data:
        count = state.retrieved_data["unbalanced"].get("unbalanced_count", 0)
        if count > 0:
            flags.append({
                "flag":   SoxFlag.UNBALANCED_ENTRY.value,
                "detail": f"{count} journal entries do not balance",
            })

    # Check variance thresholds
    if "variance_analysis" in state.retrieved_data:
        breaches = state.retrieved_data["variance_analysis"].get("threshold_breaches", 0)
        if breaches > 0:
            flags.append({
                "flag":   SoxFlag.THRESHOLD_BREACH.value,
                "detail": f"{breaches} accounts exceed 10% budget variance threshold",
            })

    return flags
