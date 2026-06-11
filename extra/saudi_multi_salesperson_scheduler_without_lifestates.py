"""
Saudi Multi-Salesperson Constraint Scheduling
==============================================
Updated to use the new RFM scoring system:

  Old segments  →  New segments
  ─────────────────────────────────────────────────────────────
  Champion / Loyal / Potential Loyalist  →  High
  At Risk / Need Attention               →  Medium
  Hibernating                            →  Low

  Key RFM columns used from rfm_scores_df:
    rfm_segment_final   : "High" | "Medium" | "Low"
    final_customer_score: 0-1 continuous score (used for priority weight)
    rfm_combined        : mean(r_score, f_score, m_score)
    customer_rank       : within-territory rank (1 = best)

  Scheduling behaviour by segment:
    High   → up to 4 visits/month, highest priority weight
    Medium → up to 2 visits/month, medium priority weight
    Low    → up to 1 visit/month,  lowest priority weight

  Priority weight within each segment is further refined by
  final_customer_score so that a High customer with score 0.95
  is scheduled before one with score 0.71.

Changes vs previous version:
  1. KMeans geographic clustering replaces round-robin assignment.
  2. build_territory_day_map() — all salespeople in a territory on one map.
  3. Warehouse marker shown as first point on every map.
  4. Assignment order: customers assigned to salespeople FIRST (geographic
     clustering), THEN CP-SAT builds the monthly plan.
  5. RFM integration updated to new segment/score architecture.
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
    territory_warehouses: dict[str, tuple[float, float]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Customer-to-Salesperson Assignment  (KMeans geographic clustering)
# ---------------------------------------------------------------------------

class CustomerAssigner:
    """
    Assigns customers to salespeople by GPS proximity using KMeans clustering.

    Step 1 — cold-truck customers assigned only to cold-van salespeople.
    Step 2 — remaining customers assigned to all salespeople via KMeans.
    Step 3 — HIGH-segment rebalance across salespeople.
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

        customers   = customers.copy()
        salespeople = salespeople[salespeople["active_status"] == True].copy()

        if salespeople.empty:
            customers["assigned_sales_id"] = None
            return customers

        van_cold     = van_df.set_index("van_id")["cold_truck_enabled"].to_dict()
        sp_cold_mask = salespeople["assigned_van"].map(van_cold).fillna(False)
        salespeople  = salespeople.copy()
        salespeople["cold_capable"] = sp_cold_mask.values

        cold_sp_ids = salespeople[salespeople["cold_capable"]]["sales_id"].tolist()
        all_sp_ids  = salespeople["sales_id"].tolist()

        if not all_sp_ids:
            customers["assigned_sales_id"] = None
            return customers

        cold_customers = customers[customers["cold_truck_required"] == True].copy()
        warm_customers = customers[customers["cold_truck_required"] == False].copy()

        cold_pool      = cold_sp_ids if cold_sp_ids else all_sp_ids
        cold_customers = self._kmeans_assign(cold_customers, cold_pool)
        warm_customers = self._kmeans_assign(warm_customers, all_sp_ids)

        assigned = pd.concat([cold_customers, warm_customers], ignore_index=True)
        assigned = self._rebalance_high_segment(assigned, all_sp_ids)
        return assigned

    @staticmethod
    def _kmeans_assign(customers: pd.DataFrame, sp_ids: list[str]) -> pd.DataFrame:
        customers = customers.copy()
        n = len(sp_ids)

        if customers.empty:
            customers["assigned_sales_id"] = None
            return customers

        if n == 1 or len(customers) <= n:
            customers["assigned_sales_id"] = [
                sp_ids[i % n] for i in range(len(customers))
            ]
            return customers

        from sklearn.cluster import KMeans
        coords = customers[["gps_lat", "gps_lng"]].values
        km = KMeans(n_clusters=n, random_state=42, n_init=10)
        customers["_cluster"] = km.fit_predict(coords)

        cluster_to_sp = {i: sp_ids[i] for i in range(n)}
        customers["assigned_sales_id"] = customers["_cluster"].map(cluster_to_sp)
        customers = customers.drop(columns=["_cluster"])
        return customers

    @staticmethod
    def _rebalance_high_segment(customers: pd.DataFrame, sp_ids: list[str]) -> pd.DataFrame:
        """
        Two-pass rebalancing:
        1. Spread High-segment customers evenly (round-robin by score desc).
        2. Equalise total load — if any SP has significantly more customers
           than the target (total / n_sps), move excess non-High customers
           to under-loaded SPs. This prevents one SP getting 54 customers
           while others get 22, which makes the CP-SAT problem infeasible.
        """
        if "rfm_segment_final" not in customers.columns:
            return customers

        n         = len(sp_ids)
        high_mask = customers["rfm_segment_final"] == "High"
        high      = customers[high_mask].copy()

        if "final_customer_score" in high.columns:
            high = high.sort_values("final_customer_score", ascending=False)
        else:
            high = high.sort_values("customer_id")

        high  = high.reset_index(drop=True)
        other = customers[~high_mask].copy()
        high["assigned_sales_id"] = [sp_ids[i % n] for i in range(len(high))]
        result = pd.concat([high, other], ignore_index=True)

        # ── Load equalisation ────────────────────────────────────────────
        target  = len(result) // n          # ideal customers per SP
        surplus = len(result) - target * n  # first `surplus` SPs get +1

        # Count current load per SP
        load = {sp: int((result["assigned_sales_id"] == sp).sum()) for sp in sp_ids}

        # Identify over- and under-loaded SPs
        # A SP is over target if it has more than target (+1 for surplus slots)
        for i, sp in enumerate(sp_ids):
            cap = target + (1 if i < surplus else 0)
            excess = load[sp] - cap
            if excess <= 0:
                continue

            # Move excess non-High customers from this SP to under-loaded SPs
            moveable = result[
                (result["assigned_sales_id"] == sp) &
                (result["rfm_segment_final"] != "High")
            ].index.tolist()

            for j, other_sp in enumerate(sp_ids):
                if excess <= 0:
                    break
                other_cap  = target + (1 if j < surplus else 0)
                other_load = int((result["assigned_sales_id"] == other_sp).sum())
                space      = other_cap - other_load
                if space <= 0:
                    continue
                n_move = min(space, excess, len(moveable))
                for idx in moveable[:n_move]:
                    result.at[idx, "assigned_sales_id"] = other_sp
                moveable = moveable[n_move:]
                excess  -= n_move
                load[sp]        -= n_move
                load[other_sp]  += n_move

        return result


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
# RFM helpers  (updated for High / Medium / Low segments)
# ---------------------------------------------------------------------------

