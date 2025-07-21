import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from isyatirimhisse import fetch_stock_data

def main():
    """
    isyatirimhisse kütüphanesinin temel çalışmasını test etmek için
    basit bir Streamlit arayüzü.
    """

    # Sayfa başlığı ve açıklaması
    st.set_page_config(page_title="İş Yatırım Kütüphane Testi", layout="centered")
    st.title("`isyatirimhisse` Kütüphanesi Test Aracı")
    st.info("Bu sayfa, kütüphanenin tek bir hisse için veri çekip çekemediğini basitçe test eder.")

    # 1. Kullanıcıdan test edilecek hisse kodunu al
    symbol = st.text_input(
        "Test Edilecek Hisse Kodu:", 
        value="GARAN", 
        help="Örn: GARAN, TUPRS, EREGL"
    ).upper()  # Hisse kodları genellikle büyük harftir

    # 2. Testi başlatacak buton
    if st.button("Veriyi Çek ve Test Et"):
        if not symbol:
            st.warning("Lütfen bir hisse kodu girin.")
            st.stop()

        # Kullanıcıya işlem yapıldığını bildirmek için spinner
        with st.spinner(f"'{symbol}' için son 30 günlük veri çekiliyor..."):
            try:
                # Tarih aralığını belirle (son 30 gün)
                end_date = datetime.today()
                start_date = end_date - timedelta(days=30)

                # Veriyi çek
                df = fetch_stock_data(
                    symbols=symbol,
                    start_date=start_date.strftime("%d-%m-%Y"),
                    end_date=end_date.strftime("%d-%m-%Y"),
                    save_to_excel=False
                )

                # 3. Sonucu kontrol et ve göster
                if df is not None and not df.empty:
                    st.success(f"✔️ **Başarılı!** '{symbol}' için veri başarıyla alındı.")
                    st.write(f"Toplam {df.shape[0]} satır veri bulundu.")
                    st.dataframe(df)
                else:
                    # 4. Başarısızlık durumunu bildir
                    st.error(
                        f"❌ **Başarısız!** '{symbol}' için veri alınamadı. "
                        "Hisse kodu geçersiz olabilir veya API geçici olarak yanıt vermiyor olabilir."
                    )

            except Exception as e:
                # 5. Beklenmedik bir hata durumunu bildir
                st.error("Beklenmedik bir hata oluştu. İnternet bağlantınızı kontrol edin.")
                st.exception(e)  # Hatayı detaylı olarak ekrana yazdır

if __name__ == "__main__":
    main()
