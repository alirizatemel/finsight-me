from sqlalchemy import create_engine #type: ignore
import pandas as pd
import os

# use env‑vars for secrets
PG_URL = "postgresql://postgres:secret@localhost:5432/fin_db"  # ← burayı değiştirin
engine = create_engine(PG_URL, pool_pre_ping=True)

def scores_table_empty() -> bool:
    query = "SELECT COUNT(*) FROM radar_scores"
    return pd.read_sql(query, engine).iloc[0, 0] == 0

def load_scores_df() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM radar_scores", engine)

def save_scores_df(df: pd.DataFrame) -> None:
    df.to_sql("radar_scores", engine, if_exists="replace", index=False)
