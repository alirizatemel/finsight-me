import streamlit as st
import pandas as pd
from config import RADAR_XLSX
from modules.scanner import run_scan
from modules.db.trend_scores import get_or_compute_today
from modules.db.core import save_dataframe

st.set_page_config(layout="wide")
st.title("⚙️ Analiz ve Veri Güncelleme")

st.info(
    "Bu sayfa, temel ve teknik analiz skorlarını hesaplar ve sonuçları veritabanına kaydeder. \n\n"
    "Bu işlem, şirket sayısına bağlı olarak birkaç dakika sürebilir."
)

# Radar dosyasından şirket listesini al
try:
    df_radar = pd.read_excel(RADAR_XLSX)
    df_radar["Şirket"] = df_radar["Şirket"].str.strip()
    companies = df_radar["Şirket"].dropna().unique()
    st.markdown(f"**Analiz edilecek şirket sayısı:** `{len(companies)}`")
except Exception as e:
    st.error(f"Radar dosyası okunamadı: {e}")
    st.stop()


if st.button("🚀 Tüm Analizleri Başlat ve Veritabanını Güncelle", type="primary"):

    # --- 1. Temel Analiz Skorlarını Hesapla ---
    with st.spinner("📊 Temel analiz skorları hesaplanıyor... (Bu işlem uzun sürebilir)"):
        try:
            df_fundamental, logs, _ = run_scan(df_radar)
            st.success("✅ Temel analiz skorları başarıyla hesaplandı.")
            # Hata ayıklama için geçici olarak göster
            st.write("Hesaplanan Temel Skorlar (ilk 5 satır):")
            st.dataframe(df_fundamental.head())
        except Exception as e:
            st.error(f"Temel analiz sırasında bir hata oluştu: {e}")
            st.stop()


    # --- 2. Teknik Analiz Metriklerini Hesapla ---
    with st.spinner("📈 Güncel teknik metrikler ve fiyatlar hesaplanıyor..."):
        try:
            # force_refresh=True her zaman en güncel veriyi çeker ve DB'ye yazar
            df_technical = get_or_compute_today(
                list(companies),
                force_refresh=True
            )
            st.success("✅ Teknik analiz metrikleri başarıyla hesaplandı.")
            st.write("Hesaplanan Teknik Metrikler (ilk 5 satır):")
            st.dataframe(df_technical.head())
        except Exception as e:
            st.error(f"Teknik analiz sırasında bir hata oluştu: {e}")
            st.stop()


    # --- 3. İki Veri Setini Birleştir ---
    st.info("İki veri seti birleştiriliyor...")
    try:
        symbol_col = "hisse"
        # Teknik verideki 'symbol' kolonunu 'hisse' olarak yeniden adlandır
        df_merged = df_fundamental.merge(
            df_technical.rename(columns={"symbol": symbol_col}),
            on=symbol_col,
            how="left"
        )
        st.success("✅ Veriler başarıyla birleştirildi.")
        st.write("Birleştirilmiş Veri (ilk 5 satır):")
        st.dataframe(df_merged.head())
    except Exception as e:
        st.error(f"Veri birleştirme sırasında bir hata oluştu: {e}")
        st.stop()

    # --- 4. Birleşik Veriyi Veritabanına Kaydet ---
    with st.spinner("💾 Birleştirilmiş veriler `radar_scores` tablosuna kaydediliyor..."):
        try:
            # Temel ve teknik skorları bir arada olan df_merged'i kaydediyoruz.
            save_dataframe(df_merged, table="radar_scores")
            st.success("🎉 Tüm veriler başarıyla veritabanına kaydedildi!")
            st.balloons()
        except Exception as e:
            st.error(f"Veritabanına kaydetme sırasında bir hata oluştu: {e}")
            st.stop()