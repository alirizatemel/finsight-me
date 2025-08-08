# modules/technical_analysis/trend_indicators.py

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

def calculate_rsi_trend(df: pd.DataFrame) -> dict:
    """
    RSI, SMA20, SMA50 ve trend yönünü hesaplar.
    """
    df = df.copy()
    df['rsi'] = RSIIndicator(df['close'], window=14).rsi()
    df['sma20'] = SMAIndicator(df['close'], window=20).sma_indicator()
    df['sma50'] = SMAIndicator(df['close'], window=50).sma_indicator()

    rsi_val = round(df['rsi'].iloc[-1], 2)
    sma20 = round(df['sma20'].iloc[-1], 2)
    sma50 = round(df['sma50'].iloc[-1], 2)

    if sma20 > sma50:
        trend = "YÜKSELİŞ"
    elif sma20 < sma50:
        trend = "DÜŞÜŞ"
    else:
        trend = "TREND DÖNÜŞÜ"

    return {
        "rsi": rsi_val,
        "sma20": sma20,
        "sma50": sma50,
        "trend": trend
    }
