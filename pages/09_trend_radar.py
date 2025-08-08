import os
import streamlit as st
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
from streamlit import column_config as cc # type: ignore
from isyatirimhisse import StockData

from modules.utils_db import load_filtered_radar_scores

# -------------------------------------------
# Teknik analiz verisini önbellekten getir veya çek
# Bu fonksiyon zaten bir dosya tabanlı önbellekleme yapıyor, bu iyi.
# -------------------------------------------
def get_cached_or_fetch(symbol: str, days: int = 120) -> pd.DataFrame:
    cache_dir = "data_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{symbol}.parquet")

    if os.path.exists(cache_path):
        try:
            df = pd.read_parquet(cache_path)
            if not df.empty:
                df.index = pd.to_datetime(df.index)
                last_date = df.index.max().date()
                today = pd.Timestamp.now().date()
                # Sadece bugün tarihli veri varsa doğrudan dön
                if last_date >= today - pd.Timedelta(days=1): # Hafta sonunu tolere etmek için >= 1 gün
                    return df
        except Exception:
            # Parquet dosyası bozuksa yeniden çek
            pass

    sd = StockData()
    end_date = datetime.today()
    start_date = end_date - pd.Timedelta(days=days)
    df_all = sd.get_data(
        symbols=[symbol],
        start_date=start_date.strftime("%d-%m-%Y"),
        end_date=end_date.strftime("%d-%m-%Y"),
        frequency="1d",
        return_type="0",
    )
    if df_all is None or df_all.empty:
        return pd.DataFrame()

    df_all.rename(columns={
        "CLOSING_TL": "close",
        "HIGH_TL": "high",
        "LOW_TL": "low",
        "VOLUME_TL": "volume",
        "DATE": "date",
        "CODE": "symbol"
    }, inplace=True)

    df_all["date"] = pd.to_datetime(df_all["date"])
    df_all.set_index("date", inplace=True)
    df_all.sort_index(inplace=True)
    df_all.to_parquet(cache_path)
    return df_all

# -------------------------------------------
# Teknik filtreleri hesapla
# -------------------------------------------
def apply_technical_filters(symbol: str, df_price: pd.DataFrame) -> dict:
    if df_price.empty or "close" not in df_price:
        return {"RSI": np.nan, "Trend": "YOK"}

    close = df_price["close"].dropna()
    if len(close) < 50:
        return {"RSI": np.nan, "Trend": "YETERSIZ VERI"}

    rsi_val = ta.rsi(close, length=14).dropna()
    rsi = round(rsi_val.iloc[-1], 1) if not rsi_val.empty else np.nan

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()

    trend = "YOK"
    try:
        prev_sma20 = sma20.iloc[-2]
        prev_sma50 = sma50.iloc[-2]
        curr_sma20 = sma20.iloc[-1]
        curr_sma50 = sma50.iloc[-1]

        if prev_sma20 < prev_sma50 and curr_sma20 > curr_sma50:
            trend = "🔁 TREND DÖNÜŞÜ"
        elif curr_sma20 > curr_sma50:
            trend = "📈 YUKARI"
        else:
            trend = "📉 ASAGI"
    except IndexError:
        trend = "YETERSIZ VERI"

    return {"RSI": rsi, "Trend": trend}

# -------------------------------------------
# Streamlit Sayfa
# -------------------------------------------
def main():
    st.set_page_config(page_title="Filtrelenmiş Değer + Teknik Radar", layout="wide")
    st.title("📡 Filtrelenmiş Değer + Teknik Radar")

    # st.session_state kullanarak hesaplamaların tekrarını önle
    if 'df_final_tech_radar' not in st.session_state:
        st.write("Veriler ilk kez yükleniyor, lütfen bekleyin...")
        
        df_scores = load_filtered_radar_scores()
        if df_scores.empty:
            st.warning("Filtreye uyan radar skoru verisi bulunamadı.")
            st.stop() # Sayfanın geri kalanını çalıştırmayı durdur

        unique_symbols = df_scores["hisse"].unique()
        results = []
        progress_bar = st.progress(0, text="Teknik veriler hesaplanıyor...")

        for i, symbol in enumerate(unique_symbols):
            df_price = get_cached_or_fetch(symbol)
            tech = apply_technical_filters(symbol, df_price)

            latest = df_scores[df_scores["hisse"] == symbol].sort_values("timestamp", ascending=False).iloc[0]

            results.append({
                "Hisse": symbol,
                "F-Skor": latest.f_skor,
                "M-Skor": latest.m_skor,
                "Graham": latest.graham,
                "Lynch": latest.lynch,
                "MOS %": round(latest["MOS"], 2),
                "RSI": tech["RSI"],
                "Trend": tech["Trend"]
            })
            
            progress_bar.progress((i + 1) / len(unique_symbols), text=f"Teknik veriler hesaplanıyor... ({symbol})")

        # Hesaplanan DataFrame'i session_state'e kaydet
        st.session_state.df_final_tech_radar = pd.DataFrame(results)
        progress_bar.empty()

    # Artık her rerun'da bu df'i session_state'den hızlıca okuyabiliriz
    df_final = st.session_state.df_final_tech_radar
    
    df_final["Link"] = "/stock_analysis?symbol=" + df_final["Hisse"]

    st.subheader("🎯 Temel + Teknik Filtre Sonuçları")
    st.caption("Detayları görmek için aşağıdaki tablodan bir satıra tıklayın.")

    selection = st.dataframe(
        df_final,
        column_config={
            "Link": cc.LinkColumn(
                label="Link",    # hangi kolon URL’yi tutuyor
                display_text="Analize Git"
            )
        },
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row"
    )

    st.subheader("📋 Satır Bazlı Kopyalanabilir Veri")

    if selection.selection.rows:
        selected_row_index = selection.selection.rows[0]
        row = df_final.iloc[selected_row_index]
        row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
        st.code(row_str, language="markdown")
    else:
        st.info("Kopyalanabilir veriyi görmek için yukarıdaki tablodan bir hisse seçin.")

    st.download_button("⬇️ CSV İndir", df_final.to_csv(index=False), file_name="tech_radar.csv", mime="text/csv")

    st.caption("Not: Bu analiz yatırım tavsiyesi değildir. Finsight-me & İş Yatırım verileri kullanılmıştır.")

if __name__ == "__main__":
    main()