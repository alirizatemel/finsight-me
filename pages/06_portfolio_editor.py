import streamlit as st #type: ignore
import pandas as pd
from datetime import date
# Veritabanı fonksiyonlarını modülden import ediyoruz
from modules.db.portfolio import (
    upsert_portfolio, 
    load_full_portfolio_df, 
    delete_portfolio_by_id
)


st.set_page_config(page_title="Portföy Yönetimi", page_icon="📋", layout="wide")

# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _df_defaults() -> dict:
    """Yeni kayıt için varsayılan değerler"""
    return {
        "hisse": "",
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
    lot = form.number_input("Lot", min_value=1, value=int(rec["lot"]))
    maliyet = form.number_input("Maliyet", format="%.4f", value=float(rec["maliyet"]))
    alis_tarihi = form.date_input("Alış Tarihi", value=rec["alis_tarihi"])
    
    # satis_tarihi pd.NaT ise None'a çevir
    satis_tarihi_value = rec["satis_tarihi"]
    if pd.isna(satis_tarihi_value):
        satis_tarihi_value = None

    satis_tarihi = form.date_input(
        "Satış Tarihi",
        value=satis_tarihi_value,
        disabled=False
    ) 
    satis_fiyat_raw = form.text_input(
        "Satış Fiyatı",
        value="" if rec["satis_fiyat"] in (None, 0.0) else f"{rec['satis_fiyat']:.4f}"
    )

    try:
        satis_fiyat = float(satis_fiyat_raw) if satis_fiyat_raw.strip() else None
    except ValueError:
        st.warning("Satış fiyatı geçerli bir sayı olmalıdır.")
        satis_fiyat = None
    notu = form.text_area("Not", value=rec.get("notu", "")) # get() ile notu yoksa hatayı önle

    return {
        "hisse": hisse,
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
# Mevcut kayıtları yükle (MODÜL FONKSİYONU İLE)
# ---------------------------------------------------------------------------
df_all = load_full_portfolio_df()

# Hesaplamalar DataFrame yüklendikten sonra yapılır
if not df_all.empty:
    df_all["toplam_maliyet"] = df_all["maliyet"] * df_all["lot"]
    df_all = df_all.sort_values(by="toplam_maliyet", ascending=False)

# ---------------------------------------------------------------------------
# Kayıt seç / düzenle bölümü (DEĞİŞİKLİK YOK)
# ---------------------------------------------------------------------------
with st.expander("➕ Yeni Kayıt / ✏️ Güncelle"):
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
            upsert_portfolio(rec_df)  # Bu çağrı zaten modülerdi
            st.success("Kayıt eklendi/güncellendi. Sayfa yeniden yükleniyor...")
            st.rerun()

# ---------------------------------------------------------------------------
# Tablo
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📑 Mevcut Portföy Pozisyonları")
# id sütununu gizleyerek gösterim
if not df_all.empty:
    st.dataframe(df_all, use_container_width=True, hide_index=True)
else:
    st.info("Henüz portföy kaydı bulunmuyor.")

# ---------------------------------------------------------------------------
# Silme bölümü
# ---------------------------------------------------------------------------
st.markdown("### ❌ Kayıt Sil")
if not df_all.empty:
    row_id = st.number_input("Silmek istediğiniz kaydın ID'si", min_value=1, step=1)
    if st.button("Sil"):
        # Doğrudan SQL yerine modül fonksiyonunu çağırıyoruz
        rows_deleted = delete_portfolio_by_id(row_id)
        if rows_deleted > 0:
            st.success(f"ID {row_id} silindi. Sayfa yeniden yükleniyor...")
        else:
            st.error(f"ID {row_id} bulunamadı veya silinemedi.")
        st.rerun()
else:
    st.warning("Silinecek kayıt bulunmuyor.")

# --- END OF FILE 06_portfolio_editor.py ---