def get_max_visits(segment: str) -> int:
    """
    Maximum visits per month per customer based on new RFM segment.

    High   → 4 visits  (was Champion: 4, Loyal: 3)
    Medium → 2 visits  (was Potential Loyalist / At Risk / Need Attention: 2)
    Low    → 1 visit   (was Hibernating: 1)
    """
    return {
        "High":   4,
        "Medium": 2,
        "Low":    1,
    }.get(segment, 1)


def get_segment_priority_weight(segment: str) -> int:
    """
    Base priority weight by segment.
    The CP-SAT objective further multiplies this by (final_customer_score * 100)
    so customers with higher scores within the same segment are preferred.

    High   → 120  (top priority)
    Medium →  60  (mid priority)
    Low    →  15  (lowest priority)
    """
    return {
        "High":   120,
        "Medium":  60,
        "Low":     15,
    }.get(segment, 15)


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
        extra_high_bonus: int = 30,
        # solver_time_seconds: int = 60,
        solver_time_seconds: int = 150,
        
    ):
        self.priority_weights    = priority_weights or {}
        self.preference_weights  = preference_weights or {"day_match": 15}
        self.extra_high_bonus    = extra_high_bonus      # bonus for High segment (was champion bonus)
        self.solver_time_seconds = solver_time_seconds

    # def solve(
    #     self,
    #     customers: pd.DataFrame,
    #     valid_dates: list[pd.Timestamp],
    #     daily_work_minutes: int  = DEFAULT_DAILY_WORK_MINUTES,
    #     avg_visit_minutes: int   = DEFAULT_AVG_VISIT_MINUTES,
    #     avg_speed_kmph: float    = DEFAULT_AVG_SPEED_KMPH,
    #     warehouse_lat: float     = 0.0,
    #     warehouse_lng: float     = 0.0,
    #     sales_id: str            = "",
    #     territory_id: str        = "",
    #     solver_time_seconds: int = None,
    # ) -> pd.DataFrame:
    #     model        = cp_model.CpModel()
    #     customer_ids = customers["customer_id"].tolist()
    #     empty        = self._empty_df()

    #     if not customer_ids or not valid_dates:
    #         return empty

    #     # per-customer time costs
    #     visit_mins:  dict[str, int] = {}
    #     travel_mins: dict[str, int] = {}
    #     for _, cust in customers.iterrows():
    #         cid = cust["customer_id"]
    #         visit_mins[cid] = avg_visit_minutes
    #         dist_km = _haversine_km(
    #             warehouse_lat, warehouse_lng,
    #             float(cust["gps_lat"]), float(cust["gps_lng"]),
    #         )
    #         travel_mins[cid] = int((dist_km * 2 / avg_speed_kmph) * 60)

    #     avg_travel         = int(sum(travel_mins.values()) / max(len(travel_mins), 1))
    #     time_per_visit     = max(avg_visit_minutes + avg_travel, 1)
    #     max_visits_per_day = max(1, daily_work_minutes // time_per_visit)

    #     # decision variables
    #     x: dict[tuple[str, pd.Timestamp], cp_model.IntVar] = {}
    #     for cid in customer_ids:
    #         for d in valid_dates:
    #             x[(cid, d)] = model.NewBoolVar(f"x_{cid}_{d.strftime('%Y%m%d')}")

    #     cust_lookup = customers.set_index("customer_id").to_dict("index")

    #     # ── Capacity check before setting visit bounds ────────────────────
    #     # Total mandatory visits (min 1 per non-Churned/Dormant customer).
    #     # If mandatory visits alone exceed available slot capacity, reduce
    #     # max_v for High then Medium customers until capacity is sufficient,
    #     # ensuring every mandatory customer gets their guaranteed 1 visit.
    #     total_slots    = len(valid_dates) * max_visits_per_day
    #     # All customers are mandatory — RFM segment is the only decision maker
    #     mandatory_ids = customer_ids
    #     n_mandatory   = len(mandatory_ids)

    #     # Desired total visits (sum of max_v per customer)
    #     desired_visits = sum(
    #         get_max_visits(cust_lookup[cid].get("rfm_segment_final", "Low"))
    #         for cid in customer_ids
    #     )

    #     # If desired visits exceed capacity, cap max_v starting from Low
    #     # upward until total fits — guaranteeing at least 1 visit for all.
    #     effective_max: dict[str, int] = {
    #         cid: get_max_visits(cust_lookup[cid].get("rfm_segment_final", "Low"))
    #         for cid in customer_ids
    #     }

    #     if desired_visits > total_slots:
    #         # First try capping Medium to 1, then High to 1 if still tight
    #         for cap_segment, cap_value in [("Medium", 1), ("High", 2), ("High", 1)]:
    #             for cid in customer_ids:
    #                 if cust_lookup[cid].get("rfm_segment_final") == cap_segment:
    #                     effective_max[cid] = min(effective_max[cid], cap_value)
    #             new_total = sum(effective_max.values())
    #             if new_total <= total_slots:
    #                 break

    #     # per-customer visit bounds — RFM segment drives everything
    #     #   High   → min 1, max 4
    #     #   Medium → min 1, max 2
    #     #   Low    → min 1, max 1
    #     for cid in customer_ids:
    #         max_v  = effective_max[cid]
    #         vars_c = [x[(cid, d)] for d in valid_dates]
    #         model.Add(sum(vars_c) >= 1)
    #         model.Add(sum(vars_c) <= max(max_v, 1))

    #     # daily capacity constraints
    #     for d in valid_dates:
    #         day_vars = [x[(cid, d)] for cid in customer_ids]
    #         model.Add(sum(day_vars) <= max_visits_per_day)
    #         model.Add(
    #             sum(
    #                 (visit_mins[cid] + travel_mins[cid]) * x[(cid, d)]
    #                 for cid in customer_ids
    #             ) <= daily_work_minutes
    #         )

    #     # objective — maximise weighted visits
    #     # Priority = base_segment_weight
    #     #           + score_bonus (final_customer_score * 100, integer)
    #     #           + extra_high_bonus if High segment
    #     #           + preference_weight if preferred day matches
    #     # All multiplied by day_weight so earlier dates are preferred.
    #     obj_terms = []
    #     for di, d in enumerate(valid_dates):
    #         day_weight = 1_000_000 - di
    #         for cid in customer_ids:
    #             info      = cust_lookup[cid]
    #             segment   = info.get("rfm_segment_final", "Low")
    #             base      = self.priority_weights.get(
    #                 segment, get_segment_priority_weight(segment)
    #             )
    #             # final_customer_score refines priority within the same segment
    #             score_bonus = int(info.get("final_customer_score", 0.5) * 100)
    #             bonus     = self.extra_high_bonus if segment == "High" else 0
    #             pref      = get_preference_weight(
    #                 d, info.get("preferred_visit_day"), self.preference_weights
    #             )
    #             obj_terms.append(day_weight                      * x[(cid, d)])
    #             obj_terms.append((base + score_bonus + bonus) * 100 * x[(cid, d)])
    #             obj_terms.append(pref                            * x[(cid, d)])

    #     model.Maximize(sum(obj_terms))

    #     solver = cp_model.CpSolver()
    #     solver.parameters.max_time_in_seconds = (
    #         solver_time_seconds if solver_time_seconds is not None
    #         else self.solver_time_seconds
    #     )
    #     solver.parameters.num_search_workers  = 8
    #     status = solver.Solve(model)

    #     if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    #         return empty

    #     print(f"  [{sales_id}] {solver.StatusName(status)} | obj={solver.ObjectiveValue():.0f}")

    #     rows: list[dict[str, Any]] = []
    #     for cid in customer_ids:
    #         for d in valid_dates:
    #             if solver.Value(x[(cid, d)]) == 1:
    #                 info = cust_lookup[cid]
    #                 rows.append({
    #                     "schedule_date":            d,
    #                     "sales_id":                 sales_id,
    #                     "territory_id":             territory_id,
    #                     "customer_id":              cid,
    #                     "shop_name":                info.get("shop_name", ""),
    #                     "locality":                 info.get("locality", ""),
    #                     "gps_lat":                  info.get("gps_lat"),
    #                     "gps_lng":                  info.get("gps_lng"),
    #                     # new RFM fields
    #                     "rfm_segment_final":        info.get("rfm_segment_final", ""),
    #                     "final_customer_score":     info.get("final_customer_score", 0.0),
    #                     "rfm_combined":             info.get("rfm_combined", 0.0),
    #                     "customer_rank":            info.get("customer_rank", 0),
    #                     "seasonality_score":        info.get("seasonality_score", 0.0),
    #                     "territory_score":          info.get("territory_score", 0.0),
    #                     "locality_score":           info.get("locality_score", 0.0),
    #                     "rating_score":             info.get("rating_score", 0.0),
    #                     # customer context
    #                     "lifecycle_state":          info.get("lifecycle_state", False),
    #                     "cold_truck_required":      info.get("cold_truck_required", False),
    #                     "estimated_visit_minutes":  visit_mins[cid],
    #                     "estimated_travel_minutes": travel_mins[cid],
    #                 })

    #     if not rows:
    #         return empty

    #     result_df = (
    #         pd.DataFrame(rows)
    #         .sort_values(["schedule_date", "final_customer_score"],
    #                      ascending=[True, False])
    #         .reset_index(drop=True)
    #     )

    #     # ── Post-solve: warn if any mandatory customer was not scheduled ──
    #     scheduled_ids = set(result_df["customer_id"].unique())
    #     missed = [cid for cid in customer_ids if cid not in scheduled_ids]
    #     if missed:
    #         print(
    #             f"  WARNING [{sales_id}]: {len(missed)} mandatory customer(s) "
    #             f"could not be scheduled due to capacity constraints: {missed}"
    #         )

    #     return result_df


    def solve(
        self,
        customers: pd.DataFrame,
        valid_dates: list[pd.Timestamp],
        daily_work_minutes: int = DEFAULT_DAILY_WORK_MINUTES,
        avg_visit_minutes: int = DEFAULT_AVG_VISIT_MINUTES,
        avg_speed_kmph: float = DEFAULT_AVG_SPEED_KMPH,
        warehouse_lat: float = 0.0,
        warehouse_lng: float = 0.0,
        sales_id: str = "",
        territory_id: str = "",
        solver_time_seconds: int = None,
    ) -> pd.DataFrame:
        model = cp_model.CpModel()
        customer_ids = customers["customer_id"].tolist()
        empty = self._empty_df()

        if not customer_ids or not valid_dates:
            return empty

        # per-customer time costs
        visit_mins: dict[str, int] = {}
        travel_mins: dict[str, int] = {}
        for _, cust in customers.iterrows():
            cid = cust["customer_id"]
            visit_mins[cid] = avg_visit_minutes
            dist_km = _haversine_km(
                warehouse_lat, warehouse_lng,
                float(cust["gps_lat"]), float(cust["gps_lng"]),
            )
            travel_mins[cid] = int((dist_km * 2 / avg_speed_kmph) * 60)

        avg_travel = int(sum(travel_mins.values()) / max(len(travel_mins), 1))
        time_per_visit = max(avg_visit_minutes + avg_travel, 1)
        max_visits_per_day = max(1, daily_work_minutes // time_per_visit)

        # decision variables
        x: dict[tuple[str, pd.Timestamp], cp_model.IntVar] = {}
        for cid in customer_ids:
            for d in valid_dates:
                x[(cid, d)] = model.NewBoolVar(f"x_{cid}_{d.strftime('%Y%m%d')}")

        cust_lookup = customers.set_index("customer_id").to_dict("index")

        # ── Week-of-month mapping (1‑based, e.g., June 1‑6 → week 1) ──
        week_of_month = {}
        for d in valid_dates:
            week_of_month[d] = (d.day - 1) // 7 + 1
        all_weeks = sorted(set(week_of_month.values()))

        # ── Capacity check before setting visit bounds ─────────────────
        total_slots = len(valid_dates) * max_visits_per_day
        mandatory_ids = customer_ids
        n_mandatory = len(mandatory_ids)

        desired_visits = sum(
            get_max_visits(cust_lookup[cid].get("rfm_segment_final", "Low"))
            for cid in customer_ids
        )

        effective_max: dict[str, int] = {
            cid: get_max_visits(cust_lookup[cid].get("rfm_segment_final", "Low"))
            for cid in customer_ids
        }

        if desired_visits > total_slots:
            for cap_segment, cap_value in [("Medium", 1), ("High", 2), ("High", 1)]:
                for cid in customer_ids:
                    if cust_lookup[cid].get("rfm_segment_final") == cap_segment:
                        effective_max[cid] = min(effective_max[cid], cap_value)
                new_total = sum(effective_max.values())
                if new_total <= total_slots:
                    break

        # ── per-customer visit bounds + week‑based constraints ─────────
        for cid in customer_ids:
            info = cust_lookup[cid]
            segment = info.get("rfm_segment_final", "Low")
            max_v = effective_max[cid]
            vars_c = [x[(cid, d)] for d in valid_dates]

            # Minimum 1 visit for all active customers (lifecycle not Churned/Dormant)
            # In this version we treat all customers as mandatory.
            model.Add(sum(vars_c) >= 1)
            model.Add(sum(vars_c) <= max(max_v, 1))

            # -------------------------------------------------------------
            # HIGH segment: at most one visit per week
            # -------------------------------------------------------------
            if segment == "High":
                for week in all_weeks:
                    vars_in_week = [x[(cid, d)] for d in valid_dates if week_of_month[d] == week]
                    if vars_in_week:
                        model.Add(sum(vars_in_week) <= 1)

            # -------------------------------------------------------------
            # MEDIUM segment: exactly 2 visits, different weeks,
            #                weeks must be non‑consecutive (at least one week gap)
            # -------------------------------------------------------------
            elif segment == "Medium":
                # We already have max_v = 2, min_v = 1 from the bounds above.
                # Enforce exactly 2 visits (must be 2, not 1) – adjust max_v to 2.
                model.Add(sum(vars_c) == 2)

                # Create a boolean per week indicating whether that week has any visit
                week_used = {}
                for week in all_weeks:
                    week_used[week] = model.NewBoolVar(f"week_{cid}_{week}")
                    vars_in_week = [x[(cid, d)] for d in valid_dates if week_of_month[d] == week]
                    if vars_in_week:
                        model.Add(sum(vars_in_week) >= 1).OnlyEnforceIf(week_used[week])
                        model.Add(sum(vars_in_week) == 0).OnlyEnforceIf(week_used[week].Not())
                    else:
                        # No valid dates in this week -> force unused
                        model.Add(week_used[week] == 0)

                # Exactly two weeks are used
                model.Add(sum(week_used.values()) == 2)

                # Weeks must be non‑consecutive: for any two weeks that are consecutive,
                # at most one of them can be used.
                # This handles both 1‑based week numbers and possible 5 weeks.
                sorted_weeks = sorted(all_weeks)
                for i in range(len(sorted_weeks) - 1):
                    w1, w2 = sorted_weeks[i], sorted_weeks[i+1]
                    if w2 == w1 + 1:
                        model.Add(week_used[w1] + week_used[w2] <= 1)

            # LOW segment: no extra constraints (max = 1 already)

        # ── daily capacity constraints ──────────────────────────────────
        for d in valid_dates:
            day_vars = [x[(cid, d)] for cid in customer_ids]
            model.Add(sum(day_vars) <= max_visits_per_day)
            model.Add(
                sum(
                    (visit_mins[cid] + travel_mins[cid]) * x[(cid, d)]
                    for cid in customer_ids
                ) <= daily_work_minutes
            )

        # ── objective ───────────────────────────────────────────────────
        obj_terms = []
        for di, d in enumerate(valid_dates):
            day_weight = 1_000_000 - di
            for cid in customer_ids:
                info = cust_lookup[cid]
                segment = info.get("rfm_segment_final", "Low")
                base = self.priority_weights.get(
                    segment, get_segment_priority_weight(segment)
                )
                score_bonus = int(info.get("final_customer_score", 0.5) * 100)
                bonus = self.extra_high_bonus if segment == "High" else 0
                pref = get_preference_weight(
                    d, info.get("preferred_visit_day"), self.preference_weights
                )
                obj_terms.append(day_weight * x[(cid, d)])
                obj_terms.append((base + score_bonus + bonus) * 100 * x[(cid, d)])
                obj_terms.append(pref * x[(cid, d)])

        model.Maximize(sum(obj_terms))

        # ── solve ───────────────────────────────────────────────────────
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = (
            solver_time_seconds if solver_time_seconds is not None
            else self.solver_time_seconds
        )
        solver.parameters.num_search_workers = 8
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
                        "schedule_date": d,
                        "sales_id": sales_id,
                        "territory_id": territory_id,
                        "customer_id": cid,
                        "shop_name": info.get("shop_name", ""),
                        "locality": info.get("locality", ""),
                        "gps_lat": info.get("gps_lat"),
                        "gps_lng": info.get("gps_lng"),
                        "rfm_segment_final": info.get("rfm_segment_final", ""),
                        "final_customer_score": info.get("final_customer_score", 0.0),
                        "rfm_combined": info.get("rfm_combined", 0.0),
                        "customer_rank": info.get("customer_rank", 0),
                        "seasonality_score": info.get("seasonality_score", 0.0),
                        "territory_score": info.get("territory_score", 0.0),
                        "locality_score": info.get("locality_score", 0.0),
                        "rating_score": info.get("rating_score", 0.0),
                        "lifecycle_state": info.get("lifecycle_state", False),
                        "cold_truck_required": info.get("cold_truck_required", False),
                        "estimated_visit_minutes": visit_mins[cid],
                        "estimated_travel_minutes": travel_mins[cid],
                    })

        if not rows:
            return empty

        result_df = (
            pd.DataFrame(rows)
            .sort_values(["schedule_date", "final_customer_score"],
                        ascending=[True, False])
            .reset_index(drop=True)
        )

        # ── Warn if any mandatory customer could not be scheduled ──────
        scheduled_ids = set(result_df["customer_id"].unique())
        missed = [cid for cid in customer_ids if cid not in scheduled_ids]
        if missed:
            print(
                f"  WARNING [{sales_id}]: {len(missed)} mandatory customer(s) "
                f"could not be scheduled due to capacity constraints: {missed}"
            )

        return result_df



    @staticmethod
    def _empty_df() -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "schedule_date", "sales_id", "territory_id", "customer_id",
            "shop_name", "locality", "gps_lat", "gps_lng",
            "rfm_segment_final", "final_customer_score", "rfm_combined",
            "customer_rank", "seasonality_score", "territory_score",
            "locality_score", "rating_score",
            "lifecycle_state", "cold_truck_required",
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
            nearest_idx  = int(distances.idxmin())
            row          = unvisited.loc[nearest_idx]
            route.append(row.to_dict())
            current_lat  = float(row["gps_lat"])
            current_lng  = float(row["gps_lng"])
            unvisited    = unvisited.drop(index=nearest_idx).reset_index(drop=True)

        result = pd.DataFrame(route)
        result["route_rank"] = range(1, len(result) + 1)
        return result


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

