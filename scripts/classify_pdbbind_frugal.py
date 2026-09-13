"""
classify_pdbbind_frugal.py - Clasifica PDBbind por familia en modo frugal.

Usa 3 estrategias en orden:
  1. Si el PDB ya esta en target_library -> usar clasificacion del manifest
  2. RCSB API (REST) ThreadPool con 5 workers, max 10s request timeout
  3. Fallback: marcar como 'unclassified'

La meta es clasificar los 708 PDBs de entrenamiento para saber cuantos
kinase/enzyme/etc hay vs gpcr/protease.
"""
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDB_FILE = PROJECT_ROOT / "data" / "gnn_v31" / "pids_in_dataset.txt"
CLASSIFICATION_OUT = PROJECT_ROOT / "data" / "gnn_v31" / "pdbbind_classification.json"
COUNTS_OUT = PROJECT_ROOT / "data" / "gnn_v31" / "pdbbind_family_counts.json"
OVERLAP_OUT = PROJECT_ROOT / "data" / "gnn_v31" / "test_target_family_overlap.json"

# Mapa de PDB IDs conocidos -> familia (fuente target_library manifest)
KNOWN_PDBS = {
    # GPCR
    "4IAQ": "gpcr", "4IAR": "gpcr", "6Y5A": "gpcr",
    # Kinase
    "1IS0": "kinase", "2H02": "kinase", "2I3U": "kinase", "2I4G": "kinase", "2I4H": "kinase",
    # Protease
    "1FH0": "protease", "1ITO": "protease", "1M6D": "protease",
    "3F75": "protease", "4I04": "protease", "5FPW": "protease", "5TUN": "protease",
    # Nuclear receptor
    "1CBR": "nuclear_receptor", "1CBS": "nuclear_receptor", "1EPB": "nuclear_receptor",
    "1FEM": "nuclear_receptor", "1GX9": "nuclear_receptor", "2FR3": "nuclear_receptor",
    "2LBD": "nuclear_receptor", "2VE3": "nuclear_receptor", "3LBD": "nuclear_receptor",
    "6EU9": "nuclear_receptor",
    # Ion channel
    "3RVY": "ion_channel", "3RVZ": "ion_channel", "3RW0": "ion_channel",
    "4MS2": "ion_channel", "5VB8": "ion_channel", "5YUA": "ion_channel",
    # Phosphodiesterase
    "1RKP": "phosphodiesterase", "3V94": "phosphodiesterase", "4JV6": "phosphodiesterase",
    # Epigenetics
    "1C3P": "epigenetics", "1C3R": "epigenetics", "1C3S": "epigenetics",
    "1T69": "epigenetics", "1VKG": "epigenetics", "1W22": "epigenetics",
    # Immuno-oncology
    "1SM3": "immuno_oncology", "2OA8": "immuno_oncology", "3MXJ": "immuno_oncology",
    # Transporters
    "8HFE": "transporter", "8HFF": "transporter", "8HFG": "transporter",
    # Metabolism
    "3FLI": "metabolism", "3L1B": "metabolism", "3P88": "metabolism",
}

TEST_TARGET_MAP = {
    "7E2Y": "gpcr",
    "1HSG": "protease",
    "3PP0": "kinase",
    "3ERT": "nuclear_receptor",
    "3CYX": "protease",
    "1C4U": "protease",
    "3DC3": "metalloenzyme",
}

EC_PATTERNS = {
    "gpcr": [],  # detectado por keywords proteina / nombre
    "kinase": ["ec 2.7."],
    "protease": ["ec 3.4."],
    "nuclear_receptor": [],  # keyword
    "metalloenzyme": [],  # detectado por keyword
    "phosphodiesterase": ["ec 3.1.4."],
    "oxidoreductase": ["ec 1."],
    "transferase": ["ec 2."],
    "hydrolase": ["ec 3."],
    "lyase": ["ec 4."],
    "isomerase": ["ec 5."],
    "ligase": ["ec 6."],
    "transporter": [],
    "ion_channel": [],
    "antibody": [],
    "epigenetics": [],
    "immuno_oncology": [],
    "metabolism": [],
}

