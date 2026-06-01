"""
Saudi Multi-Salesperson Constraint Scheduling
==============================================
Changes vs previous version:
  1. KMeans geographic clustering replaces round-robin assignment —
     customers nearest to each other are grouped and assigned to one salesperson.
  2. build_territory_day_map() — new function that shows ALL salespeople
     in a territory on a single folium map for a given date, each SP
     in a distinct colour with their own route line.
  3. Warehouse marker shown as first point on every map (both single-SP
     and territory-wide maps), with a home icon and "Warehouse" label.
  4. Assignment order clarified — customers are assigned to salespeople
     FIRST (geographic clustering), THEN CP-SAT builds the monthly plan.
"""

from __future__ import annotations

import calendar
import math
from dataclasses import dataclass, field
from typing import Any, Optional

import pandas as pd
from ortools.sat.python import cp_model


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SalespersonScheduleResult:
    sales_id: str
    territory_id: str
    detailed_schedule: pd.DataFrame
    daily_schedule: pd.DataFrame
    assigned_customers: pd.DataFrame


@dataclass
class MultiScheduleResult:
    detailed_schedule: pd.DataFrame
    daily_schedule: pd.DataFrame
    salesperson_results: dict[str, SalespersonScheduleResult] = field(default_factory=dict)
    # warehouse coords stored so maps can access them
    territory_warehouses: dict[str, tuple[float, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Customer-to-Salesperson Assignment  (KMeans geographic clustering)
# ---------------------------------------------------------------------------

class CustomerAssigner:
    """
    Assigns customers to salespeople by GPS proximity using KMeans clustering.

    Step 1 — cold-truck customers assigned only to cold-van salespeople
             (still clustered geographically within that subset).
    Step 2 — remaining customers assigned to all salespeople via KMeans.
    Step 3 — HIGH-tier rebalance across salespeople.

    This replaces the old round-robin-by-locality approach so that
    geographically close customers always go to the same salesperson.
    """

    def assign(
        self,
        customers: pd.DataFrame,
        salespeople: pd.DataFrame,
        van_df: pd.DataFrame,
    ) -> pd.DataFrame:
        try:
            from sklearn.cluster import KMeans
        except ImportError:
            raise ImportError("Install scikit-learn:  pip install scikit-learn")

        customers  = customers.copy()
        salespeople = salespeople[salespeople["active_status"] == True].copy()

        if salespeople.empty:
            customers["assigned_sales_id"] = None
            return customers

        # cold-truck capability map
        van_cold  = van_df.set_index("van_id")["cold_truck_enabled"].to_dict()
        sp_cold_mask = salespeople["assigned_van"].map(van_cold).fillna(False)
        salespeople = salespeople.copy()
        salespeople["cold_capable"] = sp_cold_mask.values

        cold_sp_ids = salespeople[salespeople["cold_capable"]]["sales_id"].tolist()
        all_sp_ids  = salespeople["sales_id"].tolist()

        if not all_sp_ids:
            customers["assigned_sales_id"] = None
            return customers

        cold_customers = customers[customers["cold_truck_required"] == True].copy()
        warm_customers = customers[customers["cold_truck_required"] == False].copy()

        # assign cold customers → cold-capable SPs only
        cold_pool = cold_sp_ids if cold_sp_ids else all_sp_ids
        cold_customers = self._kmeans_assign(cold_customers, cold_pool)

        # assign warm customers → all SPs
        warm_customers = self._kmeans_assign(warm_customers, all_sp_ids)

        assigned = pd.concat([cold_customers, warm_customers], ignore_index=True)
        assigned = self._rebalance_high_tier(assigned, all_sp_ids)
        return assigned

    # ------------------------------------------------------------------

    @staticmethod
    def _kmeans_assign(customers: pd.DataFrame, sp_ids: list[str]) -> pd.DataFrame:
        """
        Cluster customers into len(sp_ids) geographic clusters using KMeans,
        then assign each cluster to one salesperson.
        Customers closest to each other end up with the same salesperson.
        """
        customers = customers.copy()
        n = len(sp_ids)

        if customers.empty:
            customers["assigned_sales_id"] = None
            return customers

        if n == 1 or len(customers) <= n:
            # Not enough customers to cluster — just round-robin
            customers["assigned_sales_id"] = [
                sp_ids[i % n] for i in range(len(customers))
            ]
            return customers

        from sklearn.cluster import KMeans
        coords = customers[["gps_lat", "gps_lng"]].values
        km = KMeans(n_clusters=n, random_state=42, n_init=10)
        customers["_cluster"] = km.fit_predict(coords)

        # map cluster index → salesperson id
        cluster_to_sp = {i: sp_ids[i] for i in range(n)}
        customers["assigned_sales_id"] = customers["_cluster"].map(cluster_to_sp)
        customers = customers.drop(columns=["_cluster"])
        return customers

    @staticmethod
    def _rebalance_high_tier(customers: pd.DataFrame, sp_ids: list[str]) -> pd.DataFrame:
        """Spread HIGH-tier customers evenly — round-robin by customer_id sort."""
        if "volume_tier" not in customers.columns:
            return customers

        n = len(sp_ids)
        high_mask = customers["volume_tier"] == "HIGH"
        high = customers[high_mask].copy().sort_values("customer_id").reset_index(drop=True)
        other = customers[~high_mask].copy()
        high["assigned_sales_id"] = [sp_ids[i % n] for i in range(len(high))]
        return pd.concat([high, other], ignore_index=True)


# ---------------------------------------------------------------------------
# Holiday helpers
# ---------------------------------------------------------------------------

def get_salesperson_blocked_dates(
    sales_id: str,
    holiday_df: pd.DataFrame,
    month_start: pd.Timestamp,
    month_end: pd.Timestamp,
) -> set[pd.Timestamp]:
    blocked: set[pd.Timestamp] = set()
    hdf = holiday_df.copy()
    hdf["from_date"] = pd.to_datetime(hdf["from_date"]).dt.normalize()
    hdf["to_date"]   = pd.to_datetime(hdf["to_date"]).dt.normalize()

    for _, row in hdf[hdf["salesperson_holiday"] == sales_id].iterrows():
        cur = row["from_date"]
        while cur <= row["to_date"]:
            blocked.add(cur)
            cur += pd.Timedelta(days=1)

    return {d for d in blocked if month_start <= d <= month_end}


def get_territory_blocked_dates(
    territory_id: str,
    holiday_df: pd.DataFrame,
    month_start: pd.Timestamp,
    month_end: pd.Timestamp,
) -> set[pd.Timestamp]:
    blocked: set[pd.Timestamp] = set()
    hdf = holiday_df.copy()
    hdf["from_date"] = pd.to_datetime(hdf["from_date"]).dt.normalize()
    hdf["to_date"]   = pd.to_datetime(hdf["to_date"]).dt.normalize()

    for _, row in hdf[hdf["territory_holiday"] == territory_id].iterrows():
        cur = row["from_date"]
        while cur <= row["to_date"]:
            blocked.add(cur)
            cur += pd.Timedelta(days=1)

    return {d for d in blocked if month_start <= d <= month_end}


# ---------------------------------------------------------------------------
# RFM helpers
# ---------------------------------------------------------------------------

def get_max_visits(segment: str) -> int:
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
    if preferred_visit_day and visit_date.day_name() == preferred_visit_day:
        return preference_weights.get("day_match", 15)
    return 0


# ---------------------------------------------------------------------------
# CP-SAT solver — one salesperson, one month
# ---------------------------------------------------------------------------

class SalespersonScheduler:
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
        self.priority_weights     = priority_weights or {}
        self.preference_weights   = preference_weights or {"day_match": 15}
        self.extra_champion_bonus = extra_champion_bonus
        self.solver_time_seconds  = solver_time_seconds

    def solve(
        self,
        customers: pd.DataFrame,
        valid_dates: list[pd.Timestamp],
        daily_work_minutes: int  = DEFAULT_DAILY_WORK_MINUTES,
        avg_visit_minutes: int   = DEFAULT_AVG_VISIT_MINUTES,
        avg_speed_kmph: float    = DEFAULT_AVG_SPEED_KMPH,
        warehouse_lat: float     = 0.0,
        warehouse_lng: float     = 0.0,
        sales_id: str            = "",
        territory_id: str        = "",
    ) -> pd.DataFrame:
        model        = cp_model.CpModel()
        customer_ids = customers["customer_id"].tolist()
        empty        = self._empty_df()

        if not customer_ids or not valid_dates:
            return empty

        # per-customer time costs
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

        avg_travel      = int(sum(travel_mins.values()) / max(len(travel_mins), 1))
        time_per_visit  = max(avg_visit_minutes + avg_travel, 1)
        max_visits_per_day = max(1, daily_work_minutes // time_per_visit)

        # decision variables
        x: dict[tuple[str, pd.Timestamp], cp_model.IntVar] = {}
        for cid in customer_ids:
            for d in valid_dates:
                x[(cid, d)] = model.NewBoolVar(f"x_{cid}_{d.strftime('%Y%m%d')}")

        cust_lookup = customers.set_index("customer_id").to_dict("index")

        # per-customer visit bounds
        for cid in customer_ids:
            info      = cust_lookup[cid]
            segment   = info.get("segment", "Need Attention")
            lifecycle = info.get("lifecycle_state", "Active")
            max_v     = get_max_visits(segment)
            min_v     = 0 if lifecycle in ("Churned", "Dormant") else 1
            vars_c    = [x[(cid, d)] for d in valid_dates]
            model.Add(sum(vars_c) >= min_v)
            model.Add(sum(vars_c) <= max_v)

        # daily constraints
        for d in valid_dates:
            day_vars = [x[(cid, d)] for cid in customer_ids]
            model.Add(sum(day_vars) <= max_visits_per_day)
            model.Add(
                sum(
                    (visit_mins[cid] + travel_mins[cid]) * x[(cid, d)]
                    for cid in customer_ids
                ) <= daily_work_minutes
            )

        # objective
        obj_terms = []
        for di, d in enumerate(valid_dates):
            day_weight = 1_000_000 - di
            for cid in customer_ids:
                info    = cust_lookup[cid]
                segment = info.get("segment", "Need Attention")
                base    = self.priority_weights.get(segment, get_segment_priority_weight(segment))
                bonus   = self.extra_champion_bonus if segment == "Champion" else 0
                pref    = get_preference_weight(d, info.get("preferred_visit_day"), self.preference_weights)
                obj_terms.append(day_weight           * x[(cid, d)])
                obj_terms.append((base + bonus) * 100 * x[(cid, d)])
                obj_terms.append(pref                 * x[(cid, d)])

        model.Maximize(sum(obj_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.solver_time_seconds
        solver.parameters.num_search_workers  = 8
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return empty

        print(f"  [{sales_id}] {solver.StatusName(status)} | obj={solver.ObjectiveValue():.0f}")

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

    @staticmethod
    def _empty_df() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "schedule_date", "sales_id", "territory_id", "customer_id",
            "shop_name", "locality", "gps_lat", "gps_lng",
            "segment", "lifecycle_state", "cold_truck_required",
            "estimated_visit_minutes", "estimated_travel_minutes",
        ])


# ---------------------------------------------------------------------------
# Daily route planner (nearest-neighbour from warehouse)
# ---------------------------------------------------------------------------

class DailyRoutePlanner:
    def get_route(
        self,
        day_schedule: pd.DataFrame,
        start_lat: float,
        start_lng: float,
    ) -> pd.DataFrame:
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
    Pipeline (order matters):
    1. Merge customer + RFM data.
    2. For each territory — assign customers to salespeople via KMeans clustering
       (geographic proximity). This happens FIRST, before any scheduling.
    3. For each salesperson — compute valid dates, run CP-SAT, build daily routes.
    4. Aggregate all outputs.
    """

    def __init__(
        self,
        extra_champion_bonus: int = 30,
        solver_time_seconds:  int = 60,
    ):
        self.extra_champion_bonus = extra_champion_bonus
        self.solver_time_seconds  = solver_time_seconds
        self._assigner      = CustomerAssigner()
        self._sp_scheduler  = SalespersonScheduler(
            extra_champion_bonus=extra_champion_bonus,
            solver_time_seconds=solver_time_seconds,
        )
        self._route_planner = DailyRoutePlanner()

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

        month_start   = pd.Timestamp(month_start_date).normalize()
        year, month   = month_start.year, month_start.month
        days_in_month = calendar.monthrange(year, month)[1]
        month_end     = month_start + pd.Timedelta(days=days_in_month - 1)

        cfg = config_df.set_index("config_key")["config_value"].to_dict() if not config_df.empty else {}
        avg_speed_kmph     = float(cfg.get("avg_speed_kmh", 32))
        avg_visit_minutes  = int(float(cfg.get("avg_service_time_min", 22)))
        daily_work_minutes = 480

        full_customers = self._build_full_customer_df(customer_df, rfm_scores_df)
        ter_info       = territory_df.set_index("territory_id").to_dict("index")

        # territory-wide blocked dates (Fridays, public holidays)
        ter_blocked: dict[str, set[pd.Timestamp]] = {}
        for tid in territory_df["territory_id"]:
            ter_blocked[tid] = get_territory_blocked_dates(
                tid, holiday_df, month_start, month_end
            )

        all_detailed:  list[pd.DataFrame] = []
        sp_results:    dict[str, SalespersonScheduleResult] = {}
        ter_warehouses: dict[str, tuple[float, float]] = {}

        for _, ter_row in territory_df.iterrows():
            territory_id  = ter_row["territory_id"]
            ter_customers = full_customers[full_customers["territory_id"] == territory_id].copy()
            territory_sps = salesperson_df[salesperson_df["territory_id"] == territory_id]

            if ter_customers.empty or territory_sps.empty:
                continue

            wh_lat = float(ter_info[territory_id]["warehouse_lat"])
            wh_lng = float(ter_info[territory_id]["warehouse_lng"])
            ter_warehouses[territory_id] = (wh_lat, wh_lng)

            # ── STEP 1: assign customers to salespeople (KMeans, before scheduling) ──
            print(f"\nTerritory {territory_id}: assigning {len(ter_customers)} customers "
                  f"to {len(territory_sps)} salespeople via KMeans clustering...")
            ter_customers = self._assigner.assign(ter_customers, territory_sps, van_df)

            # print assignment summary
            for sp_id in territory_sps["sales_id"]:
                n_assigned = (ter_customers["assigned_sales_id"] == sp_id).sum()
                print(f"  {sp_id} → {n_assigned} customers assigned")

            # ── STEP 2: for each salesperson, run CP-SAT monthly plan ──
            for _, sp_row in territory_sps.iterrows():
                sales_id = sp_row["sales_id"]

                if not sp_row.get("active_status", True):
                    continue

                sp_customers = ter_customers[ter_customers["assigned_sales_id"] == sales_id].copy()
                if sp_customers.empty:
                    continue

                sp_blocked  = get_salesperson_blocked_dates(sales_id, holiday_df, month_start, month_end)
                all_blocked = ter_blocked[territory_id] | sp_blocked

                valid_dates = [
                    month_start + pd.Timedelta(days=i)
                    for i in range(days_in_month)
                    if (month_start + pd.Timedelta(days=i)) not in all_blocked
                ]
                if not valid_dates:
                    continue

                print(f"\n  Scheduling {sales_id} ({len(sp_customers)} customers, "
                      f"{len(valid_dates)} valid days)...")

                detailed = self._sp_scheduler.solve(
                    customers          = sp_customers,
                    valid_dates        = valid_dates,
                    daily_work_minutes = daily_work_minutes,
                    avg_visit_minutes  = avg_visit_minutes,
                    avg_speed_kmph     = avg_speed_kmph,
                    warehouse_lat      = wh_lat,
                    warehouse_lng      = wh_lng,
                    sales_id           = sales_id,
                    territory_id       = territory_id,
                )
                if detailed.empty:
                    continue

                daily = self._build_daily_routes(detailed, wh_lat, wh_lng)

                all_detailed.append(detailed)
                sp_results[sales_id] = SalespersonScheduleResult(
                    sales_id           = sales_id,
                    territory_id       = territory_id,
                    detailed_schedule  = detailed,
                    daily_schedule     = daily,
                    assigned_customers = sp_customers,
                )

        if all_detailed:
            combined_detailed = pd.concat(all_detailed, ignore_index=True).sort_values(
                ["territory_id", "sales_id", "schedule_date", "customer_id"]
            ).reset_index(drop=True)
        else:
            combined_detailed = SalespersonScheduler._empty_df()

        combined_daily = self._build_combined_daily(sp_results)

        return MultiScheduleResult(
            detailed_schedule    = combined_detailed,
            daily_schedule       = combined_daily,
            salesperson_results  = sp_results,
            territory_warehouses = ter_warehouses,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_full_customer_df(customer_df, rfm_scores_df):
        rfm_cols = ["customer_id", "recency", "frequency", "monetary",
                    "r_score", "f_score", "m_score", "rfm_score", "segment"]
        rfm_use  = [c for c in rfm_cols if c in rfm_scores_df.columns]
        merged   = customer_df.merge(rfm_scores_df[rfm_use], on="customer_id", how="left")
        merged["segment"] = merged["segment"].fillna("Need Attention")
        return merged

    def _build_daily_routes(self, detailed, wh_lat, wh_lng):
        rows = []
        for (sales_id, sched_date), group in detailed.groupby(["sales_id", "schedule_date"]):
            routed = self._route_planner.get_route(group.copy(), wh_lat, wh_lng)
            rows.append({
                "schedule_date":    sched_date,
                "sales_id":         sales_id,
                "territory_id":     group["territory_id"].iloc[0],
                "customer_list":    routed["customer_id"].tolist(),
                "customer_count":   len(routed),
                "route_order":      routed["shop_name"].tolist(),
                "total_visit_min":  int(routed["estimated_visit_minutes"].sum()),
                "total_travel_min": int(routed["estimated_travel_minutes"].sum()),
            })
        if not rows:
            return pd.DataFrame(columns=[
                "schedule_date", "sales_id", "territory_id",
                "customer_list", "customer_count", "route_order",
                "total_visit_min", "total_travel_min",
            ])
        return pd.DataFrame(rows).sort_values(["sales_id", "schedule_date"]).reset_index(drop=True)

    @staticmethod
    def _build_combined_daily(sp_results):
        parts = [r.daily_schedule for r in sp_results.values() if not r.daily_schedule.empty]
        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, ignore_index=True).sort_values(
            ["territory_id", "sales_id", "schedule_date"]
        ).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Folium map — single salesperson, single day  (warehouse shown as stop 0)
# ---------------------------------------------------------------------------

# distinct colours per salesperson slot (used by both map functions)
_SP_COLOURS = ["red", "blue", "green", "purple", "orange", "darkred",
               "cadetblue", "darkgreen", "darkpurple", "black"]

SEGMENT_COLOUR = {
    "Champion":           "red",
    "Loyal":              "blue",
    "Potential Loyalist": "green",
    "At Risk":            "orange",
    "Need Attention":     "purple",
    "Hibernating":        "gray",
}


def _add_warehouse_marker(m, wh_lat: float, wh_lng: float, label: str = "Warehouse"):
    """Add a distinct warehouse / start-point marker to a folium map."""
    import folium
    folium.Marker(
        [wh_lat, wh_lng],
        icon=folium.Icon(color="black", icon="home", prefix="fa"),
        tooltip=f"🏭 {label} (start / end)",
        popup=f"<b>{label}</b><br>Start and end of route",
    ).add_to(m)


def _get_ordered_day_df(
    detailed_schedule: pd.DataFrame,
    daily_schedule: pd.DataFrame,
    sales_id: str,
    sched_date: pd.Timestamp,
) -> pd.DataFrame:
    """Return the day's visits sorted by route_rank, computing rank if missing."""
    day_df = detailed_schedule[
        (detailed_schedule["sales_id"]      == sales_id) &
        (detailed_schedule["schedule_date"] == sched_date)
    ].copy()

    if day_df.empty:
        return day_df

    if "route_rank" not in day_df.columns:
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

    return day_df.sort_values("route_rank").reset_index(drop=True)


def build_route_map_for_salesperson(
    daily_schedule:    pd.DataFrame,
    detailed_schedule: pd.DataFrame,
    sales_id:          str,
    schedule_date:     str | pd.Timestamp,
    warehouse_lat:     float = 0.0,
    warehouse_lng:     float = 0.0,
    zoom_start:        int   = 12,
):
    """
    Folium map for ONE salesperson on ONE day.
    Route always starts from the warehouse marker (stop 0).
    Customer markers are numbered 1, 2, 3… and coloured by RFM segment.
    """
    try:
        import folium
        from folium.plugins import PolyLineTextPath
    except ImportError:
        raise ImportError("pip install folium")

    sched_date = pd.Timestamp(schedule_date).normalize()
    day_df     = _get_ordered_day_df(detailed_schedule, daily_schedule, sales_id, sched_date)

    if day_df.empty:
        raise ValueError(f"No visits for {sales_id} on {sched_date.date()}")

    # centre map on customers
    center_lat = day_df["gps_lat"].mean()
    center_lng = day_df["gps_lng"].mean()
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start)

    # warehouse marker (start point)
    if warehouse_lat != 0.0 or warehouse_lng != 0.0:
        _add_warehouse_marker(m, warehouse_lat, warehouse_lng)
        route_coords = [[warehouse_lat, warehouse_lng]] + day_df[["gps_lat", "gps_lng"]].values.tolist()
    else:
        route_coords = day_df[["gps_lat", "gps_lng"]].values.tolist()

    # customer markers
    for _, row in day_df.iterrows():
        color = SEGMENT_COLOUR.get(str(row.get("segment", "")), "blue")
        folium.Marker(
            [row["gps_lat"], row["gps_lng"]],
            icon=folium.DivIcon(
                html=f"""<div style="background:{color};color:white;border-radius:50%;
                         width:26px;height:26px;text-align:center;line-height:26px;
                         font-weight:bold;font-size:11px;">{row['route_rank']}</div>""",
            ),
            tooltip=(
                f"{row['route_rank']}. {row.get('shop_name','')} "
                f"[{row.get('segment','')}] {row.get('locality','')} "
                f"– Cold: {row.get('cold_truck_required','?')}"
            ),
        ).add_to(m)

    # route line with direction arrows
    line = folium.PolyLine(route_coords, weight=3, color="navy")
    m.add_child(line)
    PolyLineTextPath(
        line, "➤", repeat=True, offset=7,
        attributes={"fill": "red", "font-size": "14"},
    ).add_to(m)

    # title
    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed;top:10px;left:60px;z-index:1000;
                background:white;padding:8px 12px;border-radius:6px;
                border:1px solid #ccc;font-family:sans-serif;">
        <b>{sales_id}</b> — {sched_date.strftime('%d %b %Y')} &nbsp;|&nbsp; {len(day_df)} stops
    </div>"""))

    return m


# ---------------------------------------------------------------------------
# Folium map — ALL salespeople in a territory on a single map for one day
# ---------------------------------------------------------------------------

def build_territory_day_map(
    result:        MultiScheduleResult,
    territory_id:  str,
    schedule_date: str | pd.Timestamp,
    zoom_start:    int = 11,
):
    """
    Shows ALL salespeople in one territory on a single folium map for a given date.

    - Each salesperson gets a distinct colour for both their markers and route line.
    - Warehouse is shown once as a black home-icon marker (start point for all SPs).
    - Customer markers are numbered per-salesperson (1, 2, 3…) in their SP colour.
    - A legend is shown in the top-right corner.

    Parameters
    ----------
    result        : MultiScheduleResult returned by create_schedules()
    territory_id  : e.g. "TER_RUH"
    schedule_date : e.g. "2026-06-09"
    zoom_start    : folium zoom level

    Returns
    -------
    folium.Map
    """
    try:
        import folium
        from folium.plugins import PolyLineTextPath
    except ImportError:
        raise ImportError("pip install folium")

    sched_date = pd.Timestamp(schedule_date).normalize()

    # collect salespeople in this territory that have visits today
    territory_sp_ids = [
        sid for sid, sp in result.salesperson_results.items()
        if sp.territory_id == territory_id
    ]

    if not territory_sp_ids:
        raise ValueError(f"No salespeople found for territory {territory_id}")

    # warehouse for this territory
    wh_lat, wh_lng = result.territory_warehouses.get(territory_id, (0.0, 0.0))

    # collect all customer coords to centre map
    all_lats, all_lngs = [], []
    sp_day_data: dict[str, pd.DataFrame] = {}

    for sales_id in territory_sp_ids:
        sp = result.salesperson_results[sales_id]
        day_df = _get_ordered_day_df(
            sp.detailed_schedule, sp.daily_schedule, sales_id, sched_date
        )
        if not day_df.empty:
            sp_day_data[sales_id] = day_df
            all_lats.extend(day_df["gps_lat"].tolist())
            all_lngs.extend(day_df["gps_lng"].tolist())

    if not sp_day_data:
        raise ValueError(
            f"No visits found in territory {territory_id} on {sched_date.date()}"
        )

    # centre on mean of all visited customers
    center_lat = sum(all_lats) / len(all_lats)
    center_lng = sum(all_lngs) / len(all_lngs)
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start)

    # warehouse marker (one for the whole territory)
    if wh_lat != 0.0 or wh_lng != 0.0:
        _add_warehouse_marker(m, wh_lat, wh_lng, label=f"Warehouse ({territory_id})")

    # assign a colour to each salesperson
    sp_colour_map = {
        sid: _SP_COLOURS[i % len(_SP_COLOURS)]
        for i, sid in enumerate(sorted(sp_day_data.keys()))
    }

    legend_items = []

    for sales_id, day_df in sp_day_data.items():
        sp_color = sp_colour_map[sales_id]

        # route: warehouse → customers in order
        if wh_lat != 0.0 or wh_lng != 0.0:
            route_coords = [[wh_lat, wh_lng]] + day_df[["gps_lat", "gps_lng"]].values.tolist()
        else:
            route_coords = day_df[["gps_lat", "gps_lng"]].values.tolist()

        # customer markers (numbered circles in SP colour)
        for _, row in day_df.iterrows():
            folium.Marker(
                [row["gps_lat"], row["gps_lng"]],
                icon=folium.DivIcon(
                    html=f"""<div style="background:{sp_color};color:white;
                             border-radius:50%;width:26px;height:26px;
                             text-align:center;line-height:26px;
                             font-weight:bold;font-size:11px;
                             border:2px solid white;">{row['route_rank']}</div>""",
                ),
                tooltip=(
                    f"[{sales_id}] {row['route_rank']}. {row.get('shop_name','')} "
                    f"[{row.get('segment','')}] – Cold: {row.get('cold_truck_required','?')}"
                ),
            ).add_to(m)

        # route line
        line = folium.PolyLine(route_coords, weight=3, color=sp_color, opacity=0.8)
        m.add_child(line)
        PolyLineTextPath(
            line, "➤", repeat=True, offset=7,
            attributes={"fill": sp_color, "font-size": "13"},
        ).add_to(m)

        legend_items.append(
            f'<li><span style="background:{sp_color};width:14px;height:14px;'
            f'display:inline-block;border-radius:50%;margin-right:6px;"></span>'
            f'{sales_id} ({len(day_df)} stops)</li>'
        )

    # legend box
    legend_html = f"""
    <div style="position:fixed;top:10px;right:10px;z-index:1000;
                background:white;padding:10px 14px;border-radius:8px;
                border:1px solid #ccc;font-family:sans-serif;font-size:12px;
                min-width:200px;">
        <b>{territory_id}</b> — {sched_date.strftime('%d %b %Y')}<br>
        <ul style="list-style:none;margin:6px 0 0;padding:0;">
            {''.join(legend_items)}
            <li style="margin-top:6px;">
                <span style="background:black;width:14px;height:14px;
                display:inline-block;border-radius:50%;margin-right:6px;"></span>
                Warehouse
            </li>
        </ul>
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R    = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))