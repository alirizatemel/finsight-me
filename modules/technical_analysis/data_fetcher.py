# data_fetcher.py

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from tenacity import retry, wait_random_exponential, stop_after_attempt

# >>> isyatirimhisse import yolunu kendi projenizde nasıl kullanıyorsanız ÖYLE bırakın/değiştirin.
# Örn: from isyatirimhisse import fetch_stock_data  veya  from isyatirimhisse.some_module import fetch_stock_data
from isyatirimhisse import fetch_stock_data  

logger = logging.getLogger(__name__)

# API'nin ham kolon isimlerini -> senin standart isimlerine mapliyoruz.
COLUMN_MAP = {
    "HGDG_TARIH": "date",
    "HGDG_KAPANIS": "close",
    "HGDG_MAX": "high",
    "HGDG_MIN": "low",
    "HGDG_HACIM": "volume",
}

REQUIRED_STD_COLS = ["date", "close", "high", "low", "volume"]


@st.cache_data(show_spinner=True, ttl=timedelta(minutes=15))
def fetch_and_process_stock_data(
    symbol: str,
    days: int = 252,
    *,
    filter_weekends: bool = True,
) -> pd.DataFrame:
    """
    Belirtilen sembol için fiyat verisini çeker, standardize eder ve son `days` satırı döner.

    Özellikler:
    - `days` artık gerçekten anlamlı: Yeterli veri alabilmek için takvim gününü geniş tutuyoruz.
    - Exponential backoff ile retry (tenacity).
    - Kolonlar güvenli şekilde rename edilir, eksikse uyarı/stop.
    - Tarih parse, NaN temizliği, duplicate tarihler, sort ve (opsiyonel) hafta sonu filtrelemesi.
    """

    end_date = datetime.today()
    # 252 işlem gününü güvene almak için ~1.6x-2x takvim günü kadar veri çekelim
    lookback_days = max(days, 30) * 2
    start_date = end_date - timedelta(days=lookback_days)

    # isyatirimhisse genelde "DD-MM-YYYY" bekliyor; farklıysa burada düzelt.
    start_str = start_date.strftime("%d-%m-%Y")
    end_str = end_date.strftime("%d-%m-%Y")

    @retry(wait=wait_random_exponential(min=0.5, max=4), stop=stop_after_attempt(3))
    def _fetch():
        # fetch_stock_data’nın imzası senin sürümüne göre değişebilir.
        # symbols bir liste olmak zorundaysa: symbols=[symbol]
        # DataFrame döndürüyorsa direkt alırız, dict döndürüyorsa symbol anahtarını seçeriz.
        res = fetch_stock_data(
            symbols=[symbol],
            start_date=start_str,
            end_date=end_str,
            # save_to_excel gibi gereksiz/olmayan parametreler kaldırıldı
        )

        if isinstance(res, dict):
            # Sende DataFrame doğrudan dönüyorsa bu blok sorunsuz atlanır.
            # Dict dönüyorsa çoğunlukla {symbol: df} pattern'i olur.
            # Anahtar isimleri farklıysa burayı özelleştir.
            return res.get(symbol, pd.DataFrame())
        return res

    try:
        df_raw = _fetch()
    except Exception as e:
        logger.exception("Veri çekme hatası")
        with st.expander("Teknij veri hata ayrıntıları", expanded=False):
            st.error(f"'{symbol}' için veri çekilirken bir AĞ/API HATASI oluştu.")
            st.warning(f"Detay: {e}")
            st.info("Sunucu geçici olarak isteği reddetmiş olabilir (rate limiting). Biraz bekleyip tekrar deneyin.")
        return pd.DataFrame()

    if df_raw is None or df_raw.empty:
        st.warning(f"'{symbol}' için veri bulunamadı.")
        return pd.DataFrame()

    # Beklenen kolonlar geliyor mu?
    missing_raw = set(COLUMN_MAP.keys()) - set(df_raw.columns)
    if missing_raw:
        st.error(f"Beklenen kolonlar gelmedi: {missing_raw}. API değişmiş olabilir.")
        st.write("Gelen Kolonlar:", df_raw.columns.tolist())
        return pd.DataFrame()

    # Standardize et
    df = (
        df_raw.rename(columns=COLUMN_MAP)
        .loc[:, REQUIRED_STD_COLS]  # yalnızca ihtiyacımız olan standart kolonlar
        .assign(
            date=lambda d: pd.to_datetime(d["date"], errors="coerce"),
            close=lambda d: pd.to_numeric(d["close"], errors="coerce"),
            high=lambda d: pd.to_numeric(d["high"], errors="coerce"),
            low=lambda d: pd.to_numeric(d["low"], errors="coerce"),
            volume=lambda d: pd.to_numeric(d["volume"], errors="coerce"),
        )
        .dropna(subset=["date"])
        .drop_duplicates(subset=["date"], keep="last")
        .set_index("date")
        .sort_index()
    )

    if filter_weekends:
        df = df[df.index.dayofweek < 5]

    # Son 'days' işlem gününü ver
    return df.tail(days)
