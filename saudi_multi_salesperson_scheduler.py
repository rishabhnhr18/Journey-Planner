"""
Saudi Multi-Salesperson Constraint Scheduling
==============================================
Extends the JP Replication single-salesperson constraint scheduler to handle
multiple salespeople per territory (Saudi master data structure).

Key differences vs JP Replication:
  - Each territory has N salespeople (e.g. 3)
  - Each salesperson has their own daily capacity, leave holidays, and van constraints
  - Customers are partitioned across salespeople (by locality / RFM / cold-truck match)
  - Each salesperson gets their own CP-SAT monthly plan and daily nearest-neighbor route
  - Outputs: per-salesperson detailed schedule, daily summary, and folium route maps

Entry point:
    outputs, report = generate_all(seed=42)   # from saudi_master_data_generator
    result = MultiSalespersonScheduler().create_schedules(
        customer_df   = customer_df,
        rfm_scores_df = rfm_scores_df,
        salesperson_df= salesperson_df,
        holiday_df    = holiday_df,
        territory_df  = territory_df,
        config_df     = config_df,
        month_start_date = "2026-06-01",
    )
    result.detailed_schedule   # one row per (salesperson, customer, visit date)
    result.daily_schedule      # daily summary per salesperson
    result.salesperson_routes  # dict[sales_id -> dict[date -> ranked DataFrame]]
"""

from __future__ import annotations

import ast
import calendar
import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

import pandas as pd
from ortools.sat.python import cp_model


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SalespersonScheduleResult:
    """Holds results for one salesperson."""
    sales_id: str
    territory_id: str
    detailed_schedule: pd.DataFrame      # rows: (schedule_date, customer_id, ...)
    daily_schedule: pd.DataFrame          # rows: (schedule_date, customer_list, count, minutes)
    assigned_customers: pd.DataFrame      # customers assigned to this salesperson


@dataclass
class MultiScheduleResult:
    """Aggregated result across all salespeople and territories."""
    detailed_schedule: pd.DataFrame       # all salespeople combined
    daily_schedule: pd.DataFrame          # all salespeople combined
    salesperson_results: dict[str, SalespersonScheduleResult] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Customer-to-Salesperson Assignment
# ---------------------------------------------------------------------------

