"""Weekly Bill Pay Live — real-time Ramp bill status for the current week."""
import os
import json
from datetime import date, timedelta

import requests
import streamlit as st

from data import monday_of, fmt, fmt_date, parse_d

TODAY      = date(2026, 3, 30)
WEEK_START = monday_of(TODAY)
WEEK_END   = WEEK_START + timedelta(6)

# Statuses that count as "done" for this week
DONE_STATUSES   = {"INITIATED", "PAID", "SCHEDULED_PAID"}
PENDING_STATUSES = {"UNSCHEDULED", "SCHEDULED", "READY_FOR_PAYMENT",
                    "PENDING", "WAITING_FOR_MATCH"}

STATUS_LABELS = {
    "INITIATED":          "🟢 Initiated",
    "PAID":               "✅ Paid",
    "SCHEDULED_PAID":     "✅ Paid",
    "SCHEDULED":          "🔵 Scheduled",
    "UNSCHEDULED":        "⚪ Unscheduled",
    "READY_FOR_PAYMENT":  "🟡 Ready for Payment",
    "PENDING":            "🟡 Pending",
    "WAITING_FOR_MATCH":  "🟠 Waiting for Match",
}

STATUS_COLORS = {
    "INITIATED":         "#2e8b57",
    "PAID":              "#2e8b57",
    "SCHEDULED":         "#6495ed",
    "UNSCHEDULED":       "#9e9990",
    "READY_FOR_PAYMENT": "#b8860b",
    "PENDING":           "#b8860b",
    "WAITING_FOR_MATCH": "#cc7722",
}


