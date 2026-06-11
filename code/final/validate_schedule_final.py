"""
validate_schedule_final.py
───────────────────────────────────────────────────────────────────────
Validates the monthly schedule produced by MultiSalesManScheduler in scheduler_final.py.

Key checks implemented:
 1. Cold truck requirement: Cold-truck customers must only be visited by cold-capable salesperson.
 2. Active customers: Active customer must have >= 1 visit (informational).
 3. Max visits/month by segment: High <= 30, Medium <= 15, Low <= 10.
 4. Single salesperson per customer (assignment consistency).
 5. Daily customer count limit: based on daily time capacity.
 6. Daily total time limit: route_leg_km-based daily time <= daily_work_minutes.
 7. Holiday blocking: No visits on territory or salesperson holidays.
 8. Visit minutes accuracy: estimated_visit_minutes == customer_serving_time.
 9. Travel minutes accuracy: estimated_travel_minutes within tolerance.
10. Route leg km accuracy: route_leg_km matches haversine from previous stop.
11. Cumulative route km non-decreasing along route_rank.
12. Date range: all dates fall within the requested month.
13. Cold / Normal plans disjoint (no shared customer_id).
14. Unvisited customers (0 visits - informational).
15. Under-visited customers (< target cap visits - informational).
"""

import math
import numpy as np
import pandas as pd
from collections import defaultdict

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONFIGURATION CONSTANTS (synchronized with scheduler_final.py)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_SOLVER_CAPS = {"High": 20, "Medium": 11, "Low": 5}
DEFAULT_REPORT_CAPS = {"High": 20, "Medium": 11, "Low": 5} # Matches SEG_CAPS in scheduler_final.py

TRAVEL_LEG_TOLERANCE_MIN = 5.0
TREAT_TRAVEL_MIN_AS_INFO = True  # Check 9 is informational
LEG_KM_TOLERANCE_M = 500.0       # 500m tolerance for haversine accuracy

