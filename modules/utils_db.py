from sqlalchemy import create_engine, text  #type: ignore
import pandas as pd
from typing import Optional, Iterable, Mapping
from modules.logger import logger 
from config import PG_URL

# use env‑vars for secrets

engine = create_engine(PG_URL, pool_pre_ping=True)

def read_df(sql: str, params: Optional[Mapping] = None) -> pd.DataFrame:
    """Parametreli sorgu ile DataFrame döndür."""
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

def execute_many(sql: str, rows: Iterable[Mapping]) -> None:
    rows = list(rows)
    if not rows:
        return
    with engine.begin() as conn:
        conn.execute(text(sql), rows)

def scores_table_empty(table: str = "trap") -> bool:
    query = f"SELECT COUNT(*) FROM {table}"
    return pd.read_sql(query, engine).iloc[0, 0] == 0

def load_scores_df(*, table: str = "trap") -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM {table}", engine)

def save_scores_df(df: pd.DataFrame, *, table: str = "trap"):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table};"))
        df.to_sql(table, con=conn, if_exists="append", index=False)

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
        "alis_tarihi", "satis_tarihi", "satis_fiyat", "graham"
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
        rs.graham 
    FROM
        portfolio p
    JOIN
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

def load_filtered_radar_scores(
    f_min=5, graham_min=2, lynch_min=1, m_max=-1.78, mos_min=20.0
) -> pd.DataFrame:
    query = f"""
    SELECT hisse, f_skor, m_skor, graham, lynch,
           icsel_deger_medyan, piyasa_degeri, "MOS", "timestamp"
    FROM public.radar_scores
    WHERE f_skor >= {f_min}
       AND graham >= {graham_min}
       AND lynch >= {lynch_min}
    """
    return pd.read_sql(query, engine)


def save_trend_score(symbol: str, date: pd.Timestamp, metrics: dict) -> None:
    """
    trend_scores (symbol, date) üzerine upsert.
    Şema varsayımı:
      trend_scores(symbol TEXT, date DATE, rsi REAL, sma20 REAL, sma50 REAL, trend TEXT, created_at TIMESTAMPTZ DEFAULT now(),
                   UNIQUE(symbol, date))
    """
    sql = """
    INSERT INTO trend_scores (symbol, date, rsi, sma20, sma50, trend, created_at)
    VALUES (:symbol, :date, :rsi, :sma20, :sma50, :trend, NOW())
    ON CONFLICT (symbol, date)
    DO UPDATE SET
        rsi   = EXCLUDED.rsi,
        sma20 = EXCLUDED.sma20,
        sma50 = EXCLUDED.sma50,
        trend = EXCLUDED.trend,
        created_at = NOW();
    """
    row = {
        "symbol": symbol,
        "date": pd.to_datetime(date).date(),
        "rsi":  metrics.get("rsi"),
        "sma20": metrics.get("sma20"),
        "sma50": metrics.get("sma50"),
        "trend": metrics.get("trend"),
    }
    execute_many(sql, [row])

