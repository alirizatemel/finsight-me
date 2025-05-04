import streamlit as st
import pandas as pd
from datetime import datetime
from config import PORTFOLIO_XLSX, PERFORMANS_XLSX, RADAR_XLSX

st.set_page_config(page_title="📈 Performans Log Güncelle", layout="wide")

st.title("📘 Performans Log Güncelleme Aracı")

# === 1. Excel dosyalarını yükle ===
@st.cache_data
def load_data():
    df_portfoy = pd.read_excel(PORTFOLIO_XLSX)
    df_fiyat = pd.read_excel(RADAR_XLSX)
    df_log = pd.read_excel(PERFORMANS_XLSX)
    return df_portfoy, df_fiyat, df_log

df_portfoy, df_fiyat, df_log = load_data()

# === 2. Hisse isimlerini normalize et ===

df_portfoy = df_portfoy[pd.notnull(df_portfoy["Graham Skoru"])]
df_portfoy["Hisse"] = df_portfoy["Hisse"].str.upper().str.strip()
df_fiyat["Hisse"] = df_fiyat["Şirket"].str.upper().str.strip()
df_log["Hisse"] = df_log["Hisse"].str.upper().str.strip()


# === 3. Güncelleme butonu ===
st.info("Portföy verileri ile log dosyasını karşılaştırarak yeni hareketleri otomatik olarak ekler.")
if st.button("🔄 Log Güncelle"):

    bugun = datetime.today()
    yeni_kayitlar = []

    for _, row in df_portfoy.iterrows():
        hisse = row["Hisse"]
        mevcut_lot = row["Lot"]

        log_kayitlari = df_log[df_log["Hisse"] == hisse]
        son_lot = log_kayitlari.sort_values("Tarih").iloc[-1]["Lot"] if not log_kayitlari.empty else 0

        fiyat_bilgisi = df_fiyat[df_fiyat["Hisse"] == hisse]
        fiyat = fiyat_bilgisi.iloc[0]["Son Fiyat"] if not fiyat_bilgisi.empty else None

        yeni_kayitlar.append({
            "Tarih": bugun,
            "Hisse": hisse,
            "Lot": mevcut_lot,
            "Fiyat": fiyat
        })

    if yeni_kayitlar:
        df_yeni = pd.DataFrame(yeni_kayitlar)
        df_log = pd.concat([df_log, df_yeni], ignore_index=True)
        df_log.to_excel(PERFORMANS_XLSX, index=False)
        st.success(f"🟢 {len(yeni_kayitlar)} yeni kayıt eklendi.")
    else:
        st.warning("⚪ Herhangi bir değişiklik tespit edilmedi.")

# === 4. Mevcut Log Görüntüleme ===
st.subheader("📊 Güncel Performans Logu")

# 1. Tarih sütununu datetime'a çevir
df_log["Tarih"] = pd.to_datetime(df_log["Tarih"], errors="coerce")

# 2. Sıralamayı burada yap
df_log_sorted = df_log.sort_values("Tarih", ascending=False)

# 3. Görselleştirme için kopya al ve sadece formatla
df_log_display = df_log_sorted.copy()
df_log_display["Tarih"] = df_log_display["Tarih"].dt.strftime("%d.%m.%Y")

# 4. Ekranda göster
st.dataframe(df_log_display, hide_index=True, use_container_width=True)
