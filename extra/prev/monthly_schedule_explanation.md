# Monthly Scheduling Flow Explained

This document explains, end to end, how the monthly sales plan is generated in this workspace. It covers the data-generation notebook, the RFM scoring step, the CP-SAT scheduler, the route ordering pass, and the final merged outputs.

## What the system produces

The workflow generates a monthly plan for all territories and all active salespeople. The final outputs are:

- `detailed_schedule`: one row per scheduled customer visit
- `cold_schedule`: only cold-truck customer visits
- `normal_schedule`: only normal-truck customer visits
- `daily_schedule`: one row per salesperson per day, with route summaries
- `salesperson_results`: per-salesperson detailed and daily schedules
- `territory_warehouses`: warehouse coordinates used for routing

The plan is built territory by territory and truck group by truck group. Cold-chain customers and normal customers are intentionally separated so the solver can enforce vehicle compatibility cleanly.

## High-level pipeline

The full flow is:

1. Generate synthetic master data.
2. Compute customer priority scores and RFM segments.
3. Build visit history used for RFM seeding and diagnostics.
4. Merge customer and RFM data.
5. For each territory, split customers into cold and normal groups.
6. For each group, build the valid working calendar after holidays.
7. Solve assignment and visit dates with CP-SAT.
8. Post-process each day with nearest-neighbour route ordering.
9. Combine all territories into one monthly result.

The key point is that the solver does not start from a fixed preassignment. It decides both who serves each customer and on which dates the customer is visited.

## Data generation stage

The notebook entry point is `generate_all(seed=42)`. It creates the tables the scheduler needs:

- `territory_df`
- `salesperson_df`
- `van_df`
- `customer_df`
- `holiday_df`
- `config_df`
- `rfm_scores_df`

The synthetic visit table is generated separately by `generate_visits(...)` and is mainly used to seed RFM computation and to demonstrate visit behavior.

### Territory data

Each territory contains:

- territory ID and name
- warehouse latitude and longitude
- territory center coordinates
- radius constraint for customer placement

These fields matter later because the scheduler checks geographic feasibility and uses the warehouse coordinates to estimate travel cost and route order.

### Salesperson data

Each salesperson is tied to one territory and receives:

- a sales ID
- a territory ID
- an assigned van
- a working-hour budget
- a start shift time
- an active/inactive flag
- a performance multiplier

The assigned van is critical because the scheduler later determines whether a salesperson can serve cold-chain customers.

### Van data

Each van has:

- a van ID
- a territory ID
- a cold-truck enabled flag

This is how the scheduler knows whether a salesperson can be placed in the cold-truck pool.

### Customer data

Each customer includes business and geographic attributes such as:

- customer ID
- shop name
- GPS location
- locality
- territory
- rating information
- shop category
- cold-truck requirement
- volume tier
- payment type
- credit limit
- outstanding balance
- lifecycle state
- acquisition date
- preferred visit day
- preferred order window

The most important fields for scheduling are:

- territory_id
- cold_truck_required
- final_customer_score
- rfm_segment_final
- preferred_visit_day
- gps coordinates

### Holiday data

The holiday table may contain three kinds of blocked events:

- territory-wide holidays
- salesperson personal leave
- van maintenance days

These are expanded into exact blocked dates later so the scheduler never places a visit on a non-working day.

### RFM scoring

The notebook computes the RFM table in `generate_rfm_scores(customer_df, visit_df, config_df)`.

RFM is used to classify customers into:

- High
- Medium
- Low

The final customer score is a weighted score based on:

- RFM combined score
- seasonality score
- territory score
- locality score
- rating score

This score is later used by the solver to prioritize which customers get scheduled earlier and which customers are considered more important.

## RFM segmentation logic

The scheduler does not just keep a generic priority label. It uses the RFM segment in two ways:

1. It sets the maximum number of visits per month.
2. It drives the optimization objective so higher segments are preferred.

The segment visit caps are:

