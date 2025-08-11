# 03_portfolio_dashboard.py (HAFTALIK SHARPE ORANI HESAPLAMASI DÜZELTİLMİŞ)

from __future__ import annotations
import math
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

from modules.db.performance_log import load_performance_log
from modules.db.portfolio import load_active_portfolio_df

# --- 1. Sayfa Yapısı ve Başlık ---
st.set_page_config(page_title="Portföy & Performans Dashboard", page_icon="📊", layout="wide")
st.title("📊 Portföy & Performans Dashboard")

# --- 2. Veri Yükleme ve Hazırlık Fonksiyonları ---
@st.cache_data(ttl=900)
def load_data():
    df_log = load_performance_log()
    if not df_log.empty:
        df_log["Değer"] = df_log["lot"] * df_log["fiyat"]
        df_log["tarih"] = pd.to_datetime(df_log["tarih"])
        latest_prices = df_log.sort_values("tarih").groupby("hisse").tail(1).set_index("hisse")["fiyat"]
    else:
        latest_prices = pd.Series(dtype=float)
    df_portfolio = load_active_portfolio_df()
    df_portfolio["Güncel Fiyat"] = df_portfolio["hisse"].map(latest_prices)
    df_portfolio["alis_tarihi"] = pd.to_datetime(df_portfolio["alis_tarihi"])
    return df_log, df_portfolio

@st.cache_data
def enrich_portfolio(df: pd.DataFrame):
    df = df.copy()
    df["Yatırılan Tutar"] = df["lot"] * df["maliyet"]
    df["Anlık Değer"] = df["lot"] * df["Güncel Fiyat"]
    df["Kar/Zarar"] = df["Anlık Değer"] - df["Yatırılan Tutar"]
    df["Kar/Zarar (%)"] = (df["Kar/Zarar"] / df["Yatırılan Tutar"]) * 100
    df["Gün"] = (datetime.now() - df["alis_tarihi"]).dt.days
    return df

@st.cache_data
def calculate_performance_metrics(df_log: pd.DataFrame):
    if df_log.empty or len(df_log) < 2:
        return pd.DataFrame(), pd.DataFrame()
    
    seven_days_ago = df_log["tarih"].max() - timedelta(days=7)
    df_slice = df_log[df_log["tarih"] >= seven_days_ago].copy()
    first_prices = df_slice.groupby("hisse").first()["fiyat"]
    last_prices = df_slice.groupby("hisse").last()["fiyat"]
    weekly_perf = ((last_prices - first_prices) / first_prices * 100).round(2)
    weekly_perf = weekly_perf.reset_index(name="Getiri 7G (%)")

    df_sorted = df_log.sort_values(["hisse", "tarih"]).copy()
    df_sorted["Getiri"] = df_sorted.groupby("hisse")["fiyat"].pct_change()
    
    # --- DEĞİŞİKLİK 1: Risksiz faiz oranı haftalık hale getirildi ---
    risk_free_weekly = 0.47 / 52 
    
    agg = df_sorted.groupby("hisse").agg(ort_getiri=("Getiri", "mean"), std=("Getiri", "std"), n=("Getiri", "count"))
    
    # --- DEĞİŞİKLİK 2: Eşik 5'e düşürüldü ---
    agg = agg[agg['n'] > 5] 
    
    agg = agg[agg['std'].notna() & (agg['std'] != 0)]
    
    if not agg.empty:
        # --- DEĞİŞİKLİK 3: Yıllıklandırma faktörü haftalık veriye göre düzeltildi (sqrt(52)) ---
        agg["Sharpe Oranı"] = ((agg["ort_getiri"] - risk_free_weekly) / agg["std"]) * math.sqrt(52)
        sharpe_ratios = agg[["Sharpe Oranı"]].reset_index()
    else:
        sharpe_ratios = pd.DataFrame(columns=['hisse', 'Sharpe Oranı'])

    return weekly_perf, sharpe_ratios

# --- 3. Ana Sayfa Mantığı ---
# (KODUN GERİ KALANI BİR ÖNCEKİ İLE AYNI)
df_log, df_portfolio_raw = load_data()
if df_portfolio_raw.empty:
    st.info("Portföyde gösterilecek aktif pozisyon bulunamadı.")
    st.stop()
df_portfolio = enrich_portfolio(df_portfolio_raw)

