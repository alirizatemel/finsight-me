import streamlit as st  # type: ignore
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt  # type: ignore
from modules.data_loader import load_financial_data
from modules.scores import (
    calculate_scores,
    show_company_scorecard,
    period_order,
    fcf_detailed_analysis,
    fcf_detailed_analysis_plot,
    fcf_yield_time_series,
    monte_carlo_dcf_simple
)
from config import RADAR_XLSX

def latest_common_period(balance, income, cashflow):
    bal_periods = {c for c in balance.columns if "/" in c}
    inc_periods = {c for c in income.columns  if "/" in c}
    cf_periods  = {c for c in cashflow.columns if "/" in c}
    return sorted(bal_periods & inc_periods & cf_periods,
                  key=period_order, reverse=True)

# --- yeni, önerilen yöntem -----------------------
params = st.query_params          # doğrudan Mapping[str, str]
default_symbol = params.get("symbol", "").upper()

@st.cache_data(show_spinner=False)
def get_scores_cached(symbol, radar_row, balance, income, cashflow, curr, prev):
    return calculate_scores(symbol, radar_row, balance, income, cashflow, curr, prev)

@st.cache_data(show_spinner=False)
def get_financials(symbol: str):
    """Load balance, income, and cash‑flow sheets for a single ticker."""
    return load_financial_data(symbol)

@st.cache_data(show_spinner=False)
def get_radar() -> pd.DataFrame:
    """Read the pre‑built fintables_radar Excel once and cache it."""
    df = pd.read_excel(RADAR_XLSX)
    df["Şirket"] = df["Şirket"].str.strip()
    return df

def format_scores_for_clipboard(data: dict) -> str:
    s = data["scores"]
    lines = [
        f"**Şirket:** {data['company']}",
        f"**Dönem:** {data['periods']['current']}  (önceki: {data['periods']['previous']})",
        "",
        f"**Piotroski F‑Score:** {s['piotroski_card']}",
        "\n".join(f"- {k}: {'✅' if v=='✅' else '❌'}" for k, v in s["piotroski_detail"].items()),
        "",
        f"**Beneish M‑Skor:** {s['beneish_card']} ({s['beneish']:+.2f})",
        *[f"- {line}" for line in s["beneish_lines"]],
        "",
        f"**Graham Skoru:** {s['graham']} / 5",
        *[f"- {line}" for line in s["graham_lines"]],
        "",
        f"**Peter Lynch Skoru:** {s['lynch']} / 3",
        *[f"- {line}" for line in s["lynch_lines"]],
    ]
    return "\n".join(lines)

