from sqlalchemy import create_engine #type: ignore
import pandas as pd
from modules.logger import logger 

# use env‑vars for secrets
PG_URL = "postgresql://postgres:secret@localhost:5432/fin_db"  # ← burayı değiştirin
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
