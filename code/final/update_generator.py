import json
import os

notebook_path = os.path.join(os.path.dirname(__file__), "jp_run_final.ipynb")

if os.path.exists(notebook_path):
    with open(notebook_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    updated_utils = False
    updated_gen = False
    
    # Define functions to inject
    is_on_land_code = (
        "\n"
        "def is_on_land(lat, lng, tid, locality):\n"
        "    if tid == 'TER_JED':\n"
        "        if 'Zahra' in locality or 'Zahrah' in locality:\n"
        "            return lng >= 39.128\n"
        "        elif 'Salamah' in locality:\n"
        "            return lng >= 39.138\n"
        "        elif 'Rawdah' in locality:\n"
        "            return lng >= 39.152\n"
        "        elif 'Hamra' in locality:\n"
        "            return lng >= 39.158\n"
        "        else:\n"
        "            lng_coast = 39.19 - 0.26 * (lat - 21.342)\n"
        "            return lng >= lng_coast\n"
        "    elif tid == 'TER_DMM':\n"
        "        if 'Shati' in locality:\n"
        "            return lng <= 50.110 and lat <= 26.485\n"
        "        elif 'Mazruiyah' in locality:\n"
        "            return lng <= 50.108\n"
        "        else:\n"
        "            return lng <= 50.110\n"
        "    return True\n"
    )

    new_gen_loop = [
        "            locality, base_lat, base_lng = random.choice(LOCALITIES[tid])\n",
        "            for _ in range(500):\n",
        "                lat, lng = jitter_location(base_lat, base_lng, radius_km=2.5)\n",
        "                if haversine_km(lat,lng,ter.center_lat,ter.center_lng) <= ter.radius_km and is_on_land(lat, lng, tid, locality):\n",
        "                    break\n",
        "            else:\n",
        "                lat, lng = base_lat, base_lng\n",
        "                if tid == 'TER_JED' and 'Hamra' in locality:\n",
        "                    lng = 39.162\n",
        "                elif tid == 'TER_DMM' and 'Shati' in locality:\n",
        "                    lng = 50.105\n"
    ]

    for cell in data.get("cells", []):
        if cell.get("cell_type") == "code":
            source = cell.get("source", [])
            source_str = "".join(source)
            
            # 1. Update utility cell (add is_on_land function)
            if "def jitter_location" in source_str and "def is_on_land" not in source_str:
                for idx, line in enumerate(source):
                    if "return float(lat+lat_j), float(lng+lng_j)" in line:
                        source.insert(idx + 1, is_on_land_code)
                        cell["source"] = source
                        updated_utils = True
                        break
            
            # 2. Update customer generator cell (inject checks directly inside generation loop)
            if "def generate_customers" in source_str and "is_on_land(" not in source_str:
                start_idx = -1
                end_idx = -1
                for idx, line in enumerate(source):
                    if "locality, base_lat, base_lng = random.choice(LOCALITIES[tid])" in line:
                        start_idx = idx
                    if start_idx != -1 and "lat, lng = base_lat, base_lng" in line:
                        end_idx = idx
                        break
                
                if start_idx != -1 and end_idx != -1:
                    # Replace lines from start_idx to end_idx + 1 (which includes lat, lng = base_lat, base_lng)
                    new_source = source[:start_idx] + new_gen_loop + source[end_idx + 1:]
                    cell["source"] = new_source
                    updated_gen = True
                    
    if updated_utils or updated_gen:
        with open(notebook_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        print("Successfully updated jp_run_final.ipynb utility functions and customer generation cell!")
    else:
        print("Note: Notebook was already updated or target lines not found.")
else:
    print(f"Error: Notebook not found at {notebook_path}")
