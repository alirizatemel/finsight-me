import streamlit as st # type: ignore
from modules.finance.downloader import update_companies_if_needed

def run_balance_download_workflow():
    """
    Fintables'tan bilanço dosyalarını indirir.
    Streamlit arayüzü üzerinden loglama yapar.
    """
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    
    st.session_state.logs = [] # Her çalıştırmada logları temizle

    def streamlit_logger(msg: str):
        st.session_state.logs.append(msg)
        # Placeholder'a yazma işi ana sayfada yapılacak.
        # Bu fonksiyon sadece logları toplar.

    with st.spinner("İndirme işlemi sürüyor..."):
        with st.expander("⬇️ İşlem Günlüğü", expanded=True):
            log_placeholder = st.empty()
            
            # Logger'ın anlık olarak yazabilmesi için placeholder'ı parametre olarak alması gerekir.
            def logger_with_placeholder(msg: str):
                st.session_state.logs.append(msg)
                log_placeholder.markdown("  \n".join(st.session_state.logs))

            update_companies_if_needed(log=logger_with_placeholder)
    
    st.success("✅ İndirme işlemi başarıyla tamamlandı.")