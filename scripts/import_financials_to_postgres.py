import sys
import os

import pandas as pd
from sqlalchemy import create_engine #type: ignore
from pathlib import Path
from datetime import datetime

from pathlib import Path
sys.path.append(os.path.abspath(".."))
from config import RADAR_XLSX

# Proje kökünü bul (scripts/ klasörünün 1 üstü)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# --- AYARLAR ---
PG_URL = "postgresql://postgres:secret@localhost:5432/fin_db"  # ← burayı değiştirin

def load_radar() -> pd.DataFrame:
    df = pd.read_excel(RADAR_XLSX)
    df["Şirket"] = df["Şirket"].str.strip()
    return df

# --- HAZIRLIK ---
engine = create_engine(PG_URL)

def clean_and_melt(company: str, df: pd.DataFrame, statement_type: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str)
    df.rename(columns={df.columns[0]: "item_name"}, inplace=True)
    df = df.dropna(subset=["item_name"])

        # --- sadece cashflow için flow_category ayrımı ---
    if statement_type == "cashflow":
        flow_cat = None
        flow_categories = {
            "İşletme Faaliyetlerinden Nakit Akışları": "operating",
            "Yatırım Faaliyetlerinden Kaynaklanan Nakit Akışları": "investing",
            "Finansman Faaliyetlerinden Nakit Akışları": "financing",
        }

        current_category = None
        category_list = []
        for item in df["item_name"]:
            if item.strip() in flow_categories:
                current_category = flow_categories[item.strip()]
            category_list.append(current_category)

        df["flow_category"] = category_list
        df = df.dropna(subset=["flow_category"])
    else:
        df["flow_category"] = None
    
    df_melted = df.melt(id_vars=["item_name", "flow_category"], var_name="period", value_name="value")
    df_melted["statement_type"] = statement_type
    df_melted["company"] = company

    # Tarih formatını dönüştür: 2023/12 → 2023-12-31
    def convert_period(p):
        try:
            year, month = map(int, p.strip().split("/"))
            return datetime(year, month, 1).date().replace(day=28)  # Dönemi ay sonuna sabitle
        except:
            return pd.NaT
    df_melted["period"] = df_melted["period"].apply(convert_period)
    df_melted = df_melted.dropna(subset=["period"])
    
    return df_melted[["company", "statement_type", "flow_category", "item_name", "period", "value"]]

def import_excel_to_postgres(company):
    excel_path = PROJECT_ROOT / "data" / "companies" / company / f"{company} (TRY).xlsx"
    
    if not excel_path.exists():
        print(f"❌ Excel dosyası bulunamadı: {excel_path}")
        return  
    
    print(f"⏳ Excel dosyası okunuyor: {excel_path}")
    sheets = pd.read_excel(excel_path, sheet_name=None)

    all_data = []

    for sheet_name in sheets:
        df = sheets[sheet_name]
        table_mapping = {
            "bilanço": "balance",
            "gelir tablosu (dönemsel)": "income",
            "nakit akış (dönemsel)": "cashflow",
        }

        sheet_key = sheet_name.lower().strip()
        if sheet_key in table_mapping:
            statement_type = table_mapping[sheet_key]
            melted = clean_and_melt(company, df, statement_type)
            all_data.append(melted)
        else:
            print(f"⚠️ Atlandı: {sheet_name}")


    final_df = pd.concat(all_data, ignore_index=True)

    print(f"✅ Toplam {len(final_df)} satır hazır.")

    # PostgreSQL'e yaz
    final_df.to_sql(
        "financial_statements",
        engine,
        if_exists="append",
        index=False,
        method="multi",         # ← toplu INSERT
        chunksize=1000          # ← her seferinde 1000 satır gönder
    )
    print("🚀 Veri başarıyla PostgreSQL'e aktarıldı.")

if __name__ == "__main__":
    radar = load_radar()
    companies = radar["Şirket"].dropna().unique()
    for company in companies:
        import_excel_to_postgres(company)
