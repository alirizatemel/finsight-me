"""Profitability analytics: build 7-year profitability table and helpers."""
from __future__ import annotations

import math
import pandas as pd
from typing import Dict, List, Optional

from modules.finance.data_loader import load_financial_data
from modules.utils import period_order


def _ensure_index(df: pd.DataFrame) -> pd.DataFrame:
    if df.index.name != "Kalem":
        return df.set_index("Kalem")
    return df


def _series_from(df: pd.DataFrame, item: str) -> pd.Series:
    if item not in df.index:
        raise KeyError(f"'{item}' satırı bulunamadı")
    s = df.loc[item]
    # Keep only period-like columns
    s = s[[c for c in s.index if isinstance(c, str) and "/" in c]].copy()
    s = pd.to_numeric(s, errors="coerce")
    # Sort by period chronologically
    s = s[pd.Index(sorted(s.index, key=period_order))]
    return s


def _series_from_any(df: pd.DataFrame, items) -> pd.Series:
    """Try multiple possible row names and return the first found series."""
    if isinstance(items, str):
        items = [items]
    last_err = None
    for name in items:
        try:
            return _series_from(df, name)
        except Exception as e:
            last_err = e
            continue
    raise last_err if last_err else KeyError("No matching row name found")


def _yearly_sum(flow_q: pd.Series) -> pd.Series:
    # Sum quarterly values per calendar year
    groups: Dict[str, List[str]] = {}
    for col in flow_q.index:
        year = str(col).split("/")[0]
        groups.setdefault(year, []).append(col)
    data = {}
    for y, cols in groups.items():
        data[y] = pd.to_numeric(flow_q.loc[cols], errors="coerce").sum(min_count=1)
    s = pd.Series(data)
    s = s.sort_index()
    return s


def _yearly_last_level(stock_q: pd.Series) -> pd.Series:
    # Take last available quarter of each year (e.g., 12 > 09 > 06 > 03)
    by_year: Dict[str, str] = {}
    for col in stock_q.index:
        year, month = str(col).split("/")
        if year not in by_year:
            by_year[year] = col
        else:
            # pick the later period in the same year
            prev = by_year[year]
            by_year[year] = max(prev, col, key=period_order)
    data = {y: stock_q.loc[col] for y, col in by_year.items()}
    s = pd.Series(data)
    s = pd.to_numeric(s, errors="coerce").sort_index()
    return s


def build_profitability_table(symbol: str, last_n_years: int = 7) -> pd.DataFrame:
    """Return a DataFrame indexed by year with Sales, Net Profit, Equity, Assets, and ratios.

    Columns:
      - Satışlar
      - Net Kâr
      - Özkaynaklar (Yıl Sonu)
      - Varlıklar (Yıl Sonu)
      - Net Marj (%)
      - ROE (%)
      - ROA (%)
    """
    balance, income, _ = load_financial_data(symbol)
    balance = _ensure_index(balance)
    income = _ensure_index(income)

    sales_q = _series_from_any(income, ["Satış Gelirleri", "Hasılat", "Net Satışlar"])  # satış alternatifleri
    # Net profit may exist in income; if not, it's typically present in cashflow too,
    # but for profitability ratios we use the income statement definition when available.
    net_items = [
        "Dönem Karı (Zararı)",
        "Net Dönem Karı (Zararı)",
    ]
    for name in net_items:
        if name in income.index:
            net_q = _series_from(income, name)
            break
    else:
        # Fallback: try a common cashflow label if income one is missing
        _, _, cash = load_financial_data(symbol)
        cash = _ensure_index(cash)
        net_q = _series_from(cash, "Dönem Karı (Zararı)")

    equity_q = _series_from_any(balance, [
        "Ana Ortaklığa Ait Özkaynaklar",
        "Toplam Özkaynaklar",
        "Özkaynaklar",
        "Özkaynaklar Toplamı",
        "Özkaynaklar (Toplam)",
    ])
    assets_q = _series_from_any(balance, [
        "Toplam Varlıklar",
        "Varlıklar Toplamı",
    ])

    sales_y = _yearly_sum(sales_q)
    net_y = _yearly_sum(net_q)
    equity_y = _yearly_last_level(equity_q)
    assets_y = _yearly_last_level(assets_q)

    # Align by common years and keep the most recent N years
    years = sorted(set(sales_y.index) & set(net_y.index) & set(equity_y.index) & set(assets_y.index))
    df = pd.DataFrame({
        "Satışlar": sales_y.reindex(years),
        "Net Kâr": net_y.reindex(years),
        "Özkaynaklar (Yıl Sonu)": equity_y.reindex(years),
        "Varlıklar (Yıl Sonu)": assets_y.reindex(years),
    })
    df = df.tail(last_n_years)

    # Ratios
    with pd.option_context("mode.use_inf_as_na", True):
        df["Net Marj (%)"] = (df["Net Kâr"] / df["Satışlar"]) * 100
        df["ROE (%)"] = (df["Net Kâr"] / df["Özkaynaklar (Yıl Sonu)"]) * 100
        df["ROA (%)"] = (df["Net Kâr"] / df["Varlıklar (Yıl Sonu)"]) * 100

    return df


