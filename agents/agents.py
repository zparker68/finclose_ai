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
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from core.state import AgentState, AgentRole, AuditEntry, SoxFlag, TaskType
from core import db_tools
from core.prompts import get_prompt, get_version

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
           confidence: float = 1.0,
           prompt_version: str = "") -> AuditEntry:
    return AuditEntry(
        timestamp=datetime.now(timezone.utc).isoformat(),
        agent=agent,
        action=action,
        input_hash=_hash_inputs(inputs),
        reasoning=reasoning,
        output=output,
        sox_flags=sox_flags or [],
        citations=citations or [],
        confidence=confidence,
        prompt_version=prompt_version,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT 1 — PLANNER
# ═══════════════════════════════════════════════════════════════════════════════

PLANNER_SYSTEM = get_prompt("planner")


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
        prompt_version=get_version("planner"),
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

EXECUTOR_SYSTEM = get_prompt("executor")


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
        prompt_version=get_version("executor"),
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

CRITIC_SYSTEM = get_prompt("critic")


# ── Numeric Claim Verifier ────────────────────────────────────────────────────
# Deterministic layer between Executor and Critic.
# Extracts dollar amounts from the Executor's text and cross-checks them
# against actual values in retrieved_data — no LLM involved.

# Three patterns, all require >= $1,000 threshold in _extract_dollar_claims:
#   1. Explicit $: $285,000  $1.2M  $285K
#   2. Comma-formatted: 285,000  1,234,567  (Mistral sometimes omits $)
#   3. Raw float: 974654.96  75787.75  (Mistral table output — no $ or commas)
_DOLLAR_RE = re.compile(
    r'\$\s*([\d,]+(?:\.\d+)?)\s*([KMBkmb](?:illion)?)?'              # group 1,2
    r'|(?<![.\d\-])([\d]{1,3}(?:,\d{3})+(?:\.\d+)?)'                 # group 3 (comma-fmt)
    r'|(?<![.\d\-])(\d{4,}\.\d+)(?![,\d])',                           # group 4 (raw float)
    re.IGNORECASE,
)

# Fields to harvest as ground-truth numeric values from each retrieved dataset
_NUMERIC_FIELDS = {
    "debit", "credit", "amount", "invoice_amount", "open_amount",
    "open_balance", "gl_balance", "sub_ledger_balance", "difference",
    "budget_amount", "actual_amount", "vs_budget_amt", "variance_amt",
    "prior_balance", "net_activity", "ending_balance",
    "total_debits", "total_credits", "imbalance",
    "total_open_payables", "total_accrual_amount", "total_unexplained_difference",
}


def _extract_dollar_claims(text: str) -> list[tuple[str, float]]:
    """Return (raw_string, normalized_float) for every dollar amount in text.
    Handles $285,000 / 285,000 / 974654.96 (raw float from Mistral tables)."""
    results = []
    for m in _DOLLAR_RE.finditer(text):
        raw = m.group(0).strip()
        # g1+g2: explicit $;  g3: comma-formatted;  g4: raw float
        num_str = m.group(1) or m.group(3) or m.group(4)
        suffix  = (m.group(2) or "").upper()
        if not num_str:
            continue
        try:
            num = float(num_str.replace(",", ""))
        except ValueError:
            continue
        if suffix.startswith("K"):
            num *= 1_000
        elif suffix.startswith("M"):
            num *= 1_000_000
        elif suffix.startswith("B"):
            num *= 1_000_000_000
        if num >= 1_000:    # ignore trivially small amounts
            results.append((raw, num))
    return results


def _flatten_data_values(retrieved_data: dict) -> list[float]:
    """
    Harvest all numeric ground-truth values from the pipeline retrieved data.
    Checks both dataset-level summary fields and per-record fields.
    """
    values: list[float] = []
    for dataset in retrieved_data.values():
        if not isinstance(dataset, dict):
            continue
        # Dataset-level summary totals (e.g. total_open_payables)
        for k, v in dataset.items():
            if k in _NUMERIC_FIELDS and isinstance(v, (int, float)) and v > 0:
                values.append(float(v))
        # Per-record fields
        for rec in dataset.get("records", []):
            if not isinstance(rec, dict):
                continue
            for k, v in rec.items():
                if k in _NUMERIC_FIELDS and isinstance(v, (int, float)) and v and v > 0:
                    values.append(float(v))
    return values


def _verify_numeric_claims(state: AgentState) -> dict:
    """
    Cross-check every dollar amount in the Executor's analysis against the
    actual numbers in retrieved_data.

    Verdict per claim:
      verified   — within 15% of a known data value (rounding / presentation)
      suspicious — 15–50% off nearest known value (possible rounding error)
      mismatch   — >50% off every known value (likely hallucination)

    Returns a summary dict stored in state.numeric_verification.
    The Critic agent receives this summary before it writes its verdict,
    so it cannot be fooled by confident phrasing around wrong numbers.
    """
    claims     = _extract_dollar_claims(state.analysis_result)
    data_vals  = _flatten_data_values(state.retrieved_data)

    if not claims:
        return {"claims_extracted": 0, "verified": 0, "suspicious": 0,
                "mismatches": 0, "details": [], "status": "no_claims"}

    if not data_vals:
        return {"claims_extracted": len(claims), "verified": 0,
                "suspicious": len(claims), "mismatches": 0,
                "details": [], "status": "no_data_to_compare"}

    verified_n = suspicious_n = mismatch_n = 0
    details: list[dict] = []

    for raw, claim_val in claims:
        closest   = min(data_vals, key=lambda x: abs(x - claim_val))
        denom     = max(abs(closest), abs(claim_val))
        delta_pct = abs(claim_val - closest) / denom * 100 if denom else 100.0

        if delta_pct <= 15:
            verdict_tag = "verified"
            verified_n += 1
        elif delta_pct <= 50:
            verdict_tag = "suspicious"
            suspicious_n += 1
        else:
            verdict_tag = "mismatch"
            mismatch_n += 1

        details.append({
            "claim":     raw,
            "value":     claim_val,
            "closest":   closest,
            "delta_pct": round(delta_pct, 1),
            "verdict":   verdict_tag,
        })

    total   = verified_n + suspicious_n + mismatch_n
    status  = ("all_verified" if mismatch_n == 0 and suspicious_n == 0
               else "mismatches_found" if mismatch_n > 0
               else "suspicious_found")

    return {
        "claims_extracted": len(claims),
        "claims_checked":   total,
        "verified":         verified_n,
        "suspicious":       suspicious_n,
        "mismatches":       mismatch_n,
        "details":          details,          # full list for audit log
        "status":           status,
    }


_CONFIDENCE_WEIGHTS = {
    "data_completeness":    0.25,
    "policy_alignment":     0.15,
    "arithmetic_integrity": 0.30,
    "anomaly_coverage":     0.20,
    "llm_coherence":        0.10,
}

# Expected retrieval keys per task type (used to score data completeness)
_TASK_EXPECTED_KEYS: dict[TaskType, list[str]] = {
    TaskType.ANOMALY_DETECTION: ["anomalies", "gl_transactions"],
    TaskType.VARIANCE_ANALYSIS: ["variance_analysis"],
    TaskType.RECONCILIATION:    ["reconciliations"],
    TaskType.ACCRUAL_REVIEW:    ["accruals"],
    TaskType.JOURNAL_ENTRY:     ["gl_transactions", "accruals"],
    TaskType.CLOSE_CHECKLIST:   ["reconciliations", "accruals", "variance_analysis"],
}


def _compute_confidence_breakdown(
    state: AgentState,
    rule_based_flags: list[dict],
    llm_confidence: float,
) -> dict[str, float]:
    """
    Computes 5 deterministic confidence dimensions from raw pipeline data.
    Runs BEFORE the LLM verdict is accepted, so hallucinated Executor output
    cannot inflate the score through confident phrasing alone.

    Returns a dict of dimension_name → [0.0, 1.0] score.
    """
    scores: dict[str, float] = {}

    # ── 1. Data Completeness ───────────────────────────────────────────────
    # How many expected data sources came back non-empty?
    expected = _TASK_EXPECTED_KEYS.get(state.task_type, [])
    if not expected:
        scores["data_completeness"] = 1.0  # general query — no hard expectation
    else:
        filled = 0
        for key in expected:
            dataset = state.retrieved_data.get(key, {})
            n = dataset.get("record_count") or len(dataset.get("records", []))
            if n > 0:
                filled += 1
        scores["data_completeness"] = filled / len(expected)

    # ── 2. Policy Alignment ────────────────────────────────────────────────
    # Were any accounting policies retrieved to ground the analysis?
    n_policies = len(state.policy_context)
    scores["policy_alignment"] = min(1.0, n_policies / 2.0)  # 2+ docs = full score

    # ── 3. Arithmetic Integrity ────────────────────────────────────────────
    # Two sub-signals, both deterministic:
    #   a) Unbalanced JEs — each docks 25% (hard SOX control failure)
    #   b) Numeric claim mismatches — fraction of Executor's dollar claims
    #      that don't match any retrieved data value within 50%
    unbalanced = 0
    if "unbalanced" in state.retrieved_data:
        unbalanced = state.retrieved_data["unbalanced"].get("unbalanced_count", 0)
    if unbalanced == 0:
        for rb in rule_based_flags:
            if rb.get("flag") == SoxFlag.UNBALANCED_ENTRY.value:
                unbalanced += 1

    verif        = state.numeric_verification
    checked      = verif.get("claims_checked", 0)
    mismatch_n   = verif.get("mismatches", 0)
    mismatch_penalty = (mismatch_n / checked) * 0.5 if checked > 0 else 0.0

    scores["arithmetic_integrity"] = max(
        0.0, 1.0 - (unbalanced * 0.25) - mismatch_penalty
    )

    # ── 4. Anomaly Coverage ────────────────────────────────────────────────
    # What fraction of rule-based flags have their key identifiers
    # (JE-ID or flag label) mentioned anywhere in the Executor's analysis?
    if not rule_based_flags:
        scores["anomaly_coverage"] = 1.0
    else:
        analysis_lower = state.analysis_result.lower()
        mentioned = 0
        for rb in rule_based_flags:
            je_id = (rb.get("je_id") or "").lower()
            label = rb.get("flag", "").lower().replace("_", " ")
            if (je_id and je_id in analysis_lower) or (label and label in analysis_lower):
                mentioned += 1
        scores["anomaly_coverage"] = mentioned / len(rule_based_flags)

    # ── 5. LLM Coherence (deliberately downweighted) ──────────────────────
    # The Critic LLM's own confidence claim.  Only 10% weight because it is
    # susceptible to confident hallucination by the same LLM family.
    scores["llm_coherence"] = max(0.0, min(1.0, llm_confidence))

    return scores


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

    # ── Deterministic checks (LLM-independent) ────────────────────────────
    rule_based_flags = _run_sox_rule_checks(state)

    # Numeric claim verifier: cross-check Executor's dollar amounts against
    # retrieved_data BEFORE passing anything to the Critic LLM.
    verification = _verify_numeric_claims(state)
    state.numeric_verification = verification

    # Build human-readable verification summary for the Critic prompt
    verif_lines = [
        f"NUMERIC CLAIM VERIFICATION (deterministic — pre-LLM):",
        f"  Dollar claims extracted from analysis : {verification['claims_extracted']}",
        f"  Verified against source data (≤15% off): {verification['verified']}",
        f"  Suspicious (15–50% off nearest value)  : {verification['suspicious']}",
        f"  Flagged mismatches (>50% off)          : {verification['mismatches']}",
    ]
    for d in verification.get("details", []):
        if d["verdict"] in ("mismatch", "suspicious"):
            verif_lines.append(
                f"  ⚠ {d['verdict'].upper()}: {d['claim']} → "
                f"closest data value ${d['closest']:,.0f} ({d['delta_pct']:.0f}% off)"
            )
    verif_block = "\n".join(verif_lines)

    prompt = f"""EXECUTOR ANALYSIS TO REVIEW:
{state.analysis_result[:3000]}

PERIOD: {state.period}
TASK TYPE: {state.task_type.value}

{verif_block}

RULE-BASED SOX FINDINGS (already detected):
{json.dumps(rule_based_flags, indent=2)}

DATA SOURCES USED:
{chr(10).join(state.citations)}

Review the analysis for accuracy, SOX compliance, and completeness.
Pay particular attention to any MISMATCH or SUSPICIOUS numeric claims above."""

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

    state.critic_verdict = verdict

    # Compute 5-dimension confidence breakdown (deterministic; LLM is only 10%)
    breakdown = _compute_confidence_breakdown(state, rule_based_flags, confidence)
    state.confidence_breakdown = breakdown
    state.confidence_score = round(
        sum(breakdown[k] * _CONFIDENCE_WEIGHTS[k] for k in _CONFIDENCE_WEIGHTS), 3
    )

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

    # Build confidence breakdown summary line
    dim_labels = {
        "data_completeness":    "Data",
        "policy_alignment":     "Policy",
        "arithmetic_integrity": "Arithmetic",
        "anomaly_coverage":     "Coverage",
        "llm_coherence":        "AI",
    }
    breakdown_line = "  |  ".join(
        f"{dim_labels[k]}: {breakdown[k]*100:.0f}%"
        for k in dim_labels if k in breakdown
    )

    state.final_response = f"""### {state.task_type.value.upper().replace('_', ' ')} REPORT
**Period:** {state.period}  |  **Session:** {state.session_id}  |  **Prepared by:** {state.requested_by}

{state.analysis_result}

---

### CRITIC REVIEW

**Verdict:** {verdict}
**Composite Confidence:** {state.confidence_score:.0%}
**Breakdown:** {breakdown_line}
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
        prompt_version=get_version("critic"),
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