FAMILY_KEYWORDS = {
    "gpcr": ["g-protein coupled receptor", "gpcr", "seven-transmembrane", "7tm", "olfactory receptor", "rhodopsin"],
    "kinase": ["kinase", "phosphotransferase", "ec 2.7.", "serine/threonine", "tyrosine kinase", "cyclin-dependent"],
    "protease": ["protease", "peptidase", "proteinase", "ec 3.4.", "hydrolase, acting on peptide bonds", "hiv protease", "thrombin", "factor x"],
    "nuclear_receptor": ["nuclear receptor", "estrogen receptor", "androgen receptor", "retinoic acid", "thyroid hormone", "peroxisome", "retinoid x", "ec 4.13"],
    "metalloenzyme": ["metalloenzyme", "carbonic anhydrase", "matrix metalloprotease", "metallo", "zinc", "ec 4.2.1", "ec 3.1.26", "ec 3.1.27"],
    "phosphodiesterase": ["phosphodiesterase", "pde", "ec 3.1.4."],
    "oxidoreductase": ["ec 1.", "oxidoreductase", "dehydrogenase", "reductase", "oxidase", "cytochrome p450"],
    "transferase": ["ec 2.", "transferase", "methyltransferase", "acetyltransferase"],
    "hydrolase": ["ec 3.", "hydrolase"],
    "lyase": ["ec 4.", "lyase", "decarboxylase", "synthase (decarboxylating)"],
    "isomerase": ["ec 5.", "isomerase", "mutase", "epimerase"],
    "ligase": ["ec 6.", "ligase", "synthetase"],
    "transporter": ["transporter", "pump", "abc transporter", "major facilitator"],
    "ion_channel": ["ion channel", "voltage-gated", "ligand-gated ion channel", "acetylcholine receptor", "gaba receptor"],
    "antibody": ["antibody", "immunoglobulin", "fab", "scfv", "monoclonal"],
    "epigenetics": ["histone", "deacetylase", "hdac", "bromodomain", "methyltransferase", "dna methyl"],
    "immuno_oncology": ["interleukin", "cytokine", "interferon", "chemokine", "cell receptor", "pd-1", "pd-l1", "ctla-4"],
}

FAMILY_PRECEDENCE = [
    "gpcr", "kinase", "protease", "nuclear_receptor", "metalloenzyme",
    "phosphodiesterase", "epigenetics", "immuno_oncology", "transporter",
    "ion_channel", "oxidoreductase", "transferase", "hydrolase", "lyase",
    "isomerase", "ligase", "antibody", "metabolism", "other"
]

# Target list for the 7 test PDBs - known classes
TEST_PDB_FAMILY = {
    "7E2Y": "gpcr",
    "1HSG": "protease",
    "3PP0": "kinase",
    "3ERT": "nuclear_receptor",
    "3CYX": "protease",
    "1C4U": "protease",
    "3DC3": "metalloenzyme",
}


def classify_by_keywords(name, ec_number, go_terms, lineage):
    """Clasifica una proteina por keywords en el nombre, EC, GO terms, lineage."""
    text = " ".join([
        (name or "").lower(),
        (ec_number or "").lower(),
        " ".join((go_terms or [])).lower(),
        " ".join(lineage or []).lower(),
    ])
    for family, keywords in FAMILY_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                return family
    return "other"


def classify_one(pdb_id):
    """Clasifica un solo PDB por API RCSB."""
    url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return pdb_id, "unclassified", {}
        data = r.json()
        
        # Extrer informacion del polymer entity
        polymers = []
        for entity in data.get("rcsb_entry_info", {}).get("polymer_entity_count", 0):
            pass
        
        struct_title = data.get("struct", {}).get("title", "")
        
        # Buscar en polymer entities
        ec_numbers = []
        uniprot_ids = []
        protein_names = []
        go_terms = []
        lineage = []
        
        entities = data.get("polymer_entities", [])
        if not entities:
            entities = data.get("rcsb_polymer_entity_container_identifiers", [])
            if not isinstance(entities, list):
                entities = [entities] if entities else []
        
        if not entities:
            return pdb_id, "other", {"name": struct_title, "ec": "", "source": "title_only"}
        
        for ent in entities:
            # EC number
            ec = ent.get("rcsb_entity_source_organism", [{}])[0] if isinstance(ent.get("rcsb_entity_source_organism"), list) else {}
            ec_nums = ent.get("rcsb_entry_info", {})
            
            # Uniprot annotation
            uniprot_annot = ent.get("rcsb_uniprot_annotation", [])
            for ua in uniprot_annot if isinstance(uniprot_annot, list) else []:
                prot_name = ua.get("name", "")
                if prot_name:
                    protein_names.append(prot_name.lower())
                ec_val = ua.get("ec", "")
                if ec_val:
                    ec_numbers.append(ec_val)
                lineage_tags = ua.get("lineage", [])
                for l in lineage_tags if isinstance(lineage_tags, list) else []:
                    lname = l.get("name", "") if isinstance(l, dict) else str(l)
                    if lname:
                        lineage.append(lname.lower())
            
            # Named lineage - this often has GO terms
            for ua in uniprot_annot if isinstance(uniprot_annot, list) else []:
                keywords = ua.get("keywords", [])
                for kw in keywords if isinstance(keywords, list) else []:
                    if isinstance(kw, dict):
                        go_terms.append(kw.get("name", "").lower())
                    else:
                        go_terms.append(str(kw).lower())
        
        # Si no hay datos via API, probar con annotation del struct title
        name = " ".join(protein_names) or struct_title
        ec_str = ec_numbers[0] if ec_numbers else ""
        
        family = classify_by_keywords(name, ec_str, go_terms, lineage)
        
        return pdb_id, family, {
            "name": struct_title or name or "",
            "ec": ec_str,
            "uniprot": uniprot_ids[0] if uniprot_ids else "",
            "go": go_terms[:5] if go_terms else [],
            "lineage": lineage[:5] if lineage else [],
        }
    except Exception as e:
        return pdb_id, "unclassified", {"error": str(e)[:100]}