def compute_net_profit_cagr(df: pd.DataFrame) -> Optional[float]:
    """Compute CAGR (%) for Net Profit in the given yearly profitability table."""
    if df.empty or "Net Kâr" not in df:
        return None
    series = df["Net Kâr"].dropna()
    if len(series) < 2:
        return None
    first, last = float(series.iloc[0]), float(series.iloc[-1])
    n = len(series) - 1
    if first <= 0 or last <= 0:
        return None
    cagr = (last / first) ** (1 / n) - 1
    return cagr * 100


def build_profitability_ratios(symbol: str, last_n_years: int = 7) -> pd.DataFrame:
    """Return yearly ratios for ROE, ROA, Net Margin, Gross Margin, and EBITDA Margin.

    Uses income, balance, and cashflow tables. EBITDA approximated as
    Esas/Faaliyet Kârı + Amortisman (nakit akışındaki düzeltmeler).
    """
    balance, income, cashflow = load_financial_data(symbol)
    balance = _ensure_index(balance)
    income = _ensure_index(income)
    cashflow = _ensure_index(cashflow)

    # Akış kalemleri (yıllık toplanır)
    sales_q = _series_from_any(income, ["Satış Gelirleri", "Hasılat", "Net Satışlar"])  
    net_q = _series_from_any(income, ["Dönem Karı (Zararı)", "Net Dönem Karı (Zararı)"])
    gross_q = _series_from_any(income, ["Brüt Kar (Zarar)", "Ticari Faaliyetlerden Brüt Kar (Zarar)"])

    # Stok kalemleri (yıl sonu seviye)
    equity_q = _series_from_any(balance, [
        "Ana Ortaklığa Ait Özkaynaklar",
        "Toplam Özkaynaklar",
    ])
    assets_q = _series_from_any(balance, ["Toplam Varlıklar", "Varlıklar Toplamı"])

    # EBITDA ≈ Esas/ Faaliyet Kârı + Amortisman
    op_profit_q = None
    for cand in ["Esas Faaliyet Karı (Zararı)", "Faaliyet Karı (Zararı)", "Faaliyetlerden Kar (Zarar)"]:
        if cand in income.index:
            op_profit_q = _series_from(income, cand)
            break
    dep_q = None
    for cand in [
        "Amortisman ve İtfa Gideri İle İlgili Düzeltmeler",
        "Amortisman ve İtfa Düzeltmeleri",
    ]:
        if cand in cashflow.index:
            dep_q = _series_from(cashflow, cand)
            break

    # Yıllıklaştırma
    sales_y = _yearly_sum(sales_q)
    net_y = _yearly_sum(net_q)
    gross_y = _yearly_sum(gross_q)
    equity_y = _yearly_last_level(equity_q)
    assets_y = _yearly_last_level(assets_q)
    ebitda_y = None
    if op_profit_q is not None and dep_q is not None:
        ebitda_y = _yearly_sum(op_profit_q) + _yearly_sum(dep_q)

    years = sorted(set(sales_y.index) & set(net_y.index) & set(equity_y.index) & set(assets_y.index))
    df = pd.DataFrame(index=years)
    df.index.name = "Yıl"
    df["ROE (%)"] = (net_y.reindex(years) / equity_y.reindex(years)) * 100
    df["ROA (%)"] = (net_y.reindex(years) / assets_y.reindex(years)) * 100
    df["Net Kâr Marjı (%)"] = (net_y.reindex(years) / sales_y.reindex(years)) * 100
    df["Brüt Marj (%)"] = (gross_y.reindex(years) / sales_y.reindex(years)) * 100
    if ebitda_y is not None:
        df["FAVÖK Marjı (%)"] = (ebitda_y.reindex(years) / sales_y.reindex(years)) * 100
    else:
        df["FAVÖK Marjı (%)"] = pd.Series(index=years, dtype=float)

    df = df.sort_index().tail(last_n_years)
    return df
