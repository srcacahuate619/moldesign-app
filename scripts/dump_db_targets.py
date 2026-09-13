import sqlite3
import json
import os
from pathlib import Path

def main():
    db_path = os.path.expanduser("~/MolDesign/data/moldesign_local.db")
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get columns
    c.execute("PRAGMA table_info(targets)")
    columns = [row["name"] for row in c.fetchall()]
    print("Columns:", columns)
    
    c.execute("SELECT * FROM targets")
    rows = []
    for r in c.fetchall():
        row_dict = {}
        for col in columns:
            val = r[col]
            # Deserialize JSON fields if necessary (like hotspots or cofactors_whitelist)
            if col in ("hotspots", "cofactors_whitelist") and isinstance(val, str):
                try:
                    row_dict[col] = json.loads(val)
                except Exception:
                    row_dict[col] = val
            else:
                row_dict[col] = val
        rows.append(row_dict)
        
    print(f"Loaded {len(rows)} targets.")
    
    # Save to JSON in root
    out_path = Path("D:/moldesign-build/curated_targets.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        
    print(f"Saved targets seed to {out_path}")
    conn.close()

if __name__ == "__main__":
    main()
