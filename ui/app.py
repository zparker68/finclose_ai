"""
finclose_ai/ui/app.py
──────────────────────
FinClose AI — Streamlit Dashboard
Palette: Refined Dark Finance — deep navy, muted 18k gold, strong borders.

Layout:
  Sidebar       → period, model, analyst, quick-launch nav, Ollama status
  Nav bar       → logo, period/model badges, session info
  KPI strip     → 4 top-line metrics (GL entries, accruals, open recons, breaches)
  Close board   → workstream completion progress (recons / accruals / variances / anomalies)
  Panel row 1   → Run Close + Verdict (with confidence thresholds)
  Panel row 2   → Analysis output + SOX Flags (with remediation)
  Charts        → 4 Plotly charts (cached, with freshness timestamp)
  Audit trail   → expandable table + export buttons
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import sys
import queue
import subprocess
import threading
import time
import uuid
from datetime import datetime

# ── Path fix ──────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.db_tools import (
    get_accruals,
    get_anomalous_entries,
    get_ar_aging,
    get_gl_transactions,
    get_reconciliations,
    get_trial_balance,
    get_variance_analysis,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinClose AI",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Palette — Refined Dark Finance ────────────────────────────────────────────
C_BG      = "#0F1923"
C_CARD    = "#162030"
C_INPUT   = "#0A1018"
C_BORDER  = "#1E2D3D"
C_BORDER2 = "#243447"

C_GOLD    = "#C9A84C"
C_GOLD_LT = "#DDB96A"
C_GOLD_BG = "rgba(201,168,76,0.08)"

C_TEXT    = "#D4D8E2"
C_TEXT2   = "#6B7A8D"
C_TEXT3   = "#3D4F63"

C_GREEN   = "#2EAA5C"
C_AMBER   = "#D9922A"
C_RED     = "#C94040"
C_BLUE    = "#3B82C4"

# ── SOX remediation map ───────────────────────────────────────────────────────
SOX_REMEDIATION: dict[str, str] = {
    "SELF_APPROVAL":        "Route to secondary approver. Do not post until sign-off obtained.",
    "MISSING_APPROVER":     "Obtain approver signature before period close. Escalate if unavailable.",
    "UNBALANCED_ENTRY":     "Correct debit/credit imbalance before posting. Do not submit to GL.",
    "WEEKEND_POSTING":      "Verify posting date with controller. Obtain weekend exception approval.",
    "PRIOR_PERIOD_POSTING": "Obtain prior-period adjustment authorization from CFO.",
    "ROUND_NUMBER_MANUAL":  "Provide supporting documentation for manual round-number entry.",
    "THRESHOLD_BREACH":     "Prepare variance explanation memo. CFO sign-off required before close.",
    "UNUSUAL_ACCOUNT_COMBO":"Verify account coding with GL accountant. Flag for internal audit.",
}

# ── Theme CSS ─────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');

html, body, [data-testid="stApp"] {{
    background-color: {C_BG};
    color: {C_TEXT};
    font-family: 'IBM Plex Mono', 'Courier New', monospace;
}}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background-color: {C_BG};
    border-right: 1px solid {C_BORDER};
}}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stTextInput label {{
    color: {C_TEXT2} !important;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}}
[data-testid="stSidebar"] .stButton > button {{
    background: transparent !important;
    border: none !important;
    border-left: 2px solid {C_BORDER} !important;
    border-radius: 0 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    padding: 0.35rem 0.6rem 0.35rem 0.75rem !important;
    color: {C_TEXT2} !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    transition: border-left-color 0.12s, color 0.12s, background 0.12s !important;
    width: 100% !important;
}}
[data-testid="stSidebar"] .stButton > button:hover {{
    border-left-color: {C_GOLD} !important;
    color: {C_GOLD} !important;
    background: {C_GOLD_BG} !important;
}}

/* ── Section label ── */
.section-label {{
    color: {C_TEXT2};
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.4rem;
    padding-bottom: 0.3rem;
    border-bottom: 1px solid {C_BORDER};
}}

/* ── Nav bar ── */
.nav-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-top: 2px solid {C_GOLD};
    border-radius: 6px;
    padding: 0.65rem 1.4rem;
    margin-bottom: 0.75rem;
}}
.nav-logo {{
    color: {C_GOLD};
    font-size: 1.1rem;
    font-weight: 700;
    letter-spacing: 0.08em;
}}
.nav-badge-period {{
    background: rgba(201,168,76,0.12);
    color: {C_GOLD};
    border: 1px solid rgba(201,168,76,0.4);
    font-size: 0.68rem;
    padding: 0.15rem 0.65rem;
    border-radius: 3px;
    margin-left: 0.6rem;
    letter-spacing: 0.08em;
}}
.nav-badge-model {{
    background: rgba(59,130,196,0.12);
    color: {C_BLUE};
    border: 1px solid rgba(59,130,196,0.4);
    font-size: 0.68rem;
    padding: 0.15rem 0.65rem;
    border-radius: 3px;
    margin-left: 0.4rem;
    letter-spacing: 0.06em;
}}
.nav-right {{
    color: {C_TEXT3};
    font-size: 0.7rem;
    letter-spacing: 0.04em;
}}

/* ── KPI strip ── */
.kpi-strip {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.6rem;
    margin-bottom: 0.75rem;
}}
.kpi-card {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 0.75rem 1rem;
    position: relative;
    overflow: hidden;
}}
.kpi-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    border-radius: 6px 0 0 6px;
}}
.kpi-gold::before   {{ background: {C_GOLD}; }}
.kpi-blue::before   {{ background: {C_BLUE}; }}
.kpi-green::before  {{ background: {C_GREEN}; }}
.kpi-red::before    {{ background: {C_RED}; }}
.kpi-amber::before  {{ background: {C_AMBER}; }}
.kpi-label {{
    color: {C_TEXT2};
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.3rem;
}}
.kpi-value {{
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 0.15rem;
}}
.kpi-sub {{
    color: {C_TEXT3};
    font-size: 0.65rem;
}}
.kpi-delta-up   {{ color: {C_RED};   font-size: 0.65rem; }}
.kpi-delta-down {{ color: {C_GREEN}; font-size: 0.65rem; }}

/* ── Close status board ── */
.close-board {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 0.6rem;
    margin-bottom: 0.75rem;
}}
.close-card {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
    padding: 0.8rem 1rem;
}}
.close-card-title {{
    color: {C_TEXT2};
    font-size: 0.62rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.5rem;
}}
.close-count {{
    font-size: 1rem;
    font-weight: 700;
    margin-bottom: 0.4rem;
}}
.close-bar-track {{
    background: {C_BORDER};
    border-radius: 2px;
    height: 4px;
    margin-bottom: 0.35rem;
    overflow: hidden;
}}
.close-bar-fill {{
    height: 4px;
    border-radius: 2px;
    transition: width 0.3s ease;
}}
.close-status-label {{
    font-size: 0.62rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}}

/* ── Panel heading ── */
.panel-title {{
    color: {C_TEXT2};
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
}}
.panel-title::before {{
    content: '';
    display: inline-block;
    width: 3px;
    height: 10px;
    background: {C_GOLD};
    border-radius: 2px;
}}

/* ── Verdict pill ── */
.verdict-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.05rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    padding: 0.5rem 1.2rem;
    border-radius: 4px;
    margin-bottom: 0.6rem;
    border-width: 1px;
    border-style: solid;
}}
.verdict-approved {{ color:{C_GREEN}; background:rgba(46,170,92,0.1);  border-color:{C_GREEN}; }}
.verdict-flagged  {{ color:{C_AMBER}; background:rgba(217,146,42,0.1); border-color:{C_AMBER}; }}
.verdict-rejected {{ color:{C_RED};   background:rgba(201,64,64,0.1);  border-color:{C_RED}; }}
.verdict-pending  {{ color:{C_TEXT3}; background:rgba(61,79,99,0.15);  border-color:{C_BORDER}; font-size:0.85rem; font-weight:400; }}

/* ── Confidence thresholds ── */
.conf-thresholds {{
    display: flex;
    gap: 0.5rem;
    margin-top: 0.4rem;
    font-size: 0.6rem;
    color: {C_TEXT3};
    letter-spacing: 0.04em;
}}
.conf-t-green {{ color: {C_GREEN}; }}
.conf-t-amber {{ color: {C_AMBER}; }}
.conf-t-red   {{ color: {C_RED}; }}

/* ── Metrics ── */
[data-testid="stMetricValue"] {{
    color: {C_GOLD} !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.45rem !important;
}}
[data-testid="stMetricLabel"] {{
    color: {C_TEXT2} !important;
    font-size: 0.65rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}}

/* ── Run button ── */
div[data-testid="stButton"]:has(button[kind="primary"]) > button {{
    background: {C_GOLD} !important;
    color: {C_BG} !important;
    border: none !important;
    border-radius: 4px !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.06em !important;
    padding: 0.6rem 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
}}
div[data-testid="stButton"]:has(button[kind="primary"]) > button:hover {{
    background: {C_GOLD_LT} !important;
}}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
}}

/* ── Inputs ── */
.stTextArea textarea {{
    background: {C_INPUT} !important;
    color: {C_TEXT} !important;
    border: 1px solid {C_BORDER} !important;
    border-radius: 4px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    line-height: 1.5 !important;
}}
.stTextArea textarea:focus {{
    border-color: {C_GOLD} !important;
    box-shadow: 0 0 0 1px {C_GOLD} !important;
}}
.stSelectbox div[data-baseweb="select"] {{
    background: {C_INPUT} !important;
    border: 1px solid {C_BORDER} !important;
}}

/* ── Analysis box ── */
.analysis-box {{
    background: {C_INPUT};
    border: 1px solid {C_BORDER};
    border-radius: 4px;
    padding: 1rem 1.1rem;
    max-height: 300px;
    overflow-y: auto;
    font-size: 0.77rem;
    line-height: 1.7;
    color: {C_TEXT};
}}
.analysis-box h3 {{
    color: {C_GOLD};
    font-size: 0.78rem;
    font-weight: 600;
    margin: 0.8rem 0 0.25rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-bottom: 1px solid {C_BORDER};
    padding-bottom: 0.2rem;
}}
.analysis-box strong {{ color: {C_TEXT}; font-weight: 600; }}
.analysis-box .num   {{ color: {C_GOLD_LT}; font-weight: 600; }}

/* ── Freshness stamp ── */
.freshness {{
    color: {C_TEXT3};
    font-size: 0.62rem;
    letter-spacing: 0.04em;
    float: right;
    margin-top: 0.1rem;
}}

/* ── Status ── */
.status-online  {{ color: {C_GREEN}; font-size: 0.75rem; letter-spacing: 0.06em; }}
.status-offline {{ color: {C_RED};   font-size: 0.75rem; letter-spacing: 0.06em; }}

/* ── Divider ── */
hr {{ border-color: {C_BORDER}; margin: 0.75rem 0; }}

/* ── Expander ── */
[data-testid="stExpander"] {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 6px;
}}
[data-testid="stExpander"] summary {{
    color: {C_TEXT2};
    font-size: 0.75rem;
    letter-spacing: 0.06em;
}}
</style>
""", unsafe_allow_html=True)

