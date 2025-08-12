import streamlit as st #type: ignore
import pandas as pd
from datetime import datetime, timedelta
from modules.technical_analysis.data_fetcher import fetch_and_process_stock_data
from modules.db.performance_log import upsert_performance_log

def run_performance_log_update(acik_pozisyonlar: pd.DataFrame, df_log: pd.DataFrame):
    """
    Açık pozisyonlar için eksik haftalık kapanışları bulur ve veritabanına ekler.
    Streamlit arayüz elemanları ile ilerlemeyi gösterir.
    """
    if acik_pozisyonlar.empty:
        st.info("⚪ Log’a eklenecek **açık** pozisyon bulunmadı.")
        return

    yeni_kayitlar = []
    log_summary = {}
    
    st.write(f"Toplam {len(acik_pozisyonlar)} adet açık pozisyon için eksik veriler taranıyor...")
    progress_bar = st.progress(0, text="Başlatılıyor...")

    for i, (_, prt) in enumerate(acik_pozisyonlar.iterrows()):
        hisse = prt["Hisse"]
        lot_now = prt["lot"]
        progress_bar.progress((i) / len(acik_pozisyonlar), text=f"🔎 {hisse} taranıyor...")

        # Başlangıç tarihini belirle
        log_for_hisse = df_log[df_log["hisse"] == hisse]
        start_date = log_for_hisse["tarih"].max() + timedelta(days=1) if not log_for_hisse.empty else prt["alis_tarihi"]

        if start_date.date() >= datetime.today().date():
            continue

        try:
            days_to_fetch = (datetime.today() - start_date).days + 2
            price_df = fetch_and_process_stock_data(symbol=hisse, days=days_to_fetch)
            if price_df.empty:
                st.warning(f"⚠️ **{hisse}** için fiyat verisi bulunamadı.")
                continue
            
            weekly_closes = price_df['close'].resample('W-FRI').last().dropna()
            weekly_closes = weekly_closes[weekly_closes.index >= start_date]

            if not weekly_closes.empty:
                for date, price in weekly_closes.items():
                    yeni_kayitlar.append({"tarih": date, "hisse": hisse, "lot": lot_now, "fiyat": price})
                log_summary[hisse] = len(weekly_closes)

        except Exception as e:
            st.error(f"❌ **{hisse}** için veri çekilirken hata oluştu: {e}")

    progress_bar.progress(1.0, text="Tamamlandı!")

    if yeni_kayitlar:
        df_yeni = pd.DataFrame(yeni_kayitlar)
        upsert_performance_log(df_yeni)
        st.cache_data.clear() # Cache'i temizle
        
        st.success(f"✅ Toplam {len(yeni_kayitlar)} adet eksik haftalık kayıt başarıyla log'landı!")
        with st.expander("Detayları Gör"):
            for hisse, count in log_summary.items():
                st.markdown(f"- **{hisse}:** `{count}` adet yeni kayıt eklendi.")
        st.balloons()
    else:
        st.info("💡 Tüm hisseleriniz güncel. Log'a eklenecek yeni haftalık veri bulunamadı.")