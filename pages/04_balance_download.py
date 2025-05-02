#  pages/04_balance_download.py
import streamlit as st #type: ignore
from modules.downloader import update_companies_if_needed

st.title("📥 Fintables Bilanço İndirici")

st.markdown(
    """
    Bu sayfa, **data/son_bilancolar.json** dosyasındaki şirket kodlarını tarar,  
    _companies_ klasöründe güncel bilanço dosyası (**2025/3** dönemi) bulunmayan
    veya eski sürümü bulunan şirketlerin Excel dosyalarını Fintables’tan otomatik indirir
    ve ilgili klasöre kaydeder.
    """
)


# Mesajları tutacak liste
if "logs" not in st.session_state:
    st.session_state["logs"] = []

def streamlit_logger(msg: str):
    st.session_state.logs.append(msg)
    log_placeholder.markdown("  \n".join(st.session_state.logs))

if st.button("🔽 Bilançoları İndir"):
    st.session_state.logs = []          # eski logları temizle
    with st.spinner("İndiriliyor…"):
        with st.expander("⬇️ İşlem Günlüğü", expanded=True):
            log_placeholder = st.empty()
            update_companies_if_needed(log=streamlit_logger)  # ↓ retry’li fonksiyon
    st.success("İndirme tamamlandı.")
