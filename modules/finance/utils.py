
"""Finance utilities: period parsing, validations, and helpers."""

from __future__ import annotations
import pandas as pd
from typing import Iterable, Tuple, Union

def period_order(period_str: str) -> pd.Timestamp:
    """Parse a "YYYY/MM" string into a pandas Timestamp at month start.
    Returns pd.NaT for invalid inputs (so sort/dropna can handle gracefully).
    """
    try:
        year, month = str(period_str).split("/")
        return pd.to_datetime(f"{int(year):04d}-{int(month):02d}-01", errors="coerce")
    except Exception:
        return pd.NaT

def validate_market_cap(value) -> float:
    """Validate and return market cap as positive float, else raise ValueError."""
    import pandas as pd
    from modules.utils import scalar  # uses project's helper

    try:
        v = scalar(pd.to_numeric(value, errors="coerce"))
        if v is None or pd.isna(v) or v <= 0:
            raise ValueError("Geçersiz piyasa değeri (<= 0 veya NaN)." )
        return float(v)
    except Exception as e:
        raise ValueError(f"Piyasa değeri geçersiz: {e}")

def sort_period_index(idx: Iterable[str]) -> list:
    """Return a list of the given period labels sorted chronologically."""
    return sorted(idx, key=period_order)

def ensure_unique_ordered(series: pd.Series) -> pd.Series:
    """Drop duplicate index labels, then sort chronologically by period."""
    s = series.loc[~series.index.duplicated()].copy()
    s = s[sort_period_index(s.index)]
    return s
