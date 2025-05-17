from sqlalchemy import create_engine, text  #type: ignore
import pandas as pd
from typing import Optional
from modules.logger import logger 

# use env‑vars for secrets
PG_URL = "postgresql://postgres:secret@localhost:5432/fin_db"
engine = create_engine(PG_URL, pool_pre_ping=True)

def scores_table_empty(table: str = "trap") -> bool:
    query = f"SELECT COUNT(*) FROM {table}"
    return pd.read_sql(query, engine).iloc[0, 0] == 0

def load_scores_df(*, table: str = "trap") -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM {table}", engine)

def save_scores_df(df: pd.DataFrame, *, table: str = "trap"):
    try:
        df.to_sql(table, engine, if_exists="replace", index=False)
    except Exception as e:
        logger.exception("DB save failed:", e)
        raise

# ——— PERFORMANCE LOG yardımcıları ———
def load_performance_log() -> pd.DataFrame:
    """Tablodaki tüm logu getirir (yoksa boş df döner)."""
    try:
        return pd.read_sql("SELECT pl.tarih, pl.hisse, pl.lot, pl.fiyat FROM performance_log pl JOIN portfolio p ON pl.hisse = p.hisse where p.satis_fiyat is null;", engine)
    except Exception:       # tablo yoksa
        return pd.DataFrame(columns=["tarih", "hisse", "lot", "fiyat"])

def upsert_performance_log(df: pd.DataFrame) -> None:
    """
    DataFrame satırlarını performance_log’a ‘UPSERT’ eder.
    tarih-hisse benzersiz olduğu için duplicate eklenmez,
    lot ve fiyat güncellenir.
    """
    insert_sql = """
        INSERT INTO performance_log (tarih, hisse, lot, fiyat)
        VALUES (:tarih, :hisse, :lot, :fiyat)
        ON CONFLICT (tarih, hisse)
        DO UPDATE
           SET lot   = EXCLUDED.lot,
               fiyat = EXCLUDED.fiyat;
    """
    try:
        with engine.begin() as conn:
            conn.execute(
                text(insert_sql),
                df[["tarih", "hisse", "lot", "fiyat"]].to_dict("records"),
            )
    except Exception as e:
        logger.exception("Performance-log upsert failed:", e)
        raise

# --- yeni fonksiyonlar -------------------------------------------------------
def load_portfolio_df() -> pd.DataFrame:
    """
    Portföy tablosunu DataFrame olarak getirir.
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
    Portföy tablosunu DataFrame olarak getirir.
    Boşsa sütun başlıkları korunarak boş döner.
    """
    cols = [
        "hisse",  "lot", "maliyet",
        "alis_tarihi", "satis_tarihi", "satis_fiyat", "graham_skor"
    ]
    try:
        return pd.read_sql("""
    SELECT
        p.id,
        p.hisse,
        p.lot,
        p.maliyet,
        p.alis_tarihi,
        p.satis_tarihi,
        p.satis_fiyat,
        rs."Graham" AS graham_skor 
    FROM
        portfolio p
    JOIN
        radar_scores rs ON rs."Şirket" = p.hisse
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