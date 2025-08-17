# modules/page_actions/radar_analysis.py
import streamlit as st
import pandas as pd
import inspect

# Domain functions
from modules.scanner import run_scan
from modules.db.trend_scores import get_or_compute_today  # computes today's technicals
from modules.db.core import save_dataframe  # generic upsert/insert helper

FUNDAMENTAL_TARGET_TABLE = "radar_scores"
TECHNICAL_TARGET_TABLE = "trend_scores"

# These are dropped from fundamentals before writing to radar_scores
FUNDAMENTAL_TECH_COLS = {"rsi", "sma20", "sma50", "trend", "last_price", "date", "tarih"}
TECH_COLS_PREFERRED_ORDER = ["symbol", "hisse", "date", "tarih", "last_price", "fiyat", "rsi", "sma20", "sma50", "trend"]


def _strip_technical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove any technical columns that should no longer live in radar_scores."""
    drop_cols = [c for c in df.columns if c in FUNDAMENTAL_TECH_COLS]
    if drop_cols:
        df = df.drop(columns=drop_cols, errors="ignore")
    return df


def _rename_fundamental_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize fundamental dataframe columns to match `radar_scores` schema.
    - Expect 'Şirket' to be used as the join key in many places; rename to 'hisse' for DB.
    """
    renames = {}
    if "Şirket" in df.columns and "hisse" not in df.columns:
        renames["Şirket"] = "hisse"
    return df.rename(columns=renames)


def _ensure_tech_column_order(df: pd.DataFrame) -> pd.DataFrame:
    cols = []
    for c in TECH_COLS_PREFERRED_ORDER:
        if c in df.columns and c not in cols:
            cols.append(c)
    # keep any extra columns to the right (if present)
    extra = [c for c in df.columns if c not in cols]
    return df[cols + extra] if cols else df


def run_fundamental_analysis(df_radar: pd.DataFrame) -> pd.DataFrame:
    """
    Runs fundamental analysis pipeline and returns a DB-ready dataframe.
    """
    df_fundamental, _, _ = run_scan(df_radar)

    df_fundamental = _rename_fundamental_columns(df_fundamental)
    df_fundamental = _strip_technical_columns(df_fundamental)

    return df_fundamental


def persist_fundamentals(df_fundamental: pd.DataFrame) -> None:
    st.info(f"💾 Temel analiz sonuçları `{FUNDAMENTAL_TARGET_TABLE}` tablosuna kaydediliyor...")
    
    unique_columns = ['hisse', 'period']

    # DataFrame'in bu sütunları içerdiğinden emin olalım.
    if not all(col in df_fundamental.columns for col in unique_columns):
        missing = [col for col in unique_columns if col not in df_fundamental.columns]
        st.error(
            f"`{FUNDAMENTAL_TARGET_TABLE}` tablosuna kayıt için gerekli olan "
            f"`{', '.join(missing)}` sütun(ları) bulunamadı."
        )
        return

    # `save_dataframe` fonksiyonunu upsert modunda çağırıyoruz.
    save_dataframe(df_fundamental, table=FUNDAMENTAL_TARGET_TABLE, index_elements=unique_columns)
    
    st.success("✅ Temel analiz verileri başarıyla kaydedildi.")


def run_technical_analysis(companies: list, force_refresh: bool = False) -> pd.DataFrame:
    """
    Computes/retrieves today's technical metrics for the given companies.

    This function is resilient to different signatures of
    `modules.db.trend_scores.get_or_compute_today`, trying common
    parameter names such as: companies, symbols, tickers, or a positional.
    """
    sig = inspect.signature(get_or_compute_today)
    param_names = [p.name for p in sig.parameters.values()
                   if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]

    # Build common kwargs variants
    variants = []
    if "companies" in param_names:
        variants.append(dict(companies=companies, force_refresh=force_refresh))
    if "symbols" in param_names:
        variants.append(dict(symbols=companies, force_refresh=force_refresh))
    if "tickers" in param_names:
        variants.append(dict(tickers=companies, force_refresh=force_refresh))

    # If none of the common names matched, try positional and force_refresh kw
    tried = []
    df_tech = None
    last_err = None

    try:
        for kwargs in variants:
            tried.append(f"get_or_compute_today({', '.join([f'{k}={{...}}' for k in kwargs])})")
            df_tech = get_or_compute_today(**kwargs)  # type: ignore[arg-type]
            if df_tech is not None:
                break
    except TypeError as e:
        last_err = e
        df_tech = None

    if df_tech is None:
        # Try (companies) positional + force_refresh if present
        try:
            if "force_refresh" in param_names and len(param_names) >= 1:
                df_tech = get_or_compute_today(companies, force_refresh=force_refresh)  # type: ignore[misc]
                tried.append("get_or_compute_today(companies, force_refresh=...) [positional]")
            else:
                df_tech = get_or_compute_today(companies)  # type: ignore[misc]
                tried.append("get_or_compute_today(companies) [positional]")
        except TypeError as e:
            last_err = e
            df_tech = None

    if df_tech is None:
        # Try calling without the list (maybe it computes for all)
        try:
            if "force_refresh" in param_names:
                df_tech = get_or_compute_today(force_refresh=force_refresh)  # type: ignore[misc]
                tried.append("get_or_compute_today(force_refresh=...)")
            else:
                df_tech = get_or_compute_today()  # type: ignore[misc]
                tried.append("get_or_compute_today()")
        except TypeError as e:
            last_err = e
            df_tech = None

    if df_tech is None:
        tried_str = " -> ".join(tried) if tried else "no attempts?"
        raise TypeError(f"Could not call get_or_compute_today with any known signature. Tried: {tried_str}. Last error: {last_err}")

    # Filter to requested companies if function returned broader set
    try:
        # Accept common symbol column names
        symbol_col = None
        for cand in ["symbol", "hisse", "Şirket"]:
            if cand in df_tech.columns:
                symbol_col = cand
                break
        if symbol_col is not None and companies:
            df_tech = df_tech[df_tech[symbol_col].isin(companies)].copy()
    except Exception:
        # non-fatal: keep whatever came back
        pass

    # Ensure date column exists; if not, fill with today
    if "date" not in df_tech.columns and "tarih" not in df_tech.columns:
        try:
            df_tech["date"] = pd.Timestamp.today().date()
        except Exception:
            pass

    # Order columns if possible (keeps extras to the right)
    df_tech = _ensure_tech_column_order(df_tech)

    return df_tech


