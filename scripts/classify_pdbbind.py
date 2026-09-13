"""
classify_pdbbind.py v2 - Clasifica 708 PDBs de entrenamiento por familia.
Usa struct_keywords.pdbx_keywords + struct.title + polymer_entity.rcsb_polymer_entity.pdbx_ec
"""
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDB_FILE = PROJECT_ROOT / "data" / "gnn_v31" / "pids_in_dataset.txt"
CLASSIFICATION_OUT = PROJECT_ROOT / "data" / "gnn_v31" / "pdbbind_classification.json"
COUNTS_OUT = PROJECT_ROOT / "data" / "gnn_v31" / "pdbbind_family_counts.json"
OVERLAP_OUT = PROJECT_ROOT / "data" / "gnn_v31" / "test_target_family_overlap.json"

TEST_PDB_FAMILY = {
    "7E2Y": "gpcr",
    "1HSG": "protease",
    "3PP0": "kinase",
    "3ERT": "nuclear_receptor",
    "3CYX": "protease",
    "1C4U": "protease",
    "3DC3": "metalloenzyme",
}


def classify_from_keywords(pdbx_keywords, struct_title):
    """Clasifica un PDB basado en el campo pdbx_keywords y el title."""
    text = ((pdbx_keywords or "") + " " + (struct_title or "")).upper()
    
    # Check each family in order of precedence
    if "KINASE" in text or "TRANSFERASE" in text and "SERINE" in text and "THREONINE" in text:
        return "kinase"
    if "PROTEASE" in text or "PROTEINASE" in text or "PEPTIDASE" in text:
        return "protease"
    if "KINASE" in text or "PHOSPHOTRANSFERASE" in text:
        return "kinase"
    if "GPCR" in text or "G PROTEIN" in text or "RHODOPSIN" in text or "7TM" in text:
        return "gpcr"
    if "NUCLEAR RECEPTOR" in text or "ESTROGEN" in text or "RETINOIC ACID" in text or "THYROID HORMONE" in text:
        return "nuclear_receptor"
    if "CARBONIC ANHYDRASE" in text or "METALLOPROTEINASE" in text or "METALLOENZYME" in text:
        return "metalloenzyme"
    if "PHOSPHODIESTERASE" in text:
        return "phosphodiesterase"
    if "IMMUNOGLOBULIN" in text or "ANTIBODY" in text or "FAB" in text:
        return "antibody"
    if "ION CHANNEL" in text or "VOLTAGE-GATED" in text:
        return "ion_channel"
    if "TRANSPORTER" in text or "ABC TRANSPORTER" in text:
        return "transporter"
    if "HISTONE" in text or "DEACETYLASE" in text or "BROMODOMAIN" in text:
        return "epigenetics"
    if "INTERLEUKIN" in text or "CYTOKINE" in text or "CHEMOKINE" in text:
        return "immuno_oncology"
    
    # EC-number based classification
    if "EC 1." in text:
        return "oxidoreductase"
    if "EC 2." in text:
        return "transferase"
    if "EC 3." in text:
        return "hydrolase"
    if "EC 4." in text:
        return "lyase"
    if "EC 5." in text:
        return "isomerase"
    if "EC 6." in text:
        return "ligase"
    
    # Broader matches
    if "HYDROLASE" in text or "PROTEINASE" in text:
        return "hydrolase"
    if "TRANSFERASE" in text or "METHYLTRANSFERASE" in text or "ACETYLTRANSFERASE" in text:
        return "transferase"  
    if "OXIDOREDUCTASE" in text or "DEHYDROGENASE" in text or "REDUCTASE" in text or "OXIDASE" in text:
        return "oxidoreductase"
    if "LYASE" in text or "SYNTHASE" in text:
        return "lyase"
    if "ISOMERASE" in text or "MUTASE" in text or "EPIMERASE" in text:
        return "isomerase"
    if "LIGASE" in text or "SYNTHETASE" in text:
        return "ligase"
    if "COMPLEX" in text and ("PEPTIDE" in text or "PROTEIN" in text):
        return "other"
    
    return "other"


