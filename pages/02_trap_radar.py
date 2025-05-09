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
import numpy as np
from streamlit import column_config as cc  # type: ignore
import traceback 
from datetime import datetime
from modules.data_loader import load_financial_data
from modules.scores import (
    calculate_piotroski_f_score,
    calculate_beneish_m_score,
    graham_score_card,
    peter_lynch_score_card,
    monte_carlo_dcf_simple,
    period_order,
    fcf_detailed_analysis
)
from modules.utils_db import engine, scores_table_empty, load_scores_df, save_scores_df
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
# Ana tarama fonksiyonu
# ──────────────────────────────────────────────────────────────────────────────

def run_scan(radar: pd.DataFrame, forecast_years: int, n_sims: int):
    records, logs = [], []
    counters = {"dönem": 0, "fcf": 0, "piyasa": 0, "diğer": 0}

    companies = radar["Şirket"].dropna().unique()
    total = len(companies)
    progress = st.progress(0.0, text="Tarama başlıyor…")

    for i, c in enumerate(companies, 1):
        try:
            row = radar[radar["Şirket"] == c]
            bal, inc, cash = get_financials(c)

            # 🔹 ortak dönem seçimi
            periods = latest_common_period(bal, inc, cash)
            if len(periods) < 2:
                raise ValueError("ortak dönem yok")
            curr, prev = periods[:2]

            # 🔹 temel skorlar
            f_score, _ = calculate_piotroski_f_score(row, bal, inc, curr, prev)
            m_score    = calculate_beneish_m_score(c, bal, inc, cash, curr, prev)
            graham, *_ = graham_score_card(row)
            lynch , *_ = peter_lynch_score_card(row)

            # Son 12 ay FCF’i çek (yıllıklandırılmış)
            df_fcf = fcf_detailed_analysis(c, row)
            if df_fcf is None or df_fcf.empty:
                raise ValueError("FCF verileri eksik.")

            # --- trailing-12-month FCF (TTM) ------------------------------------
            if len(df_fcf) >= 4:
                last_fcf = df_fcf["FCF"].iloc[-4:].sum()   # TTM: son 4 çeyrek toplamı
            else:
                last_fcf = df_fcf["FCF"].iloc[-1]          # fallback: tek dönem

            if last_fcf <= 0:
                raise ValueError("Son FCF negatif veya sıfır, değerleme anlamsız.")

            intrinsic = np.median(
                monte_carlo_dcf_simple(last_fcf, forecast_years=forecast_years, n_sims=n_sims)
            )
            
            # --- convert EV → intrinsic value per share -------------------------------
            cur_price = row.get("Son Fiyat", pd.Series(dtype=float)).iat[0] \
                        if "Son Fiyat" in row else None

            market_cap = row.get("Piyasa Değeri", pd.Series(dtype=float)).iat[0] \
                        if "Piyasa Değeri" in row else None

            if cur_price and market_cap and market_cap > 0:
                
                shares_out = market_cap / cur_price                 # float shares
                intrinsic_ps = intrinsic / shares_out               # per-share value
                premium = (intrinsic_ps - cur_price) / cur_price

                records.append({
                    "Şirket": c,
                    "F-Skor": f_score,
                    "M-Skor": f"{round(m_score, 2)} ⚠️" if m_score > -2.22 else f"{round(m_score, 2)}",
                    "Graham": graham,
                    "Lynch":  lynch,
                    "İçsel Değer (Medyan)": intrinsic,
                    "Piyasa Değeri":        market_cap,
                    "MOS": premium,
                })

        except ValueError as exc:
            msg = str(exc).lower()
            if "dönem" in msg:
                counters["dönem"] += 1
            elif "fcf" in msg:
                counters["fcf"] += 1
            elif "piyasa" in msg:
                counters["piyasa"] += 1
            else:
                counters["diğer"] += 1
            logs.append(f"{c}: {exc}\n↳ {traceback.format_exc(limit=2)}")  # <-- ek
        except Exception as exc:
            counters["diğer"] += 1
            logs.append(f"{c}: {exc}")
        finally:
            progress.progress(i / total, text=f"{i}/{total} tarandı…")

    progress.empty()

    df = pd.DataFrame.from_records(records)
    if not df.empty:
        df["timestamp"] = datetime.now()
    if "MOS" in df.columns:
        df.sort_values("MOS", ascending=False, inplace=True)

    return df, logs, counters

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
        if scores_table_empty() or st.session_state.get("force_refresh"):
            st.info("📊 Skorlar hesaplanıyor, veritabanı güncelleniyor…")
            df, logs, counters = run_scan(radar, years, int(n_sims))
            if not df.empty:
                save_scores_df(df)                     # TABLOYU YENİLE
        else:
            st.success("📁 Skorlar veritabanından yüklendi.")
            df = load_scores_df()
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
