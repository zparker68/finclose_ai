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
[![SQLite](https://img.shields.io/badge/Oracle_GL-Simulated-003B57?style=flat-square&logo=sqlite)](https://sqlite.org)
[![SOX](https://img.shields.io/badge/SOX-Compliant_Audit_Trail-2ECC71?style=flat-square)]()
[![Offline](https://img.shields.io/badge/Data-100%25_Offline-E74C3C?style=flat-square)]()

*Automates reconciliation · journal entries · variance analysis · anomaly detection — entirely offline*

</div>

---

## What Is This?

FinClose AI is an end-to-end multi-agent system that automates the most labour-intensive tasks in a corporate financial close cycle. It mirrors the exact accounting AI initiatives described by leading gaming and entertainment companies, including workflows for Oracle Fusion GL, Blackline reconciliations, HFM variance reporting, and SOX internal controls.

**The system runs 100% offline.** No financial data ever leaves your machine — a critical requirement in regulated industries (gaming, healthcare, financial services) where sensitive GL data cannot be transmitted to third-party cloud LLM APIs.

This is not a demo. It is a functioning accounting automation engine backed by realistic enterprise data, a full audit trail, and SOX-aware control checks.

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
  │          │                │                  │                  │        │
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
  │   ╚═══════════════╝     ║                  ║                           │
  │                         ║  • Classify task ║                           │
  │                         ║  • Write plan    ║                           │
  │                         ║  • Select tools  ║                           │
  │                         ╚════════╤═════════╝                           │
  │                                  │                                      │
  │                                  ▼                                      │
  │                         ╔══════════════════╗     ┌──────────────────┐  │
  │                         ║  2. RETRIEVER    ║────▶│  Policy Library  │  │
  │                         ║                  ║     │  (RAG context)   │  │
  │                         ║  • Pull DB data  ║     │  5 GAAP/SOX docs │  │
  │                         ║  • Load policies ║     └──────────────────┘  │
  │                         ║  • Hash inputs   ║                           │
  │                         ╚════════╤═════════╝                           │
  │                                  │                                      │
  │                                  ▼                                      │
  │                         ╔══════════════════╗     ┌──────────────────┐  │
  │                         ║  3. EXECUTOR     ║────▶│  Ollama (Local)  │  │
  │                         ║                  ║     │  Mistral 7B Q4   │  │
  │                         ║  • Reconcile     ║     │  ~4.5GB RAM      │  │
  │                         ║  • Generate JEs  ║     │  CPU inference   │  │
  │                         ║  • Variance calc ║     └──────────────────┘  │
  │                         ║  • Write narrative║                          │
  │                         ╚════════╤═════════╝                           │
  │                                  │                                      │
  │                                  ▼                                      │
  │                         ╔══════════════════╗                           │
  │                         ║  4. CRITIC       ║  ← SOX Gate               │
  │                         ║                  ║                           │
  │                         ║  • SOX checks    ║                           │
  │                         ║  • Math verify   ║                           │
  │                         ║  • Confidence    ║                           │
  │                         ║  • APPROVE/FLAG/ ║                           │
  │                         ║    REJECT        ║                           │
  │                         ╚════════╤═════════╝                           │
  └──────────────────────────────────│────────────────────────────────────┘
                                     │
  ┌──────────────────────────────────│────────────────────────────────────┐
  │  OUTPUT LAYER                    ▼                                    │
  │                                                                        │
  │   ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
  │   │  Formatted       │  │  SOX Audit Log  │  │  Streamlit UI       │ │
  │   │  Analysis Report │  │  (JSON export)  │  │  Dashboard          │ │
  │   │                  │  │                 │  │                     │ │
  │   │  APPROVED ✅     │  │  Timestamped    │  │  "Run Close" btn    │ │
  │   │  FLAGGED  ⚠️     │  │  Input hashes   │  │  Plotly charts      │ │
  │   │  REJECTED ❌     │  │  Attribution    │  │  Audit trail view   │ │
  │   └──────────────────┘  └─────────────────┘  └─────────────────────┘ │
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
│                │  rule-based checks first (no LLM). Then uses LLM to       │
│                │  verify math, completeness, and policy alignment. Issues   │
│                │  APPROVED / FLAGGED / REJECTED verdict with confidence     │
│                │  score. Never trusts — always verifies independently.      │
│                │  Model role: Internal audit + SOX reviewer                │
└────────────────┴────────────────────────────────────────────────────────────┘
```

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
          │                            ┌────────────────────────────────────┐
          ▼                            │ item_id     • category             │
  chart_of_accounts                   │ recon_id    • aging_days ◄─── KPI  │
  39 accounts | 5 types               │ amount      • reference            │
  Asset/Liability/Equity              └────────────────────────────────────┘
  Revenue/Expense

  ORACLE FUSION AP                    ORACLE FUSION AR
  ─────────────────                   ──────────────────
  ap_invoices (120)                   ar_aging (80)
  ┌───────────────────────┐           ┌──────────────────────────┐
  │ vendor_name           │           │ customer_name            │
  │ invoice_amount        │           │ open_balance             │
  │ open_amount  ◄─── KPI │           │ aging_bucket ◄─── KPI   │
  │ status               │           │  Current / 31-60         │
  │ due_date             │           │  61-90 / 91-120 / 120+   │
  │ po_number            │           │ collection_status        │
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
    "timestamp":   "2024-12-31T18:42:07.441Z",     ← UTC, always
    "agent":       "executor",                      ← attribution
    "action":      "execute_variance_analysis",     ← what happened
    "input_hash":  "a3f8c2d19e4b",                 ← SHA-256 of inputs
    "reasoning":   "Executed variance analysis using 2 datasets",
    "output":      "4 accounts exceed 10% threshold...",
    "sox_flags":   ["THRESHOLD_BREACH"],            ← compliance signals
    "citations":   ["Oracle/HFM Variance | 4 threshold breaches"],
    "confidence":  0.88
  }

  ┌──────────────────────────────────────────────────────────┐
  │  GUARANTEED PROPERTIES                                   │
  │                                                          │
  │  ✅  Append-only — entries are never modified           │
  │  ✅  Input hashing — SHA-256 detects data tampering     │
  │  ✅  Agent attribution — who did what, when             │
  │  ✅  Policy citations — every finding references source  │
  │  ✅  SOX flags propagate — Planner→Executor→Critic      │
  │  ✅  JSON exportable — ready for external audit PBC     │
  │  ✅  Session ID — links all entries to one workflow run  │
  └──────────────────────────────────────────────────────────┘

  CRITIC VERDICT FLOW
  ───────────────────

  Rule-based checks  ──┐
  (deterministic)      │
                       ├──▶  Combined SOX Flag List  ──▶  Verdict
  LLM review      ─────┘
  (contextual)

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
                       executor→critic→END. Easily extensible to conditional
                       edges (e.g., re-route rejected analyses back to executor).

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
                       deepseek-r1  → best reasoning, needs 8GB+ for 7B

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

  ChromaDB (roadmap)   Local vector store for semantic policy retrieval.
                       Current implementation uses full-text injection;
                       ChromaDB chunking + embedding is the next upgrade.

  RESPONSIBLE AI
  ──────────────
  Deterministic SOX    Rule-based control checks run independently of the
  rule engine          LLM — provides an objective compliance floor that
                       cannot be hallucinated away.

  Input hashing        SHA-256 of all agent inputs. Stored in audit log.
                       Detects data tampering between pipeline stages.

  Confidence scoring   Critic emits a 0.0–1.0 confidence score alongside
                       its verdict. Low-confidence outputs surface for
                       mandatory human review.

  Append-only log      Audit entries are never modified or deleted.
                       Designed for external audit PBC list readiness.

  Citation requirement Every Executor output must cite source documents
                       and data hashes. Hallucination without grounding
                       fails the Critic review.
```

---

## File Structure

```
finclose_ai/
├── pipeline.py                 LangGraph graph + run_pipeline() entry point
├── requirements.txt
│
├── core/
│   ├── state.py                AgentState dataclass + enums (SoxFlag, TaskType)
│   └── db_tools.py             Enterprise data tool layer (Oracle/Blackline API sim)
│
├── agents/
│   └── agents.py               All 4 agents: Planner, Retriever, Executor, Critic
│
├── ui/
│   └── app.py                  Streamlit dashboard — dark theme, Plotly charts, real-time progress
│
├── api/
│   └── server.py               FastAPI REST layer — /run, /health, /demo/{task}, /audit
│
├── eval/
│   ├── test_queries.json       20-query evaluation set across 5 task types
│   ├── ground_truth.json       Expected SOX flags, keywords, verdicts per query
│   └── run_eval.py             Scoring script — faithfulness, accuracy, SOX recall
│
├── monitoring/
│   └── metrics.py              JSONL metrics tracker — latency, confidence, verdict distribution
│
├── tests/
│   ├── test_planner.py         8 unit tests (LLM mocked)
│   ├── test_retriever.py       10 unit tests (real DB, no LLM)
│   ├── test_executor.py        6 unit tests (LLM mocked)
│   ├── test_critic.py          17 unit tests — rule-based SOX checks + parsing
│   └── test_integration.py     Full pipeline + schema tests (Ollama-gated)
│
├── scripts/
│   └── setup.sh                One-command environment setup
│
└── finclose_data_gen/
    ├── generate_mock_data.py   Data generation script (run once to create DB)
    └── finclose.db             SQLite — 10 tables, enterprise mock data (gitignored)
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- [Ollama](https://ollama.com) installed and running
- ~5GB free RAM (for Mistral 7B Q4)

### Installation

```bash
# 1. Clone the repository
git clone https://gitlab.com/zparker68/finclose-ai.git
cd finclose-ai

# 2. One-command setup (installs deps, pulls model, generates DB)
bash scripts/setup.sh

# — or manually:
pip install -r requirements.txt
ollama pull mistral
python finclose_data_gen/generate_mock_data.py
```

### Running

```bash
# Terminal 1 — keep Ollama running
ollama serve

# Streamlit dashboard
python -m streamlit run ui/app.py

# FastAPI server (http://localhost:8000/docs)
python -m uvicorn api.server:app --reload

# CLI demo (interactive — pick from 5 task types)
python pipeline.py

# Unit tests (no Ollama needed)
python -m pytest tests/ -v -m "not integration"

# Eval suite (needs Ollama)
python eval/run_eval.py
```

### Swap the LLM

```bash
# Lighter model (2GB RAM, faster demo)
FINCLOSE_MODEL=llama3.2:3b python pipeline.py

# Best math reasoning (needs 8GB+)
FINCLOSE_MODEL=qwen2.5:7b python pipeline.py

# Azure OpenAI (requires langchain-openai + API key)
# Edit agents/agents.py: replace ChatOllama with AzureChatOpenAI
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
        f"https://your-oracle-instance.oraclecloud.com/fscmRestApi/resources/11.13.18.05/generalLedgerJournals",
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
  - Confidence score from independent Critic review
  No black-box outputs. Every conclusion is traceable to source data.

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

  HUMAN OVERSIGHT
  ───────────────
  FLAGGED and REJECTED outputs require mandatory human review before
  any action is taken. The system issues recommendations, not commands.
  All journal entries require human approval before posting to the GL.
  Confidence scores below 0.75 trigger automatic escalation.

  HALLUCINATION CONTROLS
  ──────────────────────
  - Retriever pulls data before Executor generates narrative
  - Critic independently verifies dollar amounts against source data
  - Policy citations must match retrieved documents
  - Round-trip consistency check: JE debits must equal JE credits
```

---

## Roadmap

- [x] **Streamlit UI** — One-click "Run Monthly Close" dashboard with Plotly visualizations (`ui/app.py`)
- [x] **FastAPI REST layer** — Full HTTP API exposing pipeline with `/run`, `/health`, `/demo/{task}`, `/audit` (`api/server.py`)
- [x] **Evaluation framework** — RAGAS-style faithfulness, accuracy, and SOX recall scoring on 20-query test set (`eval/`)
- [x] **Model monitoring** — JSONL-based metrics tracker for latency, confidence drift, and SOX flag rates (`monitoring/metrics.py`)
- [x] **Test suite** — 47 unit + integration tests covering all 4 agents (`tests/`)
- [ ] **ChromaDB RAG** — Semantic chunking of policy documents with hybrid search
- [ ] **Conditional routing** — REJECTED outputs automatically re-routed to Executor for revision
- [ ] **Multi-period analysis** — Quarter-over-quarter and year-over-year comparisons
- [ ] **HFM consolidation** — Intercompany elimination automation

---

## About This Project

FinClose AI was built as a portfolio demonstration of production-grade AI engineering applied to enterprise accounting automation. It directly mirrors the architecture and use cases of AI initiatives at leading global accounting organizations — including agent-based workflow orchestration, responsible AI controls, SOX compliance tooling, and enterprise system integration patterns.

**Tech stack alignment with enterprise accounting AI requirements:**

| Requirement | Implementation |
|---|---|
| AI agents for accounting use cases | LangGraph multi-agent pipeline |
| Workflow orchestration & automation | Directed state graph with typed state |
| Enterprise system integration | db_tools.py REST API abstraction layer |
| Data pipelines | SQLite ETL + Pandas transforms |
| Responsible AI | Deterministic rule checks + confidence scoring |
| SOX compliance | Append-only audit log + input hashing |
| Model evaluation | Critic agent + confidence scoring |
| Offline / data privacy | 100% local Ollama inference |
| Power Platform-style UX | Streamlit UI (`ui/app.py`) — dark theme, Plotly charts, real-time agent progress |
| REST API layer | FastAPI server (`api/server.py`) — `/run`, `/health`, `/demo/{task}`, `/audit` endpoints |
| Evaluation framework | 20-query test set with faithfulness, accuracy, and SOX recall scoring (`eval/`) |
| Observability | JSONL metrics tracking latency, confidence drift, verdict distribution (`monitoring/`) |
| Test coverage | 47 unit + integration tests across all agents (`tests/`) |

---

<div align="center">

*Built by Zac Parker · Las Vegas, NV*
*gitlab.com/zparker68*

</div>
