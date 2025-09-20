import pandas as pd

def graham_score(row):
    if not row.empty:
        row = row.iloc[0]
    score = 0
    if pd.notnull(row['F/K']) and row['F/K'] < 15:
        score += 1
    if pd.notnull(row['PD/DD']) and row['PD/DD'] < 1.5:
        score += 1
    if pd.notnull(row['Cari Oran']) and 2 < row['Cari Oran'] < 100:
        score += 1
    if pd.notnull(row['İşletme Faaliyetlerinden Nakit Akışları']) and row['İşletme Faaliyetlerinden Nakit Akışları'] > 0:
        score += 1
    if pd.notnull(row['Yıllıklandırılmış Serbest Nakit Akışı']) and row['Yıllıklandırılmış Serbest Nakit Akışı'] > 0:
        score += 1
    return score

def graham_score_card(row):
    # Kabul edilen tipler: DataFrame (tek satır beklenir) veya Series
    if isinstance(row, pd.DataFrame):
        if row.empty:
            row = pd.Series(dtype=float)
        else:
            row = row.iloc[0]
    elif not isinstance(row, pd.Series):
        row = pd.Series(dtype=float)

    score = 0
    lines = []

    items = [
        ("F/K", row.get("F/K") if hasattr(row, "get") else None, lambda x: x < 15, "F/K < 15"),
        ("PD/DD", row.get("PD/DD") if hasattr(row, "get") else None, lambda x: x < 1.5, "PD/DD < 1.5"),
        ("Cari Oran", row.get("Cari Oran") if hasattr(row, "get") else None, lambda x: 2 < x < 100, "2 < Cari Oran < 100"),
        ("Nakit Akışı", row.get("İşletme Faaliyetlerinden Nakit Akışları") if hasattr(row, "get") else None, lambda x: x > 0, "İşletme Nakit Akışı > 0"),
        ("Serbest Nakit Akışı", row.get("Yıllıklandırılmış Serbest Nakit Akışı") if hasattr(row, "get") else None, lambda x: x > 0, "Yıllıklandırılmış FCF > 0"),
    ]

    for label, value, condition, desc in items:
        v = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.notna(v):
            passed = bool(condition(float(v)))
            # Güvenli gösterim
            disp = f"{float(v):.2f}" if label in ("F/K", "PD/DD", "Cari Oran") else f"{float(v):.0f}"
            lines.append(f"- {label} = {disp} → {'✅' if passed else '❌'} ({desc})")
            score += int(passed)
        else:
            lines.append(f"- {label} verisi eksik")

    description = f"Graham Skoru: {score} / 5"
    return score, description, lines


class GrahamScorer:
    def __init__(self, row):
        self.row = row

    def calculate(self):

        g_score, summary, lines = graham_score_card(self.row)
        return g_score, summary, lines
