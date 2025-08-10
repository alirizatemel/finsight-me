# modules/trend_score_manager.py
from __future__ import annotations
from datetime import datetime, timedelta
import pytz
import pandas as pd
import pandas_ta as ta # type: ignore
from sqlalchemy import create_engine, text
from config import PG_URL  # type: ignore
from modules.cache_manager import get_price_df
from modules.technical_analysis.trend_indicators import calculate_rsi_trend

from modules.cache_manager import get_price_df  # -> data_cache/{symbol}.parquet
from modules.utils_db import execute_many, read_df 

engine = create_engine(PG_URL)

DDL = """
CREATE TABLE IF NOT EXISTS trend_scores (
  id SERIAL PRIMARY KEY,
  symbol TEXT NOT NULL,
  date DATE NOT NULL,
  rsi REAL,
  sma20 REAL,
  sma50 REAL,
  trend TEXT,
  last_price REAL,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(symbol, date)
);
"""

UPSERT = """
INSERT INTO trend_scores(symbol, "date", rsi, sma20, sma50, trend, last_price, created_at, updated_at)
VALUES (:symbol, :date, :rsi, :sma20, :sma50, :trend, :last_price, NOW(), NOW())
ON CONFLICT (symbol, "date")
DO UPDATE SET
  rsi        = EXCLUDED.rsi,
  sma20      = EXCLUDED.sma20,
  sma50      = EXCLUDED.sma50,
  trend      = EXCLUDED.trend,
  last_price = EXCLUDED.last_price,
  updated_at = NOW();
"""

def ensure_table():
    with engine.begin() as conn:
        conn.execute(text(DDL))

