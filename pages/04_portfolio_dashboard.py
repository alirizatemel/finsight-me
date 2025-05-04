# 📊 Portföy & Performans Dashboard ‑ Streamlit Page
"""
Streamlit page that combines the logic from the uploaded Jupyter notebooks
(`performans_dashboard.ipynb` and `portfolio_analysis.ipynb`).
Drop this file into your Streamlit app’s **pages/** folder. It will appear as
“05_📊 Portföy & Performans Dashboard” in the sidebar.

Dependencies (add to requirements.txt if missing):
    pandas
    numpy
    matplotlib
    streamlit>=1.33

Folder expectations (override from sidebar if needed):
    data/performans_log.xlsx   – daily position log (columns: Tarih, Hisse, Lot, Fiyat)
    data/portfoy_verisi.xlsx   – portfolio snapshot (columns incl. Graham Skoru…)

Author: ChatGPT (o3) – generated 2025‑05‑02
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt #type: ignore
import numpy as np
import pandas as pd
import streamlit as st #type: ignore

# ---------------------------------------------------------------------------
# ⏱ Page set‑up
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Portföy & Performans Dashboard",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Portföy & Performans Dashboard")

# ---------------------------------------------------------------------------
# 🔧 Helper functions (taken & refactored from your notebooks)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)          # refresh every 60 s
def latest_prices_from_log(log_path: Path | str) -> pd.Series:
    """
    Return a Series indexed by ticker (Hisse) containing the most
    recent price in performans_log.xlsx.
    """
    df = load_log(log_path)                         # re‑use existing loader
    if df.empty:
        return pd.Series(dtype=float)

    # ensure newest record per ticker
    df_sorted = df.sort_values(["Hisse", "Tarih"])
    latest = df_sorted.groupby("Hisse").tail(1).set_index("Hisse")["Fiyat"]
    return latest


@st.cache_data(show_spinner=False)
def load_log(log_path: Path | str) -> pd.DataFrame:
    """Read the daily position log and enrich with helper columns."""
    df = pd.read_excel(log_path)
    if df.empty:
        st.warning("Performans log dosyası boş görünüyor.")
        return df

    df["Tarih"] = pd.to_datetime(df["Tarih"])
    df["Değer"] = df["Lot"] * df["Fiyat"]
    return df

@st.cache_data(show_spinner=False)
def load_portfolio(xlsx_path: Path | str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path)
    return df

@st.cache_data(show_spinner=False)
def weekly_performance(df_log: pd.DataFrame, lookback_days: int = 7) -> pd.DataFrame:
    """Return % performance for the last *lookback_days* for each stock."""
    if df_log.empty:
        return pd.DataFrame()

    cutoff = df_log["Tarih"].max() - timedelta(days=lookback_days)
    df_slice = df_log[df_log["Tarih"] >= cutoff].copy()
    df_slice.sort_values(["Hisse", "Tarih"], inplace=True)
    first_prices = df_slice.groupby("Hisse").first()["Fiyat"]
    last_prices = df_slice.groupby("Hisse").last()["Fiyat"]
    perf = ((last_prices - first_prices) / first_prices * 100).round(2)
    return perf.reset_index(name="Getiri (%)")

@st.cache_data(show_spinner=False)
def sharpe_ratio(df_log: pd.DataFrame, risk_free_daily: float = 0.47 / 252) -> pd.DataFrame:
    if df_log.empty:
        return pd.DataFrame()

    df_sorted = df_log.sort_values(["Hisse", "Tarih"]).copy()
    df_sorted["Getiri"] = df_sorted.groupby("Hisse")["Fiyat"].pct_change()

    agg = df_sorted.groupby("Hisse").agg(
        ort_getiri=("Getiri", "mean"),
        std=("Getiri", "std"),
        n=("Getiri", "count"),
    )
    agg["Sharpe_oran"] = ((agg["ort_getiri"] - risk_free_daily) / agg["std"]) * math.sqrt(252)
    agg = agg.reset_index()
    return agg

@st.cache_data(show_spinner=False)
def enrich_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    """Classify assets and pre‑compute P/L columns."""
    df = df.copy()
    df["Varlık Tipi"] = df["Graham Skoru"].apply(
        lambda x: "Değer Hissesi" if pd.notnull(x) else "Fon/Spekülatif"
    )

    # Open positions (no sale price)
    df_open = df[df["Satış Fiyatı"].isna()].copy()
    df_open["Yatırılan Tutar"] = df_open["Lot"] * df_open["Maliyet"]
    df_open["Anlık Değer"] = df_open["Lot"] * df_open["Güncel Fiyat"]
    df_open["Kar/Zarar"] = df_open["Anlık Değer"] - df_open["Yatırılan Tutar"]
    df_open["Kar/Zarar (%)"] = (df_open["Kar/Zarar"] / df_open["Yatırılan Tutar"]) * 100

    # Closed positions
    df_closed = df[df["Satış Fiyatı"].notna()].copy()
    df_closed["Yatırılan Tutar"] = df_closed["Lot"] * df_closed["Maliyet"]
    df_closed["Satış Tutarı"] = df_closed["Lot"] * df_closed["Satış Fiyatı"]
    df_closed["Gerçekleşen Kar/Zarar"] = df_closed["Satış Tutarı"] - df_closed["Yatırılan Tutar"]
    df_closed["Kar/Zarar (%)"] = (df_closed["Gerçekleşen Kar/Zarar"] / df_closed["Yatırılan Tutar"]) * 100

    return df_open, df_closed

# ---------------------------------------------------------------------------
# 📂 Sidebar – File selection & controls
# ---------------------------------------------------------------------------
st.sidebar.header("⚙️ Ayarlar")

def_path_log = Path("data/performans_log.xlsx")
log_file = st.sidebar.file_uploader(
    "Performans logu (performans_log.xlsx)",
    type=["xlsx"],
    accept_multiple_files=False,
    key="log_uploader",
)

log_path: Path | str = log_file if log_file else def_path_log


def_path_port = Path("data/portfoy_verisi.xlsx")
port_file = st.sidebar.file_uploader(
    "Portföy verisi (portfoy_verisi.xlsx)",
    type=["xlsx"],
    accept_multiple_files=False,
    key="port_uploader",
)

port_path: Path | str = port_file if port_file else def_path_port

page = st.sidebar.radio("Sayfa Seç", ["Performans", "Portföy Analizi"])

# ---------------------------------------------------------------------------
# 📊 PERFORMANS PANELİ
# ---------------------------------------------------------------------------
if page == "Performans":
    df_log = load_log(log_path)

    if df_log.empty:
        st.info("Veri bulunamadı veya dosya yüklenmedi.")
        st.stop()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Haftalık Getiri (%)")
        perf = weekly_performance(df_log)
        if perf.empty:
            st.warning("Haftalık performans hesaplanamadı.")
        else:
            st.dataframe(perf, hide_index=True)
            colors = ["green" if x > 0 else "red" for x in perf["Getiri (%)"]]
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.bar(perf["Hisse"], perf["Getiri (%)"], color=colors)
            ax.axhline(0, color="grey", linestyle="--", lw=1)
            ax.set_ylabel("%")
            ax.set_title("Toplam Getiri (7g)")
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            st.pyplot(fig)

    with col2:
        st.subheader("Sharpe Oranı (yıllıklaştırılmış)")
        sharpe = sharpe_ratio(df_log)
        if sharpe.empty:
            st.warning("Sharpe oranı hesaplanamadı.")
        else:
            st.dataframe(
                sharpe[["Hisse", "Sharpe_oran", "n"]].rename(
                    columns={"Sharpe_oran": "Sharpe", "n": "Gözlem"}
                ),
                hide_index=True,
            )
            fig, ax = plt.subplots(figsize=(6, 4))
            colors = ["green" if x > 0 else "red" for x in sharpe["Sharpe_oran"]]
            ax.bar(sharpe["Hisse"], sharpe["Sharpe_oran"], color=colors)
            ax.axhline(0, color="grey", linestyle="--", lw=1)
            ax.set_ylabel("Sharpe")
            ax.set_title("Sharpe Oranı")
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            st.pyplot(fig)

    st.divider()
    st.subheader("Zaman Serisi – Portföy Değeri")
    fig, ax = plt.subplots(figsize=(12, 4))
    for hisse, grp in df_log.groupby("Hisse"):
        ax.plot(grp["Tarih"], grp["Değer"], label=hisse)
    ax.legend(ncol=5, fontsize="small")
    ax.set_ylabel("TL")
    ax.set_xlabel("")
    ax.grid(True, axis="y", linestyle="--", lw=0.5)
    st.pyplot(fig)

# ---------------------------------------------------------------------------
# 💼 PORTFÖY ANALİZİ
# ---------------------------------------------------------------------------
else:
    df_port = load_portfolio(port_path)
    if df_port.empty:
        st.info("Portföy verisi bulunamadı veya dosya yüklenmedi.")
        st.stop()
    # ---- Güncel Fiyatı performans_log.xlsx'den al ----------------------------
    latest_prices = latest_prices_from_log(log_path)

    # Tablodaki fiyatı log verisiyle güncelle; logda yoksa eski fiyat korunur
    df_port["Güncel Fiyat"] = (
        df_port["Hisse"]
        .map(latest_prices)
        .fillna(df_port["Güncel Fiyat"])
    )
    df_open, df_closed = enrich_portfolio(df_port)

    # ---- Değer Hisseleri – Açık ----
    st.subheader("🟢 Değer Hisseleri – Açık Pozisyonlar")
    if df_open.empty:
        st.info("Açık değer hissesi pozisyonu yok.")
    else:
        st.dataframe(
            df_open[
                [
                    "Hisse",
                    "Lot",
                    "Maliyet",
                    "Güncel Fiyat",
                    "Kar/Zarar",
                    "Kar/Zarar (%)",
                    "Graham Skoru",
                ]
            ].round(2),
            hide_index=True,
        )
        fig, ax = plt.subplots(figsize=(8, 4))
        colors = ["green" if x > 0 else "red" for x in df_open["Kar/Zarar"]]
        ax.scatter(df_open["Graham Skoru"], df_open["Kar/Zarar"], c=colors)
        ax.set_xlabel("Graham Skoru")
        ax.set_ylabel("Kar/Zarar (TL)")
        ax.set_title("Graham Skoru vs Kar/Zarar – Açık Pozisyonlar")
        st.pyplot(fig)

    st.divider()

    # ---- Değer Hisseleri – Kapalı ----
    st.subheader("📘 Değer Hisseleri – Satışı Yapılmış Pozisyonlar")
    if df_closed.empty:
        st.info("Satılmış değer hissesi pozisyonu yok.")
    else:
        st.dataframe(
            df_closed[
                [
                    "Hisse",
                    "Lot",
                    "Maliyet",
                    "Satış Fiyatı",
                    "Gerçekleşen Kar/Zarar",
                    "Kar/Zarar (%)",
                ]
            ].round(2),
            hide_index=True,
        )
        fig, ax = plt.subplots(figsize=(8, 4))
        colors = ["green" if x > 0 else "red" for x in df_closed["Gerçekleşen Kar/Zarar"]]
        ax.bar(df_closed["Hisse"], df_closed["Gerçekleşen Kar/Zarar"], color=colors)
        ax.set_ylabel("TL")
        ax.set_title("Net Kar/Zarar – Satılmış Değer Hisseleri")
        st.pyplot(fig)

        # ---- Fon/Spekülatif – Genel ----
        st.divider()
        st.subheader("🟡 Fon / Spekülatif Varlıklar")

        # classify on the fly – no extra column needed
        df_fon = df_port[df_port["Graham Skoru"].isna()].copy()   # ← changed line

        if df_fon.empty:
            st.info("Fon/spekülatif varlık pozisyonu yok.")
        else:
            st.dataframe(df_fon.round(2), hide_index=True)
            fig, ax = plt.subplots(figsize=(8, 4))
            colors = ["green" if x > 0 else "red" for x in df_fon["Kar / Zarar"].fillna(0)]
            ax.bar(df_fon["Hisse"], df_fon["Kar / Zarar"].fillna(0), color=colors)
            ax.set_ylabel("TL")
            ax.set_title("Fon / Spekülatif – Kar/Zarar")
            st.pyplot(fig)

# ---------------------------------------------------------------------------
# 📑 Footer
# ---------------------------------------------------------------------------
st.caption("Bu sayfa Jupyter notebook’lardan Streamlit’e otomatik olarak taşındı. 🔥")
