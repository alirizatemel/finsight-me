import os
import time
import shutil
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMP_DIR = os.path.join(BASE_DIR, "downloads")
COMPANY_DIR = os.path.join(BASE_DIR, "companies")

RADAR_XLSX = "companies/test_radar.xlsx"

loglar = []

def load_radar() -> pd.DataFrame:
    """Read Fintables radar sheet once & cache."""
    df = pd.read_excel(RADAR_XLSX)
    df["Şirket"] = df["Şirket"].str.strip()
    return df

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(COMPANY_DIR, exist_ok=True)

def configure_driver():
    options = Options()
    options.add_argument(r"user-data-dir=C:\selenium_data")  # tamamen özel, karışmayan dizin

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--disable-extensions")
    options.add_argument("--start-maximized")

    options.add_experimental_option("prefs", {
        "download.default_directory": TEMP_DIR,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    })

    return webdriver.Chrome(options=options)

def download_all_companies():

    driver = configure_driver()
    time.sleep(3)
    radar = load_radar()
    companies = radar["Şirket"].unique()

    print(f"{len(companies)} şirket bulundu")

    for c in companies:
        try:
            folder = os.path.join(COMPANY_DIR, c)
            os.makedirs(folder, exist_ok=True)

            driver.get(f"https://fintables.com/sirketler/{c}/finansal-tablolar/bilanco")
            time.sleep(2)

            excel_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(text(), \"Excel'e Aktar\")]"))
            )
            excel_button.click()
            time.sleep(5)

            file_name = f"{c} (TRY).xlsx"
            src = os.path.join(TEMP_DIR, file_name)
            dst = os.path.join(folder, file_name)

            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"{c} ✓ indirildi")
            else:
                print(f"{c} ⚠️ dosya bulunamadı")

        except Exception as e:
            print(f"{c} hata: {e}")

    driver.quit()
