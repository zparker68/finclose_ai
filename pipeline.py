"""
finclose_ai/pipeline.py
────────────────────────
LangGraph state machine wiring the four agents into a directed pipeline.

Graph topology:
  START → planner → retriever → executor → critic → END

State flows as a dataclass through each node.
The graph is compiled once and reused across requests (thread-safe).

Usage:
    from pipeline import run_pipeline, FinCloseGraph

    result = run_pipeline(
        query="Reconcile the cash accounts for December 2024",
        period="2024-12",
        requested_by="jsmith"
    )
    print(result.final_response)
    print(result.critic_verdict)     # APPROVED | FLAGGED | REJECTED
    print(len(result.audit_log))     # audit trail entry count
"""

from __future__ import annotations

import sqlite3
import uuid
import time
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage

from core.state import AgentState, TaskType
from agents.agents import planner_agent, retriever_agent, executor_agent, critic_agent

# ── Checkpointer setup ────────────────────────────────────────────────────────
# SqliteSaver persists pipeline state so sessions survive server restarts.
# To upgrade to Postgres: swap SqliteSaver for PostgresSaver and point at your DB.
# The API is identical — one line change.

_CHECKPOINT_DB = os.path.join(os.path.dirname(__file__), "checkpoints.db")

def _get_checkpointer():
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
        conn = sqlite3.connect(_CHECKPOINT_DB, check_same_thread=False)
        return SqliteSaver(conn)
    except Exception:
        return None  # Degrade gracefully if checkpointer unavailable


# ── Graph definition ──────────────────────────────────────────────────────────

def _build_graph():
    """
    Constructs and compiles the LangGraph pipeline.
    Returns a compiled graph ready for .invoke() calls.
    """
    # LangGraph requires a TypedDict or dict as state — we use a wrapper
    # that converts our dataclass AgentState to/from dict at graph boundaries.

    from typing import TypedDict, Any

    class GraphState(TypedDict, total=False):
        state: Any  # holds our AgentState dataclass

    def wrap_planner(gs: dict) -> dict:
        gs["state"] = planner_agent(gs["state"])
        return gs

    def wrap_retriever(gs: dict) -> dict:
        gs["state"] = retriever_agent(gs["state"])
        return gs

    def wrap_executor(gs: dict) -> dict:
        gs["state"] = executor_agent(gs["state"])
        return gs

    def wrap_critic(gs: dict) -> dict:
        gs["state"] = critic_agent(gs["state"])
        return gs

    graph = StateGraph(dict)
    graph.add_node("planner",   wrap_planner)
    graph.add_node("retriever", wrap_retriever)
    graph.add_node("executor",  wrap_executor)
    graph.add_node("critic",    wrap_critic)

    graph.add_edge(START,       "planner")
    graph.add_edge("planner",   "retriever")
    graph.add_edge("retriever", "executor")
    graph.add_edge("executor",  "critic")
    graph.add_edge("critic",    END)

    checkpointer = _get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


# Compiled graph — module-level singleton
_graph = None

def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ── Public API ────────────────────────────────────────────────────────────────

def run_pipeline(
    query: str,
    period: str = "2024-12",
    requested_by: str = "user",
) -> AgentState:
    """
    Main entry point. Runs the full 4-agent pipeline for a given query.

    Args:
        query:        Natural language accounting task
        period:       Accounting period (YYYY-MM)
        requested_by: User ID for audit log attribution

    Returns:
        Fully populated AgentState with:
        - final_response: formatted output ready to display
        - critic_verdict: APPROVED | FLAGGED | REJECTED
        - sox_flags: list of SOX control violations detected
        - audit_log: complete tamper-evident audit trail
        - processing_ms: total pipeline latency
    """
    t0 = time.time()

    initial_state = AgentState(
        user_query=query,
        period=period,
        session_id=str(uuid.uuid4())[:8],
        requested_by=requested_by,
        messages=[HumanMessage(content=query)],
    )

    graph = _get_graph()
    config = {"configurable": {"thread_id": initial_state.session_id}}
    result = graph.invoke({"state": initial_state}, config=config)
    final_state: AgentState = result["state"]
    final_state.processing_ms = (time.time() - t0) * 1000

    try:
        from monitoring.metrics import record_run
        record_run(final_state, model=os.environ.get("FINCLOSE_MODEL", "mistral"))
    except Exception:
        pass  # Never let monitoring break the pipeline

    return final_state