- High: up to 4 visits per month
- Medium: up to 2 visits per month
- Low: up to 1 visit per month

At the same time, every active customer must receive at least one visit per month. So the segment controls the upper bound, while the hard minimum ensures coverage.

## Monthly scheduling entry point

The scheduler begins in `MultiSalespersonScheduler.create_schedules(...)`.

This method is the orchestration layer. It does not solve a CP model itself. Instead, it prepares the data for one territory and truck group at a time and then delegates the real optimization to `TerritoryScheduler.solve(...)`.

### Step 1: Read the month context

The method converts `month_start_date` into a normalized monthly timestamp and derives:

- the month year
- the month number
- the number of days in the month
- the last day of the month

This calendar window defines which dates can be used for scheduling.

### Step 2: Read config values

The config table supplies solver and planning defaults such as:

- average speed in km/h
- average service time in minutes
- daily work minutes

These values are used to estimate route cost and daily capacity.

### Step 3: Merge customer and RFM tables

`_build_full_customer_df(customer_df, rfm_scores_df)` merges the customer master data with the RFM scores.

After the merge, each customer row contains the scheduling attributes that the solver needs, especially:

- rfm_segment_final
- final_customer_score
- customer_rank
- recency, frequency, monetary
- rating and locality scores

If a customer does not have a matching RFM row, defaults are filled in so the scheduler still works.

### Step 4: Filter territories

If a `territory_id` is provided, only that territory is scheduled.
Otherwise, all territories are included.

This is why the system can produce either:

- one-territory plans
- or a full monthly plan for all territories

## Territory-level planning

Inside `create_schedules(...)`, the code loops through each territory independently.

For every territory:

1. Filter customers for that territory.
2. Filter active salespeople for that territory.
3. Read the warehouse location.
4. Compute territory-level blocked dates.
5. Split customers into cold and normal groups.
6. Build salesperson-specific valid working dates.
7. Solve cold and normal groups separately.
8. Route-order each daily plan.
9. Store per-salesperson and combined outputs.

This means the optimization problem is deliberately decomposed into smaller subproblems.

## Holiday and availability handling

The scheduler uses two helper functions:

- `get_territory_blocked_dates(...)`
- `get_salesperson_blocked_dates(...)`

These rely on `_blocked_dates(...)`, which expands date ranges into exact daily blocks.

The valid date set for a salesperson is the monthly date range minus:

- territory holidays
- that salesperson’s personal leave

The solver only builds visit variables for dates that survive this filtering.

That is an important modeling choice because it keeps the CP-SAT model smaller and prevents the solver from planning on impossible days.

## Cold and normal truck separation

The code separates customers into two groups:

- cold customers, where `cold_truck_required == True`
- normal customers, where `cold_truck_required == False`

Then it splits salespeople into pools based on whether their assigned van is cold-enabled.

### Why this matters

Cold-chain customers must never be assigned to a salesperson who cannot serve them. By solving the two groups separately, the model can enforce this cleanly and avoid invalid assignments.

If no cold-capable salesperson exists in a territory, the code prints a warning and falls back to using all salespeople. That is a practical fallback, but it means the data model is missing a true cold-capable route resource.

## The CP-SAT solver

The actual schedule logic lives in `TerritoryScheduler.solve(...)`.

This method solves one territory and one truck group at a time. It is a mixed assignment-and-scheduling model built on OR-Tools CP-SAT.

### Inputs to the solver

The solver receives:

- filtered customers
- filtered salespeople
- van data
- valid monthly dates for the group
- warehouse coordinates
- daily work minutes
- average visit minutes
- average speed
- truck group label
- salesperson-specific valid dates

### What the solver is deciding

The solver decides:

- which salesperson is responsible for each customer
- on which dates that customer is visited

It does not only assign customers to salespeople. It also schedules the month’s actual visit occurrences.

## Core variables

Two binary variable families are created.

### assigned[cid][sid]

This means:

- 1 if customer `cid` is assigned to salesperson `sid`
- 0 otherwise