# ── Constants ─────────────────────────────────────────────────────────────────

DEMO_QUERIES: dict[str, str] = {
    "SOX Violations": (
        "Scan all December 2024 journal entries for SOX control violations "
        "and suspicious patterns"
    ),
    "Variance Analysis": (
        "Analyze December 2024 budget vs actual variances and write a "
        "CFO-ready narrative for accounts with >5% variance"
    ),
    "Reconciliations": (
        "Review the status of all December 2024 account reconciliations "
        "and identify items requiring escalation"
    ),
    "Accrual Schedule": (
        "Review the December 2024 accrual schedule for completeness "
        "and validate all entries are properly supported"
    ),
    "Salary Accrual JE": (
        "Generate a journal entry to accrue $285,000 of unpaid December "
        "salaries as of period end"
    ),
}

PERIOD_OPTIONS = [
    "2024-12", "2024-11", "2024-10", "2024-09",
    "2024-08", "2024-07", "2024-06",
]

MODEL_OPTIONS = {
    "mistral":     "Mistral 7B",
    "llama3.2:3b": "Llama 3.2 3B (fast)",
    "qwen2.5:7b":  "Qwen 2.5 7B (math)",
}

# ── Session state ─────────────────────────────────────────────────────────────

def _init_session():
    defaults = {
        "result":         None,
        "selected_query": DEMO_QUERIES["Variance Analysis"],
        "running":        False,
        "error":          None,
        "session_id":     str(uuid.uuid4())[:8],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()

# ── Ollama check ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=30, show_spinner=False)
def _check_ollama() -> bool:
    try:
        r = subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
        return r.returncode == 0
    except Exception:
        return False

# ── Pipeline thread ───────────────────────────────────────────────────────────

def _run_pipeline_thread(query: str, period: str, requested_by: str,
                         model: str, result_q: queue.Queue):
    try:
        os.environ["FINCLOSE_MODEL"] = model
        from pipeline import run_pipeline
        result_q.put(("ok", run_pipeline(query=query, period=period,
                                         requested_by=requested_by)))
    except Exception as exc:
        result_q.put(("err", str(exc)))

# ── Helpers ───────────────────────────────────────────────────────────────────

def _compact(v: float) -> str:
    av = abs(v)
    if av >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if av >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"

def _pct_color(pct: float) -> str:
    if pct >= 80:
        return C_GREEN
    if pct >= 50:
        return C_AMBER
    return C_RED

# ── Cached DB fetchers ────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_gl(period):        return get_gl_transactions(period, limit=500)

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_recons(period):    return get_reconciliations(period)

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_accruals(period):  return get_accruals(period)

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_variances(period): return get_variance_analysis(period)

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_anomalies(period): return get_anomalous_entries(period)

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_ar(period):        return get_ar_aging(period)

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_tb(period):        return get_trial_balance(period)

# ── KPI strip data ────────────────────────────────────────────────────────────

def _kpi_data(period: str) -> dict:
    try:
        gl       = _fetch_gl(period)
        recons   = _fetch_recons(period)
        accruals = _fetch_accruals(period)
        variances= _fetch_variances(period)
        return {
            "gl_entries":      gl["record_count"],
            "accrual_exposure":accruals["total_accrual_amount"],
            "open_recons":     sum(1 for r in recons["records"]
                                   if r["status"] != "Reconciled"),
            "var_breaches":    variances["threshold_breaches"],
            "unexplained_diff":recons["total_unexplained_difference"],
        }
    except Exception:
        return {
            "gl_entries": "—", "accrual_exposure": "—",
            "open_recons": "—", "var_breaches": "—",
            "unexplained_diff": "—",
        }

# ── Close status board data ───────────────────────────────────────────────────

def _close_status(period: str) -> dict:
    try:
        recons    = _fetch_recons(period)
        accruals  = _fetch_accruals(period)
        variances = _fetch_variances(period)
        anomalies = _fetch_anomalies(period)

        r_total = len(recons["records"])
        r_done  = sum(1 for r in recons["records"] if r["status"] == "Reconciled")

        a_total = len(accruals["records"])
        a_done  = sum(1 for r in accruals["records"] if r["status"] == "Posted")

        v_total = variances["record_count"]
        v_ok    = v_total - variances["threshold_breaches"]

        anom_count = anomalies["anomaly_count"]

        return {
            "recons":   (r_done, r_total),
            "accruals": (a_done, a_total),
            "variances":(v_ok,   v_total),
            "anomalies": anom_count,
        }
    except Exception:
        return {
            "recons": (0, 0), "accruals": (0, 0),
            "variances": (0, 0), "anomalies": 0,
        }

# ── Chart base ────────────────────────────────────────────────────────────────

_CL = dict(
    paper_bgcolor=C_BG,
    plot_bgcolor=C_CARD,
    font=dict(family="IBM Plex Mono, Courier New, monospace", color=C_TEXT2, size=10),
    margin=dict(l=10, r=10, t=36, b=10),
)

def _empty_chart(title: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **_CL,
        title=dict(text=title, font=dict(color=C_TEXT3, size=11), x=0.02),
        annotations=[dict(text="No data available", x=0.5, y=0.5,
                          showarrow=False, font=dict(color=C_TEXT3, size=11))],
    )
    return fig

# ── Charts ────────────────────────────────────────────────────────────────────

def _chart_trial_balance(period: str) -> go.Figure:
    try:
        records = _fetch_tb(period).get("records", [])
        if not records:
            return _empty_chart("Trial Balance")
        df = pd.DataFrame(records)
        grp = df.groupby("account_type")["ending_balance"].sum().reset_index()
        color_map = {
            "asset": C_GOLD, "liability": C_RED, "equity": C_GREEN,
            "revenue": C_BLUE, "expense": C_AMBER,
        }
        colors = [color_map.get((t or "").lower(), C_TEXT2) for t in grp["account_type"]]
        fig = go.Figure(go.Bar(
            x=grp["account_type"],
            y=grp["ending_balance"],
            marker_color=colors,
            marker_line_color=C_BORDER,
            marker_line_width=1,
            text=[_compact(v) for v in grp["ending_balance"]],
            textposition="outside",
            textfont=dict(size=9, color=C_TEXT),
        ))
        fig.update_layout(
            **_CL,
            title=dict(text="Trial Balance", font=dict(color=C_GOLD, size=11), x=0.02),
            xaxis=dict(tickfont=dict(size=9), gridcolor=C_BORDER, linecolor=C_BORDER),
            yaxis=dict(tickfont=dict(size=9), gridcolor=C_BORDER,
                       showgrid=True, tickformat="$,.0f"),
            showlegend=False,
        )
        return fig
    except Exception:
        return _empty_chart("Trial Balance")


def _chart_variance(period: str) -> go.Figure:
    try:
        records = _fetch_variances(period).get("records", [])
        if not records:
            return _empty_chart("Variance Analysis")
        df = pd.DataFrame(records).head(8)
        names   = df.get("account_name", df.index.astype(str)).str[:16]
        breach  = df.get("threshold_breached", pd.Series([False] * len(df)))
        pct     = df.get("vs_budget_pct", pd.Series([0.0] * len(df)))
        actual_colors = [C_RED if b else C_GOLD for b in breach]

        hover_budget = [
            f"{row.get('account_name','')}<br>Budget: {_compact(row['budget_amount'])}"
            for _, row in df.iterrows()
        ]
        hover_actual = [
            f"{row.get('account_name','')}<br>Actual: {_compact(row['actual_amount'])}"
            f"<br>vs Budget: {row.get('vs_budget_pct',0):.1f}%"
            f"{'  ⚠ BREACH' if row.get('threshold_breached') else ''}"
            for _, row in df.iterrows()
        ]

        fig = go.Figure()
        fig.add_trace(go.Bar(
            name="Budget", x=names, y=df["budget_amount"],
            marker_color=C_BORDER2, marker_line_width=0, opacity=0.85,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_budget,
        ))
        fig.add_trace(go.Bar(
            name="Actual", x=names, y=df["actual_amount"],
            marker_color=actual_colors, marker_line_width=0,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_actual,
        ))
        fig.update_layout(
            **_CL,
            title=dict(text="Variance Analysis", font=dict(color=C_GOLD, size=11), x=0.02),
            barmode="group",
            xaxis=dict(tickfont=dict(size=8), tickangle=-30, gridcolor=C_BORDER),
            yaxis=dict(tickfont=dict(size=9), gridcolor=C_BORDER, tickformat="$,.0f"),
            legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)",
                        x=0.01, y=0.99, xanchor="left", yanchor="top"),
        )
        return fig
    except Exception:
        return _empty_chart("Variance Analysis")