def main():
    # Leer lista de PDBs
    pdb_ids = [l.strip() for l in open(PDB_FILE).read().strip().split("\n") if l.strip()]
    print(f"  Total PDBs a clasificar: {len(pdb_ids)}")
    
    # Primero buscar PDBs ya conocidos
    pdb_ids_upper = [p.upper() for p in pdb_ids]
    classification = {}
    
    for p in pdb_ids:
        pu = p.upper()
        if pu in KNOWN_PDBS:
            classification[p] = {
                "family": KNOWN_PDBS[pu],
                "name": "",
                "ec": "",
                "uniprot": "",
                "source": "target_library",
            }
    
    pending = [p for p in pdb_ids if p not in classification]
    print(f"  Conocidos previamente: {len(classification)}")
    print(f"  Pendientes de clasificar via API: {len(pending)}")
    
    if not pending:
        print("  Todos clasificados sin API! (imposible con 708 PDBs)")
    
    # Clasificar pendientes via API con ThreadPoolExecutor (5 workers)
    classified_count = 0
    error_count = 0
    start_time = time.time()
    batch_size = 100
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_pdb = {
            executor.submit(classify_one, p.upper()): p
            for p in pending
        }
        for future in as_completed(future_to_pdb):
            pdb = future_to_pdb[future]
            try:
                pdb_id, family, info = future.result()
                classification[pdb] = dict(info)
                classification[pdb]["family"] = family
                classification[pdb]["source"] = "rcsb_api"
                classified_count += 1
            except Exception as e:
                classification[pdb] = {"family": "unclassified", "error": str(e)[:100], "source": "failed"}
                error_count += 1
            
            if (classified_count + error_count) % batch_size == 0:
                elapsed = time.time() - start_time
                print(f"  Progreso: {classified_count + error_count}/{len(pending)} "
                      f"(errors: {error_count}) [{elapsed:.0f}s]")
    
    elapsed_total = time.time() - start_time
    print(f"  API classification done: {classified_count} classified, {error_count} errors, {elapsed_total:.0f}s")
    
    # Agregar los test PDBs a la clasificacion
    for pdb, fam in TEST_PDB_FAMILY.items():
        classification[pdb.lower()] = {
            "family": fam, "name": f"test_target_{pdb}", "ec": "",
            "uniprot": "", "source": "manual_annotation",
        }
    
    # Family counts
    from collections import Counter
    family_counts = Counter()
    for pdb, info in classification.items():
        family_counts[info.get("family", "unclassified")] += 1
    
    # Overlap for test targets
    test_overlap = {}
    for test_pdb, test_family in TEST_PDB_FAMILY.items():
        same_family = sum(1 for info in classification.values() if info.get("family") == test_family)
        total_classified = sum(1 for info in classification.values() if info.get("family") != "unclassified")
        test_overlap[test_pdb] = {
            "family": test_family,
            "n_train_pdb_same_family": same_family,
            "pct": round(100.0 * same_family / max(1, total_classified), 1),
        }
    
    # Save
    PROJECT_ROOT.joinpath("data/gnn_v31").mkdir(parents=True, exist_ok=True)
    
    # Limpiar classification de objetos no serializables
    clean_class = {}
    for pdb, info in classification.items():
        clean_info = {}
        for k, v in info.items():
            if isinstance(v, dict):
                clean_info[k] = str(v)
            elif isinstance(v, list):
                clean_info[k] = [str(x) for x in v[:5]]
            elif isinstance(v, (str, int, float, bool)) or v is None:
                clean_info[k] = v
            else:
                clean_info[k] = str(v)
        clean_class[pdb] = clean_info
    
    with open(CLASSIFICATION_OUT, "w") as f:
        json.dump(clean_class, f, indent=2)
    print(f"  Saved: {CLASSIFICATION_OUT}")
    
    with open(COUNTS_OUT, "w") as f:
        json.dump({
            "family_counts": dict(family_counts.most_common()),
            "total": sum(family_counts.values()),
            "total_classified": sum(1 for info in classification.values() if info.get("family") != "unclassified"),
            "unclassified": family_counts.get("unclassified", 0),
        }, f, indent=2)
    print(f"  Saved: {COUNTS_OUT}")
    
    with open(OVERLAP_OUT, "w") as f:
        json.dump(test_overlap, f, indent=2)
    print(f"  Saved: {OVERLAP_OUT}")
    
    # Print summary
    print(f"\n  FAMILY COUNTS (top 15):")
    print(f"  {'family':<22}{'count':>8}")
    print(f"  " + "-" * 32)
    for family, count in family_counts.most_common(15):
        print(f"  {family:<22}{count:>8}")
    
    print(f"\n  TEST TARGET OVERLAP:")
    print(f"  {'test_pdb':<10}{'family':<20}{'n_train_same':>12}{'pct':>8}")
    print(f"  " + "-" * 56)
    for test_pdb, info in test_overlap.items():
        print(f"  {test_pdb:<10}{info['family']:<20}{info['n_train_same']:>12}{info['pct']:>7.1f}%")

    print(f"\n  Done in {elapsed_total:.0f}s")


if __name__ == "__main__":
    main()
