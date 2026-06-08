import pandas as pd
import numpy as np
from scheduler_2 import MultiSalespersonScheduler

# Load the master data
customer_df = pd.read_csv("saudi_master_data_output/customer.csv")
rfm_scores_df = pd.read_csv("saudi_master_data_output/rfm_scores.csv")
salesperson_df = pd.read_csv("saudi_master_data_output/salesperson.csv")
holiday_df = pd.read_csv("saudi_master_data_output/holiday.csv")
territory_df = pd.read_csv("saudi_master_data_output/territory.csv")
config_df = pd.read_csv("saudi_master_data_output/config.csv")
van_df = pd.read_csv("saudi_master_data_output/van.csv")

# Run scheduler for Riyadh normal group
scheduler = MultiSalespersonScheduler(solver_time_seconds=90)
result = scheduler.create_schedules(
    customer_df      = customer_df,
    rfm_scores_df    = rfm_scores_df,
    salesperson_df   = salesperson_df,
    holiday_df       = holiday_df,
    territory_df     = territory_df,
    config_df        = config_df,
    van_df           = van_df,
    month_start_date = "2026-07-01",
    territory_id     = "TER_RUH",
)

print("\n--- Solver Debug Output ---")
print("Unvisited customers:")
print(result.unvisited_customers[["customer_id", "shop_name", "rfm_segment_final", "gps_lat", "gps_lng"]])

# Inspect detailed schedule counts per salesperson per day
detailed_df = result.detailed_schedule
if not detailed_df.empty:
    daily_counts = detailed_df.groupby(["sales_id", "schedule_date"]).size().reset_index(name="visit_count")
    print("\nVisit counts per salesperson per day (sample):")
    print(daily_counts.head(15))
    print("\nSummary of daily visit counts:")
    print(daily_counts["visit_count"].describe())
    
    # Check assignment of customers to salespeople
    assigned_sp = detailed_df.groupby("customer_id")["sales_id"].first().reset_index()
    sp_counts = assigned_sp.groupby("sales_id").size().reset_index(name="customer_count")
    print("\nNumber of unique customers assigned to each salesperson:")
    print(sp_counts)