def export_audit_log(state: AgentState, path: str | None = None) -> str:
    """
    Exports the full audit log to JSON.
    SOX-ready: includes timestamps, input hashes, agent attributions, and citations.
    """
    import dataclasses

    log_data = {
        "session_id":    state.session_id,
        "period":        state.period,
        "query":         state.user_query,
        "requested_by":  state.requested_by,
        "verdict":       state.critic_verdict,
        "confidence":    state.confidence_score,
        "sox_flags":     [f.value for f in state.sox_flags],
        "processing_ms": state.processing_ms,
        "exported_at":   __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        "audit_entries": [dataclasses.asdict(e) for e in state.audit_log],
    }

    json_str = json.dumps(log_data, indent=2, default=str)

    if path:
        with open(path, "w") as f:
            f.write(json_str)

    return json_str


# ── CLI Runner ────────────────────────────────────────────────────────────────

DEMO_QUERIES = {
    "1": ("Anomaly Detection",
          "Scan all December 2024 journal entries for SOX control violations and suspicious patterns"),
    "2": ("Variance Analysis",
          "Analyze December 2024 budget vs actual variances and write a CFO-ready narrative for accounts with >5% variance"),
    "3": ("Reconciliation",
          "Review the status of all December 2024 account reconciliations and identify items requiring escalation"),
    "4": ("Accrual Review",
          "Review the December 2024 accrual schedule for completeness and validate all entries are properly supported"),
    "5": ("Journal Entry",
          "Generate a journal entry to accrue $285,000 of unpaid December salaries as of period end"),
}


if __name__ == "__main__":
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import print as rprint

    console = Console()

    console.print(Panel.fit(
        "[bold cyan]FinClose AI Agent[/bold cyan]\n"
        "[dim]Multi-Agent Accounting Automation | Powered by LangGraph + Ollama[/dim]\n"
        "[dim]100% Local | SOX-Auditable | Oracle/Blackline Simulated[/dim]",
        border_style="cyan"
    ))

    # Show demo menu
    table = Table(title="Demo Tasks", show_header=True, header_style="bold magenta")
    table.add_column("#", style="cyan", width=3)
    table.add_column("Task Type", style="bold", width=20)
    table.add_column("Query", style="dim")

    for key, (task, query) in DEMO_QUERIES.items():
        table.add_row(key, task, query[:70] + "...")

    console.print(table)
    console.print()

    choice = console.input("[bold]Select demo (1-5) or type your own query: [/bold]").strip()

    if choice in DEMO_QUERIES:
        _, query = DEMO_QUERIES[choice]
    else:
        query = choice if choice else DEMO_QUERIES["1"][1]

    console.print(f"\n[bold yellow]Running:[/bold yellow] {query}\n")

    with console.status("[bold green]Running 4-agent pipeline...[/bold green]", spinner="dots"):
        result = run_pipeline(query, period="2024-12", requested_by="demo_user")

    # Display results
    console.print(Panel(result.final_response, title="[bold]Analysis Result[/bold]", border_style="green"))

    # Audit log summary
    console.print(f"\n[bold]Audit Trail:[/bold] {len(result.audit_log)} entries")
    for entry in result.audit_log:
        status = "✅" if not entry.sox_flags else "⚠️ "
        console.print(f"  {status} [{entry.agent}] {entry.action} — {entry.timestamp}")

    if result.sox_flags:
        console.print(f"\n[bold red]SOX Flags:[/bold red] {', '.join(f.value for f in result.sox_flags)}")

    # Export audit log
    log_path = f"audit_log_{result.session_id}.json"
    export_audit_log(result, log_path)
    console.print(f"\n[dim]Audit log exported → {log_path}[/dim]")
