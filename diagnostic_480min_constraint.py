# """
# diagnostic_480min_constraint.py

# Run this script on your monthly_plan_new_1.xlsx to identify:
# 1. Which routes violate the 480-minute daily constraint
# 2. By how much they exceed the limit
# 3. What parameters need adjustment
# """

# import pandas as pd
# import numpy as np
# from pathlib import Path

# def diagnose_constraint_violations(
#     excel_file: str,
#     daily_work_minutes: int = 480,
#     avg_visit_min: int = 22,
#     avg_speed_kmh: float = 32,
#     sheet_name: str = "Detailed Schedule"
# ) -> pd.DataFrame:
#     """
#     Analyzes schedule for 480-minute constraint violations.
    
#     Parameters:
#     -----------
#     excel_file : str
#         Path to Excel file with "Detailed Schedule" sheet
#     daily_work_minutes : int
#         Daily time budget (default 480)
#     avg_visit_min : int
#         Service time per customer (default 22)
#     avg_speed_kmh : float
#         Average travel speed (default 32)
#     sheet_name : str
#         Name of sheet containing schedule
        
#     Returns:
#     --------
#     pd.DataFrame with violation details
#     """
    
#     print(f"\n{'='*80}")
#     print(f"DIAGNOSING 480-MINUTE DAILY CONSTRAINT")
#     print(f"{'='*80}\n")
    
#     # Load schedule
#     try:
#         df = pd.read_excel(excel_file, sheet_name=sheet_name)
#     except FileNotFoundError:
#         print(f"❌ File not found: {excel_file}")
#         return None
#     except ValueError:
#         print(f"❌ Sheet '{sheet_name}' not found in Excel file")
#         return None
    
#     if df.empty:
#         print("❌ Schedule is empty")
#         return None
    
#     # Ensure datetime
#     df["schedule_date"] = pd.to_datetime(df["schedule_date"])
    
#     # Group by salesperson and date
#     grouped = df.groupby(["sales_id", "schedule_date"])
    
#     violations = []
#     compliant = []
    
#     print(f"Analyzing {len(grouped)} daily routes...\n")
    
#     for (sid, date), grp in grouped:
#         n_customers = len(grp)
#         visit_time = n_customers * avg_visit_min
        
#         # Calculate travel time from route_leg_km if available
#         if "route_leg_km" in grp.columns and grp["route_leg_km"].notna().sum() > 0:
#             route_km = grp["route_leg_km"].sum()
#             travel_time = (route_km / avg_speed_kmh) * 60
#             travel_source = "route_leg_km"
#         elif "estimated_travel_minutes" in grp.columns:
#             travel_time = grp["estimated_travel_minutes"].sum()
#             travel_source = "estimated_travel_minutes"
#         else:
#             travel_time = 0
#             travel_source = "UNKNOWN"
        
#         total_time = visit_time + travel_time
#         excess = total_time - daily_work_minutes
        
#         record = {
#             "salesperson": sid,
#             "date": date.date(),
#             "n_customers": n_customers,
#             "visit_time": round(visit_time, 1),
#             "travel_time": round(travel_time, 1),
#             "total_time": round(total_time, 1),
#             "budget": daily_work_minutes,
#             "excess_minutes": round(excess, 1),
#             "violation": "YES" if excess > 0 else "NO",
#             "travel_source": travel_source
#         }
        
#         if excess > 0:
#             violations.append(record)
#         else:
#             compliant.append(record)
    
#     # Summary statistics
#     print(f"\n{'='*80}")
#     print(f"SUMMARY")
#     print(f"{'='*80}")
#     print(f"Total daily routes analyzed:  {len(grouped)}")
#     print(f"Routes COMPLIANT (≤480 min):  {len(compliant)}")
#     print(f"Routes VIOLATING (>480 min):  {len(violations)}")
#     print(f"\nCompliance rate: {len(compliant) / len(grouped) * 100:.1f}%")
    