# modules/page_actions/radar_analysis.py dosyasında

def persist_technicals(df_tech: pd.DataFrame) -> None:
    st.info(f"💾 Teknik metrikler `{TECHNICAL_TARGET_TABLE}` tablosuna kaydediliyor...")
    
    # --- DEĞİŞİKLİK BURADA ---
    # `save_dataframe` fonksiyonuna hangi sütunların unique olduğunu belirtiyoruz.
    # Bu sayede fonksiyon, "append" yerine "upsert" yapacak.
    unique_columns = ['symbol', 'date']

    # Gelen DataFrame'de 'symbol' veya 'date' sütunları olmayabilir, kontrol edelim.
    # Örneğin 'hisse' varsa 'symbol' olarak kabul edilebilir.
    # Bu basit kontrolü ekleyelim:
    if 'hisse' in df_tech.columns and 'symbol' not in df_tech.columns:
        df_tech = df_tech.rename(columns={'hisse': 'symbol'})
    if 'tarih' in df_tech.columns and 'date' not in df_tech.columns:
        df_tech = df_tech.rename(columns={'tarih': 'date'})

    # Sütunların varlığından emin olalım
    if not all(col in df_tech.columns for col in unique_columns):
        missing = [col for col in unique_columns if col not in df_tech.columns]
        st.error(f"Kaydetme işlemi için gerekli olan `{', '.join(missing)}` sütun(ları) bulunamadı.")
        return

    save_dataframe(df_tech, table=TECHNICAL_TARGET_TABLE, index_elements=unique_columns)
    # --- DEĞİŞİKLİK SONU ---

    st.success("✅ Teknik metrikler başarıyla kaydedildi.")


def render_analysis_controls(df_radar: pd.DataFrame, companies: list):
    """
    Streamlit UI:
      - Separate buttons for triggering fundamental vs technical analysis.
      - Shows small previews and persists to their respective tables.
    """
    st.subheader("⚙️ Analiz İşlemleri")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Temel Analizi Güncelle", type="primary", use_container_width=True):
            try:
                with st.spinner("📊 Temel analiz skorları hesaplanıyor..."):
                    df_fund = run_fundamental_analysis(df_radar)
                    with st.expander("Temel Analiz (ilk 10 satır)"):
                        st.dataframe(df_fund.head(10))
                persist_fundamentals(df_fund)
                st.balloons()
            except Exception as e:
                with st.expander("Hata Detayı", expanded=False):
                    st.exception(e)
                st.error("Temel analiz güncelleme sırasında bir hata oluştu.")

    with col2:
        if st.button("Teknik Metrikleri Güncelle", use_container_width=True):
            try:
                with st.spinner("📈 Teknik metrikler hesaplanıyor / geri çağrılıyor..."):
                    df_tech = run_technical_analysis(companies, force_refresh=False)
                    with st.expander("Teknik Metrikler (ilk 10 satır)"):
                        st.dataframe(df_tech.head(10))
                persist_technicals(df_tech)
                st.toast("Trend verileri trend_scores'a kaydedildi.", icon="✅")
            except Exception as e:
                with st.expander("Hata Detayı", expanded=False):
                    st.exception(e)
                st.error("Teknik metrik güncelleme sırasında bir hata oluştu.")


# Backward-compatible API (if older pages import run_radar_analysis_workflow)
def run_radar_analysis_workflow(df_radar: pd.DataFrame, companies: list):
    """
    Backward compatibility shim:
    Instead of computing & merging into radar_scores, render two buttons
    that trigger separate pipelines. This avoids mixing technical columns
    into `radar_scores` and saves technicals into `trend_scores`.
    """
    render_analysis_controls(df_radar, companies)
