import streamlit as st

st.set_page_config(
    page_title="Mack Weldon — AP Forecast",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  #MainMenu, footer { visibility: hidden; }
  header { visibility: hidden; }
  .block-container { padding-top: 0.5rem; }

  /* Force sidebar always visible */
  [data-testid="stSidebar"] {
    background-color: #0D1B2A !important;
    min-width: 200px !important;
  }
  [data-testid="stSidebarContent"] {
    background-color: #0D1B2A !important;
  }
  /* Hide the X / collapse arrow entirely */
  [data-testid="stSidebar"] button,
  [data-testid="collapsedControl"] {
    display: none !important;
    visibility: hidden !important;
  }
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] span {
    color: #d8d4cc !important;
  }
  .mw-header {
    background: #0D1B2A; color: white;
    padding: 14px 20px; border-radius: 8px;
    margin-bottom: 16px;
    display: flex; justify-content: space-between; align-items: center;
  }
  .mw-header h1 { font-size: 20px; margin: 0; color: white; }
  .mw-header .sub { font-size: 10px; color: #B8935A; letter-spacing: 0.12em; text-transform: uppercase; }
  .mw-badge { background: rgba(184,147,90,0.2); color: #B8935A; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
</style>
""", unsafe_allow_html=True)

# Navigation using selectbox at top if sidebar fails
with st.sidebar:
    st.markdown(
        "<div style='padding:16px 0 8px;'><span style='font-family:serif;font-size:16px;color:white;font-weight:600'>💼 MACK WELDON</span><br>"
        "<span style='font-size:10px;color:#B8935A;letter-spacing:0.12em'>AP FORECAST</span></div>",
        unsafe_allow_html=True
    )
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 AP Forecast", "📋 Weekly Bill Pay", "☰ Bill View",
         "⬡ Inventory Detail", "✎ Payment Terms"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#5a5550;font-size:10px'>As of 3/30/2026<br>Wk 3/30 — Wk 5/4</small>",
        unsafe_allow_html=True
    )

# Fallback top nav if sidebar is hidden
st.markdown("<div style='margin-bottom:8px'>", unsafe_allow_html=True)
top_nav = st.selectbox(
    "📍 Navigate (use this if sidebar is hidden)",
    ["📊 AP Forecast", "📋 Weekly Bill Pay", "☰ Bill View", "⬡ Inventory Detail", "✎ Payment Terms"],
    key="top_nav"
)
st.markdown("</div>", unsafe_allow_html=True)

# Use whichever nav the user picks
active_page = page if page else top_nav

if active_page == "📊 AP Forecast":
    from pages_src.forecast import show
    show()
elif active_page == "📋 Weekly Bill Pay":
    from pages_src.weekly import show
    show()
elif active_page == "☰ Bill View":
    from pages_src.bills import show
    show()
elif active_page == "⬡ Inventory Detail":
    from pages_src.inventory import show
    show()
elif active_page == "✎ Payment Terms":
    from pages_src.terms import show
    show()
