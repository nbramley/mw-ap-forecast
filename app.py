import streamlit as st

st.set_page_config(
    page_title="Mack Weldon — AP Forecast",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand styles ──────────────────────────────────────────────
st.markdown("""
<style>
  #MainMenu, header, footer { visibility: hidden; }
  .block-container { padding-top: 1.5rem; }
  section[data-testid="stSidebar"] {
    background: #0D1B2A !important;
    display: block !important;
    visibility: visible !important;
    min-width: 220px !important;
  }
  section[data-testid="stSidebar"] * { color: #d8d4cc !important; }
  section[data-testid="stSidebar"] .stRadio label { font-size: 13px !important; }
  button[data-testid="collapsedControl"] { display: none !important; }
  .mw-header {
    background: #0D1B2A; color: white; padding: 16px 24px;
    border-radius: 8px; margin-bottom: 20px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .mw-header h1 { font-size: 22px; margin: 0; color: white; }
  .mw-header .sub { font-size: 11px; color: #B8935A; letter-spacing: 0.12em; text-transform: uppercase; }
  .mw-badge { background: rgba(184,147,90,0.2); color: #B8935A; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar navigation ────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💼 MACK WELDON")
    st.markdown("#### AP Forecast")
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 AP Forecast", "📋 Weekly Bill Pay", "☰ Bill View",
         "⬡ Inventory Detail", "✎ Payment Terms"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#5a5550'>As of 3/30/2026<br>Wk 3/30 — Wk 5/4</small>",
        unsafe_allow_html=True
    )

# ── Route to pages ────────────────────────────────────────────
if page == "📊 AP Forecast":
    from pages_src.forecast import show
    show()
elif page == "📋 Weekly Bill Pay":
    from pages_src.weekly import show
    show()
elif page == "☰ Bill View":
    from pages_src.bills import show
    show()
elif page == "⬡ Inventory Detail":
    from pages_src.inventory import show
    show()
elif page == "✎ Payment Terms":
    from pages_src.terms import show
    show()
