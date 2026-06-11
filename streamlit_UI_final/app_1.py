import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import threading
import time
import folium
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
has_plotly = True
from folium.plugins import MarkerCluster
from datetime import datetime

# Insert current directory into path for local imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import backend scheduler and validator
from scheduler_osrm import (
    MultiSalesManScheduler,
    MultiScheduleResult,
    build_route_map_for_salesperson,
    build_territory_day_map,
    build_stop_to_stop_distance_table,
    build_stop_to_stop_map,
    export_stop_to_stop_excel,
    export_under_visited_excel,
)
from validate_schedule_final import validate_schedule_final, diagnose_schedule_failure

# Try importing streamlit_folium
try:
    from streamlit_folium import st_folium
    has_streamlit_folium = True
except ImportError:
    has_streamlit_folium = False

# Paths
# BASE_DIR = os.path.abspath(os.path.join(current_dir, "..", ".."))
BASE_DIR = r'D:\Data Science\Basamh\JP_Yash\journey-planner\streamlit_UI_final'
DATA_DIR = os.path.join(BASE_DIR, "saudi_master_data_output")
OUTPUT_DIR = os.path.join(BASE_DIR, "jp_data_output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------
# PAGE SETUP & STYLING
# ------------------------------------------------------------
st.set_page_config(
    page_title="DelivIQ | Premium Saudi Journey Planner",
    page_icon="DQ",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject custom modern CSS
st.markdown("""
<style>
    /* Global Background and Fonts */
    .stApp {
        background-color: #F8F9FC;
    }

    /* Title and headers */
    h1, h2, h3 {
        color: #1E293B !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }

    /* Metrics / Stat Card */
    .stat-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.03);
        border: 1px solid #E2E8F0;
        transition: all 0.3s ease;
        margin-bottom: 1rem;
    }
    .stat-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 25px rgba(79, 127, 250, 0.08);
        border-color: #CBD5E1;
    }
    .stat-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.7px;
        margin-bottom: 0.5rem;
    }
    .stat-value {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0F172A;
    }

    /* Badges */
    .custom-badge {
        padding: 6px 14px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.75rem;
        display: inline-block;
        text-align: center;
    }
    .badge-high { background-color: #FEE2E2; color: #EF4444; }
    .badge-medium { background-color: #FEF3C7; color: #D97706; }
    .badge-low { background-color: #F1F5F9; color: #64748B; }

    /* Status Checklist card */
    .checklist-card {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        border-left: 5px solid #E2E8F0;
        margin-bottom: 0.75rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }
    .checklist-pass { border-left-color: #10B981; }
    .checklist-info { border-left-color: #3B82F6; }
    .checklist-fail { border-left-color: #EF4444; }

    /* Preformatted Code (Terminal) Styling */
    .terminal-container {
        background-color: #0F172A !important;
        color: #38BDF8 !important;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Courier New', Courier, monospace;
        border: 1px solid #1E293B;
        max-height: 400px;
        overflow-y: auto;
    }

    /* ── Dark Sidebar Theme ───────────────────────────────── */
    section[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid #1E293B;
    }
    /* Make all sidebar text light */
    section[data-testid="stSidebar"] * {
        color: #E2E8F0 !important;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }
    /* Radio / widget option labels */
    section[data-testid="stSidebar"] .stRadio label,
    section[data-testid="stSidebar"] label {
        color: #CBD5E1 !important;
    }
    /* Dividers inside sidebar */
    section[data-testid="stSidebar"] hr {
        border-color: #1E293B !important;
    }
    /* Sidebar input / select boxes */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] input {
        background-color: #1E293B !important;
        color: #E2E8F0 !important;
        border-color: #334155 !important;
    }
    /* Logo container */
    .sidebar-logo {
        background: #FFFFFF;
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 1rem;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0,0,0,0.25);
    }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# DATA LOADING UTILITIES
# ------------------------------------------------------------
@st.cache_data(ttl=600)
def load_master_data():
    def get_sheet_df(xls, candidate_names, fallback_empty=False):
        for name in candidate_names:
            for sheet in xls.sheet_names:
                if sheet.strip().lower() == name.lower():
                    return pd.read_excel(xls, sheet_name=sheet)
        if fallback_empty:
            return pd.DataFrame()
        raise ValueError(f"Could not find any of the sheets {candidate_names} in the Excel file.")

    # Attempt to load the holiday list from holiday_1.xlsx or holiday_1.csv first
    holiday_df = None
    holiday_xlsx_path = os.path.join(DATA_DIR, "holiday_1.xlsx")
    holiday_csv_path = os.path.join(DATA_DIR, "holiday_1.csv")

    if os.path.exists(holiday_xlsx_path):
        try:
            holiday_df = pd.read_excel(holiday_xlsx_path)
            holiday_df.columns = [c.strip() for c in holiday_df.columns]
        except Exception as e:
            st.warning(f"Failed to load holiday from {holiday_xlsx_path}: {e}")
    elif os.path.exists(holiday_csv_path):
        try:
            holiday_df = pd.read_csv(holiday_csv_path)
            holiday_df.columns = [c.strip() for c in holiday_df.columns]
        except Exception as e:
            st.warning(f"Failed to load holiday from {holiday_csv_path}: {e}")

    # Check saudi_master_data_output first, then jp_data_output
    xlsx_path = os.path.join(DATA_DIR, "jp_data.xlsx")
    if not os.path.exists(xlsx_path):
        xlsx_path = os.path.join(OUTPUT_DIR, "jp_data.xlsx")

    if os.path.exists(xlsx_path):
        try:
            with pd.ExcelFile(xlsx_path, engine="openpyxl") as xls:
                customer_df = get_sheet_df(xls, ["customer", "customers"])
                salesperson_df = get_sheet_df(xls, ["salesperson", "salesman", "salespeople", "salespersons"])
                van_df = get_sheet_df(xls, ["van", "vans"])

                # Use holiday sheet only if we couldn't load holiday_1.xlsx or holiday_1.csv
                if holiday_df is None:
                    try:
                        holiday_df = get_sheet_df(xls, ["holiday", "holidays"])
                        holiday_df.columns = [c.strip() for c in holiday_df.columns]
                    except Exception:
                        holiday_df = pd.DataFrame(columns=["holiday_id", "from_date", "to_date", "reason"])

                territory_df = get_sheet_df(xls, ["territory", "territories"])
                rfm_scores_df = get_sheet_df(xls, ["rfm_scores", "rfm", "rfm_score"])
                config_df = get_sheet_df(xls, ["config", "configs", "configuration", "configurations"])
                visit_df = get_sheet_df(xls, ["visit", "visits"])

                # Format time strings or datetime values from Excel to clean strings
                if "config_value" in config_df.columns:
                    config_df["config_value"] = config_df["config_value"].apply(
                        lambda x: x.strftime("%H:%M") if hasattr(x, "strftime") else str(x)
                    )

                return customer_df, salesperson_df, van_df, holiday_df, territory_df, rfm_scores_df, config_df, visit_df
        except Exception as e:
            st.warning(f"Failed to load data from {xlsx_path}, falling back to CSVs: {e}")

    try:
        customer_df = pd.read_csv(os.path.join(DATA_DIR, "customer.csv"))
        salesperson_df = pd.read_csv(os.path.join(DATA_DIR, "salesperson.csv"))
        van_df = pd.read_csv(os.path.join(DATA_DIR, "van.csv"))

        # Use holiday.csv fallback only if we couldn't load holiday_1.xlsx or holiday_1.csv
        if holiday_df is None:
            holiday_df = pd.read_csv(os.path.join(DATA_DIR, "holiday.csv"))
            holiday_df.columns = [c.strip() for c in holiday_df.columns]

        territory_df = pd.read_csv(os.path.join(DATA_DIR, "territory.csv"))
        rfm_scores_df = pd.read_csv(os.path.join(DATA_DIR, "rfm_scores.csv"))
        config_df = pd.read_csv(os.path.join(DATA_DIR, "config.csv"))
        visit_df = pd.read_csv(os.path.join(DATA_DIR, "visit.csv"))
        return customer_df, salesperson_df, van_df, holiday_df, territory_df, rfm_scores_df, config_df, visit_df
    except Exception as e:
        st.error(f"Error loading master data files: {e}")
        st.info("Ensure saudi_master_data_output/ directory exists with jp_data.xlsx or customer.csv, salesperson.csv, van.csv, etc.")
        return None, None, None, None, None, None, None, None

def save_config_csv(config_df):
    try:
        # Save to config.csv (legacy fallback)
        os.makedirs(DATA_DIR, exist_ok=True)
        config_df.to_csv(os.path.join(DATA_DIR, "config.csv"), index=False)

        # Save to jp_data.xlsx if it exists
        xlsx_path = os.path.join(DATA_DIR, "jp_data.xlsx")
        if not os.path.exists(xlsx_path):
            xlsx_path = os.path.join(OUTPUT_DIR, "jp_data.xlsx")

        if os.path.exists(xlsx_path):
            sheets = {}
            with pd.ExcelFile(xlsx_path, engine="openpyxl") as xls:
                for sheet_name in xls.sheet_names:
                    sheets[sheet_name] = pd.read_excel(xls, sheet_name=sheet_name)

            # Update config sheet (find dynamically)
            config_sheet_name = next(
                (s for s in sheets if s.strip().lower() in ["config", "configs", "configuration", "configurations"]),
                "config"
            )
            sheets[config_sheet_name] = config_df

            # Write back all sheets
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                for sheet_name, df in sheets.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

        st.cache_data.clear() # Clear streamlit cache so the updated data is reloaded immediately
        st.success("Configurations persistently saved to both config.csv and jp_data.xlsx!")
    except Exception as e:
        st.error(f"Failed to save configurations: {e}")

# Render download buttons helper function
def render_download_buttons(df, filename_prefix, sheet_name, key_prefix):
    c1, c2 = st.columns(2)
    with c1:
        csv_bytes = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name=f"{filename_prefix}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            width='stretch'
        )
    with c2:
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        st.download_button(
            label="Download Excel",
            data=buffer.getvalue(),
            file_name=f"{filename_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_xlsx",
            width='stretch'
        )

# Helper to render maps dynamically
def display_map(m, key, height=700):
    if has_streamlit_folium:
        try:
            st_folium(m, width="100%", height=height, key=key, returned_objects=[])
        except Exception:
            # Fallback to iframe HTML component if st_folium fails
            st.components.v1.html(m._repr_html_(), height=height, scrolling=True)
    else:
        st.components.v1.html(m._repr_html_(), height=height, scrolling=True)

# Load data initially
customer_df, salesperson_df, van_df, holiday_df, territory_df, rfm_scores_df, config_df, visit_df = load_master_data()

# Sync SEG_CAPS from loaded configurations if they exist
if config_df is not None:
    try:
        cfg_dict = config_df.set_index("config_key")["config_value"].to_dict()
        cap_high = int(float(cfg_dict.get("segment_cap_high", 15)))
        cap_med = int(float(cfg_dict.get("segment_cap_medium", 6)))
        cap_low = int(float(cfg_dict.get("segment_cap_low", 4)))
        import scheduler_osrm
        scheduler_osrm.SEG_CAPS = {"High": cap_high, "Medium": cap_med, "Low": cap_low}
    except Exception as e:
        st.warning(f"Failed to sync SEG_CAPS: {e}")

# Initialize solver container and plan states at startup
if "solver_container" not in st.session_state:
    st.session_state["solver_container"] = {
        "status": "idle",
        "result": None,
        "error": None,
        "meta": None,
        "start_time": None
    }

if "latest_plan" not in st.session_state:
    st.session_state["latest_plan"] = None

if "latest_plan_meta" not in st.session_state:
    st.session_state["latest_plan_meta"] = None

is_running = st.session_state["solver_container"]["status"] == "running"

# ============================================================
# INSIGHT SECTIONS SUPPORT (Know Your Customer / Territory / Salesperson)
# Adapted from the previous DelivIQ app, wired to the REAL master data.
# ============================================================
BLUE = "#4F7FFA"; GREEN = "#34C48B"; ORANGE = "#F5A623"
RED = "#F06565"; PURPLE = "#9B7FFA"; TEAL = "#7CB9E8"
_PALETTE = [GREEN, BLUE, TEAL, ORANGE, RED, PURPLE, "#E8A0BF", "#7C9EB2", "#C29B45"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
TIER_COLORS = {"HIGH": GREEN, "MED": BLUE, "LOW": ORANGE}


def _build_insight_df():
    """Merge customer master with RFM scores into one analysis dataframe."""
    if customer_df is None or rfm_scores_df is None:
        return None
    rcols = ["customer_id", "recency", "frequency", "monetary", "r_score",
             "f_score", "m_score", "final_customer_score",
             "rfm_segment_final", "customer_rank"]
    rcols = [c for c in rcols if c in rfm_scores_df.columns]
    df = customer_df.merge(rfm_scores_df[rcols], on="customer_id", how="left")
    df = df.rename(columns={"rfm_segment_final": "segment"})
    if "segment" not in df.columns:
        df["segment"] = "Unknown"
    df["segment"] = df["segment"].fillna("Unknown")
    df["acquisition_month"] = pd.to_datetime(
        df.get("acquisition_date"), errors="coerce").dt.month
    for c in ["monetary", "recency", "frequency",
              "outstanding_balance", "credit_limit"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    return df


insight_df = _build_insight_df()

if insight_df is not None:
    TER_NAME = dict(zip(territory_df["territory_id"], territory_df["territory_name"]))
    SEG_LIST = sorted(insight_df["segment"].dropna().unique().tolist())
    SEG_COLORS = {s: _PALETTE[i % len(_PALETTE)] for i, s in enumerate(SEG_LIST)}
    LC_LIST = sorted(insight_df["lifecycle_state"].dropna().unique().tolist())
    LC_COLORS = {s: _PALETTE[i % len(_PALETTE)] for i, s in enumerate(LC_LIST)}
else:
    TER_NAME = {}; SEG_COLORS = {}; LC_COLORS = {}


def _section(title):
    st.markdown(f"#### {title}")


def _render_folium(m, key, height=460):
    if has_streamlit_folium:
        try:
            st_folium(m, width=None, height=height, returned_objects=[], key=key)
            return
        except Exception:
            pass
    st.components.v1.html(m._repr_html_(), height=height, scrolling=True)


def insight_filters(key_prefix, show_category=False, show_month=False):
    """Render a filter row (territory / tier / lifecycle [+ category/month])."""
    n = 3 + int(show_category) + int(show_month)
    cols = st.columns(n)
    i = 0
    ter_names = [TER_NAME.get(t, t)
                 for t in sorted(insight_df["territory_id"].dropna().unique())]
    ter_sel = cols[i].multiselect("Territory", ter_names,
                                  default=ter_names, key=f"{key_prefix}_ter"); i += 1
    tiers = [t for t in ["HIGH", "MED", "LOW"]
             if t in insight_df["volume_tier"].unique()] or \
        sorted(insight_df["volume_tier"].dropna().unique().tolist())
    tier_sel = cols[i].multiselect("Volume Tier", tiers,
                                   default=tiers, key=f"{key_prefix}_tier"); i += 1
    lc_opts = sorted(insight_df["lifecycle_state"].dropna().unique().tolist())
    lc_sel = cols[i].multiselect("Lifecycle", lc_opts,
                                 default=lc_opts, key=f"{key_prefix}_lc"); i += 1
    cat_sel = month_sel = None
    if show_category:
        cats = sorted(insight_df["shop_category"].dropna().unique().tolist())
        cat_sel = cols[i].multiselect("Category", cats,
                                      default=cats, key=f"{key_prefix}_cat"); i += 1
    if show_month:
        mvals = sorted(int(x) for x in insight_df["acquisition_month"].dropna().unique())
        labels = [MONTHS[m - 1] for m in mvals]
        msel = cols[i].multiselect("Acq. Month", labels,
                                   default=labels, key=f"{key_prefix}_month"); i += 1
        month_sel = [m for m in mvals if MONTHS[m - 1] in msel]

    df = insight_df.copy()
    df = df[df["territory_id"].map(TER_NAME).isin(ter_sel)]
    df = df[df["volume_tier"].isin(tier_sel)]
    df = df[df["lifecycle_state"].isin(lc_sel)]
    if cat_sel is not None:
        df = df[df["shop_category"].isin(cat_sel)]
    if month_sel is not None:
        df = df[df["acquisition_month"].isin(month_sel)]
    return df


def customer_directory_filters(key_prefix):
    """Customer-directory style filter row (Territory / Volume Tier / Cold-Chain /
    Lifecycle + search). Returns the filtered customer_df.

    Reused across the Customer Directory, Territory Centroids and RFM Scoreboard
    tabs so they all share the same filter look-and-feel and selection."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        filt_ter = st.selectbox("Filter Territory", ["All"] + list(territory_df["territory_id"].unique()), key=f"{key_prefix}_ter")
    with c2:
        filt_tier = st.selectbox("Filter Volume Tier", ["All", "HIGH", "MED", "LOW"], key=f"{key_prefix}_tier")
    with c3:
        filt_cold = st.selectbox("Cold-Chain Required", ["All", "Yes", "No"], key=f"{key_prefix}_cold")
    with c4:
        filt_life = st.selectbox("Lifecycle State", ["All"] + list(customer_df["lifecycle_state"].unique()), key=f"{key_prefix}_life")

    search_q = st.text_input("Search outlets by ID or shop name...", key=f"{key_prefix}_search")

    f_df = customer_df.copy()
    if filt_ter != "All":
        f_df = f_df[f_df["territory_id"] == filt_ter]
    if filt_tier != "All":
        f_df = f_df[f_df["volume_tier"] == filt_tier]
    if filt_cold != "All":
        f_df = f_df[f_df["cold_truck_required"] == (filt_cold == "Yes")]
    if filt_life != "All":
        f_df = f_df[f_df["lifecycle_state"] == filt_life]
    if search_q:
        f_df = f_df[f_df["shop_name"].str.contains(search_q, case=False, na=False) | f_df["customer_id"].str.contains(search_q, case=False, na=False)]
    return f_df


def historical_visit_filters(key_prefix):
    """Customer-directory style filter row for the Historical Visit Log, with
    RFM Category in place of Volume Tier. Resolves the customer master + RFM
    scores into a matching customer_id set and returns the filtered visit_df."""
    rfm_cats = sorted(rfm_scores_df["rfm_segment_final"].dropna().unique().tolist())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        filt_ter = st.selectbox("Filter Territory", ["All"] + list(territory_df["territory_id"].unique()), key=f"{key_prefix}_ter")
    with c2:
        filt_rfm = st.selectbox("RFM Category", ["All"] + rfm_cats, key=f"{key_prefix}_rfm")
    with c3:
        filt_cold = st.selectbox("Cold-Chain Required", ["All", "Yes", "No"], key=f"{key_prefix}_cold")
    with c4:
        filt_life = st.selectbox("Lifecycle State", ["All"] + list(customer_df["lifecycle_state"].unique()), key=f"{key_prefix}_life")

    search_q = st.text_input("Search outlets by ID or shop name...", key=f"{key_prefix}_search")

    # Build the matching customer_id set from the customer master + RFM scores.
    cust = customer_df.copy()
    if filt_ter != "All":
        cust = cust[cust["territory_id"] == filt_ter]
    if filt_cold != "All":
        cust = cust[cust["cold_truck_required"] == (filt_cold == "Yes")]
    if filt_life != "All":
        cust = cust[cust["lifecycle_state"] == filt_life]
    if search_q:
        cust = cust[cust["shop_name"].str.contains(search_q, case=False, na=False) | cust["customer_id"].str.contains(search_q, case=False, na=False)]
    if filt_rfm != "All":
        rfm_ids = rfm_scores_df[rfm_scores_df["rfm_segment_final"] == filt_rfm]["customer_id"]
        cust = cust[cust["customer_id"].isin(rfm_ids)]

    matching_ids = set(cust["customer_id"])
    if "customer_id" in visit_df.columns:
        return visit_df[visit_df["customer_id"].isin(matching_ids)]
    return visit_df


def render_know_customer(filtered_df=None):
    st.subheader("Know Your Customer")
    if insight_df is None:
        st.info("Customer/RFM data not available.")
        return
    # Reuse the filters applied in "Active Customer Profiles" instead of
    # rendering a separate filter row. `filtered_df` carries the customer
    # selection; we map it onto the richer insight_df (with RFM columns).
    if filtered_df is not None:
        df = insight_df[insight_df["customer_id"].isin(filtered_df["customer_id"])]
    else:
        df = insight_filters("cu", show_category=True, show_month=False)
    st.caption(f"Showing **{len(df)}** customers after filters")

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Customers", f"{len(df):,}")
    k2.metric("Avg Monetary", f"SAR {df['monetary'].mean():,.0f}" if len(df) else "-")
    k3.metric("Credit Customers", f"{(df['payment_type'] == 'credit').sum():,}")
    k4.metric("Cold-Chain Req.", f"{int(df['cold_truck_required'].sum()):,}")
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        _section("Top 10 by Monetary Value")
        top = df.nlargest(10, "monetary")[["shop_name", "volume_tier", "segment", "monetary"]]
        fig = px.bar(top, x="monetary", y="shop_name", color="segment", orientation="h",
                     color_discrete_map=SEG_COLORS, template="plotly_white",
                     labels={"monetary": "SAR", "shop_name": ""})
        fig.update_layout(height=340, margin=dict(t=20, b=10, l=0, r=0),
                          yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch', key="cu_top")
    with c2:
        _section("Revenue by Shop Category")
        cat_rev = df.groupby("shop_category")["monetary"].sum().reset_index().sort_values(
            "monetary", ascending=False)
        fig = px.bar(cat_rev, x="shop_category", y="monetary", color_discrete_sequence=[PURPLE],
                     template="plotly_white", labels={"shop_category": "Category", "monetary": "Total SAR"})
        fig.update_layout(height=340, margin=dict(t=20, b=60, l=0, r=0), xaxis_tickangle=-30)
        st.plotly_chart(fig, width='stretch', key="cu_catrev")

    _section("At-Risk Customers")
    at_risk = df[df["lifecycle_state"].astype(str).str.contains("risk", case=False)][
        ["shop_name", "shop_category", "volume_tier", "outstanding_balance", "monetary"]
    ].sort_values("outstanding_balance", ascending=False)
    st.dataframe(at_risk.reset_index(drop=True), width='stretch', height=260)


def render_know_territory(filtered_df=None):
    st.subheader("Know Your Territory")
    if insight_df is None:
        st.info("Customer/RFM data not available.")
        return
    # Reuse the Territory Centroids filter selection instead of a separate row.
    if filtered_df is not None:
        df = insight_df[insight_df["customer_id"].isin(filtered_df["customer_id"])]
    else:
        df = insight_filters("te", show_category=True, show_month=False)
    st.caption(f"{len(df)} customers in filter")

    ter_stats = []
    for _, ter in territory_df.iterrows():
        tc = df[df["territory_id"] == ter.territory_id]
        ter_stats.append({
            "Territory": ter.territory_name,
            "Customers": len(tc),
            "At Risk": int(tc["lifecycle_state"].astype(str).str.contains("risk", case=False).sum()),
            "Cold Chain": int(tc["cold_truck_required"].sum()),
            "Total Monetary (SAR)": round(tc["monetary"].sum(), 0),
            "Avg Monetary (SAR)": round(tc["monetary"].mean(), 0) if len(tc) else 0,
            "Credit %": round((tc["payment_type"] == "credit").mean() * 100, 1) if len(tc) else 0,
        })
    st.dataframe(pd.DataFrame(ter_stats), width='stretch')

    c1, c2 = st.columns(2)
    with c1:
        ter_mon = df.groupby("territory_id")["monetary"].sum().reset_index()
        ter_mon["Territory"] = ter_mon["territory_id"].map(TER_NAME)
        fig = px.bar(ter_mon, x="Territory", y="monetary", color="Territory",
                     color_discrete_sequence=_PALETTE, template="plotly_white",
                     title="Total Monetary by Territory")
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=0, r=0),
                          showlegend=False, title_font_size=14)
        st.plotly_chart(fig, width='stretch', key="te_mon")
    with c2:
        temp_df = df.copy()
        temp_df["lifecycle_state"] = temp_df["lifecycle_state"].fillna("Unknown")
        life_counts = temp_df.groupby(["territory_id", "lifecycle_state"]).size().reset_index(name="Count")
        life_counts["Territory"] = life_counts["territory_id"].map(TER_NAME)
        
        fig = px.bar(life_counts, x="Territory", y="Count", color="lifecycle_state", barmode="group",
                     title="Customer Lifecycle States by Territory",
                     color_discrete_sequence=_PALETTE, template="plotly_white")
        fig.update_layout(
            height=280,
            margin=dict(t=40, b=10, l=0, r=120),
            title_font_size=14,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1.02,
                xanchor="left",
                x=1.02
            ),
            legend_title_text="Customer Type"
        )
        st.plotly_chart(fig, width='stretch', key="te_kc")

    _section("Customer Locations - Street Map")
    col_f1, col_f2 = st.columns([2, 1])
    with col_f2:
        ter_opts_map = ["All"] + [TER_NAME.get(t, t) for t in territory_df["territory_id"]]
        ter_filter_map = st.selectbox("Filter territory on map", ter_opts_map, key="te_map_ter")
        tier_filter_map = st.multiselect("Filter tier on map", ["HIGH", "MED", "LOW"],
                                         default=["HIGH", "MED", "LOW"], key="te_map_tier")
        show_cluster = st.checkbox("Cluster markers", value=True, key="te_cluster")

    map_df = df.dropna(subset=["gps_lat", "gps_lng"]).copy()
    if ter_filter_map != "All":
        rev = {v: k for k, v in TER_NAME.items()}
        map_df = map_df[map_df["territory_id"] == rev.get(ter_filter_map, ter_filter_map)]
    map_df = map_df[map_df["volume_tier"].isin(tier_filter_map)]

    tier_fc = {"HIGH": "green", "MED": "blue", "LOW": "orange"}
    if len(map_df) == 0:
        st.info("No customers match this filter.")
    else:
        center = [map_df["gps_lat"].mean(), map_df["gps_lng"].mean()]
        m = folium.Map(location=center, zoom_start=10, tiles="OpenStreetMap", control_scale=True)
        for _, ter in territory_df.iterrows():
            if ter_filter_map == "All" or TER_NAME.get(ter.territory_id) == ter_filter_map:
                folium.Marker(
                    [ter.warehouse_lat, ter.warehouse_lng],
                    popup=str(ter.get("warehouse_address", "")),
                    tooltip=f"Warehouse: {ter.territory_name}",
                    icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
        container = MarkerCluster(disableClusteringAtZoom=13).add_to(m) if show_cluster else m
        for _, row in map_df.iterrows():
            col = tier_fc.get(row["volume_tier"], "blue")
            folium.CircleMarker(
                location=[row["gps_lat"], row["gps_lng"]],
                radius=7, color=col, fill=True, fill_color=col, fill_opacity=0.8,
                popup=folium.Popup(
                    f"<b>{row['shop_name']}</b><br>{row['shop_category']}<br>"
                    f"Tier: {row['volume_tier']}<br>Seg: {row['segment']}<br>"
                    f"Monetary: SAR {row['monetary']:,.0f}", max_width=220),
                tooltip=row["shop_name"]).add_to(container)
        with col_f1:
            _render_folium(m, key="te_folium", height=480)


def render_know_salesperson():
    st.subheader("Know Your Salesperson")
    if insight_df is None:
        st.info("Customer/RFM data not available.")
        return
    ter_names = [TER_NAME.get(t, t) for t in sorted(salesperson_df["territory_id"].dropna().unique())]
    rev = {v: k for k, v in TER_NAME.items()}

    # Customer-section style filter row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        filt_ter = st.selectbox("Filter Territory", ["All"] + ter_names, key="sp_ter")
    with c2:
        filt_cold = st.selectbox("Cold Van", ["All", "Yes", "No"], key="sp_cold")
    with c3:
        filt_sort = st.selectbox("Sort By", ["Revenue (SAR)", "Customers", "At Risk", "Perf x"], key="sp_sort")
    with c4:
        search_sp = st.text_input("Search salesperson by name...", key="sp_search")
    sel_ter_ids = list(rev.get(t, t) for t in ter_names) if filt_ter == "All" else [rev.get(filt_ter, filt_ter)]

    sp_stats = []
    for _, sp in salesperson_df.iterrows():
        if sp.territory_id not in sel_ter_ids:
            continue
        ter_cust = insight_df[insight_df["territory_id"] == sp.territory_id]
        n_sp = max(1, len(salesperson_df[salesperson_df["territory_id"] == sp.territory_id]))
        share = max(1, len(ter_cust) // n_sp)
        my = ter_cust.sample(min(share, len(ter_cust)), random_state=42) if len(ter_cust) else ter_cust
        van_row = van_df[van_df["van_id"] == sp.get("assigned_van")] if "assigned_van" in salesperson_df.columns else van_df.iloc[0:0]
        is_cold = bool(van_row.iloc[0]["cold_truck_enabled"]) if len(van_row) and "cold_truck_enabled" in van_row.columns else False
        sp_stats.append({
            "Name": sp["name"], "Territory": TER_NAME.get(sp.territory_id, sp.territory_id),
            "Van": sp.get("assigned_van"), "Cold Van": "Yes" if is_cold else "",
            "Customers": len(my),
            "Revenue (SAR)": round(my["monetary"].sum(), 0),
            "Avg AOV (SAR)": round(my["monetary"].mean(), 0) if len(my) else 0,
            "At Risk": int(my["lifecycle_state"].astype(str).str.contains("risk", case=False).sum()),
            "Perf x": sp.get("performance_multiplier", 1.0),
        })

    if not sp_stats:
        st.info("No salespeople for the selected territory.")
        return

    sp_disp = pd.DataFrame(sp_stats)
    if filt_cold != "All":
        sp_disp = sp_disp[sp_disp["Cold Van"] == ("Yes" if filt_cold == "Yes" else "")]
    if search_sp:
        sp_disp = sp_disp[sp_disp["Name"].str.contains(search_sp, case=False, na=False)]

    if sp_disp.empty:
        st.info("No salespeople match these filters.")
        return

    sp_disp = sp_disp.sort_values(filt_sort, ascending=False).reset_index(drop=True)
    sp_disp.index += 1

    k1, k2, k3 = st.columns(3)
    top = sp_disp.iloc[0]
    k1.metric("Top Performer", top["Name"], f"SAR {top['Revenue (SAR)']:,.0f}")
    if "performance_multiplier" in salesperson_df.columns:
        k2.metric("Avg Performance x", f"x{salesperson_df['performance_multiplier'].mean():.2f}")
    k3.metric("Total Salespeople", len(sp_disp))

    st.markdown("---")
    _section("Leaderboard")
    st.dataframe(sp_disp, width='stretch')

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(sp_disp, x="Name", y="Revenue (SAR)", color="Territory",
                     title="Revenue by Salesperson", template="plotly_white",
                     color_discrete_sequence=_PALETTE)
        fig.update_layout(height=300, margin=dict(t=40, b=80, l=0, r=0),
                          xaxis_tickangle=-30, title_font_size=14)
        st.plotly_chart(fig, width='stretch', key="sp_rev")
    with c2:
        fig = px.scatter(sp_disp, x="Perf x", y="Revenue (SAR)", size="Customers",
                         color="Territory", hover_name="Name", template="plotly_white",
                         title="Performance x vs Revenue", color_discrete_sequence=_PALETTE)
        fig.add_vline(x=1.0, line_dash="dash", line_color="gray",
                      annotation_text="Baseline x1.0", annotation_position="top right")
        fig.update_layout(height=300, margin=dict(t=40, b=10, l=0, r=0), title_font_size=14)
        st.plotly_chart(fig, width='stretch', key="sp_scat")

    # Top 3 performers per territory, grouped into one chart
    _section("Top 3 Performers per Territory")
    top3 = (
        sp_disp.sort_values("Revenue (SAR)", ascending=False)
        .groupby("Territory", group_keys=False)
        .head(3)
        .copy()
    )
    top3["Rank"] = (
        top3.groupby("Territory")["Revenue (SAR)"]
        .rank(method="first", ascending=False)
        .astype(int)
        .map({1: "#1", 2: "#2", 3: "#3"})
    )
    fig = px.bar(
        top3, x="Territory", y="Revenue (SAR)", color="Rank", barmode="group",
        hover_name="Name", text="Name", template="plotly_white",
        title="Top 3 Performers per Territory (by Revenue)",
        color_discrete_map={"#1": GREEN, "#2": BLUE, "#3": ORANGE},
    )
    fig.update_traces(textposition="outside", textfont_size=10, cliponaxis=False)
    fig.update_layout(height=380, margin=dict(t=50, b=40, l=0, r=0),
                      xaxis_tickangle=-20, title_font_size=14)
    st.plotly_chart(fig, width='stretch', key="sp_top3")


# ------------------------------------------------------------
# EXISTING-PLAN LOADER (reuse a plan already saved to disk)
# ------------------------------------------------------------
def list_existing_plan_files():
    import glob
    search_dirs = [current_dir, OUTPUT_DIR, DATA_DIR]
    patterns = ["monthly_plan_for_*.xlsx", "monthly_plan_*.xlsx", "detailed_schedule*.csv"]
    files = []
    for d in search_dirs:
        for pat in patterns:
            files.extend(glob.glob(os.path.join(d, pat)))
    # de-duplicate while preserving order, newest first
    seen, uniq = set(), []
    for f in sorted(files, key=os.path.getmtime, reverse=True):
        if f not in seen:
            seen.add(f); uniq.append(f)
    return uniq


def load_existing_plan_result(plan_path):
    """Reconstruct a MultiScheduleResult from a saved plan (.xlsx workbook or .csv)."""
    import re
    if plan_path.lower().endswith(".csv"):
        detailed = pd.read_csv(plan_path)
        daily = pd.DataFrame()
    else:
        with pd.ExcelFile(plan_path, engine="openpyxl") as xl:
            detailed = pd.read_excel(xl, "Detailed Schedule")
            daily = pd.read_excel(xl, "Daily Schedule") if "Daily Schedule" in xl.sheet_names else pd.DataFrame()
    for d in (detailed, daily):
        if "schedule_date" in d.columns:
            d["schedule_date"] = pd.to_datetime(d["schedule_date"], errors="coerce")

    tg = detailed["truck_group"] if "truck_group" in detailed.columns else None
    cold = detailed[tg == "cold"] if tg is not None else detailed.iloc[0:0]
    normal = detailed[tg == "normal"] if tg is not None else detailed.iloc[0:0]

    try:
        unvis = pd.read_csv(os.path.join(OUTPUT_DIR, "unvisited.csv"))
    except Exception:
        unvis = pd.DataFrame()

    wh = {}
    if territory_df is not None:
        for _, t in territory_df.iterrows():
            try:
                wh[t["territory_id"]] = (float(t["warehouse_lat"]), float(t["warehouse_lng"]))
            except Exception:
                pass

    cfgv = config_df.set_index("config_key")["config_value"].to_dict() if config_df is not None else {}
    osrm_mode = cfgv.get("osrm_routing_mode", "http")
    osrm_url = cfgv.get("osrm_server_url", "http://router.project-osrm.org")
    osrm_path = cfgv.get("osrm_data_path", "")

    from osrm_helper import OSRMHelper
    osrm_h = OSRMHelper(mode=osrm_mode, server_url=osrm_url, data_path=osrm_path)

    res = MultiScheduleResult(
        detailed_schedule=detailed,
        cold_schedule=cold,
        normal_schedule=normal,
        daily_schedule=daily,
        unvisited_customers=unvis,
        under_visited_customers=pd.DataFrame(),
        daily_visit_plan=pd.DataFrame(),
        salesperson_results={},
        territory_warehouses=wh,
        osrm_helper=osrm_h,
    )

    terrs = detailed["territory_id"].dropna().unique().tolist() if "territory_id" in detailed.columns else []
    territory = terrs[0] if len(terrs) == 1 else "All Territories"
    mobj = re.search(r"(\d{4}-\d{2}-\d{2})", os.path.basename(plan_path))
    if mobj:
        month = mobj.group(1)
    elif "schedule_date" in detailed.columns and detailed["schedule_date"].notna().any():
        month = pd.Timestamp(detailed["schedule_date"].min()).strftime("%Y-%m-%d")
    else:
        month = "loaded"

    meta_config = {
        "avg_speed": float(cfgv.get("avg_speed_kmh", 32)),
        "customer_serving_time": int(float(cfgv.get("avg_service_time_min", 22))),
        "salesman_daily_work_minutes": 480,
    }
    meta = {"month": month, "territory": territory, "config": meta_config}
    return res, meta


# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
# Logo at top-left of the sidebar. Drop a logo image at one of these paths.
_LOGO_PATH = next(
    (p for p in [
        os.path.join(current_dir, "assets", "logo.png"),
        os.path.join(current_dir, "assets", "yash_logo.png"),
        os.path.join(current_dir, "logo.png"),
        os.path.join(current_dir, "yash_logo.png"),
    ] if os.path.exists(p)),
    None,
)
if _LOGO_PATH:
    st.sidebar.image(_LOGO_PATH)

st.sidebar.title("DelivIQ Intellect")
st.sidebar.caption("Journey Planner & Route Optimization Control Room")
st.sidebar.markdown("---")

pages_list = [
    "Master Data Explorer",
    "Know Your Customer",
    "Know Your Salesperson",
    "Know Your Territory",
    "Monthly Plan Generator",
    "VRP Routing & Driver Maps",
    "Executive Visualization & Analytics",
    "Global Configuration Settings",
]

if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "Master Data Explorer"

if is_running:
    st.sidebar.warning("Navigation is locked while optimization is in progress.")
    page = "Monthly Plan Generator"
    st.session_state["selected_page"] = "Monthly Plan Generator"
    # Render disabled radio to show locked status
    st.sidebar.radio("Navigation", pages_list, index=4, disabled=True)
else:
    try:
        default_idx = pages_list.index(st.session_state["selected_page"])
    except ValueError:
        default_idx = 0
    page = st.sidebar.radio("Navigation", pages_list, index=default_idx)
    st.session_state["selected_page"] = page

st.sidebar.markdown("---")

# ------------------------------------------------------------
# PAGE 1: MASTER DATA EXPLORER
# ------------------------------------------------------------
if page == "Master Data Explorer":
    st.title("Master Data & Peer Segment Explorer")
    st.caption("Inspect customer master files, RFM scoring models, territory configurations, and holiday schedules.")

    if customer_df is None:
        st.stop()

    # Stats Row
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Total Retail Outlets</div>
            <div class="stat-value">{len(customer_df)}</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        cold_cnt = int(customer_df["cold_truck_required"].sum())
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Cold-Chain Outlets</div>
            <div class="stat-value">{cold_cnt}</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        lifecycle = customer_df["lifecycle_state"].astype(str)
        active_cnt = int(lifecycle.str.contains("active", case=False, na=False).sum())
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Active Customers</div>
            <div class="stat-value">{active_cnt}</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        risk_cnt = int(lifecycle.str.contains("risk", case=False, na=False).sum())
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">At-Risk Customers</div>
            <div class="stat-value">{risk_cnt}</div>
        </div>
        """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "Customer Directory",
        "Territory Centroids",
        "RFM Scoreboard",
        "Holiday Schedules",
        "Salesperson Directory",
        "Fleet Vehicles",
        "Historical Visit Log",
    ])

    with tab1:
        st.subheader("Active Customer Profiles")

        f_df = customer_directory_filters("cust_dir")

        st.markdown(f"Showing **{len(f_df)}** of **{len(customer_df)}** outlets:")
        st.dataframe(
            f_df[["customer_id", "shop_name", "locality", "territory_id", "shop_category", "cold_truck_required", "volume_tier", "payment_type", "outstanding_balance", "lifecycle_state", "preferred_visit_day"]],
            width='stretch'
        )
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(f_df, "customer_directory", "customer", "cust_dir")


    with tab2:
        st.subheader("Territory Logistics Centroids & Warehouses")

        f_df = customer_directory_filters("terr_cent")
        sel_ters = f_df["territory_id"].unique()
        terr_view = territory_df[territory_df["territory_id"].isin(sel_ters)]

        st.markdown(f"Showing **{len(terr_view)}** of **{len(territory_df)}** territories:")
        st.dataframe(terr_view, width='stretch')
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(terr_view, "territory_centroids", "territory", "terr_cent")


    with tab3:
        st.subheader("RFM Combined Score & Segmentation Summary")
        st.markdown("Customers are scored within their peer set (Territory x Truck Group) dynamically.")

        f_df = customer_directory_filters("rfm_score")
        rfm_view = rfm_scores_df[rfm_scores_df["customer_id"].isin(f_df["customer_id"])]

        # ---- RFM analytics graphs (Territory-wise) ----
        st.write("#### RFM Segment & Score Analytics")
        
        # Drop territory_id from rfm_view if it exists to avoid suffixes during merge
        rfm_view_clean = rfm_view.drop(columns=["territory_id"]) if "territory_id" in rfm_view.columns else rfm_view
        # Merge rfm_view_clean with f_df to get territory_id
        rfm_merged = rfm_view_clean.merge(f_df[["customer_id", "territory_id"]], on="customer_id", how="inner")
        
        # Map territory IDs to names safely
        ter_names_map = territory_df.set_index("territory_id")["territory_name"].to_dict() if territory_df is not None else {}
        colors_palette = ["#34C48B", "#4F7FFA", "#7CB9E8", "#F5A623", "#F06565", "#9B7FFA"]
        
        # Build color map for consistent territory coloring across all charts
        df_ratio = rfm_merged.groupby("territory_id").size().reset_index(name="Count")
        df_ratio["Territory"] = df_ratio["territory_id"].map(ter_names_map)
        df_ratio = df_ratio.dropna(subset=["Territory"])
        
        if rfm_merged.empty or df_ratio.empty:
            st.warning("No data available for the selected filters.")
        else:
            unique_territories = sorted(df_ratio["Territory"].unique().tolist())
            color_map = {t: colors_palette[i % len(colors_palette)] for i, t in enumerate(unique_territories)}
            
            # 1. Monetary Chart: Average Monetary by Territory (Horizontal Bar)
            df_mon = rfm_merged.groupby("territory_id")["monetary"].mean().reset_index()
            df_mon["Territory"] = df_mon["territory_id"].map(ter_names_map)
            df_mon = df_mon.dropna(subset=["Territory"])
            df_mon = df_mon.sort_values(by="monetary", ascending=True)
            df_mon["Monetary_Text"] = df_mon["monetary"].apply(lambda x: f"SAR {x:,.0f}")
            
            fig_mon = px.bar(df_mon, y="Territory", x="monetary", color="Territory",
                             color_discrete_map=color_map, template="plotly_white",
                             title="Avg Monetary Value per Customer",
                             orientation="h", text="Monetary_Text")
            fig_mon.update_traces(
                textposition="outside",
                cliponaxis=False,
                hovertemplate="<b>%{y}</b><br>Avg Monetary: SAR %{x:,.2f}<extra></extra>"
            )
            fig_mon.update_layout(
                height=280,
                margin=dict(t=50, b=10, l=100, r=80),
                showlegend=False,
                title_font_size=13,
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=False, title="")
            )

            # 2. Frequency Chart: Average Frequency by Territory (Horizontal Bar)
            df_freq = rfm_merged.groupby("territory_id")["frequency"].mean().reset_index()
            df_freq["Territory"] = df_freq["territory_id"].map(ter_names_map)
            df_freq = df_freq.dropna(subset=["Territory"])
            df_freq = df_freq.sort_values(by="frequency", ascending=True)
            df_freq["Frequency_Text"] = df_freq["frequency"].apply(lambda x: f"{x:.1f} visits")
            
            fig_freq = px.bar(df_freq, y="Territory", x="frequency", color="Territory",
                              color_discrete_map=color_map, template="plotly_white",
                              title="Avg Visit Frequency per Customer",
                              orientation="h", text="Frequency_Text")
            fig_freq.update_traces(
                textposition="outside",
                cliponaxis=False,
                hovertemplate="<b>%{y}</b><br>Avg Frequency: %{x:.2f} visits<extra></extra>"
            )
            fig_freq.update_layout(
                height=280,
                margin=dict(t=50, b=10, l=100, r=80),
                showlegend=False,
                title_font_size=13,
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=False, title="")
            )

            # 3. Recency Chart: Average Recency by Territory (Horizontal Bar)
            df_rec = rfm_merged.groupby("territory_id")["recency"].mean().reset_index()
            df_rec["Territory"] = df_rec["territory_id"].map(ter_names_map)
            df_rec = df_rec.dropna(subset=["Territory"])
            df_rec = df_rec.sort_values(by="recency", ascending=False) # Plotly draws bottom-to-top, so ascending=False puts lowest/best recency at top
            df_rec["Recency_Text"] = df_rec["recency"].apply(lambda x: f"{x:.1f} days")
            
            fig_rec = px.bar(df_rec, y="Territory", x="recency", color="Territory",
                             color_discrete_map=color_map, template="plotly_white",
                             title="Avg Recency (Days Since Last Order)",
                             orientation="h", text="Recency_Text")
            fig_rec.update_traces(
                textposition="outside",
                cliponaxis=False,
                hovertemplate="<b>%{y}</b><br>Avg Recency: %{x:.1f} days<extra></extra>"
            )
            fig_rec.update_layout(
                height=280,
                margin=dict(t=50, b=10, l=100, r=80),
                showlegend=False,
                title_font_size=13,
                xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=False, title="")
            )

            # 4. Customer Ratio Chart: Donut Chart of Customer Share by Territory
            total_customers = int(df_ratio["Count"].sum())
            fig_ratio = px.pie(df_ratio, names="Territory", values="Count", hole=0.6,
                               color="Territory", color_discrete_map=color_map,
                               title="Customer Distribution Share")
            fig_ratio.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>"
            )
            fig_ratio.update_layout(
                height=280,
                margin=dict(t=50, b=10, l=10, r=10),
                title_font_size=13,
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.2,
                    xanchor="center",
                    x=0.5
                ),
                annotations=[dict(text=f"Total<br><b>{total_customers}</b>", x=0.5, y=0.5, font_size=14, showarrow=False, align="center")]
            )

            g1, g2 = st.columns(2)
            with g1:
                st.plotly_chart(fig_mon, use_container_width=True, key="rfm_ter_mon")
            with g2:
                st.plotly_chart(fig_freq, use_container_width=True, key="rfm_ter_freq")

            g3, g4 = st.columns(2)
            with g3:
                st.plotly_chart(fig_rec, use_container_width=True, key="rfm_ter_rec")
            with g4:
                st.plotly_chart(fig_ratio, use_container_width=True, key="rfm_ter_ratio")

        st.markdown("---")
        st.write("#### Detailed Scoring Grid")
        st.markdown(f"Showing **{len(rfm_view)}** of **{len(rfm_scores_df)}** scored customers:")
        st.dataframe(rfm_view, width='stretch')
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(rfm_view, "rfm_scores", "rfm_scores", "rfm_score")

    with tab4:
        st.subheader("Blocked Dates & Leave Calendars")
        st.markdown("Solver checks these blocked dates. No scheduled salesperson visit can fall on these dates.")

        t_hol = holiday_df[holiday_df["territory_holiday"].notna()]
        s_hol = holiday_df[holiday_df["salesperson_holiday"].notna()]

        col1, col2 = st.columns(2)
        with col1:
            st.write("##### Territory Holidays")
            st.dataframe(t_hol[["holiday_id", "territory_holiday", "from_date", "to_date", "reason"]], width='stretch')
        with col2:
            st.write("##### Salesperson Leave Schedule")
            st.dataframe(s_hol[["holiday_id", "salesperson_holiday", "from_date", "to_date", "reason"]], width='stretch')
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(holiday_df, "holiday_schedule", "holiday", "holiday_sched")

    with tab5:
        st.subheader("Salesperson Directory")
        st.dataframe(salesperson_df, width='stretch')
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(salesperson_df, "salesperson_directory", "salesperson", "sp_dir")


    with tab6:
        st.subheader("Fleet Vehicle Roster")
        st.dataframe(van_df, width='stretch')
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(van_df, "van_fleet_directory", "van", "van_dir")

    with tab7:
        st.subheader("Historical Visit Log")

        v_df = historical_visit_filters("visit_log")

        # ---- Historical Visit Log Visual Analytics ----
        if not v_df.empty:
            import numpy as np
            st.markdown("### Historical Visit Log Visual Analytics")
            
            # Map sales_id to salesperson name
            sp_names_map = salesperson_df.set_index("sales_id")["name"].to_dict() if salesperson_df is not None else {}
            
            # Pre-process data
            v_df_processed = v_df.copy()
            v_df_processed["Date"] = pd.to_datetime(v_df_processed["visit_date"]).dt.strftime("%Y-%m-%d")
            v_df_processed["Outcome"] = v_df_processed["successful_visit"].map({True: "Successful", False: "Unsuccessful"})
            
            # Chart 1: Daily Visit Execution Trend (Stacked Bar) - Filtered to last 4 months
            v_df_processed["visit_datetime"] = pd.to_datetime(v_df_processed["visit_date"])
            max_date = v_df_processed["visit_datetime"].max()
            four_months_ago = max_date - pd.DateOffset(months=4)
            df_trend_filtered = v_df_processed[v_df_processed["visit_datetime"] >= four_months_ago]
            
            df_trend = df_trend_filtered.groupby(["Date", "Outcome"]).size().reset_index(name="Visits")
            df_trend = df_trend.sort_values(by="Date")
            
            fig_trend = px.line(
                df_trend, x="Date", y="Visits", color="Outcome",
                color_discrete_map={"Successful": "#34C48B", "Unsuccessful": "#F06565"},
                template="plotly_white",
                title="Visit Execution Outcome Trend (Daily Attempt Count)"
            )
            fig_trend.update_traces(line=dict(width=3))
            fig_trend.update_layout(
                height=300,
                margin=dict(t=50, b=10, l=10, r=10),
                title_font_size=14,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(title="", showgrid=False),
                yaxis=dict(title="Number of Visits", showgrid=True, gridcolor="#F3F4F6")
            )
            st.plotly_chart(fig_trend, use_container_width=True, key="visit_outcome_trend")
            
            # Leaderboard & RFM segments side-by-side
            c1, c2 = st.columns(2)
            
            with c1:
                # Chart 2: Salesperson Contribution Leaderboard (Horizontal Bar)
                v_df_processed["Salesperson"] = v_df_processed["sales_id"].map(sp_names_map).fillna(v_df_processed["sales_id"])
                
                df_sp = v_df_processed.groupby("Salesperson").agg(
                    total_visits=("visit_id", "count"),
                    successful_visits=("successful_visit", "sum"),
                    revenue=("transaction_amount", "sum")
                ).reset_index()
                
                df_sp["Success Rate (%)"] = (df_sp["successful_visits"] / df_sp["total_visits"] * 100).round(1)
                df_sp = df_sp.sort_values(by="revenue", ascending=True) # Ascending for horizontal bar
                df_sp["Revenue_Text"] = df_sp["revenue"].apply(lambda x: f"SAR {x:,.0f}")
                
                fig_sp = px.bar(
                    df_sp, y="Salesperson", x="revenue",
                    color_discrete_sequence=["#4F7FFA"], template="plotly_white",
                    title="Salesperson Performance & Revenue Leaderboard",
                    orientation="h", text="Revenue_Text"
                )
                fig_sp.update_traces(
                    textposition="outside",
                    cliponaxis=False,
                    hovertemplate="<b>%{y}</b><br>Revenue: SAR %{x:,.2f}<br>Success Rate: %{customdata[0]}%<br>Total Visits: %{customdata[1]}<extra></extra>",
                    customdata=np.stack((df_sp["Success Rate (%)"], df_sp["total_visits"]), axis=-1)
                )
                fig_sp.update_layout(
                    height=320,
                    margin=dict(t=50, b=10, l=100, r=80),
                    title_font_size=13,
                    xaxis=dict(showgrid=False, visible=False),
                    yaxis=dict(showgrid=False, title="")
                )
                st.plotly_chart(fig_sp, use_container_width=True, key="visit_salesperson_leaderboard")
                
            with c2:
                # Chart 3: Visit Outcomes by Customer RFM Segment (Grouped Bar)
                df_rfm = v_df_processed.groupby(["rfm_segment", "Outcome"]).size().reset_index(name="Count")
                rfm_order = {"High": 0, "Medium": 1, "Low": 2, "Unscored": 3}
                df_rfm["sort_idx"] = df_rfm["rfm_segment"].map(rfm_order).fillna(4)
                df_rfm = df_rfm.sort_values(by="sort_idx")
                
                fig_rfm = px.bar(
                    df_rfm, x="rfm_segment", y="Count", color="Outcome",
                    color_discrete_map={"Successful": "#34C48B", "Unsuccessful": "#F06565"},
                    barmode="group", template="plotly_white",
                    title="Visit Outcomes by Customer RFM Segment"
                )
                fig_rfm.update_layout(
                    height=320,
                    margin=dict(t=50, b=10, l=10, r=10),
                    title_font_size=13,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    xaxis=dict(title="Customer RFM Segment", showgrid=False),
                    yaxis=dict(title="Number of Visits", showgrid=True, gridcolor="#F3F4F6")
                )
                st.plotly_chart(fig_rfm, use_container_width=True, key="visit_rfm_outcomes")
            
            st.markdown("---")

        st.markdown(f"Showing **{len(v_df)}** of **{len(visit_df)}** historical visits:")
        st.dataframe(v_df.head(1000), width='stretch')
        st.caption("Showing up to the first 1,000 matching rows. Use the buttons below to export the complete filtered dataset.")
        st.markdown("---")
        st.write("##### Export Directory")
        render_download_buttons(v_df, "historical_visit_log", "visit", "visit_log")

# ------------------------------------------------------------
# PAGE: KNOW YOUR CUSTOMER
# ------------------------------------------------------------
elif page == "Know Your Customer":
    st.title("Know Your Customer")
    st.caption("Inspect active customer profiles, RFM segments, and monetary value statistics.")
    f_df = customer_directory_filters("know_cust")
    render_know_customer(f_df)

# ------------------------------------------------------------
# PAGE: KNOW YOUR SALESPERSON
# ------------------------------------------------------------
elif page == "Know Your Salesperson":
    st.title("Know Your Salesperson")
    st.caption("Inspect salesperson performance, active status, and territory coverage.")
    render_know_salesperson()

# ------------------------------------------------------------
# PAGE: KNOW YOUR TERRITORY
# ------------------------------------------------------------
elif page == "Know Your Territory":
    st.title("Know Your Territory")
    st.caption("Inspect territory logistics centroids, customer counts, and lifecycle statuses.")
    f_df = customer_directory_filters("know_terr")
    render_know_territory(f_df)

# ------------------------------------------------------------
# PAGE 2: MONTHLY PLAN GENERATOR
# ------------------------------------------------------------
elif page == "Monthly Plan Generator":
    st.title("Monthly Journey Plan Generator")
    st.caption("Generate mathematical schedules on the fly. Utilizes OR-Tools CP-SAT and outputs validation checklist.")

    if customer_df is None:
        st.stop()

    status = st.session_state["solver_container"]["status"]

    if status == "idle":
        tab_gen, tab_exist = st.tabs(["Generate Plan", "Use an Existing Plan"])
        
        with tab_gen:
            st.write("### Solver Configurations")
            st.caption("These settings are loaded from Global Configurations and are read-only here.")

            # Load default configs
            cfg_vals = config_df.set_index("config_key")["config_value"].to_dict() if config_df is not None else {}

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                ui_speed = st.slider("Average Route Speed (km/h)", 15, 60, int(cfg_vals.get("avg_speed_kmh", 32)), disabled=True)
            with c2:
                ui_service = st.slider("Average Service Time (min)", 5, 60, int(cfg_vals.get("avg_service_time_min", 22)), disabled=True)
            with c3:
                ui_shift = st.number_input("Salesperson Daily Limit (min)", 120, 600, int(cfg_vals.get("salesman_daily_work_minutes", 480)), step=30, disabled=True)
            with c4:
                ui_solve_time = st.slider("Solver Run Time (sec)", 10, 1200, int(cfg_vals.get("solver_run_time_sec", 1200)), step=10, disabled=True)

            sel_ter = st.selectbox("Run Solver For Territory", ["All Territories"] + list(territory_df["territory_id"].unique()))
            run_month_start = st.date_input("Schedule Month Start Date", datetime(2026, 7, 1))

            ui_min_visit = st.checkbox(
                "Require minimum 1 visit per customer",
                value=(cfg_vals.get("require_min_visit", "True") == "True"),
                disabled=True,
                help="When ON, the solver enforces at least one visit for every active customer "
                     "(relaxing only if capacity makes it impossible). When OFF, the solver "
                     "maximizes value within caps and may leave some customers unvisited."
            )

            # Run solver button
            if st.button("Generate Schedule & Optimize Routes", type="primary"):
                config_override = {
                    "avg_speed": ui_speed,
                    "customer_serving_time": ui_service,
                    "salesman_daily_work_minutes": ui_shift,
                    "require_min_visit": ui_min_visit
                }

                target_ter = None if sel_ter == "All Territories" else sel_ter
                month_str = run_month_start.strftime("%Y-%m-%d")

                # Update state to running
                st.session_state["solver_container"]["status"] = "running"
                st.session_state["solver_container"]["start_time"] = time.time()
                st.session_state["solver_container"]["meta"] = {
                    "month": month_str,
                    "territory": sel_ter,
                    "config": config_override
                }
                st.session_state["solver_container"]["result"] = None
                st.session_state["solver_container"]["error"] = None

                # Truncate solver log
                log_path = os.path.join(current_dir, "solver_log.txt")
                with open(log_path, "w", encoding="utf-8") as lf:
                    lf.write(f"=== Optimization Started: {datetime.now()} ===\n")
                    lf.write(f"Config Override: {config_override}\n")
                    lf.write(f"Target Territory: {sel_ter}\n")
                    lf.write(f"Require min-1-visit: {ui_min_visit}\n")
                    lf.write(f"Month: {month_str}\n\n")

                # Start background thread
                container = st.session_state["solver_container"]

                def run_thread_job(cnt, speed, s_time, work_min, m_str, t_id, solve_time, require_min_visit = True):
                    try:
                        import scheduler_osrm
                        # Dynamically override the backend solver's hardcoded time limits proportionally
                        scheduler_osrm.MIN_SOLVER_TIME = max(10, solve_time // 2)
                        scheduler_osrm.MAX_SOLVER_TIME = solve_time

                        # Get OSRM config parameters
                        cfg_vals = config_df.set_index("config_key")["config_value"].to_dict() if config_df is not None else {}
                        osrm_mode = cfg_vals.get("osrm_routing_mode", "http")
                        osrm_url = cfg_vals.get("osrm_server_url", "http://router.project-osrm.org")
                        osrm_path = cfg_vals.get("osrm_data_path", "")

                        scheduler = MultiSalesManScheduler({
                            "avg_speed": speed,
                            "customer_serving_time": s_time,
                            "salesman_daily_work_minutes": work_min,
                            "osrm_routing_mode": osrm_mode,
                            "osrm_server_url": osrm_url,
                            "osrm_data_path": osrm_path
                        })
                        res = scheduler.create_monthly_schedule(
                            customer_df=customer_df,
                            rfm_scores_df=rfm_scores_df,
                            salesperson_df=salesperson_df,
                            holiday_df=holiday_df,
                            territory_df=territory_df,
                            van_df=van_df,
                            month_start_date=m_str,
                            territory_id=t_id,
                            require_min_visit=require_min_visit
                        )
                        cnt["result"] = res
                        cnt["status"] = "finished"
                    except Exception as e:
                        import traceback
                        cnt["error"] = f"{str(e)}\n{traceback.format_exc()}"
                        cnt["status"] = "error"

                t = threading.Thread(
                    target=run_thread_job,
                    args=(
                        container,
                        ui_speed,
                        ui_service,
                        ui_shift,
                        month_str,
                        target_ter,
                        ui_solve_time,
                        ui_min_visit
                    )
                )
                t.start()
                st.rerun()

        with tab_exist:
            st.write("### Use an Existing Plan (skip solver)")
            st.caption("Load a previously generated monthly plan from disk. All downstream "
                       "sections (VRP Routing & Driver Maps, Executive Analytics) will use it.")
            existing_files = list_existing_plan_files()
            if not existing_files:
                st.info("No saved plan workbooks found in the output folder.")
            else:
                labels = [os.path.basename(f) for f in existing_files]
                sel_existing = st.selectbox("Available saved plans", labels, key="existing_plan_sel")
                if st.button("Load This Plan & Use Downstream", key="load_existing_plan"):
                    try:
                        path = existing_files[labels.index(sel_existing)]
                        with st.spinner("Loading saved plan..."):
                            res_loaded, meta_loaded = load_existing_plan_result(path)
                        st.session_state["latest_plan"] = res_loaded
                        st.session_state["latest_plan_meta"] = meta_loaded
                        st.success(f"Loaded {sel_existing} - "
                                   f"{len(res_loaded.detailed_schedule)} scheduled visits, "
                                   f"scope {meta_loaded['territory']}, month {meta_loaded['month']}.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to load plan: {e}")

        # Display previous results notification if available in st.session_state
        if st.session_state["latest_plan"] is not None:
            st.markdown("---")
            st.info("A plan is loaded and available. Inspect details below, or configure options above to build a new one.")

    elif status == "running":
        st.info("Optimization Solver is currently running in the background...")
        elapsed = time.time() - st.session_state["solver_container"]["start_time"]
        st.write(f"Elapsed Time: **{elapsed:.1f} seconds**")

        tab_status, tab_logs = st.tabs(["Generation Status", "Live Execution Log"])
        with tab_status:
            st.info("Monthly plan is generating, it will take around 10min-20min, kindly wait")
        with tab_logs:
            st.write("### OR-Tools CP-SAT Solver Execution Output (Live Log)")
            log_placeholder = st.empty()

            # Read and display logs
            log_path = os.path.join(current_dir, "solver_log.txt")
            log_text = ""
            if os.path.exists(log_path):
                with open(log_path, "r", encoding="utf-8") as lf:
                    log_text = lf.read()

            lines = log_text.split("\n")
            log_placeholder.code("\n".join(lines[-20:]), language="text")

        # Auto-refresh loop
        time.sleep(1.5)
        st.rerun()

    elif status == "finished":
        st.success("Optimization schedule completed successfully!")
        st.session_state["latest_plan"] = st.session_state["solver_container"]["result"]
        st.session_state["latest_plan_meta"] = st.session_state["solver_container"]["meta"]

        if st.button("Reset & Build New Plan"):
            st.session_state["solver_container"]["status"] = "idle"
            st.session_state["solver_container"]["result"] = None
            st.session_state["solver_container"]["error"] = None
            st.session_state["solver_container"]["meta"] = None
            st.rerun()

    elif status == "error":
        st.error("Solver failed with an error during background execution:")
        st.code(st.session_state["solver_container"]["error"], language="text")

        if st.button("Reset Solver"):
            st.session_state["solver_container"]["status"] = "idle"
            st.session_state["solver_container"]["error"] = None
            st.rerun()

    # Display results if available
    if st.session_state["latest_plan"] is not None:
        res = st.session_state["latest_plan"]
        meta = st.session_state["latest_plan_meta"]

        st.write("## Optimization Results & Validation Checklist")
        st.info(f"Showing schedule details for **{meta['month']}** | Scope: **{meta['territory']}**")

        if res.detailed_schedule.empty:
            st.warning("No solution schedule returned. The solver might be infeasible. Running failure diagnostics...")
            diags = diagnose_schedule_failure(
                customer_df=customer_df,
                salesperson_df=salesperson_df,
                van_df=van_df,
                holiday_df=holiday_df,
                territory_df=territory_df,
                config_df=meta["config"],
                month_start_date=meta["month"],
                territory_id=None if meta["territory"] == "All Territories" else meta["territory"]
            )
            for d in diags:
                st.error(f"{d}")
            st.stop()

        # Metrics Summary
        r1, r2, r3, r4 = st.columns(4)
        with r1:
            tot_visits = len(res.detailed_schedule)
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">Total Visits Scheduled</div>
                <div class="stat-value">{tot_visits}</div>
            </div>
            """, unsafe_allow_html=True)
        with r2:
            unv_cnt = len(res.unvisited_customers)
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">Unvisited (0 visits)</div>
                <div class="stat-value" style="color: {'#10B981' if unv_cnt == 0 else '#EF4444'}">{unv_cnt}</div>
            </div>
            """, unsafe_allow_html=True)
        with r3:
            und_cnt = len(res.under_visited_customers)
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">Under-Visited (&lt; Cap)</div>
                <div class="stat-value" style="color: {'#10B981' if und_cnt == 0 else '#F5A623'}">{und_cnt}</div>
            </div>
            """, unsafe_allow_html=True)
        with r4:
            tot_dist = res.detailed_schedule["route_leg_km"].sum() if "route_leg_km" in res.detailed_schedule.columns else 0.0
            st.markdown(f"""
            <div class="stat-card">
                <div class="stat-label">Total Distance Travelled</div>
                <div class="stat-value">{tot_dist:,.1f} km</div>
            </div>
            """, unsafe_allow_html=True)



        # Unvisited & Under-visited Outlets List
        combined_list = []
        caps = {"High": 15, "Medium": 6, "Low": 4}
        if config_df is not None:
            try:
                cfg_dict = config_df.set_index("config_key")["config_value"].to_dict()
                caps["High"] = int(float(cfg_dict.get("segment_cap_high", 15)))
                caps["Medium"] = int(float(cfg_dict.get("segment_cap_medium", 6)))
                caps["Low"] = int(float(cfg_dict.get("segment_cap_low", 4)))
            except Exception:
                pass

        if hasattr(res, "unvisited_customers") and res.unvisited_customers is not None and not res.unvisited_customers.empty:
            uv = res.unvisited_customers.copy()
            uv["Status"] = "Unvisited"
            uv["Actual Visits"] = 0
            seg_col = "rfm_segment_final" if "rfm_segment_final" in uv.columns else ("segment" if "segment" in uv.columns else "")
            if seg_col:
                uv["Target Visits"] = uv[seg_col].map(caps).fillna(0).astype(int)
            else:
                uv["Target Visits"] = 0
            uv["Visits Gap"] = uv["Target Visits"]
            
            cols_to_keep = ["customer_id", "shop_name", "territory_id", "Status", "Actual Visits", "Target Visits", "Visits Gap"]
            if seg_col:
                uv = uv.rename(columns={seg_col: "RFM Segment"})
                cols_to_keep.append("RFM Segment")
            else:
                uv["RFM Segment"] = "Unknown"
                cols_to_keep.append("RFM Segment")
            combined_list.append(uv[[c for c in cols_to_keep if c in uv.columns]])

        if hasattr(res, "under_visited_customers") and res.under_visited_customers is not None and not res.under_visited_customers.empty:
            ud = res.under_visited_customers.copy()
            ud["Status"] = "Under-visited"
            ud["Actual Visits"] = ud["actual_visits"].fillna(0).astype(int) if "actual_visits" in ud.columns else 0
            ud["Target Visits"] = ud["visit_cap"].fillna(0).astype(int) if "visit_cap" in ud.columns else 0
            ud["Visits Gap"] = ud["visits_gap"].fillna(0).astype(int) if "visits_gap" in ud.columns else 0
            seg_col = "rfm_segment_final" if "rfm_segment_final" in ud.columns else ("segment" if "segment" in ud.columns else "")
            
            cols_to_keep = ["customer_id", "shop_name", "territory_id", "Status", "Actual Visits", "Target Visits", "Visits Gap"]
            if seg_col:
                ud = ud.rename(columns={seg_col: "RFM Segment"})
                cols_to_keep.append("RFM Segment")
            else:
                ud["RFM Segment"] = "Unknown"
                cols_to_keep.append("RFM Segment")
            combined_list.append(ud[[c for c in cols_to_keep if c in ud.columns]])

        if not combined_list:
            st.success("The entire plan has been generated successfully.")
        else:
            df_unres = pd.concat(combined_list, ignore_index=True)
            if df_unres.empty:
                st.success("The entire plan has been generated successfully.")
            else:
                st.write("### Unvisited & Under-visited Outlets Analysis")
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    unres_ter = st.selectbox("Filter by Territory", ["All"] + sorted(list(df_unres["territory_id"].dropna().unique())), key="unres_ter_filter")
                with col_u2:
                    unres_search = st.text_input("Search Customer ID or Shop Name", key="unres_search_filter")
                    
                df_filtered = df_unres.copy()
                if unres_ter != "All":
                    df_filtered = df_filtered[df_filtered["territory_id"] == unres_ter]
                if unres_search:
                    df_filtered = df_filtered[
                        df_filtered["customer_id"].astype(str).str.contains(unres_search, case=False, na=False) |
                        df_filtered["shop_name"].astype(str).str.contains(unres_search, case=False, na=False)
                    ]
                
                if df_filtered.empty:
                    st.info("No unvisited/under-visited customers match the selected filters.")
                else:
                    st.dataframe(df_filtered, use_container_width=True, hide_index=True)

        # Download reports center
        st.write("### Reports Center")
        c1, c2, c3 = st.columns(3)
        with c1:
            csv_data = res.detailed_schedule.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Detailed Schedule (CSV)",
                data=csv_data,
                file_name=f"detailed_schedule_{meta['month']}.csv",
                mime="text/csv",
                width='stretch'
            )
        with c2:
            st.write("Generating Excel Route summary...")
            # Trigger VRP excel export on user button click
            if st.button("Generate & Download Stop-to-Stop Excel", width='stretch'):
                filepath = os.path.join(OUTPUT_DIR, f"stop_to_stop_distances.xlsx")
                first_ter = territory_df["territory_id"].iloc[0] if target_t_id is None else target_t_id
                export_stop_to_stop_excel(res, first_ter, meta["month"], filepath)
                with open(filepath, "rb") as f:
                    st.download_button(
                        label="Click here to Download Excel Workbook",
                        data=f,
                        file_name=f"VRP_stop_to_stop_{meta['month']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width='stretch'
                    )
        with c3:
            st.write("Generating Under-visited report...")
            if st.button("Generate & Download Under-Visited Report", width='stretch'):
                filepath = os.path.join(OUTPUT_DIR, f"under_visited_report.xlsx")
                export_under_visited_excel(res, filepath, territory_id=target_t_id)
                with open(filepath, "rb") as f:
                    st.download_button(
                        label="Click here to Download Excel Report",
                        data=f,
                        file_name=f"Under_visited_report_{meta['month']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width='stretch'
                    )

