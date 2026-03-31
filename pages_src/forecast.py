"""AP Forecast — 6-week grid view."""
import math
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from data import (INVENTORY_TERMS, JUSTWORKS_PAYROLL, JUSTWORKS_TAXES,
                  OTHER_WEEKLY, PRIORITY_TERMS, RAMP_CC_AMOUNT,
                  REVENUE_PAYOUT_PCT, SHIPPING_PCT, adj_back, adj_fwd,
                  fetch_overrides, fetch_ramp_bills, fmt, fmt_date,
                  monday_of, parse_d, parse_excel_date, parse_ramp_bill,
                  ramp_pay_date, week_idx)


def get_week_starts(today: date) -> list:
    return [monday_of(today) + timedelta(weeks=i) for i in range(6)]


def empty_bucket():
    return {"ov": 0.0, "wks": [0.0] * 6}


def add(b, amt, idx, auto_debit=False):
    if idx == -1:
        if not auto_debit:
            b["ov"] += amt
    elif isinstance(idx, int) and 0 <= idx < 6:
        b["wks"][idx] += amt


def calc_must_pays(xl_path, today, week_starts):
    result = {}

    # JustWorks
    jw_sched = [
        (date(2026, 4, 6), JUSTWORKS_TAXES),
        (date(2026, 4, 10), JUSTWORKS_PAYROLL),
        (date(2026, 4, 27), JUSTWORKS_PAYROLL),
        (date(2026, 5, 6), JUSTWORKS_TAXES),
        (date(2026, 5, 11), JUSTWORKS_PAYROLL),
        (date(2026, 5, 26), JUSTWORKS_PAYROLL),
        (date(2026, 6, 8), JUSTWORKS_TAXES),
        (date(2026, 6, 10), JUSTWORKS_PAYROLL),
        (date(2026, 6, 25), JUSTWORKS_PAYROLL),
        (date(2026, 7, 6), JUSTWORKS_TAXES),
        (date(2026, 7, 10), JUSTWORKS_PAYROLL),
        (date(2026, 7, 27), JUSTWORKS_PAYROLL),
        (date(2026, 8, 6), JUSTWORKS_TAXES),
        (date(2026, 8, 10), JUSTWORKS_PAYROLL),
        (date(2026, 8, 25), JUSTWORKS_PAYROLL),
        (date(2026, 9, 8), JUSTWORKS_TAXES),
        (date(2026, 9, 10), JUSTWORKS_PAYROLL),
        (date(2026, 9, 25), JUSTWORKS_PAYROLL),
    ]
    b = empty_bucket()
    for d, amt in jw_sched:
        add(b, amt, week_idx(d, week_starts))
    result["JustWorks"] = b

    # Ramp CC — auto-debit, never overdue
    b = empty_bucket()
    for m in range(1, 13):
        try:
            d = adj_fwd(date(today.year, m, 12))
            add(b, RAMP_CC_AMOUNT, week_idx(d, week_starts), auto_debit=True)
        except ValueError:
            pass
    result["Ramp Credit Card"] = b

    # Customs — auto-debit, never overdue
    import pandas as _pd
    MONTH_MAP = {"january": 1, "february": 2, "march": 3, "april": 4,
                 "may": 5, "june": 6, "july": 7, "august": 8,
                 "september": 9, "october": 10, "november": 11, "december": 12}
    b = empty_bucket()
    try:
        df_c = _pd.read_excel(xl_path, sheet_name="Customs", header=2)
        df_c.columns = ["_", "Month", "Amount", "Type"]
        for _, row in df_c[_pd.notna(df_c["Month"])].iterrows():
            mn = MONTH_MAP.get(str(row["Month"]).strip().lower())
            if not mn: continue
            d = date(today.year, mn, 23)
            add(b, float(row["Amount"]), week_idx(d, week_starts), auto_debit=True)
    except Exception:
        pass
    result["Customs & Duties"] = b

    # Revenue & Numeral
    df_rev = _pd.DataFrame()
    try:
        df_rev_raw = _pd.read_excel(xl_path, sheet_name="Revenue", header=None)
        rev_data = []
        for _, row in df_rev_raw.iterrows():
            d, v = row[1], row[5]
            if _pd.notna(d) and _pd.notna(v) and isinstance(v, (int, float)):
                try:
                    rev_data.append({"date": _pd.to_datetime(d).date(), "rev": float(v)})
                except Exception:
                    pass
        df_rev = _pd.DataFrame(rev_data)
    except Exception:
        pass

    # Numeral — auto-debit
    b = empty_bucket()
    try:
        df_num = _pd.read_excel(xl_path, sheet_name="Numeral", header=0)
        df_num.columns = ["Filing ID", "Time period", "Jurisdiction", "Type",
                          "Status", "Date filed", "Taxable sales", "Non-taxable sales",
                          "Tax collected", "Tax due", "Interest", "Penalty", "State discount"]
        df_num["date_filed"] = df_num["Date filed"].apply(parse_excel_date)
        df_num["Tax due"] = _pd.to_numeric(df_num["Tax due"], errors="coerce").fillna(0)
        for _, row in df_num.iterrows():
            if row["Status"] == "Filed" and row["date_filed"]:
                pay = adj_back(row["date_filed"] + timedelta(1))
                add(b, row["Tax due"], week_idx(pay, week_starts), auto_debit=True)
            elif str(row["Status"]).lower() == "approved to file" and not row["date_filed"]:
                add(b, row["Tax due"], week_idx(week_starts[0], week_starts), auto_debit=True)
        # Next month: 5% of current month rev
        if not df_rev.empty:
            cur_rev = df_rev[df_rev["date"].apply(
                lambda d: d.month == today.month and d.year == today.year)]["rev"].sum()
            next_num = cur_rev * 0.05
            for ws, pct in [(week_starts[0], 0.25), (week_starts[1], 0.50), (week_starts[2], 0.25)]:
                add(b, next_num * pct, week_idx(ws, week_starts), auto_debit=True)
    except Exception:
        pass
    result["Numeral"] = b

    # Shipping
    b = empty_bucket()
    if not df_rev.empty:
        raw = [0.0] * 6
        for _, row in df_rev.iterrows():
            idx = week_idx(row["date"], week_starts)
            if isinstance(idx, int) and 0 <= idx < 6:
                raw[idx] += row["rev"] * SHIPPING_PCT
        b["wks"] = [math.ceil(v / 10_000) * 10_000 for v in raw]
    result["Shipping"] = b

    # Other
    b = empty_bucket()
    b["wks"] = [OTHER_WEEKLY] * 6
    result["Other"] = b

    return result, df_rev


