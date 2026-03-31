"""Bill View — all outstanding bills with override capability."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data import (PRIORITY_TERMS, delete_override, fetch_overrides,
                  fmt, fmt_date, monday_of, save_override)

TODAY      = date(2026, 3, 30)
WEEK_START = monday_of(TODAY)

# Demo bills — in production these come from Ramp API + NetSuite
DEMO_BILLS = [
    {"id":"bb64","source":"Ramp","cat":"Ramp Standard","vendor":"Ad Results Media, LLC","inv":"bb645675","desc":"Broadcast media - programmatic advertising campaign","inv_date":"2026-01-06","due_date":"2026-02-05","amount":55368.88},
    {"id":"ec24","source":"Ramp","cat":"Ramp Standard","vendor":"Ad Results Media, LLC","inv":"ec2d417e","desc":"Podcast advertising January 2026","inv_date":"2026-01-06","due_date":"2026-02-05","amount":33828.82},
    {"id":"c66e","source":"Ramp","cat":"Ramp Standard","vendor":"Ad Results Media, LLC","inv":"c66e876a","desc":"Podcast advertising spots multiple shows","inv_date":"2026-02-04","due_date":"2026-03-06","amount":43886.18},
    {"id":"ad9c","source":"Ramp","cat":"Ramp Standard","vendor":"Ad Results Media, LLC","inv":"ad9c77e2","desc":"Programmatic advertising February 2026","inv_date":"2026-02-04","due_date":"2026-03-06","amount":50963.92},
    {"id":"73bd","source":"Ramp","cat":"Ramp Standard","vendor":"Ad Results Media, LLC","inv":"73bd7d31","desc":"Broadcast media - podcast baked in spots","inv_date":"2025-12-02","due_date":"2026-01-01","amount":27847.17},
    {"id":"c3ec","source":"Ramp","cat":"Ramp Standard","vendor":"Agency Within LLC DBA Brkfst","inv":"c3ec8e8d","desc":"Ad spend fees December 2025","inv_date":"2025-12-31","due_date":"2026-01-30","amount":15498.88},
    {"id":"92f2","source":"Ramp","cat":"Ramp Standard","vendor":"Agency Within LLC DBA Brkfst","inv":"92f25913","desc":"Brkfst Ad Spend Fee February 2026","inv_date":"2026-02-28","due_date":"2026-03-30","amount":6180.14},
    {"id":"919c","source":"Ramp","cat":"Ramp Priority","vendor":"Alexander Adamov (Fit Modeling Services)","inv":"919cdaf2","desc":"Fitting services March 10 2026","inv_date":"2026-03-10","due_date":"2026-03-10","amount":450.00},
    {"id":"5aa1","source":"Ramp","cat":"Ramp Standard","vendor":"Apex Trial Law","inv":"5aa184cb","desc":"Settlement agreement - ADA website accessibility","inv_date":"2026-02-24","due_date":"2026-04-30","amount":6500.00},
    {"id":"b08e","source":"Ramp","cat":"Ramp Priority","vendor":"Barrel LLC","inv":"b08ebdd7","desc":"Website retainer ecommerce care plus CRO","inv_date":"2026-03-01","due_date":"2026-03-31","amount":37500.00},
    {"id":"cbiz1","source":"Ramp","cat":"Ramp Standard","vendor":"CBIZ CPAS P.C.","inv":"1946bc5b","desc":"Audit services fiscal year 2025","inv_date":"2026-02-01","due_date":"2026-02-01","amount":21000.00},
    {"id":"cbiz2","source":"Ramp","cat":"Ramp Standard","vendor":"CBIZ CPAS P.C.","inv":"0568c6c3","desc":"Audit services 2025 financial statements","inv_date":"2026-03-01","due_date":"2026-03-01","amount":52500.00},
    {"id":"ery","source":"Ramp","cat":"Ramp Priority","vendor":"ERY Retail Podium LLC","inv":"ee8b16f1","desc":"Retail rent and utility charges Hudson Yards","inv_date":"2026-03-01","due_date":"2026-03-01","amount":6065.34},
    {"id":"fin","source":"Ramp","cat":"Ramp Priority","vendor":"Fin Technologies dba Alkami Technology, Inc","inv":"2a841940","desc":"Monthly sublease rent and utility fees","inv_date":"2026-02-01","due_date":"2026-02-22","amount":17207.86},
    {"id":"google","source":"Ramp","cat":"Ramp Priority","vendor":"Google LLC","inv":"13ce3768","desc":"Google Ads advertising services","inv_date":"2026-02-28","due_date":"2026-03-30","amount":184642.80},
    {"id":"rak1","source":"Ramp","cat":"Ramp Standard","vendor":"Rakuten Marketing LLC","inv":"3012c9d6","desc":"Affiliate marketing Jan 2026","inv_date":"2026-01-31","due_date":"2026-02-28","amount":7183.98},
    {"id":"rak2","source":"Ramp","cat":"Ramp Standard","vendor":"Rakuten Marketing LLC","inv":"5dd67dc5","desc":"Affiliate commissions January 2026","inv_date":"2026-03-01","due_date":"2026-03-01","amount":33318.62},
    {"id":"xb1","source":"Ramp","cat":"Ramp Priority","vendor":"XB Fulfillment","inv":"d9b33874","desc":"Scrap charges disposal services","inv_date":"2026-03-06","due_date":"2026-03-24","amount":3824.40},
    {"id":"xb2","source":"Ramp","cat":"Ramp Priority","vendor":"XB Fulfillment","inv":"fd2fa43a","desc":"Drayage Feb 23 to Mar 01","inv_date":"2026-03-05","due_date":"2026-03-23","amount":6316.47},
    {"id":"xb3","source":"Ramp","cat":"Ramp Priority","vendor":"XB Fulfillment","inv":"03711c9e","desc":"Drayage March 2 to March 8","inv_date":"2026-03-12","due_date":"2026-03-13","amount":17165.63},
    {"id":"oracle1","source":"Ramp","cat":"Ramp Priority","vendor":"Oracle America Inc.","inv":"d26f3f58","desc":"NetSuite cloud services","inv_date":"2026-01-17","due_date":"2026-02-25","amount":13087.04},
    {"id":"rna","source":"Ramp","cat":"Ramp Priority","vendor":"R&A Engineering LLC","inv":"b2473d23","desc":"Data consulting services Feb-Mar","inv_date":"2026-03-19","due_date":"2026-04-18","amount":8000.00},
    # Inventory
    {"id":"inv_taa1","source":"Inventory","cat":"Inventory","vendor":"Triple A Apparel LTD","inv":"TA260054","desc":"Invoice TA260054","inv_date":"2026-01-31","due_date":"2026-03-01","amount":69826.42},
    {"id":"inv_taa2","source":"Inventory","cat":"Inventory","vendor":"Triple A Apparel LTD","inv":"TA260014","desc":"Invoice TA260014","inv_date":"2026-01-16","due_date":"2026-03-10","amount":25274.00},
    {"id":"inv_sg1","source":"Inventory","cat":"Inventory","vendor":"The S Group","inv":"INV10815","desc":"Invoice INV10815","inv_date":"2025-12-01","due_date":"2025-12-31","amount":12284.23},
    {"id":"inv_sg2","source":"Inventory","cat":"Inventory","vendor":"The S Group","inv":"INV10842","desc":"Invoice INV10842","inv_date":"2025-12-08","due_date":"2026-01-07","amount":18924.15},
    {"id":"inv_dg1","source":"Inventory","cat":"Inventory","vendor":"Delta Galil Industries Ltd.","inv":"DG-2025-4412","desc":"Invoice DG-2025-4412","inv_date":"2025-10-01","due_date":"2025-11-15","amount":89432.10},
    {"id":"inv_ap1","source":"Inventory","cat":"Inventory","vendor":"American Phil Textiles Limited","inv":"APT10051","desc":"Invoice APT10051","inv_date":"2025-10-21","due_date":"2025-11-30","amount":48697.60},
]


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

    # ── Filters ───────────────────────────────────────────────
    col_s, col_c, col_ov = st.columns([3, 2, 2])
    search   = col_s.text_input("🔍 Search vendors", placeholder="Type to filter…")
    cat_flt  = col_c.selectbox("Category", ["All", "Inventory", "Ramp Priority", "Ramp Standard"])
    ov_only  = col_ov.checkbox("Overdue only")

    # ── Filter bills ──────────────────────────────────────────
    bills = DEMO_BILLS
    if search:
        bills = [b for b in bills if search.lower() in b["vendor"].lower() or search.lower() in b["desc"].lower()]
    if cat_flt != "All":
        bills = [b for b in bills if b["cat"] == cat_flt]
    if ov_only:
        bills = [b for b in bills if date.fromisoformat(b["due_date"]) < TODAY]

    # Sort by due date
    bills = sorted(bills, key=lambda b: b["due_date"])

    total_amt = sum(b["amount"] for b in bills)
    st.markdown(f"**{len(bills)} bills · {fmt(total_amt)} total**")
    st.markdown("---")

    # ── Render each bill with override input ──────────────────
    CAT_COLORS = {
        "Inventory":     "#B8935A",
        "Ramp Priority": "#6495ed",
        "Ramp Standard": "#5a5550",
    }

    for b in bills:
        due       = date.fromisoformat(b["due_date"])
        days_out  = (TODAY - due).days
        is_ov     = days_out > 0
        cur_ovr   = overrides.get(b["inv"])
        cat_color = CAT_COLORS.get(b["cat"], "#5a5550")

        with st.container():
            col_v, col_cat, col_due, col_days, col_amt, col_ov_input, col_del = st.columns([3, 1.5, 1.2, 1.2, 1.2, 1.8, 0.5])

            col_v.markdown(f"**{b['vendor']}**  \n<small style='color:#9e9990'>{b['desc'][:50]}</small>", unsafe_allow_html=True)
            col_cat.markdown(f"<span style='background:rgba(0,0,0,0.2);color:{cat_color};padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600'>{b['cat']}</span>", unsafe_allow_html=True)
            col_due.markdown(f"<small style='color:#9e9990'>Due</small>  \n**{fmt_date(b['due_date'])}**", unsafe_allow_html=True)
            col_days.markdown(
                f"<small style='color:#9e9990'>Days O/S</small>  \n"
                f"<span style='color:{'#d94f4f' if is_ov else '#9e9990'};font-weight:{'600' if is_ov else '400'}'>"
                f"{'🔴 +' + str(days_out) + 'd' if is_ov else ('✅ in ' + str(-days_out) + 'd' if days_out < 0 else 'Today')}</span>",
                unsafe_allow_html=True
            )
            col_amt.markdown(f"<small style='color:#9e9990'>Amount</small>  \n**{fmt(b['amount'])}**", unsafe_allow_html=True)

            # Override input
            new_override = col_ov_input.date_input(
                "Override",
                value=cur_ovr,
                key=f"ov_{b['id']}",
                label_visibility="collapsed",
                format="MM/DD/YYYY",
            )

            # Save if changed
            if new_override and new_override != cur_ovr:
                if save_override(b["inv"], b["vendor"], b["source"], new_override):
                    st.success(f"✓ Override saved for {b['vendor']} — moving to week of {new_override.strftime('%-m/%-d')}", icon="✅")
                    st.rerun()

            # Delete override
            if cur_ovr and col_del.button("✕", key=f"del_{b['id']}", help="Remove override"):
                delete_override(b["inv"])
                st.rerun()

            st.divider()
