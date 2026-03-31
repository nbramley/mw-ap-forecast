"""Payment Terms — editable vendor rules + Customs & Duties editor."""
import json
import os
import requests
import streamlit as st
from data import INVENTORY_TERMS, PRIORITY_TERMS

MONTH_NAMES = ["January","February","March","April","May","June",
               "July","August","September","October","November","December"]


@st.cache_data(ttl=60)
def fetch_customs():
    url = st.secrets.get("SUPABASE_URL","") or os.environ.get("SUPABASE_URL","")
    key = st.secrets.get("SUPABASE_KEY","") or os.environ.get("SUPABASE_KEY","")
    if not url or not key:
        return {}
    try:
        resp = requests.get(
            f"{url}/rest/v1/customs_duties",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            params={"select": "*", "order": "month_num.asc"},
            timeout=10,
        )
        resp.raise_for_status()
        return {row["month_num"]: row for row in resp.json()}
    except Exception as e:
        st.warning(f"Could not load customs data: {e}")
        return {}


def save_customs(month_num: int, amount: float, notes: str = ""):
    url = st.secrets.get("SUPABASE_URL","") or os.environ.get("SUPABASE_URL","")
    key = st.secrets.get("SUPABASE_KEY","") or os.environ.get("SUPABASE_KEY","")
    if not url or not key:
        return False
    try:
        resp = requests.patch(
            f"{url}/rest/v1/customs_duties",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "Prefer": "return=minimal"},
            params={"month_num": f"eq.{month_num}"},
            json={"amount": amount, "notes": notes},
            timeout=10,
        )
        resp.raise_for_status()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

DEFAULT_INVENTORY = [
    {"vendor": k, "days": v, "description": f"{v} days past due date"}
    for k, v in INVENTORY_TERMS.items()
]

DEFAULT_PRIORITY = [
    {"vendor": "Kristina Boiano",                                "days": 0,    "description": "Pay on due date"},
    {"vendor": "R&A Engineering LLC",                            "days": 5,    "description": "5 days past due date"},
    {"vendor": "Alexander Adamov (Fit Modeling Services)",       "days": 15,   "description": "15 days past due date"},
    {"vendor": "Barrel LLC",                                     "days": 15,   "description": "15 days past due date"},
    {"vendor": "SBH Plus, Inc",                                  "days": 15,   "description": "15 days past due date"},
    {"vendor": "ERY Retail Podium LLC",                          "days": 25,   "description": "25 days past due date"},
    {"vendor": "Fin Technologies dba Alkami Technology, Inc",    "days": 25,   "description": "25 days past due date"},
    {"vendor": "Madeleine Lachesnez",                            "days": 30,   "description": "30 days past due date"},
    {"vendor": "Oracle America Inc.",                            "days": 30,   "description": "30 days past due date"},
    {"vendor": "STUDIO TAVISH TIMOTHY LLC",                      "days": 30,   "description": "30 days past due date"},
    {"vendor": "Nick Pichaiwongse",                              "days": 45,   "description": "45 days past due date"},
    {"vendor": "Google LLC",                                     "days": None, "description": "3rd week of due month (custom logic)"},
    {"vendor": "XB Fulfillment",                                 "days": None, "description": "One-time: all bills week of 3/30/2026 (wind-down)"},
]

DEFAULT_FIXED = [
    {"vendor": "Ramp Credit Card",           "days": None, "description": "$150,000 on 12th each month — auto-debit"},
    {"vendor": "JustWorks — Taxes/Benefits", "days": None, "description": "$32,624 per occurrence — fixed schedule"},
    {"vendor": "JustWorks — Mid-Month",      "days": None, "description": "$184,962 per occurrence — fixed schedule"},
    {"vendor": "JustWorks — End-Month",      "days": None, "description": "$184,962 per occurrence — fixed schedule"},
    {"vendor": "Customs & Duties",           "days": None, "description": "Paid on 23rd each month — auto-debit"},
    {"vendor": "Numeral",                    "days": None, "description": "Filed: day after filing. Next month: 5% of prior revenue — auto-debit"},
    {"vendor": "Shipping",                   "days": None, "description": "6% of daily discounted revenue, rounded up $10K"},
    {"vendor": "Other",                      "days": None, "description": "$20,000 per week — hardcoded"},
]


