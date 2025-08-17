# modules/db/core.py
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Any
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text, Table, MetaData  # SQLAlchemy 2.x
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from modules.logger import logger  # projendeki logger

# --- Bağlantı ayarı ---------------------------------------------------------
# 1) config.PG_URL varsa onu kullan; yoksa ortam değişkeninden oku.
try:
    from config import PG_URL  # projen varsa genelde burada duruyor
except Exception:
    PG_URL = os.getenv("PG_URL", "postgresql+psycopg2://user:pass@localhost:5432/dbname")

# Tek bir engine yarat ve paylaş (Streamlit tekrar yüklemelerinde sağlam kalsın)
# pool_pre_ping: ölü bağlantıları tespit eder
# pool_recycle: uzun süreli idle bağlantıların yenilenmesini sağlar (ör: 1 saat = 3600sn)
engine: Engine = create_engine(
    PG_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    # echo=True,  # debug için açabilirsin
)

__all__ = [
    "engine",
    "read_df",
    "execute_many",
    "execute_one",
    "fetch_value",
    "save_dataframe",
    "scores_table_empty",
]


# --- Basit yardımcılar ------------------------------------------------------
def read_df(sql: str, params: Optional[Mapping[str, Any]] = None) -> pd.DataFrame:
    """
    Parametreli SELECT çalıştır ve DataFrame döndür.
    Kullanım: read_df("SELECT * FROM t WHERE d >= :d", {"d": "2025-01-01"})
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)


def execute_many(sql: str, rows: Iterable[Mapping[str, Any]]) -> int:
    """
    Çok satırlı INSERT/UPDATE için atomik execute.
    Dönüş: etkilenen satır tahmini (vendor'a göre değişebilir, garanti değil).
    """
    rows = list(rows)
    if not rows:
        return 0
    try:
        with engine.begin() as conn:
            res: Result = conn.execute(text(sql), rows)
            # bazı sürücüler rowcount sağlamayabilir
            return getattr(res, "rowcount", -1) or -1
    except SQLAlchemyError as e:
        logger.exception("execute_many failed")
        raise


def execute_one(sql: str, params: Optional[Mapping[str, Any]] = None) -> int:
    """
    Tek sorgu (INSERT/UPDATE/DDL) çalıştır. (ULTRA DETAYLI HATA AYIKLAMA MODU)
    """

    stmt = text(sql)
    parameters = params or {}

    try:
        with engine.begin() as conn:
            res: Result = conn.execute(stmt, parameters)
            rowcount = res.rowcount if res.rowcount is not None else -1
            
            sys.stderr.flush()
            return rowcount
    except SQLAlchemyError as e:
        # Hatanın orijinal traceback'ini (izini) de yazdıralım
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        # Hatayı yine de yukarıya fırlatıyoruz ki Streamlit bunu görsün.
        raise


def fetch_value(sql: str, params: Optional[Mapping[str, Any]] = None) -> Any:
    """
    Tek değer dönen sorgular için yardımcı (COUNT(*), MAX(date) gibi).
    """
    with engine.connect() as conn:
        res: Result = conn.execute(text(sql), params or {})
        row = res.fetchone()
        return None if row is None else row[0]


def save_dataframe(df: pd.DataFrame, table: str, index_elements: list = None):
    """
    Saves a DataFrame to a database table.
    
    If `index_elements` are provided, it performs an "upsert" operation
    (updates on conflict, inserts if new) based on those unique key columns.
    Otherwise, it performs a simple append.

    Args:
        df (pd.DataFrame): The dataframe to save.
        table (str): The name of the target database table.
        index_elements (list, optional): A list of column names that form the
                                          unique constraint. For upserting.
                                          Defaults to None (simple append).
    """
    
    if not index_elements:
        # Eski davranış: Basitçe ekle (append)
        df.to_sql(table, con=engine, if_exists="append", index=False)
        return

    # Yeni davranış: Upsert (Update or Insert)
    with engine.connect() as conn:
        with conn.begin(): # Transaksiyon başlat
            # DataFrame'i dictionary listesine çevir
            data_to_insert = df.to_dict(orient='records')
            
            # SQLAlchemy kullanarak tablo nesnesini al
            
            metadata = MetaData()
            target_table = Table(table, metadata, autoload_with=engine)
            
            # PostgreSQL'e özel INSERT ... ON CONFLICT ifadesini oluştur
            stmt = pg_insert(target_table).values(data_to_insert)
            
            # Güncellenecek sütunları belirle
            # Unique key olanlar hariç diğer tüm sütunları güncelle
            update_cols = {
                c.name: c for c in stmt.excluded if c.name not in index_elements
            }
            
            # ON CONFLICT ifadesini tamamla
            # Eğer index_elements'a göre bir çakışma olursa, update_cols'u güncelle
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_cols,
            )
            
            # Komutu çalıştır
            conn.execute(upsert_stmt)   


def scores_table_empty(table: str) -> bool:
    """
    Tablo boş mu? (True/False)
    """
    try:
        cnt = fetch_value(f'SELECT COUNT(*) FROM "{table}"')
        return int(cnt or 0) == 0
    except Exception as e:
        # tablo yoksa da "boş" varsay
        logger.warning(f'scores_table_empty("{table}") check failed: {e}')
        return True
