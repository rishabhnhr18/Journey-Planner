import os
import pandas as pd

# Define paths relative to this script
current_dir = os.path.dirname(os.path.abspath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, "..", ".."))

xlsx_path = os.path.join(base_dir, "jp_data_output", "jp_data.xlsx")
csv_dir = os.path.join(base_dir, "saudi_master_data_output")

def sync():
    if not os.path.exists(xlsx_path):
        print(f"Error: {xlsx_path} not found. Please run the jp_run_final.ipynb notebook first to generate it.")
        return
        
    print(f"Reading Excel workbook from: {xlsx_path}")
    xls = pd.ExcelFile(xlsx_path)
    
    os.makedirs(csv_dir, exist_ok=True)
    
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        csv_name = f"{sheet_name}.csv"
        csv_path = os.path.join(csv_dir, csv_name)
        
        # Save as CSV
        df.to_csv(csv_path, index=False)
        print(f"Successfully synced: Sheet '{sheet_name}' -> {csv_name} (Rows: {len(df)})")
        
    # Also sync data quality report if exists
    src_report = os.path.join(base_dir, "jp_data_output", "data_quality_report.json")
    dst_report = os.path.join(csv_dir, "data_quality_report.json")
    if os.path.exists(src_report):
        import shutil
        shutil.copy(src_report, dst_report)
        print("Successfully synced: data_quality_report.json")

if __name__ == "__main__":
    sync()
