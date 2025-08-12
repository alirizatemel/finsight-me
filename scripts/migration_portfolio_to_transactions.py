# migration_script.py
# Bu script, eski 'portfolio' tablosundaki verileri
# yeni 'transactions' tablosuna taşımak için tasarlanmıştır.
import sys
import pandas as pd
import os
from sqlalchemy import text
from typing import List, Dict, Any
from pathlib import Path

# Bu script dosyasının bulunduğu dizini al (örn: .../finsight-me/scripts)
script_dir = os.path.dirname(os.path.abspath(__file__))
# Projenin ana dizinine git (scripts'in bir üst klasörü)
project_root = os.path.dirname(script_dir)
# Projenin ana dizinini Python'un import yollarına ekle
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# ----------------------------------------


# Projenizdeki veritabanı bağlantı modüllerini import edin
# Bu yolların projenize uygun olduğundan emin olun
from modules.db.core import engine
from modules.db.transactions import add_transaction

def fetch_old_portfolio_data() -> pd.DataFrame:
    """Eski portfolio tablosundaki tüm verileri çeker."""
    print("Eski 'portfolio' tablosundan veriler okunuyor...")
    try:
        # pd.read_sql_table kullanmak, sütun tiplerini daha iyi korur
        df = pd.read_sql_table("portfolio", engine)
        print(f"Başarılı: {len(df)} kayıt bulundu.")
        return df
    except Exception as e:
        print(f"HATA: 'portfolio' tablosu okunurken bir hata oluştu: {e}")
        print("İpucu: Tablo adı doğru mu? Veritabanı bağlantısı çalışıyor mu?")
        return pd.DataFrame()

def migrate_single_record(record: pd.Series):
    """
    Tek bir 'portfolio' kaydını bir veya iki 'transactions' kaydına dönüştürür.
    """
    print(f"\nİşleniyor: Hisse {record['hisse']}, Alış Tarihi {record['alis_tarihi']}")

    # 1. ALIŞ İŞLEMİNİ OLUŞTUR
    # ------------------------------------
    # `is_fund` bilgisini notun başına ekleyerek koruyalım
    note_prefix = "[FON] " if record.get('is_fund') else ""
    original_note = record.get('notu') or ""
    final_note = f"{note_prefix}{original_note}".strip()

    try:
        # `add_transaction` fonksiyonunu kullanarak ALIŞ işlemini ekle
        add_transaction(
            hisse=record['hisse'],
            tarih=record['alis_tarihi'],
            islem_tipi='ALIŞ',
            lot=record['lot'],
            fiyat=record['maliyet'],
            notu=final_note
        )
        print(f"  -> BAŞARILI: '{record['hisse']}' için ALIŞ işlemi eklendi.")
    except Exception as e:
        print(f"  -> HATA: ALIŞ işlemi eklenirken hata oluştu: {e}")
        return # Hata olursa bu kaydı atla
    
    # 2. SATIŞ İŞLEMİNİ OLUŞTUR (Eğer varsa)
    # ------------------------------------
    # satis_tarihi ve satis_fiyat alanlarının dolu ve geçerli olup olmadığını kontrol et
    satis_tarihi_valid = pd.notna(record.get('satis_tarihi'))
    satis_fiyat_valid = pd.notna(record.get('satis_fiyat')) and record.get('satis_fiyat', 0) > 0

    if satis_tarihi_valid and satis_fiyat_valid:
        try:
            # `add_transaction` fonksiyonunu kullanarak SATIŞ işlemini ekle
            # Satış notu, orijinal alım notuna ek olarak "Satış" bilgisi içerebilir.
            satis_notu = f"Oto-taşınan satış kaydı. (Eski not: {original_note})".strip()
            add_transaction(
                hisse=record['hisse'],
                tarih=record['satis_tarihi'],
                islem_tipi='SATIŞ',
                lot=record['lot'], # Tamamının satıldığını varsayıyoruz
                fiyat=record['satis_fiyat'],
                notu=satis_notu
            )
            print(f"  -> BAŞARILI: '{record['hisse']}' için SATIŞ işlemi eklendi.")
        except Exception as e:
            print(f"  -> HATA: SATIŞ işlemi eklenirken hata oluştu: {e}")

def clear_transactions_table():
    """
    Script'i tekrar tekrar çalıştırabilmek için 'transactions' tablosunu temizler.
    DİKKAT: Bu fonksiyon tablodaki TÜM veriyi siler.
    """
    print("\nUYARI: 'transactions' tablosu temizlenecek.")
    user_input = input("Devam etmek için 'evet' yazın: ")
    if user_input.lower() == 'evet':
        try:
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE transactions RESTART IDENTITY;"))
            print("'transactions' tablosu başarıyla temizlendi.")
            return True
        except Exception as e:
            print(f"HATA: 'transactions' tablosu temizlenirken hata oluştu: {e}")
            return False
    else:
        print("İşlem iptal edildi.")
        return False

def main():
    """Ana geçiş script'i fonksiyonu."""
    print("--- PORTFOLIO -> TRANSACTIONS GEÇİŞ SCRIPT'İ ---")
    
    # 1. Transactions tablosunu temizle (isteğe bağlı ama önerilir)
    if not clear_transactions_table():
        return

    # 2. Eski portföy verisini çek
    df_portfolio = fetch_old_portfolio_data()
    
    if df_portfolio.empty:
        print("Taşınacak veri bulunamadı. Script sonlandırılıyor.")
        return

    # 3. Her bir kaydı döngüye alıp yeni formata çevir
    print("\n--- Veri Taşıma İşlemi Başlıyor ---")
    success_count = 0
    fail_count = 0
    
    for index, row in df_portfolio.iterrows():
        try:
            migrate_single_record(row)
            success_count += 1
        except Exception as e:
            print(f"\n!!! KRİTİK HATA: Kayıt {row.get('id')} işlenirken beklenmedik bir hata oluştu: {e}")
            fail_count += 1

    print("\n--- Veri Taşıma İşlemi Tamamlandı ---")
    print(f"Toplam {len(df_portfolio)} eski kayıt işlendi.")
    print(f"Başarılı: {success_count}")
    print(f"Başarısız: {fail_count}")

if __name__ == "__main__":
    main()