import json
import os
import csv
import sqlite3
import urllib.request
from pathlib import Path
from collections import Counter

# Complete list of non-ligand HETATMs (waters, common ions, buffers, solvents, glycans)
NON_DRUG_HETATMS = {
    # Waters
    "HOH", "WAT", "DOD", "TIP", "SOL", "H2O",
    # Buffer/crystallization/solvents/salts
    "SO4", "PO4", "NO3", "EDO", "GOL", "PEG", "P4G", "PG4", "DMS", "AZI", "CON", "ACT", "FMT", "ACE", 
    "NH4", "ACN", "EPE", "MES", "TRS", "TRIS", "HEPES", "ADA", "MPD", "1PE", "PGE", "P6G", "FLC", 
    "CIT", "B3N", "DB8", "BCT", "UNX", "UNL", "IPA", "ETOH", "ME2", "DMF", "DTT", "BME", "CL", "NA",
    # Non-drug glycans/sugars
    "NAG", "NDG", "BMA", "MAN", "FUC", "GAL", "GLC", "BGC", "FUL", "SIA", "GLA", "XYP", "RAM", "RIB", "BDF", "AAL"
}

# Catalytic metal ions for metalloenzymes/metalloproteins
CATALYTIC_METALS = {"ZN", "FE", "MN", "MG", "CA", "CU", "NI", "CO", "CD"}

# Rutas RELATIVAS al repositorio. Antes eran absolutas —`d:/moldesign-build/...`
# y `C:/Users/<autor>/MolDesign/data/...`— asi que este script solo funcionaba en
# la maquina de quien lo escribio, y de paso publicaba su nombre de usuario en un
# repositorio publico.
RAIZ = Path(__file__).resolve().parents[1]

TARGET_LIB = RAIZ / "data" / "target_library"
TARGETS_DIR = RAIZ / "data" / "targets"
JSON_PATH = RAIZ / "curated_targets.json"
CSV_PATH = RAIZ / "curated_targets.csv"

#: La base local vive FUERA del repositorio: la escribe la aplicacion instalada
#: en el directorio de datos del usuario. `LOCAL_DATA_DIR` es la misma variable
#: que usa el backend (ver `utils/local_storage.py`), asi que apuntan al mismo
#: sitio sin que este script tenga que adivinarlo.
DB_PATH = Path(
    os.environ.get("LOCAL_DATA_DIR")
    or (Path.home() / "MolDesign" / "data")
) / "moldesign_local.db"

def download_pdb_from_rcsb(pdb_id: str) -> Path | None:
    """Download PDB from RCSB if missing locally."""
    pdb_id = pdb_id.upper()
    dest_dir = TARGET_LIB / "downloaded"
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_path = dest_dir / f"{pdb_id}.pdb"
    if file_path.exists() and file_path.stat().st_size > 1000:
        return file_path
    
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    try:
        urllib.request.urlretrieve(url, str(file_path))
        if file_path.exists() and file_path.stat().st_size > 1000:
            print(f"  [DOWNLOAD] Downloaded {pdb_id}.pdb from RCSB ({file_path.stat().st_size} bytes)")
            return file_path
    except Exception as e:
        print(f"  [WARN] Could not download {pdb_id} from RCSB: {e}")
    return None

def find_pdb_file(pdb_id: str) -> Path | None:
    pdb_id_upper = pdb_id.upper()
    pdb_id_lower = pdb_id.lower()
    
    for p in TARGET_LIB.glob(f"**/{pdb_id_upper}.pdb"):
        return p
    for p in TARGET_LIB.glob(f"**/{pdb_id_lower}.pdb"):
        return p
    for p in TARGETS_DIR.glob(f"**/{pdb_id_upper}.pdb"):
        return p
    for p in TARGETS_DIR.glob(f"**/{pdb_id_lower}.pdb"):
        return p
        
    return download_pdb_from_rcsb(pdb_id_upper)

