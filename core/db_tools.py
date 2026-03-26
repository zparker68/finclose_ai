"""
finclose_ai/core/db_tools.py
─────────────────────────────
SQL tool layer that agents call to query the simulated enterprise systems.
Each function represents a "mock integration" with Oracle Fusion GL/AP/AR
or Blackline — in a real deployment these become REST API calls with auth.

Design: pure functions, no side effects, all return typed dicts.
Agents never get raw DB cursors — only structured results with provenance.
"""

from __future__ import annotations
import sqlite3
import hashlib
import json
import os
from typing import Any

DB_PATH = os.environ.get(
    "FINCLOSE_DB",
    os.path.join(os.path.dirname(__file__), "../finclose_data_gen/finclose.db")
)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


def _hash(data: Any) -> str:
    return hashlib.sha256(json.dumps(str(data), sort_keys=True).encode()).hexdigest()[:12]


# ── Oracle GL ─────────────────────────────────────────────────────────────────

def get_gl_transactions(period: str, account_code: str | None = None,
                        limit: int = 100) -> dict:
    """
    Simulates: GET /api/oracle/gl?period=&account=&limit=
    Returns journal entries for the period, optionally filtered by account.
    """
    with _conn() as conn:
        if account_code:
            rows = conn.execute(
                """SELECT je_id, txn_date, account_code, account_name,
                          debit, credit, description, entry_type,
                          created_by, approved_by, legal_entity_name,
                          cost_center_name, is_anomaly, anomaly_type
                   FROM gl_transactions
                   WHERE period=? AND account_code=?
                   LIMIT ?""",
                (period, account_code, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT je_id, txn_date, account_code, account_name,
                          debit, credit, description, entry_type,
                          created_by, approved_by, legal_entity_name,
                          cost_center_name, is_anomaly, anomaly_type
                   FROM gl_transactions WHERE period=? LIMIT ?""",
                (period, limit)
            ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Oracle Fusion GL",
        "endpoint": f"/api/oracle/gl?period={period}",
        "period": period,
        "record_count": len(data),
        "data_hash": _hash(data),
        "records": data,
    }


def get_anomalous_entries(period: str) -> dict:
    """Returns only flagged/anomalous journal entries for Critic agent review."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT je_id, txn_date, account_code, account_name,
                      debit, credit, description, entry_type,
                      created_by, approved_by, anomaly_type
               FROM gl_transactions
               WHERE period=? AND is_anomaly=1
               ORDER BY anomaly_type""",
            (period,)
        ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Oracle Fusion GL — Anomaly Scan",
        "period": period,
        "anomaly_count": len(data),
        "data_hash": _hash(data),
        "records": data,
    }


def get_gl_by_anomaly_type(period: str, anomaly_type: str) -> dict:
    """
    Returns all GL entries of a specific anomaly type for drill-down traceability.
    Used by the UI to show the exact source records behind each SOX flag.
    """
    with _conn() as conn:
        rows = conn.execute(
            """SELECT je_id, txn_date, account_code, account_name,
                      debit, credit, description, entry_type,
                      created_by, approved_by, legal_entity_name,
                      cost_center_name, anomaly_type
               FROM gl_transactions
               WHERE period=? AND anomaly_type=?
               ORDER BY txn_date""",
            (period, anomaly_type)
        ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Oracle Fusion GL",
        "period": period,
        "anomaly_type": anomaly_type,
        "record_count": len(data),
        "data_hash": _hash(data),
        "records": data,
    }


def get_unbalanced_entries(period: str) -> dict:
    """
    Calculates net debit-credit by JE ID — any non-zero net is an imbalance.
    Critical SOX control: every JE must balance to zero.
    """
    with _conn() as conn:
        rows = conn.execute(
            """SELECT je_id,
                      SUM(debit)  AS total_debits,
                      SUM(credit) AS total_credits,
                      ROUND(SUM(debit) - SUM(credit), 2) AS imbalance
               FROM gl_transactions
               WHERE period=?
               GROUP BY je_id
               HAVING ABS(SUM(debit) - SUM(credit)) > 0.01
               ORDER BY ABS(SUM(debit) - SUM(credit)) DESC""",
            (period,)
        ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Oracle Fusion GL — Balance Validation",
        "period": period,
        "unbalanced_count": len(data),
        "records": data,
    }


# ── Trial Balance ─────────────────────────────────────────────────────────────

def get_trial_balance(period: str) -> dict:
    """Simulates: GET /api/oracle/tb?period="""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT account_code, account_name, account_type,
                      parent_group, prior_balance, net_activity,
                      ending_balance, variance_amt, variance_pct,
                      recon_status
               FROM trial_balance WHERE current_period=?
               ORDER BY account_code""",
            (period,)
        ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Oracle Fusion GL — Trial Balance",
        "period": period,
        "account_count": len(data),
        "data_hash": _hash(data),
        "records": data,
    }


# ── Blackline Reconciliations ─────────────────────────────────────────────────

def get_reconciliations(period: str, status: str | None = None) -> dict:
    """Simulates: GET /api/blackline/recons?period=&status="""
    with _conn() as conn:
        if status:
            rows = conn.execute(
                """SELECT recon_id, account_code, account_name,
                          gl_balance, sub_ledger_balance, difference,
                          status, preparer, reviewer, due_date,
                          completed_date, notes
                   FROM reconciliations WHERE period=? AND status=?""",
                (period, status)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT recon_id, account_code, account_name,
                          gl_balance, sub_ledger_balance, difference,
                          status, preparer, reviewer, due_date,
                          completed_date, notes
                   FROM reconciliations WHERE period=?
                   ORDER BY ABS(difference) DESC""",
                (period,)
            ).fetchall()
        data = _rows_to_dicts(rows)
    total_diff = sum(abs(r["difference"]) for r in data)
    return {
        "source": "Blackline",
        "endpoint": f"/api/blackline/recons?period={period}",
        "period": period,
        "record_count": len(data),
        "total_unexplained_difference": round(total_diff, 2),
        "data_hash": _hash(data),
        "records": data,
    }


def get_recon_items(recon_id: str) -> dict:
    """Returns supporting line items for a specific reconciliation."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT item_id, item_date, description, amount,
                      category, aging_days, reference
               FROM recon_items WHERE recon_id=?
               ORDER BY aging_days DESC""",
            (recon_id,)
        ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Blackline — Rec Items",
        "recon_id": recon_id,
        "item_count": len(data),
        "records": data,
    }


# ── Oracle AP ─────────────────────────────────────────────────────────────────

def get_ap_invoices(period: str, status: str | None = None) -> dict:
    """Simulates: GET /api/oracle/ap?period=&status="""
    with _conn() as conn:
        if status:
            rows = conn.execute(
                """SELECT invoice_id, vendor_name, vendor_category,
                          invoice_date, due_date, invoice_amount,
                          open_amount, status, po_number
                   FROM ap_invoices WHERE period=? AND status=?
                   ORDER BY invoice_amount DESC""",
                (period, status)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT invoice_id, vendor_name, vendor_category,
                          invoice_date, due_date, invoice_amount,
                          open_amount, status, po_number
                   FROM ap_invoices WHERE period=?
                   ORDER BY invoice_amount DESC""",
                (period,)
            ).fetchall()
        data = _rows_to_dicts(rows)
    total_open = sum(r["open_amount"] for r in data)
    return {
        "source": "Oracle Fusion AP",
        "period": period,
        "record_count": len(data),
        "total_open_payables": round(total_open, 2),
        "records": data,
    }


# ── Oracle AR ─────────────────────────────────────────────────────────────────

def get_ar_aging(period: str) -> dict:
    """Simulates: GET /api/oracle/ar?period="""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT ar_id, customer_name, customer_type,
                      invoice_date, due_date, invoice_amount,
                      open_balance, days_outstanding, aging_bucket,
                      collection_status
               FROM ar_aging WHERE period=?
               ORDER BY open_balance DESC""",
            (period,)
        ).fetchall()
        data = _rows_to_dicts(rows)

        # Aging summary
        summary = conn.execute(
            """SELECT aging_bucket,
                      COUNT(*) as invoice_count,
                      ROUND(SUM(open_balance),2) as total_balance
               FROM ar_aging WHERE period=?
               GROUP BY aging_bucket
               ORDER BY aging_bucket""",
            (period,)
        ).fetchall()
        aging_summary = _rows_to_dicts(summary)

    return {
        "source": "Oracle Fusion AR",
        "period": period,
        "record_count": len(data),
        "aging_summary": aging_summary,
        "records": data,
    }


# ── Accruals ──────────────────────────────────────────────────────────────────

def get_accruals(period: str) -> dict:
    """Returns accrual schedule for the period."""
    with _conn() as conn:
        rows = conn.execute(
            """SELECT accrual_id, description, debit_account,
                      credit_account, amount, accrual_type,
                      prepared_by, status, reversal_period
               FROM accruals WHERE period=?
               ORDER BY amount DESC""",
            (period,)
        ).fetchall()
        data = _rows_to_dicts(rows)
    total = sum(r["amount"] for r in data)
    pending = [r for r in data if r["status"] != "Posted"]
    return {
        "source": "Oracle Fusion GL — Accruals",
        "period": period,
        "total_accrual_amount": round(total, 2),
        "pending_count": len(pending),
        "records": data,
    }


# ── Variance Analysis ─────────────────────────────────────────────────────────

def get_variance_analysis(period: str, threshold_only: bool = False) -> dict:
    """Returns budget vs. actual variance data."""
    with _conn() as conn:
        if threshold_only:
            rows = conn.execute(
                """SELECT va.*, coa.account_name, coa.account_type
                   FROM variance_analysis va
                   JOIN chart_of_accounts coa ON va.account_code = coa.account_code
                   WHERE va.period=? AND va.threshold_breached=1
                   ORDER BY ABS(va.vs_budget_pct) DESC""",
                (period,)
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT va.*, coa.account_name, coa.account_type
                   FROM variance_analysis va
                   JOIN chart_of_accounts coa ON va.account_code = coa.account_code
                   WHERE va.period=?
                   ORDER BY ABS(va.vs_budget_pct) DESC""",
                (period,)
            ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Oracle Fusion GL / Hyperion HFM",
        "period": period,
        "record_count": len(data),
        "threshold_breaches": sum(1 for r in data if r.get("threshold_breached")),
        "records": data,
    }


# ── Policy / RAG Knowledge Base ───────────────────────────────────────────────

def get_policy_documents(category: str | None = None) -> dict:
    """Returns accounting policy text for RAG context injection."""
    with _conn() as conn:
        if category:
            rows = conn.execute(
                "SELECT doc_id, title, category, content FROM policy_documents WHERE category=?",
                (category,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT doc_id, title, category, content FROM policy_documents"
            ).fetchall()
        data = _rows_to_dicts(rows)
    return {
        "source": "Internal Policy Library",
        "record_count": len(data),
        "records": data,
    }


def get_chart_of_accounts() -> dict:
    """Returns full chart of accounts for account validation."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM chart_of_accounts ORDER BY account_code"
        ).fetchall()
        data = _rows_to_dicts(rows)
    return {"source": "Oracle Fusion COA", "records": data}