def _chart_ar_aging(period: str) -> go.Figure:
    try:
        summary = _fetch_ar(period).get("aging_summary", [])
        if not summary:
            return _empty_chart("AR Aging")
        df = pd.DataFrame(summary)
        palette = [C_GREEN, C_GOLD, C_AMBER, C_RED]
        fig = go.Figure(go.Pie(
            labels=df["aging_bucket"],
            values=df["total_balance"],
            hole=0.58,
            marker=dict(colors=palette[:len(df)], line=dict(color=C_BG, width=2)),
            textinfo="percent",
            textfont=dict(size=10, color=C_TEXT),
            hovertemplate="%{label}<br>%{customdata}<br>%{percent}<extra></extra>",
            customdata=[_compact(v) for v in df["total_balance"]],
        ))
        fig.update_layout(
            **_CL,
            title=dict(text="AR Aging", font=dict(color=C_GOLD, size=11), x=0.02),
            legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
        )
        return fig
    except Exception:
        return _empty_chart("AR Aging")


def _chart_accruals(period: str) -> go.Figure:
    try:
        records = _fetch_accruals(period).get("records", [])
        if not records:
            return _empty_chart("Accrual Status")
        df  = pd.DataFrame(records)
        grp = df.groupby("status")["amount"].sum().reset_index()
        palette = {
            "Posted":           C_GREEN,
            "Pending":          C_GOLD,
            "Pending Review":   C_AMBER,
            "Pending Approval": C_AMBER,
            "Reversed":         C_RED,
        }
        colors = [palette.get(s, C_BLUE) for s in grp["status"]]
        fig = go.Figure(go.Pie(
            labels=grp["status"],
            values=grp["amount"],
            hole=0.58,
            marker=dict(colors=colors, line=dict(color=C_BG, width=2)),
            textinfo="percent",
            textfont=dict(size=10, color=C_TEXT),
            hovertemplate="%{label}<br>%{customdata}<extra></extra>",
            customdata=[_compact(v) for v in grp["amount"]],
        ))
        fig.update_layout(
            **_CL,
            title=dict(text="Accrual Status", font=dict(color=C_GOLD, size=11), x=0.02),
            legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)"),
        )
        return fig
    except Exception:
        return _empty_chart("Accrual Status")

