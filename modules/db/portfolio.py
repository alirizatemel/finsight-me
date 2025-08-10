# --- START OF FILE portfolio.py ---

from sqlalchemy import text  #type: ignore
import pandas as pd
from typing import Optional
# Bu importun projenizde doğru yolda olduğundan emin olun
from modules.db.core import engine

# --- MEVCUT FONKSİYONLAR (DEĞİŞİKLİK YOK) ---

def load_portfolio_df() -> pd.DataFrame:
    """
    Portföy tablosunu DataFrame olarak getirir. Sadece belirli sütunları içerir.
    Boşsa sütun başlıkları korunarak boş döner.
    """
    cols = [
        "hisse",  "lot", "maliyet",
        "alis_tarihi", "satis_tarihi", "satis_fiyat", "notu",
    ]
    try:
        return pd.read_sql("SELECT * FROM portfolio", engine)[cols]
    except Exception:                # tablo yoksa
        return pd.DataFrame(columns=cols)

def load_active_portfolio_df() -> pd.DataFrame:
    """
    Sadece aktif (satılmamış) portföy pozisyonlarını DataFrame olarak getirir.
    Boşsa sütun başlıkları korunarak boş döner.
    """
    cols = [
        "id", "hisse",  "lot", "maliyet",
        "alis_tarihi", "satis_tarihi", "satis_fiyat", "graham"
    ]
    try:
        # Sorgu düzeltildi: `id` sütunu `p` tablosundan gelmeli ve cols listesine eklendi.
        return pd.read_sql("""
    SELECT
        p.id,
        p.hisse,
        p.lot,
        p.maliyet,
        p.alis_tarihi,
        p.satis_tarihi,
        p.satis_fiyat,
        rs.graham 
    FROM
        portfolio p
    LEFT JOIN
        radar_scores rs ON rs.hisse = p.hisse
    WHERE
        p.satis_fiyat IS NULL
""", engine)[cols]
    except Exception as e:                # tablo yoksa
        print(f"exception:{e}")
        return pd.DataFrame(columns=cols)

def upsert_portfolio(df: pd.DataFrame,
                     conflict_cols: Optional[list[str]] = None) -> None:
    """
    DataFrame’deki pozisyonları ‘UPSERT’ eder.
    Varsayılan eşsiz anahtar: (hisse, alis_tarihi)
    """
    conflict_cols = conflict_cols or ["hisse", "alis_tarihi"]

    insert_sql = f"""
        INSERT INTO portfolio (
            hisse, lot, maliyet,
            alis_tarihi, satis_tarihi, satis_fiyat, notu
        )
        VALUES (
            :hisse,  :lot, :maliyet,
            :alis_tarihi, :satis_tarihi, :satis_fiyat, :notu
        )
        ON CONFLICT ({", ".join(conflict_cols)})
        DO UPDATE
           SET 
               lot         = EXCLUDED.lot,
               maliyet     = EXCLUDED.maliyet,
               satis_tarihi= EXCLUDED.satis_tarihi,
               satis_fiyat = EXCLUDED.satis_fiyat,
               notu        = EXCLUDED.notu;
    """
    with engine.begin() as conn:
        conn.execute(text(insert_sql), df.to_dict("records"))


# --- YENİ EKLENEN FONKSİYONLAR ---

def load_full_portfolio_df() -> pd.DataFrame:
    """
    Portföy tablosundaki TÜM kayıtları ve SÜTUNLARI getirir.
    Editör sayfası için tasarlanmıştır.
    """
    try:
        df = pd.read_sql("SELECT * FROM portfolio ORDER BY alis_tarihi DESC", engine)
        # Tarih sütunlarını doğru tipe çevirelim
        df['alis_tarihi'] = pd.to_datetime(df['alis_tarihi']).dt.date
        df['satis_tarihi'] = pd.to_datetime(df['satis_tarihi']).dt.date
        return df
    except Exception:
        # Tablo yoksa veya başka bir hata olursa boş DataFrame döndürür.
        # Streamlit tarafında hata kontrolüne gerek kalmaz.
        return pd.DataFrame()

def delete_portfolio_by_id(record_id: int) -> int:
    """
    Verilen ID'ye sahip portföy kaydını siler.
    Dönen değer: Etkilenen satır sayısı (başarılıysa 1, değilse 0).
    """
    delete_sql = text("DELETE FROM portfolio WHERE id = :id")
    with engine.begin() as conn:
        result = conn.execute(delete_sql, {"id": record_id})
        return result.rowcount

# --- END OF FILE portfolio.py ---