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
            for i, line in enumerate(source):
                if "customer_df    = generate_customers(territory_df)" in line and "clean_coastal_coordinates" not in "".join(source):
                    # Insert the clean step after this line
                    source.insert(i + 1, "    from scheduler_final import clean_coastal_coordinates\n")
                    source.insert(i + 2, "    customer_df    = clean_coastal_coordinates(customer_df)\n")
                    cell["source"] = source
                    updated = True
                    break
            if updated:
                break
                
    if updated:
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print("Successfully updated jp_run_final.ipynb with clean_coastal_coordinates step!")
    else:
        print("Note: Notebook was already updated or target line not found.")
else:
    print(f"Error: Notebook not found at {notebook_path}")
