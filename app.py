
import streamlit as st # type: ignore

st.set_page_config(page_title="FinSight Me", page_icon="💹", layout="wide")

# st.sidebar.page_link("pages/01_financial_radar.py", label="Bilanço Radar", icon="📊")
# st.sidebar.page_link("pages/02_stock_analysis.py", label="Tek Hisse Analizi", icon="📈")
# st.sidebar.page_link("pages/03_trap_radar.py", label="Değer Tuzakları Radarı", icon="🚨")

with st.sidebar:
    st.markdown("### 📊 Portfolio")
    st.page_link("pages/03_portfolio_dashboard.py", label="Portfolio Dashboard")
    st.page_link("pages/04_performance_log_update.py", label="Performance Log Update")

    st.markdown("### 🔍 Analysis Tools")
    st.page_link("pages/01_financial_radar.py", label="Financial Radar")
    st.page_link("pages/02_stock_analysis.py", label="Stock Analysis")

    st.markdown("### 📥 Data")
    st.page_link("pages/05_balance_download.py", label="Balance Download")

    st.markdown("### ⚙️ Developer")
    st.page_link("app.py", label="App")

st.title("FinSight Me")
st.markdown(
    '''
    Multi-page Streamlit app for analysing Borsa İstanbul companies.  
    Place your **Fintables** Excel exports in `data/companies/<TICKER>/<TICKER> (TRY).xlsx`  
    and pick a page from the sidebar to start exploring.
    '''
)
