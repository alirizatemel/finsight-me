from sqlalchemy import text  #type: ignore
import pandas as pd
from modules.logger import logger 
from modules.db.core import read_df, execute_many

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
    return read_df(query)

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

def load_unified_radar_data() -> pd.DataFrame:
    """
    'radar_scores' (temel) ve 'trend_scores' (teknik) tablolarını
    'hisse'/'symbol' üzerinden birleştirir (LEFT JOIN).
    
    'radar_scores' ana tablodur. Her temel skor için en güncel teknik
    skoru (aynı hisse için) bulup ekler.
    
    Dönüş: Tüm skorları içeren tek bir DataFrame.
    """
    # SQL sorgusu, iki tabloyu birleştirir.
    # trend_scores tablosundan sadece en güncel tarihli kaydı almak için
    # window fonksiyonu (ROW_NUMBER) kullanıyoruz.
    query = text("""
    WITH latest_trends AS (
        SELECT
            symbol,
            date,
            rsi,
            sma20,
            sma50,
            trend,
            last_price,
            ROW_NUMBER() OVER(PARTITION BY symbol ORDER BY date DESC) as rn
        FROM trend_scores
    )
    SELECT
        rs.*, -- radar_scores'dan tüm kolonlar
        lt.date AS tech_date, -- Teknik analizin tarihini ayrı bir isimle alalım
        lt.rsi,
        lt.sma20,
        lt.sma50,
        lt.trend,
        lt.last_price
    FROM
        radar_scores rs
    LEFT JOIN
        latest_trends lt ON rs.hisse = lt.symbol AND lt.rn = 1;
    """)
    
    try:
        df = read_df(query)
        # 'date' ve 'timestamp' kolonları çakışabilir veya kafa karıştırabilir.
        # Ana tarih olarak radar_scores'daki timestamp'i kullanalım.
        # Teknik analizin tarihini tech_date olarak aldık, gerekirse kullanılabilir.
        if 'date' in df.columns and 'tech_date' in df.columns:
                df.rename(columns={'tech_date': 'date'}, inplace=True)
                 
        return df
    except Exception as e:
        # Hata durumunda veya tablolar boşsa, logla ve boş DataFrame dön.
        logger.error(f"Birleşik radar verisi yüklenirken hata oluştu: {e}")
        return pd.DataFrame()