st.subheader("Portföy Genel Bakış")
total_yatirim = df_portfolio["Yatırılan Tutar"].sum()
total_deger = df_portfolio["Anlık Değer"].sum()
total_kar_zarar = df_portfolio["Kar/Zarar"].sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Anlık Portföy Değeri", f"{total_deger:,.0f} TL", delta=f"{total_kar_zarar:,.0f} TL", help="Açık pozisyonların güncel piyasa değeridir. Delta, açık pozisyonlardaki toplam kar/zararı gösterir.")
col2.metric("Toplam Yatırım (Açık)", f"{total_yatirim:,.0f} TL")

if total_yatirim > 0:
    overall_return_pct = (total_kar_zarar / total_yatirim) * 100
    col3.metric("Toplam Getiri (%)", f"{overall_return_pct:.2f}%")
else:
    col3.metric("Toplam Getiri (%)", "N/A")

col4.metric("Gerçekleşen K/Z", "N/A", help="Bu metrik için satışı yapılmış pozisyonların veritabanından yüklenmesi gerekir.")
st.divider()

tab1, tab2 = st.tabs(["💼 Portföy Analizi", "📈 Performans Metrikleri"])

with tab1:
    st.subheader("Açık Pozisyonlar")
    col_config = {
        "hisse": st.column_config.TextColumn("Hisse"),
        "lot": st.column_config.NumberColumn("Lot"),
        "maliyet": st.column_config.NumberColumn("Maliyet", format="₺%.2f"),
        "Güncel Fiyat": st.column_config.NumberColumn("Güncel Fiyat", format="₺%.2f"),
        "Yatırılan Tutar": st.column_config.NumberColumn("Yatırım", format="₺%.0f"),
        "Anlık Değer": st.column_config.NumberColumn("Değer", format="₺%.0f"),
        "Kar/Zarar": st.column_config.NumberColumn("K/Z (TL)", format="₺%.0f"),
        "Kar/Zarar (%)": st.column_config.NumberColumn("K/Z (%)", format="%.2f%%"),
        "Gün": st.column_config.NumberColumn("Gün"),
    }
    display_cols = ["hisse", "lot", "maliyet", "Güncel Fiyat", "Yatırılan Tutar", "Anlık Değer", "Kar/Zarar", "Kar/Zarar (%)", "Gün"]
    st.dataframe(df_portfolio[display_cols], hide_index=True, use_container_width=True, column_config=col_config)
    st.subheader("Görselleştirmeler")
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        df_plot = df_portfolio.dropna(subset=['Anlık Değer'])
        if not df_plot.empty:
            fig, ax = plt.subplots()
            ax.pie(df_plot['Anlık Değer'], labels=df_plot['hisse'], autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
            ax.set_title("Varlık Dağılımı (Anlık Değere Göre)")
            st.pyplot(fig)
    with g_col2:
        df_plot = df_portfolio.dropna(subset=['Kar/Zarar'])
        if not df_plot.empty:
            fig, ax = plt.subplots()
            colors = ["g" if x > 0 else "r" for x in df_plot["Kar/Zarar"]]
            ax.bar(df_plot["hisse"], df_plot["Kar/Zarar"], color=colors)
            ax.axhline(0, color="grey", linestyle="--", lw=1)
            ax.set_ylabel("Kar/Zarar (TL)")
            ax.set_title("Açık Pozisyonlar Kar/Zarar Durumu")
            plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
            st.pyplot(fig)

with tab2:
    st.subheader("Hisse Performans Metrikleri")
    if df_log.empty:
        st.warning("Performans metriklerini hesaplamak için log verisi bulunamadı.")
    else:
        weekly_perf, sharpe_ratios = calculate_performance_metrics(df_log)
        perf_summary = pd.merge(weekly_perf, sharpe_ratios, on="hisse", how="outer")
        st.dataframe(perf_summary, hide_index=True, use_container_width=True)
        st.subheader("Zaman Serisi – Portföy Değeri")
        fig, ax = plt.subplots(figsize=(12, 4))
        pivot_df = df_log.pivot(index='tarih', columns='hisse', values='Değer').fillna(0)
        ax.stackplot(pivot_df.index, pivot_df.T, labels=pivot_df.columns)
        ax.legend(loc='upper left', ncol=math.ceil(len(pivot_df.columns)/2), fontsize="small")
        ax.set_ylabel("Portföy Değeri (TL)")
        ax.set_xlabel("")
        ax.grid(True, axis='y', linestyle='--', alpha=0.6)
        st.pyplot(fig)