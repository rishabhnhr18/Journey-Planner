"""
validate_schedule.py  (v4 — matches scheduler.py v4)
─────────────────────────────────────────────────────
Validates the monthly schedule produced by the v4 MultiSalespersonScheduler.

Changes vs v3 validate_schedule
────────────────────────────────
1.  Buffer time REMOVED from Check 5 and Check 6.
    Capacity and time checks now use pure arithmetic (no 15-min buffer).
2.  Check 14 added: validates result.unvisited_customers — customers who
    received zero visits despite being active.
3.  Docstring updated to reflect v4 constraint set.
"""

import math
from collections import defaultdict

import numpy as np
import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# Haversine helper
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2):
    R    = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
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
):
    """
    Validates all constraints against the v4 scheduler output.

    Checks
    ──────
    1.  Cold-truck customers only assigned to cold-capable salespeople.
    2.  Every active (non-Churned, non-Dormant) customer has ≥ 1 visit.
    3.  Max visits/month by RFM segment (High≤30, Medium≤15, Low≤10).
    4.  Each customer is served by ONE salesperson for all their visits.
    5.  Daily customer count ≤ capacity (pure time arithmetic, no buffer).
    6.  Daily total time ≤ daily_work_minutes per salesperson (no buffer).
    7.  No visits on territory or salesperson holidays.
    8.  estimated_visit_minutes == avg_service_time_min (default 22).
    9.  estimated_travel_minutes == one-way distance / speed (no ×2).
    10. route_leg_km sanity check (nearest-neighbour order).
    11. cumulative_route_km is non-decreasing per (sales_id, date).
    12. All schedule dates within the requested month.
    13. Cold plan / Normal plan are disjoint (no customer in both).
    14. Unvisited customers — result.unvisited_customers must be empty
        for a fully satisfied schedule.
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
    detailed = detailed.merge(
        customer_df[cust_cols], on="customer_id", how="left",
        suffixes=("", "_cust")
    )

    # ── RFM segment ───────────────────────────────────────────────────────────
    if "rfm_segment_final" not in detailed.columns and rfm_scores_df is not None:
        rfm = rfm_scores_df[["customer_id", "rfm_segment_final"]].copy()
        detailed = detailed.merge(rfm, on="customer_id", how="left")
    detailed["rfm_segment_final"] = detailed.get("rfm_segment_final", pd.Series("Low")).fillna("Low")

    # ── SP cold capability ────────────────────────────────────────────────────
    van_cold = van_df.set_index("van_id")["cold_truck_enabled"].to_dict()
    salesperson_df = salesperson_df.copy()
    salesperson_df["cold_capable"] = salesperson_df["assigned_van"].map(van_cold).fillna(False)
    sp_cold = salesperson_df.set_index("sales_id")["cold_capable"].to_dict()
    detailed["salesperson_cold_capable"] = detailed["sales_id"].map(sp_cold)

    # ── Territory warehouse coords ────────────────────────────────────────────
    ter_wh = territory_df.set_index("territory_id")[["warehouse_lat", "warehouse_lng"]].to_dict("index")
    detailed["warehouse_lat"] = detailed["territory_id"].apply(
        lambda tid: ter_wh.get(tid, {}).get("warehouse_lat", 0)
    )
    detailed["warehouse_lng"] = detailed["territory_id"].apply(
        lambda tid: ter_wh.get(tid, {}).get("warehouse_lng", 0)
    )

    # ── Config ────────────────────────────────────────────────────────────────
    cfg = config_df.set_index("config_key")["config_value"].to_dict() if not config_df.empty else {}
    avg_visit_min  = int(float(cfg.get("avg_service_time_min", 22)))
    avg_speed_kmh  = float(cfg.get("avg_speed_kmh", 32))
    daily_work_min = int(cfg.get("daily_work_minutes", 480))


    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 1: Cold-truck customers → cold-capable salesperson
    # ─────────────────────────────────────────────────────────────────────────
    cold_violations = []
    for _, row in detailed[detailed["cold_truck_required"] == True].iterrows():
        if not row.get("salesperson_cold_capable", False):
            cold_violations.append(
                f"Customer {row['customer_id']} (cold) assigned to {row['sales_id']} (not cold-capable)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 2: Unvisited active customers (informational — not a hard constraint)
    # Min-1-visit is NOT enforced in the solver. Customers with 0 visits appear
    # in result.unvisited_customers due to capacity overflow, not a solver bug.
    # This check is kept for visibility only — violations are expected when
    # total demand exceeds available salesperson capacity.
    # ─────────────────────────────────────────────────────────────────────────
    active_custs = customer_df[
        ~customer_df["lifecycle_state"].isin(["Churned", "Dormant"])
    ]
    if territory_id:
        active_custs = active_custs[active_custs["territory_id"] == territory_id]

    visited_cust      = set(detailed["customer_id"].unique())
    missing_active    = set(active_custs["customer_id"]) - visited_cust
    min_visit_viol    = [
        f"[INFO] Active customer {cid} has 0 visits (capacity overflow, not a constraint breach)"
        for cid in missing_active
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 3: Max visits/month by segment
    # ─────────────────────────────────────────────────────────────────────────
    # max_by_seg = {"High": 4, "Medium": 2, "Low": 1}
    max_by_seg = {"High": 30, "Medium": 15, "Low": 10}
    visit_counts  = detailed.groupby("customer_id").size()
    max_visit_viol = []
    for cid, cnt in visit_counts.items():
        seg     = detailed[detailed["customer_id"] == cid].iloc[0]["rfm_segment_final"]
        max_all = max_by_seg.get(seg, 1)
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
    # CHECK 5: Daily customer count ≤ capacity (pure arithmetic, no buffer)
    # cap = floor(daily_work_min / (visit_min + avg_travel_min))
    # ─────────────────────────────────────────────────────────────────────────
    daily_cap_viol = []
    grouped = detailed.groupby(["sales_id", "schedule_date"])

    for (sid, date), grp in grouped:
        wh_lat = grp.iloc[0]["warehouse_lat"]
        wh_lng = grp.iloc[0]["warehouse_lng"]

        # Prefer route_leg_km (actual leg) over estimated_travel_minutes
        # (which was historically warehouse distance — now avg leg distance).
        if "route_leg_km" in grp.columns and grp["route_leg_km"].notna().all():
            avg_travel = float((grp["route_leg_km"] / avg_speed_kmh * 60).mean())
        elif "estimated_travel_minutes" in grp.columns:
            avg_travel = grp["estimated_travel_minutes"].mean()
        else:
            travels = []
            for _, row in grp.iterrows():
                dist = haversine_km(wh_lat, wh_lng, row["gps_lat"], row["gps_lng"])
                travels.append(int((dist / avg_speed_kmh) * 60))   # one-way, no ×2
            avg_travel = np.mean(travels) if travels else 0

        tpv = avg_visit_min + avg_travel
        cap = max(1, int(daily_work_min / max(tpv, 1)))   # no buffer

        if len(grp) > cap:
            daily_cap_viol.append(
                f"{sid} on {date.date()}: {len(grp)} customers, capacity={cap} "
                f"(visit={avg_visit_min}, avg_travel_1way={avg_travel:.1f}min)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 6: Daily total time ≤ daily_work_minutes (no buffer)
    # Matches Constraint 6 in solver: sum(visit_min + travel_min) <= 480
    # ─────────────────────────────────────────────────────────────────────────
    time_viol = []
    for (sid, date), grp in grouped:
        visit_t = grp["estimated_visit_minutes"].sum()
        # Use actual route leg km if available, else estimated_travel_minutes
        if "route_leg_km" in grp.columns and grp["route_leg_km"].notna().all():
            travel_t = float(grp["route_leg_km"].sum() / avg_speed_kmh * 60)
        else:
            travel_t = grp["estimated_travel_minutes"].sum()
        total_t = visit_t + travel_t
        if total_t > daily_work_min:
            time_viol.append(
                f"{sid} on {date.date()}: total={int(total_t)}min > {daily_work_min}min"
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
                holiday_viol.append(f"Visit on territory holiday: {tid} on {d.date()}")
            if d in sp_blocked.get(sid, set()):
                holiday_viol.append(f"Visit on salesperson holiday: {sid} on {d.date()}")

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 8: estimated_visit_minutes == avg_service_time_min
    # ─────────────────────────────────────────────────────────────────────────
    visit_min_viol = []
    if "estimated_visit_minutes" in detailed.columns:
        bad = detailed[detailed["estimated_visit_minutes"] != avg_visit_min]
        for _, row in bad.iterrows():
            visit_min_viol.append(
                f"Customer {row['customer_id']} visit_min={row['estimated_visit_minutes']} ≠ {avg_visit_min}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 9: estimated_travel_minutes ≈ one-way distance / speed
    # ─────────────────────────────────────────────────────────────────────────
    travel_viol = []
    if "estimated_travel_minutes" in detailed.columns:
        for _, row in detailed.iterrows():
            dist = haversine_km(
                row["warehouse_lat"], row["warehouse_lng"],
                row["gps_lat"], row["gps_lng"],
            )
            expected = max(1, int((dist / avg_speed_kmh) * 60))   # ONE-WAY, no ×2
            stored   = int(row["estimated_travel_minutes"])
            if abs(stored - expected) > 1:
                travel_viol.append(
                    f"Customer {row['customer_id']}: stored={stored}min, "
                    f"expected_1way={expected}min (dist={dist:.2f}km)"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 10: route_leg_km sanity
    # ─────────────────────────────────────────────────────────────────────────
    leg_viol = []
    if "route_leg_km" in detailed.columns and "route_rank" in detailed.columns:
        for (sid, date), grp in detailed.groupby(["sales_id", "schedule_date"]):
            wh_lat = grp.iloc[0]["warehouse_lat"]
            wh_lng = grp.iloc[0]["warehouse_lng"]
            grp    = grp.sort_values("route_rank")
            prev_lat, prev_lng = wh_lat, wh_lng
            for _, row in grp.iterrows():
                expected_leg = haversine_km(prev_lat, prev_lng, row["gps_lat"], row["gps_lng"])
                stored_leg   = row.get("route_leg_km", 0.0) or 0.0
                if abs(stored_leg - expected_leg) > 0.5:   # tolerance 500m
                    leg_viol.append(
                        f"{sid}/{date.date()} stop#{row['route_rank']}: "
                        f"stored_leg={stored_leg:.3f}km, expected={expected_leg:.3f}km"
                    )
                prev_lat = row["gps_lat"]
                prev_lng = row["gps_lng"]

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 11: cumulative_route_km is non-decreasing
    # ─────────────────────────────────────────────────────────────────────────
    cumulative_viol = []
    if "cumulative_route_km" in detailed.columns and "route_rank" in detailed.columns:
        for (sid, date), grp in detailed.groupby(["sales_id", "schedule_date"]):
            grp = grp.sort_values("route_rank")
            prev_cum = -1.0
            for _, row in grp.iterrows():
                cum = row.get("cumulative_route_km", 0.0) or 0.0
                if cum < prev_cum - 0.01:
                    cumulative_viol.append(
                        f"{sid}/{date.date()} stop#{row['route_rank']}: "
                        f"cumulative_km decreased ({prev_cum:.3f} → {cum:.3f})"
                    )
                prev_cum = cum

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 12: Date range within month
    # ─────────────────────────────────────────────────────────────────────────
    month_start_dt = pd.Timestamp(month_start).normalize()
    month_end_dt   = (month_start_dt + pd.offsets.MonthEnd(0)).normalize()
    out_of_range   = detailed[
        (detailed["schedule_date"] < month_start_dt) |
        (detailed["schedule_date"] > month_end_dt)
    ]
    date_viol = [
        f"Visit on {d.date()} outside month"
        for d in out_of_range["schedule_date"].unique()
    ]

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 13: Cold plan / Normal plan are disjoint
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
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 14: Unvisited + under-visited customers
    # unvisited_customers   = 0 visits (capacity overflow — informational)
    # under_visited_customers = >0 but < cap (capacity overflow — informational)
    # Neither is a solver error; both are expected when demand > capacity.
    # ─────────────────────────────────────────────────────────────────────────
    unvisited_viol = []
    if hasattr(result, "unvisited_customers") and not result.unvisited_customers.empty:
        uv = result.unvisited_customers.copy()
        if territory_id:
            uv = uv[uv["territory_id"] == territory_id]
        for _, row in uv.iterrows():
            unvisited_viol.append(
                f"Customer {row['customer_id']}  [{row.get('rfm_segment_final','?')}]  "
                f"{row.get('shop_name','')}  ({row.get('territory_id','')})"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Report
    # ─────────────────────────────────────────────────────────────────────────
    checks = {
        "Cold truck requirement":               cold_violations,
        "Min 1 visit per active customer":      min_visit_viol,
        "Max visits/month by segment":          max_visit_viol,
        "Single salesperson per customer":      assign_viol,
        "Daily customer count limit":           daily_cap_viol,
        "Daily total time limit":               time_viol,
        "Holiday blocking":                     holiday_viol,
        "Visit minutes (= avg_service_time)":   visit_min_viol,
        "Travel minutes (one-way, no ×2)":      travel_viol,
        "Route leg km accuracy":                leg_viol,
        "Cumulative route km non-decreasing":   cumulative_viol,
        "Date range (within month)":            date_viol,
        "Cold / Normal plans disjoint":         disjoint_viol,
        "Unvisited customers (min-1 not met)":  unvisited_viol,
    }

    total_errors = 0
    print(f"\n{'='*60}")
    print(f"SCHEDULE VALIDATION REPORT")
    scope = f"territory={territory_id}" if territory_id else "all territories"
    print(f"Month: {month_start}  |  Scope: {scope}")
    print(f"Rows: {len(detailed)}  |  Customers: {detailed['customer_id'].nunique()}")
    uv_count = len(result.unvisited_customers) if hasattr(result, 'unvisited_customers') else 'N/A'
    print(f"Cold visits: {len(result.cold_schedule)}  |  Normal visits: {len(result.normal_schedule)}  |  Unvisited: {uv_count}")
    print(f"{'='*60}")

    for name, violations in checks.items():
        if violations:
            print(f"\n  ❌ {name} — {len(violations)} violation(s):")
            for v in violations[:5]:
                print(f"     {v}")
            if len(violations) > 5:
                print(f"     … and {len(violations) - 5} more")
            total_errors += len(violations)
        else:
            print(f"  ✅ {name}")

    print(f"\n{'='*60}")
    if total_errors == 0:
        print("🎉  ALL CONSTRAINTS SATISFIED — Schedule is valid.")
    else:
        print(f"⚠️   {total_errors} total violation(s) found.")
    print(f"{'='*60}\n")

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
#   rfm_scores_df   — RFM scores table (optional but recommended)
#
#
# ─────────────────────────────────────────────────────────────────────────────
# CASE 1: Validate ALL territories at once
# ─────────────────────────────────────────────────────────────────────────────
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
#       territory_id   = None,          # ← None = all territories
#   )
#
#
# ─────────────────────────────────────────────────────────────────────────────
# CASE 2: Validate ONE territory only (e.g. Riyadh)
# ─────────────────────────────────────────────────────────────────────────────
#
#   checks_ruh = validate_schedule(
#       result         = result,
#       customer_df    = customer_df,
#       salesperson_df = salesperson_df,
#       van_df         = van_df,
#       territory_df   = territory_df,
#       holiday_df     = holiday_df,
#       config_df      = config_df,
#       rfm_scores_df  = rfm_scores_df,
#       month_start    = "2026-06-01",
#       territory_id   = "TER_RUH",     # ← filter to Riyadh only
#   )
#
#
# ─────────────────────────────────────────────────────────────────────────────
# CASE 3: Validate a different month
# ─────────────────────────────────────────────────────────────────────────────
#
#   checks_jul = validate_schedule(
#       result         = result_july,
#       customer_df    = customer_df,
#       salesperson_df = salesperson_df,
#       van_df         = van_df,
#       territory_df   = territory_df,
#       holiday_df     = holiday_df,
#       config_df      = config_df,
#       rfm_scores_df  = rfm_scores_df,
#       month_start    = "2026-07-01",   # ← change month here
#       territory_id   = None,
#   )
#
#
# ─────────────────────────────────────────────────────────────────────────────
# CASE 4: Loop over all territories and collect results
# ─────────────────────────────────────────────────────────────────────────────
#
#   all_checks = {}
#   for tid in territory_df["territory_id"].unique():
#       all_checks[tid] = validate_schedule(
#           result         = result,
#           customer_df    = customer_df,
#           salesperson_df = salesperson_df,
#           van_df         = van_df,
#           territory_df   = territory_df,
#           holiday_df     = holiday_df,
#           config_df      = config_df,
#           rfm_scores_df  = rfm_scores_df,
#           month_start    = "2026-06-01",
#           territory_id   = tid,
#       )
#
#
# ─────────────────────────────────────────────────────────────────────────────
# CASE 5: Inspect specific check results after validation
# ─────────────────────────────────────────────────────────────────────────────
#
#   checks = validate_schedule(...)    # returns dict of {check_name: [violations]}
#
#   # See all unvisited customers
#   print(checks["Unvisited customers (min-1 not met)"])
#
#   # See all cold-truck violations
#   print(checks["Cold truck requirement"])
#
#   # See all holiday violations
#   print(checks["Holiday blocking"])
#
#   # See all max-visit violations
#   print(checks["Max visits/month by segment"])
#
#   # See daily time violations
#   print(checks["Daily total time limit"])
#
#   # See daily count violations
#   print(checks["Daily customer count limit"])
#
#   # Check if fully valid
#   is_valid = all(len(v) == 0 for v in checks.values())
#   print("Schedule valid:", is_valid)
#
#
# ─────────────────────────────────────────────────────────────────────────────
# CASE 6: Access unvisited customers DataFrame directly
# ─────────────────────────────────────────────────────────────────────────────
#
#   # After scheduling
#   print(result.unvisited_customers)
#
#   # Save to CSV
#   result.unvisited_customers.to_csv("unvisited_customers.csv", index=False)
#
#
# ─────────────────────────────────────────────────────────────────────────────
# WHAT EACH CHECK VALIDATES
# ─────────────────────────────────────────────────────────────────────────────
#
#  Check  1 — Cold truck requirement
#             Cold-truck customers (Cold Store, Butchery) must be visited only
#             by salespeople whose assigned van has cold_truck_enabled=True.
#
#  Check  2 — Min 1 visit per active customer
#             Every customer not in lifecycle_state Churned/Dormant must appear
#             at least once in the schedule.
#
#  Check  3 — Max visits/month by RFM segment
#             High ≤ 30 visits, Medium ≤ 15 visits, Low ≤ 10 visits.
#
#  Check  4 — Single salesperson per customer
#             All visits for a given customer must be by the same salesperson.
#             Multiple salespeople visiting the same customer is not allowed.
#
#  Check  5 — Daily customer count limit
#             floor(480 / (visit_min + avg_travel_min)) customers per SP per day.
#             No buffer — pure arithmetic. Must match scheduler Constraint 7.
#
#  Check  6 — Daily total time limit
#             sum(visit_min + travel_min) across all customers on that day ≤ 480.
#             No buffer. Must match scheduler Constraint 6 exactly.
#
#  Check  7 — Holiday blocking
#             No visit should fall on a territory holiday or the assigned
#             salesperson's personal leave dates.
#
#  Check  8 — Visit minutes accuracy
#             estimated_visit_minutes must equal avg_service_time_min from config
#             (default 22 min).
#
#  Check  9 — Travel minutes accuracy
#             estimated_travel_minutes must equal one-way haversine distance /
#             avg_speed_kmh × 60.  Tolerance: ±1 minute.
#
#  Check 10 — Route leg km accuracy
#             route_leg_km for each stop must match the haversine distance from
#             the previous stop.  Tolerance: ±500m.
#
#  Check 11 — Cumulative route km non-decreasing
#             cumulative_route_km must never decrease along the route order.
#
#  Check 12 — Date range within month
#             All schedule_date values must fall within the requested month.
#
#  Check 13 — Cold / Normal plans disjoint
#             No customer_id should appear in both cold_schedule and
#             normal_schedule.
#
#  Check 14 — Unvisited customers
#             result.unvisited_customers lists every active customer who
#             received 0 visits because capacity could not accommodate them.
#             These are explicitly tracked — NOT silently dropped.
#             An empty unvisited_customers means all customers were scheduled.
#
# =============================================================================