Every customer must be assigned to exactly one salesperson.

### visit[cid][sid][d]

This means:

- 1 if customer `cid` is visited by salesperson `sid` on date `d`
- 0 otherwise

The visit variable can only be 1 if the customer is assigned to that salesperson.

## Capacity model

Before constraints are added, the code estimates how many customers a salesperson can realistically handle.

### Travel estimate

For each customer and salesperson pair, travel minutes are estimated from the warehouse-to-customer distance using the haversine formula and the configured average speed.

This is a one-way estimate, not a round-trip estimate.

### Visit time estimate

Each stop has:

- average service time
- estimated travel time from the warehouse

Those are combined into an effective time per visit.

### Daily capacity

The code then computes a daily stop capacity per salesperson by testing how many stops fit inside the daily work limit.

It also accounts for a 15-minute buffer after every 4 customers.

This buffer is built into the effective capacity calculation so the model does not overpack a route.

## Hard constraints

The solver uses hard constraints to guarantee a valid schedule.

### 1. Each customer is assigned to exactly one salesperson

This is the primary ownership rule. A customer cannot be split across multiple salespeople.

### 2. A visit can happen only if the customer is assigned to that salesperson

This links assignment to the actual monthly visit schedule.

### 3. Cold customers are restricted to cold-capable salespeople

When the group is cold, the solver removes all non-cold salespeople from consideration.

### 4. Every active customer must receive at least one visit per month

This is the monthly coverage rule.

### 5. Monthly visit caps by RFM segment

Each customer’s total number of visits is capped by their segment:

- High: 4
- Medium: 2
- Low: 1

### 6. Daily time budget per salesperson

For each salesperson on each valid date, the total time cost of assigned visits must stay within the daily work minutes.

### 7. Daily stop limit per salesperson

Each salesperson has a maximum number of customers per day based on their estimated capacity.

### 8. A customer can be visited at most once per day

This avoids duplicate same-day visits for the same customer.

### 9. Personal blocked dates are enforced

If a salesperson cannot work on a date, all their visit variables for that date are set to 0.

Without this rule, the solver could legally assign a salesperson on an off day because the monthly valid-date set is the union of all salesperson calendars.

## Objective function

The model is not just feasible; it is optimized.

The objective is to maximize a weighted sum that favors:

- high-priority customers
- higher final_customer_score
- earlier dates in the month
- preferred visit weekdays
- compact geographic assignments
- weekly distribution patterns for higher-value segments

### Priority weighting

The segment weight makes the solver prefer High customers before Medium, and Medium before Low.

Then the final customer score refines this ranking within the same segment.

### Earlier dates

The objective slightly favors earlier dates by giving them a stronger weight than later dates.

This means the solver naturally pulls important work forward in the month when possible.

### Preferred weekday bonus

If a scheduled date matches the customer’s preferred visit day, the solver gets a large bonus.

This encourages schedules that align with business preferences rather than only optimizing purely mathematically.

### Weekly cadence bonuses

The model adds soft bonuses for temporal spread:

- High customers are rewarded for appearing in each ISO week
- Medium customers are rewarded for visits spread across different weeks

This gives the schedule a more realistic monthly cadence.

### Geographic compactness bonus

The current implementation gives each customer a compactness bonus based on proximity to the territory centroid.

This is a lightweight way to encourage geographically tight routes without creating a large pairwise O(n²) bonus structure.

That is important because it keeps the normal group from becoming too expensive to solve.

## Solver hints

Before calling CP-SAT, the code adds a greedy round-robin hint.

It sorts customers by final_customer_score and seeds an initial assignment pattern across salespeople.

This does not force the answer. It simply gives the solver a starting point so it can search more efficiently.

## Solver timeout behavior

The timeout is dynamic.

The orchestrator computes a problem size estimate based on:

- number of customers
- number of salespeople
- number of valid dates

Then it chooses a timeout ceiling that is longer for normal groups and shorter for cold groups.

This is practical because normal groups are usually bigger and harder to solve.

