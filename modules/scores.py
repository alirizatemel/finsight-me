import streamlit as st  # type: ignore

from modules.finance.data_loader import load_financial_data
from modules.scoring.beneish import BeneishScorer
from modules.scoring.graham import GrahamScorer
from modules.scoring.lynch import LynchScorer
from modules.scoring.piotroski import PiotroskiScorer

from modules.finance.fcf import (
    build_fcf_dataframe,
    fcf_yield_series,
)
from modules.finance.plots import (
    plot_fcf_yield_time_series,
    plot_fcf_detailed,
)

# ---------------- Scores ----------------

def calculate_scores(company, row, balance, income, cashflow, current_period, previous_period):
    f_score, f_karne, f_detail = PiotroskiScorer(row, balance, income, current_period, previous_period).calculate()
    m_skor, m_karne, m_lines  = BeneishScorer(company, balance, income, cashflow, current_period, previous_period).calculate()
    graham_skor, graham_karne, graham_lines = GrahamScorer(row).calculate()
    lynch_skor, lynch_karne, lynch_lines = LynchScorer(row).calculate()

    return {
        "f_score": f_score,
        "f_karne": f_karne,
        "m_skor": m_skor,
        "m_karne": m_karne,
        "m_lines": m_lines,
        "graham_skor": graham_skor,
        "graham_karne": graham_karne,
        "graham_lines": graham_lines,
        "lynch_skor": lynch_skor,
        "lynch_karne": lynch_karne,
        "lynch_lines": lynch_lines,
        "detail": f_detail
    }

def generate_report(company, scores, show_details=False):
    lines = [
        f"📌 Şirket: {company}",
        f"Piotroski F-Skor: {scores['f_karne']}",
        f"Beneish M-Skor: {scores['m_karne']}",
        f"Graham Skoru: {scores['graham_skor']}",
        f"Peter Lynch Skoru: {scores['lynch_skor']}",
        ""
    ]

    if show_details:
        lines.append("🔍 F-Skor Detayları:")
        for k, v in scores.get("detail", {}).items():
            lines.append(f"- {k}: {v}")

    lines.append("\n🧾 Graham Karne:")
    lines.append(scores.get("graham_karne", "-"))

    lines.append("\n🧾 Lynch Karne:")
    lines.append(scores.get("lynch_karne", "-"))

    return lines

def show_company_scorecard(company, row, current_period, previous_period):
    try:
        balance, income, cashflow = load_financial_data(company)
        scores = calculate_scores(
            company,
            row,
            balance,
            income,
            cashflow,
            current_period,
            previous_period,
        )

        st.subheader(f"📌 Şirket: {company}")

        st.markdown(f"**Piotroski F-Skor:** {scores['f_karne']}")
        with st.expander("🧾 F-Skor Detayları", expanded=False):
            for k, v in scores.get("detail", {}).items():
                st.markdown(f"- {k}: {v}")

        st.markdown(f"**Beneish M-Skor:** {scores['m_karne']}")
        with st.expander("🧾 Beneish M‑Skor Yorumu", expanded=False):
            for line in scores.get("m_lines", []):
                st.markdown(line)

        st.markdown(f"**Graham Skoru:** {scores['graham_skor']} / 5")
        with st.expander("🧾 Graham Kriterleri", expanded=False):
            for line in scores.get("graham_lines", []):
                st.markdown(line)

        st.markdown(f"**Peter Lynch Skoru:** {scores['lynch_skor']} / 3")
        with st.expander("🧾 Peter Lynch Kriterleri", expanded=False):
            for line in scores.get("lynch_lines", []):
                st.markdown(line)

        return {
            "company": company,
            "periods": {
                "current": current_period,
                "previous": previous_period,
            },
            "scores": {
                "piotroski": scores["f_score"],
                "piotroski_card": scores["f_karne"],
                "piotroski_detail": scores.get("detail", {}),
                "beneish": scores["m_skor"],
                "beneish_card": scores["m_karne"],
                "beneish_lines": scores.get("m_lines", []),
                "graham": scores["graham_skor"],
                "graham_lines": scores.get("graham_lines", []),
                "lynch": scores["lynch_skor"],
                "lynch_lines": scores.get("lynch_lines", []),
            }
        }
    except FileNotFoundError as e:
        st.error(f"⛔ Dosya bulunamadı: {e}")
    except Exception as e:
        st.error(f"⚠️ Hata oluştu: {e}")

# ---------------- Backward-compatible thin wrappers ----------------

def fcf_detailed_analysis(company, row):
    """Return the detailed FCF dataframe (backward-compat)."""
    return build_fcf_dataframe(company, row)

def fcf_detailed_analysis_plot(company, row):
    """Build the FCF dataframe and return a matplotlib FIG (and show via Streamlit)."""
    df = build_fcf_dataframe(company, row)
    fig = plot_fcf_detailed(company, df)
    try:
        import streamlit as st  # type: ignore
        st.pyplot(fig)
    except Exception:
        pass
    return fig

def fcf_yield_time_series(company, row):
    """Backward-compat wrapper: compute FCF yield series and show plot with Streamlit."""
    try:
        series = fcf_yield_series(company, row)
        fig = plot_fcf_yield_time_series(company, series)
        import streamlit as st  # type: ignore
        st.pyplot(fig)
    except Exception as e:
        import streamlit as st  # type: ignore
        st.error(f"⚠️ {company} için grafik oluşturulamadı: {e}")
