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
  [data-testid="stSidebar"] {
    background-color: #0D1B2A !important;
    min-width: 200px !important;
  }
  [data-testid="stSidebarContent"] {
    background-color: #0D1B2A !important;
  }
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

with st.sidebar:
    st.markdown(
        "<div style='padding:16px 0 8px;'><span style='font-family:serif;font-size:16px;color:white;font-weight:600'>💼 MACK WELDON</span><br>"
        "<span style='font-size:10px;color:#B8935A;letter-spacing:0.12em'>AP FORECAST</span></div>",
        unsafe_allow_html=True
    )
    st.markdown("---")
    page = st.radio(
        "Navigate",
        ["📊 AP Forecast", "📋 Weekly Bill Pay", "⚡ Weekly Bill Pay Live",
         "☰ Bill View", "⬡ Inventory Detail", "✎ Payment Terms"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#5a5550;font-size:10px'>As of 3/30/2026<br>Wk 3/30 — Wk 5/4</small>",
        unsafe_allow_html=True
    )

if page == "📊 AP Forecast":
    from pages_src.forecast import show
    show()
elif page == "📋 Weekly Bill Pay":
    from pages_src.weekly import show
    show()
elif page == "⚡ Weekly Bill Pay Live":
    from pages_src.live import show
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
