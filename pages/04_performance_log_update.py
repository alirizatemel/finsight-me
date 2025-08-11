# 04_performance_log_update.py (DOĞRU KOLON İSİMLERİ İLE GÜNCELLENMİŞ SÜRÜM)

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

from modules.technical_analysis.data_fetcher import fetch_and_process_stock_data
from modules.db.performance_log import (
    load_performance_log,
    upsert_performance_log,
)
from modules.db.portfolio import (
    load_portfolio_df # Sadece bu fonksiyonu kullanacağız
)

st.set_page_config(page_title="📈 Performans Log Güncelle", layout="wide")
st.title("📘 Performans Zaman Akışı Güncelle")
st.info(
    "Bu sayfa, portföydeki her hisse için en son log tarihinden bugüne kadar olan "
    "**eksik haftalık kapanış fiyatlarını** bularak zaman akışına ekler."
)

# --- 1. Verileri Yükle -------------------------------------------
@st.cache_data
def load_initial_data():
    """Veritabanından portföy ve log verilerini yükler."""
    df_portfoy = load_portfolio_df()
    df_log = load_performance_log()
    return df_portfoy, df_log

df_portfoy, df_log = load_initial_data()

# Tarih sütunlarını datetime formatına çevirelim (çok önemli)
# DEĞİŞTİRİLDİ: Kolon adı 'alis_tarih' -> 'alis_tarihi' olarak düzeltildi.
df_portfoy["alis_tarihi"] = pd.to_datetime(df_portfoy["alis_tarihi"])
if not df_log.empty:
    df_log["tarih"] = pd.to_datetime(df_log["tarih"])

df_portfoy["Hisse"] = df_portfoy["hisse"].str.upper().str.strip()


# --- 2. Eksik Haftalık Kapanışları Bul ve Güncelle --------------------------
if st.button("⏱️ Eksik Haftalık Kapanışları Logla", type="primary"):
    yeni_kayitlar = []
    log_summary = {}

    # Sadece açık pozisyonları (satış fiyatı olmayanları) al
    acik_pozisyonlar = df_portfoy[df_portfoy["satis_fiyat"].isna()]

    if acik_pozisyonlar.empty:
        st.info("⚪ Log’a eklenecek **açık** pozisyon bulunmadı.")
    else:
        st.write(f"Toplam {len(acik_pozisyonlar)} adet açık pozisyon için eksik veriler taranıyor...")
        progress_bar = st.progress(0, text="Başlatılıyor...")

        for i, (_, prt) in enumerate(acik_pozisyonlar.iterrows()):
            hisse = prt["Hisse"]
            lot_now = prt["lot"]
            progress_bar.progress((i) / len(acik_pozisyonlar), text=f"🔎 {hisse} taranıyor...")

            # 1. Bu hisse için başlangıç tarihini belirle
            log_for_hisse = df_log[df_log["hisse"] == hisse]
            if not log_for_hisse.empty:
                start_date = log_for_hisse["tarih"].max() + timedelta(days=1)
            else:
                # DEĞİŞTİRİLDİ: Kolon adı 'alis_tarih' -> 'alis_tarihi' olarak düzeltildi.
                start_date = prt["alis_tarihi"]

            # 2. Eğer başlangıç tarihi bugünden eskiyse veri çek
            if start_date.date() < datetime.today().date():
                days_to_fetch = (datetime.today() - start_date).days + 2
                
                try:
                    price_df = fetch_and_process_stock_data(symbol=hisse, days=days_to_fetch)
                    if price_df.empty:
                        st.warning(f"⚠️ **{hisse}** için fiyat verisi bulunamadı.")
                        continue
                    
                    weekly_closes = price_df['close'].resample('W-FRI').last().dropna()
                    weekly_closes = weekly_closes[weekly_closes.index >= start_date]

                    if not weekly_closes.empty:
                        for date, price in weekly_closes.items():
                            yeni_kayitlar.append({
                                "tarih": date,
                                "hisse": hisse,
                                "lot": lot_now,
                                "fiyat": price
                            })
                        log_summary[hisse] = len(weekly_closes)

                except Exception as e:
                    st.error(f"❌ **{hisse}** için veri çekilirken hata oluştu: {e}")

        progress_bar.progress(1.0, text="Tamamlandı!")

        if yeni_kayitlar:
            df_yeni = pd.DataFrame(yeni_kayitlar)
            upsert_performance_log(df_yeni)

            st.cache_data.clear()
            _, df_log = load_initial_data()
            
            st.success(f"✅ Toplam {len(yeni_kayitlar)} adet eksik haftalık kayıt başarıyla log'landı!")
            with st.expander("Detayları Gör"):
                for hisse, count in log_summary.items():
                    st.markdown(f"- **{hisse}:** `{count}` adet yeni kayıt eklendi.")
            st.balloons()
        else:
            st.info("💡 Tüm hisseleriniz güncel. Log'a eklenecek yeni haftalık veri bulunamadı.")

# --- 3. Zaman Akışı Görünümü -----------------------------------
st.subheader("📊 Güncel Performans Zaman Akışı")

if df_log.empty:
    st.info("Henüz log kaydı bulunmamaktadır.")
else:
    df_display = df_log.copy()
    df_display["tarih"] = pd.to_datetime(df_display["tarih"]).dt.strftime('%d.%m.%Y')
    
    st.dataframe(
        df_display.sort_values("tarih", ascending=False),
        hide_index=True,
        use_container_width=True,
        column_config={
            "tarih": st.column_config.TextColumn("Tarih"),
            "fiyat": st.column_config.NumberColumn("Fiyat (TL)", format="%.2f"),
            "lot": st.column_config.NumberColumn("Lot", format="%d"),
        }
    )