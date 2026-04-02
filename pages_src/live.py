"""Weekly Bill Pay Live — real-time status view pulling from Supabase."""
import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

from data import (PRIORITY_TERMS, INVENTORY_TERMS, adj_back,
                  fmt, fmt_date, monday_of, google_pay_date, ramp_pay_date,
                  XB_WEEK)

def get_today():
    return date.today()

def sat_fri_window(d: date):
    """Return (Saturday, Friday) of the Sat–Fri week containing d."""
    days_since_sat = (d.weekday() + 2) % 7
    sat = d - timedelta(days=days_since_sat)
    return sat, sat + timedelta(6)

def get_week_starts(anchor: date, n=6):
    mon = monday_of(anchor)
    return [mon + timedelta(weeks=i) for i in range(n)]

STATUS_LABELS = {
    "initiated":         "🟢 Initiated",
    "paid":              "✅ Paid",
    "scheduled":         "🔵 Scheduled",
    "unscheduled":       "⚪ Unscheduled",
    "ready_for_payment": "🟡 Ready for Payment",
    "rejected":          "🔴 Rejected",
    "pending":           "🟡 Pending",
    "waiting_for_match": "🟠 Waiting for Match",
}

DONE_STATUSES = {"initiated", "paid"}


@st.cache_data(ttl=300)
def fetch_all_bills():
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
        st.warning(f"Could not load bills from Supabase: {e}")
        return []


def parse_d(s):
    if not s: return None
    try: return date.fromisoformat(str(s)[:10])
    except: return None


def get_payment_date(bill: dict, week_starts: list):
    vendor = bill.get("vendor", "")
    source = bill.get("source", "")
    status = (bill.get("paid_status") or "").strip()
    due    = parse_d(bill.get("due_date"))
    if not due:
        return None
    if source == "NetSuite":
        days = INVENTORY_TERMS.get(vendor, 0)
        return adj_back(due + timedelta(days=days))
    elif source == "Ramp":
        return ramp_pay_date(vendor, status, due, week_starts)
    return None


def days_os(pay_date: date, today: date) -> str:
    if not pay_date:
        return "—"
    delta = (today - pay_date).days
    return str(delta)


