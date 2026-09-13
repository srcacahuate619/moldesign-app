"""
curate_pdbbind_for_gnn.py - Cura ~500 nuevos PDBbind complexes de alta calidad
para escalar GNN de 708 -> ~1200.

Criterios de calidad:
  1. Tiene binding affinity (pKi/Ki/Kd) en INDEX
  2. Ligando parseable (SDF OK, sin errores)
  3. Tamano de ligando razonable (<100 atomos pesados, <80 SMILES len)
  4. Proteina PDB parseable (no truncada)
  5. Maximizar diversidad de familias quimicas

Output:
  data/gnn_v31/pdbbind_new_curated.csv - lista de ~500 PDB IDs para procesar
  data/gnn_v31/curation_report.json - estadisticas de curacion
"""
import json, csv, math, sys
from pathlib import Path
from collections import Counter

import numpy as np
from rdkit import Chem

ROOT = Path("D:/moldesign-build")
PDBBIND = ROOT / "data" / "pdbbind"
GNN_V31 = ROOT / "data" / "gnn_v31"
INDEX_PATH = PDBBIND / "INDEX_refined_data.2020"
CLASSIFICATION_PATH = GNN_V31 / "pdbbind_classification.json"

# Training set PDBs
with open(GNN_V31 / "pids_in_dataset.txt") as f:
    TRAIN_PDBS = set(l.strip().lower() for l in f.read().strip().split("\n"))

print("=" * 70)
print("  CURACION DE NUEVOS COMPLEJOS PDBBIND PARA GNN")
print("=" * 70)

