# 05_performance_log_update.py  (KESİN INSERT/TIMELINE SÜRÜMÜ)

import streamlit as st   # type: ignore
import pandas as pd
from datetime import datetime
from config import RADAR_XLSX
from modules.utils_db import (
    load_portfolio_df,
    load_performance_log,
    upsert_performance_log,
)

st.set_page_config(page_title="📈 Performans Log Güncelle", layout="wide")
st.title("📘 Performans Zaman Akışı Güncelle")

# --- 1. Verileri Yükle ------------------------------------------------------
@st.cache_data
def load_data():
    df_portfoy = load_portfolio_df()                # lot -> DB
    df_fiyat   = pd.read_excel(RADAR_XLSX)          # fiyat -> XLSX
    df_log     = load_performance_log()
    return df_portfoy, df_fiyat, df_log

df_portfoy, df_fiyat, df_log = load_data()

# Normalize
df_portfoy["Hisse"] = df_portfoy["hisse"].str.upper().str.strip()
df_fiyat["Hisse"]   = df_fiyat["Şirket"].str.upper().str.strip()

# --- 2. Güncelle ------------------------------------------------------------
st.info("Her hisse için bugünkü fiyat-lot bilgisi zaman akışına eklenir.")
if st.button("⏱️ Tüm Hisseleri Logla"):
    zaman_damgasi = datetime.now()                 # ⚠️ tam timestamp
    yeni_kayitlar = []

    for _, prt in df_portfoy.iterrows():
        print(prt["satis_fiyat"])
        if pd.notna(prt["satis_fiyat"]):
            continue

        hisse     = prt["Hisse"]
        lot_now   = prt["lot"]

        fiyat_row = df_fiyat[df_fiyat["Hisse"] == hisse]
        fiyat_now = fiyat_row.iloc[0]["Son Fiyat"] if not fiyat_row.empty else None

        yeni_kayitlar.append(
            {"tarih": zaman_damgasi, "hisse": hisse, "lot": lot_now, "fiyat": fiyat_now}
        )

    if yeni_kayitlar:
        df_yeni = pd.DataFrame(
            yeni_kayitlar,
            columns=["tarih", "hisse", "lot", "fiyat"]   # sütunları garanti et
        )
        upsert_performance_log(df_yeni)
        st.cache_data.clear()
        _, _, df_log = load_data()
        st.success(f"🟢 {len(yeni_kayitlar)} satır eklendi.")
    else:
        st.info("⚪ Log’a eklenecek **açık** pozisyon bulunmadı.")

# --- 3. Zaman Akışı Görünümü ------------------------------------------------
st.subheader("📊 Güncel Performans Zaman Akışı")
st.dataframe(
    df_log.sort_values("tarih", ascending=False)
          .assign(tarih=lambda d: pd.to_datetime(d["tarih"]).dt.strftime("%d.%m.%Y")),
    hide_index=True,
    use_container_width=True,
)