def upsert_one(symbol: str, force_refresh: bool = False) -> dict | None:
    df = get_price_df(symbol, force_refresh=force_refresh)
    if df is None or df.empty:
        return None

    # normalize: 'date' sütunu garanti olsun
    if "date" not in df.columns:
        df = df.reset_index().rename(columns={"index":"date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    if "close" not in df.columns or df.empty:
        return None

    last_row = df.sort_values("date").iloc[-1]
    last_date = pd.to_datetime(last_row["date"]).date()
    last_price = float(last_row["close"]) if pd.notna(last_row["close"]) else None

    # RSI/SMA/Trend hesaplaman burada veya calculate_rsi_trend içinde olabilir
    metrics = calculate_rsi_trend(df)  # rsi, sma20, sma50, trend döndürdüğünü varsayıyoruz
    if metrics is None:
        return None

    payload = {
        "symbol": symbol,
        "date": last_date,
        "rsi": float(metrics.get("rsi")) if metrics.get("rsi") is not None else None,
        "sma20": float(metrics.get("sma20")) if metrics.get("sma20") is not None else None,
        "sma50": float(metrics.get("sma50")) if metrics.get("sma50") is not None else None,
        "trend": metrics.get("trend"),
        "last_price": last_price,
    }

    with engine.begin() as conn:
        conn.execute(text(UPSERT), payload)

    return payload

def batch_update(symbols: list[str], force_refresh: bool=False) -> pd.DataFrame:
    ensure_table()
    out = []
    for s in symbols:
        try:
            row = upsert_one(s, force_refresh=force_refresh)
            if row: out.append(row)
        except Exception:
            # sembol bazında hatayı yut, devam et
            pass
    return pd.DataFrame(out)

def load_for_symbols(symbols: list[str]) -> pd.DataFrame:
    if not symbols: return pd.DataFrame()
    q = text("""
        SELECT symbol, date, rsi, sma20, sma50, trend, last_price
        FROM trend_scores
        WHERE symbol = ANY(:syms)
    """)
    with engine.begin() as conn:
        df = pd.read_sql(q, conn, params={"syms": symbols})
    return df

IST = pytz.timezone("Europe/Istanbul")

def _bist_business_date(now=None):
    now = now or datetime.now(IST); d = now.date()
    if d.weekday() == 5: return d - timedelta(days=1)  # Cumartesi->Cuma
    if d.weekday() == 6: return d - timedelta(days=2)  # Pazar->Cuma
    return d

def _compute_tech_from_prices(df: pd.DataFrame) -> dict | None:
    if df is None or df.empty: 
        return None
    # df: index=date (veya 'date' kolonu) + 'close'
    if "date" not in df.columns:
        df = df.reset_index().rename(columns={"index":"date"})
    df = df.sort_values("date").copy()
    close = pd.to_numeric(df["close"], errors="coerce")
    if close.isna().all(): 
        return None
    df["close"] = close
    df["SMA20"] = close.rolling(20).mean()
    df["SMA50"] = close.rolling(50).mean()
    df["RSI14"] = ta.rsi(close, length=14)

    trend = None
    if len(df) >= 50 and df["SMA20"].notna().iloc[-1] and df["SMA50"].notna().iloc[-1]:
        prev20, prev50 = df["SMA20"].iloc[-2], df["SMA50"].iloc[-2]
        cur20, cur50   = df["SMA20"].iloc[-1], df["SMA50"].iloc[-1]
        if prev20 < prev50 and cur20 > cur50: trend = "🔁 TREND DÖNÜŞÜ (Al)"
        elif cur20 > cur50:                   trend = "📈 YUKARI"
        else:                                 trend = "📉 AŞAĞI"

    last = df.iloc[-1]
    return dict(
        date=pd.to_datetime(last["date"]).date(),
        rsi=float(last["RSI14"]) if pd.notna(last["RSI14"]) else None,
        sma20=float(last["SMA20"]) if pd.notna(last["SMA20"]) else None,
        sma50=float(last["SMA50"]) if pd.notna(last["SMA50"]) else None,
        last_price = float(last["close"]) if "close" in df.columns and pd.notna(last["close"]) else None,
        trend=trend
    )

def _get_today_from_db(symbols: list[str]) -> pd.DataFrame:
    date_ = _bist_business_date()
    q = """
        SELECT symbol, date, rsi, sma20, sma50, trend, last_price
        FROM trend_scores
        WHERE date = :date AND symbol = ANY(:symbols)
    """
    return read_df(q, {"date": date_, "symbols": list(symbols)})


def _upsert_trend_rows(rows: list[dict]) -> None:
    sql = """
    INSERT INTO trend_scores(symbol, "date", rsi, sma20, sma50, trend, last_price, created_at, updated_at)
    VALUES (:symbol, :date, :rsi, :sma20, :sma50, :trend, :last_price, NOW(), NOW())
    ON CONFLICT (symbol, "date")
    DO UPDATE SET
      rsi        = EXCLUDED.rsi,
      sma20      = EXCLUDED.sma20,
      sma50      = EXCLUDED.sma50,
      trend      = EXCLUDED.trend,
      last_price = EXCLUDED.last_price,
      updated_at = NOW();
    """
    execute_many(sql, rows)


def get_or_compute_today(symbols: list[str], *, force_refresh: bool=False) -> pd.DataFrame:
    symbols = [s.strip().upper() for s in symbols if isinstance(s, str) and s.strip()]
    if not symbols:
        return pd.DataFrame(columns=["symbol","date","rsi","sma20","sma50","trend","last_price"])

    out_df = pd.DataFrame()
    if not force_refresh:
        out_df = _get_today_from_db(symbols)

    # --- YENİ: Eksik kolonları olan bugünkü satırları da "tamamlanması gereken" olarak işaretle
    needed_cols = ["rsi", "sma20", "sma50", "trend", "last_price"]  # istersen azalt/çoğalt
    if out_df.empty:
        have_complete_syms = set()
    else:
        mask_complete = out_df[needed_cols].notna().all(axis=1)
        have_complete_syms = set(out_df.loc[mask_complete, "symbol"])

    # DB'de hiç olmayan + eksik kalan semboller
    to_compute = (set(symbols) - have_complete_syms) if not force_refresh else set(symbols)

    if to_compute:
        upsert_rows = []
        for sym in sorted(to_compute):
            price_df = get_price_df(sym, force_refresh=False)
            metrics = _compute_tech_from_prices(price_df)
            if not metrics:
                continue
            upsert_rows.append({
                "symbol": sym,
                "date":  metrics["date"],
                "rsi":   metrics["rsi"],
                "sma20": metrics["sma20"],
                "sma50": metrics["sma50"],
                "trend": metrics["trend"],
                "last_price": metrics["last_price"],
            })

        if upsert_rows:
            _upsert_trend_rows(upsert_rows)
            out_df = _get_today_from_db(symbols)

    return out_df

