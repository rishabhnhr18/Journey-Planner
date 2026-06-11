import json
import os

notebook_path = os.path.join(os.path.dirname(__file__), "jp_run_final.ipynb")

if os.path.exists(notebook_path):
    with open(notebook_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    updated = False
    for cell in data.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            new_source = []
            skip = False
            for line in source:
                if "from scheduler_final import clean_coastal_coordinates" in line:
                    updated = True
                    continue
                if "customer_df    = clean_coastal_coordinates(customer_df)" in line:
                    updated = True
                    continue
                new_source.append(line)
            cell["source"] = new_source
            
    if updated:
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print("Successfully removed external scheduler_final dependency from jp_run_final.ipynb!")
    else:
        print("Note: Dependency lines were not found in the notebook.")
else:
    print(f"Error: Notebook not found at {notebook_path}")
