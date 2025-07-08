import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict

# Kütüphane importları
from isyatirimhisse import StockData
import pandas_ta as ta

# Yerel modül
from modules.utils_db import load_portfolio_df

# ---------------------------------------------------------------------------
# Veri Çekme ve İşleme Fonksiyonları
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner="Tüm hisselerin fiyat verileri çekiliyor...", ttl=3600)
def get_all_prices(symbols: List[str], days: int = 120) -> Dict[str, pd.DataFrame]:
    if not symbols:
        return {}

    sd = StockData()
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    df_all = sd.get_data(
        symbols=symbols,
        start_date=start_date.strftime("%d-%m-%Y"),
        end_date=end_date.strftime("%d-%m-%Y"),
        frequency="1d",
        return_type="0",
    )

    if df_all is None or df_all.empty:
        st.warning(f"API'den {', '.join(symbols)} için veri alınamadı.")
        return {}

    # --- Kolon düzeltmeleri ---
    df_all.rename(columns={
        "CLOSING_TL": "close",
        "HIGH_TL": "high",
        "LOW_TL": "low",
        "VOLUME_TL": "volume",
        "DATE": "date",
        "CODE": "symbol"
    }, inplace=True)

    if 'symbol' not in df_all.columns:
        if len(symbols) == 1:
            df_all['symbol'] = symbols[0]
        else:
            st.error("Kritik Hata: Birden fazla hisse istendi ancak 'symbol' sütunu döndürülmedi.")
            return {}

    price_dict = {}
    for symbol, group in df_all.groupby('symbol'):
        group = group.copy()
        group["date"] = pd.to_datetime(group["date"])
        group.set_index("date", inplace=True)
        group.sort_index(inplace=True)
        price_dict[symbol] = group

    return price_dict


def compute_rsi(close: pd.Series, length: int = 14) -> float:
    if len(close) < length:
        return float("nan")
    rsi_series = ta.rsi(close, length=length)
    return rsi_series.dropna().iloc[-1] if not rsi_series.dropna().empty else float("nan")

# ---------------------------------------------------------------------------
# Analiz Fonksiyonları (Değişiklik yok)
# ---------------------------------------------------------------------------

def buy_back_analysis(sold_df: pd.DataFrame, all_prices: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for _, row in sold_df.iterrows():
        sym = row["hisse"]
        sale_price = row["satis_fiyat"]
        today_close = float("nan")

        if sym in all_prices:
            price_df = all_prices[sym]
            if "close" in price_df and not price_df["close"].dropna().empty:
                today_close = price_df["close"].dropna().iloc[-1]

        target_7 = round(sale_price * 0.93, 2)
        suggestion = "AL" if pd.notna(today_close) and today_close <= target_7 else "BEKLE"

        rows.append({"Hisse": sym, "Satış Fiyatı": sale_price, "Güncel Fiyat": today_close, "Hedef (−7%)": target_7, "Karar": suggestion})
    return pd.DataFrame(rows)


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
    return pd.DataFrame(rows)

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

        sold_df, active_df = portfolio_df[portfolio_df["satis_fiyat"].notnull()], portfolio_df[portfolio_df["satis_fiyat"].isnull()]
        all_symbols = list(portfolio_df["hisse"].unique())
        if not all_symbols:
            st.info("Portföyde analiz edilecek hisse bulunmuyor."); return

        all_prices_dict = get_all_prices(symbols=all_symbols)

        tab1, tab2 = st.tabs(["🛒 Geri Alım Fırsatları", "💸 Satış Sinyalleri"])
        with tab1:
            st.subheader("Satış Sonrası Geri Alım Analizi")
            if sold_df.empty: st.info("Analiz edilecek, satılmış pozisyon bulunmuyor.")
            else: st.dataframe(buy_back_analysis(sold_df, all_prices_dict), use_container_width=True, hide_index=True)
        with tab2:
            st.subheader("Aktif Pozisyonlar için Satış Analizi")
            if active_df.empty: st.info("Analiz edilecek, aktif pozisyon bulunmuyor.")
            else: st.dataframe(sell_analysis(active_df, all_prices_dict), use_container_width=True, hide_index=True)

    except FileNotFoundError: st.error("Portföy dosyası (portfolio.csv) bulunamadı.")
    except Exception as e: 
        st.error(f"Beklenmedik bir genel hata oluştu: {e}")

    st.caption("Veri kaynağı: İş Yatırım • Bu sayfa bir yatırım tavsiyesi değildir.")

if __name__ == "__main__":
    main()
