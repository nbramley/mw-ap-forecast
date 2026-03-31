"""Weekly Bill Pay Live — real-time status view pulling from Supabase + Ramp status."""
import os
from datetime import date, timedelta

import requests
import streamlit as st

from data import PRIORITY_TERMS, INVENTORY_TERMS, adj_back, fmt, fmt_date, monday_of

TODAY      = date(2026, 3, 31)
WEEK_START = monday_of(TODAY)
WEEK_END   = WEEK_START + timedelta(6)

STATUS_LABELS = {
    "initiated":         "🟢 Initiated",
    "paid":              "✅ Paid",
    "scheduled":         "🔵 Scheduled",
    "unscheduled":       "⚪ Unscheduled",
    "ready_for_payment": "🟡 Ready for Payment",
    "pending":           "🟡 Pending",
    "waiting_for_match": "🟠 Waiting for Match",
}

DONE_STATUSES    = {"initiated", "paid"}
PENDING_STATUSES = {"unscheduled", "scheduled", "ready_for_payment",
                    "pending", "waiting_for_match"}


@st.cache_data(ttl=300)
def fetch_all_bills():
    """Pull all bills from Supabase."""
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


def get_payment_date(bill: dict) -> date:
    """Calculate expected payment date for a bill based on terms."""
    vendor = bill.get("vendor", "")
    source = bill.get("source", "")
    due    = parse_d(bill.get("due_date"))
    if not due:
        return None

    if source == "NetSuite":
        days = INVENTORY_TERMS.get(vendor, 0)
        return adj_back(due + timedelta(days=days))
    elif source == "Ramp":
        if vendor in PRIORITY_TERMS:
            days = PRIORITY_TERMS.get(vendor, 60)
            if days == "due":
                return adj_back(due)
            elif isinstance(days, int):
                return adj_back(due + timedelta(days=days))
        return adj_back(due + timedelta(days=60))
    return None


def days_out_str(due: date) -> str:
    if not due: return "—"
    days = (TODAY - due).days
    if days > 0:    return f"+{days}d overdue"
    elif days == 0: return "Due today"
    else:           return f"In {-days}d"


