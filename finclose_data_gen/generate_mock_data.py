"""
FinClose AI Agent — Mock Accounting Data Generator
Simulates Oracle GL exports, Blackline reconciliations, and trial balance data
Author: Zac Parker (FinClose AI Project)
"""

import sqlite3
import pandas as pd
import numpy as np
import json
import csv
import os
import random
from datetime import datetime, timedelta
from faker import Faker

fake = Faker()
random.seed(42)
np.random.seed(42)

# ── Config ────────────────────────────────────────────────────────────────────
PERIOD = "2024-12"
PERIOD_START = datetime(2024, 12, 1)
PERIOD_END = datetime(2024, 12, 31)
PRIOR_PERIOD = "2024-11"
OUTPUT_DIR = "finclose_data_gen"
DB_PATH = f"{OUTPUT_DIR}/finclose.db"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Chart of Accounts (mimics Oracle COA structure) ───────────────────────────
CHART_OF_ACCOUNTS = [
    # (account_code, account_name, account_type, normal_balance, parent_group)
    ("1000", "Cash - Operating",              "Asset",     "Debit",  "Current Assets"),
    ("1010", "Cash - Payroll",                "Asset",     "Debit",  "Current Assets"),
    ("1100", "Accounts Receivable - Trade",   "Asset",     "Debit",  "Current Assets"),
    ("1110", "Allowance for Doubtful Accts",  "Asset",     "Credit", "Current Assets"),
    ("1200", "Prepaid Expenses",              "Asset",     "Debit",  "Current Assets"),
    ("1210", "Prepaid Insurance",             "Asset",     "Debit",  "Current Assets"),
    ("1500", "Property & Equipment",          "Asset",     "Debit",  "Fixed Assets"),
    ("1510", "Accumulated Depreciation",      "Asset",     "Credit", "Fixed Assets"),
    ("1600", "Intangible Assets",             "Asset",     "Debit",  "Fixed Assets"),
    ("2000", "Accounts Payable",              "Liability", "Credit", "Current Liabilities"),
    ("2010", "Accrued Liabilities",           "Liability", "Credit", "Current Liabilities"),
    ("2020", "Accrued Payroll",               "Liability", "Credit", "Current Liabilities"),
    ("2030", "Deferred Revenue",              "Liability", "Credit", "Current Liabilities"),
    ("2100", "Income Tax Payable",            "Liability", "Credit", "Current Liabilities"),
    ("2500", "Long-Term Debt",                "Liability", "Credit", "Long-Term Liabilities"),
    ("3000", "Common Stock",                  "Equity",    "Credit", "Equity"),
    ("3100", "Retained Earnings",             "Equity",    "Credit", "Equity"),
    ("3200", "Additional Paid-In Capital",    "Equity",    "Credit", "Equity"),
    ("4000", "Revenue - Gaming",              "Revenue",   "Credit", "Revenue"),
    ("4010", "Revenue - Interactive",         "Revenue",   "Credit", "Revenue"),
    ("4020", "Revenue - Lottery Systems",     "Revenue",   "Credit", "Revenue"),
    ("4900", "Other Income",                  "Revenue",   "Credit", "Revenue"),
    ("5000", "Cost of Revenue",               "Expense",   "Debit",  "COGS"),
    ("5010", "Cost of Revenue - Hardware",    "Expense",   "Debit",  "COGS"),
    ("6000", "Salaries & Wages",              "Expense",   "Debit",  "Operating Expenses"),
    ("6010", "Employee Benefits",             "Expense",   "Debit",  "Operating Expenses"),
    ("6020", "Payroll Taxes",                 "Expense",   "Debit",  "Operating Expenses"),
    ("6100", "Rent & Occupancy",              "Expense",   "Debit",  "Operating Expenses"),
    ("6110", "Utilities",                     "Expense",   "Debit",  "Operating Expenses"),
    ("6200", "Depreciation Expense",          "Expense",   "Debit",  "Operating Expenses"),
    ("6210", "Amortization Expense",          "Expense",   "Debit",  "Operating Expenses"),
    ("6300", "Professional Services",         "Expense",   "Debit",  "Operating Expenses"),
    ("6310", "Legal & Compliance",            "Expense",   "Debit",  "Operating Expenses"),
    ("6400", "Marketing & Advertising",       "Expense",   "Debit",  "Operating Expenses"),
    ("6500", "Travel & Entertainment",        "Expense",   "Debit",  "Operating Expenses"),
    ("6600", "Insurance Expense",             "Expense",   "Debit",  "Operating Expenses"),
    ("6700", "IT & Software",                 "Expense",   "Debit",  "Operating Expenses"),
    ("7000", "Interest Expense",              "Expense",   "Debit",  "Non-Operating"),
    ("7010", "Income Tax Expense",            "Expense",   "Debit",  "Non-Operating"),
]

COST_CENTERS = [
    ("CC-100", "Corporate HQ",        "Las Vegas, NV"),
    ("CC-200", "Gaming Operations",   "Las Vegas, NV"),
    ("CC-300", "Interactive Division","Austin, TX"),
    ("CC-400", "Lottery Systems",     "Atlanta, GA"),
    ("CC-500", "International Ops",   "London, UK"),
    ("CC-600", "Shared Services",     "Las Vegas, NV"),
]

LEGAL_ENTITIES = [
    ("LE-001", "Light & Wonder Inc.",              "Parent"),
    ("LE-002", "LNW Gaming Operations LLC",        "Subsidiary"),
    ("LE-003", "LNW Interactive Ltd.",             "Subsidiary"),
    ("LE-004", "Scientific Games Lottery Corp.",   "Subsidiary"),
]