def show():
    st.markdown("""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>Payment Terms</h1>
      </div>
      <div class="mw-badge" style="background:rgba(46,139,87,0.2);color:#2e8b57">Editable</div>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "⚡ **Changes saved here update the forecast logic.** "
        "Days from Due drives all payment date calculations. "
        "To make changes permanent in the Python engine, also update `data.py`.",
        icon="ℹ️"
    )

    # ── CUSTOMS & DUTIES EDITOR ───────────────────────────────
    st.markdown("### 🛃 Customs & Duties — Monthly Amounts")
    st.caption("Paid on the 23rd of each month. Changes save to Supabase and persist week to week.")

    customs = fetch_customs()
    if not customs:
        st.warning("Could not load customs data from Supabase.")
    else:
        from datetime import date as _date
        current_month = _date.today().month
        months_ordered = list(range(1, 13))
        months_ordered = months_ordered[current_month-1:] + months_ordered[:current_month-1]
        changed = {}
        cols = st.columns(4)
        for i, m in enumerate(months_ordered):
            row = customs.get(m, {})
            current_amt   = float(row.get("amount", 0))
            current_notes = row.get("notes", "") or ""
            with cols[i % 4]:
                st.markdown(f"**{MONTH_NAMES[m-1]}** · *23rd*")
                new_amt = st.number_input(
                    f"Amount {m}", value=current_amt, min_value=0.0, step=1000.0,
                    format="%.0f", key=f"cust_{m}", label_visibility="collapsed",
                )
                new_notes = st.text_input(
                    f"Notes {m}", value=current_notes, key=f"custnotes_{m}",
                    placeholder="Actual / Forecast", label_visibility="collapsed",
                )
                if new_amt != current_amt or new_notes != current_notes:
                    changed[m] = (new_amt, new_notes)
        if changed:
            if st.button(f"💾 Save {len(changed)} customs change(s)", type="primary", key="save_customs"):
                ok = sum(1 for m, (a, n) in changed.items() if save_customs(m, a, n))
                if ok == len(changed):
                    st.success(f"✅ Saved {ok} month(s) — all tabs will reflect the update.")
                    st.rerun()
                else:
                    st.error("Some saves failed — check Supabase connection.")

    st.markdown("---")


    # Load from session state or defaults
    if "terms_inventory" not in st.session_state:
        st.session_state.terms_inventory = [dict(r) for r in DEFAULT_INVENTORY]
    if "terms_priority" not in st.session_state:
        st.session_state.terms_priority = [dict(r) for r in DEFAULT_PRIORITY]

    # ── INVENTORY ─────────────────────────────────────────────
    st.markdown("### Inventory Vendors")
    st.caption("Payment terms applied to QuickBooks inventory invoices. Days are added to the invoice due date.")

    inv_rows = st.session_state.terms_inventory
    col_v, col_d, col_desc, col_del = st.columns([3, 1, 3, 0.5])
    col_v.markdown("**Vendor**")
    col_d.markdown("**Days**")
    col_desc.markdown("**Description**")

    inv_changed = False
    for i, row in enumerate(inv_rows):
        col_v, col_d, col_desc, col_del = st.columns([3, 1, 3, 0.5])
        new_vendor = col_v.text_input("v", value=row["vendor"], key=f"inv_v_{i}", label_visibility="collapsed")
        new_days   = col_d.number_input("d", value=row["days"] or 0, min_value=0, max_value=365, key=f"inv_d_{i}", label_visibility="collapsed")
        new_desc   = col_desc.text_input("desc", value=row["description"], key=f"inv_desc_{i}", label_visibility="collapsed")
        if col_del.button("✕", key=f"inv_del_{i}"):
            inv_rows.pop(i)
            inv_changed = True
            st.rerun()
        if new_vendor != row["vendor"] or new_days != (row["days"] or 0) or new_desc != row["description"]:
            row["vendor"] = new_vendor
            row["days"]   = int(new_days)
            row["description"] = new_desc
            inv_changed = True

    if st.button("+ Add inventory vendor", key="add_inv"):
        inv_rows.append({"vendor": "New Vendor", "days": 30, "description": "30 days past due date"})
        st.rerun()

    st.markdown("---")

    # ── RAMP PRIORITY ─────────────────────────────────────────
    st.markdown("### Ramp — Priority Vendors")
    st.caption("Vendors with custom negotiated terms. All other Ramp vendors default to 60 days past due.")

    pri_rows = st.session_state.terms_priority
    col_v, col_d, col_desc, col_del = st.columns([3, 1, 3, 0.5])
    col_v.markdown("**Vendor**")
    col_d.markdown("**Days**")
    col_desc.markdown("**Description / Notes**")

    for i, row in enumerate(pri_rows):
        col_v, col_d, col_desc, col_del = st.columns([3, 1, 3, 0.5])
        new_vendor = col_v.text_input("v", value=row["vendor"], key=f"pri_v_{i}", label_visibility="collapsed")
        is_custom  = row["days"] is None
        if is_custom:
            col_d.text_input("d", value="Custom", key=f"pri_d_{i}", disabled=True, label_visibility="collapsed")
            new_days = None
        else:
            new_days = int(col_d.number_input("d", value=row["days"] or 0, min_value=0, max_value=365,
                                              key=f"pri_d_{i}", label_visibility="collapsed"))
        new_desc   = col_desc.text_input("desc", value=row["description"], key=f"pri_desc_{i}", label_visibility="collapsed")
        if col_del.button("✕", key=f"pri_del_{i}"):
            pri_rows.pop(i)
            st.rerun()
        row["vendor"] = new_vendor
        row["days"]   = new_days
        row["description"] = new_desc

    if st.button("+ Add priority vendor", key="add_pri"):
        pri_rows.append({"vendor": "New Vendor", "days": 30, "description": "30 days past due date"})
        st.rerun()

    st.markdown("---")

    # ── RAMP STANDARD ─────────────────────────────────────────
    st.markdown("### Ramp — All Other Vendors")
    st.caption("Default fallback terms for any Ramp vendor not listed in Priority above.")
    col_a, col_b = st.columns([1, 3])
    col_a.metric("Default days from due", "60")
    col_b.info("All Ramp vendors not in the Priority list above automatically use 60 days past due date, adjusted for weekends.")

    st.markdown("---")

    # ── FIXED ─────────────────────────────────────────────────
    st.markdown("### Fixed & Auto-Debit Payments")
    st.caption("Informational only — these are hardcoded in the calculation engine. Edit descriptions only.")

    for row in DEFAULT_FIXED:
        col_v, col_d, col_desc = st.columns([3, 1, 3])
        col_v.text_input("v", value=row["vendor"], disabled=True, key=f"fixed_v_{row['vendor']}", label_visibility="collapsed")
        col_d.text_input("d", value="Auto" if row["days"] is None else str(row["days"]), disabled=True,
                         key=f"fixed_d_{row['vendor']}", label_visibility="collapsed")
        col_desc.text_input("desc", value=row["description"], key=f"fixed_desc_{row['vendor']}", label_visibility="collapsed")

    st.markdown("---")

    # ── Save ──────────────────────────────────────────────────
    col_save, col_reset, col_status = st.columns([1, 1, 4])
    if col_save.button("💾 Save Changes", type="primary"):
        st.session_state.terms_inventory = inv_rows
        st.session_state.terms_priority  = pri_rows
        st.success("✓ Payment terms saved — forecast will reflect changes next calculation run.")

    if col_reset.button("↩ Reset to defaults"):
        st.session_state.terms_inventory = [dict(r) for r in DEFAULT_INVENTORY]
        st.session_state.terms_priority  = [dict(r) for r in DEFAULT_PRIORITY]
        st.rerun()
