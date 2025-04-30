
import streamlit as st

st.set_page_config(page_title="FinSight Me", page_icon="💹", layout="wide")

st.sidebar.page_link("pages/01_financial_radar.py", label="Bilanço Radar", icon="📊")
st.sidebar.page_link("pages/02_stock_analysis.py", label="Tek Hisse Analizi", icon="📈")
st.sidebar.page_link("pages/03_trap_radar.py", label="Değer Tuzakları Radarı", icon="🚨")

st.title("FinSight Me")
st.markdown(
    '''
    Multi‑page Streamlit app for analysing Borsa İstanbul companies.  
    Place your **Fintables** Excel exports in `companies/<TICKER>/<TICKER> (TRY).xlsx`  
    and pick a page from the sidebar to start exploring.
    '''
)