class MultiSalespersonScheduler:
    """
    Pipeline:
    1. Merge customer + RFM data (new columns: rfm_segment_final,
       final_customer_score, rfm_combined, customer_rank, etc.)
    2. For each territory — assign customers to salespeople via KMeans.
    3. For each salesperson — compute valid dates, run CP-SAT, build routes.
    4. Aggregate outputs.
    """

    def __init__(
        self,
        extra_high_bonus:    int = 30,
        solver_time_seconds: int = 60,
    ):
        self.extra_high_bonus    = extra_high_bonus
        self.solver_time_seconds = solver_time_seconds
        self._assigner      = CustomerAssigner()
        self._sp_scheduler  = SalespersonScheduler(
            extra_high_bonus=extra_high_bonus,
            solver_time_seconds=solver_time_seconds,
        )
        self._route_planner = DailyRoutePlanner()

    def create_schedules(
        self,
        customer_df:      pd.DataFrame,
        rfm_scores_df:    pd.DataFrame,
        salesperson_df:   pd.DataFrame,
        holiday_df:       pd.DataFrame,
        territory_df:     pd.DataFrame,
        config_df:        pd.DataFrame,
        van_df:           pd.DataFrame,
        month_start_date: str | pd.Timestamp = "2026-06-01",
    ) -> MultiScheduleResult:

        month_start   = pd.Timestamp(month_start_date).normalize()
        year, month   = month_start.year, month_start.month
        days_in_month = calendar.monthrange(year, month)[1]
        month_end     = month_start + pd.Timedelta(days=days_in_month - 1)

        cfg = config_df.set_index("config_key")["config_value"].to_dict() if not config_df.empty else {}
        avg_speed_kmph    = float(cfg.get("avg_speed_kmh", 32))
        avg_visit_minutes = int(float(cfg.get("avg_service_time_min", 22)))
        daily_work_minutes = 480

        full_customers = self._build_full_customer_df(customer_df, rfm_scores_df)
        ter_info       = territory_df.set_index("territory_id").to_dict("index")

        ter_blocked: dict[str, set[pd.Timestamp]] = {}
        for tid in territory_df["territory_id"]:
            ter_blocked[tid] = get_territory_blocked_dates(
                tid, holiday_df, month_start, month_end
            )

        all_detailed:   list[pd.DataFrame] = []
        sp_results:     dict[str, SalespersonScheduleResult] = {}
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

            # ── STEP 1: assign customers → salespeople (KMeans) ──────────────
            print(f"\nTerritory {territory_id}: assigning {len(ter_customers)} customers "
                  f"to {len(territory_sps)} salespeople via KMeans clustering...")
            ter_customers = self._assigner.assign(ter_customers, territory_sps, van_df)

            for sp_id in territory_sps["sales_id"]:
                n_assigned = (ter_customers["assigned_sales_id"] == sp_id).sum()
                seg_counts = (
                    ter_customers[ter_customers["assigned_sales_id"] == sp_id]
                    ["rfm_segment_final"].value_counts().to_dict()
                )
                print(f"  {sp_id} → {n_assigned} customers  {seg_counts}")

            # ── STEP 2: for each salesperson, run CP-SAT monthly plan ─────────
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

                # Scale solver time with problem size — larger batches need more time
                n_vars = len(sp_customers) * len(valid_dates)
                dynamic_time = max(self.solver_time_seconds,
                                   min(300, len(sp_customers) * 3))
                print(f"\n  Scheduling {sales_id} ({len(sp_customers)} customers, "
                      f"{len(valid_dates)} valid days, timeout={dynamic_time}s)...")

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
                    solver_time_seconds= dynamic_time,
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
                ["territory_id", "sales_id", "schedule_date", "final_customer_score"],
                ascending=[True, True, True, False]
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
        """
        Merge customer master data with new RFM scores.
        Key columns from rfm_scores_df:
            rfm_segment_final   — High / Medium / Low
            final_customer_score— 0-1 weighted score
            rfm_combined        — mean(r, f, m)
            customer_rank       — within-territory rank
            seasonality_score, territory_score, locality_score, rating_score
        """
        rfm_cols = [
            "customer_id",
            "rfm_segment_final",
            "final_customer_score",
            "rfm_combined",
            "customer_rank",
            "recency", "frequency", "monetary",
            "r_score", "f_score", "m_score",
            "seasonality_score",
            "territory_score",
            "locality_score",
            "rating_score",
        ]
        rfm_use = [c for c in rfm_cols if c in rfm_scores_df.columns]
        merged  = customer_df.merge(rfm_scores_df[rfm_use], on="customer_id", how="left")
        merged["rfm_segment_final"]    = merged["rfm_segment_final"].fillna("Low")
        merged["final_customer_score"] = merged["final_customer_score"].fillna(0.0)
        return merged

    def _build_daily_routes(self, detailed, wh_lat, wh_lng):
        rows = []
        for (sales_id, sched_date), group in detailed.groupby(["sales_id", "schedule_date"]):
            routed = self._route_planner.get_route(group.copy(), wh_lat, wh_lng)
            rows.append({
                "schedule_date":      sched_date,
                "sales_id":           sales_id,
                "territory_id":       group["territory_id"].iloc[0],
                "customer_list":      routed["customer_id"].tolist(),
                "customer_count":     len(routed),
                "route_order":        routed["shop_name"].tolist(),
                "segment_breakdown":  routed["rfm_segment_final"].value_counts().to_dict(),
                "avg_customer_score": round(float(routed["final_customer_score"].mean()), 4),
                "total_visit_min":    int(routed["estimated_visit_minutes"].sum()),
                "total_travel_min":   int(routed["estimated_travel_minutes"].sum()),
            })
        if not rows:
            return pd.DataFrame(columns=[
                "schedule_date", "sales_id", "territory_id",
                "customer_list", "customer_count", "route_order",
                "segment_breakdown", "avg_customer_score",
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
# Folium map helpers
# ---------------------------------------------------------------------------

_SP_COLOURS = ["red", "blue", "green", "purple", "orange", "darkred",
               "cadetblue", "darkgreen", "darkpurple", "black"]

# Updated segment colours for new High / Medium / Low segments
SEGMENT_COLOUR = {
    "High":   "red",      # top priority — most visible
    "Medium": "orange",   # mid priority
    "Low":    "gray",     # lowest priority
}


def _add_warehouse_marker(m, wh_lat: float, wh_lng: float, label: str = "Warehouse"):
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
    Markers coloured by rfm_segment_final (High=red, Medium=orange, Low=gray).
    Tooltip shows final_customer_score and customer_rank.
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

    center_lat = day_df["gps_lat"].mean()
    center_lng = day_df["gps_lng"].mean()
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start)

    if warehouse_lat != 0.0 or warehouse_lng != 0.0:
        _add_warehouse_marker(m, warehouse_lat, warehouse_lng)
        route_coords = [[warehouse_lat, warehouse_lng]] + day_df[["gps_lat", "gps_lng"]].values.tolist()
    else:
        route_coords = day_df[["gps_lat", "gps_lng"]].values.tolist()

    for _, row in day_df.iterrows():
        color   = SEGMENT_COLOUR.get(str(row.get("rfm_segment_final", "")), "blue")
        score   = row.get("final_customer_score", 0.0)
        rank    = row.get("customer_rank", "?")
        folium.Marker(
            [row["gps_lat"], row["gps_lng"]],
            icon=folium.DivIcon(
                html=f"""<div style="background:{color};color:white;border-radius:50%;
                         width:26px;height:26px;text-align:center;line-height:26px;
                         font-weight:bold;font-size:11px;">{row['route_rank']}</div>""",
            ),
            tooltip=(
                f"{row['route_rank']}. {row.get('shop_name','')} "
                f"[{row.get('rfm_segment_final','')}] "
                f"score={score:.3f} rank=#{rank} "
                f"{row.get('locality','')} "
                f"– Cold: {row.get('cold_truck_required','?')}"
            ),
        ).add_to(m)

    line = folium.PolyLine(route_coords, weight=3, color="navy")
    m.add_child(line)
    PolyLineTextPath(
        line, "➤", repeat=True, offset=7,
        attributes={"fill": "red", "font-size": "14"},
    ).add_to(m)

    m.get_root().html.add_child(folium.Element(f"""
    <div style="position:fixed;top:10px;left:60px;z-index:1000;
                background:white;padding:8px 12px;border-radius:6px;
                border:1px solid #ccc;font-family:sans-serif;">
        <b>{sales_id}</b> — {sched_date.strftime('%d %b %Y')} &nbsp;|&nbsp; {len(day_df)} stops
    </div>"""))

    return m


def build_territory_day_map(
    result:        MultiScheduleResult,
    territory_id:  str,
    schedule_date: str | pd.Timestamp,
    zoom_start:    int = 11,
):
    """
    Shows ALL salespeople in one territory on a single folium map for a given date.
    Marker colour = salesperson colour (each SP gets a distinct colour).
    Tooltip shows rfm_segment_final, final_customer_score, customer_rank.
    """
    try:
        import folium
        from folium.plugins import PolyLineTextPath
    except ImportError:
        raise ImportError("pip install folium")

    sched_date = pd.Timestamp(schedule_date).normalize()

    territory_sp_ids = [
        sid for sid, sp in result.salesperson_results.items()
        if sp.territory_id == territory_id
    ]

    if not territory_sp_ids:
        raise ValueError(f"No salespeople found for territory {territory_id}")

    wh_lat, wh_lng = result.territory_warehouses.get(territory_id, (0.0, 0.0))

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
        raise ValueError(f"No visits found in territory {territory_id} on {sched_date.date()}")

    center_lat = sum(all_lats) / len(all_lats)
    center_lng = sum(all_lngs) / len(all_lngs)
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_start)

    if wh_lat != 0.0 or wh_lng != 0.0:
        _add_warehouse_marker(m, wh_lat, wh_lng, label=f"Warehouse ({territory_id})")

    sp_colour_map = {
        sid: _SP_COLOURS[i % len(_SP_COLOURS)]
        for i, sid in enumerate(sorted(sp_day_data.keys()))
    }

    legend_items = []

    for sales_id, day_df in sp_day_data.items():
        sp_color = sp_colour_map[sales_id]

        if wh_lat != 0.0 or wh_lng != 0.0:
            route_coords = [[wh_lat, wh_lng]] + day_df[["gps_lat", "gps_lng"]].values.tolist()
        else:
            route_coords = day_df[["gps_lat", "gps_lng"]].values.tolist()

        for _, row in day_df.iterrows():
            score = row.get("final_customer_score", 0.0)
            rank  = row.get("customer_rank", "?")
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
                    f"[{row.get('rfm_segment_final','')}] "
                    f"score={score:.3f} rank=#{rank} "
                    f"– Cold: {row.get('cold_truck_required','?')}"
                ),
            ).add_to(m)

        line = folium.PolyLine(route_coords, weight=3, color=sp_color, opacity=0.8)
        m.add_child(line)
        PolyLineTextPath(
            line, "➤", repeat=True, offset=7,
            attributes={"fill": sp_color, "font-size": "13"},
        ).add_to(m)

        seg_counts = day_df["rfm_segment_final"].value_counts().to_dict()
        seg_str    = " | ".join(f"{k}:{v}" for k, v in seg_counts.items())
        legend_items.append(
            f'<li><span style="background:{sp_color};width:14px;height:14px;'
            f'display:inline-block;border-radius:50%;margin-right:6px;"></span>'
            f'{sales_id} ({len(day_df)} stops — {seg_str})</li>'
        )

    legend_html = f"""
    <div style="position:fixed;top:10px;right:10px;z-index:1000;
                background:white;padding:10px 14px;border-radius:8px;
                border:1px solid #ccc;font-family:sans-serif;font-size:12px;
                min-width:220px;">
        <b>{territory_id}</b> — {sched_date.strftime('%d %b %Y')}<br>
        <ul style="list-style:none;margin:6px 0 0;padding:0;">
            {''.join(legend_items)}
            <li style="margin-top:6px;">
                <span style="background:black;width:14px;height:14px;
                display:inline-block;border-radius:50%;margin-right:6px;"></span>
                Warehouse
            </li>
        </ul>
        <hr style="margin:6px 0;">
        <span style="font-size:11px;color:#666;">
            Marker colour = salesperson<br>
            High=red &nbsp; Medium=orange &nbsp; Low=gray (segment in tooltip)
        </span>
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
