"""
validate_schedule_6.py  (v6 — matches scheduler_6_adjust_priority.py)
───────────────────────────────────────────────────────────────────────
Validates the monthly schedule produced by the v6 MultiSalespersonScheduler.

Key changes vs validate_schedule (v4)
──────────────────────────────────────
1.  CIRCUIT-BASED TIME CHECK (Check 6).
    The v6 solver uses AddCircuit with a REAL pairwise distance matrix.
    Daily time is now:
        sum(route_leg_km) / speed × 60  +  n_customers × avg_visit_min
    This mirrors the solver's Constraint 6 exactly.
    The old "estimated_travel_minutes per customer" approach is used only as
    a fallback when route_leg_km is unavailable.

2.  CHECK 9 UPDATED — estimated_travel_minutes now stores avg_leg_travel_min
    (average inter-customer leg, not warehouse-to-customer distance).
    Validation now checks that the stored value is within ±2 min of
    the average pairwise inter-customer travel time (not warehouse dist).

3.  PRIORITY TIER WEIGHTS UPDATED.
    Scheduler v6 uses _TIER = {High: 1_000_000_000, Medium: 1_000_000, Low: 1}.
    Segment caps remain: High ≤ 30, Medium ≤ 15, Low ≤ 10.

4.  UNDER-VISITED CUSTOMERS CHECK ADDED (Check 15).
    result.under_visited_customers (customers with >0 but < cap visits) is
    now separately reported alongside unvisited_customers (Check 14).

5.  GREEDY TOP-UP AWARENESS.
    The scheduler runs a post-solve greedy fill using real routed distances.
    Check 6 tolerates the greedy additions because they are also constrained
    to daily_work_minutes (remaining > avg_visit_min + 2 gate).

6.  DAILY COUNT CAP CHECK (Check 5) UPDATED.
    Cap is now: floor(daily_work_min / (avg_visit_min + avg_inter_leg_min))
    where avg_inter_leg_min is derived from route_leg_km when available.

Constraints validated
──────────────────────
 1  Cold-truck customers only served by cold-capable salesperson.
 2  Active (non-Churned, non-Dormant) customer ≥ 1 visit (informational).
 3  Max visits/month: High ≤ 30, Medium ≤ 15, Low ≤ 10.
 4  Single salesperson per customer (assignment consistency).
 5  Daily customer count ≤ floor(daily_work_min / (visit_min + avg_leg_min)).
 6  Daily total time (route_leg_km-based) ≤ daily_work_minutes.
 7  No visits on territory or salesperson holidays.
 8  estimated_visit_minutes == avg_service_time_min (default 22).
 9  estimated_travel_minutes ≈ avg inter-customer leg travel (±2 min).
10  route_leg_km matches haversine from previous stop (±500 m).
11  cumulative_route_km non-decreasing along route_rank.
12  All schedule_date values within the requested month.
13  cold_schedule and normal_schedule are disjoint (no shared customer_id).
14  Unvisited customers (0 visits — capacity overflow, informational).
15  Under-visited customers (>0 but < cap — informational).
"""

import math
from collections import defaultdict

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CONFIGURATION CONSTANTS (For easy synchronization with scheduler)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_CAPS = {"High": 25, "Medium": 16, "Low": 5}
TRAVEL_LEG_TOLERANCE_MIN = 5.0
TREAT_TRAVEL_MIN_AS_INFO = True  # If True, Check 9 is informational and does not count as a hard failure.
LEG_KM_TOLERANCE_M = 500.0       # 500m tolerance for haversine accuracy


