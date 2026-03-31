"""
data.py — shared data, payment terms, and calculation logic.
"""
import math, os
from datetime import date, timedelta
import requests
import streamlit as st

INVENTORY_TERMS = {
    "Triple A Apparel LTD": 5, "Konc": 15, "Lever Style Limited": 15,
    "Athletic Apparel Group": 30, "Primotex Textiles International Limited": 30,
    "American Phil Textiles Limited": 60, "Delta Galil Industries Ltd.": 60, "The S Group": 60,
}
PRIORITY_TERMS = {
    "Kristina Boiano": 0, "R&A Engineering LLC": 5,
    "Alexander Adamov (Fit Modeling Services)": 15, "Barrel LLC": 15, "SBH Plus, Inc": 15,
    "ERY Retail Podium LLC": 25, "Fin Technologies dba Alkami Technology, Inc": 25,
    "Madeleine Lachesnez": 30, "Oracle America Inc.": 30, "STUDIO TAVISH TIMOTHY LLC": 30,
    "Nick Pichaiwongse": 45, "Google LLC": "google", "XB Fulfillment": "xb",
}
XB_WEEK=date(2026,3,30); RAMP_CC_AMOUNT=150_000; JUSTWORKS_TAXES=32_624
JUSTWORKS_PAYROLL=184_962; REVENUE_PAYOUT_PCT=0.92; SHIPPING_PCT=0.06; OTHER_WEEKLY=20_000

def monday_of(d):
    return d - timedelta(days=d.weekday())
def adj_back(d):
    if d.weekday()==5: return d-timedelta(1)
    if d.weekday()==6: return d-timedelta(2)
    return d
def adj_fwd(d):
    if d.weekday()==5: return d+timedelta(2)
    if d.weekday()==6: return d+timedelta(1)
    return d
def week_idx(d, week_starts):
    for i,ws in enumerate(week_starts):
        if ws<=d<=ws+timedelta(6): return i
    return -1 if d<week_starts[0] else None
def google_pay_date(due):
    first=date(due.year,due.month,1)
    fm=first if first.weekday()==0 else first+timedelta((7-first.weekday())%7)
    wk4=fm+timedelta(21); d15=date(due.year,due.month,15); m15=d15-timedelta(d15.weekday())
    if due>=wk4:
        nm=(due.month%12)+1; ny=due.year+(1 if due.month==12 else 0)
        d15n=date(ny,nm,15); return d15n-timedelta(d15n.weekday())
    return m15
def parse_d(s):
    if not s: return None
    try: return date.fromisoformat(str(s)[:10])
    except: return None
def parse_excel_date(val):
    if val is None or (isinstance(val,float) and math.isnan(val)): return None
    if isinstance(val,(int,float)): return date(1899,12,30)+timedelta(days=int(val))
    if hasattr(val,"date"): return val.date()
    return None
def ramp_pay_date(payee,status,due,week_starts):
    s=(status or "").upper().replace(" ","_")
    if s=="INITIATED": return week_starts[0]
    if payee in PRIORITY_TERMS:
        t=PRIORITY_TERMS[payee]
        if t=="xb": return XB_WEEK
        if t=="google":
            if s=="READY_FOR_PAYMENT": return week_starts[0]
            return google_pay_date(due) if due else week_starts[0]
        pay=(due+timedelta(t)) if due else week_starts[0]
        return adj_back(pay)
    if s=="SCHEDULED": return adj_back(due) if due else week_starts[0]
    pay=(due+timedelta(60)) if due else week_starts[0]
    return adj_back(pay)

def _supabase_headers():
    key=st.secrets.get("SUPABASE_KEY","") or os.environ.get("SUPABASE_KEY","")
    return {"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}
def _supabase_url():
    return st.secrets.get("SUPABASE_URL","") or os.environ.get("SUPABASE_URL","")

@st.cache_data(ttl=300)
def fetch_overrides():
    url=_supabase_url()
    if not url: return {}
    try:
        resp=requests.get(f"{url}/rest/v1/bill_payment_overrides",
            headers=_supabase_headers(),params={"select":"bill_id,override_date"},timeout=15)
        resp.raise_for_status()
        return {r["bill_id"]:parse_d(r["override_date"]) for r in resp.json() if r.get("override_date")}
    except Exception as e:
        st.warning(f"Could not load overrides: {e}"); return {}

def save_override(bill_id,vendor,source,override_date,note=""):
    url=_supabase_url()
    if not url: st.error("Supabase not configured."); return False
    try:
        resp=requests.post(f"{url}/rest/v1/bill_payment_overrides",
            headers={**_supabase_headers(),"Prefer":"resolution=merge-duplicates"},
            json=[{"bill_id":bill_id,"vendor":vendor,"source":source,
                   "override_date":str(override_date),"note":note}],timeout=15)
        resp.raise_for_status(); st.cache_data.clear(); return True
    except Exception as e:
        st.error(f"Could not save override: {e}"); return False

def delete_override(bill_id):
    url=_supabase_url()
    if not url: return
    try:
        requests.delete(f"{url}/rest/v1/bill_payment_overrides",
            headers=_supabase_headers(),params={"bill_id":f"eq.{bill_id}"},timeout=15)
        st.cache_data.clear()
    except: pass

def fmt(n):
    return f"${n:,.0f}" if n else "—"
def fmt_date(d):
    if not d: return "—"
    if isinstance(d,str): d=parse_d(d)
    return d.strftime("%-m/%-d") if d else "—"
def fmt_date_full(d):
    if not d: return "—"
    if isinstance(d,str): d=parse_d(d)
    return d.strftime("%b %d, %Y") if d else "—"
