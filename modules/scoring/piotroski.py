from modules.utils import scalar, period_order
from modules.ratios import calculate_roa_ttm
from modules.financial_snapshot import build_snapshot

def calculate_piotroski_f_score(row, balance, income, curr, prev):
    net_profit = scalar(row["Net Dönem Karı"])
    operating_cash_flow = scalar(row["İşletme Faaliyetlerinden Nakit Akışları"])
    f_score = 0
    detail = {}
    detail_str = {}

    detail["Net Kar > 0"] = int(net_profit > 0)
    roa = calculate_roa_ttm(income, balance, period_order)
    detail["ROA > 0"] = int(roa > 0)
    detail["Nakit Akışı > 0"] = int(operating_cash_flow > 0)
    detail["Nakit Akışı > Net Kar"] = int(operating_cash_flow > net_profit)
    f_score += sum(detail.values())

    snap_curr = build_snapshot(balance, income, None, period=curr)
    snap_prev = build_snapshot(balance, income, None, period=prev)

    if None not in (snap_curr.short_term_liabilities, snap_curr.long_term_liabilities, snap_curr.total_assets, snap_prev.short_term_liabilities, snap_prev.long_term_liabilities, snap_prev.total_assets):
        leverage_ratio_curr = (snap_curr.short_term_liabilities + snap_curr.long_term_liabilities) / snap_curr.total_assets
        leverage_ratio_prev = (snap_prev.short_term_liabilities + snap_prev.long_term_liabilities) / snap_prev.total_assets
        detail["Borç Oranı Azalmış"] = int(leverage_ratio_curr < leverage_ratio_prev)
        f_score += detail["Borç Oranı Azalmış"]
    else:
        detail["Borç Oranı Azalmış"] = 0

    if None not in (snap_curr.current_assets, snap_curr.short_term_liabilities, snap_prev.current_assets, snap_prev.short_term_liabilities):
        snap_curr.current_ratio = snap_curr.current_assets / snap_curr.short_term_liabilities
        snap_prev.current_ratio = snap_prev.current_assets / snap_prev.short_term_liabilities
        detail["Cari Oran Artmış"] = int(snap_curr.current_ratio > snap_prev.current_ratio)
        f_score += detail["Cari Oran Artmış"]
    else:
        detail["Cari Oran Artmış"] = 0

    detail["Öz Kaynak Artmış"] = int(snap_curr.equity >= snap_prev.equity) if snap_curr.equity and snap_prev.equity else 0
    f_score += detail["Öz Kaynak Artmış"]

    if None not in (snap_curr.gross_profit, snap_prev.gross_profit, snap_curr.revenue, snap_prev.revenue):
        detail["Brüt Kar Marjı Artmış"] = int((snap_curr.gross_profit / snap_curr.revenue) > (snap_prev.gross_profit / snap_prev.revenue))
        detail["Varlık Devir Hızı Artmış"] = int((snap_curr.revenue / snap_curr.total_assets) > (snap_prev.revenue / snap_prev.total_assets))
        f_score += detail["Brüt Kar Marjı Artmış"] + detail["Varlık Devir Hızı Artmış"]
    else:
        detail["Brüt Kar Marjı Artmış"] = 0
        detail["Varlık Devir Hızı Artmış"] = 0

    # Emojili gösterim (ayrı sözlükte)
    emojis = {
        "Net Kar > 0": "🟢",
        "ROA > 0": "📈",
        "Nakit Akışı > 0": "💸",
        "Nakit Akışı > Net Kar": "🔄",
        "Borç Oranı Azalmış": "📉",
        "Cari Oran Artmış": "💧",
        "Öz Kaynak Artmış": "🏦",
        "Brüt Kar Marjı Artmış": "📊",
        "Varlık Devir Hızı Artmış": "🔁",
    }

    for key, val in detail.items():
        detail_str[f"{emojis.get(key, '')} {key}"] = "✅" if val else "❌"

    return f_score, detail_str

def f_skor_karne_yorum(f_score):
    if f_score is None:
        return "F-Skor verisi eksik"
    
    yorum = f"F-Skor: {f_score} → "
    if f_score >= 7:
        yorum += "✅ Sağlam – Finansal göstergeler güçlü"
    elif 4 <= f_score <= 6:
        yorum += "🟡 Orta seviye – Gelişme sinyalleri izlenmeli"
    else:
        yorum += "❌ Zayıf – Finansal sağlık düşük, temkinli yaklaşılmalı"
    return yorum

class PiotroskiScorer:
    def __init__(self, row, balance, income, curr, prev):
        self.row = row
        self.balance = balance
        self.income = income
        self.curr = curr
        self.prev = prev

    def calculate(self):
        f_score, detail = calculate_piotroski_f_score(
            self.row, self.balance, self.income, self.curr, self.prev
        )
        summary = f_skor_karne_yorum(f_score)
        
        return f_score, summary, detail
    

    