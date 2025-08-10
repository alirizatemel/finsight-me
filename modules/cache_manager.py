# modules/cache_manager.py
from __future__ import annotations
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import pytz

from modules.technical_analysis.data_fetcher import fetch_and_process_stock_data

CACHE_DIR = Path("data_cache")
IST = pytz.timezone("Europe/Istanbul")

def _ensure_dir(): CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _bist_business_date(now=None):
    now = now or datetime.now(IST); d = now.date()
    if d.weekday() == 5: return d - timedelta(days=1)   # Cumartesi->Cuma
    if d.weekday() == 6: return d - timedelta(days=2)   # Pazar->Cuma
    return d

def _p(symbol: str) -> Path: return CACHE_DIR / f"{symbol}.parquet"

def _read(symbol: str) -> pd.DataFrame | None:
    p = _p(symbol)
    if not p.exists(): return None
    try: return pd.read_parquet(p)
    except Exception: return None

def _write(symbol: str, df: pd.DataFrame) -> None:
    _ensure_dir()
    df2 = df.copy()
    if "date" in df2: df2["date"] = pd.to_datetime(df2["date"])
    df2.to_parquet(_p(symbol), index=False)

def _norm(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1) date kolonu yoksa index'ten veya "Date" kolonundan üret
    if "date" not in df.columns:
        # index adı 'date' veya 'Date' ise resetle
        if df.index.name and df.index.name.lower() == "date":
            df = df.reset_index().rename(columns={df.index.name: "date"})
        # index datetime ise resetle
        elif pd.api.types.is_datetime64_any_dtype(df.index):
            df = df.reset_index().rename(columns={"index": "date"})
        # kolon 'Date' ise yeniden adlandır
        elif "Date" in df.columns:
            df = df.rename(columns={"Date": "date"})

    # 2) date kolonunu datetime'a çevir
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.tz_localize(None)
        df = df.dropna(subset=["date"])
    else:
        # Hâlâ yoksa boş dönelim ki sort_values sırasında patlamayalım
        return pd.DataFrame(columns=["date","close","high","low","volume"])

    return df


def get_price_df(symbol: str, force_refresh: bool = False) -> pd.DataFrame:
    target = _bist_business_date()

    cached = _read(symbol)
    if cached is not None:
        cached = _norm(cached)

    fresh = fetch_and_process_stock_data(symbol)
    fresh = _norm(fresh)

    # 👇 Güvenli "son tarih" çıkarımı
    def _latest_date(df: pd.DataFrame):
        if df is None or df.empty or "date" not in df.columns:
            return None
        s = pd.to_datetime(df["date"], errors="coerce")
        s = s.dropna()
        if s.empty:
            return None
        return s.dt.date.max()

    cached_latest = _latest_date(cached)

    # Eğer cached tarihi okunamadıysa (None) cache'i geçersiz sayalım
    if cached is not None and cached_latest and not force_refresh:
        if cached_latest >= target:
            return cached

    # Birleştir ve yaz
    if cached is not None and not cached.empty:
        out = (
            pd.concat([cached, fresh], ignore_index=True)
              .dropna(subset=["date"])
              .sort_values("date")
              .drop_duplicates(subset=["date"], keep="last")
              .reset_index(drop=True)
        )
    else:
        out = fresh

    _write(symbol, out)
    return out

