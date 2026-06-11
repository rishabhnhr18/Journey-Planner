# Journey Planner Streamlit UI Walkthrough

We have designed and built a professional, premium-grade Streamlit web control center at [app.py](file:///D:/Data/Science/Basamh/JP_Yash/journey-planner/code/final/app.py) that integrates directly with the Journey Planner backend solver and validator scripts.

Here is a summary of the implementation:

## Key Features Built

### 1. Modern Premium Aesthetics
- Injecting a clean, custom CSS styling framework with modern stat cards, soft gradients, and customized badge systems.
- Using harmonic status colors (Red/Amber/Grey/Green) rather than default plain styles for all customer segments, lifecycle statuses, and constraint validation items.

### 2. Live Solver Progress & Logging Console
- Truncates and tails the OR-Tools CP-SAT `solver_log.txt` in a separate background thread.
- Streams the solver log output directly into a live, scrolling terminal code box on the Streamlit dashboard as the optimization executes.
- Prevents UI freezing/timeout while the solver is active.

### 3. Page 1: Overview & Master Data Explorer
- Displays high-level KPIs (Total Outlets, Cold-chain, Credit Ratio, Total monetary value).
- Provides directory tables with filters for Territory, Volume Tier, Cold-chain requirements, and Lifecycle status.
- Integrates segment score grids, RFM segment distributions, and salesperson/territory holiday dates.

### 4. Page 2: Monthly Plan Generator (On-the-Fly Optimization)
- Allows adjusting route speeds, service minutes, daily shift limits, and solver runtime limits.
- Features a single "⚡ Generate Schedule & Optimize Routes" action button.
- Dynamically executes the solver, validates the resulting plan against standard constraints, and renders a checklist (green checks for passed checks, orange info badges for informational notices).
- Displays warning diagnostics if the solver returns infeasible outcomes.
- Contains direct download buttons for the detailed CSV schedule, the VRP stop-to-stop Excel sheet, and the under-visited report.

### 5. Page 3: Daily VRP Routing & Interactive Maps
- Filters routes by Territory, Date, Salesperson, and Truck Group.
- Draws maps using `folium`:
  - **Individual Salesperson Map**: Shows stops numbered in VRP sequence starting from the warehouse.
  - **Territory Map**: Overlays all salespeople routes simultaneously with distinct colors and directional arrows.
- Renders the Daily Stop-to-Stop Distance grid and VRP leg tables.
- Implements a robust HTML iframe fallback in case `streamlit_folium` is missing or fails.

### 6. Page 4: Configuration & Fleet Settings
- Form editor to adjust `config.csv` coefficients on the fly, save updates, and read them in subsequent optimization cycles.
- Roster tables for active salespeople and vans.

### 7. Asynchronous Thread State Preservation & Navigation Lock
- Solver state is stored in a session-safe `dict` wrapper. Even if the user closes the page or switches tabs, the background thread keeps executing OR-Tools CP-SAT and streams logs into `solver_log.txt`.
- When an optimization run is active, the sidebar navigation is locked to the Generator page and other options are disabled, preventing users from disrupting the flow midway.

### 8. Dynamic Configuration Synchronization & Immediate UI Rerun
- **Persistent RFM Segment Caps**: Added storage keys (`segment_cap_high`, `segment_cap_medium`, `segment_cap_low`) inside `config.csv` and the `config` sheet of `jp_data.xlsx` to prevent the UI from resetting to defaults (15, 6, 4) on page navigation.
- **Dynamic Overrides**: Overrides `scheduler_final.SEG_CAPS` and passes adjusted limits to `validate_schedule_final` at execution runtime.
- **Instant UI Refresh**: Integrated `st.session_state` banners and an immediate `st.rerun()` to reload and render settings seamlessly once submitted.

---

## Running the Application

To start the Streamlit control room:

1. Open a terminal and navigate to the directory `D:\Data Science\Basamh\JP_Yash\journey-planner`.
2. Activate your virtual environment and launch Streamlit:
   ```bash
   .venv\Scripts\activate
   streamlit run code\final\app.py
   ```
3. Open the local address in your browser (usually `http://localhost:8501`).
