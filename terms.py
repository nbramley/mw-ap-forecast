"""Inventory Bill Detail — all outstanding inventory invoices."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data import INVENTORY_TERMS, adj_back, fetch_overrides, fmt, fmt_date, monday_of

TODAY = date(2026, 3, 30)

# Demo data — in production this comes from NetSuite/QuickBooks
DEMO_INVOICES = [
    {"vendor":"American Phil Textiles Limited","invoice":"APT10051","inv_date":"2025-10-21","due_date":"2025-11-30","amount":48697.60,"terms_days":60},
    {"vendor":"American Phil Textiles Limited","invoice":"APT10101","inv_date":"2025-11-18","due_date":"2025-12-31","amount":99011.20,"terms_days":60},
    {"vendor":"American Phil Textiles Limited","invoice":"APT10136","inv_date":"2025-12-12","due_date":"2026-01-20","amount":88848.40,"terms_days":60},
    {"vendor":"American Phil Textiles Limited","invoice":"APT10202","inv_date":"2026-01-20","due_date":"2026-02-28","amount":62772.58,"terms_days":60},
    {"vendor":"American Phil Textiles Limited","invoice":"APT10249","inv_date":"2026-02-03","due_date":"2026-03-14","amount":50103.60,"terms_days":60},
    {"vendor":"American Phil Textiles Limited","invoice":"APT10289","inv_date":"2026-02-14","due_date":"2026-03-24","amount":26368.60,"terms_days":60},
    {"vendor":"Athletic Apparel Group","invoice":"AAG20114","inv_date":"2025-11-15","due_date":"2025-12-15","amount":19282.50,"terms_days":30},
    {"vendor":"Athletic Apparel Group","invoice":"AAG20156","inv_date":"2025-12-01","due_date":"2026-01-05","amount":10234.08,"terms_days":30},
    {"vendor":"Athletic Apparel Group","invoice":"AAG20201","inv_date":"2026-01-05","due_date":"2026-03-01","amount":64143.45,"terms_days":30},
    {"vendor":"Athletic Apparel Group","invoice":"AAG20245","inv_date":"2026-01-20","due_date":"2026-03-14","amount":5806.46,"terms_days":30},
    {"vendor":"Delta Galil Industries Ltd.","invoice":"DG-2025-4412","inv_date":"2025-10-01","due_date":"2025-11-15","amount":89432.10,"terms_days":60},
    {"vendor":"Delta Galil Industries Ltd.","invoice":"DG-2025-4489","inv_date":"2025-10-20","due_date":"2025-12-04","amount":72348.23,"terms_days":60},
    {"vendor":"Delta Galil Industries Ltd.","invoice":"DG-2026-4501","inv_date":"2025-12-01","due_date":"2026-01-15","amount":83212.45,"terms_days":60},
    {"vendor":"Delta Galil Industries Ltd.","invoice":"DG-2026-4567","inv_date":"2025-12-15","due_date":"2026-02-07","amount":145780.45,"terms_days":60},
    {"vendor":"Delta Galil Industries Ltd.","invoice":"DG-2026-4601","inv_date":"2026-01-10","due_date":"2026-02-24","amount":100875.22,"terms_days":60},
    {"vendor":"Delta Galil Industries Ltd.","invoice":"DG-2026-4644","inv_date":"2026-01-28","due_date":"2026-03-14","amount":136337.12,"terms_days":60},
    {"vendor":"Konc","invoice":"KONC-1041","inv_date":"2026-01-15","due_date":"2026-03-09","amount":29344.10,"terms_days":15},
    {"vendor":"Konc","invoice":"KONC-1058","inv_date":"2026-02-01","due_date":"2026-04-10","amount":15869.90,"terms_days":15},
    {"vendor":"The S Group","invoice":"INV10815","inv_date":"2025-12-01","due_date":"2025-12-31","amount":12284.23,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10842","inv_date":"2025-12-08","due_date":"2026-01-07","amount":18924.15,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10867","inv_date":"2025-12-14","due_date":"2026-01-13","amount":15234.78,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10891","inv_date":"2025-12-19","due_date":"2026-01-18","amount":22104.56,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10920","inv_date":"2025-12-28","due_date":"2026-01-27","amount":19847.32,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10944","inv_date":"2026-01-04","due_date":"2026-02-03","amount":21560.44,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10971","inv_date":"2026-01-10","due_date":"2026-02-09","amount":16782.91,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV10998","inv_date":"2026-01-17","due_date":"2026-02-16","amount":28341.67,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11055","inv_date":"2026-01-30","due_date":"2026-02-28","amount":122.55,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11078","inv_date":"2026-02-05","due_date":"2026-03-07","amount":24891.22,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11105","inv_date":"2026-02-11","due_date":"2026-03-12","amount":31204.56,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11134","inv_date":"2026-02-18","due_date":"2026-03-19","amount":18749.33,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11162","inv_date":"2026-02-24","due_date":"2026-03-25","amount":5051.12,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11188","inv_date":"2026-03-02","due_date":"2026-04-01","amount":42108.44,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11214","inv_date":"2026-03-10","due_date":"2026-04-09","amount":38921.17,"terms_days":60},
    {"vendor":"The S Group","invoice":"INV11240","inv_date":"2026-03-17","due_date":"2026-04-16","amount":83042.27,"terms_days":60},
    {"vendor":"Triple A Apparel LTD","invoice":"TA260014","inv_date":"2026-01-16","due_date":"2026-03-10","amount":25274.00,"terms_days":5},
    {"vendor":"Triple A Apparel LTD","invoice":"TA260054","inv_date":"2026-01-31","due_date":"2026-03-01","amount":69826.42,"terms_days":5},
    {"vendor":"Triple A Apparel LTD","invoice":"TA260091","inv_date":"2026-02-14","due_date":"2026-04-08","amount":102154.05,"terms_days":5},
    {"vendor":"Triple A Apparel LTD","invoice":"TA260102","inv_date":"2026-01-16","due_date":"2026-03-17","amount":432.12,"terms_days":5},
]


def show():
    st.markdown("""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>Inventory Bill Detail</h1>
      </div>
    </div>
    """, unsafe_allow_html=True)

    week_starts = [monday_of(TODAY) + timedelta(weeks=i) for i in range(6)]
    overrides   = fetch_overrides()

    # Build enriched invoice list
    invoices = []
    for row in DEMO_INVOICES:
        due  = date.fromisoformat(row["due_date"])
        pay  = adj_back(due + timedelta(row["terms_days"]))
        eff  = overrides.get(row["invoice"], pay)
        days_out = (TODAY - due).days
        is_ov    = pay < week_starts[0]
        invoices.append({**row,
            "due":      due,
            "pay":      pay,
            "eff":      eff,
            "days_out": days_out,
            "is_ov":    is_ov,
            "pay_month": pay.strftime("%B %Y"),
        })

    # Stat cards
    total_amt  = sum(i["amount"] for i in invoices)
    ov_amt     = sum(i["amount"] for i in invoices if i["is_ov"])
    ov_count   = sum(1 for i in invoices if i["is_ov"])
    vendors    = list(dict.fromkeys(i["vendor"] for i in invoices))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Outstanding", fmt(total_amt), f"{len(invoices)} invoices")
    c2.metric("Overdue Amount", fmt(ov_amt), f"{ov_count} invoices past due")
    c3.metric("Active Vendors", str(len(vendors)))
    beyond = sum(i["amount"] for i in invoices if not i["is_ov"] and i["pay"] > week_starts[5] + timedelta(6))
    c4.metric("Beyond 6 Weeks", fmt(beyond))

    st.markdown("---")

    # Filters
    col_f1, col_f2 = st.columns([2, 4])
    selected_vendor = col_f1.selectbox("Filter by vendor", ["All vendors"] + vendors)
    show_overdue_only = col_f2.checkbox("Show overdue only", value=False)

    filtered = [i for i in invoices
                if (selected_vendor == "All vendors" or i["vendor"] == selected_vendor)
                and (not show_overdue_only or i["is_ov"])]

    st.markdown("---")

    # Group by vendor
    current_vendors = list(dict.fromkeys(i["vendor"] for i in filtered))
    colors = ["#B8935A", "#162436"]

    for vi, vendor in enumerate(current_vendors):
        vinv   = [i for i in filtered if i["vendor"] == vendor]
        vtotal = sum(i["amount"] for i in vinv)
        vov    = sum(i["amount"] for i in vinv if i["is_ov"])
        bg     = colors[vi % 2]

        st.markdown(
            f'<div style="background:{bg};padding:10px 16px;border-radius:6px 6px 0 0;'
            f'display:flex;justify-content:space-between;align-items:center;">'
            f'<span style="font-family:serif;font-size:16px;color:white;font-weight:600">{vendor}</span>'
            f'<span style="font-size:11px;color:rgba(255,255,255,0.7);font-family:monospace">'
            f'{len(vinv)} invoices · {fmt(vtotal)}'
            f'{f" · <span style=color:#ff9999>{fmt(vov)} overdue</span>" if vov > 0 else ""}'
            f'</span></div>',
            unsafe_allow_html=True
        )

        # Build table
        table_rows = []
        for inv in sorted(vinv, key=lambda x: x["due"]):
            days_str = (f"+{inv['days_out']}d ⚠️" if inv["days_out"] > 0
                        else ("Today" if inv["days_out"] == 0
                              else f"{-inv['days_out']}d away"))
            table_rows.append({
                "Invoice #":       inv["invoice"],
                "Invoice Date":    fmt_date(inv["inv_date"]),
                "Due Date":        fmt_date(inv["due_date"]),
                "Amount":          fmt(inv["amount"]),
                "Days O/S":        days_str,
                "Est. Pay Date":   fmt_date(inv["pay"]),
                "Pay Month":       inv["pay_month"],
                "Status":          "🔴 Overdue" if inv["is_ov"] else "✅ On track",
            })

        df = pd.DataFrame(table_rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=min(35 * len(table_rows) + 38, 400))
        st.markdown(
            f'<div style="border:1px solid rgba(255,255,255,0.06);border-top:none;'
            f'border-radius:0 0 6px 6px;padding:6px 16px;font-size:11px;color:#9e9990;">'
            f'Subtotal: {fmt(vtotal)}</div>',
            unsafe_allow_html=True
        )
        st.markdown("<br>", unsafe_allow_html=True)
