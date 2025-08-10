import pandas as pd
from modules.db.core import read_df, execute_many

def load_performance_log() -> pd.DataFrame:
    """Tablodaki tüm logu getirir (yoksa boş df döner)."""
    try:
        return read_df("SELECT pl.tarih, pl.hisse, pl.lot, pl.fiyat FROM performance_log pl JOIN portfolio p ON pl.hisse = p.hisse where p.satis_fiyat is null;")
    except Exception:       # tablo yoksa
        return pd.DataFrame(columns=["tarih", "hisse", "lot", "fiyat"])


def upsert_performance_log(df: pd.DataFrame) -> int:
    """
    performance_log (tarih, hisse) benzersiz anahtarı üzerinden toplu UPSERT.
    Dönüş: etkilenmiş satır sayısı (sürücüye bağlı olarak -1 gelebilir).
    """
    if df is None or df.empty:
        return 0

    insert_sql = """
        INSERT INTO performance_log (tarih, hisse, lot, fiyat)
        VALUES (:tarih, :hisse, :lot, :fiyat)
        ON CONFLICT (tarih, hisse)
        DO UPDATE
           SET lot   = EXCLUDED.lot,
               fiyat = EXCLUDED.fiyat;
    """

    # Gerekli kolonları garanti altına al
    cols = ["tarih", "hisse", "lot", "fiyat"]
    rows = df[cols].to_dict("records")

    return execute_many(insert_sql, rows)
