import streamlit as st
from modules.downloader import download_all_companies

st.title("📥 Fintables Bilanço İndirici")

if st.button("🔽 Bilançoları İndir"):
    with st.spinner("İndiriliyor... Lütfen bekleyin."):
        download_all_companies()
    st.success("İndirme tamamlandı!")
