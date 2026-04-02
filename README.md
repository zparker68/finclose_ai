# FinClose AI

<div align="center">

```
███████╗██╗███╗   ██╗ ██████╗██╗      ██████╗ ███████╗███████╗     █████╗ ██╗
██╔════╝██║████╗  ██║██╔════╝██║     ██╔═══██╗██╔════╝██╔════╝    ██╔══██╗██║
█████╗  ██║██╔██╗ ██║██║     ██║     ██║   ██║███████╗█████╗      ███████║██║
██╔══╝  ██║██║╚██╗██║██║     ██║     ██║   ██║╚════██║██╔══╝      ██╔══██║██║
██║     ██║██║ ╚████║╚██████╗███████╗╚██████╔╝███████║███████╗    ██║  ██║██║
╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝ ╚═════╝ ╚══════╝╚══════╝    ╚═╝  ╚═╝╚═╝
```

**Production-grade multi-agent AI system for enterprise financial close automation**

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-FF6B35?style=flat-square)](https://langchain-ai.github.io/langgraph/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLM-black?style=flat-square)](https://ollama.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-REST_API-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![SQLite](https://img.shields.io/badge/Oracle_GL-Simulated-003B57?style=flat-square&logo=sqlite)](https://sqlite.org)
[![SOX](https://img.shields.io/badge/SOX-Compliant_Audit_Trail-2ECC71?style=flat-square)]()
[![Offline](https://img.shields.io/badge/Data-100%25_Offline-E74C3C?style=flat-square)]()

*Automates reconciliation · journal entries · variance analysis · anomaly detection — entirely offline*

</div>

---

## What Is This?

FinClose AI is an end-to-end multi-agent system that automates the most labour-intensive tasks in a corporate financial close cycle. It mirrors the exact accounting AI initiatives described by leading gaming and entertainment companies, including workflows for Oracle Fusion GL, Blackline reconciliations, HFM variance reporting, and SOX internal controls.

**The system runs 100% offline.** No financial data ever leaves your machine — a critical requirement in regulated industries (gaming, healthcare, financial services) where sensitive GL data cannot be transmitted to third-party cloud LLM APIs.

This is not a demo. It is a functioning accounting automation engine backed by realistic enterprise data, a full audit trail, SOX-aware control checks, and a deterministic numeric claim verifier that catches LLM hallucinations before they reach the compliance gate.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FINCLOSE AI — SYSTEM ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────┐
  │  ENTERPRISE DATA LAYER  (simulated Oracle / Blackline / HFM integrations)│
  │                                                                          │
  │   ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
  │   │ Oracle GL   │  │  Blackline   │  │  Oracle AP   │  │  Oracle AR  │ │
  │   │ Journal     │  │  Account     │  │  Invoice     │  │  Aging      │ │
  │   │ Entries     │  │  Recs        │  │  Listing     │  │  Report     │ │
  │   │ 220 rows    │  │  15 recs     │  │  120 inv.    │  │  80 recs    │ │
  │   └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ │
  │          └────────────────┴──────────────────┴──────────────────┘        │
  │                                    │                                     │
  │                           ┌────────▼────────┐                           │
  │                           │  SQLite  +  ETL │  ← db_tools.py            │
  │                           │  Tool  Layer    │    (REST API simulation)   │
  │                           └────────┬────────┘                           │
  └────────────────────────────────────│────────────────────────────────────┘
                                       │
  ┌────────────────────────────────────│────────────────────────────────────┐
  │  LANGGRAPH AGENT PIPELINE          │                                    │
  │                                    ▼                                    │
  │   ╔═══════════════╗     ╔══════════════════╗                           │
  │   ║  USER QUERY   ║────▶║  1. PLANNER      ║                           │
  │   ╚═══════════════╝     ║  Classify task   ║                           │
  │                         ║  Write plan      ║                           │
  │                         ║  Select tools    ║                           │
  │                         ╚════════╤═════════╝                           │
  │                                  ▼                                      │
  │                         ╔══════════════════╗     ┌──────────────────┐  │
  │                         ║  2. RETRIEVER    ║────▶│  Policy Library  │  │
  │                         ║  Pull DB data    ║     │  (RAG context)   │  │
  │                         ║  Load policies   ║     │  5 GAAP/SOX docs │  │
  │                         ║  Hash inputs     ║     └──────────────────┘  │
  │                         ╚════════╤═════════╝                           │
  │                                  ▼                                      │
  │                         ╔══════════════════╗     ┌──────────────────┐  │
  │                         ║  3. EXECUTOR     ║────▶│  Ollama (Local)  │  │
  │                         ║  Reconcile       ║     │  Mistral 7B Q4   │  │
  │                         ║  Generate JEs    ║     │  ~4.5GB RAM      │  │
  │                         ║  Variance calc   ║     └──────────────────┘  │
  │                         ║  Write narrative ║                           │
  │                         ╚════════╤═════════╝                           │
  │                                  │                                      │
  │                         ┌────────▼────────────────────────────────┐    │
  │                         │  NUMERIC CLAIM VERIFIER  (deterministic) │    │
  │                         │  Extracts dollar amounts from Executor   │    │
  │                         │  output and cross-checks every value     │    │
  │                         │  against retrieved_data before the LLM   │    │
  │                         │  Critic sees the analysis.               │    │
  │                         │  Verified ✓ · Suspicious ● · Mismatch ⚠ │    │
  │                         └────────┬────────────────────────────────┘    │
  │                                  ▼                                      │
  │                         ╔══════════════════╗                           │
  │                         ║  4. CRITIC       ║  ← SOX Gate               │
  │                         ║  Rule-based SOX  ║                           │
  │                         ║  5-dim confidence║                           │
  │                         ║  Math verify     ║                           │
  │                         ║  APPROVE/FLAG/   ║                           │
  │                         ║  REJECT          ║                           │
  │                         ╚════════╤═════════╝                           │
  └──────────────────────────────────│────────────────────────────────────┘
                                     │
  ┌──────────────────────────────────│────────────────────────────────────┐
  │  OUTPUT LAYER                    ▼                                    │
  │                                                                        │
  │   ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
  │   │  Analysis Report │  │  SOX Audit Log  │  │  Streamlit UI       │ │
  │   │  APPROVED ✅     │  │  JSON + PBC     │  │  Confidence bars    │ │
  │   │  FLAGGED  ⚠️     │  │  SHA-256 hashes │  │  Drill-down cards   │ │
  │   │  REJECTED ❌     │  │  Prompt version │  │  Plotly charts      │ │
  │   └──────────────────┘  └─────────────────┘  └─────────────────────┘ │
  │                                                                        │
  │   ┌────────────────────────────────────────────────────────────────┐  │
  │   │  FastAPI REST Layer  (api/server.py)                           │  │
  │   │  JWT Auth · RBAC (admin/analyst) · Correlation IDs (X-Req-ID)  │  │
  │   │  POST /run   GET /demo/{task}   GET /audit/{id}/export/pbc     │  │
  │   │  GET /metrics/dashboard   GET /audit/requests                  │  │
  │   │  Per-request audit log written to audit_requests.jsonl         │  │
  │   └────────────────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Roles

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENT RESPONSIBILITIES                              │
├────────────────┬────────────────────────────────────────────────────────────┤
│  PLANNER       │  Reads the user query. Classifies it into one of 7 task   │
│                │  types. Writes a step-by-step execution plan. Selects      │
│                │  which DB tables and policies are needed.                  │
│                │  Model role: Task router + orchestrator                    │
├────────────────┼────────────────────────────────────────────────────────────┤
│  RETRIEVER     │  Pure data agent — no LLM call. Executes structured SQL   │
│                │  queries against the enterprise data layer based on the    │
│                │  Planner's routing. Pulls policy documents for RAG         │
│                │  grounding. Produces tamper-evident data hashes (SHA-256). │
│                │  Model role: Data access layer                             │
├────────────────┼────────────────────────────────────────────────────────────┤
│  EXECUTOR      │  The core analysis engine. Receives structured data +      │
│                │  policy context. Generates reconciliation findings,        │
│                │  balanced journal entries, variance narratives, or         │
│                │  anomaly reports. Writes CFO-grade output with explicit    │
│                │  dollar amounts and policy citations.                      │
│                │  Model role: Senior accountant + analyst                  │
├────────────────┼────────────────────────────────────────────────────────────┤
│  CRITIC        │  Independent SOX compliance review. Runs deterministic    │
│                │  rule-based checks AND numeric claim verification before   │
│                │  any LLM review. Emits a 5-dimension confidence breakdown  │
│                │  (not a single scalar) so reviewers understand exactly     │
│                │  what the system is and isn't certain about.              │
│                │  Issues APPROVED / FLAGGED / REJECTED verdict.            │
│                │  Model role: Internal audit + SOX reviewer                │
└────────────────┴────────────────────────────────────────────────────────────┘
```

---

## Confidence Scoring — 5-Dimension Breakdown

A single LLM confidence scalar is insufficient in a regulated environment: a manager who sees "75% confident" with a SOX flag has no idea *why* the system is uncertain. FinClose AI replaces the scalar with five deterministic dimensions, four of which run entirely without the LLM.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CONFIDENCE BREAKDOWN — WEIGHTS                          │
├──────────────────────────┬────────┬────────────────────────────────────────┤
│  Dimension               │ Weight │  How it's computed                     │
├──────────────────────────┼────────┼────────────────────────────────────────┤
│  Data Completeness       │  25%   │  Fraction of expected data sources     │
│                          │        │  (GL, AP, recs…) that returned records │
│                          │        │  for the task type. Deterministic.     │
├──────────────────────────┼────────┼────────────────────────────────────────┤
│  Policy Alignment        │  15%   │  Number of accounting policy documents │
│                          │        │  retrieved for RAG grounding.          │
│                          │        │  2+ docs = 100%. Deterministic.        │
├──────────────────────────┼────────┼────────────────────────────────────────┤
│  Arithmetic Integrity    │  30%   │  Penalises unbalanced JEs (-25% each)  │
│                          │        │  AND numeric claim mismatches from the │
│                          │        │  verifier (-50% × mismatch rate).      │
│                          │        │  Deterministic. Highest weight.        │
├──────────────────────────┼────────┼────────────────────────────────────────┤
│  Anomaly Coverage        │  20%   │  Fraction of rule-based SOX flags      │
│                          │        │  whose JE-IDs appear in the Executor's │
│                          │        │  analysis. Deterministic.              │
├──────────────────────────┼────────┼────────────────────────────────────────┤
│  AI Coherence            │  10%   │  The LLM Critic's own confidence claim.│
│                          │        │  Deliberately downweighted — a         │
│                          │        │  confidently hallucinating Executor    │
│                          │        │  can fool the Critic LLM but cannot    │
│                          │        │  move the composite score significantly.│
└──────────────────────────┴────────┴────────────────────────────────────────┘

  Composite = Σ(dimension × weight)

  Example: FLAGGED run with 2 unbalanced JEs, 1 missing data source,
           1 SOX flag not addressed in analysis:
    Data Completeness    50%  × 0.25 = 0.125
    Policy Alignment    100%  × 0.15 = 0.150
    Arithmetic Integrity 50%  × 0.30 = 0.150  ← 2 unbalanced JEs
    Anomaly Coverage     67%  × 0.20 = 0.134
    AI Coherence         95%  × 0.10 = 0.095
    ─────────────────────────────────────────
    Composite confidence:              65%     (Manual review band)
```

The breakdown bars are displayed in the Verdict panel of the Streamlit UI, showing each dimension independently so a director can see "Math Verified: 50%" and immediately understand there are arithmetic integrity issues — without needing to interpret a black-box percentage.

---

## Numeric Claim Verifier

The LLM Critic reviewing the LLM Executor's output is a "second opinion from someone who read the same book" — if the Executor hallucinates a confident number, the Critic may not catch it because both models share the same training biases.

FinClose AI solves this with a **deterministic numeric claim verifier** that runs between the Executor and Critic:

```
  Executor output
       │
       ▼
  ┌────────────────────────────────────────────────────────┐
  │  NUMERIC CLAIM VERIFIER                                │
  │                                                        │
  │  1. Extract all dollar amounts from analysis text      │
  │     Handles: $285,000  285,000  974654.96  $1.2M       │
  │                                                        │
  │  2. Flatten all numeric values from retrieved_data     │
  │     GL debits/credits, variance amounts, AP/AR         │
  │     balances, accrual amounts, dataset totals          │
  │                                                        │
  │  3. For each extracted claim, find nearest data value  │
  │     and compute relative delta:                        │
  │       ≤15% off  → verified   ✓  (rounding/format)     │
  │     15–50% off  → suspicious ●  (worth investigating)  │
  │      >50% off  → mismatch   ⚠  (likely hallucination) │
  │                                                        │
  │  4. Inject full verification report into Critic prompt │
  │     before LLM review runs — Critic cannot be fooled  │
  │     by confident phrasing around a wrong number        │
  └────────────────────────────────────────────────────────┘
       │
       ▼
  Critic prompt includes:
    "MISMATCH: $4.2M → closest data value $1.1M (73% off)"
       │
       ▼
  Mismatch rate feeds Arithmetic Integrity confidence dim
```

The verifier badge appears in the Verdict panel: `⚠ 7/10 verified · 2 suspicious · 1 mismatch`

---

## SOX Flag Drill-Downs

Each SOX flag in the UI is an expandable panel. Rather than raw data tables, it shows **executive-readable memo cards** — one card per source Oracle GL record:

```
  ▲ SELF_APPROVAL  (expanded)
  ┌────────────────────────────────────────────────────────────────┐
  │ Plain-English explanation:                                     │
  │ "A journal entry was approved by the same person who          │
  │  prepared it — this violates the segregation of duties        │
  │  control required by SOX Section 404."                        │
  │                                                               │
  │ Required Action: Reverse and repost with independent approval │
  │                                                               │
  │  Oracle GL — 2 flagged record(s)                              │
  │  ┌──────────────────────────────────────────────────┐         │
  │  │ JE-202412-00028              Dec 28, 2024         │         │
  │  │ Accounts Receivable - Trade                      │         │
  │  │ Amount: $249,998.54 Dr                           │         │
  │  │ Prepared by: jsmith                              │         │
  │  │ Approved by: jsmith  ⚠ Same person as preparer  │         │  ← highlighted in amber
  │  └──────────────────────────────────────────────────┘         │
  │                                                               │
  │  Source hash (SHA-256): a3f8c2d19e4b…                        │  ← fine print for auditors
  └────────────────────────────────────────────────────────────────┘
```

The violation-specific field is highlighted (approver for SELF_APPROVAL, date for WEEKEND_POSTING, etc.). The SHA-256 hash of the exact queried dataset is shown as fine print — present for auditors who need it, invisible to executives who don't.

---

## Data Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SIMULATED ENTERPRISE DATA LAYER                          │
│                         Period: December 2024                               │
└─────────────────────────────────────────────────────────────────────────────┘

  ORACLE FUSION GL                    BLACKLINE
  ─────────────────                   ─────────────────────────────────────
  gl_transactions                     reconciliations
  ┌──────────────────────────────┐    ┌────────────────────────────────────┐
  │ je_id          VARCHAR       │    │ recon_id        VARCHAR            │
  │ period         VARCHAR       │    │ account_code    VARCHAR            │
  │ txn_date       DATE          │    │ gl_balance      DECIMAL            │
  │ account_code   VARCHAR  ─────┼───▶│ sub_ledger_bal  DECIMAL            │
  │ account_name   VARCHAR       │    │ difference      DECIMAL  ◄─── Key  │
  │ debit          DECIMAL       │    │ status          VARCHAR  ◄─── KPI  │
  │ credit         DECIMAL       │    │ preparer        VARCHAR            │
  │ entry_type     VARCHAR       │    │ reviewer        VARCHAR  ◄─ No     │
  │ created_by     VARCHAR  ┐    │    │ due_date        DATE        Self   │
  │ approved_by    VARCHAR  ┘SOX │    │ notes           TEXT       Review  │
  │ is_anomaly     BOOLEAN  ◄────┼────┤                                    │
  │ anomaly_type   VARCHAR       │    └────────────────────────────────────┘
  └──────────────────────────────┘
          │                            recon_items (110 supporting items)
          ▼                            ┌────────────────────────────────────┐
  chart_of_accounts                   │ item_id     • category             │
  39 accounts | 5 types               │ recon_id    • aging_days ◄─── KPI  │
  Asset/Liability/Equity              │ amount      • reference            │
  Revenue/Expense                     └────────────────────────────────────┘

  ORACLE FUSION AP                    ORACLE FUSION AR
  ─────────────────                   ──────────────────
  ap_invoices (120)                   ar_aging (80)
  ┌───────────────────────┐           ┌──────────────────────────┐
  │ vendor_name           │           │ customer_name            │
  │ invoice_amount        │           │ open_balance             │
  │ open_amount  ◄─── KPI │           │ aging_bucket ◄─── KPI   │
  │ status                │           │  Current / 31-60         │
  │ due_date              │           │  61-90 / 91-120 / 120+   │
  │ po_number             │           │ collection_status        │
  └───────────────────────┘           └──────────────────────────┘

  ORACLE GL — ACCRUALS (14)           HFM — VARIANCE ANALYSIS (10)
  ─────────────────────────           ────────────────────────────
  accruals                            variance_analysis
  ┌───────────────────────┐           ┌──────────────────────────┐
  │ description           │           │ budget_amount            │
  │ debit_account         │           │ actual_amount            │
  │ credit_account        │           │ vs_budget_pct ◄─── Key  │
  │ amount ◄───── $14.1M  │           │ threshold_breached       │
  │ reversal_period       │           │  (>10% = escalate)       │
  │ status ◄──── Pending? │           │ explanation_hint         │
  └───────────────────────┘           └──────────────────────────┘

  RAG KNOWLEDGE BASE
  ──────────────────
  policy_documents (5 documents)
  ┌────────────────────────────────────────────────────────────┐
  │  POL-001  Journal Entry Policy & Procedures                │
  │  POL-002  Account Reconciliation Policy                    │
  │  POL-003  Revenue Recognition Policy (ASC 606)             │
  │  POL-004  Accruals and Estimates Policy                    │
  │  POL-005  Close Calendar & Checklist — December 2024       │
  └────────────────────────────────────────────────────────────┘
  Chunked and retrieved by task type for policy-grounded output
```

---

## SOX Audit Trail

Every agent action generates an immutable audit entry. This is what makes the system viable in a regulated environment.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   SOX AUDIT TRAIL — ENTRY STRUCTURE                        │
└─────────────────────────────────────────────────────────────────────────────┘

  {
    "timestamp":      "2024-12-31T18:42:07.441+00:00",   ← UTC, always
    "agent":          "executor",                         ← attribution
    "action":         "execute_variance_analysis",        ← what happened
    "input_hash":     "a3f8c2d19e4b",                    ← SHA-256 of inputs
    "reasoning":      "Executed variance analysis using 2 datasets",
    "output":         "4 accounts exceed 10% threshold...",
    "sox_flags":      ["THRESHOLD_BREACH"],               ← compliance signals
    "citations":      ["Oracle/HFM Variance | 4 threshold breaches"],
    "confidence":     0.88,
    "prompt_version": "1.0.0"                            ← versioned prompt registry
  }

  ┌──────────────────────────────────────────────────────────┐
  │  GUARANTEED PROPERTIES                                   │
  │                                                          │
  │  ✅  Append-only — entries are never modified           │
  │  ✅  Input hashing — SHA-256 detects data tampering     │
  │  ✅  Agent attribution — who did what, when             │
  │  ✅  Policy citations — every finding references source  │
  │  ✅  SOX flags propagate — Planner→Executor→Critic      │
  │  ✅  Prompt versioning — records which version of the   │
  │       system prompt was in effect for each decision     │
  │  ✅  PBC export — /audit/{id}/export/pbc formats the    │
  │       log as an auditor Provided-by-Client list         │
  │  ✅  Persistent sessions — SQLite checkpointer survives │
  │       restarts (Postgres-ready, one-line swap)          │
  │  ✅  Session ID — links all entries to one workflow run  │
  └──────────────────────────────────────────────────────────┘

  CRITIC VERDICT FLOW
  ───────────────────

  Rule-based checks   ──┐
  (deterministic)       │
                        ├──▶  Numeric claim verifier  ──▶  5-dim confidence
  LLM review      ──────┘         (deterministic)              breakdown
  (contextual, 10% weight)

  APPROVED   → All checks pass. Ready for Controller sign-off.
  FLAGGED    → Issues found. Usable, but requires management attention.
  REJECTED   → Material errors or unresolved SOX violations. Rework required.
```

---

## Injected Anomalies (What the System Catches)

The dataset contains 11 intentionally injected SOX control violations across the GL. The Anomaly Detection workflow is designed to surface all of them:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                      INJECTED ANOMALIES — DEC 2024                        │
├──────────────────────────┬──────────┬─────────────────────────────────────┤
│  Anomaly Type            │  Count   │  SOX Implication                    │
├──────────────────────────┼──────────┼─────────────────────────────────────┤
│  Missing Approver        │    5     │  POL-001 §4: All manual JEs require │
│                          │          │  independent approval. Deficiency.  │
├──────────────────────────┼──────────┼─────────────────────────────────────┤
│  Self Approval           │    2     │  POL-001 §4: "Self-approval is      │
│                          │          │  PROHIBITED at all dollar amounts." │
│                          │          │  Reportable SOX deficiency.         │
├──────────────────────────┼──────────┼─────────────────────────────────────┤
│  Unbalanced Entry        │    2     │  Every JE must balance. Imbalance   │
│                          │          │  indicates data integrity failure.  │
├──────────────────────────┼──────────┼─────────────────────────────────────┤
│  Weekend Posting         │    1     │  POL-001 §5: Weekend postings       │
│                          │          │  require prior Controller approval. │
├──────────────────────────┼──────────┼─────────────────────────────────────┤
│  Prior Period Posting    │    1     │  POL-001 §5: Requires CFO approval  │
│                          │          │  and SEC disclosure assessment.     │
├──────────────────────────┼──────────┼─────────────────────────────────────┤
│  TOTAL                   │   11     │  All detectable by Critic agent     │
└──────────────────────────┴──────────┴─────────────────────────────────────┘
```

---

## Supported Task Types

```
┌───────────────────┬──────────────────────────────────────────────────────┐
│  Task Type        │  What the System Does                                │
├───────────────────┼──────────────────────────────────────────────────────┤
│  reconciliation   │  Reviews all 15 account reconciliations. Identifies  │
│                   │  differences, categorizes by materiality, flags items │
│                   │  breaching the 30/60/90-day aging thresholds per     │
│                   │  POL-002. Recommends escalation path.                │
├───────────────────┼──────────────────────────────────────────────────────┤
│  journal_entry    │  Generates balanced double-entry journal entries with │
│                   │  business purpose narrative, proper account codes,    │
│                   │  and reversal date. Validates approval requirements   │
│                   │  against POL-001 thresholds.                         │
├───────────────────┼──────────────────────────────────────────────────────┤
│  variance_analysis│  Compares actuals vs. budget and prior period across  │
│                   │  10 P&L accounts. Flags threshold breaches (>10%).   │
│                   │  Writes CFO-grade narrative explanations grounded in  │
│                   │  the underlying transaction data.                    │
├───────────────────┼──────────────────────────────────────────────────────┤
│  anomaly_detection│  Scans all GL entries for 7 SOX control violation    │
│                   │  types. Runs deterministic rule-based checks first    │
│                   │  (no LLM), then contextual LLM review for edge cases.│
├───────────────────┼──────────────────────────────────────────────────────┤
│  accrual_review   │  Reviews the 14-entry accrual schedule for           │
│                   │  completeness, supporting documentation, proper       │
│                   │  reversal setup, and materiality thresholds per      │
│                   │  POL-004.                                            │
├───────────────────┼──────────────────────────────────────────────────────┤
│  close_checklist  │  Reviews December 2024 close checklist status.       │
│                   │  Identifies open items, past-due recs, missing        │
│                   │  approvals, and recommended escalation actions.       │
└───────────────────┴──────────────────────────────────────────────────────┘
```

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TECHNOLOGY STACK                                 │
└─────────────────────────────────────────────────────────────────────────────┘

  AGENT ORCHESTRATION
  ───────────────────
  LangGraph 0.2        Directed state graph wiring the 4-agent pipeline.
                       State flows as a typed dataclass — no hidden globals.
                       Deterministic routing: START→planner→retriever→
                       executor→critic→END.

  LangChain 0.3        Prompt management, message types, and LLM abstraction.
                       Allows swapping Ollama for Azure OpenAI or Claude API
                       with a one-line config change.

  LOCAL LLM (OFFLINE)
  ───────────────────
  Ollama               Runs open-weight models locally via llama.cpp backend.
                       Zero data egress — critical for regulated financial data.

  Mistral 7B Q4        Default model. ~4.5GB RAM. Strong reasoning for
                       structured accounting analysis. Fast on Apple Silicon.

  Alternatives         llama3.2:3b  → lighter, ~2GB RAM, good for demos
                       qwen2.5:7b   → strong math, good for JE generation

  DATA LAYER
  ──────────
  SQLite + Pandas      Simulates Oracle Fusion GL, AP, AR, and Blackline.
                       In production: swap db_tools.py functions for
                       authenticated REST API calls to actual systems.
                       Structure is identical — only the transport changes.

  Python REST wrappers Each db_tools function mirrors a real API endpoint:
                       /api/oracle/gl, /api/blackline/recons, etc.
                       Responses include provenance metadata (source, hash,
                       record count) that match real integration patterns.

  RAG (POLICY GROUNDING)
  ──────────────────────
  Policy documents     5 full-text accounting policy documents (JE policy,
                       rec policy, ASC 606, accruals, close checklist).
                       Injected into Executor context for grounded output.

  RESPONSIBLE AI
  ──────────────
  Deterministic SOX    Rule-based control checks run independently of the
  rule engine          LLM — provides an objective compliance floor that
                       cannot be hallucinated away.

  Numeric claim        Dollar amounts extracted from Executor output and
  verifier             cross-checked against retrieved_data before Critic
                       review. Catches hallucinated numbers regardless of
                       how confidently the Executor phrases them.

  5-dimension          Confidence score decomposed into Data Completeness,
  confidence           Policy Alignment, Arithmetic Integrity (30% weight),
                       Anomaly Coverage, and AI Coherence (10% weight).
                       Four of five dimensions are fully deterministic.

  Input hashing        SHA-256 of all agent inputs. Stored in audit log.
                       Detects data tampering between pipeline stages.

  Append-only log      Audit entries are never modified or deleted.
                       Designed for external audit PBC list readiness.

  Prompt versioning    All system prompts stored in core/prompts.py with
                       semantic version numbers. Version recorded in every
                       AuditEntry — past audits are reproducible against
                       the exact instructions that were in effect.

  API LAYER
  ─────────
  FastAPI + uvicorn    Full REST API exposing the pipeline over HTTP.
                       Async endpoints — Ollama calls run in a thread pool
                       so the event loop stays free.

  JWT Authentication   OAuth2PasswordBearer + HS256 signed tokens.
                       Two roles: admin (pipeline execution) and analyst
                       (read-only). Server-side token denylist for logout.

  RBAC                 Role-based access on every endpoint. /run and /demo
                       require admin. /sessions and /audit require analyst+.
                       /health and / are public for monitoring probes.

  Request audit log    Every API call logged with user, endpoint, status,
                       duration, client IP, and X-Request-ID correlation
                       header. Written to audit_requests.jsonl on disk.
                       SOX-relevant: proves every action on financial data
                       is attributable to an authenticated, named user.

  PBC export           GET /audit/{session_id}/export/pbc formats the full
                       pipeline audit trail as a numbered Provided-by-Client
                       list — the standard format external auditors request
                       during audit season. Reduces manual prep labor.

  Session persistence  SQLite checkpointer (langgraph.checkpoint.sqlite)
                       persists pipeline state across server restarts.
                       Upgrade path to PostgresSaver is one import swap.

  Metrics endpoints    GET /metrics/summary — aggregate performance stats
                       GET /metrics/dashboard — time-series data for charts
                       Both admin-only, ready for Plotly or Grafana.
```

---

## File Structure

```
finclose_ai/
├── pipeline.py                 LangGraph graph + run_pipeline() + SQLite checkpointer
├── requirements.txt
│
├── core/
│   ├── state.py                AgentState dataclass + enums (SoxFlag, TaskType)
│   │                           AuditEntry includes prompt_version for SOX reproducibility
│   ├── db_tools.py             Enterprise data tool layer with Pydantic return models
│   │                           Schema validation at DB boundary — catches Oracle column drift
│   └── prompts.py              Versioned prompt registry (planner/executor/critic @ 1.0.0)
│                               Bump version here when prompts change — recorded in audit log
│
├── agents/
│   └── agents.py               All 4 agents + numeric claim verifier
│                               _verify_numeric_claims() · _compute_confidence_breakdown()
│
├── api/
│   ├── server.py               FastAPI REST layer — all endpoints with RBAC
│   │                           POST /run  GET /demo/{task}  GET /health
│   │                           GET /audit/{id}  GET /audit/{id}/export/pbc
│   │                           GET /audit/requests  GET /sessions
│   │                           GET /metrics/summary  GET /metrics/dashboard
│   ├── auth.py                 JWT auth — login/logout, two roles (admin/analyst)
│   │                           bcrypt passwords · token denylist · /auth/me
│   └── middleware.py           Correlation IDs (X-Request-ID) + request audit logging
│                               Every API call logged to audit_requests.jsonl
│
├── ui/
│   └── app.py                  Streamlit dashboard
│                               Dark theme · Plotly charts · 5-dim confidence bars
│                               SOX flag memo cards · Claim verifier badge
│
├── monitoring/
│   └── metrics.py              JSONL metrics tracker (latency, confidence, verdicts)
│                               get_dashboard_data() feeds /metrics/dashboard endpoint
│
└── finclose_data_gen/
    ├── generate_mock_data.py   Data generation script (run once to create DB)
    └── finclose.db             SQLite — 10 tables, enterprise mock data (gitignored)
```

---

## Getting Started

### Prerequisites

- Python 3.12
- [Ollama](https://ollama.com) installed and running
- ~5GB free RAM (for Mistral 7B Q4)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/zparker68/finclose_ai.git
cd finclose_ai

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the default model
ollama pull mistral

# 5. Generate the mock enterprise database
python finclose_data_gen/generate_mock_data.py
```

### Running

```bash
# Terminal 1 — keep Ollama running
ollama serve

# Streamlit dashboard (primary visual interface)
streamlit run ui/app.py

# FastAPI REST layer + Swagger UI
cd finclose_ai && source venv/bin/activate
uvicorn api.server:app --reload --port 8000
# Swagger UI → http://localhost:8000/docs
# Accounts: admin / finclose2024  |  analyst / analyst2024 (read-only)

# CLI demo (interactive — pick from 5 task types)
python pipeline.py
```

### API Quick Start

```bash
# Login — get a Bearer token
curl -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=finclose2024" \
  -H "Content-Type: application/x-www-form-urlencoded"

# Health check (no auth required)
curl http://localhost:8000/health

# Run a preset demo task
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/demo/sox_scan"

# Export audit trail as a PBC list (Provided by Client — auditor format)
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/audit/<session_id>/export/pbc"

# Aggregate performance metrics
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/metrics/summary"
```

### LangSmith Telemetry (Optional)

Add to `.env` to enable real-time agent trace visualization:

```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-key-from-smith.langchain.com
LANGCHAIN_PROJECT=finclose-ai
```

Once enabled, every pipeline run appears in LangSmith with full agent reasoning paths — useful for demonstrating explainability to non-technical stakeholders.

### Swap the LLM

```bash
# Lighter model (2GB RAM, faster demo)
FINCLOSE_MODEL=llama3.2:3b streamlit run ui/app.py

# Best math reasoning (needs 8GB+)
FINCLOSE_MODEL=qwen2.5:7b streamlit run ui/app.py
```

### Connect to Real Systems

The data tool layer in `core/db_tools.py` is the integration boundary. Each function is a clean abstraction over a simulated REST endpoint. In production, replace the SQLite queries with authenticated HTTP calls:

```python
# Current (simulation)
def get_reconciliations(period: str) -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT * FROM reconciliations WHERE period=?", (period,))
        ...

# Production (Oracle Fusion REST API)
def get_reconciliations(period: str) -> dict:
    response = requests.get(
        "https://your-oracle.oraclecloud.com/fscmRestApi/resources/11.13.18.05/reconciliations",
        params={"period": period},
        headers={"Authorization": f"Bearer {ORACLE_TOKEN}"}
    )
    ...
```

The agents, state schema, audit trail, and SOX logic are identical. Only the transport layer changes.

---

## Responsible AI Design

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RESPONSIBLE AI PRINCIPLES                              │
└─────────────────────────────────────────────────────────────────────────────┘

  TRANSPARENCY
  ────────────
  Every output includes the full chain of reasoning:
  - Which data sources were used (with SHA-256 hashes)
  - Which policies were referenced (POL-001 through POL-005)
  - Which agent produced each section
  - 5-dimension confidence breakdown visible in the UI
  No black-box outputs. Every conclusion is traceable to source data.

  HALLUCINATION CONTROLS
  ──────────────────────
  Three independent layers:
  1. Retriever pulls ground-truth data before Executor generates narrative
  2. Numeric claim verifier cross-checks every dollar amount in the
     Executor's output against retrieved_data before Critic review —
     a confidently hallucinated number cannot pass this gate
  3. Critic independently verifies completeness and policy alignment

  FAIRNESS & BIAS PREVENTION
  ──────────────────────────
  SOX rule checks are deterministic and data-driven — no LLM judgment
  involved in flagging self-approvals, unbalanced entries, or threshold
  breaches. The LLM is used for narrative generation only, not for
  compliance decisions that could introduce bias.

  DATA PRIVACY
  ────────────
  100% offline architecture. No financial data, GL entries, or
  personally identifiable employee information is transmitted to any
  external API. All inference runs on local hardware. Suitable for
  deployment in air-gapped or highly regulated environments.

  AUDITABILITY
  ────────────
  The system is designed to be audited:
  - External auditors can review the JSON audit log as PBC evidence
  - Input hashes enable tamper detection
  - Agent role separation mirrors segregation of duties requirements
  - No agent can approve its own outputs (Critic is always separate)
  - SOX HTML report exportable directly from the UI

  HUMAN OVERSIGHT
  ───────────────
  FLAGGED and REJECTED outputs require mandatory human review before
  any action is taken. The system issues recommendations, not commands.
  All journal entries require human approval before posting to the GL.
  Confidence composite below 50% triggers automatic escalation band.
```

---

## Roadmap

- [x] **Multi-agent pipeline** — LangGraph 4-agent graph (Planner → Retriever → Executor → Critic)
- [x] **Enterprise data layer** — Oracle GL/AP/AR + Blackline simulation with 10 tables
- [x] **SOX rule engine** — Deterministic checks for 8 violation types, independent of LLM
- [x] **Streamlit UI** — Dark theme dashboard with Plotly charts, real-time agent progress, export buttons
- [x] **GL source traceability** — Clickable SOX flag drill-downs showing exact Oracle GL records
- [x] **Executive memo cards** — Plain-English SOX flag explanations with highlighted violation fields
- [x] **5-dimension confidence breakdown** — Replaces single LLM scalar with 4 deterministic + 1 LLM dimension
- [x] **Numeric claim verifier** — Deterministic dollar-amount cross-check between Executor and Critic
- [x] **SOX report export** — Self-contained HTML audit report with certification statement
- [ ] **FastAPI REST layer** — HTTP API exposing pipeline for external system integration
- [ ] **ChromaDB RAG** — Semantic chunking of policy documents with hybrid search
- [ ] **Evaluation framework** — Faithfulness, accuracy, and SOX recall scoring on a test query set
- [ ] **Conditional routing** — REJECTED outputs automatically re-routed to Executor for revision
- [ ] **Multi-period analysis** — Quarter-over-quarter and year-over-year comparisons

---

## About This Project

FinClose AI was built as a portfolio demonstration of production-grade AI engineering applied to enterprise accounting automation. It directly mirrors the architecture and use cases of AI initiatives at leading global accounting organizations — including agent-based workflow orchestration, responsible AI controls, SOX compliance tooling, and enterprise system integration patterns.

| Requirement | Implementation |
|---|---|
| AI agents for accounting use cases | LangGraph 4-agent pipeline |
| Workflow orchestration & automation | Directed state graph with typed state |
| Enterprise system integration | `db_tools.py` REST API abstraction layer |
| Responsible AI / hallucination controls | Deterministic numeric claim verifier + 5-dim confidence |
| SOX compliance | Append-only audit log + SHA-256 input hashing |
| Calibrated confidence scoring | 4 deterministic dimensions, LLM downweighted to 10% |
| Source traceability | Per-flag GL drill-downs with highlighted violation fields |
| Offline / data privacy | 100% local Ollama inference, zero data egress |
| Executive-readable output | Memo cards, plain-English explanations, SOX HTML export |
| Model flexibility | `FINCLOSE_MODEL` env var — swap Mistral/Llama/Qwen at runtime |

---

<div align="center">

*Built by Zac Parker · Las Vegas, NV*
*github.com/zparker68*

</div>