def show():
    st.markdown(f"""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON — LIVE</div>
        <h1>⚡ Weekly Bill Pay — Live</h1>
      </div>
      <div class="mw-badge" style="background:rgba(46,139,87,0.2);color:#2e8b57">
        Wk {WEEK_START.strftime('%-m/%-d')}–{WEEK_END.strftime('%-m/%-d')} · From Supabase
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        f"Initiated bills treated as paid · "
        f"Status updated each Monday via 'run weekly AP update' · "
        f"As of {TODAY.strftime('%-m/%-d/%Y')}"
    )

    with st.spinner("Loading bills from Supabase..."):
        raw_bills = fetch_all_bills()

    if not raw_bills:
        st.warning("No bills found in Supabase. Run 'weekly AP update' in Claude to populate.")
        return

    # ── Categorize ALL bills by status ─────────────────────────
    # Done = Initiated or Paid
    # Pending = everything else (Unscheduled, Scheduled, Ready for Payment, etc.)
    # For NetSuite bills, treat as Unpaid/pending unless explicitly paid

    done    = []
    pending = []

    for b in raw_bills:
        vendor = b.get("vendor", "")
        amount = float(b.get("amount") or 0)
        if amount <= 0:
            continue

        source      = b.get("source", "")
        paid_status = (b.get("paid_status") or "Unscheduled").lower().replace(" ", "_")
        due         = parse_d(b.get("due_date"))
        inv_id      = b.get("invoice_id", "")
        memo        = (b.get("memo") or b.get("description") or "")[:60]
        pay_date    = get_payment_date(b)

        row = {
            "vendor":   vendor,
            "inv":      inv_id,
            "memo":     memo,
            "status":   paid_status,
            "status_label": STATUS_LABELS.get(paid_status, paid_status.title()),
            "due":      due,
            "pay_date": pay_date,
            "amount":   amount,
            "source":   source,
        }

        if paid_status in DONE_STATUSES:
            done.append(row)
        else:
            pending.append(row)

    # Sort both by amount desc
    done    = sorted(done,    key=lambda x: -x["amount"])
    pending = sorted(pending, key=lambda x: -x["amount"])

    total_done    = sum(b["amount"] for b in done)
    total_pending = sum(b["amount"] for b in pending)
    total_all     = total_done + total_pending
    pct_done      = (total_done / total_all * 100) if total_all > 0 else 0

    # ── Summary cards ───────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Outstanding",   fmt(total_all))
    c2.metric("✅ Paid / Initiated",  fmt(total_done),    f"{len(done)} bills")
    c3.metric("⏳ Still Pending",     fmt(total_pending), f"{len(pending)} bills")
    c4.metric("% Complete",          f"{pct_done:.0f}%")

    # Progress bar
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.06);border-radius:6px;overflow:hidden;
    height:8px;margin:8px 0 20px;">
      <div style="background:#2e8b57;width:{pct_done:.0f}%;height:100%;border-radius:6px;"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filter controls ─────────────────────────────────────────
    st.markdown("---")
    col_s, col_src, col_wk = st.columns([3, 2, 2])
    search   = col_s.text_input("🔍 Search vendors", placeholder="Filter by vendor...")
    src_flt  = col_src.selectbox("Source", ["All", "Ramp", "NetSuite"])
    wk_only  = col_wk.checkbox("This week's payments only", value=False)

    def apply_filters(bills):
        if search:
            bills = [b for b in bills if search.lower() in b["vendor"].lower()]
        if src_flt != "All":
            bills = [b for b in bills if b["source"] == src_flt]
        if wk_only:
            bills = [b for b in bills if b.get("pay_date") and WEEK_START <= b["pay_date"] <= WEEK_END]
        return bills

    filtered_done    = apply_filters(done)
    filtered_pending = apply_filters(pending)

    import pandas as pd

    # ── DONE section ────────────────────────────────────────────
    st.markdown(f"### ✅ Paid & Initiated  <span style='font-size:14px;color:#9e9990;font-weight:normal'>({len(filtered_done)} bills · {fmt(sum(b['amount'] for b in filtered_done))})</span>", unsafe_allow_html=True)
    st.caption("Bills marked Paid in Ramp, plus all Initiated bills (payment triggered)")

    if filtered_done:
        rows = []
        for b in filtered_done:
            rows.append({
                "Vendor":      b["vendor"],
                "Invoice #":   b["inv"],
                "Description": b["memo"],
                "Status":      b["status_label"],
                "Due Date":    fmt_date(b["due"]) if b["due"] else "—",
                "Sched. Pay":  fmt_date(b["pay_date"]) if b["pay_date"] else "—",
                "Amount":      fmt(b["amount"]),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 500))
        col_l, col_r = st.columns([4, 1])
        col_l.markdown("*Subtotal — Paid & Initiated*")
        col_r.markdown(f"**{fmt(sum(b['amount'] for b in filtered_done))}**")
    else:
        st.info("No paid or initiated bills match current filters.")

    st.markdown("---")

    # ── PENDING section ─────────────────────────────────────────
    st.markdown(f"### ⏳ Still Pending  <span style='font-size:14px;color:#9e9990;font-weight:normal'>({len(filtered_pending)} bills · {fmt(sum(b['amount'] for b in filtered_pending))})</span>", unsafe_allow_html=True)
    st.caption("Bills not yet initiated or paid — includes all overdue unpaid bills")

    if filtered_pending:
        rows = []
        for b in filtered_pending:
            rows.append({
                "Vendor":      b["vendor"],
                "Invoice #":   b["inv"],
                "Description": b["memo"],
                "Status":      b["status_label"],
                "Due Date":    fmt_date(b["due"]) if b["due"] else "—",
                "Days O/S":    days_out_str(b["due"]),
                "Sched. Pay":  fmt_date(b["pay_date"]) if b["pay_date"] else "—",
                "Amount":      fmt(b["amount"]),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 600))
        col_l, col_r = st.columns([4, 1])
        col_l.markdown("*Subtotal — Still Pending*")
        col_r.markdown(f"**{fmt(sum(b['amount'] for b in filtered_pending))}**")
    else:
        st.success("All bills paid or initiated! 🎉")

    st.markdown("---")
    if st.button("🔄 Refresh from Supabase"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"{len(raw_bills)} total bills in Supabase · {len(done)} paid/initiated · {len(pending)} pending")
