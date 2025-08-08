# modules/financial_cache_manager.py
from __future__ import annotations
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import pytz
from modules.data_loader import load_financial_data

CACHE_DIR = Path("data_cache/financial")
IST = pytz.timezone("Europe/Istanbul")

def _ensure_dir(): CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _bist_business_date(now=None):
    now = now or datetime.now(IST); d = now.date()
    if d.weekday() == 5: return d - timedelta(days=1)   # Cumartesi->Cuma
    if d.weekday() == 6: return d - timedelta(days=2)   # Pazar->Cuma
    return d

def _p(symbol: str, kind: str) -> Path:
    return CACHE_DIR / f"{symbol}.{kind}.parquet"

def _read(path: Path) -> pd.DataFrame | None:
    if not path.exists(): return None
    try: return pd.read_parquet(path)
    except Exception: return None

def _write(path: Path, df: pd.DataFrame) -> None:
    _ensure_dir()
    df2 = df.copy()
    df2.to_parquet(path, index=False)

def get_financials_cached(symbol: str, force_refresh: bool=False):
    """
    Aynı BIST iş gününde aynı şirket için tekrar disk I/O yapmaz.
    Excel’ler güncellense bile gün içinde tekrar tekrar okuma yapmayı engeller.
    """
    target = _bist_business_date()

    p_bal = _p(symbol, "balance")
    p_inc = _p(symbol, "income")
    p_cf  = _p(symbol, "cashflow")

    bal, inc, cf = _read(p_bal), _read(p_inc), _read(p_cf)

    # Cache'in "gün" staleness kontrolü:
    # Kolonlarında dönem isimleri var; en yeni döneme bakıp o iş gününde yazılmış mı diye kaba kontrol:
    def _last_cache_day(df: pd.DataFrame) -> datetime.date | None:
        if df is None or df.empty: return None
        # Her üç tablo da dönem kolonları taşır; yoksa None.
        period_cols = [c for c in df.columns if "/" in c]
        return target if period_cols else None

    fresh_enough = (
        not force_refresh and
        _last_cache_day(bal) == target and
        _last_cache_day(inc) == target and
        _last_cache_day(cf)  == target
    )

    if fresh_enough and all(x is not None for x in (bal, inc, cf)):
        return bal, inc, cf

    # Diskten gerçek veriyi oku (asıl kaynak)
    bal, inc, cf = load_financial_data(symbol)

    # Cache’e yaz
    _write(p_bal, bal)
    _write(p_inc, inc)
    _write(p_cf,  cf)

    return bal, inc, cf