## What happens after a solution is found

Once CP-SAT returns a feasible or optimal solution, the solver extracts rows for each scheduled visit.

Each row includes:

- schedule date
- salesperson ID
- territory ID
- customer ID
- truck group
- shop name
- coordinates
- RFM segment
- final score
- rank
- seasonality, territory, locality, and rating scores
- lifecycle state
- cold truck requirement
- estimated visit minutes
- estimated travel minutes
- warehouse-to-customer distance

These rows are stored in a detailed schedule table.

## Route ordering and km tracking

The CP-SAT model decides assignment and visit timing, but it does not order the stops inside a day.

That task is handled by `DailyRoutePlanner.get_route(...)`.

### Route ordering logic

For each salesperson and each date:

1. Start from the warehouse.
2. Find the nearest unvisited customer.
3. Add that customer to the route.
4. Update cumulative distance.
5. Repeat until all stops are ordered.

This gives a simple nearest-neighbour route.

### Route output columns

After route ordering, each row gets:

- `route_leg_km`
- `cumulative_route_km`
- `route_rank`

This is why the final daily plan can show both the sequence of stops and the total distance traveled.

## Daily summary construction

After each salesperson’s detailed rows are ordered, `_build_daily_summary(...)` creates a day-level summary row.

Each summary includes:

- schedule date
- sales ID
- territory ID
- truck group
- customer list
- customer count
- route order
- segment breakdown
- average customer score
- total visit time
- total travel time
- total route km
- customer-to-km details

This is the table that is most useful for operational review.

## Combining all territories

After all territory and truck-group subproblems are solved, the code concatenates the detailed outputs.

The final combined table is sorted by:

- territory
- truck group
- salesperson
- schedule date
- final customer score

Then it is split again into:

- `cold_schedule`
- `normal_schedule`

The per-salesperson daily summaries are also combined into one `daily_schedule` table.

## Validation and diagnostics

The notebook includes a validation layer in `validate_all(...)`.

It checks:

- foreign key consistency
- uniqueness of IDs
- expected row counts
- valid territory assignments
- valid van and salesperson assignments
- cold truck requirement consistency
- customer radius compliance
- tier distribution consistency

If the solver fails, `_diagnose_infeasible(...)` prints likely causes such as:

- insufficient capacity
- no cold-capable salesperson
- all working days blocked
- total slots smaller than customer count

This helps explain whether the issue is a modeling problem, a data problem, or just an overloaded territory.

## What the monthly plan means operationally

The final output is a monthly execution plan, not just a list of customers.

It answers:

- which salesperson owns each customer
- how many times each customer is visited in the month
- on which dates the visits happen
- whether the customer needs cold-chain handling
- how the stops are ordered each day
- how much distance the route covers

So the result is a practical planning artifact for monthly field execution.

## Important design choices

Several choices define the behavior of this scheduler:

- Territory-by-territory solving keeps the model manageable.
- Cold and normal truck separation keeps vehicle constraints valid.
- RFM segment caps control monthly visit frequency.
- Preferred weekdays and cadence bonuses make the plan business-aware.
- Nearest-neighbour post-processing creates a usable route order.
- Validation and infeasibility diagnostics help explain why a schedule may fail.

## Things this code does not do

The system does not:

- solve all territories in one giant global CP model
- use real-time traffic
- build a fully realistic VRP with turn-by-turn routing
- replace operational holiday calendars unless you provide official data

It is a strong planning engine for synthetic or controlled master data, but it is still a planning approximation rather than a live dispatch platform.

## Final summary

In one sentence: the notebook creates the data, the scheduler assigns customers and visit dates with CP-SAT, and the route planner turns those visits into daily driving sequences.

The main logic is:

- generate master data
- compute RFM priority
- split by territory and truck type
- enforce holidays, capacity, and cold-chain rules
- optimize visit timing and salesperson assignment
- route-order each day
- combine everything into a monthly plan

That is the complete flow of the monthly scheduling system.