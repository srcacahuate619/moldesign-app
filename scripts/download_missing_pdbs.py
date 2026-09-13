import urllib.request
import os
import json
import pandas as pd
from recalculate_all_grid_centers import calculate_hetatm_centroid

missing = {
    "1BN1": "d:/moldesign-build/data/target_library/04_metabolism/1BN1.pdb",
    "1F0R": "d:/moldesign-build/data/target_library/18_cardiovascular/1F0R.pdb",
    "1GPK": "d:/moldesign-build/data/target_library/15_neurodegeneration/1GPK.pdb",
    "1XP0": "d:/moldesign-build/data/target_library/18_cardiovascular/1XP0.pdb"
}

for pdb_id, dest in missing.items():
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"Downloading {url} to {dest}...")
    try:
        urllib.request.urlretrieve(url, dest)
        print(f"Successfully downloaded {pdb_id}")
    except Exception as e:
        print(f"Failed to download {pdb_id}: {e}")

# Now update JSON and CSV
json_path = "d:/moldesign-build/curated_targets.json"
csv_path = "d:/moldesign-build/curated_targets.csv"

with open(json_path, "r", encoding="utf-8") as f:
    targets = json.load(f)

for t in targets:
    pdb_id = t.get("pdb_id")
    if pdb_id in missing:
        dest = missing[pdb_id]
        centroid = calculate_hetatm_centroid(dest)
        if centroid:
            t["grid_center_x"] = centroid[0]
            t["grid_center_y"] = centroid[1]
            t["grid_center_z"] = centroid[2]
            print(f"Updated {pdb_id}: {centroid}")

with open(json_path, "w", encoding="utf-8") as f:
    json.dump(targets, f, indent=2, ensure_ascii=False)

if os.path.exists(csv_path):
    df = pd.read_csv(csv_path)
    for t in targets:
        pdb_id = t.get("pdb_id")
        if pdb_id in missing:
            mask = df["pdb_id"] == pdb_id
            if mask.any():
                df.loc[mask, "grid_center_x"] = t["grid_center_x"]
                df.loc[mask, "grid_center_y"] = t["grid_center_y"]
                df.loc[mask, "grid_center_z"] = t["grid_center_z"]
    df.to_csv(csv_path, index=False)

# Final check of remaining zeros
zeros = [t for t in targets if t.get("grid_center_x") == 0.0 and t.get("grid_center_y") == 0.0 and t.get("grid_center_z") == 0.0]
print(f"FINAL AUDIT: Remaining (0,0,0) targets across ENTIRE library: {len(zeros)}")