# ------------------------------------------------------------
# PAGE 3: VRP ROUTING & DRIVER MAPS
# ------------------------------------------------------------
elif page == "VRP Routing & Driver Maps":
    st.title("VRP Routing & Interactive Driver Maps")
    st.caption("Inspect daily trip maps, stop sequence logs, and driver work times.")

    if st.session_state["latest_plan"] is None:
        st.warning("No generated plan loaded. Please run the monthly solver in the 'Monthly Plan Generator' first.")
        st.stop()

    res = st.session_state["latest_plan"]
    meta = st.session_state["latest_plan_meta"]

    # Active plan info
    st.info(f"Showing maps based on plan run: **{meta['month']}** | Scope: **{meta['territory']}**")

    # OSRM Router Diagnostics (commented out as requested)
    # with st.expander("OSRM Router Diagnostics & Connectivity Test"):
    #     osrm_h = getattr(res, "osrm_helper", None)
    #     if osrm_h is None:
    #         st.error("No OSRM helper attached to the loaded plan.")
    #     else:
    #         st.write(f"**Current Session Helper Mode**: `{osrm_h.mode}`")
    #         st.write(f"**Configured Server URL**: `{osrm_h.server_url}`")
    #         st.write(f"**Configured Data Path**: `{osrm_h.data_path}`")
    #         
    #         if osrm_h.mode == "haversine":
    #             st.warning("OSRM mode is currently Haversine (straight lines). This might be due to a previous request timeout or connection failure, or because Haversine is the configured default.")
    #         
    #         c_test1, c_test2 = st.columns(2)
    #         with c_test1:
    #             if st.button("Test OSRM Connection (Force HTTP/Native)"):
    #                 import requests
    #                 st.write(f"Pinging OSRM server at `{osrm_h.server_url}/nearest/v1/driving/46.6753,24.7136` ...")
    #                 try:
    #                     r = requests.get(f"{osrm_h.server_url}/nearest/v1/driving/46.6753,24.7136", timeout=4)
    #                     st.success(f"Connection Successful! HTTP status: {r.status_code}")
    #                     st.write("Response body:", r.json())
    #                 except Exception as e:
    #                     st.error(f"Connection Failed: {e}")
    #         with c_test2:
    #             if st.button("Test Route Retrieval"):
    #                 test_coords = [(24.7136, 46.6753), (24.7236, 46.6853)]
    #                 st.write("Retrieving road path route for Riyadh coordinates...")
    #                 from osrm_helper import OSRMHelper
    #                 temp_h = OSRMHelper(mode="http", server_url=osrm_h.server_url, data_path=osrm_h.data_path)
    #                 try:
    #                     route_info = temp_h.get_route(test_coords, raise_errors=True)
    #                     if route_info and "geometry" in route_info:
    #                         st.success(f"Route Retrieved successfully! Leg distance: {route_info.get('distance', 0.0):.1f} meters, Shape points: {len(route_info['geometry'])}")
    #                     else:
    #                         st.error(f"Failed to retrieve route shape. Route info: {route_info}")
    #                 except Exception as e:
    #                     st.error(f"Route query failed: {e}")
    #     
    #     # Reset mode button
    #     if st.button("Reset Helper Mode to HTTP"):
    #         if osrm_h:
    #             osrm_h.mode = "http"
    #             st.success("Reset helper mode back to 'http' for this session!")
    #             st.rerun()

    # Map filters
    c1, c2, c3 = st.columns(3)
    with c1:
        # Determine available territories in detailed schedule
        avail_terr = sorted(res.detailed_schedule["territory_id"].unique())
        sel_t = st.selectbox("Select Map Territory", avail_terr)
    with c2:
        # Filter dates for that territory
        t_sched = res.detailed_schedule[res.detailed_schedule["territory_id"] == sel_t]
        avail_dates = sorted(t_sched["schedule_date"].unique())
        avail_dates_str = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in avail_dates]
        sel_d_str = st.selectbox("Select Date of Month", avail_dates_str)
        sel_d = pd.Timestamp(sel_d_str)
    with c3:
        # Filter drivers (salespeople) active on that day
        d_sched = t_sched[t_sched["schedule_date"] == sel_d]
        avail_drivers = sorted(d_sched["sales_id"].unique())
        sel_driver = st.selectbox("Select Driver (Salesperson)", avail_drivers)

    # Render full-width route map
    st.subheader("Route Map")
    map_type = st.radio("Map View Options", ["Individual Driver Route", "Territory Overview (All Drivers)"], horizontal=True)

    wh_lat, wh_lng = res.territory_warehouses.get(sel_t, (0.0, 0.0))

    try:
        if map_type == "Individual Driver Route":
            with st.spinner("Drawing individual route map..."):
                m = build_route_map_for_salesperson(
                    daily_schedule=res.daily_schedule,
                    detailed_schedule=res.detailed_schedule,
                    sales_id=sel_driver,
                    schedule_date=sel_d,
                    warehouse_lat=wh_lat,
                    warehouse_lng=wh_lng,
                    osrm_helper=getattr(res, "osrm_helper", None)
                )
                display_map(m, key=f"ind_map_{sel_driver}_{sel_d_str}", height=750)
        else:
            with st.spinner("Drawing territory map..."):
                m = build_territory_day_map(
                    result=res,
                    territory_id=sel_t,
                    schedule_date=sel_d
                )
                display_map(m, key=f"terr_map_{sel_t}_{sel_d_str}", height=750)
    except Exception as e:
        st.error(f"Error drawing map: {e}")
        st.info("Check GPS coordinates or ensure data contains latitude and longitude columns.")

    st.markdown("---")
    st.subheader("Driver Daily Schedule & VRP Logs")

    # Filter the single salesperson day summary
    driver_day = res.detailed_schedule[
        (res.detailed_schedule["sales_id"] == sel_driver) &
        (res.detailed_schedule["schedule_date"] == sel_d)
    ].copy()

    if driver_day.empty:
        st.warning("No stops found for this driver on the selected day.")
    else:
        if "route_rank" in driver_day.columns:
            driver_day = driver_day.sort_values("route_rank")

        # Quick KPIs
        stops_count = len(driver_day)
        total_km = driver_day["route_leg_km"].sum() if "route_leg_km" in driver_day.columns else 0.0

        sc1, sc2 = st.columns(2)
        sc1.metric("Stops Visited", stops_count)
        sc2.metric("Total Route Distance", f"{total_km:.2f} km")

        # Stop table
        st.write("##### Stop Order List")
        stops_log = []
        for _, r in driver_day.iterrows():
            stops_log.append({
                "Seq": int(r.get("route_rank", 0)),
                "Customer ID": r["customer_id"],
                "Shop Name": r.get("shop_name", ""),
                "Locality": r.get("locality", ""),
                "Segment": r.get("rfm_segment_final", ""),
                "Leg (km)": r.get("route_leg_km", 0.0),
                "Cum (km)": r.get("cumulative_route_km", 0.0)
            })
        st.dataframe(pd.DataFrame(stops_log), width='stretch', hide_index=True)

        # Stop distance detail breakdown (OR-Tools table)
        st.write("##### VRP Stop-to-Stop Distance Table")
        dist_tbl = build_stop_to_stop_distance_table(res, sel_t, sel_d, sel_driver)
        if not dist_tbl.empty:
            st.dataframe(
                dist_tbl[["stop_from", "stop_to", "from_shop", "to_shop", "leg_km", "leg_min"]],
                width='stretch',
                hide_index=True
            )

