
"""Plotting utilities for finance visualizations (matplotlib only)."""
from __future__ import annotations

import matplotlib.pyplot as plt  # type: ignore
import matplotlib.dates as mdates  # type: ignore
import pandas as pd

from .utils import period_order

def plot_fcf_yield_time_series(company: str, fcf_yield: pd.Series):
    """Return a matplotlib Figure visualizing the FCF Yield time series (%) for a company."""
    fig, ax = plt.subplots(figsize=(10, 5))
    x = [period_order(p) for p in fcf_yield.index]
    y = fcf_yield.values

    ax.plot(x, y, marker="o", linestyle="-", label="FCF Verimi (%)")
    ax.fill_between(x, 0, y, alpha=0.1)
    ax.set_title(f"{company} – FCF Verimi Zaman Serisi")
    ax.set_ylabel("FCF Verimi (%)")
    ax.set_xlabel("Dönem")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

def plot_fcf_detailed(company: str, df: pd.DataFrame):
    """Return a matplotlib Figure with 5 stacked charts for detailed FCF-focused analysis."""
    # Ensure datetime x index
    idx_dt = pd.to_datetime(df.index, format="%Y/%m", errors="coerce")
    df_plot = df.copy()
    df_plot.index = idx_dt

    df_ma = df_plot.rolling(3).mean()

    x = df_plot.index
    fig, axes = plt.subplots(5, 1, figsize=(14, 16), sharex=True)

    items = [
        ("Satışlar",),
        ("Net Kâr",),
        ("FCF",),
        ("CAPEX",),
        ("FCF Verimi (%)",),
    ]

    for i, (col,) in enumerate(items):
        scale = (1e9 if "Verimi" not in col else 1.0)
        y    = df_plot[col] / scale
        y_ma = df_ma[col]   / scale

        axes[i].plot(x, y, linestyle='-', marker='o', label=col)
        axes[i].plot(x, y_ma, linestyle='--', label="Hareketli Ortalama (3)")
        axes[i].fill_between(x, 0, y, alpha=0.1)
        axes[i].set_ylabel(col + ("\n(Milyar TL)" if "Verimi" not in col else ""))
        axes[i].legend()
        axes[i].grid(True)

    axes[-1].set_xlabel("Tarih")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    fig.suptitle(f"{company} | FCF Odaklı Finansal Analiz", fontsize=16)
    plt.xticks(rotation=45)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    return fig
    