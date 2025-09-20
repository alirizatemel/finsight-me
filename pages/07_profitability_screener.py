import streamlit as st
import pandas as pd
from pathlib import Path

from config import COMPANIES_DIR, RADAR_XLSX
from modules.finance.profitability import build_profitability_ratios


@st.cache_data(show_spinner=False)
def list_symbols() -> list[str]:
    """Return symbols from RADAR_XLSX 'Şirket' column.

    Falls back to scanning company files if RADAR file is unavailable.
    """
    # Primary: read from radar file
    try:
        df = pd.read_excel(RADAR_XLSX)
        col = None
        # Try common variants to be robust against encoding/label differences
        for c in df.columns:
            cn = str(c).strip().lower()
            if cn in {"şirket", "sirket", "company", "hisse", "symbol"}:
                col = c
                break
        if col is not None:
            syms = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .dropna()
                .unique()
                .tolist()
            )
            return sorted(syms)
    except Exception:
        pass

    # Fallback: scan companies directory
    base = Path(COMPANIES_DIR)
    if not base.exists():
        return []
    syms: list[str] = []
    for p in base.iterdir():
        if p.is_dir():
            x = p / f"{p.name} (TRY).xlsx"
            if x.exists():
                syms.append(p.name)
    return sorted(set(syms))


def evaluate_company(symbol: str,
                     thresholds: dict,
                     min_years_ok: int,
                     max_exception_years: int) -> tuple[bool, dict]:
    """Return (passed, details)."""
    try:
        ratios = build_profitability_ratios(symbol, last_n_years=7)
    except Exception as e:
        return False, {"error": str(e)}

    if ratios.shape[0] < 7:
        return False, {"reason": "Yıllık veri < 7"}

    # Rename to internal keys
    col_map = {
        "ROE (%)": "roe",
        "ROA (%)": "roa",
        "Net Kâr Marjı (%)": "net_margin",
        "Brüt Marj (%)": "gross_margin",
        "FAVÖK Marjı (%)": "ebitda_margin",
    }
    det = {"symbol": symbol, "ratios": ratios}

    # Per-metric majority rule
    metric_pass = {}
    for col, key in col_map.items():
        if col not in ratios:
            metric_pass[key] = False
            continue
        series = ratios[col].dropna()
        if series.empty:
            metric_pass[key] = False
            continue
        ok_years = (series >= thresholds[key]).sum()
        metric_pass[key] = ok_years >= min_years_ok
        det[f"{key}_ok_years"] = int(ok_years)

    if not all(metric_pass.values()):
        det["reason"] = "Çoğunluk eşiği sağlanamadı"
        return False, det

    # Exception years across all metrics (per-year aggregate)
    # A yılının 'tam geçmesi' = tüm metriklerin o yıl eşiği geçmesi
    aligned = ratios[[c for c in col_map.keys() if c in ratios]].dropna(how="any")
    if aligned.shape[0] < 5:  # güvenlik
        det["reason"] = "Yeterli ortak yıl yok"
        return False, det
    per_year_ok = (aligned.iloc[:, 0] >= thresholds["roe"]) & \
                  (aligned.iloc[:, 1] >= thresholds["roa"]) & \
                  (aligned.iloc[:, 2] >= thresholds["net_margin"]) & \
                  (aligned.iloc[:, 3] >= thresholds["gross_margin"]) & \
                  (aligned.iloc[:, 4] >= thresholds["ebitda_margin"]) if aligned.shape[1] == 5 else None

    exception_years = int((~per_year_ok).sum()) if per_year_ok is not None else 7
    det["exception_years"] = exception_years
    if exception_years > max_exception_years:
        det["reason"] = f"İstisna yılı sayısı > {max_exception_years}"
        return False, det

    # Trend rule: last3 >= first3 for all metrics
    last3 = ratios.tail(3)
    first3 = ratios.head(3)
    for col in col_map.keys():
        if col in ratios:
            l = last3[col].mean(skipna=True)
            f = first3[col].mean(skipna=True)
            if pd.notna(l) and pd.notna(f) and l < f:
                det["reason"] = f"Trend zayıf: {col} son3 < ilk3"
                return False, det

    return True, det


