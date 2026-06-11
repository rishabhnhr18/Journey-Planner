import os

def update_doc():
    base_dir = r"d:\Data Science\Basamh\JP_Yash\journey-planner"
    file_path = os.path.join(base_dir, "Journey_Planner_Constraints_Summary.doc")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    try:
        # Read as UTF-16LE
        with open(file_path, "r", encoding="utf-16le") as f:
            content = f.read()
            
        target = """<h3>2.1 Salesperson Assignment Consistency</h3>
<ul>
    <li><strong>Code Lines:</strong> 1040 – 1046</li>
    <li><strong>Logic:</strong> A salesperson can only schedule a visit to a customer on a specific date if that salesperson is assigned to that customer for the month.</li>
    <li><strong>Math Form:</strong> <span class="code-inline">visit_of_customer_by_salesman_on_that_day[c, s, d] &le; assigned_salesman_to_customer[c, s]</span></li>
</ul>"""

        replacement = """<h3>2.1 Salesperson Assignment Consistency</h3>
<ul>
    <li><strong>Code Lines:</strong> 1040 – 1046</li>
    <li><strong>Logic:</strong> A salesperson can only schedule a visit to a customer on a specific date if that salesperson is assigned to that customer for the month.</li>
    <li><strong>Math Form:</strong> <span class="code-inline">visit_of_customer_by_salesman_on_that_day[c, s, d] &le; assigned_salesman_to_customer[c, s]</span></li>
    <li><strong>Note on Multi-Salesperson Lock:</strong> The solver does NOT enforce a single-salesperson-per-customer assignment lock (i.e., there is no constraint like <span class="code-inline">&sum;<sub>s</sub> assigned_salesman_to_customer[c, s] &le; 1</span>). Therefore, multiple salespeople are allowed to serve the same customer on different days during the month.</li>
</ul>"""

        # Normalize line endings to avoid platform mismatch
        content_norm = content.replace("\r\n", "\n")
        target_norm = target.replace("\r\n", "\n")
        replacement_norm = replacement.replace("\r\n", "\n")
        
        if target_norm in content_norm:
            new_content = content_norm.replace(target_norm, replacement_norm)
            # Write back as UTF-16LE with original line endings
            with open(file_path, "w", encoding="utf-16le") as f:
                f.write(new_content)
            print("Successfully updated Journey_Planner_Constraints_Summary.doc!")
        else:
            print("Target block not found in document. Trying substring matching...")
            # Fallback to a smaller search string
            small_target = "visit_of_customer_by_salesman_on_that_day[c, s, d] &le; assigned_salesman_to_customer[c, s]</span></li>"
            if small_target in content_norm:
                small_replacement = small_target + "\n    <li><strong>Note on Multi-Salesperson Lock:</strong> The solver does NOT enforce a single-salesperson-per-customer assignment lock (i.e., there is no constraint like <span class="code-inline">&sum;<sub>s</sub> assigned_salesman_to_customer[c, s] &le; 1</span>). Therefore, multiple salespeople are allowed to serve the same customer on different days during the month.</li>"
                new_content = content_norm.replace(small_target, small_replacement)
                with open(file_path, "w", encoding="utf-16le") as f:
                    f.write(new_content)
                print("Successfully updated Journey_Planner_Constraints_Summary.doc using substring match!")
            else:
                print("Could not find insertion point in file.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    update_doc()
