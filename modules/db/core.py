# modules/db/core.py
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Any
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text  # SQLAlchemy 2.x
from sqlalchemy.engine import Engine, Result
from sqlalchemy.exc import SQLAlchemyError
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


def save_dataframe(df: pd.DataFrame, *, table: str, truncate: bool = False) -> None:
    """
    DataFrame'i tabloya yazar. truncate=True ise önce tabloyu boşaltır.
    Not: to_sql için connection context'i engine.begin ile veriyoruz.
    """
    with engine.begin() as conn:
        if truncate:
            conn.execute(text(f'TRUNCATE TABLE "{table}";'))
        df.to_sql(table, con=conn, if_exists="append", index=False)


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