def main():
    st.title("💹 Karlılık Kalite Taraması (7Y)")
    st.caption("ROE, ROA, Net/Brüt/FAVÖK marjlarında süreklilik ve trend odaklı filtre")

    symbols = list_symbols()
    if not symbols:
        st.warning("Radar dosyasından şirket listesi alınamadı. Gerekirse 'data/companies' altını kontrol edin.")
        st.stop()

    with st.sidebar:
        st.subheader("Eşikler")
        roe_th = st.number_input("ROE ≥", 0.0, 50.0, 10.0, 0.5)
        roa_th = st.number_input("ROA ≥", 0.0, 50.0, 5.0, 0.5)
        nm_th  = st.number_input("Net Kâr Marjı ≥", 0.0, 80.0, 5.0, 0.5)
        gm_th  = st.number_input("Brüt Marj ≥", 0.0, 90.0, 20.0, 0.5)
        em_th  = st.number_input("FAVÖK Marjı ≥", 0.0, 80.0, 10.0, 0.5)
        min_years_ok = st.slider("Her metrikte en az yıl", 4, 7, 6)
        max_exception_years = st.slider("İzinli istisna yıl sayısı", 0, 3, 2)

    thresholds = {
        "roe": roe_th,
        "roa": roa_th,
        "net_margin": nm_th,
        "gross_margin": gm_th,
        "ebitda_margin": em_th,
    }

    with st.expander("Tablo Kolonlari Aciklamalari"):
        st.markdown(
            "- Sirket: degerlendirilen hisse kodu.\n"
            "- Durum: GECTI ise tum kurallar saglandi, aksi halde GECEMEDI.\n"
            "- ROE yil: son 7 yilda ROE esigi asilan yil sayisi.\n"
            "- ROA yil: son 7 yilda ROA esigi asilan yil sayisi.\n"
            "- NetMarj yil: son 7 yilda Net Kar Marji esigi asilan yil sayisi.\n"
            "- BrutMarj yil: son 7 yilda Brut Marj esigi asilan yil sayisi.\n"
            "- FAVOKMarj yil: son 7 yilda FAVOK Marji esigi asilan yil sayisi.\n"
            "- Istisna yil: ayni yil icinde tum metriklerin birlikte esigi gecemedigi yil sayisi.\n"
            "- Not: gecememe gerekcesi veya hata mesaji."
        )

    st.write(f"Toplam şirket: {len(symbols)}")

    if "scan_profit" not in st.session_state:
        st.session_state.scan_profit = False
    start_btn = st.sidebar.button("Taramayi Baslat")
    if start_btn:
        st.session_state.scan_profit = True
    if not st.session_state.scan_profit:
        st.info("Once filtreleri ayarlayin ve 'Taramayi Baslat' butonuna basin.")
        st.stop()
    results = []
    passed = []
    with st.spinner("Şirketler değerlendiriliyor..."):
        for sym in symbols:
            ok, detail = evaluate_company(sym, thresholds, min_years_ok, max_exception_years)
            detail["passed"] = ok
            results.append(detail)
            if ok:
                passed.append(sym)

    st.subheader(f"Geçenler ({len(passed)})")
    if passed:
        st.dataframe(pd.DataFrame({"Şirket": passed}))
    else:
        st.info("Filtreleri geçen şirket yok. Eşikleri gevşetmeyi deneyin.")

    with st.expander("Tüm Sonuçlar ve Gerekçeler"):
        rows = []
        for d in results:
            rows.append({
                "Şirket": d.get("symbol", "-"),
                "Durum": "✅" if d.get("passed") else "❌",
                "ROE yıl": d.get("roe_ok_years", "-"),
                "ROA yıl": d.get("roa_ok_years", "-"),
                "NetMarj yıl": d.get("net_margin_ok_years", "-"),
                "BrütMarj yıl": d.get("gross_margin_ok_years", "-"),
                "FAVÖKMarj yıl": d.get("ebitda_margin_ok_years", "-"),
                "İstisna yıl": d.get("exception_years", "-"),
                "Not": d.get("reason", d.get("error", "")),
            })
        st.dataframe(pd.DataFrame(rows))

    st.caption("Not: FAVÖK marjı, faaliyet/esas faaliyet kârı + amortisman ile yaklaşık hesaplanır; bazı şirketlerde boş kalabilir.")


if __name__ == "__main__":
    main()
