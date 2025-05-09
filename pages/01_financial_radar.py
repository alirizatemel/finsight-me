import streamlit as st # type: ignore
import pandas as pd
from modules.data_loader import load_financial_data
from modules.scanner import run_scan                 # NEW (shared scanner)
from modules.utils_db import (
    scores_table_empty, load_scores_df, save_scores_df
)
from streamlit import column_config as cc # type: ignore
from config import RADAR_XLSX


loglar = []

@st.cache_data(show_spinner=False)
def load_radar() -> pd.DataFrame:
    """Read Fintables radar sheet once & cache."""
    df = pd.read_excel(RADAR_XLSX)
    df["Şirket"] = df["Şirket"].str.strip()
    return df

@st.cache_data(show_spinner=False)   
def get_financials(company: str):
    """
    Returns (balance_df, income_df, cashflow_df) for a given company.
    Cached so repeated calls don't hit the disk again.
    """
    return load_financial_data(company)


def link_to_analysis(ticker: str) -> str:
    """
    Tek-hisse analiz sayfasına tıklanabilir HTML köprüsü döndürür.
    (Markdown yerine <a href=…> kullanıyoruz.)
    """
    return f'<a href="/stock_analysis?symbol={ticker}" target="_self">{ticker}</a>'

st.title("📊 Bilanço Skorları Toplu Analiz")

try:
    df_radar = load_radar()
    df_radar["Şirket"] = df_radar["Şirket"].str.strip()
    companies = df_radar["Şirket"].dropna().unique()
    loglar.append(f"🔄 Toplam {len(companies)} şirket bulundu.")
except Exception as e:
    st.error(f"Dosya okunamadı: {e}")
    st.stop()

# Örnek bir şirketten dönem kolonlarını al

def period_sort_key(period_str):
    yil, ay = map(int, period_str.split("/"))
    return yil * 100 + ay  # Örn: 2024/12 → 202412, 2024/03 → 202403

ornek_sirket = None
for c in companies:
    try:
        example_balance_sheet, _, _ = load_financial_data(c)
        ornek_sirket = c
        break
    except FileNotFoundError:
        continue

if ornek_sirket is None:
    st.error("Hiçbir şirket için bilanço Excel'i bulunamadı.")
    st.stop()

# artık example_balance_sheet zaten var
period_list = sorted(
    [col for col in example_balance_sheet.columns if "/" in col],
    key=period_sort_key,
    reverse=True
)

# Seçilebilir dönem (sadece current_period seçiliyor)
current_period = st.selectbox("Current Period", options=period_list)

# 1 yıl önceki dönemi bul (örneğin 2024/12 -> 2023/12)
def one_year_back(period):
    try:
        yil, ay = map(int, period.split("/"))
        return f"{yil-1}/{ay}"
    except:
        return None

previous_period = one_year_back(current_period)

# Eğer 1 yıl öncesi listede yoksa uyarı göster
if previous_period not in period_list:
    st.error(f"{current_period} için bir yıl önceki dönem ({previous_period}) verisi bulunamadı. Başka bir dönem seçiniz.")
    st.stop()
else:
    st.markdown(f"**Previous Period:** `{previous_period}`")

st.sidebar.header("🔍 Skor Filtreleri")

with st.sidebar.expander("Filtreler", expanded=True):
    f_min, f_max = st.slider("F-Skor Aralığı", 0, 9, (0, 9), key="f")
    m_min, m_max = st.slider("M-Skor Aralığı", -5.0, 5.0, (-5.0, 5.0), 0.1, key="m")
    l_min, l_max = st.slider("Lynch Aralığı", 0, 5, (0, 5), key="l")
    g_min, g_max = st.slider("Graham Aralığı", 0, 5, (0, 5), key="g")

    colA, colB = st.columns(2)
    with colA:
         apply = st.button("🔍 Filtrele", key="apply_filter")
    with colB:
        reset = st.button("🔄 Sıfırla", key="reset_filter")

if reset:
    st.session_state.pop("score_df", None)

# -------------------------------------------------------------------------
# DB‑first logic (same UX as Trap Radar)
# -------------------------------------------------------------------------
with st.sidebar:
    st.header("Veri Kaynağı")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Veritabanından Yükle"):
            st.session_state.scan = True
            st.session_state.force_refresh = False
    with col2:
        if st.button("Skorları Yenile"):
            st.session_state.scan = True
            st.session_state.force_refresh = True

if st.session_state.get("scan"):
    if scores_table_empty("radar_scores") or st.session_state.get("force_refresh"):
        st.info("📊 Skorlar hesaplanıyor, veritabanı güncelleniyor…")
        df_scan, logs, _ = run_scan(df_radar)   # <‑‑ lightweight scan
        save_scores_df(df_scan, table="radar_scores")
    else:
        st.success("📁 Skorlar veritabanından yüklendi.")
        df_scan = load_scores_df(table="radar_scores")
        logs = []
else:
    st.stop()

score_df = df_scan     # rename for clarity below


# Skor tablosunu göster
score_df["Link"]     = "/stock_analysis?symbol=" + score_df["Şirket"]


# Skor kolonlarını numeriğe çevir, olmayanlar NaN olur
for col in ["F-Skor", "M-Skor", "Lynch", "Graham", "MOS"]:
    score_df[col] = pd.to_numeric(score_df[col], errors="coerce")

score_df["MOS"] = score_df["MOS"]*100
# --- Uygula / sıfırla filtre --------------------------------------------
if apply:
    filtered_df = score_df[
        (score_df["F-Skor"] >= f_min) & (score_df["F-Skor"] <= f_max) &
        (score_df["M-Skor"] >= m_min) & (score_df["M-Skor"] <= m_max) &
        (score_df["Lynch"] >= l_min) & (score_df["Lynch"] <= l_max) &
        (score_df["Graham"] >= g_min) & (score_df["Graham"] <= g_max)
    ]
    st.markdown(f"**🔎 Filtrelenmiş Şirket Sayısı:** {len(filtered_df)}")
    #st.dataframe(filtered_df.sort_values("F-Skor", ascending=False), use_container_width=True)
    st.dataframe(
        filtered_df.sort_values("F-Skor", ascending=False),
        column_config={
            "Link": cc.LinkColumn(
                label="Link",    # hangi kolon URL’yi tutuyor
                display_text="Analize Git",
                #target="_self",     # aynı sekmede aç
            ),
            "MOS": cc.NumberColumn(
                label="MOS",
                format="%.1f%%", 
            ),
        },
        hide_index=True,
        use_container_width=True,
    )
    

else:
    st.markdown(f"**📋 Tüm Şirketler:** {len(score_df)}")
    #st.dataframe(score_df.sort_values("F-Skor", ascending=False), use_container_width=True)
    st.dataframe(
        score_df.sort_values("F-Skor", ascending=False),
        column_config={
            "Link": cc.LinkColumn(
                label="Link",    # hangi kolon URL’yi tutuyor
                display_text="Analize Git",
                #target="_self",     # aynı sekmede aç
            ),
            "MOS": cc.NumberColumn(
                label="MOS",
                format="%.1f%%", 
            ),
        },
        hide_index=True,
        use_container_width=True,
    )



# Logları göster
with st.expander("🪵 Loglar"):
    for log in loglar:
        st.write(log)
