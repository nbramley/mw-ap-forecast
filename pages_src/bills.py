"""Bill View — pulls all outstanding bills from Supabase."""
import os
from datetime import date

import requests
import streamlit as st

from data import delete_override, fetch_overrides, fmt, fmt_date, monday_of, save_override

TODAY      = date(2026, 3, 30)
WEEK_START = monday_of(TODAY)


@st.cache_data(ttl=300)
def fetch_bills_from_supabase():
    """Pull all bills from Supabase bills table."""
    url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
    key = st.secrets.get("SUPABASE_KEY", "") or os.environ.get("SUPABASE_KEY", "")
    if not url or not key:
        return []
    try:
        resp = requests.get(
            f"{url}/rest/v1/bills",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            params={"select": "*", "order": "due_date.asc", "limit": "500"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # Map to standard bill format
        bills = []
        for b in data:
            # Skip credits/negatives
            if float(b.get("amount", 0) or 0) <= 0:
                continue
            # Determine category
            source = b.get("source", "")
            vendor = b.get("vendor", "")
            if source == "NetSuite":
                cat = "Inventory"
            elif source == "Ramp":
                from data import PRIORITY_TERMS
                cat = "Ramp Priority" if vendor in PRIORITY_TERMS else "Ramp Standard"
            else:
                cat = source

            bills.append({
                "id":       b.get("id", ""),
                "source":   source,
                "cat":      cat,
                "vendor":   vendor,
                "inv":      b.get("invoice_id", ""),
                "desc":     b.get("description", "") or b.get("memo", ""),
                "inv_date": b.get("invoice_date", ""),
                "due_date": b.get("due_date", ""),
                "amount":   float(b.get("amount", 0) or 0),
            })
        return bills
    except Exception as e:
        st.warning(f"Could not load from Supabase: {e}")
        return []


def show():
    st.markdown("""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>Consolidated Bill View</h1>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "⚡ **Override Date column:** Enter a date to move a specific bill to a different payment week. "
        "Overrides save to Supabase automatically and persist week-to-week.",
        icon="💛"
    )

    overrides = fetch_overrides()

    # ── Load bills ────────────────────────────────────────────
    with st.spinner("Loading bills from Supabase..."):
        bills = fetch_bills_from_supabase()

    if not bills:
        st.warning("No bills found in Supabase. Run 'weekly AP update' in Claude to populate.")
        return

    # ── Filters ───────────────────────────────────────────────
    col_s, col_c, col_ov = st.columns([3, 2, 2])
    search  = col_s.text_input("🔍 Search vendors", placeholder="Type to filter…")
    cat_flt = col_c.selectbox("Category", ["All", "Inventory", "Ramp Priority", "Ramp Standard"])
    ov_only = col_ov.checkbox("Overdue only")

    # Apply filters
    filtered = bills
    if search:
        filtered = [b for b in filtered if search.lower() in b["vendor"].lower() or search.lower() in (b["desc"] or "").lower()]
    if cat_flt != "All":
        filtered = [b for b in filtered if b["cat"] == cat_flt]
    if ov_only:
        filtered = [b for b in filtered if b["due_date"] and date.fromisoformat(b["due_date"]) < TODAY]

    filtered = sorted(filtered, key=lambda b: b.get("due_date") or "")

    total_amt = sum(b["amount"] for b in filtered)
    st.markdown(f"**{len(filtered)} bills · {fmt(total_amt)} total**")
    st.markdown("---")

    # ── Render bills ──────────────────────────────────────────
    CAT_COLORS = {
        "Inventory":     "#B8935A",
        "Ramp Priority": "#6495ed",
        "Ramp Standard": "#5a5550",
    }

    for b in filtered:
        due      = date.fromisoformat(b["due_date"]) if b.get("due_date") else None
        days_out = (TODAY - due).days if due else 0
        is_ov    = days_out > 0
        cur_ovr  = overrides.get(b["inv"])
        cat_color = CAT_COLORS.get(b["cat"], "#5a5550")

        with st.container():
            col_v, col_cat, col_due, col_days, col_amt, col_ov_input, col_del = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.8, 0.5])

            col_v.markdown(
                f"**{b['vendor']}**  \n<small style='color:#9e9990'>{(b['desc'] or '')[:55]}</small>",
                unsafe_allow_html=True
            )
            col_cat.markdown(
                f"<span style='background:rgba(0,0,0,0.2);color:{cat_color};padding:2px 8px;"
                f"border-radius:10px;font-size:10px;font-weight:600'>{b['cat']}</span>",
                unsafe_allow_html=True
            )
            col_due.markdown(
                f"<small style='color:#9e9990'>Due</small>  \n**{fmt_date(b['due_date']) if b.get('due_date') else '—'}**",
                unsafe_allow_html=True
            )
            col_days.markdown(
                f"<small style='color:#9e9990'>Days O/S</small>  \n"
                f"<span style='color:{'#d94f4f' if is_ov else '#9e9990'};font-weight:{'600' if is_ov else '400'}'>"
                f"{'🔴 +' + str(days_out) + 'd' if is_ov else ('✅ in ' + str(-days_out) + 'd' if days_out < 0 else 'Today')}"
                f"</span>",
                unsafe_allow_html=True
            )
            col_amt.markdown(
                f"<small style='color:#9e9990'>Amount</small>  \n**{fmt(b['amount'])}**",
                unsafe_allow_html=True
            )

            new_override = col_ov_input.date_input(
                "Override",
                value=cur_ovr,
                key=f"ov_{b['id']}",
                label_visibility="collapsed",
                format="MM/DD/YYYY",
            )

            if new_override and new_override != cur_ovr:
                if save_override(b["inv"], b["vendor"], b["source"], new_override):
                    st.success(f"✓ Override saved for {b['vendor']}", icon="✅")
                    st.rerun()

            if cur_ovr and col_del.button("✕", key=f"del_{b['id']}", help="Remove override"):
                delete_override(b["inv"])
                st.rerun()

            st.divider()

    # Refresh button
    st.markdown("---")
    if st.button("🔄 Refresh bills from Supabase"):
        st.cache_data.clear()
        st.rerun()
