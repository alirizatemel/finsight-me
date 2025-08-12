# 03_portfolio_dashboard_v2.py (Transaction-Based & Closed Positions)

import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import math
from datetime import datetime

# Yeni transaction-based fonksiyonlarımızı import ediyoruz
from modules.db.transactions import (
    get_current_portfolio_df,
    get_closed_positions_summary
)
# Bu log dosyası hala kullanılabilir, ama portfolio verisi için değil.
from modules.db.performance_log import load_performance_log

# --- 1. Sayfa Yapısı ve Başlık ---
st.set_page_config(page_title="Portföy & Performans Dashboard", page_icon="📊", layout="wide")
st.title("📊 Portföy & Performans Dashboard")


# --- 2. Veri Yükleme ve Hazırlık Fonksiyonları (YENİ YAPI) ---
@st.cache_data(ttl=900)
def load_data():
    """Tüm gerekli verileri tek seferde yükler ve hazırlar."""
    # 1. Açık pozisyonlar (değişiklik yok)
    df_open = get_current_portfolio_df()
    
    # 2. Kapalı pozisyonlar ve yeni metrikler
    df_closed_raw = get_closed_positions_summary()
    df_closed = pd.DataFrame()
    
    # --- YENİ METRİK HESAPLAMALARI ---
    holding_metrics = {
        "avg_win_holding_days": 0,
        "avg_loss_holding_days": 0,
        "avg_profit_percent": 0,
        "total_sales_volume": 0 
    }
    # ------------------------------------

    if not df_closed_raw.empty:
        df_closed = df_closed_raw.copy()
        df_closed["kar_zarar_tl"] = df_closed["toplam_satis_tutari"] - df_closed["toplam_maliyet"]
        # Sıfıra bölme hatasını önlemek için kontrol
        df_closed["kar_zarar_yuzde"] = df_closed.apply(
            lambda row: (row["kar_zarar_tl"] / row["toplam_maliyet"]) * 100 if row["toplam_maliyet"] != 0 else 0,
            axis=1
        )
        df_closed['ilk_alis_tarihi'] = pd.to_datetime(df_closed['ilk_alis_tarihi'])
        df_closed['son_satis_tarihi'] = pd.to_datetime(df_closed['son_satis_tarihi'])
        df_closed["tutma_suresi_gun"] = (df_closed["son_satis_tarihi"] - df_closed["ilk_alis_tarihi"]).dt.days
        
        # --- YENİ METRİK HESAPLAMALARI İÇİN MANTIK ---
        winners = df_closed[df_closed["kar_zarar_tl"] > 0]
        losers = df_closed[df_closed["kar_zarar_tl"] <= 0]
        
        if not winners.empty:
            holding_metrics["avg_win_holding_days"] = winners["tutma_suresi_gun"].mean()
            holding_metrics["avg_profit_percent"] = winners["kar_zarar_yuzde"].mean()
            
        if not losers.empty:
            holding_metrics["avg_loss_holding_days"] = losers["tutma_suresi_gun"].mean()
        # ---------------------------------------------

        # --- İŞLEM HACMİ HESAPLAMASI ---
        # Sadece kapanmış pozisyonların alım ve satım tutarlarını topla
        
        total_sells = df_closed["toplam_satis_tutari"].sum()
        holding_metrics["total_sales_volume"] =  total_sells
        # ---------------------------------

    # 3. Performans log (değişiklik yok)
    df_log = load_performance_log()
    if not df_log.empty:
        df_log["Deger"] = df_log["lot"] * df_log["fiyat"]
        df_log["tarih"] = pd.to_datetime(df_log["tarih"])
        
    return df_open, df_closed, df_log, holding_metrics # <--- YENİ, metrikleri de döndür

# --- 3. Ana Sayfa Mantığı ---
# --- 3. Ana Sayfa Mantığı ---
df_open, df_closed, df_log, holding_metrics = load_data() # <--- Yeni metrikleri al

st.subheader("Portföy Genel Bakış")

# Metrikleri hesapla (mevcut kod)
total_open_value = df_open["toplam_maliyet"].sum() if not df_open.empty else 0
total_closed_profit = df_closed["kar_zarar_tl"].sum() if not df_closed.empty else 0
win_count = len(df_closed[df_closed["kar_zarar_tl"] > 0]) if not df_closed.empty else 0
loss_count = len(df_closed[df_closed["kar_zarar_tl"] <= 0]) if not df_closed.empty else 0
total_closed_trades = win_count + loss_count
win_rate = (win_count / total_closed_trades * 100) if total_closed_trades > 0 else 0

# --- METRİK GÖSTERİMİ İÇİN YENİ BÖLÜM ---
# Metrikleri daha düzenli göstermek için 2 satır kullanalım
row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
row1_col1.metric("Açık Pozisyon Değeri", f"{total_open_value:,.0f} TL", help="Açık pozisyonların güncel ağırlıklı ortalama maliyet üzerinden toplam değeri.")
row1_col2.metric("Gerçekleşen K/Z", f"{total_closed_profit:,.0f} TL", help="Tüm kapanmış pozisyonlardan elde edilen net kâr/zarar toplamı.")
row1_col3.metric("Başarı Oranı", f"{win_rate:.1f}%", help="Kârla kapatılan pozisyonların toplam kapanan pozisyonlara oranı (Win Rate).")
row1_col4.metric("Kapanan İşlem Sayısı", f"{total_closed_trades}", help=f"{win_count} kazanan / {loss_count} kaybeden.")

