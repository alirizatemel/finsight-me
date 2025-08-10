
"""FCF-related data preparation and calculations (no plotting here)."""
from __future__ import annotations
import pandas as pd

from modules.finance.data_loader import load_financial_data
from modules.logger import logger
from .utils import validate_market_cap, sort_period_index, ensure_unique_ordered

def _load_income_cashflow(company: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load income and cashflow dataframes with 'Kalem' as index."""
    _, income_df, cashflow_df = load_financial_data(company)
    income_df = income_df.set_index("Kalem")
    cashflow_df = cashflow_df.set_index("Kalem")
    return income_df, cashflow_df

def _select_capex(cashflow_df: pd.DataFrame) -> pd.Series:
    if "Maddi ve Maddi Olmayan Duran Varlık Alımları" in cashflow_df.index:
        return cashflow_df.loc["Maddi ve Maddi Olmayan Duran Varlık Alımları"]
    if "Yatırım Faaliyetlerinden Kaynaklanan Nakit Akışları" in cashflow_df.index:
        return cashflow_df.loc["Yatırım Faaliyetlerinden Kaynaklanan Nakit Akışları"]
    raise ValueError("CAPEX verisi bulunamadı.")

def fcf_yield_series(company: str, row) -> pd.Series:
    """Compute FCF Yield time series (%) using Operating CF - CAPEX divided by market cap.
    Returns a Series indexed by period labels (YYYY/MM) sorted chronologically.
    """
    income_df, cashflow_df = _load_income_cashflow(company)
    operating_cf = cashflow_df.loc["İşletme Faaliyetlerinden Nakit Akışları"]
    capex = _select_capex(cashflow_df)
    fcf = (operating_cf - capex).dropna()

    market_cap = validate_market_cap(row.get("Piyasa Değeri", None) if hasattr(row, "get") else row["Piyasa Değeri"])
    fcf_y = (fcf / market_cap * 100).dropna()
    return ensure_unique_ordered(fcf_y)

def build_fcf_dataframe(company: str, row) -> pd.DataFrame:
    """Create a detailed FCF-focused dataframe with sales, net profit, OCF, CAPEX, FCF, and FCF Yield.
    Index is periods (YYYY/MM) sorted chronologically.
    """
    income_df, cashflow_df = _load_income_cashflow(company)

    sales_series        = income_df.loc["Satış Gelirleri"]
    # Some sources keep 'Dönem Karı (Zararı)' in the income statement; if absent there, fallback to CF.
    net_profit_series   = (income_df.loc["Dönem Karı (Zararı)"]
                           if "Dönem Karı (Zararı)" in income_df.index
                           else cashflow_df.loc["Dönem Karı (Zararı)"])
    operating_cf_series = cashflow_df.loc["İşletme Faaliyetlerinden Nakit Akışları"]
    capex_series        = _select_capex(cashflow_df)

    fcf_series = operating_cf_series - capex_series
    market_cap = validate_market_cap(row.get("Piyasa Değeri", None) if hasattr(row, "get") else row["Piyasa Değeri"])
    fcf_yield  = (fcf_series / market_cap * 100).dropna()

    df = pd.DataFrame({
        "Satışlar"             : sales_series,
        "Net Kâr"              : net_profit_series,
        "Faaliyet Nakit Akışı" : operating_cf_series,
        "CAPEX"                : capex_series,
        "FCF"                  : fcf_series,
        "FCF Verimi (%)"       : fcf_yield,
    })
    df = df.loc[sort_period_index(df.index)]
    return df
