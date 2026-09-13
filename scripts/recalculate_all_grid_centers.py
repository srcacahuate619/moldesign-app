import json
import os
import glob
import pandas as pd

# List of non-ligand HETATM residue names to ignore when searching for co-crystallized ligands
IGNORE_HETATMS = {
    "HOH", "WAT", "DOD", "TIP", "SOL",  # Waters
    "CL", "NA", "K", "MG", "CA", "ZN", "MN", "FE", "CU", "NI", "CO",  # Common ions
    "SO4", "PO4", "NO3", "EDO", "GOL", "PEG", "P4G", "PG4", "DMS", "AZI", "CON", "ACT", "FMT" # Buffer/crystallization agents
}

def calculate_hetatm_centroid(pdb_path):
    if not os.path.exists(pdb_path):
        return None
    
    het_xs, het_ys, het_zs = [], [], []
    atom_xs, atom_ys, atom_zs = [], [], []
    
    with open(pdb_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("ATOM"):
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    atom_xs.append(x)
                    atom_ys.append(y)
                    atom_zs.append(z)
                except Exception:
                    pass
            elif line.startswith("HETATM"):
                res_name = line[17:20].strip()
                if res_name not in IGNORE_HETATMS:
                    try:
                        x = float(line[30:38])
                        y = float(line[38:46])
                        z = float(line[46:54])
                        het_xs.append(x)
                        het_ys.append(y)
                        het_zs.append(z)
                    except Exception:
                        pass
                        
    if het_xs:
        # Centroid of co-crystallized ligand
        return (
            round(sum(het_xs) / len(het_xs), 3),
            round(sum(het_ys) / len(het_ys), 3),
            round(sum(het_zs) / len(het_zs), 3)
        )
    elif atom_xs:
        # Fallback: centroid of protein ATOMs
        return (
            round(sum(atom_xs) / len(atom_xs), 3),
            round(sum(atom_ys) / len(atom_ys), 3),
            round(sum(atom_zs) / len(atom_zs), 3)
        )
    return None

def find_pdb_file(pdb_id):
    pdb_id_upper = pdb_id.upper()
    target_lib = "d:/moldesign-build/data/target_library"
    if os.path.exists(target_lib):
        for root, dirs, files in os.walk(target_lib):
            for f in files:
                if f.upper() == f"{pdb_id_upper}.PDB" or f.upper().startswith(f"{pdb_id_upper}_") or pdb_id_upper in f.upper():
                    return os.path.join(root, f)
    # Search targets directory
    targets_dir = "d:/moldesign-build/data/targets"
    if os.path.exists(targets_dir):
        for root, dirs, files in os.walk(targets_dir):
            for f in files:
                if f.upper() == f"{pdb_id_upper}.PDB":
                    return os.path.join(root, f)
    return None

def main():
    json_path = "d:/moldesign-build/curated_targets.json"
    csv_path = "d:/moldesign-build/curated_targets.csv"
    
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found!")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        targets = json.load(f)
        
    print(f"Loaded {len(targets)} targets from {json_path}")
    
    updated_count = 0
    missing_pdb_count = 0
    
    for target in targets:
        gx = target.get("grid_center_x", 0.0)
        gy = target.get("grid_center_y", 0.0)
        gz = target.get("grid_center_z", 0.0)
        
        if gx == 0.0 and gy == 0.0 and gz == 0.0:
            pdb_id = target.get("pdb_id", "")
            pdb_path = find_pdb_file(pdb_id)
            if pdb_path:
                centroid = calculate_hetatm_centroid(pdb_path)
                if centroid:
                    target["grid_center_x"] = centroid[0]
                    target["grid_center_y"] = centroid[1]
                    target["grid_center_z"] = centroid[2]
                    updated_count += 1
                    print(f"Updated {pdb_id}: ({centroid[0]}, {centroid[1]}, {centroid[2]}) from {pdb_path}")
                else:
                    print(f"Warning: Could not compute centroid for {pdb_id} from {pdb_path}")
            else:
                missing_pdb_count += 1
                print(f"Warning: PDB file for {pdb_id} not found!")
                
    print(f"\nSuccessfully updated {updated_count} targets.")
    print(f"Missing PDBs: {missing_pdb_count}")
    
    # Check remaining zeros
    remaining_zeros = [t for t in targets if t.get("grid_center_x") == 0.0 and t.get("grid_center_y") == 0.0 and t.get("grid_center_z") == 0.0]
    print(f"Remaining (0,0,0) targets: {len(remaining_zeros)}")
    
    # Save JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(targets, f, indent=2, ensure_ascii=False)
    print(f"Saved updated JSON to {json_path}")
    
    # Sync CSV
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        for target in targets:
            pdb_id = target.get("pdb_id")
            if pdb_id and "pdb_id" in df.columns:
                mask = df["pdb_id"] == pdb_id
                if mask.any():
                    df.loc[mask, "grid_center_x"] = target["grid_center_x"]
                    df.loc[mask, "grid_center_y"] = target["grid_center_y"]
                    df.loc[mask, "grid_center_z"] = target["grid_center_z"]
        df.to_csv(csv_path, index=False)
        print(f"Saved updated CSV to {csv_path}")

if __name__ == "__main__":
    main()
