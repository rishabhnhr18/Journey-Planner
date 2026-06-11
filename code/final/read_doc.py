import string

def extract_printable_from_doc(doc_path, txt_path):
    print(f"Reading from {doc_path}...")
    try:
        with open(doc_path, "rb") as f:
            data = f.read()
            
        # Try to find printable sequences
        printable_chars = set(string.printable.encode('ascii'))
        current_str = []
        strings = []
        
        for byte in data:
            if byte in printable_chars:
                current_str.append(chr(byte))
            else:
                if len(current_str) >= 4:
                    s = "".join(current_str).strip()
                    if s:
                        strings.append(s)
                current_str = []
        if len(current_str) >= 4:
            strings.append("".join(current_str).strip())
            
        # Filter strings to remove noise
        filtered_strings = []
        for s in strings:
            # ignore strings that are mostly punctuation or noise
            num_letters = sum(1 for c in s if c.isalnum())
            if num_letters > len(s) * 0.4 and len(s) > 3:
                filtered_strings.append(s)
                
        # Write to txt file
        with open(txt_path, "w", encoding="utf-8") as out:
            out.write("\n".join(filtered_strings))
        print(f"Extracted text saved to {txt_path}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import os
    base_dir = r"d:\Data Science\Basamh\JP_Yash\journey-planner"
    doc_path = os.path.join(base_dir, "Journey_Planner_Constraints_Summary.doc")
    txt_path = os.path.join(base_dir, "extracted_doc.txt")
    extract_printable_from_doc(doc_path, txt_path)
