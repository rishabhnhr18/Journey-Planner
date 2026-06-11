import pandas as pd
import os

workspace_dir = r"d:\Data Science\Basamh\JP_Yash\journey-planner"

files = [
    "monthly_plan_fixed_holiday.xlsx",
    "undervisted.xlsx",
    "unvisited.csv",
    "constraint_violation_analysis_v6.xlsx"
]

print("Checking files:")
for f in files:
    path = os.path.join(workspace_dir, f)
    exists = os.path.exists(path)
    print(f"- {f}: {'Exists' if exists else 'Does NOT exist'} (Size: {os.path.getsize(path) if exists else 'N/A'} bytes)")

# Try to list other files matching unvisited
all_files = os.listdir(workspace_dir)
print("\nFiles in directory containing 'visit' or 'undervist':")
for f in all_files:
    if "visit" in f.lower() or "undervist" in f.lower():
        print(f"- {f}")

# Let's inspect columns/rows
def inspect_excel(filename):
    path = os.path.join(workspace_dir, filename)
    if not os.path.exists(path):
        return
    print(f"\n=== Inspecting {filename} ===")
    if filename.endswith(".csv"):
        df = pd.read_csv(path)
    else:
        df = pd.read_excel(path)
    print(f"Shape: {df.shape}")
    print("Columns:", list(df.columns))
    print("First 3 rows:")
    print(df.head(3).to_string())
    print("-----------------------------------")

inspect_excel("monthly_plan_fixed_holiday.xlsx")
inspect_excel("undervisted.xlsx")
if os.path.exists(os.path.join(workspace_dir, "unvisited.xlsx")):
    inspect_excel("unvisited.xlsx")
else:
    inspect_excel("unvisited.csv")
inspect_excel("constraint_violation_analysis_v6.xlsx")