def main():
    st.title("📈 Tek Hisse Finans Skor Kartı")

    # Kullanıcı girişi
    symbol = st.text_input("Borsa Kodu", default_symbol).strip().upper()
    if not symbol:
        st.info("Lütfen geçerli bir borsa kodu girin.")
        st.stop()

    # Finansalları yükle
    try:
        balance, income, cashflow = get_financials(symbol)
    except FileNotFoundError:
        st.error(f"{symbol} verileri bulunamadı.")
        st.stop()

    # --- DÖNEM KONTROLÜ ------------------------------------------
    periods = latest_common_period(balance, income, cashflow)
    if len(periods) < 2:
        st.error("Üç temel tabloda da en az iki ortak dönem lazım.")
        st.stop()

    curr, prev = periods[:2]          # en yeni ve bir önceki
    st.info(f"🔎 Kullanılan son bilanço dönemi: **{curr}**")

    # Radar satırı
    radar_df = get_radar()
    radar_row = radar_df[radar_df["Şirket"] == symbol]
    if radar_row.empty:
        st.warning("Radar verisi bulunamadı; bazı skorlar eksik hesaplanabilir.")

    # Analiz başlatma kontrolü
    if "analyze" not in st.session_state:
        st.session_state.analyze = False

    if st.button("Analiz Et"):
        st.session_state.analyze = True

    if st.session_state.analyze:
        scores = get_scores_cached(symbol, radar_row, balance, income, cashflow, curr, prev)

        # Özet metrikler
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Piotroski F-Skor", f"{scores['f_score']} / 9")
            st.caption("🟢 Sağlam" if scores["f_score"] >= 7 else "🟡 Orta" if scores["f_score"] >= 4 else "🔴 Zayıf")

            mskor = scores["m_skor"]
            st.metric("Beneish M-Skor", f"{mskor:.2f}" if mskor is not None else "-")
            st.caption("🟢 Güvenilir" if mskor is not None and mskor < -2.22 else "🔴 Riskli")

        with col2:
            st.metric("Graham Skor", f"{scores['graham_skor']} / 5")
            st.caption("🟢 Güçlü" if scores["graham_skor"] >= 4 else "🟡 Sınırlı" if scores["graham_skor"] == 3 else "🔴 Zayıf")

            st.metric("Peter Lynch Skor", f"{scores['lynch_skor']} / 3")
            st.caption("🟢 Sağlam" if scores["lynch_skor"] == 3 else "🟡 Orta" if scores["lynch_skor"] == 2 else "🔴 Zayıf")


        # Sekmeler
        tab_score, tab_fcf, tab_valuation, tab_raw = st.tabs(["📊 Skor Detayları", "🔍 FCF Analizi", "⚖️ Değerleme", "🗂 Ham Veriler"])

        with tab_score:
            copy_details=show_company_scorecard(symbol, radar_row, curr, prev)

        with tab_fcf:
            st.subheader("FCF Detay Tablosu")
            df_fcf = fcf_detailed_analysis(symbol, radar_row)
            if df_fcf is not None:
                with st.expander("📊 FCF Detay Tablosu", expanded=False):
                    st.dataframe(df_fcf.style.format({"FCF Verimi (%)": "{:.2f}"}))

                st.subheader("FCF Verimi Grafiği")
                fcf_yield_time_series(symbol, radar_row)

                st.subheader("FCF + Satışlar + CAPEX Çoklu Grafik")
                fcf_detailed_analysis_plot(symbol, radar_row)
            else:
                st.info("FCF verileri hesaplanamadı veya eksik.")
        
        with tab_valuation:
            st.subheader("Monte Carlo Destekli DCF")

            # Son 12 ay FCF’i çek (yıllıklandırılmış)
            df_fcf = fcf_detailed_analysis(symbol, radar_row)
            if df_fcf is None or df_fcf.empty:
                st.info("FCF verileri eksik.")
                st.stop()

            # --- trailing-12-month FCF (TTM) ------------------------------------
            if len(df_fcf) >= 4:
                last_fcf = df_fcf["FCF"].iloc[-4:].sum()   # TTM: son 4 çeyrek toplamı
            else:
                last_fcf = df_fcf["FCF"].iloc[-1]          # fallback: tek dönem

            if last_fcf <= 0:
                st.warning("Son FCF negatif veya sıfır, değerleme anlamsız.")
                st.stop()

            # Kontroller
            col1, col2 = st.columns(2)
            with col1:
                wacc_mu = st.slider("Ortalama WACC (%)", 5.0, 25.0, 15.0, 0.5) / 100
                g_mu    = st.slider("Terminal Büyüme (%)", 0.0, 10.0, 4.0, 0.1) / 100
            with col2:
                n_sims = st.number_input(
                    "Simülasyon Sayısı",
                    min_value=1000,
                    max_value=50000,
                    value=10000,
                    step=1000,
                    format="%d",          # opsiyonel: tam sayı formatı
                )
                years  = st.slider("Projeksiyon Yılı", 3, 10, 5)

            sim_vals = monte_carlo_dcf_simple(
                last_fcf,
                forecast_years=years,
                n_sims=int(n_sims),
                wacc_mu=wacc_mu, g_mu=g_mu,
            )

            # Sonuçları göster
            intrinsic = np.median(sim_vals)
            st.metric("Medyan İçsel Değer (TL)", f"{intrinsic:,.0f}")

            # --- convert EV → intrinsic value per share -------------------------------
            cur_price = radar_row.get("Son Fiyat", pd.Series(dtype=float)).iat[0] \
                        if "Son Fiyat" in radar_row else None

            market_cap = radar_row.get("Piyasa Değeri", pd.Series(dtype=float)).iat[0] \
                        if "Piyasa Değeri" in radar_row else None

            if cur_price and market_cap and market_cap > 0:
                shares_out = market_cap / cur_price                 # float shares
                intrinsic_ps = intrinsic / shares_out               # per-share value

                st.metric("Medyan İçsel Değer (TL / Hisse)",
                        f"{intrinsic_ps:,.2f}")

                premium = (intrinsic_ps - cur_price) / cur_price * 100
                
                st.caption(f"🎯 Mevcut fiyat {cur_price:,.2f} TL — "
                        f"potansiyel {premium:+.1f}%")
            else:
                # fallback: show company-wide value
                st.metric("Medyan İçsel Değer (TL)",
                        f"{intrinsic:,.0f}")


            fig, ax = plt.subplots(figsize=(7,4))
            ax.hist(sim_vals, bins=50)
            ax.set_xlabel("İçsel Değer (TL)")
            ax.set_ylabel("Sıklık")
            ax.set_title(f"{n_sims:,} Senaryoda Değer Dağılımı")
            st.pyplot(fig)


        with tab_raw:
            st.expander("Bilanço").dataframe(balance)
            st.expander("Gelir Tablosu").dataframe(income)
            st.expander("Nakit Akış Tablosu").dataframe(cashflow)
        # ------------------------------------------------------------------
        # 📋 2) add the “Skorları Kopyala” button in your main() just after
        #        the metrics are rendered (still inside the if st.session_state.analyze block)
        # ------------------------------------------------------------------
        with st.container():  # keeps things visually grouped
            st.markdown(f"📋 Skor Kartı")
            with st.expander("⬇️ kopyalamak için tıkla", expanded=False):
                clip_text = format_scores_for_clipboard(copy_details)
                # st.code comes with a built‑in copy icon since Streamlit 1.28
                st.code(clip_text, language="markdown")

if __name__ == "__main__":
    main()
