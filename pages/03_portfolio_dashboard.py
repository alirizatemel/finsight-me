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

from modules.utils_db import load_performance_log, load_active_portfolio_df

# ---------------------------------------------------------------------------
# ⏱ Page set‑up
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Portföy & Performans Dashboard",
    page_icon="📊",
    layout="wide",
)

PORTFOLIO_COL_MAP = {
    "hisse":        "Hisse",
    "lot":          "Lot",
    "maliyet":      "Maliyet",
    "alis_tarihi":  "Alış Tarihi",
    "satis_tarihi": "Satış Tarihi",
    "satis_fiyat":  "Satış Fiyatı",
    "notu":         "Not",
    "graham_skor":  "Graham Skoru",
    "mos":          "MOS",
}

st.title("📊 Portföy & Performans Dashboard")

# ---------------------------------------------------------------------------
# 🔧 Helper functions (taken & refactored from your notebooks)
# ---------------------------------------------------------------------------

# ------------------------------------------------------------------------
# Data loaders (cached)
# ------------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def load_log() -> pd.DataFrame:
    df = load_performance_log()
    if df.empty:
        return df
    df["Değer"] = df["lot"] * df["fiyat"]
    return df

@st.cache_data(show_spinner=False, ttl=3600)
def load_portfolio() -> pd.DataFrame:
    df = load_active_portfolio_df()
    df = df.rename(columns=PORTFOLIO_COL_MAP)
    return df


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
    df_sorted = df.sort_values(["hisse", "tarih"])
    latest = df_sorted.groupby("hisse").tail(1).set_index("hisse")["fiyat"]
    return latest

@st.cache_data(show_spinner=False)
def weekly_performance(df_log: pd.DataFrame, lookback_days: int = 7) -> pd.DataFrame:
    """Return % performance for the last *lookback_days* for each stock."""
    if df_log.empty:
        return pd.DataFrame()

    cutoff = df_log["tarih"].max() - timedelta(days=lookback_days)
    df_slice = df_log[df_log["tarih"] >= cutoff].copy()
    df_slice.sort_values(["hisse", "tarih"], inplace=True)
    first_prices = df_slice.groupby("hisse").first()["fiyat"]
    last_prices = df_slice.groupby("hisse").last()["fiyat"]
    perf = ((last_prices - first_prices) / first_prices * 100).round(2)
    return perf.reset_index(name="Getiri (%)")

@st.cache_data(show_spinner=False)
def sharpe_ratio(df_log: pd.DataFrame, risk_free_daily: float = 0.47 / 252) -> pd.DataFrame:
    if df_log.empty:
        return pd.DataFrame()

    df_sorted = df_log.sort_values(["hisse", "tarih"]).copy()
    df_sorted["Getiri"] = df_sorted.groupby("hisse")["fiyat"].pct_change()

    agg = df_sorted.groupby("hisse").agg(
        ort_getiri=("Getiri", "mean"),
        std=("Getiri", "std"),
        n=("Getiri", "count"),
    )
    agg["Sharpe_oran"] = ((agg["ort_getiri"] - risk_free_daily) / agg["std"]) * math.sqrt(252)
    agg = agg.reset_index()
    return agg

@st.cache_data(show_spinner=False)
def enrich_portfolio(df: pd.DataFrame):
    df = df.copy()

    # Açık pozisyonlar
    open_mask = df["Satış Fiyatı"].isna()
    df_open = df.loc[open_mask].copy()

    df_open["Yatırılan Tutar"] = df_open["Lot"] * df_open["Maliyet"]
    df_open["Anlık Değer"] = df_open["Lot"] * df_open["Güncel Fiyat"]
    df_open["Kar/Zarar"] = df_open["Anlık Değer"] - df_open["Yatırılan Tutar"]
    df_open["Kar/Zarar (%)"] = (df_open["Kar/Zarar"] /
                                df_open["Yatırılan Tutar"]) * 100

    # Kapalı pozisyonlar
    closed_mask = ~open_mask
    df_closed = df.loc[closed_mask].copy()

    df_closed["Yatırılan Tutar"] = df_closed["Lot"] * df_closed["Maliyet"]
    df_closed["Satış Tutarı"] = df_closed["Lot"] * df_closed["Satış Fiyatı"]
    df_closed["Gerçekleşen Kar/Zarar"] = (
        df_closed["Satış Tutarı"] - df_closed["Yatırılan Tutar"]
    )
    df_closed["Kar/Zarar (%)"] = (df_closed["Gerçekleşen Kar/Zarar"] /
                                  df_closed["Yatırılan Tutar"]) * 100

    return df_open, df_closed