def classify_one(pdb_id):
    """Clasifica un solo PDB."""
    url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return pdb_id, "unclassified", {"error": f"HTTP {r.status_code}"}
        
        data = r.json()
        pdbx_keywords = data.get("struct_keywords", {}).get("pdbx_keywords", "")
        struct_title = data.get("struct", {}).get("title", "")
        
        # Get polymer entity info for EC number
        ec_numbers = []
        polymer_entity_ids = data.get("rcsb_entry_container_identifiers", {}).get("polymer_entity_ids", ["1"])
        
        for eid in polymer_entity_ids[:1]:  # just first entity
            pe_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{eid}"
            try:
                r2 = requests.get(pe_url, timeout=10)
                if r2.status_code == 200:
                    pe_data = r2.json()
                    pem = pe_data.get("rcsb_polymer_entity", {})
                    ec = pem.get("pdbx_ec", "")
                    if ec:
                        ec_numbers.append(ec)
                    # Uniprot
                    container = pe_data.get("rcsb_polymer_entity_container_identifiers", {})
                    uniprot = container.get("uniprot_ids", [])
            except:
                pass
        
        ec_text = " ".join(ec_numbers)
        full_text = f"{pdbx_keywords} {struct_title} {ec_text}"
        
        family = classify_from_keywords(pdbx_keywords, struct_title)
        
        return pdb_id, family, {
            "name": struct_title[:100] if struct_title else "",
            "pdbx_keywords": pdbx_keywords,
            "ec": ec_text,
        }
    except Exception as e:
        return pdb_id, "unclassified", {"error": str(e)[:150]}


def main():
    pdb_ids = [l.strip() for l in open(PDB_FILE).read().strip().split("\n") if l.strip()]
    print(f"  Total PDBs to classify: {len(pdb_ids)}")
    
    classification = {}
    count = 0
    start = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futs = {executor.submit(classify_one, p.upper()): p for p in pdb_ids}
        for future in as_completed(futs):
            pdb = futs[future]
            try:
                pid, family, info = future.result()
                classification[pdb] = dict(info)
                classification[pdb]["family"] = family
            except Exception as e:
                classification[pdb] = {"family": "unclassified", "error": str(e)[:100]}
            
            count += 1
            if count % 100 == 0:
                print(f"  Progress: {count}/{len(pdb_ids)} [{time.time()-start:.0f}s]")
    
    elapsed = time.time() - start
    print(f"  Done: {count} classified in {elapsed:.0f}s")
    
    # Counts
    family_counts = Counter()
    for info in classification.values():
        family_counts[info.get("family", "unclassified")] += 1
    
    # Test target overlap
    test_overlap = {}
    for test_pdb, test_family in TEST_PDB_FAMILY.items():
        same_family = sum(1 for info in classification.values() if info.get("family") == test_family)
        total_classified = sum(1 for info in classification.values() if info.get("family") != "unclassified")
        test_overlap[test_pdb] = {
            "family": test_family,
            "n_train_same_family": same_family,
            "pct": round(100.0 * same_family / max(1, total_classified), 1),
        }
    
    # Save
    PROJECT_ROOT.joinpath("data/gnn_v31").mkdir(parents=True, exist_ok=True)
    
    clean = {}
    for pdb, info in classification.items():
        clean[pdb] = {k: (str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v) for k, v in info.items()}
    
    with open(CLASSIFICATION_OUT, "w") as f:
        json.dump(clean, f)
    print(f"  Saved: {CLASSIFICATION_OUT}")
    
    with open(COUNTS_OUT, "w") as f:
        json.dump({
            "family_counts": dict(family_counts.most_common()),
            "total": sum(family_counts.values()),
            "total_classified": sum(1 for v in classification.values() if v.get("family") != "unclassified"),
        }, f, indent=2)
    print(f"  Saved: {COUNTS_OUT}")
    
    with open(OVERLAP_OUT, "w") as f:
        json.dump(test_overlap, f, indent=2)
    print(f"  Saved: {OVERLAP_OUT}")
    
    # Print
    print(f"\n  FAMILY COUNTS (top 15):")
    for family, cnt in family_counts.most_common(15):
        print(f"    {family:<22}{cnt:>5}")
    
    print(f"\n  TEST TARGET OVERLAP:")
    for tpdb, info in test_overlap.items():
        print(f"    {tpdb:<8} {info['family']:<20} train_same={info['n_train_same_family']:<4} ({info['pct']:.1f}%)")
    
    print(f"\n  Total time: {elapsed:.0f}s")
    print(f"  Unclassified: {family_counts.get('unclassified', 0)}/{sum(family_counts.values())}")


if __name__ == "__main__":
    main()
