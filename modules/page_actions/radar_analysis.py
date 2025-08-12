# modules/page_actions/radar_analysis.py
import streamlit as st
import pandas as pd
from modules.scanner import run_scan
from modules.db.trend_scores import get_or_compute_today
from modules.db.core import save_dataframe

def run_radar_analysis_workflow(companies: list):
    """
    Temel ve teknik analizleri çalıştırır, sonuçları birleştirir ve veritabanına kaydeder.
    Streamlit arayüz elemanlarını (spinner, success, error) kullanarak ilerlemeyi gösterir.
    """
    try:
        # --- 1. Temel Analiz Skorlarını Hesapla ---
        with st.spinner("📊 Temel analiz skorları hesaplanıyor... (Bu işlem uzun sürebilir)"):
            df_fundamental, _, _ = run_scan(pd.DataFrame({'Şirket': companies})) # run_scan'e uygun df gönder
            st.success("✅ Temel analiz skorları başarıyla hesaplandı.")
            with st.expander("Hesaplanan Temel Skorlar (ilk 5 satır)"):
                st.dataframe(df_fundamental.head())

        # --- 2. Teknik Analiz Metriklerini Hesapla ---
        with st.spinner("📈 Güncel teknik metrikler ve fiyatlar hesaplanıyor..."):
            df_technical = get_or_compute_today(list(companies), force_refresh=True)
            st.success("✅ Teknik analiz metrikleri başarıyla hesaplandı.")
            with st.expander("Hesaplanan Teknik Metrikler (ilk 5 satır)"):
                st.dataframe(df_technical.head())

        # --- 3. İki Veri Setini Birleştir ---
        st.info("İki veri seti birleştiriliyor...")
        symbol_col = "hisse"
        df_merged = df_fundamental.merge(
            df_technical.rename(columns={"symbol": symbol_col}),
            on=symbol_col,
            how="left"
        )
        st.success("✅ Veriler başarıyla birleştirildi.")
        with st.expander("Birleştirilmiş Veri (ilk 5 satır)"):
            st.dataframe(df_merged.head())

        # --- 4. Birleşik Veriyi Veritabanına Kaydet ---
        with st.spinner("💾 Birleştirilmiş veriler `radar_scores` tablosuna kaydediliyor..."):
            save_dataframe(df_merged, table="radar_scores")
            st.success("🎉 Tüm veriler başarıyla veritabanına kaydedildi!")
            st.balloons()

    except Exception as e:
        st.error(f"İşlem sırasında bir hata oluştu: {e}")
        st.stop()