class CustomerAssigner:
    """
    Assigns customers in a territory to salespeople.

    Strategy (in priority order):
    1. Cold-truck customers → salespeople whose van is cold_truck_enabled.
    2. Geographic clustering: customers in the same locality → same salesperson
       where possible (round-robin by locality).
    3. RFM-balanced load: after locality grouping, rebalance so each salesperson
       has a similar mix of HIGH / MED / LOW volume-tier customers.
    """

    def assign(
        self,
        customers: pd.DataFrame,
        salespeople: pd.DataFrame,
        van_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Returns customers with an extra column  ``assigned_sales_id``.
        """
        customers = customers.copy()
        salespeople = salespeople[salespeople["active_status"] == True].copy()

        if salespeople.empty:
            # Fallback: use all salespeople even inactive ones
            salespeople = salespeople.copy()

        # Build cold-truck capability map
        van_cold = van_df.set_index("van_id")["cold_truck_enabled"].to_dict()
        sp_cold = salespeople["assigned_van"].map(van_cold).fillna(False)
        salespeople["cold_capable"] = sp_cold.values

        cold_sps = salespeople[salespeople["cold_capable"]]["sales_id"].tolist()
        all_sp_ids = salespeople["sales_id"].tolist()

        if not all_sp_ids:
            customers["assigned_sales_id"] = None
            return customers

        n_sp = len(all_sp_ids)

        # Step 1: Handle cold-truck-required customers
        cold_customers = customers[customers["cold_truck_required"] == True].copy()
        warm_customers = customers[customers["cold_truck_required"] == False].copy()

        # Assign cold customers to cold-capable SPs (round-robin)
        cold_pool = cold_sps if cold_sps else all_sp_ids
        cold_customers = self._round_robin_by_locality(cold_customers, cold_pool)

        # Step 2: Assign warm customers to all SPs (round-robin by locality)
        warm_customers = self._round_robin_by_locality(warm_customers, all_sp_ids)

        # Combine
        assigned = pd.concat([cold_customers, warm_customers], ignore_index=True)

        # Step 3: Rebalance HIGH-tier customers across SPs
        assigned = self._rebalance_high_tier(assigned, all_sp_ids)

        return assigned

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _round_robin_by_locality(
        self, customers: pd.DataFrame, sp_ids: list[str]
    ) -> pd.DataFrame:
        """Assign customers locality-first, then round-robin within each locality."""
        if customers.empty or not sp_ids:
            customers = customers.copy()
            customers["assigned_sales_id"] = sp_ids[0] if sp_ids else None
            return customers

        n = len(sp_ids)
        locality_col = "locality" if "locality" in customers.columns else "territory_id"
        customers = customers.copy().sort_values([locality_col, "customer_id"]).reset_index(drop=True)
        customers["assigned_sales_id"] = [sp_ids[i % n] for i in range(len(customers))]
        return customers

    def _rebalance_high_tier(
        self, customers: pd.DataFrame, sp_ids: list[str]
    ) -> pd.DataFrame:
        """Redistribute HIGH-tier customers more evenly across salespeople."""
        if "volume_tier" not in customers.columns:
            return customers

        high_mask = customers["volume_tier"] == "HIGH"
        high_cust = customers[high_mask].copy()
        other_cust = customers[~high_mask].copy()

        # Sort high-tier by assigned SP and redistribute evenly
        n = len(sp_ids)
        high_cust = high_cust.sort_values("customer_id").reset_index(drop=True)
        high_cust["assigned_sales_id"] = [sp_ids[i % n] for i in range(len(high_cust))]

        return pd.concat([high_cust, other_cust], ignore_index=True)


# ---------------------------------------------------------------------------
# Per-salesperson holiday helper
# ---------------------------------------------------------------------------

def get_salesperson_blocked_dates(
    sales_id: str,
    holiday_df: pd.DataFrame,
    month_start: pd.Timestamp,
    month_end: pd.Timestamp,
) -> set[pd.Timestamp]:
    """
    Returns a set of dates in [month_start, month_end] that this salesperson
    cannot work, combining:
      - Territory-wide closures (Fridays, public holidays)
      - Salesperson-specific leave
      - Van maintenance days for their assigned van (van is unavailable)

    holiday_df columns: holiday_id, salesperson_holiday, van_holiday,
                        territory_holiday, from_date, to_date, reason
    """
    blocked: set[pd.Timestamp] = set()

    # Normalise dates
    hdf = holiday_df.copy()
    hdf["from_date"] = pd.to_datetime(hdf["from_date"]).dt.normalize()
    hdf["to_date"]   = pd.to_datetime(hdf["to_date"]).dt.normalize()

    def expand(row) -> list[pd.Timestamp]:
        return [
            pd.Timestamp(row["from_date"]) + pd.Timedelta(days=i)
            for i in range((row["to_date"] - row["from_date"]).days + 1)
        ]

    # Salesperson-specific leave
    sp_leave = hdf[hdf["salesperson_holiday"] == sales_id]
    for _, row in sp_leave.iterrows():
        blocked.update(expand(row))

    return {d for d in blocked if month_start <= d <= month_end}


def get_territory_blocked_dates(
    territory_id: str,
    holiday_df: pd.DataFrame,
    month_start: pd.Timestamp,
    month_end: pd.Timestamp,
) -> set[pd.Timestamp]:
    """Territory-wide blocked dates (Fridays + public holidays)."""
    blocked: set[pd.Timestamp] = set()
    hdf = holiday_df.copy()
    hdf["from_date"] = pd.to_datetime(hdf["from_date"]).dt.normalize()
    hdf["to_date"]   = pd.to_datetime(hdf["to_date"]).dt.normalize()

    ter_rows = hdf[hdf["territory_holiday"] == territory_id]
    for _, row in ter_rows.iterrows():
        cur = row["from_date"]
        while cur <= row["to_date"]:
            blocked.add(cur)
            cur += pd.Timedelta(days=1)

    return {d for d in blocked if month_start <= d <= month_end}


# ---------------------------------------------------------------------------
# RFM helpers (maps Saudi segment names → visit limits)
# ---------------------------------------------------------------------------

def get_max_visits(segment: str) -> int:
    """
    Saudi segments: Champion, Loyal, Potential Loyalist, At Risk,
                    Hibernating, Need Attention.
    Map to visit limits consistent with JP Replication logic.
    """
    return {
        "Champion":           4,
        "Loyal":              3,
        "Potential Loyalist": 2,
        "At Risk":            2,
        "Need Attention":     2,
        "Hibernating":        1,
    }.get(segment, 1)


def get_segment_priority_weight(segment: str) -> int:
    return {
        "Champion":           120,
        "Loyal":              100,
        "Potential Loyalist":  70,
        "At Risk":             50,
        "Need Attention":      40,
        "Hibernating":         10,
    }.get(segment, 10)


def get_preference_weight(
    visit_date: pd.Timestamp,
    preferred_visit_day: Optional[str],
    preference_weights: dict[str, int],
) -> int:
    """Single preferred weekday (Saudi data has preferred_visit_day per customer)."""
    if preferred_visit_day and visit_date.day_name() == preferred_visit_day:
        return preference_weights.get("day_match", 15)
    return 0


# ---------------------------------------------------------------------------
# Core per-salesperson CP-SAT solver
# ---------------------------------------------------------------------------

class SalespersonScheduler:
    """
    Solves a monthly visit schedule for one salesperson using CP-SAT.
    Mirrors ConstraintScheduling._solve_territory_schedule() from JP Replication
    but uses per-salesperson parameters.
    """

    # Salesperson-level daily capacity: derived from working hours / service time
    DEFAULT_DAILY_WORK_MINUTES = 480
    DEFAULT_AVG_VISIT_MINUTES  = 22
    DEFAULT_AVG_SPEED_KMPH     = 32

    def __init__(
        self,
        priority_weights: Optional[dict[str, int]] = None,
        preference_weights: Optional[dict[str, int]] = None,
        extra_champion_bonus: int = 30,
        solver_time_seconds: int = 60,
    ):
        self.priority_weights    = priority_weights or {}
        self.preference_weights  = preference_weights or {"day_match": 15}
        self.extra_champion_bonus = extra_champion_bonus
        self.solver_time_seconds  = solver_time_seconds

    def solve(
        self,
        customers: pd.DataFrame,
        valid_dates: list[pd.Timestamp],
        daily_work_minutes: int = DEFAULT_DAILY_WORK_MINUTES,
        avg_visit_minutes: int  = DEFAULT_AVG_VISIT_MINUTES,
        avg_speed_kmph: float   = DEFAULT_AVG_SPEED_KMPH,
        warehouse_lat: float    = 0.0,
        warehouse_lng: float    = 0.0,
        sales_id: str           = "",
        territory_id: str       = "",
    ) -> pd.DataFrame:
        """
        Returns detailed schedule DataFrame for one salesperson.
        Columns: schedule_date, sales_id, territory_id, customer_id,
                 shop_name, gps_lat, gps_lng, segment, rfm_score,
                 estimated_visit_minutes, estimated_travel_minutes
        """
        model = cp_model.CpModel()

        customer_ids = customers["customer_id"].tolist()
        n_customers  = len(customer_ids)
        n_dates      = len(valid_dates)

        empty = self._empty_df()

        if n_customers == 0 or n_dates == 0:
            return empty

        # ---- Compute per-customer time cost ----
        visit_mins:  dict[str, int] = {}
        travel_mins: dict[str, int] = {}

        for _, cust in customers.iterrows():
            cid = cust["customer_id"]
            visit_mins[cid] = avg_visit_minutes
            dist_km = _haversine_km(
                warehouse_lat, warehouse_lng,
                float(cust["gps_lat"]), float(cust["gps_lng"]),
            )
            travel_mins[cid] = int((dist_km * 2 / avg_speed_kmph) * 60)

        # ---- Derive daily visit capacity from working hours ----
        # Max customers per day = floor(work_minutes / (visit + avg_travel))
        avg_travel = int(sum(travel_mins.values()) / max(len(travel_mins), 1))
        time_per_visit = max(avg_visit_minutes + avg_travel, 1)
        max_visits_per_day = max(1, daily_work_minutes // time_per_visit)

        # ---- Decision variables ----
        x: dict[tuple[str, pd.Timestamp], cp_model.IntVar] = {}
        for cid in customer_ids:
            for d in valid_dates:
                x[(cid, d)] = model.NewBoolVar(f"x_{cid}_{d.strftime('%Y%m%d')}")

        # ---- Per-customer visit bounds ----
        cust_lookup = customers.set_index("customer_id").to_dict("index")

        for cid in customer_ids:
            info    = cust_lookup[cid]
            segment = info.get("segment", "Need Attention")
            max_v   = get_max_visits(segment)
            vars_c  = [x[(cid, d)] for d in valid_dates]

            # Every active customer gets at least 1 visit
            lifecycle = info.get("lifecycle_state", "Active")
            min_v = 0 if lifecycle in ("Churned", "Dormant") else 1

            model.Add(sum(vars_c) >= min_v)
            model.Add(sum(vars_c) <= max_v)

        # ---- Daily constraints ----
        for d in valid_dates:
            day_vars = [x[(cid, d)] for cid in customer_ids]

            # Hard daily visit count cap
            model.Add(sum(day_vars) <= max_visits_per_day)

            # Working-time constraint (visit + travel for each scheduled customer)
            model.Add(
                sum(
                    (visit_mins[cid] + travel_mins[cid]) * x[(cid, d)]
                    for cid in customer_ids
                ) <= daily_work_minutes
            )

        # ---- Objective ----
        obj_terms = []
        for di, d in enumerate(valid_dates):
            day_weight = 1_000_000 - di  # prefer earlier dates

            for cid in customer_ids:
                info    = cust_lookup[cid]
                segment = info.get("segment", "Need Attention")

                base   = self.priority_weights.get(segment, get_segment_priority_weight(segment))
                bonus  = self.extra_champion_bonus if segment == "Champion" else 0
                pref   = get_preference_weight(
                    d,
                    info.get("preferred_visit_day"),
                    self.preference_weights,
                )

                obj_terms.append(day_weight          * x[(cid, d)])
                obj_terms.append((base + bonus) * 100 * x[(cid, d)])
                obj_terms.append(pref              * x[(cid, d)])

        model.Maximize(sum(obj_terms))

        # ---- Solve ----
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.solver_time_seconds
        solver.parameters.num_search_workers  = 8

        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return empty

        print("Status:", solver.StatusName(status))
        print("Objective value:", solver.ObjectiveValue())   # higher = better schedule
        print("Best bound:", solver.BestObjectiveBound())    # theoretical maximum possibl

        # ---- Extract solution ----
        rows: list[dict[str, Any]] = []
        for cid in customer_ids:
            for d in valid_dates:
                if solver.Value(x[(cid, d)]) == 1:
                    info = cust_lookup[cid]
                    rows.append({
                        "schedule_date":            d,
                        "sales_id":                 sales_id,
                        "territory_id":             territory_id,
                        "customer_id":              cid,
                        "shop_name":                info.get("shop_name", ""),
                        "locality":                 info.get("locality", ""),
                        "gps_lat":                  info.get("gps_lat"),
                        "gps_lng":                  info.get("gps_lng"),
                        "segment":                  info.get("segment", ""),
                        "lifecycle_state":          info.get("lifecycle_state", ""),
                        "cold_truck_required":      info.get("cold_truck_required", False),
                        "estimated_visit_minutes":  visit_mins[cid],
                        "estimated_travel_minutes": travel_mins[cid],
                    })

        if not rows:
            return empty

        return (
            pd.DataFrame(rows)
            .sort_values(["schedule_date", "customer_id"])
            .reset_index(drop=True)
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _empty_df() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "schedule_date", "sales_id", "territory_id", "customer_id",
            "shop_name", "locality", "gps_lat", "gps_lng",
            "segment", "lifecycle_state", "cold_truck_required",
            "estimated_visit_minutes", "estimated_travel_minutes",
        ])


# ---------------------------------------------------------------------------
# Daily route planner (nearest-neighbour, identical to JP Replication)
# ---------------------------------------------------------------------------

class DailyRoutePlanner:
    """
    Computes a nearest-neighbour route for a salesperson on a single day,
    starting from the warehouse.
    """

    def get_route(
        self,
        day_schedule: pd.DataFrame,
        start_lat: float,
        start_lng: float,
    ) -> pd.DataFrame:
        """
        Returns day_schedule with an added ``route_rank`` column.
        """
        if day_schedule.empty:
            return day_schedule.copy()

        unvisited = day_schedule.copy().reset_index(drop=True)
        route: list[dict] = []

        current_lat, current_lng = start_lat, start_lng

        while not unvisited.empty:
            distances = unvisited.apply(
                lambda row: _haversine_km(
                    current_lat, current_lng,
                    float(row["gps_lat"]), float(row["gps_lng"]),
                ),
                axis=1,
            )
            nearest_idx = int(distances.idxmin())
            row = unvisited.loc[nearest_idx]
            route.append(row.to_dict())
            current_lat = float(row["gps_lat"])
            current_lng = float(row["gps_lng"])
            unvisited = unvisited.drop(index=nearest_idx).reset_index(drop=True)

        result = pd.DataFrame(route)
        result["route_rank"] = range(1, len(result) + 1)
        return result


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class MultiSalespersonScheduler:
    """
    Orchestrates the full multi-salesperson scheduling pipeline:

    1. Generate all master data (passed in from saudi_master_data_generator).
    2. Join customer + RFM data.
    3. For each territory:
        a. Assign customers to salespeople (CustomerAssigner).
        b. For each salesperson:
            i.  Compute valid working dates (territory holidays ∪ SP leave).
            ii. Run CP-SAT solver (SalespersonScheduler).
            iii. Build nearest-neighbour daily routes (DailyRoutePlanner).
    4. Aggregate all outputs.
    """

    def __init__(
        self,
        extra_champion_bonus: int = 30,
        solver_time_seconds:  int = 60,
    ):
        self.extra_champion_bonus = extra_champion_bonus
        self.solver_time_seconds  = solver_time_seconds
        self._assigner    = CustomerAssigner()
        self._sp_scheduler = SalespersonScheduler(
            extra_champion_bonus=extra_champion_bonus,
            solver_time_seconds=solver_time_seconds,
        )
        self._route_planner = DailyRoutePlanner()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def create_schedules(
        self,
        customer_df:    pd.DataFrame,
        rfm_scores_df:  pd.DataFrame,
        salesperson_df: pd.DataFrame,
        holiday_df:     pd.DataFrame,
        territory_df:   pd.DataFrame,
        config_df:      pd.DataFrame,
        van_df:         pd.DataFrame,
        month_start_date: str | pd.Timestamp = "2026-06-01",
    ) -> MultiScheduleResult:
        """
        Main entry point. Returns a MultiScheduleResult.
        """
        month_start = pd.Timestamp(month_start_date).normalize()
        year, month = month_start.year, month_start.month
        days_in_month = calendar.monthrange(year, month)[1]
        month_end = month_start + pd.Timedelta(days=days_in_month - 1)

        # ---- Read config ----
        cfg = config_df.set_index("config_key")["config_value"].to_dict() if not config_df.empty else {}
        avg_speed_kmph     = float(cfg.get("avg_speed_kmh", 32))
        avg_visit_minutes  = int(float(cfg.get("avg_service_time_min", 22)))
        daily_work_minutes = 480   # 8 hours default; could be in config

        # ---- Merge customer + RFM ----
        full_customers = self._build_full_customer_df(customer_df, rfm_scores_df)

        # ---- Warehouse coordinates per territory ----
        ter_info = territory_df.set_index("territory_id").to_dict("index")

        # ---- Territory-level blocked dates ----
        ter_blocked: dict[str, set[pd.Timestamp]] = {}
        for tid in territory_df["territory_id"]:
            ter_blocked[tid] = get_territory_blocked_dates(
                tid, holiday_df, month_start, month_end
            )

        # ---- All salespeople indexed ----
        sp_lookup = salesperson_df.set_index("sales_id").to_dict("index")

        # ---- Per-territory processing ----
        all_detailed: list[pd.DataFrame] = []
        sp_results:   dict[str, SalespersonScheduleResult] = {}

        for territory_id, ter_row in territory_df.iterrows():
            territory_id = ter_row["territory_id"]
            ter_customers = full_customers[full_customers["territory_id"] == territory_id].copy()
            territory_sps = salesperson_df[salesperson_df["territory_id"] == territory_id]

            if ter_customers.empty or territory_sps.empty:
                continue

            # ---- Assign customers to salespeople ----
            ter_customers = self._assigner.assign(ter_customers, territory_sps, van_df)

            wh_lat = float(ter_info[territory_id]["warehouse_lat"])
            wh_lng = float(ter_info[territory_id]["warehouse_lng"])

            # ---- Schedule each salesperson ----
            for _, sp_row in territory_sps.iterrows():
                sales_id = sp_row["sales_id"]

                if not sp_row.get("active_status", True):
                    continue

                sp_customers = ter_customers[ter_customers["assigned_sales_id"] == sales_id].copy()

                if sp_customers.empty:
                    continue

                # Valid working dates: territory blocked + salesperson leave
                sp_blocked = get_salesperson_blocked_dates(
                    sales_id, holiday_df, month_start, month_end
                )
                all_blocked = ter_blocked[territory_id] | sp_blocked

                valid_dates = [
                    month_start + pd.Timedelta(days=i)
                    for i in range(days_in_month)
                    if (month_start + pd.Timedelta(days=i)) not in all_blocked
                ]

                if not valid_dates:
                    continue

                # Run CP-SAT
                detailed = self._sp_scheduler.solve(
                    customers         = sp_customers,
                    valid_dates       = valid_dates,
                    daily_work_minutes= daily_work_minutes,
                    avg_visit_minutes = avg_visit_minutes,
                    avg_speed_kmph    = avg_speed_kmph,
                    warehouse_lat     = wh_lat,
                    warehouse_lng     = wh_lng,
                    sales_id          = sales_id,
                    territory_id      = territory_id,
                )

                if detailed.empty:
                    continue

                # Build daily nearest-neighbour routes
                daily = self._build_daily_routes(detailed, wh_lat, wh_lng)

                all_detailed.append(detailed)
                sp_results[sales_id] = SalespersonScheduleResult(
                    sales_id           = sales_id,
                    territory_id       = territory_id,
                    detailed_schedule  = detailed,
                    daily_schedule     = daily,
                    assigned_customers = sp_customers,
                )

        # ---- Combine ----
        if all_detailed:
            combined_detailed = pd.concat(all_detailed, ignore_index=True).sort_values(
                ["territory_id", "sales_id", "schedule_date", "customer_id"]
            ).reset_index(drop=True)
        else:
            combined_detailed = SalespersonScheduler._empty_df()

        combined_daily = self._build_combined_daily(sp_results)

        return MultiScheduleResult(
            detailed_schedule  = combined_detailed,
            daily_schedule     = combined_daily,
            salesperson_results= sp_results,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_full_customer_df(
        customer_df: pd.DataFrame,
        rfm_scores_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Merge customer master with RFM scores."""
        rfm_cols = ["customer_id", "recency", "frequency", "monetary",
                    "r_score", "f_score", "m_score", "rfm_score", "segment"]
        rfm_use  = [c for c in rfm_cols if c in rfm_scores_df.columns]

        merged = customer_df.merge(
            rfm_scores_df[rfm_use],
            on="customer_id",
            how="left",
        )
        merged["segment"] = merged["segment"].fillna("Need Attention")
        return merged

    def _build_daily_routes(
        self,
        detailed: pd.DataFrame,
        wh_lat: float,
        wh_lng: float,
    ) -> pd.DataFrame:
        """
        For each (sales_id, schedule_date) group, compute nearest-neighbour route
        and return a daily summary DataFrame.
        """
        rows = []
        for (sales_id, sched_date), group in detailed.groupby(["sales_id", "schedule_date"]):
            routed = self._route_planner.get_route(group.copy(), wh_lat, wh_lng)
            rows.append({
                "schedule_date":   sched_date,
                "sales_id":        sales_id,
                "territory_id":    group["territory_id"].iloc[0],
                "customer_list":   routed["customer_id"].tolist(),
                "customer_count":  len(routed),
                "route_order":     routed["shop_name"].tolist(),
                "total_visit_min": int(routed["estimated_visit_minutes"].sum()),
                "total_travel_min":int(routed["estimated_travel_minutes"].sum()),
            })

        if not rows:
            return pd.DataFrame(columns=[
                "schedule_date", "sales_id", "territory_id",
                "customer_list", "customer_count", "route_order",
                "total_visit_min", "total_travel_min",
            ])

        return pd.DataFrame(rows).sort_values(["sales_id", "schedule_date"]).reset_index(drop=True)

    @staticmethod
    def _build_combined_daily(
        sp_results: dict[str, SalespersonScheduleResult],
    ) -> pd.DataFrame:
        parts = [r.daily_schedule for r in sp_results.values() if not r.daily_schedule.empty]
        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, ignore_index=True).sort_values(
            ["territory_id", "sales_id", "schedule_date"]
        ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Folium map builder
# ---------------------------------------------------------------------------

def build_route_map_for_salesperson(
    daily_schedule: pd.DataFrame,
    detailed_schedule: pd.DataFrame,
    sales_id: str,
    schedule_date: str | pd.Timestamp,
    zoom_start: int = 12,
):
    """
    Builds a folium map showing the nearest-neighbour route for one
    salesperson on one date.

    Requires: pip install folium

    Returns: folium.Map
    """
    try:
        import folium
        from folium.plugins import PolyLineTextPath
    except ImportError:
        raise ImportError("Install folium:  pip install folium")

    sched_date = pd.Timestamp(schedule_date).normalize()

    day_df = detailed_schedule[
        (detailed_schedule["sales_id"]      == sales_id) &
        (detailed_schedule["schedule_date"] == sched_date)
    ].copy()

    if day_df.empty:
        raise ValueError(f"No visits for {sales_id} on {sched_date.date()}")

    # Re-order by route_rank if present, else use order as-is
    if "route_rank" not in day_df.columns:
        # Recompute route order from daily_schedule
        day_row = daily_schedule[
            (daily_schedule["sales_id"]      == sales_id) &
            (daily_schedule["schedule_date"] == sched_date)
        ]
        if not day_row.empty:
            ordered_ids = day_row.iloc[0]["customer_list"]
            order_map   = {cid: i for i, cid in enumerate(ordered_ids)}
            day_df["route_rank"] = day_df["customer_id"].map(order_map).fillna(99).astype(int) + 1
        else:
            day_df["route_rank"] = range(1, len(day_df) + 1)

    day_df = day_df.sort_values("route_rank").reset_index(drop=True)

    center_lat = day_df["gps_lat"].mean()
    center_lng = day_df["gps_lng"].mean()

    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start)

    coords = day_df[["gps_lat", "gps_lng"]].values.tolist()

    for _, row in day_df.iterrows():
        segment_color = {
            "Champion":           "red",
            "Loyal":              "blue",
            "Potential Loyalist": "green",
            "At Risk":            "orange",
            "Need Attention":     "purple",
            "Hibernating":        "gray",
        }.get(str(row.get("segment", "")), "blue")

        folium.Marker(
            [row["gps_lat"], row["gps_lng"]],
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    background:{segment_color};
                    color:white;
                    border-radius:50%;
                    width:26px;
                    height:26px;
                    text-align:center;
                    line-height:26px;
                    font-weight:bold;
                    font-size:11px;
                ">{row['route_rank']}</div>
                """,
            ),
            tooltip=(
                f"{row['route_rank']}. {row.get('shop_name','')} "
                f"[{row.get('segment','')}] {row.get('locality','')} "
                f"– Cold: {row.get('cold_truck_required','?')}"
            ),
        ).add_to(m)

    line = folium.PolyLine(coords, weight=3, color="navy")
    m.add_child(line)

    PolyLineTextPath(
        line, "➤", repeat=True, offset=7,
        attributes={"fill": "red", "font-size": "14"},
    ).add_to(m)

    title_html = f"""
    <div style="position:fixed;top:10px;left:60px;z-index:1000;
                background:white;padding:8px 12px;border-radius:6px;
                border:1px solid #ccc;font-family:sans-serif;">
        <b>{sales_id}</b> — {sched_date.strftime('%d %b %Y')} &nbsp;|&nbsp;
        {len(day_df)} stops
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    return m


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Quick-start usage example
# ---------------------------------------------------------------------------

USAGE_EXAMPLE = """
# ── 1. Generate master data ──────────────────────────────────────────────
from saudi_master_data_generator import generate_all
outputs, report = generate_all(seed=42)

territory_df    = outputs["territory"]
salesperson_df  = outputs["salesperson"]
van_df          = outputs["van"]
customer_df     = outputs["customer"]
holiday_df      = outputs["holiday"]
config_df       = outputs["config"]
rfm_scores_df   = outputs["rfm_scores"]

# ── 2. Run multi-salesperson scheduler ───────────────────────────────────
from saudi_multi_salesperson_scheduler import MultiSalespersonScheduler

scheduler = MultiSalespersonScheduler(
    extra_champion_bonus=30,
    solver_time_seconds=60,
)

result = scheduler.create_schedules(
    customer_df     = customer_df,
    rfm_scores_df   = rfm_scores_df,
    salesperson_df  = salesperson_df,
    holiday_df      = holiday_df,
    territory_df    = territory_df,
    config_df       = config_df,
    van_df          = van_df,
    month_start_date= "2026-06-01",
)

# ── 3. Inspect outputs ───────────────────────────────────────────────────
print(result.detailed_schedule.head(20))
print(result.daily_schedule.head(20))

# Per-salesperson results
for sales_id, sp_result in result.salesperson_results.items():
    print(f"\\n=== {sales_id} ({sp_result.territory_id}) ===")
    print(f"  Assigned customers : {len(sp_result.assigned_customers)}")
    print(f"  Scheduled visits   : {len(sp_result.detailed_schedule)}")
    print(f"  Working days       : {sp_result.daily_schedule['schedule_date'].nunique()}")

# ── 4. Export ─────────────────────────────────────────────────────────────
result.detailed_schedule.to_csv("multi_sp_detailed_schedule.csv", index=False)
result.daily_schedule.to_csv("multi_sp_daily_schedule.csv", index=False)

# ── 5. Folium route map for one salesperson, one day ─────────────────────
from saudi_multi_salesperson_scheduler import build_route_map_for_salesperson

m = build_route_map_for_salesperson(
    daily_schedule    = result.daily_schedule,
    detailed_schedule = result.detailed_schedule,
    sales_id          = "SAL_RUH_001",
    schedule_date     = "2026-06-03",
)
m   # display in Jupyter
"""

if __name__ == "__main__":
    print(USAGE_EXAMPLE)