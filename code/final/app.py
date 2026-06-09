import streamlit as st
import pandas as pd
import numpy as np
import os
import sys
import threading
import time
import folium
from datetime import datetime

# Insert current directory into path for local imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import backend scheduler and validator
from scheduler_final import (
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

# Try importing plotly
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    has_plotly = True
except ImportError:
    has_plotly = False

# Paths
BASE_DIR = os.path.abspath(os.path.join(current_dir, "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "saudi_master_data_output")
OUTPUT_DIR = os.path.join(BASE_DIR, "jp_data_output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------------------------------------
# PAGE SETUP & STYLING
# ------------------------------------------------------------
st.set_page_config(
    page_title="DelivIQ | Premium Saudi Journey Planner",
    page_icon="🚚",
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
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# DATA LOADING UTILITIES
# ------------------------------------------------------------
# ------------------------------------------------------------
# DATA LOADING UTILITIES
# ------------------------------------------------------------
@st.cache_data(ttl=600)
def load_master_data():
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

    xlsx_path = os.path.join(OUTPUT_DIR, "jp_data.xlsx")
    if os.path.exists(xlsx_path):
        try:
            with pd.ExcelFile(xlsx_path, engine="openpyxl") as xls:
                customer_df = pd.read_excel(xls, sheet_name="customer")
                salesperson_df = pd.read_excel(xls, sheet_name="salesperson")
                van_df = pd.read_excel(xls, sheet_name="van")
                
                # Use holiday sheet only if we couldn't load holiday_1.xlsx or holiday_1.csv
                if holiday_df is None:
                    holiday_df = pd.read_excel(xls, sheet_name="holiday")
                    holiday_df.columns = [c.strip() for c in holiday_df.columns]
                    
                territory_df = pd.read_excel(xls, sheet_name="territory")
                rfm_scores_df = pd.read_excel(xls, sheet_name="rfm_scores")
                config_df = pd.read_excel(xls, sheet_name="config")
                visit_df = pd.read_excel(xls, sheet_name="visit")
                
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
        st.info("Ensure saudi_master_data_output/ directory exists with customer.csv, salesperson.csv, van.csv, etc.")
        return None, None, None, None, None, None, None, None

def save_config_csv(config_df):
    try:
        # Save to config.csv (legacy fallback)
        os.makedirs(DATA_DIR, exist_ok=True)
        config_df.to_csv(os.path.join(DATA_DIR, "config.csv"), index=False)
        
        # Save to jp_data.xlsx if it exists
        xlsx_path = os.path.join(OUTPUT_DIR, "jp_data.xlsx")
        if os.path.exists(xlsx_path):
            sheets = {}
            with pd.ExcelFile(xlsx_path, engine="openpyxl") as xls:
                for sheet_name in xls.sheet_names:
                    sheets[sheet_name] = pd.read_excel(xls, sheet_name=sheet_name)
            
            # Update config sheet
            sheets["config"] = config_df
            
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
            label="⬇️ Download CSV",
            data=csv_bytes,
            file_name=f"{filename_prefix}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            use_container_width=True
        )
    with c2:
        import io
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        st.download_button(
            label="⬇️ Download Excel",
            data=buffer.getvalue(),
            file_name=f"{filename_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_xlsx",
            use_container_width=True
        )

# Helper to render maps dynamically
def display_map(m, key):
    if has_streamlit_folium:
        try:
            st_folium(m, width="100%", height=550, key=key, returned_objects=[])
        except Exception:
            # Fallback to iframe HTML component if st_folium fails
            st.components.v1.html(m._repr_html_(), height=550, scrolling=True)
    else:
        st.components.v1.html(m._repr_html_(), height=550, scrolling=True)

# Load data initially
customer_df, salesperson_df, van_df, holiday_df, territory_df, rfm_scores_df, config_df, visit_df = load_master_data()

# Sync SEG_CAPS from loaded configurations if they exist
if config_df is not None:
    try:
        cfg_dict = config_df.set_index("config_key")["config_value"].to_dict()
        cap_high = int(float(cfg_dict.get("segment_cap_high", 15)))
        cap_med = int(float(cfg_dict.get("segment_cap_medium", 6)))
        cap_low = int(float(cfg_dict.get("segment_cap_low", 4)))
        import scheduler_final
        scheduler_final.SEG_CAPS = {"High": cap_high, "Medium": cap_med, "Low": cap_low}
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

# ------------------------------------------------------------
# SIDEBAR
# ------------------------------------------------------------
st.sidebar.title("DelivIQ Center 🚚")
st.sidebar.caption("Journey Planner & Route Optimization Control Room")
st.sidebar.markdown("---")

# Page list
pages_list = [
    "📊 Master Data Explorer",
    "⚡ Monthly Plan Generator",
    "🗺️ VRP Routing & Driver Maps",
    "📈 Executive Visualization & Analytics",
    "⚙️ Global Configuration Settings"
]

if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "📊 Master Data Explorer"

if is_running:
    st.sidebar.warning("⏳ Navigation is locked while optimization is in progress.")
    page = "⚡ Monthly Plan Generator"
    st.session_state["selected_page"] = "⚡ Monthly Plan Generator"
    # Render disabled radio to show locked status
    st.sidebar.radio("Navigation", pages_list, index=1, disabled=True)
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
if page == "📊 Master Data Explorer":
    st.title("📊 Master Data & Peer Segment Explorer")
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
        tot_mon = customer_df.merge(rfm_scores_df, on="customer_id", how="left")["monetary"].sum()
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Total Peer Value</div>
            <div class="stat-value">SAR {tot_mon:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        credit_pct = (customer_df["payment_type"] == "credit").mean() * 100
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-label">Credit Customers</div>
            <div class="stat-value">{credit_pct:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "👥 Customer Directory", 
        "🗺️ Territory Centroids", 
        "📈 RFM Scoreboard", 
        "📅 Holiday Schedules",
        "🧑‍💼 Salesperson Directory",
        "🚐 Fleet Vehicles",
        "📊 Historical Visit Log"
    ])
    
    with tab1:
        st.subheader("👥 Active Customer Profiles")
        
        # Filters
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            filt_ter = st.selectbox("Filter Territory", ["All"] + list(territory_df["territory_id"].unique()))
        with c2:
            filt_tier = st.selectbox("Filter Volume Tier", ["All", "HIGH", "MED", "LOW"])
        with c3:
            filt_cold = st.selectbox("Cold-Chain Required", ["All", "Yes", "No"])
        with c4:
            filt_life = st.selectbox("Lifecycle State", ["All"] + list(customer_df["lifecycle_state"].unique()))
            
        search_q = st.text_input("🔍 Search outlets by ID or shop name...")
        
        # Apply filters
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
            
        st.markdown(f"Showing **{len(f_df)}** of **{len(customer_df)}** outlets:")
        st.dataframe(
            f_df[["customer_id", "shop_name", "locality", "territory_id", "shop_category", "cold_truck_required", "volume_tier", "payment_type", "outstanding_balance", "lifecycle_state", "preferred_visit_day"]],
            use_container_width=True
        )
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(f_df, "customer_directory", "customer", "cust_dir")

    with tab2:
        st.subheader("🗺️ Territory Logistics Centroids & Warehouses")
        st.dataframe(territory_df, use_container_width=True)
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(territory_df, "territory_centroids", "territory", "terr_cent")
        
    with tab3:
        st.subheader("📈 RFM Combined Score & Segmentation Summary")
        st.markdown("Customers are scored within their peer set (Territory × Truck Group) dynamically.")
        
        # Segment counts
        seg_counts = rfm_scores_df["rfm_segment_final"].value_counts().reset_index()
        seg_counts.columns = ["Segment", "Count"]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.write("#### Peer Segments")
            st.dataframe(seg_counts, use_container_width=True)
        with c2:
            st.write("#### Top 15 Customer Scores")
            top_rfm = rfm_scores_df.nlargest(15, "final_customer_score").merge(customer_df[["customer_id", "shop_name"]], on="customer_id")
            st.dataframe(
                top_rfm[["customer_id", "shop_name", "rfm_segment_final", "final_customer_score", "recency", "frequency", "monetary", "customer_rank"]],
                use_container_width=True
            )
            
        st.write("#### Detailed Scoring Grid")
        st.dataframe(rfm_scores_df, use_container_width=True)
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(rfm_scores_df, "rfm_scores", "rfm_scores", "rfm_score")
        
    with tab4:
        st.subheader("📅 Blocked Dates & Leave Calendars")
        st.markdown("Solver checks these blocked dates. No scheduled salesperson visit can fall on these dates.")
        
        t_hol = holiday_df[holiday_df["territory_holiday"].notna()]
        s_hol = holiday_df[holiday_df["salesperson_holiday"].notna()]
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("##### 🗺️ Territory Holidays")
            st.dataframe(t_hol[["holiday_id", "territory_holiday", "from_date", "to_date", "reason"]], use_container_width=True)
        with col2:
            st.write("##### 🧑‍💼 Salesperson Leave Schedule")
            st.dataframe(s_hol[["holiday_id", "salesperson_holiday", "from_date", "to_date", "reason"]], use_container_width=True)
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(holiday_df, "holiday_schedule", "holiday", "holiday_sched")

    with tab5:
        st.subheader("🧑‍💼 Salesperson Directory")
        st.dataframe(salesperson_df, use_container_width=True)
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(salesperson_df, "salesperson_directory", "salesperson", "sp_dir")

    with tab6:
        st.subheader("🚐 Fleet Vehicle Roster")
        st.dataframe(van_df, use_container_width=True)
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(van_df, "van_fleet_directory", "van", "van_dir")

    with tab7:
        st.subheader("📊 Historical Visit Log")
        st.markdown(f"Total historical visits: **{len(visit_df)}**")
        st.dataframe(visit_df.head(1000), use_container_width=True)
        st.caption("Showing the first 1,000 rows. Use the buttons below to export the complete dataset.")
        st.markdown("---")
        st.write("##### 📥 Export Directory")
        render_download_buttons(visit_df, "historical_visit_log", "visit", "visit_log")

# ------------------------------------------------------------
# PAGE 2: MONTHLY PLAN GENERATOR
# ------------------------------------------------------------
elif page == "⚡ Monthly Plan Generator":
    st.title("⚡ Monthly Journey Plan Generator")
    st.caption("Generate mathematical schedules on the fly. Utilizes OR-Tools CP-SAT and outputs validation checklist.")
    
    if customer_df is None:
        st.stop()
        
    # Parameter Controls
    st.write("### ⚙️ Solver Configuration Overrides")
    
    # Load default configs
    cfg_vals = config_df.set_index("config_key")["config_value"].to_dict() if config_df is not None else {}
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui_speed = st.slider("Average Route Speed (km/h)", 15, 60, int(cfg_vals.get("avg_speed_kmh", 32)))
    with c2:
        ui_service = st.slider("Average Service Time (min)", 5, 60, int(cfg_vals.get("avg_service_time_min", 22)))
    with c3:
        ui_shift = st.number_input("Salesperson Daily Limit (min)", 120, 600, 480, step=30)
    with c4:
        ui_solve_time = st.slider("Solver Run Time (sec)", 10, 1200, 1200, step=10)
        
    sel_ter = st.selectbox("Run Solver For Territory", ["All Territories"] + list(territory_df["territory_id"].unique()))
    run_month_start = st.date_input("Schedule Month Start Date", datetime(2026, 7, 1))
    
    st.markdown("---")
    
    status = st.session_state["solver_container"]["status"]

    if status == "idle":
        # Run solver button
        if st.button("⚡ Generate Schedule & Optimize Routes", type="primary"):
            config_override = {
                "avg_speed": ui_speed,
                "customer_serving_time": ui_service,
                "salesman_daily_work_minutes": ui_shift
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
                lf.write(f"Month: {month_str}\n\n")
            
            # Start background thread
            container = st.session_state["solver_container"]
            
            def run_thread_job(cnt, speed, s_time, work_min, m_str, t_id, solve_time):
                try:
                    import scheduler_final
                    # Dynamically override the backend solver's hardcoded time limits proportionally
                    scheduler_final.MIN_SOLVER_TIME = max(10, solve_time // 2)
                    scheduler_final.MAX_SOLVER_TIME = solve_time

                    scheduler = MultiSalesManScheduler({
                        "avg_speed": speed,
                        "customer_serving_time": s_time,
                        "salesman_daily_work_minutes": work_min
                    })
                    res = scheduler.create_monthly_schedule(
                        customer_df=customer_df,
                        rfm_scores_df=rfm_scores_df,
                        salesperson_df=salesperson_df,
                        holiday_df=holiday_df,
                        territory_df=territory_df,
                        van_df=van_df,
                        month_start_date=m_str,
                        territory_id=t_id
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
                    ui_solve_time
                )
            )
            t.start()
            st.rerun()
            
        # Display previous results if available in st.session_state
        if st.session_state["latest_plan"] is not None:
            st.markdown("---")
            st.info("💡 **A previously generated plan is available.** Inspect details below or configure options above to build a new one.")

    elif status == "running":
        st.info("⏳ **Optimization Solver is currently running in the background...**")
        elapsed = time.time() - st.session_state["solver_container"]["start_time"]
        st.write(f"Elapsed Time: **{elapsed:.1f} seconds**")
        
        st.write("### 🖥️ OR-Tools CP-SAT Solver Execution Output (Live Log)")
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
        st.success("🎉 **Optimization schedule completed successfully!**")
        st.session_state["latest_plan"] = st.session_state["solver_container"]["result"]
        st.session_state["latest_plan_meta"] = st.session_state["solver_container"]["meta"]
        
        if st.button("🔄 Reset & Build New Plan"):
            st.session_state["solver_container"]["status"] = "idle"
            st.session_state["solver_container"]["result"] = None
            st.session_state["solver_container"]["error"] = None
            st.session_state["solver_container"]["meta"] = None
            st.rerun()

    elif status == "error":
        st.error("❌ **Solver failed with an error during background execution:**")
        st.code(st.session_state["solver_container"]["error"], language="text")
        
        if st.button("🔄 Reset Solver"):
            st.session_state["solver_container"]["status"] = "idle"
            st.session_state["solver_container"]["error"] = None
            st.rerun()

    # Display results if available
    if st.session_state["latest_plan"] is not None:
        res = st.session_state["latest_plan"]
        meta = st.session_state["latest_plan_meta"]
        
        st.write("## 📊 Optimization Results & Validation Checklist")
        st.info(f"Showing schedule details for **{meta['month']}** | Scope: **{meta['territory']}**")
        
        if res.detailed_schedule.empty:
            st.warning("⚠️ No solution schedule returned. The solver might be infeasible. Running failure diagnostics...")
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
                st.error(f"❌ {d}")
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
            
        # Run validation checker
        with st.spinner("Running mathematical validator..."):
            target_t_id = None if meta["territory"] == "All Territories" else meta["territory"]
            import scheduler_final
            val_report = validate_schedule_final(
                result=res,
                customer_df=customer_df,
                salesperson_df=salesperson_df,
                van_df=van_df,
                territory_df=territory_df,
                holiday_df=holiday_df,
                config_df=meta["config"],
                rfm_scores_df=rfm_scores_df,
                month_start=meta["month"],
                territory_id=target_t_id,
                solver_caps=scheduler_final.SEG_CAPS,
                report_caps=scheduler_final.SEG_CAPS
            )
            
        # Render validation checklist
        st.write("### 🔍 Mathematical Constraint Checklist")
        info_check_names = {
            "Min 1 visit per active customer (INFO)",
            "Unvisited customers (0 visits, INFO)",
            "Under-visited customers (<cap, INFO)",
            "Single salesperson per customer",
            "Travel minutes (avg inter-leg, ±5.0 min)",
            "Travel minutes (avg inter-leg, ±5 min)"
        }
        
        for name, violations in val_report.items():
            is_info = any(ic in name for ic in info_check_names)
            card_class = "checklist-card"
            if not violations:
                card_class += " checklist-pass"
                icon = "✅"
                status_text = "PASSED - 0 violations"
            elif is_info:
                card_class += " checklist-info"
                icon = "ℹ️"
                status_text = f"INFORMATIONAL - {len(violations)} items noted"
            else:
                card_class += " checklist-fail"
                icon = "❌"
                status_text = f"VIOLATED - {len(violations)} constraint breaches"
                
            with st.expander(f"{icon} **{name}** — {status_text}"):
                if not violations:
                    st.success("All checks passed for this constraint.")
                else:
                    for v in violations[:15]:
                        st.markdown(f"- {v}")
                    if len(violations) > 15:
                        st.caption(f"...and {len(violations) - 15} more.")
                        
        # Download reports center
        st.write("### 📥 Reports Center")
        c1, c2, c3 = st.columns(3)
        with c1:
            csv_data = res.detailed_schedule.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Download Detailed Schedule (CSV)",
                data=csv_data,
                file_name=f"detailed_schedule_{meta['month']}.csv",
                mime="text/csv",
                use_container_width=True
            )
        with c2:
            st.write("Generating Excel Route summary...")
            # Trigger VRP excel export on user button click
            if st.button("Generate & Download Stop-to-Stop Excel", use_container_width=True):
                filepath = os.path.join(OUTPUT_DIR, f"stop_to_stop_distances.xlsx")
                first_ter = territory_df["territory_id"].iloc[0] if target_t_id is None else target_t_id
                export_stop_to_stop_excel(res, first_ter, meta["month"], filepath)
                with open(filepath, "rb") as f:
                    st.download_button(
                        label="⬇️ Click here to Download Excel Workbook",
                        data=f,
                        file_name=f"VRP_stop_to_stop_{meta['month']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
        with c3:
            st.write("Generating Under-visited report...")
            if st.button("Generate & Download Under-Visited Report", use_container_width=True):
                filepath = os.path.join(OUTPUT_DIR, f"under_visited_report.xlsx")
                export_under_visited_excel(res, filepath, territory_id=target_t_id)
                with open(filepath, "rb") as f:
                    st.download_button(
                        label="⬇️ Click here to Download Excel Report",
                        data=f,
                        file_name=f"Under_visited_report_{meta['month']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

# ------------------------------------------------------------
# PAGE 3: VRP ROUTING & DRIVER MAPS
# ------------------------------------------------------------
elif page == "🗺️ VRP Routing & Driver Maps":
    st.title("🗺️ VRP Routing & Interactive Driver Maps")
    st.caption("Inspect daily trip maps, stop sequence logs, and driver work times.")
    
    if st.session_state["latest_plan"] is None:
        st.warning("⚠️ No generated plan loaded. Please run the monthly solver in the '⚡ Monthly Plan Generator' tab first.")
        st.stop()
        
    res = st.session_state["latest_plan"]
    meta = st.session_state["latest_plan_meta"]
    
    # Active plan info
    st.info(f"Showing maps based on plan run: **{meta['month']}** | Scope: **{meta['territory']}**")
    
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
        avail_dates_str = [d.strftime("%Y-%m-%d") for d in avail_dates]
        sel_d_str = st.selectbox("Select Date of Month", avail_dates_str)
        sel_d = pd.Timestamp(sel_d_str)
    with c3:
        # Filter drivers (salespeople) active on that day
        d_sched = t_sched[t_sched["schedule_date"] == sel_d]
        avail_drivers = sorted(d_sched["sales_id"].unique())
        sel_driver = st.selectbox("Select Driver (Salesperson)", avail_drivers)
        
    st.subheader("🗺️ Route Map")
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
                    warehouse_lng=wh_lng
                )
                display_map(m, key=f"ind_map_{sel_driver}_{sel_d_str}")
        else:
            with st.spinner("Drawing territory map..."):
                m = build_territory_day_map(
                    result=res,
                    territory_id=sel_t,
                    schedule_date=sel_d
                )
                display_map(m, key=f"terr_map_{sel_t}_{sel_d_str}")
    except Exception as e:
        st.error(f"Error drawing map: {e}")
        st.info("Check GPS coordinates or ensure data contains latitude and longitude columns.")
        
    st.markdown("---")
    st.subheader("🧑‍✈️ Driver Daily Schedule & VRP Logs")
    
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
        
        # Display KPIs in clean columns
        kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
        with kpi_col1:
            st.metric("Stops Visited", stops_count)
        with kpi_col2:
            st.metric("Total Route Distance", f"{total_km:.2f} km")
        with kpi_col3:
            driver_info = salesperson_df[salesperson_df["sales_id"] == sel_driver]
            if not driver_info.empty:
                van_id = driver_info["assigned_van"].values[0]
                van_info = van_df[van_df["van_id"] == van_id]
                if not van_info.empty:
                    is_cold = van_info["cold_truck_enabled"].values[0]
                    driver_cat = "Cold-Chain" if is_cold else "Normal-Chain"
                else:
                    driver_cat = "Normal-Chain"
            else:
                driver_cat = "N/A"
            st.metric("Driver Category", driver_cat)

        # Columns for side-by-side tables
        c_tbl1, c_tbl2 = st.columns(2)
        
        with c_tbl1:
            st.write("##### 📋 Stop Order List")
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
            st.dataframe(pd.DataFrame(stops_log), use_container_width=True, hide_index=True)
            
        with c_tbl2:
            st.write("##### 🚐 VRP Stop-to-Stop Distance Table")
            dist_tbl = build_stop_to_stop_distance_table(res, sel_t, sel_d, sel_driver)
            if not dist_tbl.empty:
                st.dataframe(
                    dist_tbl[["stop_from", "stop_to", "from_shop", "to_shop", "leg_km", "leg_min"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No detailed VRP routing table available for this driver on this day.")

# ------------------------------------------------------------
# PAGE 4: EXECUTIVE VISUALIZATION & ANALYTICS
# ------------------------------------------------------------
elif page == "📈 Executive Visualization & Analytics":
    st.title("📈 Executive Visualization & Analytics")
    st.caption("Visual dashboard for master registries and active journey optimization plan metrics.")
    
    if customer_df is None:
        st.stop()
        
    plan_generated = st.session_state["latest_plan"] is not None
    
    # Create two tabs for cleaner UX
    tab_master, tab_plan = st.tabs(["📊 Master Registry Analytics", "⚡ Optimized Route Plan Analytics"])
    
    # ------------------------------------------------------------
    # TAB 1: MASTER REGISTRY ANALYTICS
    # ------------------------------------------------------------
    with tab_master:
        st.write("## 🗃️ Master Data Registry Insights")
        
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
                st.write("##### 📊 Outlet Volume Tier Breakdown by Territory")
                st.bar_chart(t_tier, use_container_width=True)
            with col_c2:
                st.write("##### 🔄 Customer Lifecycle States by Territory")
                st.bar_chart(t_life, use_container_width=True)
                
            col_c3, col_c4 = st.columns(2)
            with col_c3:
                st.write("##### 🛡️ RFM Combined Segments Distribution")
                st.bar_chart(rfm_counts, use_container_width=True)
            with col_c4:
                st.write("##### ❄️ Cold-Chain Truck Requirements by Territory")
                st.bar_chart(cold_share, use_container_width=True)
                
    # ------------------------------------------------------------
    # TAB 2: OPTIMIZED ROUTE PLAN ANALYTICS
    # ------------------------------------------------------------
    with tab_plan:
        st.write("## ⚡ Optimization & Route Plan Metrics")
        
        if not plan_generated:
            st.markdown(
                """
                <div class="stat-card" style="border-left: 5px solid #F5A623; background-color: #FFFDF5; padding: 2rem;">
                    <h3 style="color: #D97706 !important; margin-top: 0;">⚠️ Route Plan Data Not Available</h3>
                    <p style="color: #451A03; font-size: 1.05rem;">
                        A monthly optimization plan has not yet been generated in this session.
                    </p>
                    <p style="color: #78350F; font-size: 0.95rem; margin-bottom: 1.5rem;">
                        To analyze route layouts, drive distances, service hours, and salesperson workloads:
                    </p>
                    <ol style="color: #78350F; font-size: 0.95rem; margin-left: 1.5rem; margin-bottom: 0;">
                        <li>Navigate to the <b>⚡ Monthly Plan Generator</b> tab.</li>
                        <li>Verify/adjust your speed, service time, and solver limits.</li>
                        <li>Click <b>⚡ Generate Schedule & Optimize Routes</b> to run the OR-Tools solver.</li>
                    </ol>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            res = st.session_state["latest_plan"]
            meta = st.session_state["latest_plan_meta"]
            
            st.success(f"📊 Displaying active plan visualizations for: **{meta['month']}** | Scope: **{meta['territory']}**")
            
            # Extract scheduler stats
            detailed = res.detailed_schedule
            
            # Determine the subset of customers involved in this plan
            if meta["territory"] != "All Territories":
                t_cust_df = customer_df[customer_df["territory_id"] == meta["territory"]]
            else:
                t_cust_df = customer_df
                
            total_custs = len(t_cust_df)
            unvisited_custs = len(res.unvisited_customers)
            visited_custs = max(0, total_custs - unvisited_custs)
            
            # Coverage metrics row
            p_m1, p_m2, p_m3 = st.columns(3)
            with p_m1:
                st.metric("Total Scheduled Visits", len(detailed))
            with p_m2:
                st.metric("Store Coverage Ratio", f"{visited_custs} / {total_custs} outlets", f"{visited_custs/total_custs*100:.1f}%" if total_custs > 0 else "0.0%")
            with p_m3:
                total_dist = detailed["route_leg_km"].sum() if "route_leg_km" in detailed.columns else 0.0
                st.metric("Total Mileage Allotted", f"{total_dist:,.1f} km")
                
            # Group by salesperson to show estimated workload
            cfg_vals = config_df.set_index("config_key")["config_value"].to_dict() if config_df is not None else {}
            service_time_min = int(float(cfg_vals.get("avg_service_time_min", 22)))
            avg_speed = float(cfg_vals.get("avg_speed_kmh", 32))
            
            # service minutes per salesperson
            sp_service = detailed.groupby("sales_id").size().reset_index(name="service_min")
            sp_service["service_min"] = sp_service["service_min"] * service_time_min
            
            if "route_leg_km" in detailed.columns:
                sp_travel = detailed.groupby("sales_id")["route_leg_km"].sum().reset_index(name="travel_min")
                sp_travel["travel_min"] = (sp_travel["travel_min"] / avg_speed * 60).round(1)
                sp_dist = detailed.groupby("sales_id")["route_leg_km"].sum().reset_index(name="distance_km")
            else:
                sp_travel = pd.DataFrame(columns=["sales_id", "travel_min"])
                sp_dist = pd.DataFrame(columns=["sales_id", "distance_km"])
                sp_dist["distance_km"] = 0.0
                
            sp_visits = detailed.groupby("sales_id").size().reset_index(name="visits")
            
            # Merge all salesperson metrics
            sp_metrics = sp_service.merge(sp_travel, on="sales_id", how="outer")
            sp_metrics = sp_metrics.merge(sp_dist, on="sales_id", how="outer")
            sp_metrics = sp_metrics.merge(sp_visits, on="sales_id", how="outer").fillna(0.0)
            sp_metrics["total_workload"] = sp_metrics["service_min"] + sp_metrics["travel_min"]
            
            work_summary = sp_metrics.rename(columns={
                "sales_id": "Salesperson ID",
                "service_min": "Total Service Time (min)",
                "travel_min": "Total Travel Time (min)",
                "total_workload": "Total Workload (min)",
                "distance_km": "Total Distance (km)",
                "visits": "Scheduled Visits"
            }).set_index("Salesperson ID")
            
            st.write("### 🧑‍✈️ Multi-Dimensional Salesperson Performance Dashboard")
            
            if has_plotly:
                # Build the unified Plotly Subplot
                fig_sp = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.15,
                    subplot_titles=(
                        "⏳ Cumulative Monthly Time Allocation (Minutes)",
                        "📈 Route Density (Visits Scheduled) vs. Total Travel Distance (km)"
                    ),
                    specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
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

                # Row 2 Bar Chart trace for Visits
                fig_sp.add_trace(
                    go.Bar(
                        x=sp_metrics["sales_id"],
                        y=sp_metrics["visits"],
                        name="Visits Scheduled (cnt)",
                        marker_color="#3B82F6",
                        hovertemplate="Salesperson: %{x}<br>Visits: %{y}<extra></extra>"
                    ),
                    row=2, col=1,
                    secondary_y=False
                )

                # Row 2 Scatter trace for Distance
                fig_sp.add_trace(
                    go.Scatter(
                        x=sp_metrics["sales_id"],
                        y=sp_metrics["distance_km"],
                        name="Travel Distance (km)",
                        mode="lines+markers",
                        line=dict(color="#EF4444", width=3),
                        marker=dict(size=8),
                        hovertemplate="Salesperson: %{x}<br>Distance: %{y:.1f} km<extra></extra>"
                    ),
                    row=2, col=1,
                    secondary_y=True
                )

                fig_sp.update_layout(
                    height=700,
                    barmode="group",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    template="plotly_white",
                    margin=dict(t=30, b=30, l=30, r=30)
                )

                fig_sp.update_yaxes(title_text="Minutes", row=1, col=1)
                fig_sp.update_yaxes(title_text="Scheduled Visits", row=2, col=1, secondary_y=False)
                fig_sp.update_yaxes(title_text="Distance (km)", row=2, col=1, secondary_y=True)
                fig_sp.update_xaxes(title_text="Salesperson ID", row=2, col=1)
                
                st.plotly_chart(fig_sp, use_container_width=True)
            else:
                # Fallback to standard streamlit bar charts
                st.write("##### ⏳ Workload (Service vs Travel Time)")
                st.bar_chart(work_summary[["Total Service Time (min)", "Total Travel Time (min)"]], use_container_width=True)
                st.write("##### 📈 Scheduled Visits & Route Distance")
                st.bar_chart(work_summary[["Scheduled Visits", "Total Distance (km)"]], use_container_width=True)
                
            st.markdown("---")
            st.write("### 📅 Detailed Daily Load & Customer Analysis")
            
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
                fig_daily.update_layout(
                    title="Daily Workload Distribution (Visits vs Distance)",
                    yaxis=dict(title="Scheduled Visits"),
                    yaxis2=dict(title="Distance (km)", overlaying="y", side="right"),
                    xaxis=dict(title="Date", tickangle=-45),
                    legend=dict(orientation="h", y=1.1, x=0),
                    template="plotly_white",
                    height=400,
                    margin=dict(t=40, b=30, l=30, r=30)
                )
                st.plotly_chart(fig_daily, use_container_width=True)
            else:
                daily_load = daily_load.set_index("schedule_date")
                st.write("##### 📅 Daily Schedule Load (Visits per Day)")
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
                    fig_coverage.update_layout(
                        title="🎯 Active Store Coverage Ratio",
                        annotations=[dict(text=f"{visited_custs/total_custs*100:.1f}%" if total_custs > 0 else "0%", x=0.5, y=0.5, font_size=20, showarrow=False)],
                        showlegend=True,
                        height=350,
                        margin=dict(t=40, b=0, l=0, r=0)
                    )
                    st.plotly_chart(fig_coverage, use_container_width=True)
                else:
                    st.write("##### 🎯 Store Coverage Share")
                    cov_df = pd.DataFrame([{"Status": "Visited", "Count": visited_custs}, {"Status": "Unvisited", "Count": unvisited_custs}]).set_index("Status")
                    st.bar_chart(cov_df, use_container_width=True)
                    
            with col_p4:
                if has_plotly:
                    # 4. Visits Allocated by RFM Segment
                    segment_visits = detailed.groupby("rfm_segment_final").size().reset_index(name="visits")
                    fig_seg_visits = go.Figure(data=[go.Bar(
                        x=segment_visits["rfm_segment_final"],
                        y=segment_visits["visits"],
                        marker_color=["#10B981", "#3B82F6", "#F5A623", "#EF4444"][:len(segment_visits)]
                    )])
                    fig_seg_visits.update_layout(
                        title="⚡ Visits Allocated by Customer RFM Segment",
                        xaxis_title="RFM Segment",
                        yaxis_title="Scheduled Visits",
                        template="plotly_white",
                        height=350,
                        margin=dict(t=40, b=30, l=30, r=30)
                    )
                    st.plotly_chart(fig_seg_visits, use_container_width=True)
                else:
                    st.write("##### ⚡ Visits Allocated by Customer RFM Segment")
                    segment_visits = detailed.groupby("rfm_segment_final").size()
                    st.bar_chart(segment_visits, use_container_width=True)
                    
            st.markdown("---")
            st.write("### 🧑‍✈️ Salesperson Workload Table")
            st.dataframe(work_summary, use_container_width=True)

# ------------------------------------------------------------
# PAGE 5: GLOBAL CONFIGURATION SETTINGS
# ------------------------------------------------------------
elif page == "⚙️ Global Configuration Settings":
    st.title("⚙️ Global Configuration Settings")
    st.caption("View and edit route planning coefficients, shift limits, and fleet details dynamically.")
    
    if config_df is None:
        st.stop()
        
    tab1, tab2 = st.tabs(["🔧 Config Parameters Editor", "🚚 Driver & Fleet Directory"])
    
    with tab1:
        if "config_save_success" in st.session_state:
            st.success(st.session_state["config_save_success"])
            del st.session_state["config_save_success"]

        st.subheader("🔧 Active Global Configuration Coefficient List")
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
                
            submitted = st.form_submit_button("💾 Save Settings (CSV & jp_data.xlsx)")
            
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
                    {"config_key": "segment_cap_low", "config_value": str(cap_low)}
                ])
                save_config_csv(new_cfg)
                
                # Apply dynamic Segment Cap updates in scheduler memory
                import scheduler_final
                scheduler_final.SEG_CAPS = {"High": cap_high, "Medium": cap_med, "Low": cap_low}
                
                # Save success message in session state and rerun
                st.session_state["config_save_success"] = f"Configurations persistently saved! Solver runtime caps updated: High={cap_high}, Med={cap_med}, Low={cap_low}"
                st.rerun()
                
    with tab2:
        st.subheader("🧑‍💼 Salesperson Roster")
        st.dataframe(salesperson_df, use_container_width=True)
        
        st.subheader("🚐 Fleet Vehicle Roster")
        st.dataframe(van_df, use_container_width=True)