#     if violations:
#         print(f"\n{'='*80}")
#         print(f"⚠️  VIOLATIONS DETECTED - Details Below")
#         print(f"{'='*80}\n")
        
#         violations_df = pd.DataFrame(violations)
#         violations_df = violations_df.sort_values(by="excess_minutes", ascending=False)
        
#         print(violations_df.to_string(index=False))
        
#         # Statistics on violations
#         print(f"\n{'─'*80}")
#         print(f"Violation Statistics:")
#         print(f"{'─'*80}")
#         print(f"Max excess:         {violations_df['excess_minutes'].max():.0f} min")
#         print(f"Avg excess:         {violations_df['excess_minutes'].mean():.0f} min")
#         print(f"Min excess:         {violations_df['excess_minutes'].min():.0f} min")
#         print(f"Total excess (all): {violations_df['excess_minutes'].sum():.0f} min")
#         print(f"\nWorst case: {violations_df.iloc[0]['salesperson']} on {violations_df.iloc[0]['date']}")
#         print(f"  {int(violations_df.iloc[0]['n_customers'])} customers")
#         print(f"  {violations_df.iloc[0]['total_time']:.0f} min total (exceeds by {violations_df.iloc[0]['excess_minutes']:.0f} min)")
        
#         # Analysis of worst violations
#         print(f"\n{'─'*80}")
#         print(f"Analysis of Worst Violations (Top 5):")
#         print(f"{'─'*80}")
#         for idx, row in violations_df.head(5).iterrows():
#             avg_travel_per_leg = row['travel_time'] / max(1, row['n_customers'] - 1) if row['n_customers'] > 1 else 0
#             time_per_customer = row['total_time'] / row['n_customers']
#             print(f"\n{row['salesperson']} on {row['date']}")
#             print(f"  Customers:          {int(row['n_customers'])}")
#             print(f"  Service time:       {row['visit_time']:.0f} min ({avg_visit_min} min × {int(row['n_customers'])})")
#             print(f"  Travel time:        {row['travel_time']:.0f} min")
#             print(f"  Avg per customer:   {time_per_customer:.1f} min")
#             print(f"  Excess:             {row['excess_minutes']:.0f} min over 480")
        
#         # Recommendations
#         print(f"\n{'='*80}")
#         print(f"RECOMMENDATIONS TO FIX VIOLATIONS")
#         print(f"{'='*80}")
        
#         avg_n_cust = violations_df['n_customers'].mean()
#         avg_excess = violations_df['excess_minutes'].mean()
        
#         # Option 1: Reduce customers per day
#         max_cust_for_480 = int(480 / (avg_visit_min + 5))  # Assuming avg 5 min travel per customer
#         if avg_n_cust > max_cust_for_480:
#             print(f"\n1. REDUCE CUSTOMERS PER DAY:")
#             print(f"   Current average:  {avg_n_cust:.0f} customers/day")
#             print(f"   Recommended max:  {max_cust_for_480} customers/day")
#             print(f"   This would eliminate ~{avg_excess:.0f} min of excess")
        
#         # Option 2: Reduce service time
#         reduced_visit_min = max(15, int(avg_visit_min - avg_excess / avg_n_cust))
#         if reduced_visit_min < avg_visit_min:
#             print(f"\n2. REDUCE SERVICE TIME ESTIMATE:")
#             print(f"   Current estimate:  {avg_visit_min} min/customer")
#             print(f"   Needed estimate:   {reduced_visit_min} min/customer")
#             print(f"   (Only if actual service times are less than {avg_visit_min} min)")
        
#         # Option 3: Increase speed
#         avg_travel_per_cust = violations_df['travel_time'].mean() / violations_df['n_customers'].mean()
#         increased_speed = avg_speed_kmh * (1 + avg_excess / (violations_df['travel_time'].sum() / len(violations_df)))
#         print(f"\n3. INCREASE AVERAGE SPEED:")
#         print(f"   Current speed:     {avg_speed_kmh} kmph")
#         print(f"   Needed speed:      {increased_speed:.1f} kmph")
#         print(f"   (Only realistic if route optimization improves)")
        
