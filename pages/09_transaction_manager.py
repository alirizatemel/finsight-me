import streamlit as st
import pandas as pd
from datetime import date
# Yeni veritabanı modülümüzü import ediyoruz
from modules.db.transactions import (
    add_transaction,
    delete_transaction_by_id,
    load_all_transactions_df,
    get_current_portfolio_df
)
# (varsa) core modülünü de import edin
# from modules.db.core import engine 

st.set_page_config(page_title="Portföy Yönetimi", page_icon="📋", layout="wide")

st.title("📋 Portföy ve İşlem Yönetimi")
st.info("Bu sayfada portföyünüze yeni alım/satım işlemleri ekleyebilir ve mevcut pozisyonlarınızı görebilirsiniz.")

# ---------------------------------------------------------------------------
# Yeni İşlem Ekleme Formu
# ---------------------------------------------------------------------------
with st.expander("➕ Yeni Alım/Satım İşlemi Ekle", expanded=True):
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            hisse = st.text_input("Hisse Kodu", max_chars=20)
            islem_tipi = st.radio("İşlem Tipi", ('ALIŞ', 'SATIŞ'), horizontal=True)
            rsi_input = st.text_input("RSI (Opsiyonel)", help="İşlem günündeki RSI değerini girin.")
        with col2:
            lot = st.number_input("Lot", min_value=1, step=10)
            fiyat = st.number_input("Fiyat", min_value=0.0, format="%.4f")
            vfi_input = st.text_input("VFI (Opsiyonel)", help="İşlem günündeki VFI değerini girin.")
        with col3:
            tarih = st.date_input("İşlem Tarihi", value=date.today())
            notu = st.text_input("Not (Opsiyonel)")

        submitted = st.form_submit_button("İşlemi Kaydet")

        if submitted:
            # Basit doğrulama
            if not hisse or lot <= 0 or fiyat <= 0:
                st.warning("Lütfen Hisse Kodu, Lot ve Fiyat alanlarını doğru bir şekilde doldurun.")
            else:
                try:
                    rsi_value = float(rsi_input) if rsi_input else None
                    vfi_value = float(vfi_input) if vfi_input else None

                    row_count = add_transaction(
                        hisse=hisse,
                        tarih=tarih,
                        islem_tipi=islem_tipi,
                        lot=int(lot),
                        fiyat=float(fiyat),
                        notu=notu,
                        rsi=rsi_value,
                        vfi=vfi_value
                    )
                    if row_count > 0:
                        st.success(f"{hisse} için {islem_tipi} işlemi başarıyla kaydedildi.")
                        # `get_current_portfolio_df` ve `load_all_transactions_df` fonksiyonlarındaki
                        # cache'i temizlemek için (eğer @st.cache_data kullanıyorsanız)
                        # get_current_portfolio_df.clear()
                        # load_all_transactions_df.clear()
                    else:
                        st.error("İşlem kaydedilirken bir hata oluştu.")
                except Exception as e:
                    st.error(f"Bir hata oluştu: {e}")
                # st.rerun() # Sayfayı yeniden yüklemek için bu satırı etkinleştirebilirsiniz,
                             # ancak success/error mesajları kaybolur. Genellikle formda gerekmez.


# ---------------------------------------------------------------------------
# Mevcut Portföy Durumu
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Mevcut Portföy Pozisyonları")
st.caption("Bu tablo, tüm alım ve satım işlemleriniz üzerinden hesaplanan net pozisyonlarınızı gösterir.")

df_portfolio = get_current_portfolio_df()

if not df_portfolio.empty:
    st.dataframe(
        df_portfolio,
        use_container_width=True,
        hide_index=True,
        column_config={
            "hisse": st.column_config.TextColumn("Hisse"),
            "lot": st.column_config.NumberColumn("Mevcut Lot", format="%d"),
            "ortalama_maliyet": st.column_config.NumberColumn("Ortalama Maliyet", format="₺%.4f"),
            "toplam_maliyet": st.column_config.NumberColumn("Toplam Maliyet", format="₺%.2f"),
        }
    )
else:
    st.info("Henüz görüntülenecek bir pozisyon bulunmuyor. Lütfen önce bir 'ALIŞ' işlemi ekleyin.")


# ---------------------------------------------------------------------------
# İşlem Geçmişi ve Silme
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("📜 İşlem Geçmişi")
st.caption("Burada tüm alım/satım geçmişinizi görebilir ve hatalı bir kaydı silebilirsiniz.")

df_transactions = load_all_transactions_df()

if not df_transactions.empty:
    st.dataframe(df_transactions, use_container_width=True, hide_index=True)
    
    st.markdown("##### ❌ İşlem Sil")
    col_del1, col_del2 = st.columns([1, 3])
    with col_del1:
        id_to_delete = st.number_input("Silmek istediğiniz işlemin ID'si", min_value=1, step=1, key="del_id")
    with col_del2:
        st.write("") # Boşluk için
        st.write("") # Boşluk için
        if st.button("Seçili ID'deki İşlemi Sil", type="primary"):
            try:
                rows_deleted = delete_transaction_by_id(id_to_delete)
                if rows_deleted > 0:
                    st.success(f"ID {id_to_delete} olan işlem silindi. Sayfa yeniden yükleniyor...")
                    st.rerun()
                else:
                    st.error(f"ID {id_to_delete} bulunamadı veya silinemedi.")
            except Exception as e:
                st.error(f"Silme sırasında bir hata oluştu: {e}")
else:
    st.info("Henüz kayıtlı bir işlem bulunmuyor.")