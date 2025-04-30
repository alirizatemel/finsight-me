"""Streamlit page – 🚨 Tuzak Radar (Value‑Trap Scanner)

Finansal Radar altyapısını temel alarak, her BIST şirketi için:
• Piotroski F, Beneish M, Graham ve Peter Lynch temel skorlarını hesaplar
• Son 12 ay FCF üzerinden Monte‑Carlo DCF (tek‑aşamalı) medyan içsel değeri bulur
• Piyasa değerine göre Margin‑of‑Safety (MOS) çıkartır
• MOS eşiğini geçen en iyi 15 hisselik tablo + grafik gösterir
• Eksik veri / hata kayıtlarını “Loglar” bölümünde listeler
"""

import streamlit as st  # type: ignore
import pandas as pd
import numpy as np
from streamlit import column_config as cc
import traceback 
from modules.utils import safe_float
from modules.data_loader import load_financial_data
from modules.scores import (
    calculate_piotroski_f_score,
    calculate_beneish_m_score,
    graham_score_card,
    peter_lynch_score_card,
    monte_carlo_dcf_simple,
    period_order,
)

RADAR_XLSX = "companies/fintables_radar.xlsx"

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

            # 🔹 FCF (son 4 çeyrek)
            cf = cash.set_index("Kalem")
            if "İşletme Faaliyetlerinden Nakit Akışları" not in cf.index:
                raise ValueError("fcf verisi eksik")
            ofcf = cf.loc["İşletme Faaliyetlerinden Nakit Akışları"]
            capex_key = (
                "Maddi ve Maddi Olmayan Duran Varlık Alımları"
                if "Maddi ve Maddi Olmayan Duran Varlık Alımları" in cf.index
                else "Yatırım Faaliyetlerinden Kaynaklanan Nakit Akışları"
            )
            capex = cf.loc[capex_key]
            fcf_series = ofcf - capex
            if fcf_series.tail(4).isna().all():
                raise ValueError("fcf verisi eksik")
            last_fcf = fcf_series.tail(4).sum()
            if last_fcf <= 0:
                raise ValueError("fcf negatif")

            intrinsic = np.median(
                monte_carlo_dcf_simple(last_fcf, forecast_years=forecast_years, n_sims=n_sims)
            )

            market_cap = safe_float(row.get("Piyasa Değeri"))
            if pd.isna(market_cap) or market_cap <= 0:
                raise ValueError("piyasa değeri yok")

            mos = (intrinsic - market_cap) / intrinsic

            records.append({
                "Şirket": c,
                "F-Skor": f_score,
                "M-Skor": m_score,
                "Graham": graham,
                "Lynch":  lynch,
                "İçsel Değer (Medyan)": intrinsic,
                "Piyasa Değeri":        market_cap,
                "MOS": mos,
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
    if "MOS" in df.columns:
        df.sort_values("MOS", ascending=False, inplace=True)

    return df, logs, counters

# ──────────────────────────────────────────────────────────────────────────────
# UI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    st.title("🚨 Tuzak Radar – Top 15")
    st.caption("Finansal Radar taramasından türetilmiş, **margin‑of‑safety** odaklı fırsat/tuzak listesi.")

    radar = load_radar()

    with st.sidebar:
        st.header("Tarama Ayarları")
        years   = st.slider("Projeksiyon Yılı", 3, 10, 5)
        n_sims  = st.number_input("Simülasyon Sayısı", 1000, 50000, 10000, step=1000, format="%d")
        min_mos = st.slider("Minimum MOS (%)", 0, 100, 20) / 100
        if st.button("Tarama Başlat"):
            st.session_state.scan = True

    if st.session_state.get("scan"):
        df, logs, counters = run_scan(radar, years, int(n_sims))

        # Loglar
        with st.expander(f"🪵 Loglar ({len(logs)})"):
            for line in logs:
                st.text(line)
            st.write("**Elenme istatistikleri**", counters)

        if df.empty:
            st.info("Filtreni̇ geçecek şirket bulunamadı. MOS eşiğini düşür veya veri setini güncelle.")
            return

        top15 = df[df["MOS"] >= min_mos].head(15)
        st.subheader(f"En İyi {len(top15)} Hisse (MOS ≥ {min_mos:.0%})")
        st.dataframe(
            top15.style
                 .format({
                     "İçsel Değer (Medyan)": "{:,.0f}",
                     "Piyasa Değeri":        "{:,.0f}",
                     "MOS":                  "{:.1%}",
                 })
                 .background_gradient(subset=["MOS"], cmap="RdYlGn")
        )
        st.bar_chart(top15.set_index("Şirket")["MOS"])

if __name__ == "__main__":
    main()