# ── Verdict pill ──────────────────────────────────────────────────────────────

def _verdict_html(verdict: str) -> str:
    cfg = {
        "APPROVED": ("verdict-approved", "✓"),
        "FLAGGED":  ("verdict-flagged",  "⚠"),
        "REJECTED": ("verdict-rejected", "✗"),
    }
    cls, icon = cfg.get(verdict, ("verdict-pending", "—"))
    return f'<div class="verdict-pill {cls}">{icon}&nbsp; {verdict or "—"}</div>'

# ── Confidence gauge ──────────────────────────────────────────────────────────

def _confidence_gauge(score: float) -> go.Figure:
    color = C_GREEN if score >= 0.8 else C_AMBER if score >= 0.5 else C_RED
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=round(score * 100, 1),
        number=dict(suffix="%",
                    font=dict(color=color, size=26,
                              family="IBM Plex Mono, monospace")),
        gauge=dict(
            axis=dict(range=[0, 100],
                      tickfont=dict(size=9, color=C_TEXT2),
                      tickcolor=C_BORDER),
            bar=dict(color=color, thickness=0.25),
            bgcolor=C_BORDER,
            borderwidth=0,
            steps=[
                dict(range=[0,  50], color=C_INPUT),
                dict(range=[50, 80], color=C_CARD),
                dict(range=[80,100], color=C_CARD),
            ],
            threshold=dict(
                line=dict(color=C_TEXT3, width=1),
                thickness=0.75,
                value=80,
            ),
        ),
        domain=dict(x=[0, 1], y=[0, 1]),
    ))
    fig.update_layout(
        paper_bgcolor=C_BG, plot_bgcolor=C_BG,
        font=dict(family="IBM Plex Mono, monospace", color=C_TEXT2),
        height=155,
        margin=dict(l=20, r=20, t=20, b=10),
    )
    return fig

