import streamlit as st # type: ignore
import pandas as pd
from config import RADAR_XLSX

# Action modules (our library)
from modules.page_actions.radar_analysis import run_radar_analysis_workflow
from modules.page_actions.performance_log import run_performance_log_update
from modules.page_actions.balance_download import run_balance_download_workflow

# Required DB functions
from modules.db.performance_log import load_performance_log
from modules.db.portfolio import load_portfolio_df

st.set_page_config(page_title="Action Center", layout="wide")
st.title("🛠️ Action Center")
st.markdown("Manage all periodic actions like data download, analysis, and updates from this center.")

# Define the tabs
tab1, tab2, tab3 = st.tabs([
    "⚙️ Run Radar Analysis",
    "📘 Update Performance Log",
    "📥 Download Balances"
])

# --- Tab 1: Radar Analysis ---
with tab1:
    st.header("Calculate & Save Radar Scores")
    st.info(
        "This action calculates fundamental and technical analysis scores and saves the results to the `radar_scores` table. \n\n"
        "This process may take a few minutes depending on the number of companies."
    )
    try:
        df_radar = pd.read_excel(RADAR_XLSX)
        df_radar["Şirket"] = df_radar["Şirket"].str.strip()
        companies = df_radar["Şirket"].dropna().unique().tolist()
        st.markdown(f"**Number of companies to be analyzed:** `{len(companies)}`")

        if st.button("🚀 Start Full Analysis", key="run_analysis", type="primary"):
            run_radar_analysis_workflow(companies)

    except FileNotFoundError:
        st.error(f"Radar file not found: `{RADAR_XLSX}`. Please check the file.")
    except Exception as e:
        st.error(f"An error occurred while reading the radar file: {e}")

# --- Tab 2: Performance Log Update ---
with tab2:
    st.header("Update Performance Log Timeline")
    st.info(
        "Finds and adds missing **weekly closing prices** for open positions in the portfolio, from the last log date to today."
    )

    @st.cache_data
    def load_log_data():
        """Loads portfolio and log data from the database."""
        df_portfoy = load_portfolio_df()
        df_log = load_performance_log()
        return df_portfoy, df_log

    df_portfoy, df_log = load_log_data()
    
    if not df_portfoy.empty:
        df_portfoy["alis_tarihi"] = pd.to_datetime(df_portfoy["alis_tarihi"])
        df_portfoy["Hisse"] = df_portfoy["hisse"].str.upper().str.strip()
    if not df_log.empty:
        df_log["tarih"] = pd.to_datetime(df_log["tarih"])
    
    acik_pozisyonlar = df_portfoy[df_portfoy["satis_fiyat"].isna()] if not df_portfoy.empty else pd.DataFrame()

    if st.button("⏱️ Log Missing Weekly Closes", key="run_log_update", type="primary"):
        run_performance_log_update(acik_pozisyonlar, df_log)
        # Reload data to show the most up-to-date log after the operation
        st.cache_data.clear()
        df_portfoy, df_log = load_log_data()

    st.subheader("📊 Current Performance Timeline")
    if df_log.empty:
        st.info("No log entries found yet.")
    else:
        df_display = df_log.copy()
        df_display["tarih"] = pd.to_datetime(df_display["tarih"]).dt.strftime('%d.%m.%Y')
        st.dataframe(
            df_display.sort_values("tarih", ascending=False),
            hide_index=True, use_container_width=True,
            column_config={
                "tarih": st.column_config.TextColumn("Tarih"),
                "fiyat": st.column_config.NumberColumn("Fiyat (TL)", format="%.2f"),
                "lot": st.column_config.NumberColumn("Lot", format="%d"),
            }
        )

# --- Tab 3: Balance Sheet Download ---
with tab3:
    st.header("Fintables Balance Sheet Downloader")
    st.info(
        """
        This tool scans the companies in **data/son_bilancolar.json** and downloads
        the latest balance sheet files from Fintables for those missing them.
        """
    )
    if st.button("🔽 Download Balances", key="download_balances", type="primary"):
        run_balance_download_workflow()

    st.markdown("---")
    with st.expander("Page Description and Technical Details"):
        st.markdown(
            """
            <div style='background-color: #2b2b2b; padding: 12px; border-radius: 8px; margin-top: 10px; font-size: 15px;'>
            This tool automates the download of financial data (balance sheet, income statement, cash flow) from Fintables. It uses browser automation (Selenium) to download the data and saves it to the <code>companies/{Symbol}/</code> folder.
            </div>
            <h4 style='margin-top: 1.5em;'>Developer Notes</h4>
            <ul>
              <li>A dedicated Chrome profile is used for downloading. You may need to manually log in to Fintables on the first use.</li>
              <li>A company's financial file is re-downloaded if it is <strong>missing</strong> or <strong>older than 3 days</strong>.</li>
            </ul>
            """, unsafe_allow_html=True
        )