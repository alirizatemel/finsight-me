import streamlit as st
import pandas as pd
from typing import Optional

# YENİ: Sadece birleşik veri yükleme fonksiyonunu import ediyoruz
from modules.db.radar_scores import load_unified_radar_data 
from streamlit import column_config as cc

st.set_page_config(layout="wide")
st.title("📊 Bilanço Skorları Radarı")

# --- Yardımcı Fonksiyonlar (Görselleştirme için) ---

def millify(n):
    # ... (Bu fonksiyon değişmiyor)
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    units = ["", "K", "M", "B", "T"]
    k = 0
    while abs(n) >= 1000 and k < len(units)-1:
        n /= 1000.0
        k += 1
    return f"{n:.2f}{units[k]}"

def trend_badge(x: Optional[str]):
    # ... (Bu fonksiyon değişmiyor)
    if not isinstance(x, str): return ""
    if "YUKARI" in x: return "🟢 YUKARI"
    elif "AŞAĞI" in x: return "🔴 AŞAĞI"
    return x

# render_table fonksiyonu artık sadece formatlama yapıyor
def render_table(df: pd.DataFrame):
    df = df.copy()

    # 1. Görsel formatlama için yeni kolonlar oluştur
    if "piyasa_degeri" in df.columns:
        df["piyasa_degeri_fmt"] = df["piyasa_degeri"].map(millify)
    if "icsel_deger_medyan" in df.columns:
        df["icsel_deger_medyan_fmt"] = df["icsel_deger_medyan"].map(millify)
    if "trend" in df.columns:
        df["trend_badge"] = df["trend"].map(trend_badge)
    
    if "hisse" in df.columns:
        df["Link"] = "/stock_analysis?symbol=" + df["hisse"]
    
    # MOS'u yüzdeye çevir
    if "MOS" in df.columns and pd.api.types.is_numeric_dtype(df["MOS"]):
        df["MOS"] = df["MOS"] * 100
    
    # 2. Gösterilecek kolonları ve başlıklarını tanımla
    column_config = {
        "hisse": "Hisse",
        "f_skor": cc.NumberColumn("Piotroski", format="%d/9", help="Piotroski F-Score"),
        "m_skor": cc.NumberColumn("Beneish", format="%.2f"),
        "graham": cc.NumberColumn("Graham", format="%d/5"),
        "lynch": cc.NumberColumn("Peter Lynch", format="%d/3"),
        "icsel_deger_medyan_fmt": cc.TextColumn("İçsel Değer"),
        "piyasa_degeri_fmt": cc.TextColumn("Piyasa Değeri"),
        "MOS": cc.NumberColumn("MOS", format="%.1f%%", help="Güvenlik Marjı"),
        "last_price": cc.NumberColumn("Fiyat", format="%.2f"),
        "date": cc.DateColumn("Teknik Analiz Tarihi"),
        "rsi": cc.NumberColumn("RSI(14)", format="%.1f"),
        "trend_badge": cc.TextColumn("Trend"),
        "timestamp": cc.DatetimeColumn("Skor Tarihi", format="YYYY-MM-DD HH:mm"),
        "Link": cc.LinkColumn("Detay", display_text="🔗"),
    }
    
    # Sadece DataFrame'de var olan kolonları göster
    display_cols = [col for col in column_config.keys() if col in df.columns or col.replace("_badge", "") in df.columns or col.replace("_fmt", "") in df.columns]


    # 3. Sırala ve çiz
    df = df.sort_values(["f_skor", "MOS"], ascending=[False, False], na_position="last")
    
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_order=display_cols, # Kolon sırasını belirle
        column_config=column_config
    )

# --- Veri Yükleme ve Filtreleme ---
@st.cache_data(ttl=300)  # Veriyi 5 dakika önbellekte tut
def get_display_data():
    # Artık sadece bu tek fonksiyonu çağırıyoruz!
    return load_unified_radar_data()

score_df = get_display_data()

if score_df.empty:
    st.warning(
        "Veritabanında gösterilecek veri bulunamadı. "
        "Lütfen soldaki menüden **'Analiz ve Veri Güncelleme'** sayfasına gidip analiz işlemini başlatın."
    )
    st.stop()

# --- Filtreleme ---
st.sidebar.header("🔍 Filtreler")
with st.sidebar.expander("Filtreleri Ayarla", expanded=True):
    f_min, f_max = st.slider("Piotroski F-Skor", 0, 9, (0, 9))
    m_min, m_max = st.slider("Beneish M-Skor", -5.0, 5.0, (-5.0, 5.0), 0.1)
    g_min, g_max = st.slider("Graham Skoru", 0, 5, (0, 5), help="Graham kriterlerine göre skor (0-5)")
    l_min, l_max = st.slider("Peter Lynch Skoru", 0, 3, (0, 3), help="Peter Lynch kriterlerine göre skor (0-3)")

# Filtreleme mantığı
# Not: MOS'u filtrelerken orijinal değerini (0-100 aralığı) kullanıyoruz.
filtered_df = score_df[
    (score_df["f_skor"].between(f_min, f_max)) &
    (score_df["m_skor"].between(m_min, m_max)) &
    (score_df["graham"].fillna(0).between(g_min, g_max)) &
    (score_df["lynch"].fillna(0).between(l_min, l_max)) 
].copy()

# --- Sayfayı Çiz ---
st.markdown(f"**Gösterilen Şirket Sayısı:** `{len(filtered_df)}` / `{len(score_df)}`")
render_table(filtered_df)

st.sidebar.info(
    "Verileri güncellemek için soldaki menüden **'Analiz ve Veri Güncelleme'** sayfasına gidin."
)