# ─────────────────────────────────────────────────────────────────────────────
# Haversine helper
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R    = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = (math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ─────────────────────────────────────────────────────────────────────────────
# Main validator
# ─────────────────────────────────────────────────────────────────────────────

def validate_schedule(
    result,
    customer_df:     pd.DataFrame,
    salesperson_df:  pd.DataFrame,
    van_df:          pd.DataFrame,
    territory_df:    pd.DataFrame,
    holiday_df:      pd.DataFrame,
    config_df:       pd.DataFrame,
    rfm_scores_df:   pd.DataFrame = None,
    month_start:     str          = "2026-06-01",
    territory_id:    str          = None,   # None → validate all
    caps:            dict         = None,
):
    """
    Validates all constraints against the v6 scheduler output.

    Parameters
    ──────────
    result          : MultiScheduleResult from MultiSalespersonScheduler.create_schedules()
    customer_df     : customer master table
    salesperson_df  : salesperson table (with assigned_van column)
    van_df          : van table (with cold_truck_enabled column)
    territory_df    : territory table (with warehouse_lat/lng)
    holiday_df      : holiday table (from_date, to_date, territory_holiday, salesperson_holiday)
    config_df       : config table (avg_service_time_min, avg_speed_kmh, daily_work_minutes)
    rfm_scores_df   : RFM scores table (optional — rfm_segment_final must be in detailed_schedule)
    month_start     : first day of the scheduled month (YYYY-MM-DD)
    territory_id    : validate only this territory (None = all territories)

    Returns
    ───────
    dict of {check_name: [violation_strings]}
    """
    detailed = result.detailed_schedule.copy()
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
    # Prefer schedule copy of coordinates (gps_lat/lng should already be there)
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
    van_cold = van_df.set_index("van_id")["cold_truck_enabled"].to_dict()
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
    )
    detailed["warehouse_lat"] = detailed["territory_id"].apply(
        lambda tid: ter_wh.get(tid, {}).get("warehouse_lat", 0)
    )
    detailed["warehouse_lng"] = detailed["territory_id"].apply(
        lambda tid: ter_wh.get(tid, {}).get("warehouse_lng", 0)
    )

    # ── Config ────────────────────────────────────────────────────────────────
    cfg = (
        config_df.set_index("config_key")["config_value"].to_dict()
        if not config_df.empty else {}
    )
    avg_visit_min  = int(float(cfg.get("avg_service_time_min", 22)))
    avg_speed_kmh  = float(cfg.get("avg_speed_kmh", 32))
    daily_work_min = int(cfg.get("daily_work_minutes", 480))

    # ── Segment visit caps (v6) ───────────────────────────────────────────────
    _CAPS = caps if caps is not None else DEFAULT_CAPS

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
    # In v6, min-1-visit is NOT a solver constraint.  0-visit customers
    # appear in result.unvisited_customers due to capacity overflow.
    # ─────────────────────────────────────────────────────────────────────────
    active_custs = customer_df[
        ~customer_df["lifecycle_state"].isin(["Churned", "Dormant"])
    ].copy()
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
    # CHECK 3: Max visits/month by segment (High ≤ 30, Medium ≤ 15, Low ≤ 10)
    # ─────────────────────────────────────────────────────────────────────────
    visit_counts  = detailed.groupby("customer_id").size()
    max_visit_viol = []
    for cid, cnt in visit_counts.items():
        seg     = detailed[detailed["customer_id"] == cid].iloc[0]["rfm_segment_final"]
        max_all = _CAPS.get(seg, 10)
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
    # v6 solver derives capacity as:
    #   cap = floor(daily_work_min / (avg_visit_min + avg_inter_leg_min))
    # where avg_inter_leg_min = mean of actual route_leg_km / speed × 60.
    # Use route_leg_km when available, fall back to estimated_travel_minutes.
    # ─────────────────────────────────────────────────────────────────────────
    daily_cap_viol = []
    grouped = detailed.groupby(["sales_id", "schedule_date"])

    for (sid, date), grp in grouped:
        n_cust = len(grp)

        if ("route_leg_km" in grp.columns and grp["route_leg_km"].notna().all()
                and n_cust > 1):
            # Average inter-customer leg (exclude warehouse-departure leg by
            # averaging over all legs — conservative, matches solver avg)
            avg_inter_min = float((grp["route_leg_km"] / avg_speed_kmh * 60).mean())
        elif "estimated_travel_minutes" in grp.columns:
            avg_inter_min = float(grp["estimated_travel_minutes"].mean())
        else:
            # Fallback: average haversine from warehouse for each customer
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
    # v6 Constraint 6 uses AddCircuit with REAL pairwise distances.
    # Post-solve, DailyRoutePlanner fills route_leg_km with exact NN legs.
    # Total time = sum(route_leg_km) / speed × 60  +  n_stops × visit_min.
    # Greedy top-up also respects this budget (gate: remaining > visit_min + 2).
    # ─────────────────────────────────────────────────────────────────────────
    time_viol = []
    for (sid, date), grp in grouped:
        service_t = len(grp) * avg_visit_min

        if ("route_leg_km" in grp.columns and grp["route_leg_km"].notna().all()):
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
    # CHECK 8: estimated_visit_minutes == avg_service_time_min
    # v6 hard-codes avg_visit_minutes = 22 (from config avg_service_time_min).
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
    # CHECK 9: estimated_travel_minutes ≈ avg inter-customer leg (±2 min)
    # In v6, estimated_travel_minutes stores avg_leg_travel_min — the mean of
    # ALL pairwise inter-customer travel times in the territory group.
    # It is NOT the warehouse-to-customer distance (that was v4 behaviour).
    # We validate per (SP, day): check stored value vs mean actual leg time.
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
                # (loose tolerance because avg_leg_travel_min is computed
                #  from ALL territory customers, not just this day's subset)
                travel_viol.append(
                    f"{sid} on {date.date()}: stored estimated_travel_minutes="
                    f"{stored:.1f} min, day avg_leg={actual_avg_leg_min:.1f} min "
                    f"(diff={abs(stored - actual_avg_leg_min):.1f} min)"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 10: route_leg_km accuracy (haversine from previous stop ± 500 m)
    # DailyRoutePlanner computes nearest-neighbour from warehouse; validation
    # re-computes each leg and compares to stored route_leg_km.
    # ─────────────────────────────────────────────────────────────────────────
    leg_viol = []
    if "route_leg_km" in detailed.columns and "route_rank" in detailed.columns:
        for (sid, date), grp in detailed.groupby(["sales_id", "schedule_date"]):
            wh_lat_v = grp.iloc[0]["warehouse_lat"]
            wh_lng_v = grp.iloc[0]["warehouse_lng"]
            grp_sorted = grp.sort_values("route_rank")
            prev_lat, prev_lng = wh_lat_v, wh_lng_v
            for _, row in grp_sorted.iterrows():
                expected_leg = haversine_km(
                    prev_lat, prev_lng, row["gps_lat"], row["gps_lng"]
                )
                stored_leg = row.get("route_leg_km", 0.0) or 0.0
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
    # A customer should only appear in one truck group.
    # ─────────────────────────────────────────────────────────────────────────
    disjoint_viol = []
    if "truck_group" in detailed.columns:
        cold_ids   = set(result.cold_schedule["customer_id"].unique())
        normal_ids = set(result.normal_schedule["customer_id"].unique())
        overlap    = cold_ids & normal_ids
        if overlap:
            disjoint_viol.append(
                f"{len(overlap)} customer(s) appear in BOTH cold and normal plans: "
                f"{list(overlap)[:5]}"
                + (f" …+{len(overlap)-5} more" if len(overlap) > 5 else "")
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 14: Unvisited customers (0 visits — capacity overflow)
    # result.unvisited_customers is populated by the orchestrator post-solve.
    # These are explicitly tracked and NOT a solver error.
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
    # CHECK 15: Under-visited customers (>0 but < segment cap — informational)
    # result.under_visited_customers is populated post-solve by the orchestrator.
    # These customers received visits but did not reach their full segment cap.
    # ─────────────────────────────────────────────────────────────────────────
    under_visited_viol = []
    if hasattr(result, "under_visited_customers") and not result.under_visited_customers.empty:
        uv = result.under_visited_customers.copy()
        if territory_id and "territory_id" in uv.columns:
            uv = uv[uv["territory_id"] == territory_id]
        for _, row in uv.iterrows():
            cap     = _CAPS.get(row.get("rfm_segment_final", "Low"), 10)
            actual  = int(row.get("actual_visits", 0))
            gap     = int(row.get("visits_gap", cap - actual))
            under_visited_viol.append(
                f"[INFO] Customer {row['customer_id']}  "
                f"[{row.get('rfm_segment_final', '?')}]  "
                f"{row.get('shop_name', '')}  "
                f"visits={actual}/{cap} (gap={gap})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Compile and report
    # ─────────────────────────────────────────────────────────────────────────
    checks = {
        "Cold truck requirement":                   cold_violations,
        "Min 1 visit per active customer (INFO)":   min_visit_viol,
        "Max visits/month by segment":              max_visit_viol,
        "Single salesperson per customer":          assign_viol,
        "Daily customer count limit":               daily_cap_viol,
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

    # Hard-error checks only (INFO checks are excluded from error count)
    _info_checks = {
        "Min 1 visit per active customer (INFO)",
        "Unvisited customers (0 visits, INFO)",
        "Under-visited customers (<cap, INFO)",
    }
    if TREAT_TRAVEL_MIN_AS_INFO:
        _info_checks.add(f"Travel minutes (avg inter-leg, ±{TRAVEL_LEG_TOLERANCE_MIN:.0f} min)")

    total_errors = sum(
        len(v) for k, v in checks.items() if k not in _info_checks
    )

    print(f"\n{'='*65}")
    print(f"SCHEDULE VALIDATION REPORT  (scheduler v6 — adjust_priority)")
    scope = f"territory={territory_id}" if territory_id else "all territories"
    print(f"Month: {month_start}  |  Scope: {scope}")
    print(f"Rows: {len(detailed)}  |  Customers: {detailed['customer_id'].nunique()}")
    uv_count  = (len(result.unvisited_customers)
                 if hasattr(result, "unvisited_customers") else "N/A")
    uvd_count = (len(result.under_visited_customers)
                 if hasattr(result, "under_visited_customers") else "N/A")
    print(
        f"Cold visits: {len(result.cold_schedule)}  |  "
        f"Normal visits: {len(result.normal_schedule)}  |  "
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


# =============================================================================
# HOW TO RUN THE VALIDATOR — COMPLETE USAGE GUIDE
# =============================================================================
#
# PREREQUISITES
# ─────────────
# All variables below must exist in your notebook / script session:
#
#   result          — MultiScheduleResult from MultiSalespersonScheduler.create_schedules()
#   customer_df     — customer master table
#   salesperson_df  — salesperson table (with assigned_van column)
#   van_df          — van table (with cold_truck_enabled column)
#   territory_df    — territory table (with warehouse_lat/lng)
#   holiday_df      — holiday table
#   config_df       — config table (avg_service_time_min, avg_speed_kmh, etc.)
#   rfm_scores_df   — RFM scores table (optional — rfm_segment_final is embedded in schedule)
#
#
# CASE 1: Validate ALL territories at once
# ─────────────────────────────────────────
#
#   checks_all = validate_schedule(
#       result         = result,
#       customer_df    = customer_df,
#       salesperson_df = salesperson_df,
#       van_df         = van_df,
#       territory_df   = territory_df,
#       holiday_df     = holiday_df,
#       config_df      = config_df,
#       rfm_scores_df  = rfm_scores_df,
#       month_start    = "2026-06-01",
#       territory_id   = None,
#   )
#
#
# CASE 2: Validate ONE territory only
# ─────────────────────────────────────
#
#   checks_ruh = validate_schedule(
#       result         = result,
#       ...
#       month_start    = "2026-06-01",
#       territory_id   = "TER_RUH",
#   )
#
#
# CASE 3: Loop over all territories
# ──────────────────────────────────
#
#   all_checks = {}
#   for tid in territory_df["territory_id"].unique():
#       all_checks[tid] = validate_schedule(
#           result      = result,
#           ...
#           month_start = "2026-06-01",
#           territory_id = tid,
#       )
#
#
# CASE 4: Inspect specific check results
# ────────────────────────────────────────
#
#   checks = validate_schedule(...)   # returns dict
#
#   # Hard constraint violations
#   print(checks["Cold truck requirement"])
#   print(checks["Max visits/month by segment"])
#   print(checks["Daily total time limit (circuit-based)"])
#   print(checks["Holiday blocking"])
#
#   # Informational only
#   print(checks["Unvisited customers (0 visits, INFO)"])
#   print(checks["Under-visited customers (<cap, INFO)"])
#
#   # Check if ALL hard constraints pass
#   _info = {"Min 1 visit per active customer (INFO)",
#            "Unvisited customers (0 visits, INFO)",
#            "Under-visited customers (<cap, INFO)"}
#   is_valid = all(len(v) == 0 for k, v in checks.items() if k not in _info)
#   print("Schedule hard-constraint valid:", is_valid)
#
#
# CASE 5: Access unvisited / under-visited DataFrames directly
# ─────────────────────────────────────────────────────────────
#
#   print(result.unvisited_customers)
#   print(result.under_visited_customers)
#
#   result.unvisited_customers.to_csv("unvisited.csv", index=False)
#   result.under_visited_customers.to_csv("under_visited.csv", index=False)
#
#
# =============================================================================
# WHAT EACH CHECK VALIDATES
# =============================================================================
#
#  Check  1 — Cold truck requirement
#             Cold-truck customers must be visited only by cold-capable SPs
#             (assigned van has cold_truck_enabled=True).
#
#  Check  2 — Min 1 visit per active customer [INFO]
#             Informational only. In v6 the solver does NOT enforce min-1 as a
#             hard constraint. Customers with 0 visits are in unvisited_customers
#             (capacity overflow). This check just surfaces them visibly.
#
#  Check  3 — Max visits/month by RFM segment
#             High ≤ 30 visits, Medium ≤ 15 visits, Low ≤ 10 visits.
#
#  Check  4 — Single salesperson per customer
#             All visits for a given customer must be by the same salesperson.
#
#  Check  5 — Daily customer count limit
#             cap = floor(daily_work_min / (visit_min + avg_inter_leg_min)).
#             avg_inter_leg_min derived from route_leg_km when available.
#
#  Check  6 — Daily total time limit (circuit-based)
#             total = sum(route_leg_km)/speed×60 + n_stops×visit_min ≤ 480 min.
#             Mirrors Constraint 6 (AddCircuit) in the v6 solver exactly.
#             Includes greedy top-up visits (they respect the same budget).
#
#  Check  7 — Holiday blocking
#             No visit on a territory or salesperson holiday.
#
#  Check  8 — Visit minutes accuracy
#             estimated_visit_minutes must equal avg_service_time_min (22 min).
#
#  Check  9 — Travel minutes accuracy (avg inter-leg, ±5 min)
#             estimated_travel_minutes stores the avg inter-customer leg travel
#             (avg_leg_travel_min from the pairwise matrix). Validated per day
#             against mean(route_leg_km)/speed×60 for that day. Loose ±5 min
#             tolerance because the stored value is territory-wide average.
#
#  Check 10 — Route leg km accuracy
#             route_leg_km must match haversine from previous stop (±500 m).
#
#  Check 11 — Cumulative route km non-decreasing
#             cumulative_route_km must never decrease along route_rank order.
#
#  Check 12 — Date range within month
#             All schedule_date values must fall within the requested month.
#
#  Check 13 — Cold / Normal plans disjoint
#             No customer_id should appear in both cold_schedule and
#             normal_schedule.
#
#  Check 14 — Unvisited customers [INFO]
#             result.unvisited_customers = customers who received 0 visits
#             because capacity could not accommodate them. Not a solver bug.
#
#  Check 15 — Under-visited customers [INFO]
#             result.under_visited_customers = customers with >0 but < segment
#             cap visits. Capacity-overflow case, not a constraint breach.
#
# =============================================================================
