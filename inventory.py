"""Weekly Bill Pay — current week invoice detail."""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data import fmt, monday_of

TODAY      = date(2026, 3, 30)
WEEK_START = monday_of(TODAY)
WEEK_END   = WEEK_START + timedelta(6)

REV_PAYOUT     = 700_181
REV_START      = WEEK_START - timedelta(3)
REV_END        = WEEK_START + timedelta(3)

WEEK_PAYMENTS = {
    "Auto ACH": [
        {"vendor": "JustWorks", "desc": "—", "amount": None, "note": "No payment this week"},
        {"vendor": "Ramp Credit Card", "desc": "—", "amount": None, "note": "No payment this week"},
    ],
    "Ramp — Priority Vendors": [
        {"vendor": "Google LLC",      "desc": "Google Ads advertising services",       "amount": 184642.80},
        {"vendor": "XB Fulfillment",  "desc": "Multiple invoices — facility wind-down","amount": 48375.10},
        {"vendor": "Alexander Adamov (Fit Modeling Services)", "desc": "Fitting services", "amount": 300.00},
        {"vendor": "SBH Plus, Inc",   "desc": "Temporary staffing",                   "amount": 1428.00},
    ],
    "Ramp — All Other Vendors": [
        {"vendor": "Ad Results Media, LLC",            "desc": "Broadcast media - Initiated",     "amount": 88751.14},
        {"vendor": "CBIZ CPAS P.C.",                   "desc": "Audit services",                 "amount": 21000.00},
        {"vendor": "Joanna Goddard, Inc.",             "desc": "Advertising services",            "amount": 20000.00},
        {"vendor": "GHP Media, Inc",                   "desc": "Retail signage",                 "amount": 17754.28},
        {"vendor": "Benjo Arwas Studio",               "desc": "Photography services",            "amount": 21322.75},
        {"vendor": "Nicholas Duers Photography LLC",   "desc": "Photography services",            "amount": 15862.71},
        {"vendor": "Agency Within LLC DBA Brkfst",     "desc": "Brkfst Ad Spend Fee Feb 2026",   "amount": 6180.14},
        {"vendor": "Rhg USA LLC",                      "desc": "Recycled LDPE bags",             "amount": 8954.20},
        {"vendor": "Imperial Dade",                    "desc": "Shipping boxes",                 "amount": 12427.43},
        {"vendor": "SGS North America Inc.",           "desc": "Lab testing services",           "amount": 4188.99},
        {"vendor": "Tucker & Latifi, LLP",             "desc": "Legal fees - trademark",         "amount": 5890.00},
        {"vendor": "Kensington Grey International Inc.","desc": "Influencer marketing",          "amount": 6000.00},
        {"vendor": "SUPREME SYSTEMS INC",              "desc": "Courier delivery services",      "amount": 1477.30},
    ],
    "Inventory Vendors": [
        {"vendor": "Athletic Apparel Group", "desc": "Invoice AAG20201", "amount": 64143.45},
        {"vendor": "The S Group",            "desc": "Invoice INV11055", "amount": 122.55},
    ],
}


def show():
    st.markdown(f"""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>Weekly Bill Pay</h1>
      </div>
      <div class="mw-badge">
        {WEEK_START.strftime('%-m/%-d')} — {WEEK_END.strftime('%-m/%-d/%Y')}
      </div>
    </div>
    """, unsafe_allow_html=True)

    grand_total = 0
    subtotals   = {}

    for category, items in WEEK_PAYMENTS.items():
        payable = [i for i in items if i.get("amount")]
        if not payable:
            continue

        st.markdown(f"#### {category}")

        rows = []
        for item in payable:
            rows.append({
                "Vendor":       item["vendor"],
                "Description":  item["desc"],
                "Amount":       fmt(item["amount"]),
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True,
                     height=min(35 * len(rows) + 38, 350))

        subtotal = sum(i["amount"] for i in payable)
        subtotals[category] = subtotal
        grand_total += subtotal

        col_l, col_r = st.columns([4, 1])
        col_l.markdown(f"*Subtotal — {category}*")
        col_r.markdown(f"**{fmt(subtotal)}**")
        st.markdown("---")

    # Grand Total
    st.markdown(
        f"""
        <div style="background:#0D1B2A;padding:16px 20px;border-radius:8px;
        display:flex;justify-content:space-between;align-items:center;margin-top:8px;">
          <span style="font-family:serif;font-size:20px;color:#B8935A;font-weight:600">
            GRAND TOTAL
          </span>
          <span style="font-family:monospace;font-size:22px;color:#B8935A;font-weight:700">
            {fmt(grand_total)}
          </span>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Revenue payout band
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div style="background:rgba(42,157,143,0.08);border:1px solid rgba(42,157,143,0.25);
        border-radius:8px;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-size:10px;color:#2a9d8f;text-transform:uppercase;letter-spacing:0.1em;font-weight:600">
              Estimated Revenue Payout
            </div>
            <div style="font-size:11px;color:#9e9990;font-family:monospace;margin-top:3px">
              92% discounted rev · {REV_START.strftime('%-m/%-d')}–{REV_END.strftime('%-m/%-d')}
            </div>
          </div>
          <div style="font-family:monospace;font-size:20px;color:#2a9d8f;font-weight:700">
            {fmt(REV_PAYOUT)}
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )
