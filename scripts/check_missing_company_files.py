import os
import psycopg2 # type: ignore
import urllib.parse as urlparse

# PostgreSQL bağlantı URL'si
PG_URL = "postgresql://postgres:secret@localhost:5432/fin_db"

# data klasörü script'in bir üst dizininde
COMPANIES_BASE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "companies")

def parse_pg_url(pg_url):
    result = urlparse.urlparse(pg_url)
    return {
        "dbname": result.path[1:],
        "user": result.username,
        "password": result.password,
        "host": result.hostname,
        "port": result.port,
    }

def get_company_list_from_db(pg_url):
    config = parse_pg_url(pg_url)
    query = 'SELECT DISTINCT "Şirket" FROM radar_scores'
    try:
        conn = psycopg2.connect(**config)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        company_list = {row[0] for row in rows if row[0]}
        cur.close()
        conn.close()
        return company_list
    except Exception as e:
        logger.exception("Veritabanı hatası:", e)
        return set()

def get_company_list_from_files(base_path):
    companies = set()
    for company_dir in os.listdir(base_path):
        folder = os.path.join(base_path, company_dir)
        if os.path.isdir(folder):
            expected_file = os.path.join(folder, f"{company_dir} (TRY).xlsx")
            if os.path.isfile(expected_file):
                companies.add(company_dir)
    return companies

if __name__ == "__main__":
    db_companies = get_company_list_from_db(PG_URL)
    file_companies = get_company_list_from_files(COMPANIES_BASE_PATH)

    print(f"💾 Dosyadan gelen şirket sayısı: {len(file_companies)}")
    print(f"🗃️  Veritabanından gelen şirket sayısı: {len(db_companies)}")

    missing_in_db = file_companies - db_companies
    print(f"\n🚨 Veritabanında olmayan ama dosyada bulunan şirket sayısı: {len(missing_in_db)}")

    if missing_in_db:
        print("\n📌 Eksik veritabanı kayıtları (dosyada var, DB'de yok):")
        for name in sorted(missing_in_db):
            print("-", name)
    else:
        print("✅ Tüm dosya şirketleri veritabanında mevcut.")
