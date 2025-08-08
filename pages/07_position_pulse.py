# --- START OF FILE 08_position_pulse.py (CSV ÇIKTISINA GÖRE GÜNCELLENDİ) ---

import traceback 
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
import os

# Kütüphane importları
from isyatirimhisse import fetch_stock_data
import pandas_ta as ta

# Yerel modül
from modules.utils_db import load_portfolio_df

# ---------------------------------------------------------------------------
# Veri Çekme ve İşleme Fonksiyonları
# ---------------------------------------------------------------------------

def get_cached_or_fetch(symbol: str, days: int = 120, max_age_days: int = 1) -> pd.DataFrame:
    cache_dir = "data_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{symbol}.parquet")

    now = pd.Timestamp.now()
    if os.path.exists(cache_path):
        df = pd.read_parquet(cache_path)
        if not df.empty:
            df.index = pd.to_datetime(df.index)
            if df.index.max() is not pd.NaT:
                age = (now - df.index.max()).days
                if age <= max_age_days:
                    return df

    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    try:
        df_all = fetch_stock_data(
            symbols=[symbol],
            start_date=start_date.strftime("%d-%m-%Y"),
            end_date=end_date.strftime("%d-%m-%Y"),
            save_to_excel=False
        )
    except Exception as e:
        st.warning(f"⚠️ **{symbol}** için veri çekilirken beklenmedik bir hata oluştu: {e}. Bu hisse atlanıyor.")
        return pd.DataFrame()

    # DÜZELTME 1: Sütun kontrolü, gerçek sütun adına ('HGDG_TARIH') göre yapıldı.
    if df_all is None or df_all.empty or "HGDG_TARIH" not in df_all.columns:
        st.info(f"ℹ️ **{symbol}** için geçerli veri bulunamadı.")
        return pd.DataFrame()

    # DÜZELTME 2: 'rename' işlemi, CSV'den gelen gerçek sütun adlarına göre güncellendi.
    df_all.rename(columns={
        "HGDG_KAPANIS": "close",
        "HGDG_MAX": "high",
        "HGDG_MIN": "low",
        "HGDG_HACIM": "volume", # HGDG_HACIM veya HG_HACIM kullanılabilir, ikisi de aynı görünüyor.
        "HGDG_TARIH": "date",
        "HGDG_HS_KODU": "symbol"
    }, inplace=True)

    df_all["date"] = pd.to_datetime(df_all["date"])
    df_all.set_index("date", inplace=True)
    df_all.sort_index(inplace=True)
    
    # Sadece gerekli sütunları tutarak dosyayı küçültebiliriz (isteğe bağlı)
    final_df = df_all[['close', 'high', 'low', 'volume', 'symbol']]
    
    final_df.to_parquet(cache_path)
    return final_df


def get_all_prices(symbols: List[str], days: int = 120) -> Dict[str, pd.DataFrame]:
    price_dict = {}
    progress_bar = st.progress(0, text="Hisse senedi verileri çekiliyor...")
    total_symbols = len(symbols)

    for i, symbol in enumerate(symbols):
        df = get_cached_or_fetch(symbol, days=days)
        if not df.empty:
            price_dict[symbol] = df
        
        progress_bar.progress((i + 1) / total_symbols, text=f"Hisse verileri çekiliyor... ({symbol})")
    
    progress_bar.empty()
    return price_dict


def compute_rsi(close: pd.Series, length: int = 14) -> float:
    if len(close) < length:
        return float("nan")
    rsi_series = ta.rsi(close, length=length)
    return rsi_series.dropna().iloc[-1] if not rsi_series.dropna().empty else float("nan")

# ---------------------------------------------------------------------------
# Analiz Fonksiyonları (Bu bölümlerde değişiklik yok)
# ---------------------------------------------------------------------------