st.markdown("---") # Ayraç

row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4) 
row2_col1.metric(
    "Toplam Satışlar Tutarı",
    f"{holding_metrics['total_sales_volume']:,.0f} TL", # YENİ METRİK
    help="Kapanmış pozisyonlarınızdaki toplam alım ve satım işlemlerinin parasal değeridir."
)
row2_col2.metric(
    "Ort. Kâr Yüzdesi (Kazananlar)",
    f"% {holding_metrics['avg_profit_percent']:.2f}",
    help="Sadece kârla kapatılan pozisyonların ortalama getiri yüzdesidir."
)
row2_col3.metric(
    "Ort. Tutma Süresi (Kazananlar)",
    f"{holding_metrics['avg_win_holding_days']:.0f} gün",
    help="Kârla kapatılan bir pozisyonu ortalama kaç gün elinizde tuttuğunuzu gösterir."
)
row2_col4.metric(
    "Ort. Tutma Süresi (Kaybedenler)",
    f"{holding_metrics['avg_loss_holding_days']:.0f} gün",
    help="Zararla kapatılan bir pozisyonu ortalama kaç gün elinizde tuttuğunuzu gösterir."
)
# --------------------------------------------

st.divider()

tab1, tab2, tab3 = st.tabs(["💼 Açık Pozisyonlar", "✅ Kapalı Pozisyonlar", "📈 Performans Metrikleri"])

with tab1:
    st.subheader("Mevcut Portföy Pozisyonları")
    if df_open.empty:
        st.info("Gösterilecek aktif pozisyon bulunamadı.")
    else:
        st.dataframe(
            df_open,
            hide_index=True, use_container_width=True,
            column_config={
                "hisse": st.column_config.TextColumn("Hisse"),
                "lot": st.column_config.NumberColumn("Lot"),
                "ortalama_maliyet": st.column_config.NumberColumn("Ort. Maliyet", format="₺%.4f"),
                "toplam_maliyet": st.column_config.NumberColumn("Toplam Değer", format="₺%.2f"),
            }
        )
        st.subheader("Görselleştirmeler")
        if not df_open.empty:
            fig, ax = plt.subplots()
            ax.pie(df_open['toplam_maliyet'], labels=df_open['hisse'], autopct='%1.1f%%', startangle=90)
            ax.axis('equal')
            ax.set_title("Varlık Dağılımı (Maliyete Göre)")
            st.pyplot(fig)


with tab2:
    st.subheader("Gerçekleşen Kâr/Zarar Analizi")
    if df_closed.empty:
        st.info("Henüz tamamı satılmış ve kapanmış bir pozisyon bulunmuyor.")
    else:
        display_cols_closed = ["hisse", "kar_zarar_tl", "kar_zarar_yuzde", "tutma_suresi_gun", "toplam_maliyet", "toplam_satis_tutari"]
        st.dataframe(
            df_closed[display_cols_closed].sort_values("kar_zarar_tl", ascending=False),
            hide_index=True, use_container_width=True,
            column_config={
                "hisse": "Hisse",
                "kar_zarar_tl": st.column_config.NumberColumn("K/Z (TL)", format="₺%.2f"),
                "kar_zarar_yuzde": st.column_config.NumberColumn("K/Z (%)", format="%.2f%%"),
                "tutma_suresi_gun": st.column_config.NumberColumn("Tutma Süresi (Gün)"),
                "toplam_maliyet": st.column_config.NumberColumn("Toplam Alım Maliyeti", format="₺%.2f"),
                "toplam_satis_tutari": st.column_config.NumberColumn("Toplam Satış Tutarı", format="₺%.2f"),
            }
        )
        # K/Z Bar Grafiği
        df_plot_closed = df_closed.sort_values("kar_zarar_tl", ascending=False)
        fig, ax = plt.subplots()
        colors = ["g" if x > 0 else "r" for x in df_plot_closed["kar_zarar_tl"]]
        ax.bar(df_plot_closed["hisse"], df_plot_closed["kar_zarar_tl"], color=colors)
        ax.axhline(0, color="grey", linestyle="--", lw=1)
        ax.set_ylabel("Gerçekleşen Kar/Zarar (TL)")
        ax.set_title("Kapanan Pozisyonlar Kâr/Zarar Durumu")
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        st.pyplot(fig)


with tab3:
    st.subheader("Zaman Serisi ve Metrikler")
    if df_log.empty:
        st.warning("Performans metriklerini ve zaman serisi grafiğini hesaplamak için log verisi bulunamadı.")
    else:
        # Sharpe oranı ve haftalık getiri gibi hesaplamalar buraya tekrar eklenebilir.
        # Bu kısım şimdilik basitleştirilmiştir.
        st.subheader("Portföy Değerinin Zaman İçindeki Değişimi")
        fig, ax = plt.subplots(figsize=(12, 4))
        pivot_df = df_log.pivot(index='tarih', columns='hisse', values='Deger').fillna(0)
        ax.stackplot(pivot_df.index, pivot_df.T, labels=pivot_df.columns)
        ax.legend(loc='upper left', ncol=math.ceil(len(pivot_df.columns)/2), fontsize="small")
        ax.set_ylabel("Portföy Değeri (TL)")
        ax.set_xlabel("")
        ax.grid(True, axis='y', linestyle='--', alpha=0.6)
        st.pyplot(fig)