VENDORS = [
    ("V-1001", "Microsoft Corporation",       "Technology"),
    ("V-1002", "Oracle America Inc.",          "Technology"),
    ("V-1003", "Deloitte LLP",                 "Professional Services"),
    ("V-1004", "CBRE Group",                   "Real Estate"),
    ("V-1005", "ADP LLC",                      "Payroll Services"),
    ("V-1006", "Travelers Insurance",          "Insurance"),
    ("V-1007", "AWS - Amazon Web Services",    "Technology"),
    ("V-1008", "Salesforce Inc.",              "Technology"),
    ("V-1009", "Iron Mountain",                "Records Management"),
    ("V-1010", "FedEx Corporation",            "Logistics"),
    ("V-1011", "WeWork",                       "Facilities"),
    ("V-1012", "Workday Inc.",                 "HR Technology"),
    ("V-1013", "Ernst & Young LLP",            "Professional Services"),
    ("V-1014", "Nevada Power Company",         "Utilities"),
    ("V-1015", "AT&T Inc.",                    "Telecommunications"),
]

CUSTOMERS = [
    ("C-001", "MGM Resorts International",     "Gaming Operator"),
    ("C-002", "Caesars Entertainment",         "Gaming Operator"),
    ("C-003", "Wynn Resorts",                  "Gaming Operator"),
    ("C-004", "Penn Entertainment",            "Gaming Operator"),
    ("C-005", "Hard Rock International",       "Gaming Operator"),
    ("C-006", "Arizona Lottery",               "Lottery Authority"),
    ("C-007", "Texas Lottery Commission",      "Lottery Authority"),
    ("C-008", "New York State Gaming Comm.",   "Lottery Authority"),
    ("C-009", "DraftKings Inc.",               "Interactive"),
    ("C-010", "BetMGM LLC",                    "Interactive"),
]


def random_date(start, end):
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days),
                              hours=random.randint(0, 23),
                              minutes=random.randint(0, 59))


