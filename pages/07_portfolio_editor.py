"""
SQL (run once):  VIEW v_portfolio_dashboard
-------------------------------------------------
CREATE OR REPLACE VIEW v_portfolio_dashboard AS
WITH latest_scores AS (
    SELECT DISTINCT ON ("Şirket")
        "Şirket",
        "Graham" AS graham_skor,
        "MOS"    AS mos,
        "timestamp"
    FROM   radar_scores
    ORDER  BY "Şirket", "timestamp" DESC
)
SELECT p.*, ls.graham_skor, ls.mos
FROM   portfolio p
LEFT   JOIN latest_scores ls ON ls."Şirket" = p.hisse;
"""

import streamlit as st #type: ignore
import pandas as pd
from datetime import date
from modules.utils_db import load_portfolio_df, upsert_portfolio, engine
from sqlalchemy import text #type: ignore

st.set_page_config(page_title="Portföy Yönetimi", page_icon="📋", layout="wide")

# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _df_defaults() -> dict:
    """Yeni kayıt için varsayılan değerler"""
    return {
        "hisse": "",
        "is_fund": False,
        "lot": 1,
        "maliyet": 0.0,
        "alis_tarihi": date.today(),
        "satis_tarihi": None,
        "satis_fiyat": 0.0,
        "notu": "",
    }


def _fill_form(form, rec: dict):
    """Form alanlarını doldurur ve kullanıcı girişini alır."""
    hisse = form.text_input("Hisse", max_chars=20, value=rec["hisse"])
    is_fund = form.checkbox("Yatırım Fonu mu?", value=rec["is_fund"])
    lot = form.number_input("Lot", min_value=1, value=int(rec["lot"]))
    maliyet = form.number_input("Maliyet", format="%.4f", value=float(rec["maliyet"]))
    alis_tarihi = form.date_input("Alış Tarihi", value=rec["alis_tarihi"])
    satis_tarihi = form.date_input(
        "Satış Tarihi",
        value=rec["satis_tarihi"] if rec["satis_tarihi"] else None,
        disabled=False
    ) 
    satis_fiyat = form.number_input("Satış Fiyatı", format="%.4f", value=float(rec["satis_fiyat"]))
    notu = form.text_area("Not", value=rec["notu"])

    return {
        "hisse": hisse,
        "is_fund": is_fund,
        "lot": lot,
        "maliyet": maliyet,
        "alis_tarihi": alis_tarihi,
        "satis_tarihi": satis_tarihi,
        "satis_fiyat": satis_fiyat,
        "notu": notu,
    }

# ---------------------------------------------------------------------------
# Başlık
# ---------------------------------------------------------------------------
st.title("📋 Portföy Yönetimi")

# ---------------------------------------------------------------------------
# Mevcut kayıtları yükle
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Mevcut kayıtları yükle (id dâhil)
# ---------------------------------------------------------------------------
try:
    df_all = pd.read_sql("SELECT * FROM portfolio ORDER BY alis_tarihi DESC", engine)
except Exception:
    df_all = pd.DataFrame()

# ---------------------------------------------------------------------------
# Kayıt seç / düzenle bölümü
# ---------------------------------------------------------------------------
with st.expander("➕ Yeni Kayıt / ✏️ Güncelle"):

    # Selectbox'ta hisse adları gösterilsin; tekrar eden hisseler için ilk kayıt seçilir
    if df_all.empty:
        options = ["Yeni Kayıt"]
    else:
        options = ["Yeni Kayıt"] + sorted(df_all["hisse"].unique().tolist())

    selected = st.selectbox(
        "Düzenlemek istediğiniz kayıt (hisse adı)",
        options=options,
        index=0,
    )

    if selected == "Yeni Kayıt":
        record_defaults = _df_defaults()
    else:
        # Seçilen hisseye ait ilk satırı getir (birden fazla pozisyon varsa en eskiyi alır)
        record_defaults = (
            df_all[df_all["hisse"] == selected]
            .sort_values("alis_tarihi")
            .iloc[0]
            .to_dict()
        )

    with st.form("portfolio_form", clear_on_submit=False):
        new_values = _fill_form(st, record_defaults)
        submitted = st.form_submit_button("Kaydet")

        if submitted:
            rec_df = pd.DataFrame([new_values])
            upsert_portfolio(rec_df)  # util fonksiyonu id'siz upsert eder
            st.success("Kayıt eklendi/güncellendi. Sayfayı yenileyin veya tabloyu kontrol edin.")

# ---------------------------------------------------------------------------
# Tablo
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📑 Mevcut Portföy Pozisyonları")
st.dataframe(df_all, use_container_width=True)

# ---------------------------------------------------------------------------
# Silme bölümü
# ---------------------------------------------------------------------------
st.markdown("### ❌ Kayıt Sil")
row_id = st.number_input("Silmek istediğiniz kaydın ID'si", min_value=1, step=1)
if st.button("Sil"):
    delete_sql = text("DELETE FROM portfolio WHERE id = :id")
    with engine.begin() as conn:
        conn.execute(delete_sql, {"id": row_id})
    st.warning(f"ID {row_id} silindi. Tabloyu yenileyin.")
