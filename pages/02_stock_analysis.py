import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from modules.finance.data_loader import load_financial_data
from modules.scores import (
    calculate_scores,
    show_company_scorecard,
    fcf_detailed_analysis,
    fcf_detailed_analysis_plot,
    fcf_yield_time_series
)
from modules.finance.profitability import build_profitability_table, compute_net_profit_cagr
from modules.finance.dcf import monte_carlo_dcf_simple
from modules.utils import period_order

from modules.technical_analysis.cache_manager import get_price_df
from config import RADAR_XLSX
import pandas_ta as ta
from typing import Optional

@st.cache_data(show_spinner=False) # Üst fonksiyon zaten spinner gösteriyor
def apply_technical_filters(symbol: str, _df_price: pd.DataFrame) -> dict:
    """
    Fiyat verisi üzerinden teknik göstergeleri hesaplar.
    `10_tech_radar.py` dosyasından alınıp grafik için SMA'ları da döndürecek şekilde güncellendi.
    """
    df_price = _df_price.copy()
    if df_price.empty or "close" not in df_price:
        return {"RSI": np.nan, "Trend": "YOK", "SMA20": None, "SMA50": None}

    close = df_price["close"].dropna()
    if len(close) < 50:
        return {"RSI": np.nan, "Trend": "YETERSIZ VERI", "SMA20": None, "SMA50": None}

    rsi_val = ta.rsi(close, length=14).dropna()
    rsi = round(rsi_val.iloc[-1], 1) if not rsi_val.empty else np.nan

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    
    # DataFrame'e ekle
    df_price['SMA20'] = sma20
    df_price['SMA50'] = sma50

    trend = "YOK"
    try:
        prev_sma20 = sma20.iloc[-2]
        prev_sma50 = sma50.iloc[-2]
        curr_sma20 = sma20.iloc[-1]
        curr_sma50 = sma50.iloc[-1]

        if prev_sma20 < prev_sma50 and curr_sma20 > curr_sma50:
            trend = "🔁 TREND DÖNÜŞÜ (Al Sinyali)"
        elif curr_sma20 > curr_sma50:
            trend = "📈 YUKARI"
        else:
            trend = "📉 AŞAĞI"
    except IndexError:
        trend = "YETERSIZ VERI"

    return {"RSI": rsi, "Trend": trend, "price_df": df_price}

# -----------------------------------------------------------

def latest_common_period(balance, income, cashflow):
    bal_periods = {c for c in balance.columns if "/" in c}
    inc_periods = {c for c in income.columns  if "/" in c}
    cf_periods  = {c for c in cashflow.columns if "/" in c}
    return sorted(bal_periods & inc_periods & cf_periods,
                  key=period_order, reverse=True)

params = st.query_params
default_symbol = params.get("symbol", "").upper()

@st.cache_data(show_spinner=False)
def get_scores_cached(symbol, radar_row, balance, income, cashflow, curr, prev):
    return calculate_scores(symbol, radar_row, balance, income, cashflow, curr, prev)

@st.cache_data(show_spinner=False)
def get_financials(symbol: str):
    return load_financial_data(symbol)

@st.cache_data(show_spinner=False)
def get_radar() -> pd.DataFrame:
    df = pd.read_excel(RADAR_XLSX)
    df["Şirket"] = df["Şirket"].str.strip()
    return df

def _fmt(val, pattern="{:+.2f}", default="-"):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            raise ValueError
        return pattern.format(val)
    except (TypeError, ValueError):
        return default

def format_scores_for_clipboard(data: dict) -> str:
    s = data["scores"]

    lines = [
        f"**Şirket:** {data['company']}",
        f"**Dönem:** {data['periods']['current']}  (önceki: {data['periods']['previous']})",
        "",
        f"**Piotroski F-Score:** {s.get('piotroski_card', '-')}",
        "\n".join(f"- {k}: {'✅' if v=='✅' else '❌'}"
                  for k, v in s.get('piotroski_detail', {}).items()),
        "",
    ]
    if s.get("beneish_card") is not None:
        lines.append(
            f"**Beneish M-Skor:** {s['beneish_card']} "
            f"({_fmt(s.get('beneish'))})"
        )
        lines.extend(f"- {l}" for l in s.get("beneish_lines", []))
        lines.append("")
    if "graham" in s:
        lines.append(f"**Graham Skoru:** {s['graham']} / 5")
        lines.extend(f"- {l}" for l in s.get("graham_lines", []))
        lines.append("")
    if "lynch" in s:
        lines.append(f"**Peter Lynch Skoru:** {s['lynch']} / 3")
        lines.extend(f"- {l}" for l in s.get("lynch_lines", []))

    return "\n".join(lines)


def main():
    st.title("📈 Tek Hisse Analiz Platformu (Temel + Teknik)")

    symbol = st.text_input("Borsa Kodu", default_symbol).strip().upper()
    if not symbol:
        st.info("Lütfen geçerli bir borsa kodu girin.")
        st.stop()

    try:
        balance, income, cashflow = get_financials(symbol)
    except FileNotFoundError:
        st.error(f"{symbol} için finansal veriler bulunamadı. Fintables'tan indirdiğinizden emin olun.")
        st.stop()

    periods = latest_common_period(balance, income, cashflow)
    if len(periods) < 2:
        st.error("Üç temel tabloda da en az iki ortak dönem bulunamadı.")
        st.stop()

    curr, prev = periods[:2]
    st.info(f"🔎 Kullanılan son bilanço dönemi: **{curr}**")

    radar_df = get_radar()
    radar_row = radar_df[radar_df["Şirket"] == symbol]
    if radar_row.empty:
        st.warning("Radar verisi bulunamadı; bazı skorlar ve değerleme eksik hesaplanabilir.")

    if "analyze" not in st.session_state:
        st.session_state.analyze = False

    if st.button("Analiz Et"):
        st.session_state.analyze = True

    if st.session_state.analyze:
        with st.spinner("Finansal skorlar hesaplanıyor..."):
            scores = get_scores_cached(symbol, radar_row, balance, income, cashflow, curr, prev)
        
        # YENİ: Teknik analiz verilerini çek
        with st.spinner("Teknik göstergeler hesaplanıyor..."):
            df_price_raw = get_price_df(symbol)
            tech_indicators = apply_technical_filters(symbol, df_price_raw)
            df_price_tech = tech_indicators.get("price_df")


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

        # DEĞİŞTİRİLDİ: Yeni sekme eklendi
        tab_score, tab_fcf, tab_valuation, tab_profit, tab_tech = st.tabs([
            "📊 Skor Detayları", "🔍 FCF Analizi", "⚖️ Değerleme", "💹 Karlılık (7Y)", "📈 Teknik Analiz"
        ])
        
        copy_details = None
        
        with tab_score:
            copy_details=show_company_scorecard(symbol, radar_row, curr, prev)
            with st.container():
                st.markdown(f"📋 Skor Kartı")
                with st.expander("⬇️ kopyalamak için tıkla", expanded=False):
                    try:
                        clip_text = format_scores_for_clipboard(copy_details)
                        st.code(clip_text, language="markdown")
                    except Exception as e:
                        st.warning("Skor kartı kopyalanamadı: " + str(e))

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
            df_fcf = fcf_detailed_analysis(symbol, radar_row)
            if df_fcf is None or df_fcf.empty:
                st.info("Değerleme için FCF verileri eksik.")
            else:
                if len(df_fcf) >= 4:
                    last_fcf = df_fcf["FCF"].iloc[-4:].sum()
                else:
                    last_fcf = df_fcf["FCF"].iloc[-1]
                
                if last_fcf <= 0:
                    st.warning("Son FCF negatif veya sıfır, değerleme anlamsız.")
                else:
                    col1, col2 = st.columns(2)
                    with col1:
                        wacc_mu = st.slider("Ortalama WACC (%)", 5.0, 25.0, 15.0, 0.5, key="wacc") / 100
                        g_mu = st.slider("Terminal Büyüme (%)", 0.0, 10.0, 4.0, 0.1, key="g") / 100
                    with col2:
                        n_sims = st.number_input("Simülasyon Sayısı", 1000, 50000, 10000, 1000, "%d")
                        years = st.slider("Projeksiyon Yılı", 3, 10, 5)

                    sim_vals = monte_carlo_dcf_simple(last_fcf, years, int(n_sims), wacc_mu, g_mu)
                    intrinsic = np.median(sim_vals)

                    cur_price = None
                    market_cap = None
                    try:
                        if hasattr(radar_row, "columns") and "Son Fiyat" in radar_row.columns and len(radar_row) > 0:
                            cur_price = radar_row["Son Fiyat"].iloc[0]
                        if hasattr(radar_row, "columns") and "Piyasa Değeri" in radar_row.columns and len(radar_row) > 0:
                            market_cap = radar_row["Piyasa Değeri"].iloc[0]
                    except Exception:
                        cur_price = None
                        market_cap = None

                    if cur_price and market_cap and market_cap > 0:
                        shares_out = market_cap / cur_price
                        intrinsic_ps = intrinsic / shares_out
                        price_col, value_col, gain_col = st.columns(3)
                        with price_col: st.metric("🎯 Mevcut Fiyat (TL)", f"{cur_price:,.2f}")
                        with value_col: st.metric("📊 Medyan İçsel Değer (TL)", f"{intrinsic_ps:,.2f}")
                        with gain_col:
                            premium = (intrinsic_ps - cur_price) / cur_price * 100
                            st.metric(f"{'📈' if premium >= 0 else '📉'} Potansiyel Getiri (%)", f"{premium:+.1f}%")
                    else:
                        st.metric("Medyan İçsel Değer (TL)", f"{intrinsic:,.0f}")

                    fig, ax = plt.subplots(figsize=(7, 4))
                    ax.hist(sim_vals, bins=50, alpha=0.8, color='skyblue', edgecolor='black')
                    ax.axvline(intrinsic, color='red', linestyle='--', label=f'Medyan: {intrinsic:,.0f} TL')
                    ax.set_xlabel("İçsel Değer (TL)"); ax.set_ylabel("Sıklık")
                    ax.set_title(f"{n_sims:,} Senaryoda Değer Dağılımı"); ax.legend()
                    st.pyplot(fig)
        
        # YENİ: Karlılık (7Y) sekmesi
        with tab_profit:
            st.subheader("7 Yıllık Karlılık ve Getiri Oranları")
            try:
                prof_df = build_profitability_table(symbol, last_n_years=7)
            except Exception as e:
                prof_df = None
                st.warning(f"Karlılık verileri oluşturulamadı: {e}")

            if prof_df is None or prof_df.empty:
                st.info("Yeterli yıllık veri yok veya veriler eksik.")
            else:
                # Özet metrikler
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    med_margin = prof_df["Net Marj (%)"].median(skipna=True)
                    st.metric("Medyan Net Marj (7Y)", f"{med_margin:.1f}%" if pd.notna(med_margin) else "-")
                with col_b:
                    med_roe = prof_df["ROE (%)"].median(skipna=True)
                    st.metric("Medyan ROE (7Y)", f"{med_roe:.1f}%" if pd.notna(med_roe) else "-")
                with col_c:
                    cagr = compute_net_profit_cagr(prof_df)
                    st.metric("Net Kâr CAGR (7Y)", f"{cagr:.1f}%" if cagr is not None else "-")

                # ROE/ROA kısa açıklamaları
                st.caption(
                    "ROE (%): Özsermaye kârlılığı = Net Kâr / Özkaynaklar.  "
                    "ROA (%): Aktif kârlılığı = Net Kâr / Toplam Varlıklar."
                )

                # Yorumlayıcı rozetler (eşiklere göre)
                def _rate(value: Optional[float], kind: str):
                    import math
                    if value is None or (isinstance(value, float) and (pd.isna(value) or math.isinf(value))):
                        return "⚪", "Veri yok"
                    v = float(value)
                    if kind in ("margin", "roe", "roa"):
                        if v < 0:          return "🔴", "Çok kötü"
                        elif v < 5:        return "🟠", "Kötü"
                        elif v < 10:       return "🟡", "Vasat"
                        elif v < 20:       return "🟢", "İyi"
                        else:              return "🟢", "Çok iyi"
                    if kind == "cagr":
                        if v <= -10:       return "🔴", "Çok kötü"
                        elif v < 0:        return "🟠", "Kötü"
                        elif v < 5:        return "🟡", "Vasat"
                        elif v < 15:       return "🟢", "İyi"
                        else:              return "🟢", "Çok iyi"
                    return "⚪", "-"

                with st.container():
                    st.markdown("**Nasıl yorumlanır? (Hızlı İpucu)**")
                    r_margin = _rate(med_margin, "margin") if 'med_margin' in locals() else ("⚪","Veri yok")
                    r_roe    = _rate(med_roe, "roe") if 'med_roe' in locals() else ("⚪","Veri yok")
                    r_cagr   = _rate(cagr, "cagr")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown(f"Net Marj: {r_margin[0]} {r_margin[1]}")
                    with c2:
                        st.markdown(f"ROE: {r_roe[0]} {r_roe[1]}")
                    with c3:
                        st.markdown(f"Net Kâr CAGR: {r_cagr[0]} {r_cagr[1]}")

                    with st.expander("Eşikler (genel rehber)"):
                        st.markdown("- 🔴 Çok kötü  •  🟠 Kötü  •  🟡 Vasat  •  🟢 İyi  •  🟢 Çok iyi")
                        st.markdown("- Net Marj/ROE/ROA: <0 çok kötü, 0-5 kötü, 5-10 vasat, 10-20 iyi, 20+ çok iyi")
                        st.markdown("- Net Kâr CAGR: ≤-10 çok kötü, -10–0 kötü, 0–5 vasat, 5–15 iyi, 15+ çok iyi")
                        st.caption("Not: Sektöre göre makul aralıklar değişebilir.")

                with st.expander("📋 Yıllık Karlılık Tablosu", expanded=False):
                    fmt_cols = {
                        "Satışlar": "{:,.0f}",
                        "Net Kâr": "{:,.0f}",
                        "Özkaynaklar (Yıl Sonu)": "{:,.0f}",
                        "Varlıklar (Yıl Sonu)": "{:,.0f}",
                        "Net Marj (%)": "{:.1f}",
                        "ROE (%)": "{:.1f}",
                        "ROA (%)": "{:.1f}",
                    }
                    st.dataframe(prof_df.style.format(fmt_cols))

                st.subheader("Oranlar – Zaman Serisi")
                ratios = prof_df[["Net Marj (%)", "ROE (%)", "ROA (%)"]].copy()
                # Yılı x eksenine düzgün oturtmak için index'i yıl olarak kullanalım
                ratios.index.name = "Yıl"
                st.line_chart(ratios)
        
        # YENİ EKLENDİ: Teknik Analiz sekmesinin içeriği
        with tab_tech:
            st.subheader("Teknik Göstergeler")
            
            # df_price_tech'in boş olmadığını kontrol et
            if df_price_tech is not None and not df_price_tech.empty:
                col1, col2 = st.columns(2)
                with col1:
                    rsi_val = tech_indicators.get('RSI')
                    st.metric("RSI (14)", f"{rsi_val:.1f}" if pd.notna(rsi_val) else "Hesaplanamadı")
                    if pd.notna(rsi_val):
                        if rsi_val > 70: rsi_caption = "🔴 Aşırı Alım Bölgesi"
                        elif rsi_val < 30: rsi_caption = "🟢 Aşırı Satım Bölgesi"
                        else: rsi_caption = "⚪ Nötr Bölge"
                        st.caption(rsi_caption)
                
                with col2:
                    trend_val = tech_indicators.get('Trend')
                    st.metric("SMA 20/50 Trendi", trend_val)
                    st.caption("20 günlük ortalamanın 50 günlük ortalamaya göre konumu")

                st.subheader("Fiyat ve Hareketli Ortalamalar Grafiği")
                
                # --- GRAFİK İÇİN DÜZELTME BURADA ---
                
                # 1. Grafik için kullanılacak DataFrame'i kopyala
                chart_df = df_price_tech.copy()
                
                # 2. 'date' sütununu datetime formatına çevir (garanti olsun)
                chart_df['date'] = pd.to_datetime(chart_df['date'])
                
                # 3. İNDEKSİ 'date' SÜTUNU OLARAK AYARLA (En önemli adım)
                chart_df.set_index('date', inplace=True)
                
                # 4. Sadece ilgili sütunları ve son 1 yıllık veriyi seç
                chart_data_to_plot = chart_df[['close', 'SMA20', 'SMA50']].tail(252)
                
                # 5. Artık doğru indekslenmiş veriyi grafiğe gönder
                st.line_chart(chart_data_to_plot)
                
                # --- DÜZELTME SONU ---
                
                st.caption("MAVI: Kapanış Fiyatı, TURUNCU: 20 Günlük Basit Ort., YEŞİL: 50 Günlük Basit Ort.")

            else:
                st.warning(f"'{symbol}' için teknik analiz verisi çekilemedi.")


if __name__ == "__main__":
    main()