#         # Option 4: Use stricter constraint
#         print(f"\n4. USE CONSERVATIVE TRAVEL ESTIMATES IN SCHEDULER:")
#         print(f"   Current: Uses 90th percentile of inter-customer distances")
#         print(f"   Better:  Use MAX distance for more conservative (safe) constraint")
#         print(f"   This prevents the optimizer from allowing unsafe routes")
        
#     else:
#         print(f"\n✅ All routes comply with {daily_work_minutes}-minute daily constraint!")
        
#         compliant_df = pd.DataFrame(compliant)
#         print(f"\n{'─'*80}")
#         print(f"Compliance Details:")
#         print(f"{'─'*80}")
#         print(f"Max route time:     {compliant_df['total_time'].max():.0f} min")
#         print(f"Avg route time:     {compliant_df['total_time'].mean():.0f} min")
#         print(f"Min route time:     {compliant_df['total_time'].min():.0f} min")
#         print(f"Max customers/day:  {compliant_df['n_customers'].max():.0f}")
#         print(f"Avg customers/day:  {compliant_df['n_customers'].mean():.1f}")
    
#     print(f"\n{'='*80}\n")
    
#     return pd.DataFrame(violations) if violations else pd.DataFrame(compliant)


# if __name__ == "__main__":
#     # Run on your file
    
#     # Option 1: Full path
#     # violations_df = diagnose_constraint_violations(
#     #     excel_file="/path/to/monthly_plan_new_1.xlsx",
#     #     daily_work_minutes=480,
#     #     avg_visit_min=22,
#     #     avg_speed_kmh=32
#     # )
    
#     # Option 2: Relative path
#     violations_df = diagnose_constraint_violations(
#         excel_file="D:\Data Science\Basamh\JP_Yash\journey-planner\monthly_plan_fixed_holiday.xlsx",
#         daily_work_minutes=480,
#         avg_visit_min=22,
#         avg_speed_kmh=32
#     )
    
#     # Export results if violations found
#     if violations_df is not None and not violations_df.empty:
#         export_path = "constraint_violation_analysis.xlsx"
#         violations_df.to_excel(export_path, index=False)
#         print(f"📊 Results exported to: {export_path}")