# ── Analysis renderer ─────────────────────────────────────────────────────────

def _render_analysis(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        if re.match(r"^#{1,3}\s+", line):
            heading = re.sub(r"^#{1,3}\s+", "", line).strip()
            lines.append(f"<h3>{heading}</h3>")
        elif re.match(r"^[A-Z][A-Z\s]{3,}:\s*$", line.strip()):
            lines.append(f"<h3>{line.strip()}</h3>")
        else:
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            line = re.sub(
                r"(\$[\d,]+(?:\.\d+)?(?:[KMB])?|\b\d[\d,]*(?:\.\d+)?%)",
                r'<span class="num">\1</span>', line,
            )
            # safe-escape while preserving injected tags
            safe = (line
                .replace("&", "&amp;")
                .replace("<strong>", "\x00STRONG\x00")
                .replace("</strong>", "\x00/STRONG\x00")
                .replace('<span class="num">', "\x00NUM\x00")
                .replace("</span>", "\x00/NUM\x00")
                .replace("<h3>", "\x00H3\x00")
                .replace("</h3>", "\x00/H3\x00")
                .replace("<", "&lt;").replace(">", "&gt;")
                .replace("\x00STRONG\x00", "<strong>")
                .replace("\x00/STRONG\x00", "</strong>")
                .replace("\x00NUM\x00", '<span class="num">')
                .replace("\x00/NUM\x00", "</span>")
                .replace("\x00H3\x00", "<h3>")
                .replace("\x00/H3\x00", "</h3>")
            )
            lines.append(safe if safe.strip() else "<br>")
    return "\n".join(lines)

# ── Export helpers ────────────────────────────────────────────────────────────

def _build_audit_json(result) -> str:
    entries = []
    for e in result.audit_log:
        entries.append(dataclasses.asdict(e))
    payload = {
        "session_id":    result.session_id,
        "period":        result.period,
        "query":         result.user_query,
        "requested_by":  result.requested_by,
        "verdict":       result.critic_verdict,
        "confidence":    result.confidence_score,
        "sox_flags":     [f.value if hasattr(f, "value") else str(f)
                          for f in result.sox_flags],
        "processing_ms": result.processing_ms,
        "exported_at":   datetime.utcnow().isoformat() + "Z",
        "audit_entries": entries,
    }
    return json.dumps(payload, indent=2, default=str)

def _build_analysis_txt(result) -> str:
    lines = [
        f"FinClose AI — Analysis Report",
        f"{'=' * 50}",
        f"Session:    {result.session_id}",
        f"Period:     {result.period}",
        f"Requested:  {result.requested_by}",
        f"Verdict:    {result.critic_verdict}",
        f"Confidence: {result.confidence_score:.0%}",
        f"SOX Flags:  {len(result.sox_flags)}",
        f"Generated:  {datetime.utcnow().isoformat()}Z",
        f"{'=' * 50}",
        f"",
        result.final_response,
    ]
    if result.sox_flags:
        lines += ["", "SOX FLAGS", "-" * 30]
        for flag, detail in zip(result.sox_flags, result.sox_flag_details or []):
            fv = flag.value if hasattr(flag, "value") else str(flag)
            lines.append(f"• {fv}: {detail}")
            rem = SOX_REMEDIATION.get(fv)
            if rem:
                lines.append(f"  Action: {rem}")
    return "\n".join(lines)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown(
        f'<div style="color:{C_GOLD};font-size:1.05rem;font-weight:700;'
        f'letter-spacing:0.08em;margin-bottom:0.15rem;">⬡ FINCLOSE AI</div>'
        f'<div style="color:{C_TEXT3};font-size:0.68rem;margin-bottom:1rem;">'
        f'Multi-Agent Accounting Automation</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<hr style="border-color:{C_BORDER};margin:0 0 0.75rem;">', unsafe_allow_html=True)

    period    = st.selectbox("Period", PERIOD_OPTIONS, index=0)
    model_key = st.selectbox("Model", list(MODEL_OPTIONS.keys()),
                             format_func=lambda k: MODEL_OPTIONS[k])
    analyst   = st.text_input("Requested By", value="analyst")

    st.markdown(f'<hr style="border-color:{C_BORDER};margin:0.75rem 0 0.5rem;">', unsafe_allow_html=True)
    st.markdown('<div class="section-label">Quick Launch</div>', unsafe_allow_html=True)

    for label, query in DEMO_QUERIES.items():
        if st.button(label, key=f"ql_{label}", use_container_width=True):
            st.session_state["selected_query"] = query

    st.markdown(f'<hr style="border-color:{C_BORDER};margin:0.75rem 0 0.5rem;">', unsafe_allow_html=True)

    ollama_ok = _check_ollama()
    st.markdown(
        f'<span class="status-online">● OLLAMA ONLINE</span>'
        if ollama_ok else
        f'<span class="status-offline">✗ OLLAMA OFFLINE</span>',
        unsafe_allow_html=True,
    )

# ══════════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ══════════════════════════════════════════════════════════════════════════════

result     = st.session_state.get("result")
proc_ms    = getattr(result, "processing_ms", 0.0) if result else 0.0
session_id = result.session_id if result else st.session_state["session_id"]
right_text = (
    f"session&nbsp;{session_id}&nbsp;&nbsp;·&nbsp;&nbsp;{proc_ms/1000:.1f}s"
    if result else f"session&nbsp;{session_id}"
)

# ── Nav bar ───────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="nav-bar">
  <div style="display:flex;align-items:center;">
    <span class="nav-logo">⬡ FINCLOSE AI</span>
    <span class="nav-badge-period">{period}</span>
    <span class="nav-badge-model">{model_key}</span>
  </div>
  <div class="nav-right">{right_text}</div>
</div>
""", unsafe_allow_html=True)

if not ollama_ok:
    st.warning(
        "Ollama is not running — pipeline disabled. "
        "Charts and DB data load regardless. "
        "Start with: `ollama serve && ollama pull mistral`"
    )

# ── KPI strip ─────────────────────────────────────────────────────────────────
kpi = _kpi_data(period)

gl_val       = f"{kpi['gl_entries']:,}" if isinstance(kpi['gl_entries'], int) else "—"
acc_val      = _compact(kpi['accrual_exposure']) if isinstance(kpi['accrual_exposure'], (int, float)) else "—"
rec_val      = str(kpi['open_recons']) if isinstance(kpi['open_recons'], int) else "—"
bre_val      = str(kpi['var_breaches']) if isinstance(kpi['var_breaches'], int) else "—"
diff_val     = _compact(kpi['unexplained_diff']) if isinstance(kpi['unexplained_diff'], (int, float)) else "—"
breach_color = C_RED if isinstance(kpi['var_breaches'], int) and kpi['var_breaches'] > 0 else C_GREEN
recon_color  = C_AMBER if isinstance(kpi['open_recons'], int) and kpi['open_recons'] > 0 else C_GREEN

def _kpi_card(accent: str, label: str, value: str, sub: str) -> str:
    return (f'<div class="kpi-card" style="background:{C_CARD};border:1px solid {C_BORDER};'
            f'border-radius:6px;padding:0.75rem 1rem;border-left:3px solid {accent};">'
            f'<div style="color:{C_TEXT2};font-size:0.62rem;text-transform:uppercase;'
            f'letter-spacing:0.1em;margin-bottom:0.3rem;">{label}</div>'
            f'<div style="font-size:1.5rem;font-weight:700;color:{accent};line-height:1;'
            f'margin-bottom:0.15rem;">{value}</div>'
            f'<div style="color:{C_TEXT3};font-size:0.65rem;">{sub}</div>'
            f'</div>')

k1, k2, k3, k4 = st.columns(4, gap="small")
with k1:
    st.markdown(_kpi_card(C_GOLD,  "GL Entries",        gl_val,  f"Period {period}"), unsafe_allow_html=True)
with k2:
    st.markdown(_kpi_card(C_BLUE,  "Total Accruals",    acc_val, "Accrued this period"), unsafe_allow_html=True)
with k3:
    st.markdown(_kpi_card(recon_color,  "Open Recons",  rec_val, f"Unexplained: {diff_val}"), unsafe_allow_html=True)
with k4:
    st.markdown(_kpi_card(breach_color, "Variance Breaches", bre_val, "Above threshold"), unsafe_allow_html=True)

# ── Close status board ────────────────────────────────────────────────────────
cs = _close_status(period)

r_done, r_total = cs["recons"]
a_done, a_total = cs["accruals"]
v_ok,   v_total = cs["variances"]
anom_n          = cs["anomalies"]
anom_color      = C_RED if anom_n > 0 else C_GREEN
anom_label      = "REVIEW REQUIRED" if anom_n > 0 else "CLEAN"

def _status_card(title: str, done: int, total: int, lbl_ok: str, lbl_warn: str) -> str:
    pct  = round(done / total * 100) if total else 0
    col  = _pct_color(pct)
    lbl  = lbl_ok if pct == 100 else lbl_warn
    bar  = f'<div style="background:{C_BORDER};border-radius:2px;height:4px;margin:0.4rem 0 0.35rem;overflow:hidden;"><div style="width:{pct}%;height:4px;background:{col};border-radius:2px;"></div></div>'
    return (f'<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:6px;padding:0.8rem 1rem;">'
            f'<div style="color:{C_TEXT2};font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.4rem;">{title}</div>'
            f'<div style="font-size:1rem;font-weight:700;color:{col};margin-bottom:0;">{done} / {total}</div>'
            f'{bar}'
            f'<div style="font-size:0.62rem;letter-spacing:0.06em;text-transform:uppercase;color:{col};">{pct}% {lbl}</div>'
            f'</div>')

def _anomaly_card() -> str:
    col  = anom_color
    fill = "0" if anom_n == 0 else "100"
    bar  = f'<div style="background:{C_BORDER};border-radius:2px;height:4px;margin:0.4rem 0 0.35rem;overflow:hidden;"><div style="width:{fill}%;height:4px;background:{col};border-radius:2px;"></div></div>'
    return (f'<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:6px;padding:0.8rem 1rem;">'
            f'<div style="color:{C_TEXT2};font-size:0.62rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.4rem;">Anomalies Detected</div>'
            f'<div style="font-size:1rem;font-weight:700;color:{col};margin-bottom:0;">{anom_n}</div>'
            f'{bar}'
            f'<div style="font-size:0.62rem;letter-spacing:0.06em;text-transform:uppercase;color:{col};">{anom_label}</div>'
            f'</div>')

st.markdown(f'<div style="color:{C_TEXT2};font-size:0.65rem;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:0.4rem;padding-bottom:0.3rem;border-bottom:1px solid {C_BORDER};">Close Status — {period}</div>', unsafe_allow_html=True)

b1, b2, b3, b4 = st.columns(4, gap="small")
with b1:
    st.markdown(_status_card("Reconciliations",   r_done, r_total, "COMPLETE",         "IN PROGRESS"), unsafe_allow_html=True)
with b2:
    st.markdown(_status_card("Accruals Posted",   a_done, a_total, "COMPLETE",         "PENDING"),     unsafe_allow_html=True)
with b3:
    st.markdown(_status_card("Variances Reviewed",v_ok,   v_total, "WITHIN THRESHOLD", "BREACHES EXIST"), unsafe_allow_html=True)
with b4:
    st.markdown(_anomaly_card(), unsafe_allow_html=True)

# ── Row 1: Run Close + Verdict ────────────────────────────────────────────────
col_run, col_verdict = st.columns([1.1, 0.9], gap="medium")

with col_run:
    st.markdown('<div class="panel-title">Run Monthly Close</div>', unsafe_allow_html=True)
    task_text = st.text_area(
        "task", value=st.session_state["selected_query"],
        height=88, label_visibility="collapsed", key="task_input",
    )
    run_btn = st.button(
        "⬡  RUN MONTHLY CLOSE",
        use_container_width=True,
        disabled=st.session_state["running"] or not ollama_ok,
        type="primary", key="run_btn",
    )

    if run_btn and not st.session_state["running"]:
        st.session_state["running"] = True
        st.session_state["result"]  = None
        st.session_state["error"]   = None

        result_q: queue.Queue = queue.Queue()
        thread = threading.Thread(
            target=_run_pipeline_thread,
            args=(task_text, period, analyst, model_key, result_q),
            daemon=True,
        )
        thread.start()

        STEPS = [
            ("Planner",   "Classifying task & building execution plan...", 2.0),
            ("Retriever", "Querying Oracle GL, AP, AR & Blackline...",     3.0),
            ("Executor",  "Running LLM analysis...",                        0.0),
            ("Critic",    "SOX review & confidence scoring...",             0.5),
        ]
        with st.status("Running pipeline...", expanded=True) as status_box:
            for i, (name, desc, delay) in enumerate(STEPS):
                st.write(f"[{name}] {desc}")
                if i < 2:
                    time.sleep(delay)
                elif i == 2:
                    thread.join(timeout=300)
                else:
                    time.sleep(delay)
            status_box.update(label="Pipeline complete", state="complete")

        tag, payload = result_q.get()
        if tag == "ok":
            st.session_state["result"] = payload
        else:
            st.session_state["error"] = payload

        st.session_state["running"] = False
        st.rerun()

    if st.session_state.get("error"):
        err = st.session_state["error"]
        if any(k in err.lower() for k in ("connection", "refused", "httpx")):
            st.warning("Ollama connection refused. Run `ollama serve`.")
        else:
            st.error(f"Pipeline error: {err}")

with col_verdict:
    st.markdown('<div class="panel-title">Verdict</div>', unsafe_allow_html=True)

    if result:
        verdict = result.critic_verdict or "—"
        conf    = result.confidence_score or 0.0
        n_flags = len(result.sox_flags)

        st.markdown(_verdict_html(verdict), unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.metric("Confidence", f"{conf*100:.0f}%")
        with c2:
            st.metric("SOX Flags", n_flags)

        st.plotly_chart(_confidence_gauge(conf), use_container_width=True,
                        config={"displayModeBar": False})

        st.markdown(f"""
        <div class="conf-thresholds">
          <span class="conf-t-green">≥80% Auto-approve</span>&nbsp;·&nbsp;
          <span class="conf-t-amber">50–79% Manual review</span>&nbsp;·&nbsp;
          <span class="conf-t-red">&lt;50% Escalate</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="verdict-pill verdict-pending">— AWAITING RUN</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="color:{C_TEXT3};font-size:0.75rem;margin-top:0.75rem;">'
            f'Select a task and click RUN MONTHLY CLOSE.</div>',
            unsafe_allow_html=True,
        )