# ---------------------------------------------------------------------------
# 📂 Sidebar – File selection & controls
# ---------------------------------------------------------------------------
st.sidebar.header("⚙️ Görünüm")


page = st.sidebar.radio("Sayfa Seç", ["Performans", "Portföy Analizi"])

# ---------------------------------------------------------------------------
# 📊 PERFORMANS PANELİ
# ---------------------------------------------------------------------------
if page == "Performans":
    df_log = load_log()

    if df_log.empty:
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
            ax.bar(perf["hisse"], perf["Getiri (%)"], color=colors)
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
                sharpe[["hisse", "Sharpe_oran", "n"]].rename(
                    columns={"Sharpe_oran": "Sharpe", "n": "Gözlem"}
                ),
                hide_index=True,
            )
            fig, ax = plt.subplots(figsize=(6, 4))
            colors = ["green" if x > 0 else "red" for x in sharpe["Sharpe_oran"]]
            ax.bar(sharpe["hisse"], sharpe["Sharpe_oran"], color=colors)
            ax.axhline(0, color="grey", linestyle="--", lw=1)
            ax.set_ylabel("Sharpe")
            ax.set_title("Sharpe Oranı")
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            st.pyplot(fig)

    st.divider()
    st.subheader("Zaman Serisi – Portföy Değeri")
    fig, ax = plt.subplots(figsize=(12, 4))
    for hisse, grp in df_log.groupby("hisse"):
        ax.plot(grp["tarih"], grp["Değer"], label=hisse)
    ax.legend(ncol=5, fontsize="small")
    ax.set_ylabel("TL")
    ax.set_xlabel("")
    ax.grid(True, axis="y", linestyle="--", lw=0.5)
    st.pyplot(fig)

