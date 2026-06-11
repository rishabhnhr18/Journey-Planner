import json
import os

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    notebook_path = os.path.join(script_dir, "code", "final", "jp_run_final.ipynb")
    if not os.path.exists(notebook_path):
        print(f"Error: Could not find notebook at {notebook_path}")
        return

    print(f"Reading {notebook_path}...")
    with open(notebook_path, "r", encoding="utf-8") as f:
        nb = json.load(f)

    replacements = [
        # Cell 1: Import os and define global OUTPUT_DIR
        (
            'import sys, subprocess, importlib.util\n',
            'import os, sys, subprocess, importlib.util\n'
        ),
        # Define the global OUTPUT_DIR variable at the top of Cell 1 imports
        (
            'import os, sys, subprocess, importlib.util\n',
            'import os, sys, subprocess, importlib.util\n'
            'OUTPUT_DIR = os.path.abspath(os.path.join(os.getcwd(), "..", "..", "jp_data_output"))\n'
            'os.makedirs(OUTPUT_DIR, exist_ok=True)\n'
        ),
        (
            'HOLIDAY_CSV_PATH = "D:\\Data Science\\Basamh\\JP_Yash\\journey-planner\\saudi_master_data_output\\holiday_1.csv"',
            'HOLIDAY_CSV_PATH = os.path.abspath(os.path.join(os.getcwd(), "..", "..", "saudi_master_data_output", "holiday_1.csv"))'
        ),
        (
            'HOLIDAY_CSV_PATH = "D:\\\\Data Science\\\\Basamh\\\\JP_Yash\\\\journey-planner\\\\saudi_master_data_output\\\\holiday_1.csv"',
            'HOLIDAY_CSV_PATH = os.path.abspath(os.path.join(os.getcwd(), "..", "..", "saudi_master_data_output", "holiday_1.csv"))'
        ),
        (
            'def generate_all(seed=42, output_dir="jp_data_output", write_files=True):',
            'def generate_all(seed=42, output_dir=OUTPUT_DIR, write_files=True):'
        ),
        (
            'outputs, report = generate_all(seed=42)',
            'outputs, report = generate_all(seed=42, output_dir=OUTPUT_DIR)'
        ),
        
        # Cell 2: Save visit.csv
        (
            'out = Path("saudi_master_data_output"); out.mkdir(parents=True, exist_ok=True)\n',
            'out = Path(OUTPUT_DIR); out.mkdir(parents=True, exist_ok=True)\n'
        ),
        (
            'out = Path("jp_data_output"); out.mkdir(parents=True, exist_ok=True)\n',
            'out = Path(OUTPUT_DIR); out.mkdir(parents=True, exist_ok=True)\n'
        ),
        
        # Cell 5: Print output files inside folder
        (
            'for path in sorted(__import__("pathlib").Path("saudi_master_data_output").glob("*")):',
            'for path in sorted(__import__("pathlib").Path(OUTPUT_DIR).glob("*")):'
        ),
        (
            'for path in sorted(__import__("pathlib").Path("jp_data_output").glob("*")):',
            'for path in sorted(__import__("pathlib").Path(OUTPUT_DIR).glob("*")):'
        ),
        
        # Cell 6: Scheduler final import & instantiation & call
        (
            'from scheduler_final import MultiSalespersonScheduler\n',
            'from scheduler_final import MultiSalesManScheduler\n'
        ),
        (
            'scheduler = MultiSalespersonScheduler(solver_time_seconds=90)\n',
            'scheduler = MultiSalesManScheduler(config_df=config_df)\n'
        ),
        (
            'scheduler = MultiSalesManScheduler(solver_time_seconds=90)\n',
            'scheduler = MultiSalesManScheduler(config_df=config_df)\n'
        ),
        (
            'result_ruh = scheduler.create_schedules(\n',
            'result_ruh = scheduler.create_monthly_schedule(\n'
        ),
        
        # Cell 8: Validator import and output
        (
            'from validate_schedule_final import *\n',
            'from validate_schedule_final import validate_schedule_final\n'
        ),
        (
            'checks = validate_schedule(result, customer_df, salesperson_df, van_df,\n',
            'checks = validate_schedule_final(result, customer_df, salesperson_df, van_df,\n'
        ),
        (
            '                           territory_df, holiday_df, config_df, rfm_scores_df,\n',
            '                                 territory_df, holiday_df, config_df, rfm_scores_df,\n'
        ),
        (
            '                           month_start="2026-07-01", territory_id= "TER_RUH")',
            '                                 month_start="2026-07-01", territory_id="TER_RUH")'
        ),
        (
            'result.unvisited_customers.to_csv("unvisited.csv", index=False)',
            'result.unvisited_customers.to_csv(os.path.join(OUTPUT_DIR, "unvisited.csv"), index=False)'
        ),
        (
            'result.unvisited_customers.to_csv("jp_data_output/unvisited.csv", index=False)',
            'result.unvisited_customers.to_csv(os.path.join(OUTPUT_DIR, "unvisited.csv"), index=False)'
        ),
        
        # Cell 9: scheduler_2 import map helper
        (
            'from scheduler_2 import build_territory_day_map, build_stop_to_stop_map\n',
            'import sys, os\nsys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))\nfrom scheduler_2 import build_territory_day_map, build_stop_to_stop_map\n'
        ),
        
        # Cell 10: distances file output path (commented code)
        (
            '# from scheduler import export_stop_to_stop_monthly_excel\n',
            '# import sys, os\n# sys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))\n# from scheduler import export_stop_to_stop_monthly_excel\n'
        ),
        (
            '#     filepath="distances_july01.xlsx"\n',
            '#     filepath=os.path.join(OUTPUT_DIR, "distances_july01.xlsx")\n'
        ),
        
        # Cell 11: monthly plan file path
        (
            'excel_file_path = "monthly_plan_fixed_holiday.xlsx"\n',
            'excel_file_path = os.path.join(OUTPUT_DIR, "monthly_plan_fixed_holiday.xlsx")\n'
        ),
        (
            'excel_file_path = "jp_data_output/monthly_plan_fixed_holiday.xlsx"\n',
            'excel_file_path = os.path.join(OUTPUT_DIR, "monthly_plan_fixed_holiday.xlsx")\n'
        ),
        (
            'excel_file_path = f"D:\\\\Data Science\\\\Basamh\\\\JP_Yash\\\\journey-planner\\\\jp_data_output\\\\montly_plan_for_{date_in_string}.xlsx"',
            'excel_file_path = os.path.join(OUTPUT_DIR, f"monthly_plan_for_{date_in_string}.xlsx")'
        ),
        (
            'excel_file_path = f"D:\\Data Science\\Basamh\\JP_Yash\\journey-planner\\jp_data_output\\montly_plan_for_{date_in_string}.xlsx"',
            'excel_file_path = os.path.join(OUTPUT_DIR, f"monthly_plan_for_{date_in_string}.xlsx")'
        ),
        
        # Cell 14: Save undervisted.xlsx
        (
            'from scheduler_2 import export_under_visited_excel\n',
            'import sys, os\nsys.path.append(os.path.abspath(os.path.join(os.getcwd(), "..", "..")))\nfrom scheduler_2 import export_under_visited_excel\n'
        ),
        (
            'export_under_visited_excel(result, "undervisted.xlsx")',
            'export_under_visited_excel(result, os.path.join(OUTPUT_DIR, "undervisted.xlsx"))'
        ),
        (
            'export_under_visited_excel(result, "jp_data_output/undervisted.xlsx")',
            'export_under_visited_excel(result, os.path.join(OUTPUT_DIR, "undervisted.xlsx"))'
        ),
        (
            'export_under_visited_excel(result, "D:\\\\Data Science\\\\Basamh\\\\JP_Yash\\\\journey-planner\\\\jp_data_output\\\\undervisted.xlsx")',
            'export_under_visited_excel(result, os.path.join(OUTPUT_DIR, "undervisted.xlsx"))'
        ),
        (
            'export_under_visited_excel(result, "D:\\Data Science\\Basamh\\JP_Yash\\journey-planner\\jp_data_output\\undervisted.xlsx")',
            'export_under_visited_excel(result, os.path.join(OUTPUT_DIR, "undervisted.xlsx"))'
        ),
        
        # Cell 16: reload and validate
        (
            'import validate_scheduler\n',
            'import validate_schedule_final\n'
        ),
        (
            'importlib.reload(validate_scheduler)\n',
            'importlib.reload(validate_schedule_final)\n'
        ),
        (
            'from validate_scheduler import validate_schedule\n',
            'from validate_schedule_final import validate_schedule_final\n'
        ),
        (
            'checks = validate_schedule(\n',
            'checks = validate_schedule_final(\n'
        )
    ]

    modified_count = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        
        source = cell.get("source", [])
        combined_source = "".join(source)
        modified = combined_source
        
        for old, new in replacements:
            if old in modified and new not in modified:
                modified = modified.replace(old, new)
                
        if modified != combined_source:
            new_source = []
            lines = modified.splitlines(keepends=True)
            for line in lines:
                new_source.append(line)
            cell["source"] = new_source
            modified_count += 1

    if modified_count > 0:
        print(f"Successfully modified {modified_count} cells. Saving changes...")
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)
        print("Done.")
    else:
        print("No matches found; notebook was already modified or matched differently.")

if __name__ == "__main__":
    main()
