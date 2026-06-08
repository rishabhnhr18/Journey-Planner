import sys
import os
import pandas as pd

# Add the final code directory to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "code", "final")))

from scheduler_final import MultiSalesManScheduler
from validate_schedule_final import validate_schedule_final

print("Loading master data...")
customer_df = pd.read_csv("saudi_master_data_output/customer.csv")
rfm_scores_df = pd.read_csv("saudi_master_data_output/rfm_scores.csv")
salesperson_df = pd.read_csv("saudi_master_data_output/salesperson.csv")
holiday_df = pd.read_csv("saudi_master_data_output/holiday.csv")
territory_df = pd.read_csv("saudi_master_data_output/territory.csv")
config_df = pd.read_csv("saudi_master_data_output/config.csv")
van_df = pd.read_csv("saudi_master_data_output/van.csv")

print("Initializing scheduler...")
scheduler = MultiSalesManScheduler(config_df=config_df)

print("Running monthly schedule for Riyadh (TER_RUH)...")
result = scheduler.create_monthly_schedule(
    customer_df      = customer_df,
    rfm_scores_df    = rfm_scores_df,
    salesperson_df   = salesperson_df,
    holiday_df       = holiday_df,
    territory_df     = territory_df,
    van_df           = van_df,
    month_start_date = "2026-07-01",
    territory_id     = "TER_RUH",
)

print("\nRunning validation on the schedule...")
checks = validate_schedule_final(
    result,
    customer_df=customer_df,
    salesperson_df=salesperson_df,
    van_df=van_df,
    territory_df=territory_df,
    holiday_df=holiday_df,
    config_df=config_df,
    rfm_scores_df=rfm_scores_df,
    month_start="2026-07-01",
    territory_id="TER_RUH"
)

# Summarize errors
errors = 0
for name, failures in checks.items():
    # Only report hard constraints as errors, excluding [INFO] lines
    hard_failures = [f for f in failures if not f.startswith("[INFO]")]
    if hard_failures:
        print(f"❌ {name}: {len(hard_failures)} violations!")
        for fail in hard_failures[:5]:
            print(f"   - {fail}")
        errors += len(hard_failures)
    else:
        print(f"✅ {name}: OK")

if errors == 0:
    print("\n🎉 SUCCESS! All hard constraints passed.")
else:
    print(f"\n❌ FAILED! Found {errors} hard constraint violations.")