def je_number(n):
    return f"JE-{PERIOD.replace('-','')}-{str(n).zfill(5)}"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. GENERAL LEDGER TRANSACTIONS  (Oracle GL export simulation)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_gl_transactions(n=600):
    """
    Mimics an Oracle GL journal export.
    Each logical journal entry has a header + 2-N lines (debit/credit pairs).
    ~10% of entries contain intentional anomalies for the agent to flag.
    """
    print(f"  Generating {n} GL transactions...")

    coa_dict = {row[0]: row for row in CHART_OF_ACCOUNTS}
    rows = []
    je_counter = 1
    entry_types = ["Manual", "System", "Recurring", "Intercompany", "Accrual", "Reversal"]
    approvers = ["jsmith", "mwilliams", "kpatel", "lrodriguez", "achan", "SYSTEM"]

    # --- Pre-defined realistic transaction templates ---
    templates = [
        # (description, debit_acct, credit_acct, min_amt, max_amt, frequency)
        ("Monthly rent payment",           "6100", "1000", 45000,  120000, 1),
        ("Payroll - biweekly run",         "6000", "2020", 800000, 2500000, 2),
        ("Employer payroll taxes",         "6020", "1000", 75000,  200000, 2),
        ("Employee benefits accrual",      "6010", "2010", 50000,  150000, 1),
        ("Revenue recognition - Gaming",   "1100", "4000", 200000, 1500000, 12),
        ("Revenue recognition - Interactive","1100","4010",50000, 400000, 8),
        ("Revenue recognition - Lottery",  "1100", "4020", 100000, 600000, 6),
        ("Cash collection - AR",           "1000", "1100", 150000, 1200000, 15),
        ("Vendor payment - AP",            "2000", "1000", 5000,   250000, 20),
        ("Depreciation expense",           "6200", "1510", 80000,  180000, 1),
        ("Amortization expense",           "6210", "1600", 20000,  60000, 1),
        ("Software subscription",          "6700", "2000", 8000,   95000, 4),
        ("Professional services accrual",  "6300", "2010", 15000,  300000, 3),
        ("Legal & compliance fees",        "6310", "2000", 10000,  150000, 2),
        ("Marketing campaign spend",       "6400", "2000", 25000,  200000, 3),
        ("T&E reimbursements",             "6500", "1000", 2000,   25000, 6),
        ("Insurance expense allocation",   "6600", "1210", 12000,  40000, 1),
        ("Prepaid insurance amortization", "6600", "1210", 3000,   8000, 1),
        ("Interest expense accrual",       "7000", "2010", 50000,  180000, 1),
        ("Income tax accrual",             "7010", "2100", 100000, 500000, 1),
        ("Deferred revenue recognition",   "2030", "4000", 30000,  200000, 4),
        ("Cost of revenue - services",     "5000", "2000", 50000,  400000, 8),
        ("Utility payments",               "6110", "1000", 8000,   30000, 2),
        ("IT infrastructure costs",        "6700", "2000", 20000,  120000, 3),
        ("Intercompany charge - shared svc","6000","2010", 30000,  150000, 2),
    ]

    for tmpl in templates:
        desc, dr_acct, cr_acct, min_a, max_a, freq = tmpl
        for _ in range(freq):
            if je_counter > n:
                break
            amt = round(random.uniform(min_a, max_a), 2)
            txn_date = random_date(PERIOD_START, PERIOD_END)
            je_id = je_number(je_counter)
            le = random.choice(LEGAL_ENTITIES)
            cc = random.choice(COST_CENTERS)
            entry_type = "System" if "Recognition" in desc or "Depreciation" in desc else random.choice(entry_types[:3])
            approver = "SYSTEM" if entry_type == "System" else random.choice(approvers[:5])

            # Debit line
            rows.append({
                "je_id": je_id,
                "line_num": 1,
                "period": PERIOD,
                "txn_date": txn_date.strftime("%Y-%m-%d"),
                "posted_date": (txn_date + timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d"),
                "account_code": dr_acct,
                "account_name": coa_dict[dr_acct][1],
                "account_type": coa_dict[dr_acct][2],
                "cost_center": cc[0],
                "cost_center_name": cc[1],
                "legal_entity": le[0],
                "legal_entity_name": le[1],
                "debit": amt,
                "credit": 0.00,
                "description": desc,
                "entry_type": entry_type,
                "source_system": "Oracle Fusion GL",
                "created_by": approver,
                "approved_by": approver if entry_type == "System" else random.choice(approvers),
                "reference": f"REF-{random.randint(100000,999999)}",
                "is_anomaly": False,
                "anomaly_type": None,
            })
            # Credit line
            rows.append({
                "je_id": je_id,
                "line_num": 2,
                "period": PERIOD,
                "txn_date": txn_date.strftime("%Y-%m-%d"),
                "posted_date": (txn_date + timedelta(days=random.randint(0, 2))).strftime("%Y-%m-%d"),
                "account_code": cr_acct,
                "account_name": coa_dict[cr_acct][1],
                "account_type": coa_dict[cr_acct][2],
                "cost_center": cc[0],
                "cost_center_name": cc[1],
                "legal_entity": le[0],
                "legal_entity_name": le[1],
                "debit": 0.00,
                "credit": amt,
                "description": desc,
                "entry_type": entry_type,
                "source_system": "Oracle Fusion GL",
                "created_by": approver,
                "approved_by": approver if entry_type == "System" else random.choice(approvers),
                "reference": f"REF-{random.randint(100000,999999)}",
                "is_anomaly": False,
                "anomaly_type": None,
            })
            je_counter += 1

    # --- Inject ~10% anomalies (what the Critic agent must catch) ---
    anomaly_count = max(8, int(len(rows) / 20))
    anomaly_indices = random.sample(range(0, len(rows), 2), min(anomaly_count, len(rows)//2))

    for idx in anomaly_indices:
        atype = random.choice([
            "unbalanced_entry",
            "missing_approver",
            "weekend_posting",
            "round_number_manual",
            "self_approved",
            "unusual_account_combo",
            "prior_period_posting",
        ])
        rows[idx]["is_anomaly"] = True
        rows[idx]["anomaly_type"] = atype

        if atype == "unbalanced_entry":
            rows[idx]["debit"] += random.uniform(0.01, 500.00)  # off by small amount
        elif atype == "missing_approver":
            rows[idx]["approved_by"] = None
        elif atype == "weekend_posting":
            # Force to a weekend
            d = datetime.strptime(rows[idx]["txn_date"], "%Y-%m-%d")
            while d.weekday() not in (5, 6):
                d += timedelta(days=1)
            rows[idx]["txn_date"] = d.strftime("%Y-%m-%d")
        elif atype == "round_number_manual":
            rows[idx]["debit"] = round(rows[idx]["debit"] / 1000) * 1000
            rows[idx]["entry_type"] = "Manual"
        elif atype == "self_approved":
            rows[idx]["approved_by"] = rows[idx]["created_by"]
        elif atype == "prior_period_posting":
            rows[idx]["txn_date"] = f"{PRIOR_PERIOD}-{random.randint(1,28):02d}"

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. TRIAL BALANCE  (current + prior period)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_trial_balance(gl_df):
    """Aggregates GL into a trial balance — current and prior period."""
    print("  Generating trial balance...")

    coa_dict = {row[0]: row for row in CHART_OF_ACCOUNTS}

    # Build prior period balances (seed values)
    prior_balances = {
        "1000": 4_250_000,  "1010": 820_000,   "1100": 12_400_000,
        "1110": -310_000,   "1200": 580_000,   "1210": 145_000,
        "1500": 38_000_000, "1510": -14_200_000,"1600": 9_500_000,
        "2000": -8_300_000, "2010": -2_100_000, "2020": -950_000,
        "2030": -1_800_000, "2100": -620_000,  "2500": -25_000_000,
        "3000": -5_000_000, "3100": -8_500_000, "3200": -3_200_000,
        "4000": -18_500_000,"4010": -6_200_000, "4020": -9_800_000,
        "4900": -450_000,   "5000": 6_800_000,  "5010": 2_100_000,
        "6000": 9_200_000,  "6010": 1_380_000,  "6020": 920_000,
        "6100": 1_080_000,  "6110": 280_000,   "6200": 1_440_000,
        "6210": 360_000,    "6300": 2_100_000,  "6310": 780_000,
        "6400": 1_650_000,  "6500": 320_000,   "6600": 420_000,
        "6700": 1_120_000,  "7000": 980_000,   "7010": 2_400_000,
    }

    # Aggregate current period activity from GL
    current_activity = gl_df.groupby("account_code").agg(
        period_debits=("debit", "sum"),
        period_credits=("credit", "sum")
    ).reset_index()
    current_activity["net_activity"] = current_activity["period_debits"] - current_activity["period_credits"]

    rows = []
    for code, info in coa_dict.items():
        prior_bal = prior_balances.get(code, 0)
        activity_row = current_activity[current_activity["account_code"] == code]
        net_act = float(activity_row["net_activity"].values[0]) if len(activity_row) else 0
        ending_bal = prior_bal + net_act

        # Variance vs prior (for variance analysis agent task)
        variance_pct = ((ending_bal - prior_bal) / abs(prior_bal) * 100) if prior_bal != 0 else 0

        rows.append({
            "account_code": code,
            "account_name": info[1],
            "account_type": info[2],
            "normal_balance": info[3],
            "parent_group": info[4],
            "prior_period": PRIOR_PERIOD,
            "prior_balance": round(prior_bal, 2),
            "period_debits": round(net_act if net_act > 0 else 0, 2),
            "period_credits": round(abs(net_act) if net_act < 0 else 0, 2),
            "net_activity": round(net_act, 2),
            "current_period": PERIOD,
            "ending_balance": round(ending_bal, 2),
            "variance_amt": round(ending_bal - prior_bal, 2),
            "variance_pct": round(variance_pct, 2),
            "requires_recon": info[2] in ("Asset", "Liability"),
            "recon_status": random.choice(["Reconciled", "Reconciled", "Reconciled", "In Progress", "Exception"]),
        })

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BLACKLINE-STYLE RECONCILIATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_reconciliations(trial_balance_df):
    """
    Simulates Blackline account reconciliation workpapers.
    Balance sheet accounts get a rec with supporting items.
    """
    print("  Generating account reconciliations...")

    recon_accounts = trial_balance_df[trial_balance_df["requires_recon"] == True]
    recon_rows = []
    item_rows = []
    item_id = 1

    for _, acct in recon_accounts.iterrows():
        gl_balance = acct["ending_balance"]
        # Simulate sub-ledger or bank balance (slightly different — agent must explain)
        sub_ledger_balance = gl_balance + random.uniform(-500, 500) if random.random() > 0.15 else gl_balance
        difference = round(gl_balance - sub_ledger_balance, 2)

        status = "Reconciled" if abs(difference) < 1.0 else ("Exception" if abs(difference) > 1000 else "In Progress")
        preparer = random.choice(["jsmith", "kpatel", "lrodriguez", "achan"])
        reviewer = random.choice(["mwilliams", "jsmith", "supervisor1"])

        recon_rows.append({
            "recon_id": f"REC-{PERIOD.replace('-','')}-{acct['account_code']}",
            "period": PERIOD,
            "account_code": acct["account_code"],
            "account_name": acct["account_name"],
            "account_type": acct["account_type"],
            "gl_balance": round(gl_balance, 2),
            "sub_ledger_balance": round(sub_ledger_balance, 2),
            "difference": difference,
            "status": status,
            "preparer": preparer,
            "reviewer": reviewer if status == "Reconciled" else None,
            "due_date": f"{PERIOD}-20",
            "completed_date": f"{PERIOD}-{random.randint(15,20):02d}" if status == "Reconciled" else None,
            "notes": "Auto-reconciled via system match" if abs(difference) < 1.0 else f"Difference of ${abs(difference):,.2f} under investigation",
            "source_system": "Blackline",
        })

        # Supporting line items for each rec
        num_items = random.randint(3, 12)
        item_total = 0
        for i in range(num_items):
            is_last = (i == num_items - 1)
            if is_last:
                item_amt = round(gl_balance - item_total, 2)
            else:
                item_amt = round(random.uniform(gl_balance * 0.05, gl_balance * 0.25), 2)
                item_total += item_amt

            item_rows.append({
                "item_id": f"ITEM-{item_id:06d}",
                "recon_id": f"REC-{PERIOD.replace('-','')}-{acct['account_code']}",
                "account_code": acct["account_code"],
                "item_date": random_date(PERIOD_START, PERIOD_END).strftime("%Y-%m-%d"),
                "description": fake.bs().title(),
                "amount": item_amt,
                "category": random.choice(["Open Item", "Timing Difference", "In Transit", "Matched", "Unexplained"]),
                "aging_days": random.randint(0, 90),
                "reference": f"REF-{random.randint(100000,999999)}",
            })
            item_id += 1

    return pd.DataFrame(recon_rows), pd.DataFrame(item_rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ACCOUNTS PAYABLE — OPEN INVOICE LISTING  (Oracle AP simulation)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_ap_invoices(n=120):
    print(f"  Generating {n} AP invoices...")
    rows = []
    for i in range(n):
        vendor = random.choice(VENDORS)
        inv_date = random_date(PERIOD_START - timedelta(days=45), PERIOD_END)
        due_days = random.choice([30, 30, 30, 45, 60, 90])
        due_date = inv_date + timedelta(days=due_days)
        amount = round(random.uniform(500, 250000), 2)
        paid = random.random() > 0.35
        rows.append({
            "invoice_id": f"INV-{i+1:05d}",
            "vendor_id": vendor[0],
            "vendor_name": vendor[1],
            "vendor_category": vendor[2],
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "invoice_amount": amount,
            "paid_amount": amount if paid else 0.00,
            "open_amount": 0.00 if paid else amount,
            "payment_date": (inv_date + timedelta(days=random.randint(5, due_days))).strftime("%Y-%m-%d") if paid else None,
            "gl_account": random.choice(["6300","6700","6100","6000","6400","6600","6310"])[0],
            "cost_center": random.choice(COST_CENTERS)[0],
            "status": "Paid" if paid else ("Overdue" if due_date < PERIOD_END else "Open"),
            "po_number": f"PO-{random.randint(10000,99999)}" if random.random() > 0.3 else None,
            "period": PERIOD,
            "source_system": "Oracle Fusion AP",
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ACCOUNTS RECEIVABLE — AGING  (Oracle AR simulation)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_ar_aging(n=80):
    print(f"  Generating {n} AR records...")
    rows = []
    for i in range(n):
        customer = random.choice(CUSTOMERS)
        inv_date = random_date(PERIOD_START - timedelta(days=90), PERIOD_END)
        due_days = random.choice([30, 30, 45, 60])
        due_date = inv_date + timedelta(days=due_days)
        amount = round(random.uniform(10000, 1500000), 2)
        days_outstanding = (PERIOD_END - inv_date).days
        aging_bucket = (
            "Current" if days_outstanding <= 30 else
            "31-60"   if days_outstanding <= 60 else
            "61-90"   if days_outstanding <= 90 else
            "91-120"  if days_outstanding <= 120 else
            "120+"
        )
        rows.append({
            "ar_id": f"AR-{i+1:05d}",
            "customer_id": customer[0],
            "customer_name": customer[1],
            "customer_type": customer[2],
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "due_date": due_date.strftime("%Y-%m-%d"),
            "invoice_amount": amount,
            "open_balance": round(amount * random.uniform(0.0, 1.0), 2),
            "days_outstanding": days_outstanding,
            "aging_bucket": aging_bucket,
            "revenue_account": random.choice(["4000","4010","4020"]),
            "legal_entity": random.choice(LEGAL_ENTITIES)[0],
            "period": PERIOD,
            "source_system": "Oracle Fusion AR",
            "collection_status": random.choice(["Current","Watch","Collection","Write-off Candidate"]),
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ACCRUALS SCHEDULE
# ═══════════════════════════════════════════════════════════════════════════════

def generate_accruals():
    print("  Generating accruals schedule...")
    accruals = [
        ("ACC-001", "Payroll accrual - last 3 days Dec", "6000", "2020", 285_000, "Recurring", "SYSTEM"),
        ("ACC-002", "Bonus accrual Q4",                  "6000", "2010", 750_000, "Manual",    "mwilliams"),
        ("ACC-003", "Legal fees - Dec invoices pending",  "6310", "2010", 95_000,  "Manual",    "kpatel"),
        ("ACC-004", "Audit fees accrual",                 "6300", "2010", 125_000, "Manual",    "jsmith"),
        ("ACC-005", "Interest accrual - term loan",       "7000", "2010", 187_500, "System",    "SYSTEM"),
        ("ACC-006", "Property tax accrual",               "6100", "2010", 42_000,  "Recurring", "SYSTEM"),
        ("ACC-007", "Software maintenance accrual",       "6700", "2010", 68_000,  "Manual",    "achan"),
        ("ACC-008", "Warranty reserve increase",          "5000", "2010", 55_000,  "Manual",    "lrodriguez"),
        ("ACC-009", "Deferred revenue release - Gaming",  "2030", "4000", 220_000, "System",    "SYSTEM"),
        ("ACC-010", "Income tax accrual - Q4 estimate",   "7010", "2100", 890_000, "Manual",    "mwilliams"),
        ("ACC-011", "Depreciation - Dec",                 "6200", "1510", 162_000, "System",    "SYSTEM"),
        ("ACC-012", "Amortization - intangibles Dec",     "6210", "1600", 48_500,  "System",    "SYSTEM"),
        ("ACC-013", "Vacation accrual adjustment",        "6000", "2010", 31_000,  "Manual",    "jsmith"),
        ("ACC-014", "Marketing accrual - year-end push",  "6400", "2010", 180_000, "Manual",    "achan"),
    ]
    rows = []
    for a in accruals:
        rows.append({
            "accrual_id": a[0],
            "description": a[1],
            "debit_account": a[2],
            "credit_account": a[3],
            "amount": a[4],
            "accrual_type": a[5],
            "prepared_by": a[6],
            "period": PERIOD,
            "reversal_period": "2025-01",
            "status": random.choice(["Posted", "Posted", "Posted", "Pending Review", "Pending Approval"]),
            "supporting_doc": f"SUPP-{a[0]}.xlsx",
            "je_reference": je_number(random.randint(200, 300)),
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 7. VARIANCE ANALYSIS SEED DATA
# ═══════════════════════════════════════════════════════════════════════════════

def generate_variance_analysis():
    print("  Generating variance analysis data...")
    data = [
        # (account, budget, actual, prior_actual, explanation_hint)
        ("4000", 19_000_000, 18_420_000, 18_500_000, "Gaming revenue slightly below budget due to Q4 seasonal softness in slot placements"),
        ("4010", 6_500_000,  7_120_000,  6_200_000,  "Interactive exceeded budget driven by new sports betting module launch in November"),
        ("4020", 10_000_000, 9_650_000,  9_800_000,  "Lottery systems revenue in line; one state contract renewal delayed to Q1"),
        ("6000", 9_000_000,  9_580_000,  9_200_000,  "Salaries over budget due to 3 unplanned contractor-to-FTE conversions in Interactive"),
        ("6200", 1_500_000,  1_620_000,  1_440_000,  "Depreciation increase from $4.2M equipment placed in service in November"),
        ("6300", 2_000_000,  2_380_000,  2_100_000,  "Professional services over due to ERP upgrade consulting and year-end audit prep"),
        ("6400", 1_500_000,  1_720_000,  1_650_000,  "Marketing spend elevated for G2E trade show and holiday promotional campaigns"),
        ("6700", 1_100_000,  1_290_000,  1_120_000,  "IT costs over; cloud infrastructure scaling for interactive platform peak traffic"),
        ("7000", 950_000,    987_500,    980_000,    "Interest expense slightly above plan; rate adjustment on revolver in November"),
        ("7010", 2_200_000,  2_580_000,  2_400_000,  "Tax expense over; discrete item — settlement of prior year state tax audit"),
    ]
    rows = []
    for d in data:
        acct, budget, actual, prior, hint = d
        fav_unfav = "Favorable" if actual < budget and "Revenue" not in hint else ("Favorable" if actual > budget and "Revenue" in hint else "Unfavorable")
        rows.append({
            "account_code": acct,
            "period": PERIOD,
            "budget_amount": budget,
            "actual_amount": actual,
            "prior_period_actual": prior,
            "vs_budget_variance": actual - budget,
            "vs_budget_pct": round((actual - budget) / budget * 100, 2),
            "vs_prior_variance": actual - prior,
            "vs_prior_pct": round((actual - prior) / prior * 100, 2),
            "favorable_unfavorable": fav_unfav,
            "explanation_hint": hint,
            "requires_narrative": abs((actual - budget) / budget) > 0.05,
            "threshold_breached": abs((actual - budget) / budget) > 0.10,
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 8. ACCOUNTING POLICIES (RAG knowledge base documents)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_policy_docs():
    print("  Generating accounting policy documents...")
    policies = [
        {
            "doc_id": "POL-001",
            "title": "Journal Entry Policy and Procedures",
            "category": "Financial Close",
            "content": """
Journal Entry Policy — Light & Wonder Inc.
Version 3.2 | Effective: January 1, 2024 | Owner: Chief Accounting Officer

1. PURPOSE
This policy establishes standards for the preparation, review, approval, and documentation of all journal entries to ensure accuracy, completeness, and SOX compliance.

2. SCOPE
Applies to all manual and system-generated journal entries across all legal entities and cost centers globally.

3. JOURNAL ENTRY CLASSIFICATION
- Standard/Recurring: System-generated entries (depreciation, amortization, payroll). Auto-approved if within tolerance.
- Manual: Prepared by accounting staff. Requires preparer + independent approver.
- Accrual: Month-end estimates. Must have supporting calculation and management review.
- Top-side/Consolidation: Prepared at HFM level. Requires Senior Director approval.
- Correcting: Must reference original JE number and include error description.
- Intercompany: Must be agreed between entities before posting. Zero tolerance for imbalances.

4. APPROVAL REQUIREMENTS
- Under $10,000: Preparer + Supervisor approval
- $10,000 – $100,000: Preparer + Manager approval
- $100,000 – $500,000: Preparer + Senior Manager + Controller review
- Over $500,000: Preparer + Controller + CAO approval required
- SELF-APPROVAL IS PROHIBITED at all dollar thresholds.

5. TIMING REQUIREMENTS
- All JEs must be posted within 2 business days of the transaction date.
- Month-end accruals must be posted by the 3rd business day after period end.
- Weekend/holiday postings require prior approval from Controller.
- Prior period adjustments require CFO approval and SEC disclosure assessment.

6. SOX CONTROLS
- All manual JEs over $25,000 are subject to monthly SOX testing by Internal Audit.
- Round-number manual entries over $50,000 require additional documentation.
- Any entry with the same preparer and approver (self-approval) is a SOX deficiency.
- Entries posted to unusual account combinations must include a business purpose narrative.

7. DOCUMENTATION REQUIREMENTS
- Supporting documentation must be attached in Blackline within 24 hours of posting.
- Recurring entries must reference the approved recurring template number.
- Descriptions must be clear and reference source transactions or contracts.
"""
        },
        {
            "doc_id": "POL-002",
            "title": "Account Reconciliation Policy",
            "category": "Financial Close",
            "content": """
Account Reconciliation Policy — Light & Wonder Inc.
Version 2.8 | Effective: January 1, 2024 | Owner: VP Controller

1. PURPOSE
Establish requirements for account reconciliations to ensure GL balances are accurate, supported, and compliant with SOX controls.

2. RECONCILIATION FREQUENCY
- Daily: Cash and bank accounts (all legal entities)
- Weekly: AR trade balances over $1M
- Monthly: All balance sheet accounts
- Quarterly: Low-activity accounts (defined as <5 transactions/quarter)

3. RECONCILIATION DUE DATES (Monthly Close)
- Tier 1 (High Risk): Day 5 after period end — Cash, AR, AP, Payroll liabilities
- Tier 2 (Medium Risk): Day 8 after period end — Prepaids, accrued liabilities, deferred revenue
- Tier 3 (Low Risk): Day 12 after period end — Fixed assets, intangibles, equity accounts

4. EXCEPTION THRESHOLDS
- Immaterial: Differences < $500. Document and clear within 30 days.
- Material: Differences $500 – $50,000. Escalate to Controller. Clear within 15 days.
- Significant: Differences > $50,000. Immediate escalation to CAO. Same-day resolution plan.

5. SOX REQUIREMENTS
- All Tier 1 reconciliations are key SOX controls — failures are reportable deficiencies.
- Evidence of independent review must be documented in Blackline.
- No self-review permitted (same preparer and reviewer).

6. AGING OF RECONCILING ITEMS
- Items 0–30 days: Monitor
- Items 31–60 days: Escalate to Manager
- Items 61–90 days: Escalate to Controller with resolution plan
- Items >90 days: Escalate to CAO; assess financial statement impact
"""
        },
        {
            "doc_id": "POL-003",
            "title": "Revenue Recognition Policy (ASC 606)",
            "category": "Revenue",
            "content": """
Revenue Recognition Policy — Light & Wonder Inc.
Version 4.1 | Effective: January 1, 2024 | Owner: Chief Accounting Officer

1. OVERVIEW
Revenue is recognized in accordance with ASC 606 — Revenue from Contracts with Customers — when control of promised goods or services transfers to the customer in an amount reflecting the transaction price allocated to each performance obligation.

2. PERFORMANCE OBLIGATIONS BY SEGMENT

Gaming Systems:
- Hardware revenue: Recognized at point of delivery and customer acceptance.
- Software licenses (perpetual): Recognized at delivery/go-live.
- Software licenses (subscription/SaaS): Recognized ratably over contract term.
- Installation services: Recognized when installation is complete and accepted.
- Content/game themes: Recognized as content is made available to operator.

Interactive (iGaming / Sports Betting):
- Platform fees: Recognized monthly based on GGR or minimum guarantee, whichever is higher.
- Setup/implementation fees: Deferred and recognized over the contract term.
- Maintenance and support: Recognized ratably over service period.

Lottery Systems:
- Long-term contracts: Recognized over contract period based on tickets sold or monthly service fees.
- Upfront system fees: Typically deferred and amortized over contract life.

3. DEFERRED REVENUE
- Payments received before performance obligations are met are deferred in Account 2030.
- Monthly reconciliation of deferred revenue to contract schedules is required.
- Releases to revenue require Controller approval and supporting contract documentation.

4. VARIABLE CONSIDERATION
- Revenue including variable components (volume bonuses, penalties) must be constrained to amounts not likely to result in significant reversal.
- Quarterly reassessment of variable consideration estimates required.
"""
        },
        {
            "doc_id": "POL-004",
            "title": "Accruals and Estimates Policy",
            "category": "Financial Close",
            "content": """
Accruals and Estimates Policy — Light & Wonder Inc.
Version 2.4 | Effective: January 1, 2024

1. PURPOSE
Define standards for accruing expenses and liabilities to ensure financial statements reflect economic reality on an accrual basis.

2. ACCRUAL TYPES
- Standard recurring accruals: System-generated based on approved templates (payroll, depreciation, amortization).
- Estimate-based accruals: Require calculation support (bonuses, warranty reserves, legal contingencies).
- Cutoff accruals: Goods received / services performed but not yet invoiced at period end.

3. DOCUMENTATION REQUIREMENTS
- All manual accruals require a supporting Excel or PDF calculation uploaded to Blackline.
- Accruals over $100,000 require comparison to prior period and explanation of significant changes.
- Bonus accruals must reference approved compensation plan and HR headcount data.

4. ACCRUAL REVERSAL
- All accruals must have a designated reversal date (typically first day of following period).
- Recurring accruals are auto-reversed by Oracle on the first day of the following month.
- Failure to reverse in the designated period requires Controller approval and documentation.

5. MATERIALITY THRESHOLDS
- Accruals under $5,000 may be expensed in full if the service period straddles the period end.
- Accruals over $500,000 require CAO approval and CFO notification.
"""
        },
        {
            "doc_id": "POL-005",
            "title": "Close Calendar and Checklist — December 2024",
            "category": "Financial Close",
            "content": """
Monthly Close Calendar — December 2024
Prepared by: Close & Control Team | Due: December 31, 2024

CLOSE CHECKLIST:

Pre-Close (Dec 28–30):
[ ] Confirm all sub-ledgers (AP, AR, Payroll, Fixed Assets) are closed and tied to GL
[ ] Post all system-generated recurring journal entries
[ ] Confirm intercompany eliminations are balanced
[ ] Preliminary revenue recognition review with FP&A

Close Day (Dec 31):
[ ] Post all manual accruals (Tier 1 by 12pm, Tier 2 by 5pm)
[ ] Final revenue cut-off review — confirm no entries dated Jan 1+
[ ] Bank reconciliation — all cash accounts
[ ] Run Oracle GL period-end validation (no out-of-balance conditions)
[ ] HFM data load and preliminary consolidation

Post-Close (Jan 2–8):
[ ] Complete all Tier 1 reconciliations by Jan 5
[ ] Variance analysis — actuals vs. budget and prior period
[ ] SEC/FP&A preliminary P&L review
[ ] External audit PBC list — prepare supporting schedules
[ ] Complete all Tier 2/3 reconciliations by Jan 8
[ ] Management representation letter review

KEY CONTACTS:
- Controller: M. Williams (ext. 4422)
- Shared Services Close Lead: K. Patel (ext. 3315)
- FP&A: L. Rodriguez (ext. 5501)
- IT/Systems: A. Chan (ext. 6614)
"""
        },
    ]
    return policies


# ═══════════════════════════════════════════════════════════════════════════════
# 9. PERSIST EVERYTHING TO SQLITE + CSV/JSON EXPORTS
# ═══════════════════════════════════════════════════════════════════════════════

def save_all(gl_df, tb_df, recon_df, recon_items_df, ap_df, ar_df, accruals_df, variance_df, policies):
    print("\n  Saving to SQLite database...")
    conn = sqlite3.connect(DB_PATH)

    # Write dataframes
    gl_df.to_sql("gl_transactions",    conn, if_exists="replace", index=False)
    tb_df.to_sql("trial_balance",      conn, if_exists="replace", index=False)
    recon_df.to_sql("reconciliations", conn, if_exists="replace", index=False)
    recon_items_df.to_sql("recon_items",conn,if_exists="replace", index=False)
    ap_df.to_sql("ap_invoices",        conn, if_exists="replace", index=False)
    ar_df.to_sql("ar_aging",           conn, if_exists="replace", index=False)
    accruals_df.to_sql("accruals",     conn, if_exists="replace", index=False)
    variance_df.to_sql("variance_analysis", conn, if_exists="replace", index=False)

    # Chart of accounts
    coa_df = pd.DataFrame(CHART_OF_ACCOUNTS, columns=["account_code","account_name","account_type","normal_balance","parent_group"])
    coa_df.to_sql("chart_of_accounts", conn, if_exists="replace", index=False)

    # Policies as text table (for RAG ingestion)
    pol_df = pd.DataFrame([{"doc_id": p["doc_id"], "title": p["title"], "category": p["category"], "content": p["content"]} for p in policies])
    pol_df.to_sql("policy_documents", conn, if_exists="replace", index=False)

    conn.close()

    print("  Exporting CSV files (Oracle/Blackline simulation)...")
    gl_df.to_csv(f"{OUTPUT_DIR}/oracle_gl_export_{PERIOD}.csv", index=False)
    tb_df.to_csv(f"{OUTPUT_DIR}/trial_balance_{PERIOD}.csv", index=False)
    recon_df.to_csv(f"{OUTPUT_DIR}/blackline_recons_{PERIOD}.csv", index=False)
    ap_df.to_csv(f"{OUTPUT_DIR}/oracle_ap_invoices_{PERIOD}.csv", index=False)
    ar_df.to_csv(f"{OUTPUT_DIR}/oracle_ar_aging_{PERIOD}.csv", index=False)
    accruals_df.to_csv(f"{OUTPUT_DIR}/accruals_schedule_{PERIOD}.csv", index=False)
    variance_df.to_csv(f"{OUTPUT_DIR}/variance_analysis_{PERIOD}.csv", index=False)

    print("  Saving policy docs as JSON (for RAG chunking)...")
    with open(f"{OUTPUT_DIR}/accounting_policies.json", "w") as f:
        json.dump(policies, f, indent=2)

    # REST API simulation fixtures
    api_fixture = {
        "oracle_gl": {"endpoint": "/api/oracle/gl", "period": PERIOD, "record_count": len(gl_df)},
        "blackline":  {"endpoint": "/api/blackline/recons", "period": PERIOD, "record_count": len(recon_df)},
        "oracle_ap":  {"endpoint": "/api/oracle/ap", "period": PERIOD, "record_count": len(ap_df)},
        "oracle_ar":  {"endpoint": "/api/oracle/ar", "period": PERIOD, "record_count": len(ar_df)},
    }
    with open(f"{OUTPUT_DIR}/api_fixtures.json", "w") as f:
        json.dump(api_fixture, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  FinClose AI — Mock Data Generator")
    print(f"  Period: {PERIOD}")
    print("=" * 60)

    print("\n[1/7] GL Transactions (Oracle Fusion GL export)...")
    gl_df = generate_gl_transactions(n=600)

    print("[2/7] Trial Balance...")
    tb_df = generate_trial_balance(gl_df)

    print("[3/7] Account Reconciliations (Blackline)...")
    recon_df, recon_items_df = generate_reconciliations(tb_df)

    print("[4/7] AP Invoices (Oracle Fusion AP)...")
    ap_df = generate_ap_invoices(n=120)

    print("[5/7] AR Aging (Oracle Fusion AR)...")
    ar_df = generate_ar_aging(n=80)

    print("[6/7] Accruals Schedule...")
    accruals_df = generate_accruals()

    print("[6b/7] Variance Analysis...")
    variance_df = generate_variance_analysis()

    print("[7/7] Accounting Policy Documents (RAG knowledge base)...")
    policies = generate_policy_docs()

    print("\nSaving all datasets...")
    save_all(gl_df, tb_df, recon_df, recon_items_df, ap_df, ar_df, accruals_df, variance_df, policies)

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  DATA GENERATION COMPLETE")
    print("=" * 60)
    print(f"  GL transactions  : {len(gl_df):>6,} rows")
    print(f"  Trial balance    : {len(tb_df):>6,} accounts")
    print(f"  Reconciliations  : {len(recon_df):>6,} recs  |  {len(recon_items_df):,} items")
    print(f"  AP invoices      : {len(ap_df):>6,} invoices")
    print(f"  AR aging         : {len(ar_df):>6,} records")
    print(f"  Accruals         : {len(accruals_df):>6,} entries")
    print(f"  Variance rows    : {len(variance_df):>6,}")
    print(f"  Policy docs      : {len(policies):>6,} documents")

    anomalies = gl_df[gl_df["is_anomaly"] == True]["je_id"].nunique()
    print(f"\n  Anomalies injected: {anomalies} JEs flagged for agent detection")

    print(f"\n  Output dir : {OUTPUT_DIR}")
    print(f"  SQLite DB  : {DB_PATH}")
    print("=" * 60)

    return gl_df, tb_df, recon_df, ap_df, ar_df, accruals_df, variance_df


if __name__ == "__main__":
    main()