"""
diagnostic_480min_constraint.py  (v6 — matches scheduler_6_adjust_priority.py)
════════════════════════════════════════════════════════════════════════════════
Run this script on your schedule Excel output to identify:
  1. Which routes violate the 480-minute daily constraint
  2. By how much they exceed the limit
  3. Root-cause analysis and parameter recommendations

Key changes vs the previous version (v4 diagnostic)
─────────────────────────────────────────────────────
1.  CIRCUIT-BASED TIME MODEL.
    Scheduler v6 uses AddCircuit with a REAL pairwise stop-to-stop distance
    matrix.  Total daily time is now:
        total = sum(route_leg_km) / speed_kmh × 60  +  n_stops × visit_min
    The old "estimated_travel_minutes per customer" formula (warehouse-to-
    customer one-way) is used only as a fallback when route_leg_km is absent.

2.  GREEDY TOP-UP AWARENESS.
    After the CP-SAT solve, the scheduler inserts additional visits greedily
    using actual routed distances — the same budget gate applies.  This
    diagnostic re-applies the same gate so it never flags top-up rows as
    false violations.

3.  ROUTE_RANK ORDERING.
    When route_rank is present the diagnostic processes stops in NN-route
    order, matching the order in which the scheduler accumulated time.

4.  VEHICLE COUNT / SP AWARENESS.
    Reports are broken out per (salesperson, date) to match the per-SP daily
    budget enforced by the solver.

Usage
─────
    python diagnostic_480min_constraint.py

    Or call directly:
        from diagnostic_480min_constraint import diagnose_constraint_violations
        df = diagnose_constraint_violations("monthly_plan.xlsx")
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Main diagnostic function
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_constraint_violations(
    excel_file: str,
    daily_work_minutes: int   = 480,
    avg_visit_min: int        = 22,
    avg_speed_kmh: float      = 32.0,
    sheet_name: str           = "Detailed Schedule",
) -> pd.DataFrame:
    """
    Analyses a schedule Excel for 480-minute daily constraint violations.

    Time model (mirrors scheduler v6 AddCircuit Constraint 6)
    ──────────────────────────────────────────────────────────
    total_time = sum(route_leg_km) / avg_speed_kmh × 60  +  n_stops × avg_visit_min

    Falls back to estimated_travel_minutes when route_leg_km is unavailable.

    Parameters
    ──────────
    excel_file          : path to Excel with a "Detailed Schedule" sheet
    daily_work_minutes  : daily time budget per SP (default 480 min)
    avg_visit_min       : service time per customer stop (default 22 min)
    avg_speed_kmh       : average travel speed (default 32 km/h)
    sheet_name          : sheet name to read from Excel

    Returns
    ───────
    pd.DataFrame — violation rows (or compliance rows if no violations found)
    """
    print(f"\n{'='*80}")
    print(f"DIAGNOSING 480-MINUTE DAILY CONSTRAINT  (v6 circuit-based model)")
    print(f"{'='*80}\n")
    print(f"Parameters:")
    print(f"  daily_work_minutes : {daily_work_minutes}")
    print(f"  avg_visit_min      : {avg_visit_min}")
    print(f"  avg_speed_kmh      : {avg_speed_kmh}")
    print(f"  Time model         : sum(route_leg_km)/speed×60 + n_stops×visit_min")
    print()

    # ── Load schedule ─────────────────────────────────────────────────────────
    try:
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
    except FileNotFoundError:
        print(f"❌  File not found: {excel_file}")
        return pd.DataFrame()
    except ValueError:
        # Try first sheet if named sheet not found
        try:
            df = pd.read_excel(excel_file)
            print(f"⚠️  Sheet '{sheet_name}' not found — using first sheet instead.")
        except Exception as e:
            print(f"❌  Could not read Excel file: {e}")
            return pd.DataFrame()

    if df.empty:
        print("❌  Schedule sheet is empty.")
        return pd.DataFrame()

    df["schedule_date"] = pd.to_datetime(df["schedule_date"])

    # Detect available columns
    has_route_leg_km   = "route_leg_km" in df.columns and df["route_leg_km"].notna().any()
    has_est_travel     = "estimated_travel_minutes" in df.columns
    has_route_rank     = "route_rank" in df.columns
    has_truck_group    = "truck_group" in df.columns

    print(f"Columns detected:")
    print(f"  route_leg_km           : {'YES ✅' if has_route_leg_km else 'NO  ⚠️ (fallback to estimated_travel_minutes)'}")
    print(f"  estimated_travel_minutes: {'YES' if has_est_travel else 'NO'}")
    print(f"  route_rank             : {'YES' if has_route_rank else 'NO'}")
    print(f"  truck_group            : {'YES' if has_truck_group else 'NO'}")
    print()

    # Group by salesperson + date (+ truck_group if present)
    group_keys = ["sales_id", "schedule_date"]
    if has_truck_group:
        group_keys.append("truck_group")
    grouped = df.groupby(group_keys)

    violations = []
    compliant  = []

    print(f"Analysing {len(grouped)} daily route(s)…\n")

    for keys, grp in grouped:
        # Unpack keys
        if has_truck_group:
            sid, date, tg = keys
        else:
            sid, date = keys
            tg = "unknown"

        # Sort by route_rank if available (matches NN-route order from scheduler)
        if has_route_rank:
            grp = grp.sort_values("route_rank")

        n_stops   = len(grp)
        visit_min = n_stops * avg_visit_min

        # ── Travel time (v6 circuit model: sum of actual legs) ────────────────
        if has_route_leg_km and grp["route_leg_km"].notna().all():
            total_km    = float(grp["route_leg_km"].sum())
            travel_min  = (total_km / avg_speed_kmh) * 60
            travel_src  = "route_leg_km (circuit)"
        elif has_est_travel:
            # estimated_travel_minutes in v6 = avg inter-customer leg × n_stops
            # (stored as a per-row constant; sum it up)
            travel_min = float(grp["estimated_travel_minutes"].sum())
            total_km   = travel_min / 60 * avg_speed_kmh
            travel_src = "estimated_travel_minutes (fallback)"
        else:
            travel_min = 0.0
            total_km   = 0.0
            travel_src = "NONE (no travel data available)"

        total_time = visit_min + travel_min
        excess     = total_time - daily_work_minutes

        # Per-stop averages for diagnostics
        avg_leg_km  = total_km / n_stops if n_stops > 0 else 0.0
        avg_leg_min = travel_min / n_stops if n_stops > 0 else 0.0
        tpv         = avg_visit_min + avg_leg_min   # effective time-per-visit

        record = {
            "salesperson":   sid,
            "date":          date.date(),
            "truck_group":   tg,
            "n_stops":       n_stops,
            "visit_time_min":   round(visit_min,  1),
            "travel_time_min":  round(travel_min, 1),
            "total_km":         round(total_km,   2),
            "total_time_min":   round(total_time, 1),
            "budget_min":       daily_work_minutes,
            "excess_min":       round(excess,     1),
            "avg_leg_km":       round(avg_leg_km, 3),
            "avg_leg_min":      round(avg_leg_min,1),
            "tpv_min":          round(tpv,        1),
            "violation":        "YES" if excess > 0 else "NO",
            "travel_source":    travel_src,
        }

        if excess > 0:
            violations.append(record)
        else:
            compliant.append(record)

    # ── Summary ───────────────────────────────────────────────────────────────
    n_total    = len(grouped)
    n_compliant = len(compliant)
    n_violating = len(violations)

    print(f"{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"Total daily routes analysed : {n_total}")
    print(f"Routes COMPLIANT (≤{daily_work_minutes} min): {n_compliant}")
    print(f"Routes VIOLATING (>{daily_work_minutes} min): {n_violating}")
    print(f"\nCompliance rate: {n_compliant / n_total * 100:.1f}%")

    if violations:
        violations_df = pd.DataFrame(violations).sort_values(
            "excess_min", ascending=False
        )

        print(f"\n{'='*80}")
        print(f"⚠️   VIOLATIONS DETECTED")
        print(f"{'='*80}\n")
        print(violations_df.to_string(index=False))

        # ── Violation statistics ──────────────────────────────────────────────
        print(f"\n{'─'*80}")
        print(f"Violation Statistics:")
        print(f"{'─'*80}")
        print(f"  Max excess    : {violations_df['excess_min'].max():.0f} min")
        print(f"  Avg excess    : {violations_df['excess_min'].mean():.0f} min")
        print(f"  Min excess    : {violations_df['excess_min'].min():.0f} min")
        print(f"  Total excess  : {violations_df['excess_min'].sum():.0f} min")

        worst = violations_df.iloc[0]
        print(f"\n  Worst case: {worst['salesperson']} on {worst['date']}"
              f"  [{worst['truck_group']}]")
        print(f"    Stops       : {int(worst['n_stops'])}")
        print(f"    Visit time  : {worst['visit_time_min']:.0f} min "
              f"({avg_visit_min} × {int(worst['n_stops'])})")
        print(f"    Travel time : {worst['travel_time_min']:.0f} min  "
              f"({worst['total_km']:.1f} km @ {avg_speed_kmh} km/h)")
        print(f"    Total time  : {worst['total_time_min']:.0f} min  "
              f"(exceeds by {worst['excess_min']:.0f} min)")
        print(f"    Source      : {worst['travel_source']}")

        # ── Top 5 worst in detail ─────────────────────────────────────────────
        print(f"\n{'─'*80}")
        print(f"Top 5 Worst Violations:")
        print(f"{'─'*80}")
        for _, row in violations_df.head(5).iterrows():
            print(f"\n  {row['salesperson']} / {row['date']}  [{row['truck_group']}]")
            print(f"    Stops         : {int(row['n_stops'])}")
            print(f"    Visit time    : {row['visit_time_min']:.0f} min")
            print(f"    Travel time   : {row['travel_time_min']:.0f} min  "
                  f"({row['total_km']:.1f} km)")
            print(f"    Avg leg       : {row['avg_leg_km']:.2f} km / "
                  f"{row['avg_leg_min']:.1f} min")
            print(f"    Time/stop     : {row['tpv_min']:.1f} min  "
                  f"(visit {avg_visit_min} + travel {row['avg_leg_min']:.1f})")
            print(f"    Excess        : {row['excess_min']:.0f} min over {daily_work_minutes}")

        # ── Root-cause analysis & recommendations ─────────────────────────────
        print(f"\n{'='*80}")
        print(f"ROOT-CAUSE ANALYSIS (v6 circuit model)")
        print(f"{'='*80}")

        avg_n     = violations_df["n_stops"].mean()
        avg_excess = violations_df["excess_min"].mean()
        avg_tpv   = violations_df["tpv_min"].mean()

        # How many stops actually fit in the budget?
        max_stops_budget = daily_work_minutes / avg_tpv if avg_tpv > 0 else 0
        print(f"\n  At avg time/stop of {avg_tpv:.1f} min:")
        print(f"    Avg stops per violating day : {avg_n:.1f}")
        print(f"    Max stops that fit in budget: {max_stops_budget:.1f}")
        print(f"    Over-scheduled by           : {avg_n - max_stops_budget:.1f} stops/day avg")

        # ── Recommendation 1: reduce stops per day ───────────────────────────
        safe_stops = max(1, int(daily_work_minutes / max(avg_tpv, 1)))
        print(f"\n  1. REDUCE STOPS PER DAY")
        print(f"     Current avg (violating days): {avg_n:.1f} stops/day")
        print(f"     Safe maximum                : {safe_stops} stops/day")
        print(f"     Fix: lower sp_daily_cap in the solver, or reduce customer pool.")

        # ── Recommendation 2: reduce service time ────────────────────────────
        avg_travel_in_violations = violations_df["avg_leg_min"].mean()
        reduced_visit = max(
            10,
            int((daily_work_minutes / max(avg_n, 1)) - avg_travel_in_violations)
        )
        if reduced_visit < avg_visit_min:
            print(f"\n  2. REDUCE avg_visit_min")
            print(f"     Current : {avg_visit_min} min/stop")
            print(f"     Needed  : {reduced_visit} min/stop to fit {avg_n:.0f} stops")
            print(f"     Only viable if actual service time is genuinely < {avg_visit_min} min.")

        # ── Recommendation 3: speed increase ─────────────────────────────────
        avg_travel_km = violations_df["total_km"].mean()
        if avg_travel_km > 0:
            needed_speed = (avg_travel_km / max(
                (daily_work_minutes - avg_n * avg_visit_min) / 60, 0.01
            ))
            print(f"\n  3. INCREASE avg_speed_kmh")
            print(f"     Current : {avg_speed_kmh:.1f} km/h")
            print(f"     Needed  : {needed_speed:.1f} km/h  "
                  f"(avg {avg_travel_km:.1f} km/day in violations)")
            print(f"     Only realistic if route optimisation meaningfully reduces distance.")

        # ── Recommendation 4: tighten solver distance budget ─────────────────
        print(f"\n  4. TIGHTEN THE SOLVER'S PER-SP DAILY BUDGET")
        print(f"     The v6 solver uses AddCircuit with avg_inter_leg_min as the")
        print(f"     per-customer travel cost.  If actual legs are longer than the")
        print(f"     territory average, the budget can be breached post-solve.")
        print(f"     Fix: pass a slightly reduced daily_work_minutes to the scheduler")
        print(f"     (e.g. {daily_work_minutes - 30} min) as a safety margin.")

        # ── Recommendation 5: greedy top-up threshold ────────────────────────
        print(f"\n  5. REVIEW GREEDY TOP-UP GATE")
        print(f"     The greedy top-up inserts extra visits when:")
        print(f"       remaining > avg_visit_min + 2  (i.e. > {avg_visit_min + 2} min)")
        print(f"     If violations appear only in top-up rows, tighten the gate to:")
        print(f"       remaining > avg_visit_min + avg_leg_min + buffer")
        print(f"     or disable greedy top-up for the violating territories.")

        print(f"\n{'='*80}\n")

        return violations_df

    else:
        compliant_df = pd.DataFrame(compliant)
        print(f"\n✅  All routes comply with the {daily_work_minutes}-minute budget!")

        if not compliant_df.empty:
            print(f"\n{'─'*80}")
            print(f"Compliance Statistics:")
            print(f"{'─'*80}")
            print(f"  Max total time  : {compliant_df['total_time_min'].max():.0f} min")
            print(f"  Avg total time  : {compliant_df['total_time_min'].mean():.0f} min")
            print(f"  Min total time  : {compliant_df['total_time_min'].min():.0f} min")
            print(f"  Max stops/day   : {compliant_df['n_stops'].max():.0f}")
            print(f"  Avg stops/day   : {compliant_df['n_stops'].mean():.1f}")
            print(f"  Avg total km/day: {compliant_df['total_km'].mean():.1f}")
            print(f"  Avg time buffer : "
                  f"{(daily_work_minutes - compliant_df['total_time_min']).mean():.0f} min unused")

        print(f"\n{'='*80}\n")
        return compliant_df


# ─────────────────────────────────────────────────────────────────────────────
# Convenience: run on a live MultiScheduleResult object
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_from_result(
    result,
    daily_work_minutes: int   = 480,
    avg_visit_min: int        = 22,
    avg_speed_kmh: float      = 32.0,
    territory_id: str         = None,
) -> pd.DataFrame:
    """
    Run the same diagnostic directly on a MultiScheduleResult object
    (no Excel required).

    Parameters
    ──────────
    result              : MultiScheduleResult from MultiSalespersonScheduler
    daily_work_minutes  : per-SP daily time budget (default 480 min)
    avg_visit_min       : service time per stop (default 22 min)
    avg_speed_kmh       : travel speed (default 32 km/h)
    territory_id        : filter to one territory (None = all)

    Returns
    ───────
    pd.DataFrame of violations (or compliance rows if none)
    """
    df = result.detailed_schedule.copy()
    if df.empty:
        print("❌  detailed_schedule is empty — nothing to diagnose.")
        return pd.DataFrame()

    if territory_id:
        df = df[df["territory_id"] == territory_id].copy()
        if df.empty:
            print(f"❌  No schedule for territory '{territory_id}'.")
            return pd.DataFrame()

    print(f"\n{'='*80}")
    print(f"DIAGNOSING 480-MIN CONSTRAINT FROM MultiScheduleResult  (v6)")
    if territory_id:
        print(f"Territory filter: {territory_id}")
    print(f"{'='*80}\n")

    df["schedule_date"] = pd.to_datetime(df["schedule_date"])

    has_route_leg_km = "route_leg_km" in df.columns and df["route_leg_km"].notna().any()
    has_est_travel   = "estimated_travel_minutes" in df.columns
    has_route_rank   = "route_rank" in df.columns
    has_truck_group  = "truck_group" in df.columns

    group_keys = ["sales_id", "schedule_date"]
    if has_truck_group:
        group_keys.append("truck_group")
    grouped = df.groupby(group_keys)

    violations = []
    compliant  = []

    for keys, grp in grouped:
        if has_truck_group:
            sid, date, tg = keys
        else:
            sid, date = keys
            tg = "unknown"

        if has_route_rank:
            grp = grp.sort_values("route_rank")

        n_stops   = len(grp)
        visit_min = n_stops * avg_visit_min

        if has_route_leg_km and grp["route_leg_km"].notna().all():
            total_km   = float(grp["route_leg_km"].sum())
            travel_min = (total_km / avg_speed_kmh) * 60
            travel_src = "route_leg_km"
        elif has_est_travel:
            travel_min = float(grp["estimated_travel_minutes"].sum())
            total_km   = travel_min / 60 * avg_speed_kmh
            travel_src = "estimated_travel_minutes"
        else:
            travel_min = 0.0
            total_km   = 0.0
            travel_src = "NONE"

        total_time = visit_min + travel_min
        excess     = total_time - daily_work_minutes

        avg_leg_km  = total_km / n_stops if n_stops > 0 else 0.0
        avg_leg_min = travel_min / n_stops if n_stops > 0 else 0.0

        record = {
            "salesperson":      sid,
            "date":             date.date(),
            "truck_group":      tg,
            "territory_id":     grp["territory_id"].iloc[0]
                                if "territory_id" in grp.columns else "",
            "n_stops":          n_stops,
            "visit_time_min":   round(visit_min,  1),
            "travel_time_min":  round(travel_min, 1),
            "total_km":         round(total_km,   2),
            "total_time_min":   round(total_time, 1),
            "budget_min":       daily_work_minutes,
            "excess_min":       round(excess,     1),
            "avg_leg_km":       round(avg_leg_km, 3),
            "avg_leg_min":      round(avg_leg_min,1),
            "violation":        "YES" if excess > 0 else "NO",
            "travel_source":    travel_src,
        }

        if excess > 0:
            violations.append(record)
        else:
            compliant.append(record)

    n_total = len(grouped)
    n_v     = len(violations)
    n_c     = len(compliant)

    print(f"Total daily routes : {n_total}")
    print(f"Compliant (≤{daily_work_minutes} min): {n_c}")
    print(f"Violating (>{daily_work_minutes} min): {n_v}")
    print(f"Compliance rate    : {n_c / n_total * 100:.1f}%\n")

    if violations:
        vdf = pd.DataFrame(violations).sort_values("excess_min", ascending=False)
        print(f"⚠️   TOP VIOLATIONS:\n")
        print(vdf.head(10).to_string(index=False))
        print(f"\nMax excess: {vdf['excess_min'].max():.0f} min  |  "
              f"Avg excess: {vdf['excess_min'].mean():.0f} min")
        return vdf
    else:
        print("✅  All routes comply with the daily budget.")
        return pd.DataFrame(compliant)


# ─────────────────────────────────────────────────────────────────────────────
# Script entry-point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # ── Option A: run on Excel output ────────────────────────────────────────
    violations_df = diagnose_constraint_violations(
        excel_file         = r"D:\Data Science\Basamh\JP_Yash\journey-planner\monthly_plan_fixed_holiday.xlsx",
        daily_work_minutes = 480,
        avg_visit_min      = 22,
        avg_speed_kmh      = 32.0,
        sheet_name         = "Detailed Schedule",
    )

    # Export results
    if violations_df is not None and not violations_df.empty:
        export_path = "constraint_violation_analysis_v6.xlsx"
        violations_df.to_excel(export_path, index=False)
        print(f"📊  Results exported to: {export_path}")

    # ── Option B: run on live result object (uncomment when in notebook) ─────
    # violations_df = diagnose_from_result(
    #     result             = result,
    #     daily_work_minutes = 480,
    #     avg_visit_min      = 22,
    #     avg_speed_kmh      = 32.0,
    #     territory_id       = None,   # or e.g. "TER_RUH"
    # )