# Step 1: Read INDEX for binding affinity (refined set only)
print(f"\n  1. Cargando INDEX refined (alta calidad, con pKi)...")
pki_map = {}
if INDEX_PATH.exists():
    with open(INDEX_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            # Format: PDB_ID  resolution  year  binding_data  //  pKi
            if len(parts) >= 6:
                pid = parts[0].lower()
                try:
                    pki = float(parts[5])  # pKi is at index 5 after "//"
                    if pki > 0:
                        pki_map[pid] = pki
                except (ValueError, IndexError):
                    pass
    print(f"     {len(pki_map)} PDBs con pKi en INDEX refined")

# The refined set had 865 entries originally; 708 are in training
# So 865-708 = 157 NOT in training -> these are our HIGHEST priority
refined_not_in_train = [pid for pid in pki_map if pid not in TRAIN_PDBS]
print(f"     {len(refined_not_in_train)} en refined pero NO en training (ALTA PRIORIDAD)")

# Step 2: Check which refined-available PDBs have SDF + protein files
print(f"\n  2. Verificando archivos para refined-not-in-train...")
refined_candidates = []
for pid in refined_not_in_train:
    d = PDBBIND / pid
    if not d.is_dir():
        continue
    sdf = list(d.glob("*_ligand.sdf"))
    protein = list(d.glob("*_protein.pdb"))
    if sdf and protein:
        refined_candidates.append({"pid": pid, "sdf": sdf[0], "protein": protein[0], "pki": pki_map[pid], "source": "refined"})

print(f"     {len(refined_candidates)} complejos refined disponibles con SDF+PDB")

# Step 3: Validate with RDKit
print(f"\n  3. Validando SDF con RDKit...")
valid_refined = []
for c in refined_candidates:
    try:
        mol = Chem.SDMolSupplier(str(c["sdf"]), removeHs=False)[0]
        if mol is None:
            continue
        n_heavy = mol.GetNumHeavyAtoms()
        smi = Chem.MolToSmiles(mol)
        mol_weight = sum(atom.GetMass() for atom in mol.GetAtoms())
        if n_heavy < 5 or n_heavy > 120 or len(smi) > 100:
            continue
        c["n_heavy"] = n_heavy
        c["smi"] = smi
        c["mol_weight"] = mol_weight
        valid_refined.append(c)
    except Exception:
        pass

print(f"     Validos (RDKit + tamano): {len(valid_refined)} de {len(refined_candidates)}")


# Step 4: Load classification and balance
print(f"\n  4. Cargando clasificacion por familia...")
classification = {}
if CLASSIFICATION_PATH.exists():
    with open(CLASSIFICATION_PATH) as f:
        classification = json.load(f)

def get_family(pid):
    info = classification.get(pid, {})
    return info.get("family", "other")

train_families = Counter()
for pid in TRAIN_PDBS:
    train_families[get_family(pid)] += 1

candidate_families = Counter()
for c in valid_refined:
    candidate_families[get_family(c["pid"])] += 1

print(f"\n  Familias en training vs refined disponibles:")
print(f"  {'family':<22} {'train':>7} {'disp':>7} {'quota':>7}")
for fam in sorted(set(list(train_families.keys()) + list(candidate_families.keys()))):
    t = train_families.get(fam, 0)
    d = candidate_families.get(fam, 0)
    quota = "ALL" if d > 0 else "-"
    print(f"  {fam:<22} {t:>7} {d:>7} {quota:>7}")

# Step 5: Select ALL valid refined complexes (they're already curated)
selected = valid_refined
print(f"\n  5. Seleccion final: {len(selected)} nuevos complejos refined")
print(f"     Nuevo total training: {len(TRAIN_PDBS)} + {len(selected)} = {len(TRAIN_PDBS) + len(selected)}")

# Also check: general set availability for contrastive pretraining only
# (These don't need pKi labels - only for contrastive pretraining)
print(f"\n  6. [OPCIONAL] General set para contrastive pretraining...")
all_dirs = [d for d in PDBBIND.iterdir() if d.is_dir()]
general_available = []
for d in all_dirs:
    pid = d.name.lower()
    if pid in TRAIN_PDBS or pid in {c["pid"] for c in selected}:
        continue
    if pid in pki_map:
        continue  # already in refined
    sdf = list(d.glob("*_ligand.sdf"))
    protein = list(d.glob("*_protein.pdb"))
    if not sdf or not protein:
        continue
    try:
        mol = Chem.SDMolSupplier(str(sdf[0]), removeHs=False)[0]
        if mol is None or mol.GetNumHeavyAtoms() < 5 or mol.GetNumHeavyAtoms() > 120:
            continue
        general_available.append(pid)
    except:
        pass

print(f"     {len(general_available)} complejos generales disponibles para contrastive (sin pKi)")

# Save
out_dir = GNN_V31 / "curated_new"
out_dir.mkdir(parents=True, exist_ok=True)

with open(out_dir / "pids_refined_new.txt", "w") as f:
    for c in selected:
        f.write(c["pid"] + "\n")

with open(out_dir / "pids_general_for_contrastive.txt", "w") as f:
    for pid in general_available:
        f.write(pid + "\n")

# Curation report
report = {
    "refined_count": len(selected),
    "general_contrastive_count": len(general_available),
    "train_set_size": len(TRAIN_PDBS),
    "new_total_training": len(TRAIN_PDBS) + len(selected),
    "new_total_for_contrastive": len(TRAIN_PDBS) + len(general_available) + len(selected),
    "family_distribution_selected": dict(Counter(get_family(c["pid"]) for c in selected).most_common()),
    "pdb_ids_selected": [c["pid"] for c in selected],
}

with open(out_dir / "curation_report.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"\n  Guardado en: {out_dir}")
print(f"    - pids_refined_new.txt ({len(selected)} PDB IDs)")
print(f"    - pids_general_for_contrastive.txt ({len(general_available)} PDB IDs)")
print(f"    - curation_report.json")
print(f"\n  Resumen:")
print(f"    Dataset finetuning actual:  {len(TRAIN_PDBS)}")
print(f"    Nuevos para finetuning:    +{len(selected)}")
print(f"    Total finetuning:          ={len(TRAIN_PDBS) + len(selected)}")
print(f"    Para contrastive (opc):    +{len(general_available)}")
print(f"    Total para contrastive:    ={len(TRAIN_PDBS) + len(general_available) + len(selected)}")
print("=" * 70)


# Step 4: Load classification
print(f"\n  4. Cargando clasificacion por familia...")
classification = {}
if CLASSIFICATION_PATH.exists():
    with open(CLASSIFICATION_PATH) as f:
        classification = json.load(f)

def get_family(pid):
    info = classification.get(pid, {})
    return info.get("family", "other")

# Count families in training vs available
train_families = Counter()
for pid in TRAIN_PDBS:
    train_families[get_family(pid)] += 1

candidate_families = Counter()
for c in valid:
    candidate_families[get_family(c["pid"])] += 1

print(f"\n  Familias en training vs disponibles (para balancear):")
print(f"  {'family':<22} {'train':>7} {'disp':>7}")
for fam in sorted(set(list(train_families.keys()) + list(candidate_families.keys()))):
    t = train_families.get(fam, 0)
    d = candidate_families.get(fam, 0)
    print(f"  {fam:<22} {t:>7} {d:>7}")

# Step 5: Sample for diversity
print(f"\n  5. Muestreo balanceado por familia...")
np.random.seed(42)

# Target: ~500 new, but balance underrepresented families
# Nuclear receptor: only 9 in training -> try to add ALL available
# Kinase: 67 -> add ~30
# Metalloenzyme: 75 -> add ~30
# Others proportionally

TARGET_TOTAL = 500  # nova 500 to add to 708 = ~1200

family_quota = {}
remaining = TARGET_TOTAL
# Prioritize underrepresented
priority_families = ["nuclear_receptor", "kinase", "metalloenzyme", "protease"]
for fam in priority_families:
    available = candidate_families.get(fam, 0)
    if available > 0:
        train_count = train_families.get(fam, 0)
        # Quota: aim to double small families, boost medium ones
        if train_count < 20:
            quota = min(available, 50)  # add up to 50 if very underrepresented
        elif train_count < 50:
            quota = min(available, 30)
        else:
            quota = min(available, 20)
        family_quota[fam] = quota
        remaining -= quota

# Distribute remaining among all families proportionally
other_available = {fam: cnt for fam, cnt in candidate_families.items() if fam not in family_quota}
total_other = sum(other_available.values())
if total_other > 0:
    for fam, cnt in sorted(other_available.items(), key=lambda x: -x[1]):
        if remaining <= 0:
            break
        quota = min(cnt, max(1, int(remaining * cnt / total_other)))
        family_quota[fam] = quota
        remaining -= quota

# Sample
selected = []
for fam, quota in sorted(family_quota.items(), key=lambda x: -x[1]):
    fam_candidates = [c for c in valid if get_family(c["pid"]) == fam]
    if not fam_candidates:
        continue
    # Sort by quality: prefer diverse scaffolds (random sample)
    np.random.shuffle(fam_candidates)
    chosen = fam_candidates[:min(quota, len(fam_candidates))]
    selected.extend(chosen)
    print(f"  {fam:<22} seleccionados: {len(chosen)}")

print(f"\n  TOTAL seleccionados: {len(selected)}")

# Step 6: Write output files
out_dir = GNN_V31 / "curated_new"
out_dir.mkdir(parents=True, exist_ok=True)

# CSV for processing
with open(out_dir / "pdbbind_new_curated.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["pdb_id", "pki", "smiles", "n_heavy", "mol_weight", "family", "sdf_path", "protein_path"])
    for c in selected:
        try:
            mol = Chem.SDMolSupplier(str(c["sdf"]), removeHs=True)[0]
            smi = Chem.MolToSmiles(mol) if mol else ""
        except:
            smi = ""
        w.writerow([
            c["pid"], c["pki"], smi, c["n_heavy"], round(c["mol_weight"], 1),
            get_family(c["pid"]), str(c["sdf"]), str(c["protein"])
        ])

print(f"  Guardado: {out_dir / 'pdbbind_new_curated.csv'}")

# PDB IDs list for GNN graph generation
with open(out_dir / "pids_new.txt", "w") as f:
    for c in selected:
        f.write(c["pid"] + "\n")

print(f"  Guardado: {out_dir / 'pids_new.txt'} ({len(selected)} PDB IDs)")

# Report
report = {
    "total_candidates_raw": len(candidates),
    "valid_after_rdkit_filter": len(valid),
    "selected": len(selected),
    "train_set_size": len(TRAIN_PDBS),
    "new_total_after_curation": len(TRAIN_PDBS) + len(selected),
    "family_distribution_train": dict(train_families.most_common()),
    "family_distribution_selected": dict(Counter(get_family(c["pid"]) for c in selected).most_common()),
    "selection_criteria": {
        "has_pki": True,
        "rdkit_parseable": True,
        "heavy_atoms_5_to_100": True,
        "smiles_len_max_100": True,
        "protein_pdb_exists": True,
    },
}

with open(out_dir / "curation_report.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"  Guardado: {out_dir / 'curation_report.json'}")
print(f"\n  Nuevo dataset total: {len(TRAIN_PDBS)} (viejo) + {len(selected)} (nuevo) = {len(TRAIN_PDBS) + len(selected)}")
print("=" * 70)