# ─────────────────────────────────────────────────────────────────────────────
# Helper functions
# ─────────────────────────────────────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R    = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = (math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ─────────────────────────────────────────────────────────────────────────────
# Main validator function
# ─────────────────────────────────────────────────────────────────────────────
def validate_schedule_final(
    result,
    customer_df:     pd.DataFrame,
    salesperson_df:  pd.DataFrame,
    van_df:          pd.DataFrame,
    territory_df:    pd.DataFrame,
    holiday_df:      pd.DataFrame,
    config_df:       pd.DataFrame | dict,
    rfm_scores_df:   pd.DataFrame = None,
    month_start:     str          = "2026-07-01",
    territory_id:    str          = None,   # None -> validate all
    solver_caps:     dict         = None,
    report_caps:     dict         = None,
) -> dict:
    """
    Validates all constraints against the scheduler_final.py output.
    """
    detailed = result.detailed_schedule.copy() if hasattr(result, "detailed_schedule") else pd.DataFrame()
    if detailed.empty:
        print("No schedule generated – nothing to validate.")
        return {}

    # ── Territory filter ──────────────────────────────────────────────────────
    if territory_id is not None:
        detailed = detailed[detailed["territory_id"] == territory_id].copy()
        if detailed.empty:
            print(f"No schedule found for territory '{territory_id}'.")
            return {}

    detailed["schedule_date"] = pd.to_datetime(detailed["schedule_date"])

    # ── Enrich with customer master ───────────────────────────────────────────
    cust_cols = ["customer_id", "cold_truck_required", "lifecycle_state",
                 "gps_lat", "gps_lng", "territory_id"]
    cust_cols_present = [c for c in cust_cols if c in customer_df.columns]
    detailed = detailed.merge(
        customer_df[cust_cols_present], on="customer_id", how="left",
        suffixes=("", "_cust")
    )
    # Prefer schedule copy of coordinates
    for col in ("gps_lat", "gps_lng", "cold_truck_required", "lifecycle_state"):
        if f"{col}_cust" in detailed.columns:
            detailed[col] = detailed[col].combine_first(detailed[f"{col}_cust"])
            detailed.drop(columns=[f"{col}_cust"], inplace=True, errors="ignore")

    # ── RFM segment ───────────────────────────────────────────────────────────
    if "rfm_segment_final" not in detailed.columns and rfm_scores_df is not None:
        rfm = rfm_scores_df[["customer_id", "rfm_segment_final"]].copy()
        detailed = detailed.merge(rfm, on="customer_id", how="left")
    detailed["rfm_segment_final"] = detailed.get(
        "rfm_segment_final", pd.Series("Low", index=detailed.index)
    ).fillna("Low")

    # ── SP cold capability ────────────────────────────────────────────────────
    van_cold = van_df.set_index("van_id")["cold_truck_enabled"].to_dict() if not van_df.empty else {}
    salesperson_df = salesperson_df.copy()
    salesperson_df["cold_capable"] = (
        salesperson_df["assigned_van"].map(van_cold).fillna(False)
    )
    sp_cold = salesperson_df.set_index("sales_id")["cold_capable"].to_dict()
    detailed["salesperson_cold_capable"] = detailed["sales_id"].map(sp_cold)

    # ── Territory warehouse coords ────────────────────────────────────────────
    ter_wh = (
        territory_df
        .set_index("territory_id")[["warehouse_lat", "warehouse_lng"]]
        .to_dict("index")
        if not territory_df.empty else {}
    )
    detailed["warehouse_lat"] = detailed["territory_id"].apply(
        lambda tid: ter_wh.get(tid, {}).get("warehouse_lat", 0)
    )
    detailed["warehouse_lng"] = detailed["territory_id"].apply(
        lambda tid: ter_wh.get(tid, {}).get("warehouse_lng", 0)
    )

    # ── Config ────────────────────────────────────────────────────────────────
    if isinstance(config_df, pd.DataFrame):
        cfg = (
            config_df.set_index("config_key")["config_value"].to_dict()
            if not config_df.empty else {}
        )
    else:
        cfg = config_df if config_df else {}

    avg_visit_min  = int(float(cfg.get("customer_serving_time", 22)))
    avg_speed_kmh  = float(cfg.get("avg_speed", 32))
    daily_work_min = int(cfg.get("salesman_daily_work_minutes", 480))

    # ── Caps ──────────────────────────────────────────────────────────────────
    _solver_caps = solver_caps if solver_caps is not None else DEFAULT_SOLVER_CAPS
    _report_caps = report_caps if report_caps is not None else DEFAULT_REPORT_CAPS

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 1: Cold-truck customers → cold-capable salesperson
    # ─────────────────────────────────────────────────────────────────────────
    cold_violations = []
    cold_rows = detailed[detailed.get("cold_truck_required", pd.Series(False)) == True] \
        if "cold_truck_required" in detailed.columns else pd.DataFrame()
    for _, row in cold_rows.iterrows():
        if not row.get("salesperson_cold_capable", False):
            cold_violations.append(
                f"Customer {row['customer_id']} (cold) assigned to "
                f"{row['sales_id']} (not cold-capable)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 2: Unvisited active customers (informational — not a hard constraint)
    # ─────────────────────────────────────────────────────────────────────────
    active_custs = customer_df[
        ~customer_df["lifecycle_state"].isin(["Churned", "Dormant"])
    ].copy() if "lifecycle_state" in customer_df.columns else customer_df.copy()
    
    if territory_id and "territory_id" in active_custs.columns:
        active_custs = active_custs[active_custs["territory_id"] == territory_id]

    visited_cust   = set(detailed["customer_id"].unique())
    missing_active = set(active_custs["customer_id"]) - visited_cust
    min_visit_viol = [
        f"[INFO] Active customer {cid} has 0 visits "
        f"(capacity overflow — not a constraint breach)"
        for cid in missing_active
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 3: Max visits/month by segment (High <= 30, Medium <= 15, Low <= 10)
    # ─────────────────────────────────────────────────────────────────────────
    visit_counts  = detailed.groupby("customer_id").size()
    max_visit_viol = []
    for cid, cnt in visit_counts.items():
        customer_rows = detailed[detailed["customer_id"] == cid]
        if customer_rows.empty:
            continue
        seg = customer_rows.iloc[0]["rfm_segment_final"]
        if "visit_cap" in customer_rows.columns:
            max_all = int(customer_rows.iloc[0]["visit_cap"])
        else:
            max_all = _solver_caps.get(seg, 10)
        if cnt > max_all:
            max_visit_viol.append(
                f"Customer {cid} ({seg}) has {cnt} visits, max allowed {max_all}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 4: Single salesperson per customer (assignment consistency)
    # ─────────────────────────────────────────────────────────────────────────
    assign_viol = []
    for cid, grp in detailed.groupby("customer_id"):
        unique_sps = grp["sales_id"].unique()
        if len(unique_sps) > 1:
            assign_viol.append(
                f"Customer {cid} visited by multiple salespeople: {list(unique_sps)}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 5: Daily customer count ≤ capacity
    # ─────────────────────────────────────────────────────────────────────────
    daily_cap_viol = []
    grouped = detailed.groupby(["sales_id", "schedule_date"])

    is_osrm = hasattr(result, "osrm_helper") and result.osrm_helper is not None and result.osrm_helper.mode != "haversine"

    for (sid, date), grp in grouped:
        n_cust = len(grp)

        if is_osrm and "estimated_travel_minutes" in grp.columns and grp["estimated_travel_minutes"].notna().all():
            avg_inter_min = float(grp["estimated_travel_minutes"].mean())
        elif ("route_leg_km" in grp.columns and grp["route_leg_km"].notna().all()
                and n_cust > 1):
            avg_inter_min = float((grp["route_leg_km"] / avg_speed_kmh * 60).mean())
        elif "estimated_travel_minutes" in grp.columns:
            avg_inter_min = float(grp["estimated_travel_minutes"].mean())
        else:
            wh_lat = grp.iloc[0]["warehouse_lat"]
            wh_lng = grp.iloc[0]["warehouse_lng"]
            legs = [
                haversine_km(wh_lat, wh_lng, row["gps_lat"], row["gps_lng"])
                for _, row in grp.iterrows()
            ]
            avg_inter_min = float(np.mean(legs)) / avg_speed_kmh * 60 if legs else 0.0

        tpv = avg_visit_min + avg_inter_min
        cap = max(1, int(daily_work_min / max(tpv, 1)))

        if n_cust > cap:
            daily_cap_viol.append(
                f"{sid} on {date.date()}: {n_cust} customers, "
                f"capacity={cap} "
                f"(visit={avg_visit_min} min, avg_leg={avg_inter_min:.1f} min, "
                f"tpv={tpv:.1f} min, budget={daily_work_min} min)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 6: Daily total time ≤ daily_work_minutes
    # ─────────────────────────────────────────────────────────────────────────
    time_viol = []
    for (sid, date), grp in grouped:
        service_t = len(grp) * avg_visit_min

        if is_osrm and "estimated_travel_minutes" in grp.columns and grp["estimated_travel_minutes"].notna().all():
            travel_t = float(grp["estimated_travel_minutes"].sum())
        elif ("route_leg_km" in grp.columns and grp["route_leg_km"].notna().all()):
            travel_t = float(grp["route_leg_km"].sum() / avg_speed_kmh * 60)
        elif "estimated_travel_minutes" in grp.columns:
            travel_t = float(grp["estimated_travel_minutes"].sum())
        else:
            travel_t = 0.0

        total_t = service_t + travel_t
        if total_t > daily_work_min + 0.5:   # 0.5-min tolerance for rounding
            time_viol.append(
                f"{sid} on {date.date()}: total={total_t:.1f} min "
                f"(service={service_t} + travel={travel_t:.1f}) > "
                f"{daily_work_min} min"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 7: Holiday violations
    # ─────────────────────────────────────────────────────────────────────────
    holiday_viol = []
    if not holiday_df.empty:
        ter_blocked: dict[str, set] = defaultdict(set)
        sp_blocked:  dict[str, set] = defaultdict(set)
        hdf = holiday_df.copy()
        hdf["from_date"] = pd.to_datetime(hdf["from_date"]).dt.normalize()
        hdf["to_date"]   = pd.to_datetime(hdf["to_date"]).dt.normalize()
        for _, row in hdf.iterrows():
            dr = pd.date_range(row["from_date"], row["to_date"])
            if pd.notna(row.get("territory_holiday")):
                ter_blocked[row["territory_holiday"]].update(dr)
            if pd.notna(row.get("salesperson_holiday")):
                sp_blocked[row["salesperson_holiday"]].update(dr)
        for _, row in detailed.iterrows():
            d   = row["schedule_date"].normalize()
            tid = row["territory_id"]
            sid = row["sales_id"]
            if d in ter_blocked.get(tid, set()):
                holiday_viol.append(
                    f"Visit on territory holiday: {tid} on {d.date()} "
                    f"(SP={sid}, customer={row['customer_id']})"
                )
            if d in sp_blocked.get(sid, set()):
                holiday_viol.append(
                    f"Visit on salesperson holiday: {sid} on {d.date()} "
                    f"(customer={row['customer_id']})"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 8: estimated_visit_minutes == customer_serving_time
    # ─────────────────────────────────────────────────────────────────────────
    visit_min_viol = []
    if "estimated_visit_minutes" in detailed.columns:
        bad = detailed[detailed["estimated_visit_minutes"] != avg_visit_min]
        for _, row in bad.iterrows():
            visit_min_viol.append(
                f"Customer {row['customer_id']} on {row['sales_id']}: "
                f"estimated_visit_minutes={row['estimated_visit_minutes']} "
                f"≠ {avg_visit_min}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 9: estimated_travel_minutes ≈ avg inter-customer leg (±5 min)
    # ─────────────────────────────────────────────────────────────────────────
    travel_viol = []
    if ("estimated_travel_minutes" in detailed.columns
            and "route_leg_km" in detailed.columns):
        for (sid, date), grp in grouped:
            if grp["route_leg_km"].isna().all() or len(grp) < 2:
                continue
            actual_avg_leg_min = float(
                (grp["route_leg_km"].dropna() / avg_speed_kmh * 60).mean()
            )
            stored = float(grp["estimated_travel_minutes"].iloc[0])
            if abs(stored - actual_avg_leg_min) > TRAVEL_LEG_TOLERANCE_MIN:   # configurable tolerance
                travel_viol.append(
                    f"{sid} on {date.date()}: stored estimated_travel_minutes="
                    f"{stored:.1f} min, day avg_leg={actual_avg_leg_min:.1f} min "
                    f"(diff={abs(stored - actual_avg_leg_min):.1f} min)"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 10: route_leg_km accuracy (OSRM distance if active, else haversine ± 500 m)
    # ─────────────────────────────────────────────────────────────────────────
    leg_viol = []
    if "route_leg_km" in detailed.columns and "route_rank" in detailed.columns:
        for (sid, date), grp in detailed.groupby(["sales_id", "schedule_date"]):
            wh_lat_v = grp.iloc[0]["warehouse_lat"]
            wh_lng_v = grp.iloc[0]["warehouse_lng"]
            grp_sorted = grp.sort_values("route_rank")
            
            # Use OSRM table matrices if OSRM is enabled to get exact road distance
            dist_matrix = None
            if is_osrm:
                coords = [(wh_lat_v, wh_lng_v)]
                for _, row in grp_sorted.iterrows():
                    coords.append((float(row["gps_lat"]), float(row["gps_lng"])))
                
                osrm_data = result.osrm_helper.get_table(coords)
                if osrm_data and "distances" in osrm_data:
                    dist_matrix = osrm_data["distances"]

            prev_lat, prev_lng = wh_lat_v, wh_lng_v
            for idx, (_, row) in enumerate(grp_sorted.iterrows()):
                stored_leg = row.get("route_leg_km", 0.0) or 0.0
                
                if dist_matrix is not None and idx + 1 < len(dist_matrix):
                    # Distance from node idx (previous stop) to node idx + 1 (current stop) in km
                    # Index 0 in dist_matrix is warehouse, so 1st stop is index 1
                    dist_val = dist_matrix[idx][idx + 1]
                    expected_leg = dist_val / 1000.0 if dist_val is not None else 0.0
                else:
                    expected_leg = haversine_km(
                        prev_lat, prev_lng, row["gps_lat"], row["gps_lng"]
                    )
                
                if abs(stored_leg - expected_leg) > LEG_KM_TOLERANCE_M / 1000.0:   # configurable tolerance
                    leg_viol.append(
                        f"{sid}/{date.date()} stop#{int(row['route_rank'])}: "
                        f"stored={stored_leg:.3f} km, expected={expected_leg:.3f} km "
                        f"(diff={abs(stored_leg - expected_leg):.3f} km)"
                    )
                prev_lat = float(row["gps_lat"])
                prev_lng = float(row["gps_lng"])

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 11: cumulative_route_km is non-decreasing along route_rank
    # ─────────────────────────────────────────────────────────────────────────
    cumulative_viol = []
    if ("cumulative_route_km" in detailed.columns
            and "route_rank" in detailed.columns):
        for (sid, date), grp in detailed.groupby(["sales_id", "schedule_date"]):
            grp_sorted = grp.sort_values("route_rank")
            prev_cum = -1.0
            for _, row in grp_sorted.iterrows():
                cum = row.get("cumulative_route_km", 0.0) or 0.0
                if cum < prev_cum - 0.01:
                    cumulative_viol.append(
                        f"{sid}/{date.date()} stop#{int(row['route_rank'])}: "
                        f"cumulative_km decreased ({prev_cum:.3f} → {cum:.3f})"
                    )
                prev_cum = cum

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 12: All schedule_date values within the requested month
    # ─────────────────────────────────────────────────────────────────────────
    month_start_dt = pd.Timestamp(month_start).normalize()
    month_end_dt   = (month_start_dt + pd.offsets.MonthEnd(0)).normalize()
    out_of_range   = detailed[
        (detailed["schedule_date"] < month_start_dt) |
        (detailed["schedule_date"] > month_end_dt)
    ]
    date_viol = [
        f"Visit on {d.date()} is outside month "
        f"({month_start_dt.date()} – {month_end_dt.date()})"
        for d in out_of_range["schedule_date"].unique()
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 13: cold_schedule and normal_schedule are disjoint
    # ─────────────────────────────────────────────────────────────────────────
    disjoint_viol = []
    if "truck_group" in detailed.columns:
        cold_ids   = set(result.cold_schedule["customer_id"].unique()) if hasattr(result, "cold_schedule") and not result.cold_schedule.empty else set()
        normal_ids = set(result.normal_schedule["customer_id"].unique()) if hasattr(result, "normal_schedule") and not result.normal_schedule.empty else set()
        overlap    = cold_ids & normal_ids
        if overlap:
            disjoint_viol.append(
                f"{len(overlap)} customer(s) appear in BOTH cold and normal plans: "
                f"{list(overlap)[:5]}"
                + (f" …+{len(overlap)-5} more" if len(overlap) > 5 else "")
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 14: Unvisited customers (0 visits — capacity overflow)
    # ─────────────────────────────────────────────────────────────────────────
    unvisited_viol = []
    if hasattr(result, "unvisited_customers") and not result.unvisited_customers.empty:
        uv = result.unvisited_customers.copy()
        if territory_id and "territory_id" in uv.columns:
            uv = uv[uv["territory_id"] == territory_id]
        for _, row in uv.iterrows():
            unvisited_viol.append(
                f"[INFO] Customer {row['customer_id']}  "
                f"[{row.get('rfm_segment_final', '?')}]  "
                f"{row.get('shop_name', '')}  "
                f"({row.get('territory_id', '')})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 15: Under-visited customers (>0 but < target segment cap)
    # ─────────────────────────────────────────────────────────────────────────
    under_visited_viol = []
    if hasattr(result, "under_visited_customers") and not result.under_visited_customers.empty:
        uv = result.under_visited_customers.copy()
        if territory_id and "territory_id" in uv.columns:
            uv = uv[uv["territory_id"] == territory_id]
        for _, row in uv.iterrows():
            cap     = int(row.get("visit_cap", _report_caps.get(row.get("rfm_segment_final", "Low"), 10)))
            actual  = int(row.get("actual_visits", 0))
            gap     = int(row.get("visits_gap", cap - actual))
            under_visited_viol.append(
                f"[INFO] Customer {row['customer_id']}  "
                f"[{row.get('rfm_segment_final', '?')}]  "
                f"{row.get('shop_name', '')}  "
                f"visits={actual}/{cap} (gap={gap})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 16: At most 1 visit per customer per day
    # ─────────────────────────────────────────────────────────────────────────
    daily_dup_viol = []
    if not detailed.empty:
        daily_visits = detailed.groupby(["customer_id", "schedule_date"]).size()
        for (cid, date), count in daily_visits.items():
            if count > 1:
                daily_dup_viol.append(f"Customer {cid} visited {count} times on {date.date()}")

    # ─────────────────────────────────────────────────────────────────────────
    # Compile and report
    # ─────────────────────────────────────────────────────────────────────────
    checks = {
        "Cold truck requirement":                   cold_violations,
        "Min 1 visit per active customer (INFO)":   min_visit_viol,
        "Max visits/month by segment":              max_visit_viol,
        "Single salesperson per customer":          assign_viol,
        "Daily customer count limit":               daily_cap_viol,
        "At most 1 visit per customer per day":     daily_dup_viol,
        "Daily total time limit (circuit-based)":   time_viol,
        "Holiday blocking":                         holiday_viol,
        "Visit minutes (= avg_service_time)":       visit_min_viol,
        f"Travel minutes (avg inter-leg, ±{TRAVEL_LEG_TOLERANCE_MIN:.0f} min)":   travel_viol,
        "Route leg km accuracy (±500 m)":           leg_viol,
        "Cumulative route km non-decreasing":       cumulative_viol,
        "Date range (within month)":                date_viol,
        "Cold / Normal plans disjoint":             disjoint_viol,
        "Unvisited customers (0 visits, INFO)":     unvisited_viol,
        "Under-visited customers (<cap, INFO)":     under_visited_viol,
    }

    # Hard-error checks only
    _info_checks = {
        "Min 1 visit per active customer (INFO)",
        "Unvisited customers (0 visits, INFO)",
        "Under-visited customers (<cap, INFO)",
        "Single salesperson per customer",
    }
    if TREAT_TRAVEL_MIN_AS_INFO:
        _info_checks.add(f"Travel minutes (avg inter-leg, ±{TRAVEL_LEG_TOLERANCE_MIN:.0f} min)")

    total_errors = sum(
        len(v) for k, v in checks.items() if k not in _info_checks
    )

    print(f"\n{'='*65}")
    print(f"SCHEDULE VALIDATION REPORT  (scheduler_final)")
    scope = f"territory={territory_id}" if territory_id else "all territories"
    print(f"Month: {month_start}  |  Scope: {scope}")
    print(f"Rows: {len(detailed)}  |  Customers: {detailed['customer_id'].nunique()}")
    
    uv_count  = (len(result.unvisited_customers) if hasattr(result, "unvisited_customers") else 0)
    uvd_count = (len(result.under_visited_customers) if hasattr(result, "under_visited_customers") else 0)
    cold_count = (len(result.cold_schedule) if hasattr(result, "cold_schedule") else 0)
    norm_count = (len(result.normal_schedule) if hasattr(result, "normal_schedule") else 0)
    print(
        f"Cold visits: {cold_count}  |  "
        f"Normal visits: {norm_count}  |  "
        f"Unvisited: {uv_count}  |  Under-visited: {uvd_count}"
    )
    print(f"{'='*65}")

    for name, violations in checks.items():
        is_info = name in _info_checks
        if violations:
            tag = "ℹ️ " if is_info else "❌"
            print(f"\n  {tag} {name} — {len(violations)} item(s):")
            for v in violations[:5]:
                print(f"     {v}")
            if len(violations) > 5:
                print(f"     … and {len(violations) - 5} more")
        else:
            print(f"  ✅ {name}")

    print(f"\n{'='*65}")
    if total_errors == 0:
        print("🎉  ALL HARD CONSTRAINTS SATISFIED — Schedule is valid.")
        if unvisited_viol or under_visited_viol:
            print(
                f"    (Informational: {len(unvisited_viol)} unvisited, "
                f"{len(under_visited_viol)} under-visited — capacity overflow, not a bug)"
            )
    else:
        print(f"⚠️   {total_errors} hard constraint violation(s) found.")
    print(f"{'='*65}\n")

    return checks

# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE FAILURE DIAGNOSTICIAN
# ─────────────────────────────────────────────────────────────────────────────
def diagnose_schedule_failure(
    customer_df:      pd.DataFrame,
    salesperson_df:   pd.DataFrame,
    van_df:           pd.DataFrame,
    holiday_df:       pd.DataFrame,
    territory_df:     pd.DataFrame,
    config_df:        pd.DataFrame | dict,
    month_start_date: str = "2026-07-01",
    territory_id:     str = None,
) -> list[str]:
    """
    Stand-alone script that mimics TerritoryScheduler diagnostics for a failure.
    Finds capacity/holiday/van capability constraints issues before solver runs.
    """
    import calendar
    diagnostics = []

    # Config parsing
    if isinstance(config_df, pd.DataFrame):
        cfg = (
            config_df.set_index("config_key")["config_value"].to_dict()
            if not config_df.empty else {}
        )
    else:
        cfg = config_df if config_df else {}

    avg_visit_min  = int(float(cfg.get("customer_serving_time", 22)))
    avg_speed_kmh  = float(cfg.get("avg_speed", 32))
    daily_work_min = int(cfg.get("salesman_daily_work_minutes", 480))

    month_start = pd.Timestamp(month_start_date).normalize()
    year, month = month_start.year, month_start.month
    days_in_month = calendar.monthrange(year, month)[1]
    month_end = month_start + pd.Timedelta(days=days_in_month - 1)

    tids = [territory_id] if territory_id else territory_df["territory_id"].unique()

    van_cold = van_df.set_index("van_id")["cold_truck_enabled"].to_dict() if not van_df.empty else {}

    for tid in tids:
        t_cust = customer_df[customer_df["territory_id"] == tid]
        t_sp   = salesperson_df[salesperson_df["territory_id"] == tid]

        if t_cust.empty or t_sp.empty:
            continue

        # Get blocked dates for territory
        def _get_blocked(col, val):
            blocked = set()
            if holiday_df.empty:
                return blocked
            hdf = holiday_df[holiday_df[col] == val].copy()
            hdf["from_date"] = pd.to_datetime(hdf["from_date"]).dt.normalize()
            hdf["to_date"]   = pd.to_datetime(hdf["to_date"]).dt.normalize()
            for _, row in hdf.iterrows():
                cur = row["from_date"]
                while cur <= row["to_date"]:
                    blocked.add(cur)
                    cur += pd.Timedelta(days=1)
            return {d for d in blocked if month_start <= d <= month_end}

        t_blocked = _get_blocked("territory_holiday", tid)
        
        # Check by truck group (cold/normal)
        for tg in ["cold", "normal"]:
            custs = t_cust[t_cust["cold_truck_required"] == (tg == "cold")]
            if custs.empty:
                continue

            # Determine eligible SPs
            sp_cold_cap = t_sp["assigned_van"].map(van_cold).fillna(False)
            if tg == "cold":
                sps = t_sp[sp_cold_cap]
                if sps.empty:
                    diagnostics.append(
                        f"[{tid} - {tg} group]: ❌ COLD TRUCK ERROR: {len(custs)} cold customers require cold truck, "
                        f"but no salesperson is assigned a cold-capable van in territory {tid}."
                    )
                    continue
            else:
                sps = t_sp[~sp_cold_cap]
                if sps.empty:
                    sps = t_sp.copy() # Fallback to all SPs

            # Calculate total monthly capacity across eligible salespeople
            total_working_slots = 0
            n_sp = len(sps)
            
            # Geographic approximation
            t_info = territory_df[territory_df["territory_id"] == tid]
            if not t_info.empty:
                wh_lat = float(t_info.iloc[0]["warehouse_lat"])
                wh_lng = float(t_info.iloc[0]["warehouse_lng"])
            else:
                wh_lat, wh_lng = 0.0, 0.0

            wh_legs = []
            for _, c in custs.iterrows():
                km = haversine_km(wh_lat, wh_lng, float(c["gps_lat"]), float(c["gps_lng"]))
                wh_legs.append(max(1, round((km / avg_speed_kmh) * 60)))
            wh_leg_min = max(0, round(float(np.mean(wh_legs)))) if wh_legs else 5

            # All inter-customer distance
            all_inter = []
            c_list = custs.to_dict('records')
            for i, c1 in enumerate(c_list):
                lat1, lng1 = float(c1["gps_lat"]), float(c1["gps_lng"])
                for j, c2 in enumerate(c_list):
                    if i == j:
                        continue
                    lat2, lng2 = float(c2["gps_lat"]), float(c2["gps_lng"])
                    km = haversine_km(lat1, lng1, lat2, lng2)
                    all_inter.append(max(1, round(km / avg_speed_kmh * 60)))
            avg_leg_travel_min = max(1, round(float(np.mean(all_inter)) * 0.35)) if all_inter else 4

            # Time per visit
            tpv = avg_visit_min + avg_leg_travel_min
            wh_overhead = max(0, wh_leg_min - avg_leg_travel_min)
            daily_cap = max(1, (daily_work_min - wh_overhead) // tpv)

            total_days_worked = 0
            for _, sp_row in sps.iterrows():
                sid = sp_row["sales_id"]
                sp_blocked = _get_blocked("salesperson_holiday", sid)
                combined_blocked = t_blocked | sp_blocked
                valid_days = days_in_month - len(combined_blocked)
                total_working_slots += valid_days * daily_cap
                total_days_worked += valid_days

            n_cust = len(custs)
            if n_cust > total_working_slots:
                diagnostics.append(
                    f"[{tid} - {tg} group]: ⚠️ CAPACITY FAILURE: {n_cust} customers cannot be scheduled. "
                    f"Total monthly capacity = {total_working_slots} slots ({daily_cap} stops/day * {total_days_worked} total SP working days). "
                    f"Required slots (at least 1 visit/customer) is {n_cust}."
                )

            if total_days_worked == 0:
                diagnostics.append(
                    f"[{tid} - {tg} group]: ❌ HOLIDAY CONFLICT: All salespeople have 0 active working days this month."
                )

    if not diagnostics:
        print("🎉 Diagnostics: No upfront capacity or capability issues detected.")
    else:
        print("⚠️ Diagnostics found potential issues:")
        for d in diagnostics:
            print(f"  - {d}")

    return diagnostics
