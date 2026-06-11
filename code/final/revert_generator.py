import json
import os

notebook_path = os.path.join(os.path.dirname(__file__), "jp_run_final.ipynb")

if os.path.exists(notebook_path):
    with open(notebook_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    updated = False
    
    # Original loop inside generate_customers
    original_gen_loop = [
        "            locality, base_lat, base_lng = random.choice(LOCALITIES[tid])\n",
        "            for _ in range(100):\n",
        "                lat, lng = jitter_location(base_lat, base_lng, radius_km=2.5)\n",
        "                if haversine_km(lat,lng,ter.center_lat,ter.center_lng) <= ter.radius_km: break\n",
        "            else:\n",
        "                lat, lng = base_lat, base_lng\n"
    ]

    for cell in data.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            source_str = "".join(source)
            
            # 1. Revert utility cell (remove is_on_land function)
            if "def is_on_land" in source_str:
                new_source = []
                in_is_on_land = False
                for line in source:
                    if "def is_on_land(" in line:
                        in_is_on_land = True
                        continue
                    if in_is_on_land:
                        # is_on_land ends at the next function definition or major section
                        if line.startswith("def ") or line.startswith("# ─────────────────"):
                            in_is_on_land = False
                        else:
                            continue
                    new_source.append(line)
                cell["source"] = new_source
                updated = True
            
            # 2. Revert customer generator cell (restore original loop)
            if "def generate_customers" in source_str and "is_on_land(" in source_str:
                start_idx = -1
                end_idx = -1
                for idx, line in enumerate(source):
                    if "locality, base_lat, base_lng = random.choice(LOCALITIES[tid])" in line:
                        start_idx = idx
                    if start_idx != -1 and "lng = 50.105" in line:
                        end_idx = idx
                        break
                
                if start_idx != -1 and end_idx != -1:
                    new_source = source[:start_idx] + original_gen_loop + source[end_idx + 1:]
                    cell["source"] = new_source
                    updated = True
                    
    if updated:
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print("Successfully reverted jp_run_final.ipynb back to its original state!")
    else:
        print("Note: No modifications from update_generator.py were found to revert.")
else:
    print(f"Error: Notebook not found at {notebook_path}")
