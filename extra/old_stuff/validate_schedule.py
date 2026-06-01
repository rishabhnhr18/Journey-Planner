"""
validate_schedule.py  (v3 — matches scheduler.py v3)
─────────────────────────────────────────────────────
Validates the monthly schedule produced by the v3 MultiSalespersonScheduler.

Changes vs v2 validate_schedule
────────────────────────────────
1.  Travel-time check uses ONE-WAY distance (no ×2) + 15-min buffer after
    every 4th customer on the route.
2.  Cold/normal truck plans are validated separately and together.
3.  Salesperson assignment consistency: every visit of a given customer must
    be by the SAME salesperson (joint-assignment constraint).
4.  Route km tracking: checks route_leg_km / cumulative_route_km columns.
5.  Territory filter: pass `territory_id=None` → validate all.
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
    Validates all constraints against the v3 scheduler output.

    Checks
    ──────
    1.  Cold-truck customers only assigned to cold-capable salespeople.
    2.  Every active (non-Churned, non-Dormant) customer has ≥ 1 visit.
    3.  Max visits/month by RFM segment (High≤4, Medium≤2, Low≤1).
    4.  Each customer is served by ONE salesperson for all their visits.
    5.  Daily customer count ≤ capacity (one-way travel, 15-min buffer/4).
    6.  Daily total time ≤ daily_work_minutes per salesperson.
    7.  No visits on territory or salesperson holidays.
    8.  estimated_visit_minutes == avg_service_time_min (default 22).
    9.  estimated_travel_minutes == one-way distance / speed  (no ×2).
    10. route_leg_km sanity check (nearest-neighbour order).
    11. cumulative_route_km is non-decreasing per (sales_id, date).
    12. All schedule dates within the requested month.
    13. Cold plan / Normal plan are disjoint (no customer in both).
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

    BUFFER_EVERY   = 4    # add 15 min after every 4th customer
    BUFFER_MIN     = 15

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
    # CHECK 2: Min 1 visit per active customer
    # ─────────────────────────────────────────────────────────────────────────
    active_custs = customer_df[
        ~customer_df["lifecycle_state"].isin(["Churned", "Dormant"])
    ]
    if territory_id:
        active_custs = active_custs[active_custs["territory_id"] == territory_id]

    visited_cust      = set(detailed["customer_id"].unique())
    missing_active    = set(active_custs["customer_id"]) - visited_cust
    min_visit_viol    = [f"Active customer {cid} has 0 visits" for cid in missing_active]

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 3: Max visits/month by segment
    # ─────────────────────────────────────────────────────────────────────────
    max_by_seg = {"High": 4, "Medium": 2, "Low": 1}
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
    # CHECK 5: Daily customer count ≤ capacity (one-way travel + buffer)
    # ─────────────────────────────────────────────────────────────────────────
    daily_cap_viol = []
    grouped = detailed.groupby(["sales_id", "schedule_date"])

    for (sid, date), grp in grouped:
        wh_lat = grp.iloc[0]["warehouse_lat"]
        wh_lng = grp.iloc[0]["warehouse_lng"]

        if "estimated_travel_minutes" in grp.columns:
            avg_travel = grp["estimated_travel_minutes"].mean()
        else:
            travels = []
            for _, row in grp.iterrows():
                dist = haversine_km(wh_lat, wh_lng, row["gps_lat"], row["gps_lng"])
                travels.append(int((dist / avg_speed_kmh) * 60))   # one-way, no ×2
            avg_travel = np.mean(travels) if travels else 0

        tpv = avg_visit_min + avg_travel

        # Binary search for effective capacity with buffer
        lo, hi = 1, int(daily_work_min / max(tpv, 1))
        while lo < hi:
            mid  = (lo + hi + 1) // 2
            cost = mid * tpv + (mid // BUFFER_EVERY) * BUFFER_MIN
            if cost <= daily_work_min:
                lo = mid
            else:
                hi = mid - 1
        cap = max(1, lo)

        if len(grp) > cap:
            daily_cap_viol.append(
                f"{sid} on {date.date()}: {len(grp)} customers, capacity={cap} "
                f"(visit={avg_visit_min}, avg_travel_1way={avg_travel:.1f}min)"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CHECK 6: Daily total time ≤ daily_work_minutes
    # ─────────────────────────────────────────────────────────────────────────
    time_viol = []
    for (sid, date), grp in grouped:
        n        = len(grp)
        buffers  = (n // BUFFER_EVERY) * BUFFER_MIN
        total_t  = (grp["estimated_visit_minutes"] + grp["estimated_travel_minutes"]).sum()
        total_t += buffers
        if total_t > daily_work_min:
            time_viol.append(
                f"{sid} on {date.date()}: total={total_t}min "
                f"(+{buffers}min buffer) > {daily_work_min}min"
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
    }

    total_errors = 0
    print(f"\n{'='*60}")
    print(f"SCHEDULE VALIDATION REPORT")
    scope = f"territory={territory_id}" if territory_id else "all territories"
    print(f"Month: {month_start}  |  Scope: {scope}")
    print(f"Rows: {len(detailed)}  |  Customers: {detailed['customer_id'].nunique()}")
    print(f"Cold visits: {len(result.cold_schedule)}  |  Normal visits: {len(result.normal_schedule)}")
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