def show():
    today       = get_today()
    sat, fri    = sat_fri_window(today)
    week_starts = get_week_starts(today)
    cur_mon     = week_starts[0]
    cur_sun     = cur_mon + timedelta(6)

    st.markdown(f"""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON — LIVE</div>
        <h1>⚡ Weekly Bill Pay — Live</h1>
      </div>
      <div class="mw-badge" style="background:rgba(46,139,87,0.2);color:#2e8b57">
        As of {today.strftime('%-m/%-d/%Y')}
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        f"Paid & Initiated window: {sat.strftime('%-m/%-d')}–{fri.strftime('%-m/%-d')}  ·  "
        f"AP forecast week: {cur_mon.strftime('%-m/%-d')}–{cur_sun.strftime('%-m/%-d')}"
    )

    with st.spinner("Loading bills from Supabase..."):
        raw_bills = fetch_all_bills()

    if not raw_bills:
        st.warning("No bills found in Supabase. Run 'weekly AP update' in Claude to populate.")
        return

    done      = []
    this_week = []
    overdue   = []

    for b in raw_bills:
        amount = float(b.get("amount") or 0)
        if amount <= 0:
            continue

        vendor      = b.get("vendor", "")
        source      = b.get("source", "")
        paid_status = (b.get("paid_status") or "Unscheduled").lower().replace(" ", "_")
        due         = parse_d(b.get("due_date"))
        as_of       = parse_d(b.get("as_of_date"))
        inv_id      = b.get("invoice_id", "")
        memo        = (b.get("memo") or b.get("description") or "")[:60]
        pay_date    = get_payment_date(b, week_starts)

        row = {
            "vendor":       vendor,
            "inv":          inv_id,
            "memo":         memo,
            "status":       paid_status,
            "status_label": STATUS_LABELS.get(paid_status, paid_status.replace("_", " ").title()),
            "due":          due,
            "as_of":        as_of,
            "pay_date":     pay_date,
            "amount":       amount,
            "source":       source,
        }

        if paid_status in DONE_STATUSES:
            if as_of and sat <= as_of <= fri:
                done.append(row)
        else:
            if pay_date is None:
                continue
            if pay_date < cur_mon:
                overdue.append(row)
            elif cur_mon <= pay_date <= cur_sun:
                this_week.append(row)

    # Sort: Done → Initiated first then Paid, both by as_of date asc
    done.sort(key=lambda x: (0 if x["status"] == "initiated" else 1, x["as_of"] or date.max))
    this_week.sort(key=lambda x: -x["amount"])
    overdue.sort(key=lambda x: x["pay_date"] or date.max)

    total_done    = sum(b["amount"] for b in done)
    total_this_wk = sum(b["amount"] for b in this_week)
    total_overdue = sum(b["amount"] for b in overdue)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("✅ Paid & Initiated",  fmt(total_done),    f"{len(done)} bills")
    c2.metric("📋 This Week Pending", fmt(total_this_wk), f"{len(this_week)} bills")
    c3.metric("⚠️ Overdue Pending",   fmt(total_overdue), f"{len(overdue)} bills")
    c4.metric("🗓 AP Week", f"{cur_mon.strftime('%-m/%-d')}–{cur_sun.strftime('%-m/%-d')}")

    st.markdown("---")
    col_s, col_src = st.columns([4, 2])
    search  = col_s.text_input("🔍 Search vendors", placeholder="Filter by vendor name...")
    src_flt = col_src.selectbox("Source", ["All", "Ramp", "NetSuite"])

    def apply_filters(bills):
        if search:
            bills = [b for b in bills if search.lower() in b["vendor"].lower()]
        if src_flt != "All":
            bills = [b for b in bills if b["source"] == src_flt]
        return bills

    f_done    = apply_filters(done)
    f_this_wk = apply_filters(this_week)
    f_overdue = apply_filters(overdue)

    # ── Section 1: Paid & Initiated ──────────────────────────────────────
    st.markdown(
        f"### ✅ Paid & Initiated "
        f"<span style='font-size:14px;color:#9e9990;font-weight:normal'>"
        f"({len(f_done)} bills · {fmt(sum(b['amount'] for b in f_done))}) "
        f"· {sat.strftime('%-m/%-d')}–{fri.strftime('%-m/%-d')}"
        f"</span>", unsafe_allow_html=True)
    st.caption("Initiated first (then Paid), sorted by date updated in Ramp.")

    if f_done:
        rows = [{"Vendor": b["vendor"], "Invoice #": b["inv"],
                 "Status": b["status_label"],
                 "Due Date": fmt_date(b["due"]) if b["due"] else "—",
                 "As Of": fmt_date(b["as_of"]) if b["as_of"] else "—",
                 "Amount": fmt(b["amount"])} for b in f_done]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 450))
        cl, cr = st.columns([4, 1])
        cl.markdown("*Subtotal — Paid & Initiated*")
        cr.markdown(f"**{fmt(sum(b['amount'] for b in f_done))}**")
    else:
        st.info(f"No Paid or Initiated bills in the {sat.strftime('%-m/%-d')}–{fri.strftime('%-m/%-d')} window.")

    st.markdown("---")

    # ── Section 2: This Week Pending ─────────────────────────────────────
    st.markdown(
        f"### ⏳ Still Pending — This Week "
        f"<span style='font-size:14px;color:#9e9990;font-weight:normal'>"
        f"({len(f_this_wk)} bills · {fmt(sum(b['amount'] for b in f_this_wk))})"
        f"</span>", unsafe_allow_html=True)
    st.caption(f"Bills the AP forecast schedules for {cur_mon.strftime('%-m/%-d')}–{cur_sun.strftime('%-m/%-d')} that are not yet Initiated or Paid.")

    if f_this_wk:
        rows = [{"Vendor": b["vendor"], "Invoice #": b["inv"],
                 "Status": b["status_label"],
                 "Due Date": fmt_date(b["due"]) if b["due"] else "—",
                 "Sched. Pay": fmt_date(b["pay_date"]) if b["pay_date"] else "—",
                 "Days O/S": days_os(b["pay_date"], today),
                 "Amount": fmt(b["amount"])} for b in f_this_wk]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 500))
        cl, cr = st.columns([4, 1])
        cl.markdown("*Subtotal — This Week Pending*")
        cr.markdown(f"**{fmt(sum(b['amount'] for b in f_this_wk))}**")
    else:
        st.success("All this week's scheduled bills are paid or initiated! 🎉")

    st.markdown("---")

    # ── Section 3: Overdue Pending ───────────────────────────────────────
    st.markdown(
        f"### ⚠️ Still Pending — Overdue "
        f"<span style='font-size:14px;color:#9e9990;font-weight:normal'>"
        f"({len(f_overdue)} bills · {fmt(sum(b['amount'] for b in f_overdue))})"
        f"</span>", unsafe_allow_html=True)
    st.caption("Bills whose AP forecast payment date was before this Monday. Sorted oldest first.")

    if f_overdue:
        rows = [{"Vendor": b["vendor"], "Invoice #": b["inv"],
                 "Status": b["status_label"],
                 "Due Date": fmt_date(b["due"]) if b["due"] else "—",
                 "Sched. Pay": fmt_date(b["pay_date"]) if b["pay_date"] else "—",
                 "Days O/S": days_os(b["pay_date"], today),
                 "Amount": fmt(b["amount"])} for b in f_overdue]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 600))
        cl, cr = st.columns([4, 1])
        cl.markdown("*Subtotal — Overdue Pending*")
        cr.markdown(f"**{fmt(sum(b['amount'] for b in f_overdue))}**")
    else:
        st.success("No overdue unpaid bills! 🎉")

    st.markdown("---")
    if st.button("🔄 Refresh from Supabase"):
        st.cache_data.clear()
        st.rerun()
    st.caption(
        f"{len(raw_bills)} total bills · {len(done)} paid/initiated this window · "
        f"{len(this_week)} pending this week · {len(overdue)} overdue"
    )
