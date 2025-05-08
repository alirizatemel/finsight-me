import pandas as pd
from modules.utils import scalar
from modules.financial_snapshot import build_snapshot


def calculate_roa_ttm(income: pd.DataFrame, balance: pd.DataFrame, period_order_fn) -> float:
    """
    Adım adım loglayarak Yıllıklandırılmış ROA hesapla:
    ROA = (TTM Net Kar) / (Ortalama Toplam Varlık) * 100

    Returns:
        float: Yüzde olarak ROA (örn: -4.92)
    """
    try:
        # 1️⃣ Geçerli ortak dönemleri sırala
        valid_periods = sorted(
            [c for c in income.columns if "/" in c and c in balance.columns],
            key=period_order_fn,
            reverse=True
        )
        print("📅 Ortak dönemler:", valid_periods[:4])

        # 2️⃣ Net Kar verilerini topla
        net_incomes = []
        for p in valid_periods[:4]:
            snap_curr = build_snapshot(balance, income, None, period=p)
            val = scalar(snap_curr.net_profit)
            print(f"📈 Net Kar [{p}]:", val)
            net_incomes.append(val or 0)

        net_income_ttm = sum(net_incomes)
        print("🧮 TTM Net Kar:", net_income_ttm)

        # 3️⃣ Toplam Varlık verilerini al (2 dönem)
        assets = []
        for p in valid_periods[:4]:
            snap_curr = build_snapshot(balance, income, None, period=p)
            val = scalar(snap_curr.total_assets)
            print(f"🏦 Toplam Varlık [{p}]:", val)
            assets.append(val or 0)

        if all(a > 0 for a in assets):
            avg_assets = sum(assets) / 4
            print("🧾 Ortalama Toplam Varlık:", avg_assets)
        else:
            avg_assets = None
            print("⚠️ Ortalama varlık hesaplanamadı (eksik veri)")

        # 4️⃣ ROA hesapla
        roa = (net_income_ttm / avg_assets) * 100 if avg_assets else 0
        print(f"✅ ROA (TTM): {roa:.2f}%")
        return roa

    except Exception as e:
        print("🚨 ROA TTM hesaplama hatası:", e)
        return 0