def extract_accurate_pocket_centroid(pdb_path: Path):
    """El centro del sitio, delegado al backend.

    ESTO ERA UNA CUARTA COPIA del mismo algoritmo -las otras tres: el backend,
    `scripts/universal_metal_score.py` y la transcripcion del manifiesto de M5-
    y arrastraba los dos defectos que el backend corrigio el 2026-09-13:

      * agrupaba los HETATM por NOMBRE de residuo, asi que con el mismo ligando
        en varias cadenas el "centroide del ligando" era el promedio de todas
        las copias, que cae entre ellas y no dentro de ninguna. Medido sobre las
        411 estructuras locales: 139 daban un centro mas lejos del semilado de
        la caja que la copia mas cercana;
      * elegia el metal por NUMERO de iones, que devuelve el estructural: MMP9
        tiene cinco calcios y un zinc catalitico.

    Y es justo el script que calibra `curated_targets.json`, asi que una copia
    con el defecto lo reintroduciria en el catalogo en la siguiente pasada.
    """
    import sys

    backend = str(RAIZ / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from services.chemistry.protein_surgery import (  # noqa: PLC0415
        extract_accurate_pocket_centroid as _centroide,
    )

    return _centroide(str(pdb_path))


def main():
    print("=== RECALIBRATING ALL 386 TARGET ACTIVE SITE GRID CENTERS ===")
    if not JSON_PATH.exists():
        print(f"Error: {JSON_PATH} not found!")
        return

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        targets = json.load(f)

    print(f"Loaded {len(targets)} targets from {JSON_PATH}")

    updated_count = 0
    method_counts = Counter()
    
    for t in targets:
        pdb_id = t.get("pdb_id", "").upper()
        old_center = (t.get("grid_center_x", 0.0), t.get("grid_center_y", 0.0), t.get("grid_center_z", 0.0))
        
        pdb_path = find_pdb_file(pdb_id)
        if not pdb_path:
            print(f"  [MISSING PDB] Could not locate or download PDB for {pdb_id}")
            continue
            
        new_center, method = extract_accurate_pocket_centroid(pdb_path)
        if new_center:
            method_counts[method.split()[0]] += 1
            t["grid_center_x"] = new_center[0]
            t["grid_center_y"] = new_center[1]
            t["grid_center_z"] = new_center[2]
            
            # Check distance delta
            dx = old_center[0] - new_center[0]
            dy = old_center[1] - new_center[1]
            dz = old_center[2] - new_center[2]
            dist = round((dx*dx + dy*dy + dz*dz)**0.5, 2)
            if dist > 5.0:
                print(f"  [CORRECTED] PDB {pdb_id:5s} | Shift: {dist:5.2f}Å | Old={old_center} -> New={new_center} ({method})")
                updated_count += 1

    print("\n--- Calibration Summary ---")
    print(f"Total targets processed: {len(targets)}")
    print(f"Targets corrected with >5.0Å shift: {updated_count}")
    print("Method Distribution:")
    for m, cnt in method_counts.items():
        print(f"  {m}: {cnt}")

    # 1. Save updated curated_targets.json
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(targets, f, indent=2, ensure_ascii=False)
    print(f"\nSaved updated {JSON_PATH}")

    # 2. Save updated curated_targets.csv
    target_map = {t["pdb_id"].upper(): t for t in targets}
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            fieldnames = reader.fieldnames
            
        for r in rows:
            pdb_id = r.get("pdb_id", "").upper()
            if pdb_id in target_map:
                t = target_map[pdb_id]
                r["grid_center_x"] = t["grid_center_x"]
                r["grid_center_y"] = t["grid_center_y"]
                r["grid_center_z"] = t["grid_center_z"]
                
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved updated {CSV_PATH}")

    # 3. Update SQLite DB if present
    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        db_updates = 0
        for t in targets:
            pdb_id = t["pdb_id"].upper()
            gx, gy, gz = t["grid_center_x"], t["grid_center_y"], t["grid_center_z"]
            cursor.execute(
                "UPDATE targets SET grid_center_x=?, grid_center_y=?, grid_center_z=? WHERE UPPER(pdb_id)=?",
                (gx, gy, gz, pdb_id)
            )
            db_updates += cursor.rowcount
        conn.commit()
        conn.close()
        print(f"Updated {db_updates} target records in SQLite database ({DB_PATH})")

    # Specifically check 9QA0 and 9QA4
    qa0 = target_map.get("9QA0")
    qa4 = target_map.get("9QA4")
    print("\n--- Final Verification for 9QA0 and 9QA4 ---")
    if qa0:
        print(f"9QA0 Grid Center: ({qa0['grid_center_x']}, {qa0['grid_center_y']}, {qa0['grid_center_z']})")
    if qa4:
        print(f"9QA4 Grid Center: ({qa4['grid_center_x']}, {qa4['grid_center_y']}, {qa4['grid_center_z']})")

if __name__ == "__main__":
    main()