# ── Row 2: Analysis + SOX Flags ──────────────────────────────────────────────
col_analysis, col_sox = st.columns([1.1, 0.9], gap="medium")

with col_analysis:
    st.markdown('<div class="panel-title">Analysis Output</div>', unsafe_allow_html=True)
    if result and result.final_response:
        rendered = _render_analysis(result.final_response)
        st.markdown(f'<div class="analysis-box">{rendered}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f'<div class="analysis-box" style="color:{C_TEXT3};">'
            f'Analysis output will appear here after pipeline run.</div>',
            unsafe_allow_html=True,
        )

with col_sox:
    st.markdown('<div class="panel-title">SOX Flags</div>', unsafe_allow_html=True)

    if result and result.sox_flags:
        sox_rows = []
        for flag, detail in zip(result.sox_flags, result.sox_flag_details or []):
            fv = flag.value if hasattr(flag, "value") else str(flag)
            sox_rows.append({
                "Flag":      fv,
                "Detail":    detail,
                "Action Required": SOX_REMEDIATION.get(fv, "Review with controller."),
            })
        sox_df = pd.DataFrame(sox_rows)

        sev = {
            "SELF_APPROVAL":        f"color:{C_RED}",
            "UNBALANCED_ENTRY":     f"color:{C_RED}",
            "MISSING_APPROVER":     f"color:{C_AMBER}",
            "THRESHOLD_BREACH":     f"color:{C_AMBER}",
            "WEEKEND_POSTING":      f"color:{C_GOLD}",
            "ROUND_NUMBER_MANUAL":  f"color:{C_GOLD}",
            "PRIOR_PERIOD_POSTING": f"color:{C_BLUE}",
            "UNUSUAL_ACCOUNT_COMBO":f"color:{C_BLUE}",
        }
        def _color_sox(row):
            s = sev.get(row["Flag"], f"color:{C_TEXT}")
            return [s, f"color:{C_TEXT2}", f"color:{C_TEXT3}"]

        st.dataframe(
            sox_df.style.apply(_color_sox, axis=1),
            use_container_width=True, hide_index=True,
            height=min(260, 50 + 35 * len(sox_df)),
        )
    elif result:
        st.markdown(
            f'<div style="color:{C_GREEN};font-size:0.82rem;margin-top:0.4rem;">'
            f'✓ No SOX flags detected</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div style="color:{C_TEXT3};font-size:0.75rem;margin-top:0.4rem;">'
            f'SOX flags will appear here after pipeline run.</div>',
            unsafe_allow_html=True,
        )