# ─────────────────────────────────────────────────────────────
# RAMP API — live pull
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)  # Cache for 5 minutes — refresh on reopen
def fetch_live_bills() -> list:
    """Pull all unpaid + recently paid bills from Ramp. Cached 5 min."""
    cid  = st.secrets.get("RAMP_CLIENT_ID", "")  or os.environ.get("RAMP_CLIENT_ID", "")
    csec = st.secrets.get("RAMP_CLIENT_SECRET", "") or os.environ.get("RAMP_CLIENT_SECRET", "")

    if not cid or not csec:
        # Return demo data if no credentials configured
        return _demo_bills()

    try:
        # Get token
        token_resp = requests.post(
            "https://api.ramp.com/developer/v1/token",
            data={"grant_type": "client_credentials",
                  "client_id": cid, "client_secret": csec,
                  "scope": "bills:read"},
            timeout=30,
        )
        token_resp.raise_for_status()
        token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Pull bills — all statuses so we can see paid ones too
        bills, next_page = [], None
        params = {"from_date": "2024-01-01", "page_size": 100}

        while True:
            if next_page: params["page_cursor"] = next_page
            resp = requests.get("https://api.ramp.com/developer/v1/bills",
                                headers=headers, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            bills.extend(data.get("data", []))
            next_page = data.get("page", {}).get("next")
            if not next_page: break

        return [_parse_bill(b) for b in bills]

    except Exception as e:
        st.error(f"Ramp API error: {e}")
        return _demo_bills()


def _parse_bill(b: dict) -> dict:
    cd = b.get("canonical_dates") or {}
    if isinstance(cd, str):
        try: cd = json.loads(cd)
        except: cd = {}
    return {
        "id":        b.get("id", ""),
        "vendor":    (b.get("vendor") or {}).get("name", "") or b.get("payee_name", ""),
        "status":    (b.get("payment_status") or "UNSCHEDULED").upper().replace(" ", "_"),
        "amount":    float(b.get("amount") or 0),
        "due_date":  parse_d(cd.get("bill_due_at")),
        "paid_date": parse_d(cd.get("bill_paid_at")),
        "memo":      (b.get("memo") or "")[:60],
    }


def _demo_bills() -> list:
    """Demo data when Ramp credentials not configured."""
    return [
        {"id":"g001","vendor":"Google LLC","status":"INITIATED","amount":184642.80,
         "due_date":date(2026,3,30),"paid_date":date(2026,3,30),"memo":"Google Ads advertising services"},
        {"id":"xb01","vendor":"XB Fulfillment","status":"INITIATED","amount":17165.63,
         "due_date":date(2026,3,30),"paid_date":date(2026,3,30),"memo":"Drayage March 2 to March 8"},
        {"id":"xb02","vendor":"XB Fulfillment","status":"INITIATED","amount":6316.47,
         "due_date":date(2026,3,30),"paid_date":date(2026,3,30),"memo":"Drayage Feb 23 to Mar 01"},
        {"id":"xb03","vendor":"XB Fulfillment","status":"INITIATED","amount":3824.40,
         "due_date":date(2026,3,30),"paid_date":date(2026,3,30),"memo":"Scrap charges disposal services"},
        {"id":"ada1","vendor":"Alexander Adamov (Fit Modeling Services)","status":"INITIATED","amount":300.00,
         "due_date":date(2026,3,30),"paid_date":date(2026,3,30),"memo":"Fitting services"},
        {"id":"sbh1","vendor":"SBH Plus, Inc","status":"INITIATED","amount":1428.00,
         "due_date":date(2026,3,30),"paid_date":date(2026,3,30),"memo":"Temporary staffing"},
        {"id":"ad01","vendor":"Ad Results Media, LLC","status":"INITIATED","amount":88751.14,
         "due_date":date(2026,1,6),"paid_date":date(2026,3,30),"memo":"Broadcast media - programmatic"},
        {"id":"cbz1","vendor":"CBIZ CPAS P.C.","status":"UNSCHEDULED","amount":73500.00,
         "due_date":date(2026,2,1),"paid_date":None,"memo":"Audit services fiscal year 2025"},
        {"id":"rak1","vendor":"Rakuten Marketing LLC","status":"UNSCHEDULED","amount":40502.60,
         "due_date":date(2026,2,28),"paid_date":None,"memo":"Affiliate marketing commissions"},
        {"id":"ben1","vendor":"Benjo Arwas Studio","status":"UNSCHEDULED","amount":21322.75,
         "due_date":date(2026,2,15),"paid_date":None,"memo":"Photography services"},
        {"id":"joa1","vendor":"Joanna Goddard, Inc.","status":"UNSCHEDULED","amount":20000.00,
         "due_date":date(2026,2,28),"paid_date":None,"memo":"Advertising services"},
        {"id":"nic1","vendor":"Nicholas Duers Photography LLC","status":"UNSCHEDULED","amount":15862.71,
         "due_date":date(2026,2,1),"paid_date":None,"memo":"Photography services"},
        {"id":"agen1","vendor":"Agency Within LLC DBA Brkfst","status":"READY_FOR_PAYMENT","amount":6180.14,
         "due_date":date(2026,3,30),"paid_date":None,"memo":"Brkfst Ad Spend Fee Feb 2026"},
        {"id":"rhg1","vendor":"Rhg USA LLC","status":"READY_FOR_PAYMENT","amount":8954.20,
         "due_date":date(2026,3,15),"paid_date":None,"memo":"Recycled LDPE bags"},
        {"id":"imp1","vendor":"Imperial Dade","status":"UNSCHEDULED","amount":12427.43,
         "due_date":date(2026,2,20),"paid_date":None,"memo":"Shipping boxes"},
        {"id":"sgs1","vendor":"SGS North America Inc.","status":"PENDING","amount":4188.99,
         "due_date":date(2026,3,30),"paid_date":None,"memo":"Lab testing services"},
        {"id":"tuc1","vendor":"Tucker & Latifi, LLP","status":"UNSCHEDULED","amount":5890.00,
         "due_date":date(2026,2,15),"paid_date":None,"memo":"Legal fees - trademark"},
        {"id":"ken1","vendor":"Kensington Grey International Inc.","status":"UNSCHEDULED","amount":6000.00,
         "due_date":date(2026,2,28),"paid_date":None,"memo":"Influencer marketing"},
    ]


def _is_this_week(d: date) -> bool:
    return d and WEEK_START <= d <= WEEK_END


# ─────────────────────────────────────────────────────────────
# PAGE
# ─────────────────────────────────────────────────────────────
def show():
    st.markdown(f"""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON — LIVE</div>
        <h1>⚡ Weekly Bill Pay — Live</h1>
      </div>
      <div class="mw-badge" style="background:rgba(46,139,87,0.2);color:#2e8b57">
        Live from Ramp · refreshes every 5 min
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.caption(f"Current week: {WEEK_START.strftime('%-m/%-d')} – {WEEK_END.strftime('%-m/%-d/%Y')}  ·  "
               f"Initiated bills are treated as paid  ·  Last refresh: just now")

    with st.spinner("Loading live Ramp data..."):
        all_bills = fetch_live_bills()

    if not all_bills:
        st.warning("No bills found — check Ramp credentials in Streamlit secrets.")
        return

    # ── Categorize bills ─────────────────────────────────────
    # DONE: Initiated (any due date) OR Paid this week
    done, pending = [], []

    for b in all_bills:
        if b["amount"] <= 0: continue
        s = b["status"]

        if s == "INITIATED":
            done.append(b)
        elif s in ("PAID", "SCHEDULED_PAID"):
            if _is_this_week(b["paid_date"]):
                done.append(b)
        elif s in PENDING_STATUSES:
            pending.append(b)

    # Sort both by amount desc
    done    = sorted(done,    key=lambda x: -x["amount"])
    pending = sorted(pending, key=lambda x: -x["amount"])

    total_done    = sum(b["amount"] for b in done)
    total_pending = sum(b["amount"] for b in pending)
    total_all     = total_done + total_pending
    pct_done      = (total_done / total_all * 100) if total_all > 0 else 0

    # ── Summary cards ─────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total This Week", fmt(total_all))
    c2.metric("✅ Paid / Initiated", fmt(total_done), f"{len(done)} bills")
    c3.metric("⏳ Still Pending", fmt(total_pending), f"{len(pending)} bills")
    c4.metric("% Complete", f"{pct_done:.0f}%")

    # Progress bar
    st.markdown(f"""
    <div style="background:rgba(255,255,255,0.06);border-radius:6px;overflow:hidden;height:8px;margin:8px 0 20px;">
      <div style="background:#2e8b57;width:{pct_done:.0f}%;height:100%;border-radius:6px;transition:width 0.5s;"></div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── DONE section ─────────────────────────────────────────
    st.markdown("### ✅ Paid & Initiated")
    st.caption("Bills marked as Paid in Ramp this week, plus all Initiated bills (payment triggered)")

    if done:
        import pandas as pd
        done_rows = []
        for b in done:
            status_label = STATUS_LABELS.get(b["status"], b["status"])
            done_rows.append({
                "Vendor":      b["vendor"],
                "Description": b["memo"],
                "Status":      status_label,
                "Due Date":    fmt_date(b["due_date"]),
                "Paid Date":   fmt_date(b["paid_date"]) if b["paid_date"] else "—",
                "Amount":      fmt(b["amount"]),
            })
        df_done = pd.DataFrame(done_rows)
        st.dataframe(df_done, use_container_width=True, hide_index=True,
                     height=min(35 * len(done_rows) + 38, 400))

        col_l, col_r = st.columns([4, 1])
        col_l.markdown("*Subtotal — Paid & Initiated*")
        col_r.markdown(f"**{fmt(total_done)}**")
    else:
        st.info("No bills paid or initiated this week yet.")

    st.markdown("---")

    # ── PENDING section ───────────────────────────────────────
    st.markdown("### ⏳ Still Pending")
    st.caption("Bills not yet initiated or paid — includes overdue unpaid bills")

    if pending:
        import pandas as pd
        pending_rows = []
        for b in pending:
            days_out = (TODAY - b["due_date"]).days if b["due_date"] else 0
            overdue_str = f"+{days_out}d overdue" if days_out > 0 else (
                f"due {fmt_date(b['due_date'])}" if b["due_date"] else "—")
            status_label = STATUS_LABELS.get(b["status"], b["status"])
            pending_rows.append({
                "Vendor":      b["vendor"],
                "Description": b["memo"],
                "Status":      status_label,
                "Due":         overdue_str,
                "Amount":      fmt(b["amount"]),
            })
        df_pend = pd.DataFrame(pending_rows)
        st.dataframe(df_pend, use_container_width=True, hide_index=True,
                     height=min(35 * len(pending_rows) + 38, 500))

        col_l, col_r = st.columns([4, 1])
        col_l.markdown("*Subtotal — Still Pending*")
        col_r.markdown(f"**{fmt(total_pending)}**")
    else:
        st.success("All bills paid or initiated this week! 🎉")

    # ── Refresh button ─────────────────────────────────────────
    st.markdown("---")
    if st.button("🔄 Refresh from Ramp now"):
        st.cache_data.clear()
        st.rerun()
