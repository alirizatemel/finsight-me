#!/usr/bin/env python
"""
Bulk-imports historical performance records from
../data/performans_log.xlsx  →  performance_log (PostgreSQL).

Requires:
  pip install pandas openpyxl  # openpyxl for .xlsx parsing
"""
import sys
from pathlib import Path
import pandas as pd

# ── NEW: make <project_root> importable ───────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parents[1]   # .. (one level up from /scripts)

EXCEL_PATH = ROOT_DIR / "data" / "performans_log.xlsx"

if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))               # add once, reusable everywhere
# -----------------------------------------------------------------------------

from modules.db.performance_log import upsert_performance_log

def load_excel(path: Path) -> pd.DataFrame:
    """Read the Excel file and bring column names / types in line with the DB."""
    df = (
        pd.read_excel(path)
          .rename(
              columns={
                  "Tarih": "tarih",
                  "Hisse": "hisse",
                  "Lot":   "lot",
                  "Fiyat": "fiyat",
              }
          )
    )

    # ── tidy up ────────────────────────────────────────────────────────────────
    df["tarih"] = pd.to_datetime(df["tarih"]).dt.date
    df["hisse"] = (
        df["hisse"]
          .astype(str)
          .str.upper()
          .str.strip()
    )
    df["lot"]   = pd.to_numeric(df["lot"],   errors="coerce").astype("Int64")
    df["fiyat"] = pd.to_numeric(df["fiyat"], errors="coerce")

    # at least ‘tarih’ & ‘hisse’ must be present
    df = df.dropna(subset=["tarih", "hisse"])

    return df


def main() -> None:
    df = load_excel(EXCEL_PATH)
    if df.empty:
        print("No valid rows found – nothing to import.")
        return

    print(f"Importing {len(df)} rows …")
    upsert_performance_log(df)      # ← will do one-by-one UPSERT per row
    print("Done – table is up to date.")


if __name__ == "__main__":
    main()
