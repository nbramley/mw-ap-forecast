"""AP Forecast — reads from Supabase bills table."""
import math
import os
from datetime import date, timedelta

import requests
import streamlit as st

from data import (INVENTORY_TERMS, JUSTWORKS_PAYROLL, JUSTWORKS_TAXES,
                  OTHER_WEEKLY, PRIORITY_TERMS, RAMP_CC_AMOUNT, SHIPPING_PCT,
                  adj_back, adj_fwd, fmt, monday_of, week_idx)


def get_week_starts(today: date) -> list:
    return [monday_of(today) + timedelta(weeks=i) for i in range(6)]


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


def parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(str(s)[:10])
    except:
        return None


def empty_bucket():
    return {"ov": 0.0, "wks": [0.0] * 6}


def add_to_bucket(b, amt, idx):
    if idx == -1:
        b["ov"] += amt
    elif isinstance(idx, int) and 0 <= idx < 6:
        b["wks"][idx] += amt


def show():
    st.markdown("""
    <div class="mw-header">
      <div>
        <div class="sub">MACK WELDON</div>
        <h1>AP Cash Flow Forecast — 6 Week</h1>
      </div>
      <div class="mw-badge">Live from Supabase</div>
    </div>
    """, unsafe_allow_html=True)

    today       = date(2026, 3, 31)
    week_starts = get_week_starts(today)
    week_labels = [f"Wk {ws.strftime('%-m/%-d')}" for ws in week_starts]
    overdue_lbl = "Overdue (Pay by 3/31)"

    # ── Load bills from Supabase ────────────────────────────────
    with st.spinner("Loading from Supabase..."):
        raw_bills = fetch_bills()

    # ── Fixed Must Pays ─────────────────────────────────────────
    must_pays = {}

    # JustWorks
    jw = empty_bucket()
    for d, amt in [
        (date(2026, 4, 6),  JUSTWORKS_TAXES),
        (date(2026, 4, 10), JUSTWORKS_PAYROLL),
        (date(2026, 4, 27), JUSTWORKS_PAYROLL),
        (date(2026, 5, 6),  JUSTWORKS_TAXES),
        (date(2026, 5, 11), JUSTWORKS_PAYROLL),
        (date(2026, 5, 26), JUSTWORKS_PAYROLL),
        (date(2026, 6, 8),  JUSTWORKS_TAXES),
        (date(2026, 6, 10), JUSTWORKS_PAYROLL),
        (date(2026, 6, 25), JUSTWORKS_PAYROLL),
    ]:
        add_to_bucket(jw, amt, week_idx(d, week_starts))
    must_pays["JustWorks"] = jw

    # Ramp CC
    rcc = empty_bucket()
    for m in range(1, 13):
        try:
            d = adj_fwd(date(today.year, m, 12))
            add_to_bucket(rcc, RAMP_CC_AMOUNT, week_idx(d, week_starts))
        except: pass
    must_pays["Ramp Credit Card"] = rcc

    # Customs — hardcoded for now (April = $50K based on prior data)
    cust = empty_bucket()
    for m, amt in [(4, 50000), (5, 50000)]:
        d = date(today.year, m, 23)
        add_to_bucket(cust, amt, week_idx(d, week_starts))
    must_pays["Customs & Duties"] = cust

    # Numeral — hardcoded estimate
    num = empty_bucket()
    num["wks"] = [35982, 71964, 35982, 0, 0, 0]
    must_pays["Numeral"] = num

    # Shipping — hardcoded estimate
    ship = empty_bucket()
    ship["wks"] = [50000, 50000, 50000, 50000, 50000, 50000]
    must_pays["Shipping"] = ship

    # Other
    oth = empty_bucket()
    oth["wks"] = [OTHER_WEEKLY] * 6
    must_pays["Other"] = oth

    # ── Parse bills from Supabase ───────────────────────────────
    INVENTORY_VENDOR_NAMES = set(INVENTORY_TERMS.keys())
    PRIORITY_VENDOR_NAMES  = set(PRIORITY_TERMS.keys())

    inv_buckets  = {}
    ramp_pri_buckets = {}
    ramp_std_buckets = {}

    for b in raw_bills:
        vendor = b.get("vendor", "")
        amount = float(b.get("amount") or 0)
        source = b.get("source", "")
        due    = parse_date(b.get("due_date"))
        if amount <= 0 or not due:
            continue

        if source == "NetSuite":
            days_extra = INVENTORY_TERMS.get(vendor, 0)
            pay_date = adj_back(due + timedelta(days=days_extra))
            idx = week_idx(pay_date, week_starts)
            if vendor not in inv_buckets:
                inv_buckets[vendor] = empty_bucket()
            add_to_bucket(inv_buckets[vendor], amount, idx)

        elif source == "Ramp":
            paid_status = (b.get("paid_status") or "").lower()
            if paid_status in ("paid", "initiated"):
                continue  # Already paid

            if vendor in PRIORITY_VENDOR_NAMES:
                days_extra = PRIORITY_TERMS.get(vendor, 0)
                if days_extra == "due":
                    pay_date = adj_back(due)
                elif isinstance(days_extra, int):
                    pay_date = adj_back(due + timedelta(days=days_extra))
                else:
                    pay_date = adj_back(due + timedelta(days=60))
                idx = week_idx(pay_date, week_starts)
                if vendor not in ramp_pri_buckets:
                    ramp_pri_buckets[vendor] = empty_bucket()
                add_to_bucket(ramp_pri_buckets[vendor], amount, idx)
            else:
                pay_date = adj_back(due + timedelta(days=60))
                idx = week_idx(pay_date, week_starts)
                if vendor not in ramp_std_buckets:
                    ramp_std_buckets[vendor] = empty_bucket()
                add_to_bucket(ramp_std_buckets[vendor], amount, idx)

    # Sort each section by 6-week total desc
    def sort_section(d):
        return dict(sorted(d.items(), key=lambda x: -(x[1]["ov"] + sum(x[1]["wks"]))))

    inv_buckets      = sort_section(inv_buckets)
    ramp_pri_buckets = sort_section(ramp_pri_buckets)
    ramp_std_buckets = sort_section(ramp_std_buckets)

    SECTIONS = {
        "Must Pays":              must_pays,
        "Inventory Vendors":      inv_buckets,
        "Ramp — Priority Vendors": ramp_pri_buckets,
        "Ramp — All Other Vendors": ramp_std_buckets,
    }

    # Grand totals
    grand_ov  = sum(v["ov"]    for sec in SECTIONS.values() for v in sec.values())
    grand_wks = [sum(v["wks"][i] for sec in SECTIONS.values() for v in sec.values()) for i in range(6)]

    # ── Stat cards ──────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("This Week",    fmt(grand_wks[0]))
    c2.metric("Overdue",      fmt(grand_ov))
    hi = max(grand_wks); hi_i = grand_wks.index(hi)
    c3.metric(f"Heaviest ({week_labels[hi_i]})", fmt(hi))
    c4.metric("6-Week Total", fmt(grand_ov + sum(grand_wks)))
    st.markdown("---")

    # ── HTML Table ──────────────────────────────────────────────
    all_cols = ["Vendor", overdue_lbl] + week_labels + ["Total"]

    def fv(v):
        return f"${v:,.0f}" if isinstance(v, (int, float)) and v > 0 else ""

    th = lambda c, i: (
        f'<th style="background:#0D1B2A;color:#B8935A;padding:8px 10px;'
        f'font-weight:600;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;'
        f'border-bottom:2px solid #B8935A;text-align:{"left" if i==0 else "right"};white-space:nowrap;">{c}</th>'
    )
    header = "".join(th(c, i) for i, c in enumerate(all_cols))
    body   = ""

    for sec_name, vendors in SECTIONS.items():
        if not vendors:
            body += f'<tr><td colspan="{len(all_cols)}" style="padding:9px 12px;color:#B8935A;font-weight:700;font-size:12px;letter-spacing:0.1em;background:rgba(184,147,90,0.15);border-top:1px solid rgba(184,147,90,0.4);">▸ {sec_name.upper()} — No bills found</td></tr>'
            continue

        body += f'<tr><td colspan="{len(all_cols)}" style="padding:9px 12px;color:#B8935A;font-weight:700;font-size:12px;letter-spacing:0.1em;background:rgba(184,147,90,0.15);border-top:1px solid rgba(184,147,90,0.4);">▸ {sec_name.upper()}</td></tr>'

        sec_ov, sec_wks = 0.0, [0.0]*6
        for vendor, bk in vendors.items():
            vals = [vendor, fv(bk["ov"])] + [fv(bk["wks"][i]) for i in range(6)] + [fv(bk["ov"]+sum(bk["wks"]))]
            body += '<tr style="border-bottom:1px solid rgba(255,255,255,0.04);">'
            for j, v in enumerate(vals):
                body += f'<td style="padding:6px 10px;text-align:{"left" if j==0 else "right"};color:#d8d4cc;font-size:13px;">{v}</td>'
            body += "</tr>"
            sec_ov += bk["ov"]
            for i in range(6): sec_wks[i] += bk["wks"][i]

        # Total row — bold
        tvs = [f"TOTAL — {sec_name.upper()}", fv(sec_ov)] + [fv(sec_wks[i]) for i in range(6)] + [fv(sec_ov+sum(sec_wks))]
        body += '<tr style="background:rgba(13,27,42,0.8);border-top:1px solid rgba(255,255,255,0.12);">'
        for j, v in enumerate(tvs):
            body += f'<td style="padding:8px 10px;text-align:{"left" if j==0 else "right"};color:#d8d4cc;font-weight:700;font-size:13px;">{v}</td>'
        body += f'</tr><tr><td colspan="{len(all_cols)}" style="height:10px;background:transparent;border:none;"></td></tr>'

    # Grand total
    gvs = ["🏁  GRAND TOTAL", fv(grand_ov)] + [fv(grand_wks[i]) for i in range(6)] + [fv(grand_ov+sum(grand_wks))]
    body += '<tr style="background:#0D1B2A;border-top:2px solid #B8935A;">'
    for j, v in enumerate(gvs):
        body += f'<td style="padding:12px 10px;text-align:{"left" if j==0 else "right"};color:#B8935A;font-weight:700;font-size:14px;">{v}</td>'
    body += "</tr>"

    st.markdown(f"""
    <div style="overflow-x:auto;border-radius:8px;border:1px solid rgba(255,255,255,0.08);">
    <table style="width:100%;border-collapse:collapse;font-family:-apple-system,sans-serif;">
    <thead><tr>{header}</tr></thead><tbody>{body}</tbody></table></div>
    """, unsafe_allow_html=True)

    # Refresh button
    st.markdown("---")
    if st.button("🔄 Refresh from Supabase"):
        st.cache_data.clear()
        st.rerun()
    st.caption(f"Data as of last weekly AP update · {len(raw_bills)} bills loaded")