# ---------------------------------------------------------------------------
# 💼 PORTFÖY ANALİZİ (DAHA SAĞLAM HALE GETİRİLMİŞ VERSİYON)
# ---------------------------------------------------------------------------
else:
    df_port = load_portfolio()
    if df_port.empty:
        st.info("Portföy verisi bulunamadı.")
        st.stop()

    # Güncel fiyatları performans_log’tan çek
    log_df = load_log()
    if not log_df.empty:
        latest_prices = (
            log_df.sort_values(["hisse", "tarih"])
            .groupby("hisse")
            .tail(1)
            .set_index("hisse")["fiyat"]
        )
        df_port["Güncel Fiyat"] = df_port["Hisse"].map(latest_prices)
    else:
        df_port["Güncel Fiyat"] = np.nan

    df_open, df_closed = enrich_portfolio(df_port)

    # --- Değer ve Fon hisselerini ayıralım (GÜVENLİK KONTROLÜ EKLENDİ) ---
    open_deger = pd.DataFrame()
    closed_deger = pd.DataFrame()

    # Eğer 'Graham Skoru' sütunu varsa, varlıkları buna göre ayır.
    if "Graham Skoru" in df_open.columns:
        open_deger = df_open[df_open["Graham Skoru"].notna()].copy()
        open_fon = df_open[df_open["Graham Skoru"].isna()].copy()
    else:
        # Sütun hiç yoksa, tüm açık pozisyonlar fon/spekülatif kabul edilir.
        st.warning("`Graham Skoru` sütunu portföy verisinde bulunamadı. Tüm varlıklar 'Fon / Spekülatif' olarak sınıflandırıldı.")
        open_fon = df_open.copy()

    if "Graham Skoru" in df_closed.columns:
        closed_deger = df_closed[df_closed["Graham Skoru"].notna()].copy()
        closed_fon = df_closed[df_closed["Graham Skoru"].isna()].copy()
    else:
        # Sütun hiç yoksa, tüm kapalı pozisyonlar fon/spekülatif kabul edilir.
        closed_fon = df_closed.copy()
    # ---------------------------------------------------------------------

    # ---- Değer Hisseleri – Açık ----
    st.subheader("🟢 Değer Hisseleri – Açık Pozisyonlar")
    if open_deger.empty:
        st.info("Açık değer hissesi pozisyonu yok.")
    else:
        display_cols = [
            "Hisse", "Lot", "Maliyet", "Güncel Fiyat",
            "Kar/Zarar", "Kar/Zarar (%)", "Graham Skoru",
        ]
        st.dataframe(open_deger[display_cols].round(2), hide_index=True)
        
        plot_data = open_deger.dropna(subset=['Güncel Fiyat', 'Kar/Zarar', 'Graham Skoru'])
        if not plot_data.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            colors = ["green" if x > 0 else "red" for x in plot_data["Kar/Zarar"]]
            ax.scatter(plot_data["Graham Skoru"], plot_data["Kar/Zarar"], c=colors)
            ax.set_xlabel("Graham Skoru")
            ax.set_ylabel("Kar/Zarar (TL)")
            ax.set_title("Graham Skoru vs Kar/Zarar – Açık Pozisyonlar")
            st.pyplot(fig)

    st.divider()

    # ---- Değer Hisseleri – Kapalı ----
    st.subheader("📘 Değer Hisseleri – Satışı Yapılmış Pozisyonlar")
    if closed_deger.empty:
        st.info("Satılmış değer hissesi pozisyonu yok.")
    else:
        st.dataframe(
            closed_deger[
                [
                    "Hisse", "Lot", "Maliyet", "Satış Fiyatı",
                    "Gerçekleşen Kar/Zarar", "Kar/Zarar (%)",
                ]
            ].round(2),
            hide_index=True,
        )
        fig, ax = plt.subplots(figsize=(8, 4))
        colors = ["green" if x > 0 else "red" for x in closed_deger["Gerçekleşen Kar/Zarar"]]
        ax.bar(closed_deger["Hisse"], closed_deger["Gerçekleşen Kar/Zarar"], color=colors)
        ax.set_ylabel("TL")
        ax.set_title("Net Kar/Zarar – Satılmış Değer Hisseleri")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        st.pyplot(fig)

    st.divider()

    # ---- Fon/Spekülatif – Genel ----
    st.subheader("🟡 Fon / Spekülatif Varlıklar")
    df_fon_all = pd.concat([open_fon, closed_fon], ignore_index=True)

    if df_fon_all.empty:
        st.info("Fon/spekülatif varlık pozisyonu yok.")
    else:
        display_cols = [
            "Hisse", "Lot", "Maliyet", "Güncel Fiyat", "Satış Fiyatı",
            "Kar/Zarar", "Gerçekleşen Kar/Zarar"
        ]
        # Sadece var olan sütunları göster
        display_cols_exist = [col for col in display_cols if col in df_fon_all.columns]
        st.dataframe(df_fon_all[display_cols_exist].round(2), hide_index=True)

        df_fon_all['Net Kar/Zarar'] = df_fon_all['Kar/Zarar'].fillna(df_fon_all['Gerçekleşen Kar/Zarar']).fillna(0)
        
        if not df_fon_all.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            colors = ["green" if x > 0 else "red" for x in df_fon_all["Net Kar/Zarar"]]
            ax.bar(df_fon_all["Hisse"], df_fon_all["Net Kar/Zarar"], color=colors)
            ax.set_ylabel("TL")
            ax.set_title("Fon / Spekülatif – Net Kar/Zarar")
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            st.pyplot(fig)
# ---------------------------------------------------------------------------
# 📑 Footer
# ---------------------------------------------------------------------------
st.caption("Bu sayfa Jupyter notebook’lardan Streamlit’e otomatik olarak taşındı. 🔥")