def buy_back_analysis(sold_df: pd.DataFrame, all_prices: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for _, row in sold_df.iterrows():
        sym = row["hisse"]
        sale_price = row["satis_fiyat"]
        today_close, rsi_value, trend = float("nan"), float("nan"), "BILINMIYOR"
        suggestion = "BEKLE"

        if sym in all_prices:
            price_df = all_prices[sym]
            close = price_df["close"].dropna()
            if not close.empty:
                today_close = close.iloc[-1]
                rsi_value = round(compute_rsi(close), 1)

                if len(close) >= 50:
                    sma20_series = close.rolling(20).mean()
                    sma50_series = close.rolling(50).mean()
                    if not sma20_series.empty and not sma50_series.empty and len(sma20_series) > 1 and len(sma50_series) > 1:
                        sma20, sma50 = sma20_series.iloc[-1], sma50_series.iloc[-1]
                        prev_sma20, prev_sma50 = sma20_series.iloc[-2], sma50_series.iloc[-2]
                        trend = "YUKARI" if sma20 > sma50 else "ASAGI"

                        if prev_sma20 < prev_sma50 and sma20 > sma50:
                            trend = "TREND DÖNÜŞÜ"
                else:
                    trend = "YETERSIZ VERI"

                target_7 = round(sale_price * 0.93, 2)
                if today_close <= target_7 and (
                    (pd.notna(rsi_value) and rsi_value <= 40) or trend == "TREND DÖNÜŞÜ"):
                    suggestion = "GERI AL"

        rows.append({
            "Hisse": sym,
            "Satış Fiyatı": sale_price,
            "Güncel Fiyat": today_close,
            "RSI": rsi_value,
            "Trend": trend,
            "Hedef (−7%)": round(sale_price * 0.93, 2),
            "Karar": suggestion
        })

    df = pd.DataFrame(rows)
    return df.style.applymap(lambda v: 'color: green; font-weight: bold' if v == 'GERI AL' else ('color: gray' if v == 'BEKLE' else None), subset=['Karar'])


def sell_analysis(active_df: pd.DataFrame, all_prices: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for _, row in active_df.iterrows():
        sym, cost = row["hisse"], row["maliyet"]
        latest_close, pnl_pct, rsi_value = float("nan"), float("nan"), float("nan")
        trend, suggestion = "BILINMIYOR", "DEGERLENDIR"

        if sym in all_prices:
            df_price = all_prices[sym]
            close = df_price["close"].dropna()
            if not close.empty:
                latest_close = close.iloc[-1]
                pnl_pct = round((latest_close - cost) / cost * 100, 2)
                rsi_value = round(compute_rsi(close), 1)

                if len(close) >= 50:
                    sma20, sma50 = close.rolling(20).mean().iloc[-1], close.rolling(50).mean().iloc[-1]
                    trend = "YUKARI" if sma20 > sma50 else "ASAGI"
                else:
                    trend = "YETERSIZ VERI"

                if pd.notna(rsi_value) and rsi_value >= 75: suggestion = "SAT"
                elif trend == "ASAGI" and pnl_pct > 5: suggestion = "KAR AL / GÖZDEN GEÇİR"
                else: suggestion = "TUT"
        else:
            trend = "VERI YOK"

        rows.append({"Hisse": sym, "Lot": row["lot"], "Maliyet": cost, "Güncel": latest_close, "PnL %": pnl_pct, "RSI": rsi_value, "Trend": trend, "Karar": suggestion})

    df = pd.DataFrame(rows)
    return df.style.applymap(
        lambda v: 'color: red; font-weight: bold' if v == 'SAT' else (
                  'color: orange; font-weight: bold' if v.startswith('KAR AL') else (
                  'color: green' if v == 'TUT' else None)), subset=['Karar']
    )

# ---------------------------------------------------------------------------
# Streamlit Arayüzü
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="Portföy Nabız Paneli", layout="wide")
    st.title("📊 Portföy Nabız Paneli")

    try:
        portfolio_df = load_portfolio_df()
        if portfolio_df.empty:
            st.info("Portföy (portfolio.csv) boş veya yüklenemedi."); return

        sold_df = portfolio_df[portfolio_df["satis_fiyat"].notna()]
        active_df = portfolio_df[portfolio_df["satis_fiyat"].isnull()]
        all_symbols = list(portfolio_df["hisse"].unique())
        
        if not all_symbols:
            st.info("Portföyde analiz edilecek hisse bulunmuyor."); return

        all_prices_dict = get_all_prices(symbols=all_symbols)

        tab1, tab2 = st.tabs(["🛒 Geri Alım Fırsatları", "💸 Satış Sinyalleri"])
        with tab1:
            st.subheader("Satış Sonrası Geri Alım Analizi")
            if sold_df.empty: 
                st.info("Analiz edilecek, satılmış pozisyon bulunmuyor.")
            else: 
                st.dataframe(buy_back_analysis(sold_df, all_prices_dict), use_container_width=True, hide_index=True)
        with tab2:
            st.subheader("Aktif Pozisyonlar için Satış Analizi")
            if active_df.empty: 
                st.info("Analiz edilecek, aktif pozisyon bulunmuyor.")
            else: 
                st.dataframe(sell_analysis(active_df, all_prices_dict), use_container_width=True, hide_index=True)

    except FileNotFoundError: 
        st.error("Portföy dosyası (portfolio.csv) bulunamadı.")
    except Exception as e: 
        st.error(f"Beklenmedik bir genel hata oluştu: {e}")
        st.code(traceback.format_exc())

    st.caption("Veri kaynağı: İş Yatırım • Bu sayfa bir yatırım tavsiyesi değildir.")

if __name__ == "__main__":
    main()