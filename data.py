"""
data.py — shared data, payment terms, and calculation logic.
All payment rules live here. Edit this file to change vendor terms.
"""
import math
import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────
# PAYMENT TERMS  ←  Edit these to change vendor rules
# ─────────────────────────────────────────────────────────────
INVENTORY_TERMS = {
    "Triple A Apparel LTD": 5,
    "Konc": 15,
    "Lever Style Limited": 15,
    "Athletic Apparel Group": 30,
    "Primotex Textiles International Limited": 30,
    "American Phil Textiles Limited": 60,
    "Delta Galil Industries Ltd.": 60,
    "The S Group": 60,
}

PRIORITY_TERMS = {
    "Kristina Boiano": 0,
    "R&A Engineering LLC": 5,
    "Alexander Adamov (Fit Modeling Services)": 15,
    "Barrel LLC": 15,
    "SBH Plus, Inc": 15,
    "ERY Retail Podium LLC": 25,
    "Fin Technologies dba Alkami Technology, Inc": 25,
    "Madeleine Lachesnez": 30,
    "Oracle America Inc.": 30,
    "STUDIO TAVISH TIMOTHY LLC": 30,
    "Nick Pichaiwongse": 45,
    "Google LLC": "google",
    "XB Fulfillment": "xb",   # ← Remove after 4/5/2026
}

XB_WEEK = date(2026, 3, 30)   # XB Fulfillment one-time rule
RAMP_CC_AMOUNT = 150_000
JUSTWORKS_TAXES = 32_624
JUSTWORKS_PAYROLL = 184_962
REVENUE_PAYOUT_PCT = 0.92
SHIPPING_PCT = 0.06
OTHER_WEEKLY = 20_000

# ─────────────────────────────────────────────────────────────
# DATE UTILITIES
# ─────────────────────────────────────────────────────────────
def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())

def adj_back(d: date) -> date:
    """Saturday/Sunday → Friday."""
    if d.weekday() == 5: return d - timedelta(1)
    if d.weekday() == 6: return d - timedelta(2)
    return d

def adj_fwd(d: date) -> date:
    """Saturday/Sunday → Monday (used for Ramp CC)."""
    if d.weekday() == 5: return d + timedelta(2)
    if d.weekday() == 6: return d + timedelta(1)
    return d

def week_idx(d: date, week_starts: list) -> int:
    for i, ws in enumerate(week_starts):
        if ws <= d <= ws + timedelta(6):
            return i
    return -1 if d < week_starts[0] else None

def google_pay_date(due: date) -> date:
    first = date(due.year, due.month, 1)
    fm = first if first.weekday() == 0 else first + timedelta((7 - first.weekday()) % 7)
    wk4 = fm + timedelta(21)
    d15 = date(due.year, due.month, 15)
    m15 = d15 - timedelta(d15.weekday())
    if due >= wk4:
        nm = (due.month % 12) + 1
        ny = due.year + (1 if due.month == 12 else 0)
        d15n = date(ny, nm, 15)
        return d15n - timedelta(d15n.weekday())
    return m15

def parse_d(s) -> date:
    if not s: return None
    try: return date.fromisoformat(str(s)[:10])
    except: return None

def parse_excel_date(val):
    if val is None or (isinstance(val, float) and math.isnan(val)): return None
    if isinstance(val, (int, float)): return date(1899, 12, 30) + timedelta(days=int(val))
    if hasattr(val, "date"): return val.date()
    return None

# ─────────────────────────────────────────────────────────────
# RAMP PAY DATE
# ─────────────────────────────────────────────────────────────
def ramp_pay_date(payee: str, status: str, due: date, week_starts: list) -> date:
    s = (status or "").upper().replace(" ", "_")
    if s == "INITIATED": return week_starts[0]
    if payee in PRIORITY_TERMS:
        t = PRIORITY_TERMS[payee]
        if t == "xb": return XB_WEEK
        if t == "google":
            if s == "READY_FOR_PAYMENT": return week_starts[0]
            return google_pay_date(due) if due else week_starts[0]
        pay = (due + timedelta(t)) if due else week_starts[0]
        return adj_back(pay)
    if s == "SCHEDULED":
        return adj_back(due) if due else week_starts[0]
    pay = (due + timedelta(60)) if due else week_starts[0]
    return adj_back(pay)

# ─────────────────────────────────────────────────────────────
# RAMP API
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def fetch_ramp_bills() -> list:
    """Pull unpaid bills from Ramp API. Cached for 1 hour."""
    client_id = os.environ.get("RAMP_CLIENT_ID", "")
    client_secret = os.environ.get("RAMP_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        st.warning("Ramp credentials not configured — using demo data.")
        return []
    try:
        token_resp = requests.post(
            "https://api.ramp.com/developer/v1/token",
            data={"grant_type": "client_credentials",
                  "client_id": client_id,
                  "client_secret": client_secret,
                  "scope": "bills:read"},
            timeout=30,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        params = {"payment_status": ["INITIATED", "SCHEDULED", "UNSCHEDULED",
                                     "READY_FOR_PAYMENT", "PENDING"],
                  "from_date": "2024-01-01", "page_size": 100}
        bills, next_page = [], None
        while True:
            if next_page: params["page_cursor"] = next_page
            r = requests.get("https://api.ramp.com/developer/v1/bills",
                             headers=headers, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            bills.extend(data.get("data", []))
            next_page = data.get("page", {}).get("next")
            if not next_page: break
        return bills
    except Exception as e:
        st.error(f"Ramp API error: {e}")
        return []

def parse_ramp_bill(b: dict) -> dict:
    cd = b.get("canonical_dates", {}) or {}
    return {
        "id":         b.get("id", ""),
        "payee":      (b.get("vendor", {}) or {}).get("name", "") or b.get("payee_name", ""),
        "status":     b.get("payment_status", "UNSCHEDULED"),
        "amount":     float(b.get("amount", 0)),
        "due_date":   cd.get("bill_due_at"),
        "issued_at":  cd.get("bill_issued_at"),
        "memo":       b.get("memo", ""),
    }

# ─────────────────────────────────────────────────────────────
# SUPABASE OVERRIDES
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_overrides() -> dict:
    """Returns {bill_id: override_date} from Supabase."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return {}
    try:
        resp = requests.get(
            f"{url}/rest/v1/bill_payment_overrides",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "bill_id,override_date"},
            timeout=15,
        )
        resp.raise_for_status()
        return {r["bill_id"]: parse_d(r["override_date"])
                for r in resp.json() if r.get("override_date")}
    except Exception as e:
        st.warning(f"Could not load overrides: {e}")
        return {}

def save_override(bill_id: str, vendor: str, source: str, override_date: date, note: str = ""):
    """Upsert a single override to Supabase."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        st.error("Supabase not configured.")
        return False
    try:
        resp = requests.post(
            f"{url}/rest/v1/bill_payment_overrides",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "resolution=merge-duplicates"},
            json=[{"bill_id": bill_id, "vendor": vendor, "source": source,
                   "override_date": str(override_date), "note": note}],
            timeout=15,
        )
        resp.raise_for_status()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Could not save override: {e}")
        return False

def delete_override(bill_id: str):
    """Remove an override from Supabase."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return
    try:
        requests.delete(
            f"{url}/rest/v1/bill_payment_overrides",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"bill_id": f"eq.{bill_id}"},
            timeout=15,
        )
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Could not delete override: {e}")

# ─────────────────────────────────────────────────────────────
# FORMATTING
# ─────────────────────────────────────────────────────────────
def fmt(n) -> str:
    if not n: return "—"
    return f"${n:,.0f}"

def fmt_date(d) -> str:
    if not d: return "—"
    if isinstance(d, str): d = parse_d(d)
    return d.strftime("%-m/%-d") if d else "—"

def fmt_date_full(d) -> str:
    if not d: return "—"
    if isinstance(d, str): d = parse_d(d)
    return d.strftime("%b %d, %Y") if d else "—"
