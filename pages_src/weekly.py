"""Weekly Bill Pay — reads current week bills from Supabase."""
import os
from datetime import date, timedelta

import requests
import streamlit as st

from data import PRIORITY_TERMS, INVENTORY_TERMS, adj_back, fmt, fmt_date, monday_of, week_idx

TODAY      = date(2026, 3, 31)
WEEK_START = monday_of(TODAY)
WEEK_END   = WEEK_START + timedelta(6)
REV_PAYOUT = 700_181
REV_START  = WEEK_START - timedelta(3)
REV_END    = WEEK_START + timedelta(3)


@st.cache_data(ttl=300)
def fetch_bills():
    url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return []
    try:
        resp = requests.get(
            f"{url}/rest/v1/bills",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "*", "limit": "1000"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Supabase error: {e}")
        return []


def parse_d(s):
    if not s: return None
    try: return date.fromisoformat(str(s)[:10])
    except: return None


def days_out_str(due: date) -> str:
    if not due: return "—"
    days = (TODAY - due).days
    if days > 0:   return f"+{days}d overdue"
    elif days == 0: return "Due today"
    else:           return f"In {-days}d"


def show():
    st.markdown(f"""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>Weekly Bill Pay</h1>
      </div>
      <div class="mw-badge">{WEEK_START.strftime('%-m/%-d')} — {WEEK_END.strftime('%-m/%-d/%Y')}</div>
    </div>
    """, unsafe_allow_html=True)

    week_starts = [WEEK_START + timedelta(weeks=i) for i in range(6)]

    with st.spinner("Loading bills from Supabase..."):
        raw_bills = fetch_bills()

    if not raw_bills:
        st.warning("No bills found in Supabase. Run 'weekly AP update' in Claude to populate.")
        return

    # Categorize bills due this week
    categories = {
        "Inventory":      [],
        "Ramp Priority":  [],
        "Ramp Standard":  [],
    }

    for b in raw_bills:
        vendor = b.get("vendor", "")
        amount = float(b.get("amount") or 0)
        source = b.get("source", "")
        due    = parse_d(b.get("due_date"))
        inv_date = parse_d(b.get("invoice_date"))
        inv_id = b.get("invoice_id", "")
        memo   = b.get("memo") or b.get("description") or ""
        paid_status = (b.get("paid_status") or "").lower()

        if amount <= 0 or not due:
            continue

        # Calculate expected payment date
        if source == "NetSuite":
            days_extra = INVENTORY_TERMS.get(vendor, 0)
            pay_date = adj_back(due + timedelta(days=days_extra))
            cat = "Inventory"
        elif source == "Ramp":
            if paid_status in ("paid", "initiated"):
                continue
            if vendor in PRIORITY_TERMS:
                days_extra = PRIORITY_TERMS.get(vendor, 60)
                if days_extra == "due":
                    pay_date = adj_back(due)
                elif isinstance(days_extra, int):
                    pay_date = adj_back(due + timedelta(days=days_extra))
                else:
                    pay_date = adj_back(due + timedelta(days=60))
                cat = "Ramp Priority"
            else:
                pay_date = adj_back(due + timedelta(days=60))
                cat = "Ramp Standard"
        else:
            continue

        # Only include if payment falls in current week
        if WEEK_START <= pay_date <= WEEK_END:
            categories[cat].append({
                "vendor":    vendor,
                "inv":       inv_id,
                "inv_date":  fmt_date(inv_date) if inv_date else "—",
                "due_date":  due,
                "days_out":  days_out_str(due),
                "memo":      memo[:55],
                "amount":    amount,
                "pay_date":  pay_date,
            })

    # Sort each category by amount desc
    for cat in categories:
        categories[cat].sort(key=lambda x: -x["amount"])

    grand_total = 0
    import pandas as pd

    for cat_name, items in categories.items():
        if not items:
            continue

        st.markdown(f"#### {cat_name}")

        rows = []
        for item in items:
            rows.append({
                "Vendor":       item["vendor"],
                "Invoice #":    item["inv"],
                "Invoice Date": item["inv_date"],
                "Due Date":     fmt_date(item["due_date"]),
                "Days O/S":     item["days_out"],
                "Description":  item["memo"],
                "Amount":       fmt(item["amount"]),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 400))

        subtotal = sum(i["amount"] for i in items)
        grand_total += subtotal

        col_l, col_r = st.columns([4, 1])
        col_l.markdown(f"*Subtotal — {cat_name}*")
        col_r.markdown(f"**{fmt(subtotal)}**")
        st.markdown("---")

    if grand_total == 0:
        st.info("No bills with payment dates falling in the current week.")
        return

    st.markdown(
        f"""<div style="background:#0D1B2A;padding:16px 20px;border-radius:8px;
        display:flex;justify-content:space-between;align-items:center;">
          <span style="font-family:serif;font-size:20px;color:#B8935A;font-weight:600">GRAND TOTAL</span>
          <span style="font-family:monospace;font-size:22px;color:#B8935A;font-weight:700">{fmt(grand_total)}</span>
        </div>""", unsafe_allow_html=True
    )

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"""<div style="background:rgba(42,157,143,0.08);border:1px solid rgba(42,157,143,0.25);
        border-radius:8px;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-size:10px;color:#2a9d8f;text-transform:uppercase;letter-spacing:0.1em;font-weight:600">Estimated Revenue Payout</div>
            <div style="font-size:11px;color:#9e9990;font-family:monospace;margin-top:3px">92% discounted rev · {REV_START.strftime('%-m/%-d')}–{REV_END.strftime('%-m/%-d')}</div>
          </div>
          <div style="font-family:monospace;font-size:20px;color:#2a9d8f;font-weight:700">{fmt(REV_PAYOUT)}</div>
        </div>""", unsafe_allow_html=True
    )

    st.markdown("---")
    if st.button("🔄 Refresh from Supabase"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"{len(raw_bills)} total bills in Supabase · showing this week only")