# ------------------------------------------------------------
# PAGE 4: EXECUTIVE VISUALIZATION & ANALYTICS
# ------------------------------------------------------------
elif page == "Executive Visualization & Analytics":
    st.title("Executive Visualization & Analytics")
    st.caption("Visual dashboard for active journey optimization plan metrics.")
    
    if customer_df is None:
        st.stop()
        
    plan_generated = st.session_state["latest_plan"] is not None
    
    if not plan_generated:
        st.warning("Please generate a plan or use a generated plan to view the analysis charts.")
        st.stop()
        
    class NullContext:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    tab_plan = NullContext()
    
    # Master Registry Analytics is commented out for now
    _unused_analytics_code = """
    tab_master = NullContext()
    with tab_master:
        st.write("## Master Data Registry Insights")
        
        # Layout with metrics row
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            st.metric("Total Customer Base", len(customer_df))
        with c_m2:
            active_sps = int(salesperson_df["active_status"].sum())
            st.metric("Active Salesperson Fleet", f"{active_sps} / {len(salesperson_df)}")
        with c_m3:
            active_vans = int(van_df["active_status"].sum())
            st.metric("Active Fleet Vans", f"{active_vans} / {len(van_df)}")
            
        # Customer Tiers by Territory
        t_tier = customer_df.groupby(["territory_id", "volume_tier"]).size().unstack(fill_value=0)
        
        # Lifecycle distribution
        t_life = customer_df.groupby(["territory_id", "lifecycle_state"]).size().unstack(fill_value=0)
        
        # RFM segment counts
        rfm_counts = rfm_scores_df["rfm_segment_final"].value_counts()
        
        # Cold-chain requirements
        cold_share = customer_df.groupby("territory_id")["cold_truck_required"].mean() * 100
        
        if has_plotly:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                fig_tier = px.bar(
                    t_tier.reset_index(),
                    x="territory_id",
                    y=t_tier.columns,
                    title="Outlet Volume Tier Breakdown by Territory",
                    barmode="group",
                    color_discrete_sequence=["#1E3A8A", "#0D9488", "#F5A623", "#64748B"],
                    labels={"value": "Customer Count", "territory_id": "Territory ID"}
                )
                fig_tier.update_layout(template="plotly_white", margin=dict(t=45, b=30, l=30, r=30))
                st.plotly_chart(fig_tier, use_container_width=True)
                
            with col_c2:
                fig_life = px.bar(
                    t_life.reset_index(),
                    x="territory_id",
                    y=t_life.columns,
                    title="Customer Lifecycle States by Territory",
                    barmode="stack",
                    color_discrete_sequence=["#10B981", "#3B82F6", "#EF4444", "#8B5CF6"],
                    labels={"value": "Customer Count", "territory_id": "Territory ID"}
                )
                fig_life.update_layout(template="plotly_white", margin=dict(t=45, b=30, l=30, r=30))
                st.plotly_chart(fig_life, use_container_width=True)
                
            col_c3, col_c4 = st.columns(2)
            with col_c3:
                fig_rfm = px.pie(
                    names=rfm_counts.index,
                    values=rfm_counts.values,
                    title="RFM Combined Segments Share",
                    hole=0.45,
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_rfm.update_layout(margin=dict(t=45, b=30, l=30, r=30))
                st.plotly_chart(fig_rfm, use_container_width=True)
                
            with col_c4:
                cold_share_df = cold_share.reset_index(name="Cold-Chain Required %")
                fig_cold = px.bar(
                    cold_share_df,
                    x="territory_id",
                    y="Cold-Chain Required %",
                    title="Cold-Chain Truck Requirements by Territory (%)",
                    color="Cold-Chain Required %",
                    color_continuous_scale="Blues",
                    labels={"territory_id": "Territory ID"}
                )
                fig_cold.update_layout(template="plotly_white", margin=dict(t=45, b=30, l=30, r=30))
                st.plotly_chart(fig_cold, use_container_width=True)
        else:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.write("##### Outlet Volume Tier Breakdown by Territory")
                st.bar_chart(t_tier, use_container_width=True)
            with col_c2:
                st.write("##### Customer Lifecycle States by Territory")
                st.bar_chart(t_life, use_container_width=True)
                
            col_c3, col_c4 = st.columns(2)
            with col_c3:
                st.write("##### RFM Combined Segments Distribution")
                st.bar_chart(rfm_counts, use_container_width=True)
            with col_c4:
                st.write("##### Cold-Chain Truck Requirements by Territory")
                st.bar_chart(cold_share, use_container_width=True)
    """
                
    # ------------------------------------------------------------
    # TAB 2: OPTIMIZED ROUTE PLAN ANALYTICS
    # ------------------------------------------------------------
    with tab_plan:
        if True:
            if not plan_generated:
                st.warning("No generated plan loaded. Please run the monthly solver in the 'Monthly Plan Generator' first.")
                st.stop()

            res = st.session_state["latest_plan"]
            meta = st.session_state["latest_plan_meta"]
            
            st.success(f"Displaying active plan visualizations for: **{meta['month']}** | Scope: **{meta['territory']}**")
            
            # Extract scheduler stats
            detailed = res.detailed_schedule
            
            # Determine the subset of customers involved in this plan
            if meta["territory"] != "All Territories":
                t_cust_df = customer_df[customer_df["territory_id"] == meta["territory"]]
            else:
                t_cust_df = customer_df
                
            # Date-wise or Cumulative selectbox filter
            avail_dates = sorted(detailed["schedule_date"].unique())
            avail_dates_str = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in avail_dates]
            
            selected_date_opt = st.selectbox(
                "Filter Visualizations by Date Scope",
                ["Cumulative Month"] + avail_dates_str,
                index=0,
                key="plan_date_scope_selector"
            )
            
            is_cumulative = (selected_date_opt == "Cumulative Month")
            if is_cumulative:
                view_detailed = detailed
                total_custs = len(t_cust_df)
                unvisited_custs = len(res.unvisited_customers)
                visited_custs = max(0, total_custs - unvisited_custs)
            else:
                target_date = pd.Timestamp(selected_date_opt)
                view_detailed = detailed[detailed["schedule_date"] == target_date]
                total_custs = len(t_cust_df)
                visited_custs = view_detailed["customer_id"].nunique()
                unvisited_custs = max(0, total_custs - visited_custs)
            
            # Coverage metrics row
            p_m1, p_m2, p_m3 = st.columns(3)
            with p_m1:
                visits_label = "Total Scheduled Visits" if is_cumulative else f"Scheduled Visits ({selected_date_opt})"
                st.metric(visits_label, len(view_detailed))
            with p_m2:
                coverage_label = "Store Coverage Ratio" if is_cumulative else f"Daily Store Coverage ({selected_date_opt})"
                st.metric(coverage_label, f"{visited_custs} / {total_custs} outlets", f"{visited_custs/total_custs*100:.1f}%" if total_custs > 0 else "0.0%")
            with p_m3:
                dist_label = "Total Mileage Allotted" if is_cumulative else f"Total Distance ({selected_date_opt})"
                total_dist = view_detailed["route_leg_km"].sum() if "route_leg_km" in view_detailed.columns else 0.0
                st.metric(dist_label, f"{total_dist:,.1f} km")
                
            # Group by salesperson to show estimated workload
            cfg_vals = config_df.set_index("config_key")["config_value"].to_dict() if config_df is not None else {}
            service_time_min = int(float(cfg_vals.get("avg_service_time_min", 22)))
            avg_speed = float(cfg_vals.get("avg_speed_kmh", 32))
            
            # service minutes per salesperson
            sp_service = view_detailed.groupby("sales_id").size().reset_index(name="service_min")
            sp_service["service_min"] = sp_service["service_min"] * service_time_min
            
            if "route_leg_km" in view_detailed.columns:
                sp_travel = view_detailed.groupby("sales_id")["route_leg_km"].sum().reset_index(name="travel_min")
                sp_travel["travel_min"] = (sp_travel["travel_min"] / avg_speed * 60).round(1)
                sp_dist = view_detailed.groupby("sales_id")["route_leg_km"].sum().reset_index(name="distance_km")
            else:
                sp_travel = pd.DataFrame(columns=["sales_id", "travel_min"])
                sp_dist = pd.DataFrame(columns=["sales_id", "distance_km"])
                sp_dist["distance_km"] = 0.0
                
            sp_visits = view_detailed.groupby("sales_id").size().reset_index(name="visits")
            
            # Merge all salesperson metrics
            sp_metrics = sp_service.merge(sp_travel, on="sales_id", how="outer")
            sp_metrics = sp_metrics.merge(sp_dist, on="sales_id", how="outer")
            sp_metrics = sp_metrics.merge(sp_visits, on="sales_id", how="outer").fillna(0.0)
            sp_metrics["total_workload"] = sp_metrics["service_min"] + sp_metrics["travel_min"]
            
            work_summary = sp_metrics.rename(columns={
                "sales_id": "Salesperson ID",
                "service_min": "Total Service Time (min)" if is_cumulative else "Service Time (min)",
                "travel_min": "Total Travel Time (min)" if is_cumulative else "Travel Time (min)",
                "total_workload": "Total Workload (min)" if is_cumulative else "Workload (min)",
                "distance_km": "Total Distance (km)" if is_cumulative else "Distance (km)",
                "visits": "Scheduled Visits" if is_cumulative else "Visits"
            }).set_index("Salesperson ID")
            
            st.write("### Multi-Dimensional Salesperson Performance Dashboard")
            
            if has_plotly:
                # Build the unified Plotly Subplot
                fig_sp = make_subplots(
                    rows=1, cols=1,
                    subplot_titles=(
                        f"Time Allocation ({'Cumulative Monthly' if is_cumulative else selected_date_opt}) (Minutes)",
                    ),
                    specs=[[{"secondary_y": False}]]
                )

                # Row 1 Bar Chart traces for Time Allocation
                fig_sp.add_trace(
                    go.Bar(
                        x=sp_metrics["sales_id"],
                        y=sp_metrics["service_min"],
                        name="Service Time (min)",
                        marker_color="#0D9488",
                        hovertemplate="Salesperson: %{x}<br>Service Time: %{y} min<extra></extra>"
                    ),
                    row=1, col=1
                )
                fig_sp.add_trace(
                    go.Bar(
                        x=sp_metrics["sales_id"],
                        y=sp_metrics["travel_min"],
                        name="Travel Time (min)",
                        marker_color="#F97316",
                        hovertemplate="Salesperson: %{x}<br>Travel Time: %{y:.1f} min<extra></extra>"
                    ),
                    row=1, col=1
                )
                fig_sp.add_trace(
                    go.Bar(
                        x=sp_metrics["sales_id"],
                        y=sp_metrics["total_workload"],
                        name="Total Workload (min)",
                        marker_color="#6366F1",
                        hovertemplate="Salesperson: %{x}<br>Total Workload: %{y:.1f} min<extra></extra>"
                    ),
                    row=1, col=1
                )

                fig_sp.update_layout(
                    height=450,
                    barmode="group",
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1.02,
                        xanchor="left",
                        x=1.02
                    ),
                    template="plotly_white",
                    margin=dict(t=50, b=30, l=30, r=150)
                )

                fig_sp.update_yaxes(title_text="Minutes", row=1, col=1)
                fig_sp.update_xaxes(title_text="Salesperson ID", row=1, col=1)
                
                st.plotly_chart(fig_sp, use_container_width=True)
            else:
                # Fallback to standard streamlit bar charts
                st.write("##### Workload (Service vs Travel Time)")
                st.bar_chart(work_summary[["Total Service Time (min)", "Total Travel Time (min)"]], use_container_width=True)
                
            st.markdown("---")
            st.write("### Detailed Daily Load & Customer Analysis")
            
            # Daily load logic
            daily_load = detailed.groupby("schedule_date").size().reset_index(name="Visits Scheduled")
            
            if has_plotly:
                # 2. Daily visits and distance line/bar chart
                daily_stats = detailed.groupby("schedule_date").agg(
                    visits=("customer_id", "count"),
                    distance=("route_leg_km", "sum") if "route_leg_km" in detailed.columns else ("customer_id", lambda x: 0.0)
                ).reset_index()
                daily_stats = daily_stats.sort_values("schedule_date")
                daily_stats["date_str"] = daily_stats["schedule_date"].dt.strftime("%Y-%m-%d")

                fig_daily = go.Figure()
                fig_daily.add_trace(
                    go.Bar(
                        x=daily_stats["date_str"],
                        y=daily_stats["visits"],
                        name="Scheduled Visits",
                        marker_color="#3B82F6",
                        opacity=0.8
                    )
                )
                fig_daily.add_trace(
                    go.Scatter(
                        x=daily_stats["date_str"],
                        y=daily_stats["distance"],
                        name="Travel Distance (km)",
                        mode="lines+markers",
                        line=dict(color="#EF4444", width=2.5),
                        yaxis="y2"
                    )
                )
                
                # Highlight selected day in the daily trend chart
                if not is_cumulative:
                    fig_daily.add_vline(
                        x=selected_date_opt,
                        line_width=3,
                        line_dash="dash",
                        line_color="green",
                        annotation_text="Selected Date",
                        annotation_position="top right"
                    )
                    
                fig_daily.update_layout(
                    title="Daily Workload Distribution (Visits vs Distance)",
                    yaxis=dict(title="Scheduled Visits"),
                    yaxis2=dict(title="Distance (km)", overlaying="y", side="right"),
                    xaxis=dict(title="Date", tickangle=-45),
                    legend=dict(
                        orientation="v",
                        yanchor="top",
                        y=1.02,
                        xanchor="left",
                        x=1.02
                    ),
                    template="plotly_white",
                    height=400,
                    margin=dict(t=50, b=30, l=30, r=150)
                )
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                daily_load = daily_load.set_index("schedule_date")
                st.write("##### Daily Schedule Load (Visits per Day)")
                st.line_chart(daily_load, use_container_width=True)

            col_p3, col_p4 = st.columns(2)
            with col_p3:
                if has_plotly:
                    # 3. Store Coverage Ring (Donut Chart)
                    fig_coverage = go.Figure(data=[go.Pie(
                        labels=["Visited Outlets", "Unvisited Outlets"],
                        values=[visited_custs, unvisited_custs],
                        hole=.5,
                        marker_colors=["#10B981", "#EF4444"]
                    )])
                    title_cov = "Active Store Coverage Ratio" if is_cumulative else f"Store Coverage on {selected_date_opt}"
                    pct_text = f"{visited_custs/total_custs*100:.1f}%" if total_custs > 0 else "0%"
                    fig_coverage.update_layout(
                        title=title_cov,
                        annotations=[dict(text=pct_text, x=0.5, y=0.5, font_size=20, showarrow=False)],
                        showlegend=True,
                        height=350,
                        margin=dict(t=40, b=0, l=0, r=0)
                    )
                    st.plotly_chart(fig_coverage, use_container_width=True)
                else:
                    st.write("##### Store Coverage Share")
                    cov_df = pd.DataFrame([{"Status": "Visited", "Count": visited_custs}, {"Status": "Unvisited", "Count": unvisited_custs}]).set_index("Status")
                    st.bar_chart(cov_df, use_container_width=True)
                    
            with col_p4:
                if has_plotly:
                    # 4. Visits Allocated by RFM Segment
                    segment_visits = view_detailed.groupby("rfm_segment_final").size().reset_index(name="visits")
                    fig_seg_visits = go.Figure(data=[go.Bar(
                        x=segment_visits["rfm_segment_final"],
                        y=segment_visits["visits"],
                        marker_color=["#10B981", "#3B82F6", "#F5A623", "#EF4444"][:len(segment_visits)]
                    )])
                    title_rfm = "Visits Allocated by Customer RFM Segment" if is_cumulative else f"Visits by RFM Segment on {selected_date_opt}"
                    fig_seg_visits.update_layout(
                        title=title_rfm,
                        xaxis_title="RFM Segment",
                        yaxis_title="Scheduled Visits",
                        template="plotly_white",
                        height=350,
                        margin=dict(t=40, b=30, l=30, r=30)
                    )
                    st.plotly_chart(fig_seg_visits, use_container_width=True)
                else:
                    title_rfm = "##### Visits Allocated by Customer RFM Segment" if is_cumulative else f"##### Visits by RFM Segment on {selected_date_opt}"
                    st.write(title_rfm)
                    segment_visits = view_detailed.groupby("rfm_segment_final").size()
                    st.bar_chart(segment_visits, use_container_width=True)
                    
            st.markdown("---")
            table_title = "### Salesperson Workload Table" if is_cumulative else f"### Salesperson Workload Table for {selected_date_opt}"
            st.write(table_title)
            st.dataframe(work_summary, use_container_width=True)