def show():
    st.markdown("""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>AP Cash Flow Forecast — 6 Week</h1>
      </div>
      <div class="mw-badge">Week of 3/30/2026</div>
    </div>
    """, unsafe_allow_html=True)

    today = date(2026, 3, 30)
    week_starts = get_week_starts(today)
    week_labels = [f"Wk {ws.strftime('%-m/%-d')}" for ws in week_starts]
    overdue_label = "Overdue\n(Pay by 3/31)"

    overrides = fetch_overrides()

    # ── Use demo data since no input file in app yet ────────
    # In production, user uploads the weekly file or it pulls from NetSuite
    DEMO_SECTIONS = {
        "Must Pays": {
            "JustWorks":        {"ov": 0,      "wks": [0, 217586, 0, 0, 184962, 32624]},
            "Ramp Credit Card": {"ov": 0,      "wks": [0, 0, 150000, 0, 0, 0]},
            "Customs & Duties": {"ov": 0,      "wks": [0, 0, 0, 50000, 0, 0]},
            "Numeral":          {"ov": 0,      "wks": [35982, 71964, 35982, 0, 0, 0]},
            "Shipping":         {"ov": 0,      "wks": [50000, 50000, 50000, 50000, 50000, 50000]},
            "Other":            {"ov": 0,      "wks": [20000, 20000, 20000, 20000, 20000, 20000]},
        },
        "Inventory Vendors": {
            "The S Group":                    {"ov": 199403, "wks": [123, 0, 0, 21571, 5051, 83042]},
            "Delta Galil Industries Ltd.":    {"ov": 0,      "wks": [0, 145780, 0, 0, 136337, 0]},
            "Triple A Apparel LTD":           {"ov": 95533,  "wks": [0, 0, 102154, 0, 0, 0]},
            "American Phil Textiles Limited": {"ov": 77691,  "wks": [0, 62773, 50104, 0, 0, 0]},
            "Athletic Apparel Group":         {"ov": 40126,  "wks": [64143, 0, 5806, 0, 0, 0]},
            "Konc":                           {"ov": 0,      "wks": [0, 0, 0, 25870, 0, 0]},
        },
        "Ramp — Priority Vendors": {
            "Google LLC":                                 {"ov": 0,     "wks": [184643, 0, 0, 0, 0, 0]},
            "XB Fulfillment":                             {"ov": 0,     "wks": [48375, 0, 0, 0, 0, 0]},
            "Barrel LLC":                                 {"ov": 0,     "wks": [0, 0, 37500, 0, 0, 0]},
            "Fin Technologies dba Alkami Technology, Inc":{"ov": 17208, "wks": [0, 0, 0, 17040, 0, 0]},
            "Oracle America Inc.":                        {"ov": 13087, "wks": [0, 0, 0, 0, 13087, 0]},
            "R&A Engineering LLC":                        {"ov": 0,     "wks": [0, 0, 0, 8000, 0, 0]},
        },
        "Ramp — All Other Vendors": {
            "Ad Results Media, LLC":       {"ov": 0,     "wks": [88751, 0, 0, 0, 0, 89698]},
            "CBIZ CPAS P.C.":             {"ov": 73500, "wks": [0, 0, 0, 0, 0, 0]},
            "Rakuten Marketing LLC":       {"ov": 40503, "wks": [0, 0, 0, 0, 0, 0]},
            "Nicholas Duers Photography":  {"ov": 15863, "wks": [0, 0, 0, 0, 0, 0]},
            "Agency Within LLC DBA Brkfst":{"ov": 15499, "wks": [6180, 0, 0, 0, 0, 0]},
            "Benjo Arwas Studio":          {"ov": 21323, "wks": [0, 0, 0, 0, 0, 0]},
            "SGS North America Inc.":      {"ov": 0,     "wks": [4189, 0, 0, 5575, 0, 0]},
        },
    }

    REV_PAYOUTS = [700181, 713801, 713801, 713801, 714413, 668668]

    # Compute grand totals
    grand_ov = sum(v["ov"] for sec in DEMO_SECTIONS.values() for v in sec.values())
    grand_wks = [
        sum(v["wks"][i] for sec in DEMO_SECTIONS.values() for v in sec.values())
        for i in range(6)
    ]

    # ── Stat cards ────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("This Week", fmt(grand_wks[0]), delta=None)
    with col2:
        st.metric("Overdue", fmt(grand_ov))
    with col3:
        heaviest = max(grand_wks)
        heaviest_idx = grand_wks.index(heaviest)
        st.metric(f"Heaviest Week ({week_labels[heaviest_idx]})", fmt(heaviest))
    with col4:
        st.metric("Est. Rev Payout (Wk 1)", fmt(REV_PAYOUTS[0]))

    st.markdown("---")

    # ── Build forecast table ──────────────────────────────────
    columns = ["Vendor", overdue_label] + week_labels + ["Total"]
    rows = []

    for section_name, vendors in DEMO_SECTIONS.items():
        # Section header row
        rows.append({
            "Vendor": f"▸  {section_name.upper()}",
            **{overdue_label: ""},
            **{w: "" for w in week_labels},
            "Total": ""
        })

        sec_ov, sec_wks = 0, [0.0] * 6
        for vendor, b in vendors.items():
            row = {"Vendor": vendor}
            row[overdue_label] = b["ov"] if b["ov"] else None
            for i, w in enumerate(week_labels):
                row[w] = b["wks"][i] if b["wks"][i] else None
            row["Total"] = b["ov"] + sum(b["wks"])
            rows.append(row)
            sec_ov += b["ov"]
            for i in range(6): sec_wks[i] += b["wks"][i]

        # Section total
        tot_row = {"Vendor": f"TOTAL — {section_name.upper()}"}
        tot_row[overdue_label] = sec_ov if sec_ov else None
        for i, w in enumerate(week_labels):
            tot_row[w] = sec_wks[i] if sec_wks[i] else None
        tot_row["Total"] = sec_ov + sum(sec_wks)
        rows.append(tot_row)
        rows.append({c: "" for c in columns})  # spacer

    # Grand total row
    gt = {"Vendor": "🏁  GRAND TOTAL"}
    gt[overdue_label] = grand_ov if grand_ov else None
    for i, w in enumerate(week_labels):
        gt[w] = grand_wks[i] if grand_wks[i] else None
    gt["Total"] = grand_ov + sum(grand_wks)
    rows.append(gt)

    df = pd.DataFrame(rows, columns=columns)

    # Format currency columns
    currency_cols = [overdue_label] + week_labels + ["Total"]
    for col in currency_cols:
        df[col] = df[col].apply(
            lambda x: f"${x:,.0f}" if isinstance(x, (int, float)) and x > 0 else ("" if not x else x)
        )

    st.dataframe(df, use_container_width=True, height=680, hide_index=True)

    # ── Revenue payout rows ───────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📈 Estimated Revenue Payouts")
    st.caption("92% of discounted revenue · Revenue window = week dates −3 days")

    rev_cols = st.columns(6)
    for i, (col, payout, label) in enumerate(zip(rev_cols, REV_PAYOUTS, week_labels)):
        with col:
            net = grand_wks[i] - payout
            st.metric(
                label=label,
                value=fmt(payout),
                delta=f"Net: {fmt(net)}",
                delta_color="normal" if net >= 0 else "inverse"
            )
