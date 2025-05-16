import streamlit as st #type: ignore
import pandas as pd
from datetime import datetime

from config import PORTFOLIO_XLSX, RADAR_XLSX          # Excel hâlâ bunlardan okunuyor
from modules.utils_db import load_performance_log, upsert_performance_log

st.set_page_config(page_title="📈 Performans Log Güncelle", layout="wide")
st.title("📘 Performans Log Güncelleme Aracı")

# === 1. Dosyaları/DB’yi yükle ===
@st.cache_data
def load_data():
    df_portfoy = pd.read_excel(PORTFOLIO_XLSX)
    df_fiyat   = pd.read_excel(RADAR_XLSX)
    df_log     = load_performance_log()               # ← artık DB’den geliyor
    return df_portfoy, df_fiyat, df_log

df_portfoy, df_fiyat, df_log = load_data()

# === 2. Normalize ===
df_portfoy = df_portfoy[pd.notnull(df_portfoy["Graham Skoru"])]
df_portfoy["Hisse"] = df_portfoy["Hisse"].str.upper().str.strip()
df_fiyat["Hisse"]   = df_fiyat["Şirket"].str.upper().str.strip()
df_log["hisse"]     = df_log["hisse"].str.upper().str.strip()   # DB kolonu küçük harf

# === 3. Güncelle butonu ===
st.info("Portföy verileri ile DB’deki logu karşılaştırır, eksik satırları ekler.")
if st.button("🔄 Log Güncelle"):
    bugun = datetime.today().date()
    yeni_kayitlar = []

    for _, row in df_portfoy.iterrows():
        hisse       = row["Hisse"]
        mevcut_lot  = row["Lot"]

        # Log’daki son lotu bul
        log_kayitlari = df_log[df_log["hisse"] == hisse].sort_values("tarih")
        son_lot       = log_kayitlari.iloc[-1]["lot"] if not log_kayitlari.empty else 0

        if mevcut_lot != son_lot:                     # değişim varsa
            fiyat_bilgisi = df_fiyat[df_fiyat["Hisse"] == hisse]
            fiyat         = fiyat_bilgisi.iloc[0]["Son Fiyat"] if not fiyat_bilgisi.empty else None

            yeni_kayitlar.append(
                {"tarih": bugun, "hisse": hisse, "lot": mevcut_lot, "fiyat": fiyat}
            )

    if yeni_kayitlar:
        df_yeni = pd.DataFrame(yeni_kayitlar)
        upsert_performance_log(df_yeni)               # ← DB’ye kaydet
        # Streamlit cache’i temizle & tekrar yükle
        st.cache_data.clear()
        _, _, df_log = load_data()
        st.success(f"🟢 {len(yeni_kayitlar)} satır eklendi / güncellendi.")
    else:
        st.warning("⚪ Değişiklik bulunamadı.")

# === 4. Mevcut Log Görüntüleme ===
st.subheader("📊 Güncel Performans Logu")

df_log_display = (
    df_log.copy()
          .assign(tarih=lambda d: pd.to_datetime(d["tarih"]).dt.strftime("%d.%m.%Y"))
          .sort_values("tarih", ascending=False)
)

st.dataframe(df_log_display, hide_index=True, use_container_width=True)