# ------------------------------------------------------------
# PAGE 5: GLOBAL CONFIGURATION SETTINGS
# ------------------------------------------------------------
elif page == "Global Configuration Settings":
    st.title("Global Configuration Settings")
    st.caption("View and edit route planning coefficients, shift limits, and fleet details dynamically.")

    if config_df is None:
        st.stop()

    class NullContext:
        def __enter__(self): return self
        def __exit__(self, *args): pass
    tab1 = NullContext()

    with tab1:
        if "config_save_success" in st.session_state:
            st.success(st.session_state["config_save_success"])
            del st.session_state["config_save_success"]

        st.subheader("Active Global Configuration Coefficient List")
        st.markdown("Modify these variables and save back to both configuration sources persistently.")

        # Load configs into dictionary
        cfg_dict = config_df.set_index("config_key")["config_value"].to_dict()

        # Form
        with st.form("config_editor"):
            avg_sp = st.number_input("Average speed (kmh)", value=int(cfg_dict.get("avg_speed_kmh", 32)))
            service_t = st.number_input("Average customer service time (min)", value=int(cfg_dict.get("avg_service_time_min", 22)))
            buffer = st.number_input("Shift buffer pct (0.0 - 1.0)", value=float(cfg_dict.get("buffer_pct", 0.15)), format="%.2f")
            window = st.number_input("RFM window duration (days)", value=int(cfg_dict.get("rfm_window_days", 90)))
            credit_cap = st.number_input("Credit outstanding balance cap", value=float(cfg_dict.get("credit_outstanding_cap", 0.85)), format="%.2f")
            shift_start = st.text_input("Normal Shift Start time (HH:MM)", value=str(cfg_dict.get("normal_shift_start_time", "09:00")))
            ramadan_start = st.text_input("Ramadan Shift Start time (HH:MM)", value=str(cfg_dict.get("ramadan_shift_start_time", "10:00")))

            # Segment capacities editor
            st.write("##### RFM Segment Visit Caps")
            col1, col2, col3 = st.columns(3)
            with col1:
                cap_high = st.number_input("High segment visits cap", value=int(float(cfg_dict.get("segment_cap_high", 15))))
            with col2:
                cap_med = st.number_input("Medium segment visits cap", value=int(float(cfg_dict.get("segment_cap_medium", 6))))
            with col3:
                cap_low = st.number_input("Low segment visits cap", value=int(float(cfg_dict.get("segment_cap_low", 4))))

            st.write("##### Solver Constraints & Limits")
            col_limit1, col_limit2, col_limit3 = st.columns(3)
            with col_limit1:
                salesperson_limit = st.number_input("Salesperson Daily Limit (min)", value=int(cfg_dict.get("salesman_daily_work_minutes", 480)))
            with col_limit2:
                solve_time = st.number_input("Solver Run Time (sec)", value=int(cfg_dict.get("solver_run_time_sec", 1200)))
            with col_limit3:
                min_visit = st.checkbox("Require minimum 1 visit per customer", value=(cfg_dict.get("require_min_visit", "True") == "True"))

            # # OSRM Router Configurations
            # st.write("##### OSRM Router Configurations")
            # osrm_mode_opt = ["haversine", "http", "native"]
            # curr_mode = str(cfg_dict.get("osrm_routing_mode", "http")).lower()
            # default_mode_idx = osrm_mode_opt.index(curr_mode) if curr_mode in osrm_mode_opt else 0
            # osrm_mode = st.radio("OSRM Routing Mode", osrm_mode_opt, index=default_mode_idx, horizontal=True)

            osrm_mode = str(cfg_dict.get("osrm_routing_mode", "http"))
            osrm_url = str(cfg_dict.get("osrm_server_url", "http://router.project-osrm.org"))
            osrm_path = str(cfg_dict.get("osrm_data_path", ""))

            submitted = st.form_submit_button("Save Settings (CSV & jp_data.xlsx)")

            if submitted:
                # Update DataFrame
                new_cfg = pd.DataFrame([
                    {"config_key": "avg_speed_kmh", "config_value": str(avg_sp)},
                    {"config_key": "avg_service_time_min", "config_value": str(service_t)},
                    {"config_key": "buffer_pct", "config_value": str(buffer)},
                    {"config_key": "rfm_window_days", "config_value": str(window)},
                    {"config_key": "credit_outstanding_cap", "config_value": str(credit_cap)},
                    {"config_key": "normal_shift_start_time", "config_value": str(shift_start)},
                    {"config_key": "ramadan_shift_start_time", "config_value": str(ramadan_start)},
                    {"config_key": "segment_cap_high", "config_value": str(cap_high)},
                    {"config_key": "segment_cap_medium", "config_value": str(cap_med)},
                    {"config_key": "segment_cap_low", "config_value": str(cap_low)},
                    {"config_key": "osrm_routing_mode", "config_value": str(osrm_mode)},
                    {"config_key": "osrm_server_url", "config_value": str(osrm_url)},
                    {"config_key": "osrm_data_path", "config_value": str(osrm_path)},
                    {"config_key": "salesman_daily_work_minutes", "config_value": str(salesperson_limit)},
                    {"config_key": "solver_run_time_sec", "config_value": str(solve_time)},
                    {"config_key": "require_min_visit", "config_value": str(min_visit)}
                ])
                save_config_csv(new_cfg)

                # Apply dynamic Segment Cap updates in scheduler memory
                import scheduler_osrm
                scheduler_osrm.SEG_CAPS = {"High": cap_high, "Medium": cap_med, "Low": cap_low}

                # Save success message in session state and rerun
                st.session_state["config_save_success"] = f"Configurations persistently saved! Router mode={osrm_mode}, caps: High={cap_high}, Med={cap_med}, Low={cap_low}"
                st.rerun()


