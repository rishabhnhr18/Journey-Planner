"""
validate_schedule.py
Validates the monthly schedule from saudi_multi_salesperson_scheduler_new.py
against all business constraints.
"""

import pandas as pd
import numpy as np
import math
from collections import defaultdict

# ------------------------------------------------------------
# Helper: Haversine distance (same as in scheduler)
# ------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ------------------------------------------------------------
# Main validation function
# ------------------------------------------------------------
def validate_schedule(result, customer_df, salesperson_df, van_df, territory_df,
                      holiday_df, config_df, rfm_scores_df=None, month_start="2026-06-01"):
    """
    Validates all constraints:
    - Cold truck customers only to cold-capable salespeople.
    - Every active customer has at least 1 visit.
    - Max visits per month by RFM segment (High=4, Medium=2, Low=1).
    - Daily customer count ≤ capacity (derived from working hours / (visit+travel)).
    - Daily total visit+travel minutes ≤ daily_work_minutes.
    - No visits on territory or salesperson holidays.
    - Estimated visit minutes = config avg_service_time_min (default 22).
    - Estimated travel minutes are correct (based on warehouse distance).
    - All dates are inside the scheduled month.
    """
    detailed = result.detailed_schedule.copy()
    if detailed.empty:
        print("No schedule generated – nothing to validate.")
        return

    # Ensure date column is datetime
    detailed['schedule_date'] = pd.to_datetime(detailed['schedule_date'])

    # Merge customer master data (cold_truck, lifecycle_state, GPS)
    cust_cols = ['customer_id', 'cold_truck_required', 'lifecycle_state',
                 'gps_lat', 'gps_lng', 'territory_id']
    cust_df = customer_df[cust_cols].copy()
    detailed = detailed.merge(cust_df, on='customer_id', how='left', suffixes=('', '_cust'))

    # Merge RFM segment if not already in detailed
    if 'rfm_segment_final' not in detailed.columns and rfm_scores_df is not None:
        rfm = rfm_scores_df[['customer_id', 'rfm_segment_final']].copy()
        detailed = detailed.merge(rfm, on='customer_id', how='left')
        detailed['rfm_segment_final'] = detailed['rfm_segment_final'].fillna('Low')
    elif 'rfm_segment_final' not in detailed.columns:
        detailed['rfm_segment_final'] = 'Low'   # fallback

    # Merge salesperson van cold capability
    van_cold = van_df.set_index('van_id')['cold_truck_enabled'].to_dict()
    salesperson_df['cold_capable'] = salesperson_df['assigned_van'].map(van_cold).fillna(False)
    sp_cold = salesperson_df.set_index('sales_id')['cold_capable'].to_dict()
    detailed['salesperson_cold_capable'] = detailed['sales_id'].map(sp_cold)

    # Territory warehouse coordinates
    ter_wh = territory_df.set_index('territory_id')[['warehouse_lat', 'warehouse_lng']].to_dict('index')
    detailed['warehouse_lat'] = detailed['territory_id'].apply(lambda tid: ter_wh.get(tid, {}).get('warehouse_lat', 0))
    detailed['warehouse_lng'] = detailed['territory_id'].apply(lambda tid: ter_wh.get(tid, {}).get('warehouse_lng', 0))

    # Load config
    cfg = config_df.set_index('config_key')['config_value'].to_dict() if not config_df.empty else {}
    avg_visit_min = int(float(cfg.get('avg_service_time_min', 22)))
    avg_speed_kmh = float(cfg.get('avg_speed_kmh', 32))
    daily_work_min = int(cfg.get('daily_work_minutes', 480))

    # --- 1. Cold truck customers must be assigned to cold-capable salesperson ---
    cold_violations = []
    cold_cust = detailed[detailed['cold_truck_required'] == True]
    for _, row in cold_cust.iterrows():
        if not row['salesperson_cold_capable']:
            cold_violations.append(f"Customer {row['customer_id']} requires cold truck but assigned to {row['sales_id']} (van not cold-capable)")

    # --- 2. Minimum 1 visit per active customer ---
    active_cust = customer_df[~customer_df['lifecycle_state'].isin(['Churned', 'Dormant'])]
    visited_cust = set(detailed['customer_id'].unique())
    missing_active = set(active_cust['customer_id']) - visited_cust
    min_visit_violations = [f"Active customer {cid} has 0 visits" for cid in missing_active]

    # --- 3. Max visits per month by RFM segment ---
    max_by_segment = {'High': 4, 'Medium': 2, 'Low': 1}
    visit_counts = detailed.groupby('customer_id').size()
    max_visit_violations = []
    for cust_id, cnt in visit_counts.items():
        seg = detailed[detailed['customer_id'] == cust_id].iloc[0]['rfm_segment_final']
        max_allowed = max_by_segment.get(seg, 1)
        if cnt > max_allowed:
            max_visit_violations.append(f"Customer {cust_id} ({seg}) has {cnt} visits, max {max_allowed}")

    # --- 4. Daily customer count limit (capacity) ---
    # Compute per salesperson per day using the same logic as scheduler
    daily_cap_violations = []
    grouped = detailed.groupby(['sales_id', 'schedule_date'])
    for (sid, date), group in grouped:
        # Get territory warehouse for this group
        wh_lat = group.iloc[0]['warehouse_lat']
        wh_lng = group.iloc[0]['warehouse_lng']
        # Compute average travel time for this salesperson's assigned customers (whole month)
        # Use stored travel times if available, else compute
        if 'estimated_travel_minutes' in group.columns:
            avg_travel = group['estimated_travel_minutes'].mean()
        else:
            # fallback: compute from warehouse to each customer in this day's group
            travel_list = []
            for _, row in group.iterrows():
                dist = haversine_km(wh_lat, wh_lng, row['gps_lat'], row['gps_lng'])
                travel_list.append(int((dist / avg_speed_kmh) * 60))
            avg_travel = np.mean(travel_list) if travel_list else 0
        time_per_visit = avg_visit_min + avg_travel
        max_cust_per_day = max(1, daily_work_min // time_per_visit)
        if len(group) > max_cust_per_day:
            daily_cap_violations.append(
                f"{sid} on {date.date()}: {len(group)} customers, capacity {max_cust_per_day} "
                f"(visit={avg_visit_min}, avg_travel={avg_travel:.1f})"
            )

    # --- 5. Daily total time limit (visit+travel) ---
    time_limit_violations = []
    for (sid, date), group in grouped:
        total_time = (group['estimated_visit_minutes'] + group['estimated_travel_minutes']).sum()
        if total_time > daily_work_min:
            time_limit_violations.append(
                f"{sid} on {date.date()}: total time {total_time} min > {daily_work_min}"
            )

    # --- 6. Holiday violations ---
    holiday_violations = []
    if not holiday_df.empty:
        # Build blocked sets per territory and per salesperson
        ter_blocked = defaultdict(set)
        sp_blocked = defaultdict(set)
        hdf = holiday_df.copy()
        hdf['from_date'] = pd.to_datetime(hdf['from_date']).dt.normalize()
        hdf['to_date'] = pd.to_datetime(hdf['to_date']).dt.normalize()
        for _, row in hdf.iterrows():
            dr = pd.date_range(row['from_date'], row['to_date'])
            if pd.notna(row.get('territory_holiday')):
                ter_blocked[row['territory_holiday']].update(dr)
            if pd.notna(row.get('salesperson_holiday')):
                sp_blocked[row['salesperson_holiday']].update(dr)

        for _, row in detailed.iterrows():
            d = row['schedule_date'].normalize()
            tid = row['territory_id']
            sid = row['sales_id']
            if d in ter_blocked.get(tid, set()):
                holiday_violations.append(f"Visit on territory holiday: {tid} on {d.date()}")
            if d in sp_blocked.get(sid, set()):
                holiday_violations.append(f"Visit on salesperson holiday: {sid} on {d.date()}")

    # --- 7. Visit minutes consistency ---
    visit_min_violations = []
    if 'estimated_visit_minutes' in detailed.columns:
        bad_visit = detailed[detailed['estimated_visit_minutes'] != avg_visit_min]
        for _, row in bad_visit.iterrows():
            visit_min_violations.append(
                f"Customer {row['customer_id']} visit minutes = {row['estimated_visit_minutes']} ≠ {avg_visit_min}"
            )

    # --- 8. Travel minutes consistency (recompute from warehouse) ---
    travel_min_violations = []
    if 'estimated_travel_minutes' in detailed.columns:
        for _, row in detailed.iterrows():
            wh_lat = row['warehouse_lat']
            wh_lng = row['warehouse_lng']
            dist = haversine_km(wh_lat, wh_lng, row['gps_lat'], row['gps_lng'])
            print(f"Distance: {dist}")
            expected_travel = int((dist / avg_speed_kmh) * 60)
            if abs(row['estimated_travel_minutes'] - expected_travel) > 1:
                travel_min_violations.append(
                    f"Customer {row['customer_id']}: stored travel {row['estimated_travel_minutes']} min, "
                    f"expected {expected_travel} min (dist={dist:.2f} km)"
                )

    # --- 9. Date range (month only) ---
    month_start_dt = pd.Timestamp(month_start).normalize()
    month_end_dt = (month_start_dt + pd.offsets.MonthEnd(0)).normalize()
    out_of_range = detailed[
        (detailed['schedule_date'] < month_start_dt) |
        (detailed['schedule_date'] > month_end_dt)
    ]
    date_range_violations = [f"Visit on {d.date()} outside month" for d in out_of_range['schedule_date'].unique()]

    # --- Print report ---
    checks = {
        "Cold truck requirement": cold_violations,
        "Min 1 visit per active customer": min_visit_violations,
        "Max visits per month by segment": max_visit_violations,
        "Daily customer count limit": daily_cap_violations,
        "Daily total time limit": time_limit_violations,
        "Holiday blocking": holiday_violations,
        "Visit minutes (should be 22)": visit_min_violations,
        "Travel minutes consistency": travel_min_violations,
        "Date range (within month)": date_range_violations,
    }

    total_errors = 0
    for name, violations in checks.items():
        if violations:
            print(f"\n❌ {name} – {len(violations)} violation(s):")
            for v in violations[:5]:
                print(f"   {v}")
            if len(violations) > 5:
                print(f"   ... and {len(violations)-5} more")
            total_errors += len(violations)
        else:
            print(f"✅ {name} – OK")

    if total_errors == 0:
        print("\n🎉 ALL CONSTRAINTS SATISFIED – Schedule is valid.")
    else:
        print(f"\n⚠️ {total_errors} total violation(s) found. Please fix the schedule constraints.")

    return checks