# ── Charts ────────────────────────────────────────────────────────────────────
freshness = datetime.now().strftime("%H:%M:%S")

st.markdown(f'<hr style="border-color:{C_BORDER};margin:1rem 0 0.4rem;">', unsafe_allow_html=True)
st.markdown(
    f'<div class="section-label">Financial Dashboards — {period}'
    f'<span class="freshness">Data loaded {freshness}</span></div>',
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4, gap="small")
_opts = {"displayModeBar": False}

with c1:
    st.plotly_chart(_chart_trial_balance(period), use_container_width=True, config=_opts)
with c2:
    st.plotly_chart(_chart_variance(period),      use_container_width=True, config=_opts)
with c3:
    st.plotly_chart(_chart_ar_aging(period),      use_container_width=True, config=_opts)
with c4:
    st.plotly_chart(_chart_accruals(period),      use_container_width=True, config=_opts)

# ── Audit trail + exports ─────────────────────────────────────────────────────
st.markdown(f'<hr style="border-color:{C_BORDER};margin:0.5rem 0;">', unsafe_allow_html=True)

audit_entries = result.audit_log if result else []
n_entries     = len(audit_entries)

# Export buttons (only shown post-run)
if result:
    exp_col1, exp_col2, _ = st.columns([1, 1, 4])
    with exp_col1:
        st.download_button(
            label="Export Audit Log",
            data=_build_audit_json(result),
            file_name=f"finclose_audit_{result.session_id}_{period}.json",
            mime="application/json",
            use_container_width=True,
        )
    with exp_col2:
        st.download_button(
            label="Export Analysis",
            data=_build_analysis_txt(result),
            file_name=f"finclose_analysis_{result.session_id}_{period}.txt",
            mime="text/plain",
            use_container_width=True,
        )

with st.expander(f"Audit Trail — {n_entries} entries", expanded=False):
    if audit_entries:
        rows = []
        for e in audit_entries:
            rows.append({
                "Timestamp":  e.timestamp,
                "Agent":      e.agent,
                "Action":     e.action,
                "SOX Flags":  ", ".join(e.sox_flags) if e.sox_flags else "—",
                "Confidence": f"{e.confidence:.0%}",
                "Reasoning":  e.reasoning[:130] + ("…" if len(e.reasoning) > 130 else ""),
            })
        audit_df = pd.DataFrame(rows)

        def _audit_style(row):
            if row["SOX Flags"] != "—":
                return [f"color:{C_AMBER}"] * len(row)
            return [f"color:{C_TEXT2}"] * len(row)

        st.dataframe(
            audit_df.style.apply(_audit_style, axis=1),
            use_container_width=True, hide_index=True,
            height=min(400, 60 + 35 * n_entries),
        )
    else:
        st.markdown(
            f'<div style="color:{C_TEXT3};font-size:0.75rem;padding:0.4rem;">'
            f'Audit trail will appear here after pipeline run.</div>',
            unsafe_allow_html=True,
        )
