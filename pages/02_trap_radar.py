"""Streamlit page - 🚨 Tuzak Radar (Value-Trap Scanner)

Finansal Radar altyapısını temel alarak, her BIST şirketi için:
• Piotroski F, Beneish M, Graham ve Peter Lynch temel skorlarını hesaplar
• Son 12 ay FCF üzerinden Monte-Carlo DCF (tek-aşamalı) medyan içsel değeri bulur
• Piyasa değerine göre Margin-of-Safety (MOS) çıkartır
• MOS eşiğini geçen en iyi 15 hisselik tablo + grafik gösterir
• Eksik veri / hata kayıtlarını “Loglar” bölümünde listeler
"""

import streamlit as st  # type: ignore
import pandas as pd
from streamlit import column_config as cc  # type: ignore
from datetime import datetime
from modules.data_loader import load_financial_data
from modules.scoring.beneish import BeneishScorer
from modules.scoring.graham import GrahamScorer
from modules.scoring.lynch import LynchScorer
from modules.scoring.piotroski import PiotroskiScorer
from modules.scores import (
    period_order
)
from modules.utils_db import scores_table_empty, load_scores_df, save_scores_df
from modules.scanner import run_scan 
from config import RADAR_XLSX


# ──────────────────────────────────────────────────────────────────────────────
# Yardımcılar
# ──────────────────────────────────────────────────────────────────────────────

def latest_common_period(balance: pd.DataFrame, income: pd.DataFrame, cash: pd.DataFrame) -> list[str]:
    """En yeni→eski, üç tabloda da ortak dönem isimleri (yyyy/mm)."""
    bal = {c for c in balance.columns if "/" in c}
    inc = {c for c in income.columns  if "/" in c}
    cf  = {c for c in cash.columns    if "/" in c}
    return sorted(bal & inc & cf, key=period_order, reverse=True)

# ──────────────────────────────────────────────────────────────────────────────
# Cache’li yükleyiciler – Financial Radar ile aynı mantık
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def load_radar() -> pd.DataFrame:
    df = pd.read_excel(RADAR_XLSX)
    df["Şirket"] = df["Şirket"].str.strip()
    return df

@st.cache_data(show_spinner=False)
def get_financials(company: str):
    """(balance, income, cash) dataframes."""
    return load_financial_data(company)

# ──────────────────────────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    st.title("🚨 Tuzak Radar - Top 15")
    st.caption("Finansal Radar taramasından türetilmiş, **margin-of-safety** odaklı fırsat/tuzak listesi.")

    radar = load_radar()

    with st.sidebar:
        st.header("Tarama Ayarları")
        years   = st.slider("Projeksiyon Yılı", 3, 10, 5)
        n_sims  = st.number_input("Simülasyon Sayısı", 1000, 50000, 10000, step=1000, format="%d")

        min_mos     = st.slider("Minimum MOS (%)",      -50, 100, 20) / 100
        min_fscore  = st.slider("Minimum F-Skor",       0,   9,  5)
        min_graham  = st.slider("Minimum Graham Skoru", 0,   5,  2)
        min_lynch   = st.slider("Minimum Lynch Skoru",  0,   3,  2)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Veritabanından Yükle"):
                st.session_state.scan = True
                st.session_state.force_refresh = False   # sadece oku
        with col2:
            if st.button("Skorları Yenile"):
                st.session_state.scan = True
                st.session_state.force_refresh = True    # mutlaka hesapla

    if st.session_state.get("scan"):
        if scores_table_empty("radar_scores") or st.session_state.get("force_refresh"):
            st.info("📊 Skorlar hesaplanıyor, veritabanı güncelleniyor…")
            df, logs, counters = run_scan(radar, years, int(n_sims))
            if not df.empty:
                save_scores_df(df, table="radar_scores")
        else:
            st.success("📁 Skorlar veritabanından yüklendi.")
            df = load_scores_df(table="radar_scores")
            logs, counters = [], {}

        # Loglar
        with st.expander(f"🪵 Loglar ({len(logs)})"):
            for line in logs:
                st.text(line)
            st.write("**Elenme istatistikleri**", counters)

        if df.empty:
            st.info("Filtreni̇ geçecek şirket bulunamadı. MOS eşiğini düşür veya veri setini güncelle.")
            return

        top15 = df[
            (df["MOS"]    >= min_mos) &
            (df["F-Skor"] >= min_fscore) &
            (df["Graham"] >= min_graham) &
            (df["Lynch"]  >= min_lynch)
        ].head(50)
        st.subheader(f"En İyi {len(top15)} Hisse (MOS ≥ {min_mos:.0%})")
        st.dataframe(
            top15.style
                 .format({
                     "İçsel Değer (Medyan)": "{:,.0f}",
                     "Piyasa Değeri":        "{:,.0f}",
                     "MOS":                  "{:.1%}",
                 })
                 .set_properties(subset=["M-Skor"], **{"text-align": "right"})
                 .background_gradient(subset=["MOS"], cmap="RdYlGn")
        )
        st.bar_chart(top15.set_index("Şirket")["MOS"])
        if "timestamp" in df.columns and not df.empty:
            last_upd = pd.to_datetime(df["timestamp"]).max()
            st.caption(f"🕑 Son güncelleme: {last_upd:%Y‑%m‑%d %H:%M}")

if __name__ == "__main__":
    main()
