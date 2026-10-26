"""FEP-09: inventario y defectos independientes del código del producto.

No importa services/ ni chem/; no escribe estructuras en archivos versionados.
Las coordenadas de referencia son las del primer registro legible del SDF.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

PRODUCT = "f183e0af"
PLB_COMMIT = "fd88824f9114244f95a14b485e6d6c96c1de716d"
STANDARD = set("ALA ARG ASN ASP ASH CYS CYX GLN GLU GLH GLY HIS HID HIE HIP ILE LEU LYS LYN MET PHE PRO SER THR TRP TYR VAL".split())
WATER = {"HOH", "WAT", "TIP", "TIP3", "SOL"}
METALS = {"ZN", "MG", "CA", "MN", "FE", "CU", "CO", "NI", "K", "NA"}
COFACTORS = {"HEM", "HEC", "FAD", "FMN", "NAD", "NAP", "NADP", "ATP", "ADP", "SAM", "SAH", "SF4", "FES"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def rewrite_conect(line, mapping, removed=frozenset()):
    ids = [int(line[i:i+5]) for i in range(6, len(line.rstrip()), 5) if line[i:i+5].strip()]
    if not ids or ids[0] in removed:
        return ""
    ids = [i for i in ids if i not in removed]
    return "CONECT" + "".join(f"{mapping.get(i, i):5d}" for i in ids) + "\n" if len(ids) > 1 else ""


def atoms(data):
    out = []
    for i, line in enumerate(data.decode("utf-8").splitlines()):
        if line[:6].strip() not in {"ATOM", "HETATM"}:
            continue
        out.append({"line": i, "key": [line[21], line[22:26].strip(), line[26].strip(), line[17:20].strip()],
                    "name": line[12:16].strip(), "element": line[76:78].strip() or line[12:16].strip()[0],
                    "xyz": [float(line[s:s+8]) for s in (30, 38, 46)]})
    return out


def distance(a, points):
    return min(math.dist(a, p) for p in points)


def box_distance(a, center, size):
    return math.sqrt(sum(max(abs(v-c)-s/2, 0)**2 for v, c, s in zip(a, center, size)))


def read_target(plb, target):
    from rdkit import Chem
    p = plb / "data" / target
    pdb = (p / "01_protein/crd/protein.pdb").read_bytes()
    supplier = Chem.SDMolSupplier(str(p / "02_ligands/ligands.sdf"), removeHs=False)
    record, mol = next((i, m) for i, m in enumerate(supplier) if m is not None)
    heavy = Chem.RemoveHs(mol)
    points = [list(heavy.GetConformer().GetAtomPosition(i)) for i in range(heavy.GetNumAtoms())]
    return pdb, heavy, record, points


def describe(plb):
    from rdkit import Chem, rdBase, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize
    RDLogger.DisableLog("rdApp.*")
    actual = subprocess.check_output(["git", "-C", str(plb), "rev-parse", "HEAD"], text=True).strip()
    if actual != PLB_COMMIT:
        raise RuntimeError(f"PLB no coincide: {actual}")
    targets = sorted(p.name for p in (plb / "data").iterdir()
                     if (p / "01_protein/crd/protein.pdb").is_file() and (p / "02_ligands/ligands.sdf").is_file())
    systems, cases = [], []
    enumerator = rdMolStandardize.TautomerEnumerator()
    for target in targets:
        pdb, mol, record, points = read_target(plb, target)
        aa = atoms(pdb)
        residues = defaultdict(list)
        for a in aa:
            residues[tuple(a["key"])].append(a)
        center = [round(sum(p[i] for p in points)/len(points), 4) for i in range(3)]
        size = [20.0]*3
        by_chain = defaultdict(list)
        for key in residues:
            if key[3] in STANDARD:
                by_chain[key[0]].append(key)
        contributions = {c: sum(distance(a["xyz"], points) <= 6 for k in keys for a in residues[k] if a["element"] != "H")
                         for c, keys in by_chain.items()}
        chain = sorted(contributions, key=lambda c: (-contributions[c], c))[0]
        system = {"target": target, "record": record, "ligand": mol.GetProp("_Name") if mol.HasProp("_Name") else f"record{record}",
                  "smiles": Chem.MolToSmiles(mol), "pdb_path": str((plb / "data" / target / "01_protein/crd/protein.pdb").resolve()),
                  "sdf_path": str((plb / "data" / target / "02_ligands/ligands.sdf").resolve()),
                  "pdb_sha256": sha(pdb), "sdf_sha256": sha((plb / "data" / target / "02_ligands/ligands.sdf").read_bytes()),
                  "chain": chain, "chain_contributions_6A": contributions, "grid_center": center, "grid_size": size,
                  "hetero_residues": dict(Counter(k[3] for k in residues if k[3] not in STANDARD))}
        systems.append(system)

        def add(category, defect, smiles=None, arm="A", repeat=0):
            cases.append({"case_id": f"{target}__{category}__{repeat}", "target": target, "ligand": system["ligand"],
                          "arm": arm, "category": category, "repeat": repeat, "defect": defect,
                          "smiles": smiles or system["smiles"], "baseline_id": f"{target}__baseline__0"})

        for rep in range(3):
            add("baseline", {}, arm="B", repeat=rep)
        add("seriales_renumerados", {"operation": "renumber_serials"}, arm="B")
        near, far = [], []
        for c, keys in by_chain.items():
            for start in range(1, len(keys)-3):
                cut = keys[start:start+3]
                flanks = [keys[start-1], keys[start+3]]
                if not all(any(a["name"] == n for a in residues[k]) for k, n in zip(flanks, ["C", "N"])):
                    continue
                left = next(a for a in residues[flanks[0]] if a["name"] == "C")
                right = next(a for a in residues[flanks[1]] if a["name"] == "N")
                # Un único corte: no se atraviesan discontinuidades ya presentes.
                seq = keys[start-1:start+4]
                if not all(any(a["name"] == "C" for a in residues[x]) and any(a["name"] == "N" for a in residues[y])
                           and math.dist(next(a["xyz"] for a in residues[x] if a["name"] == "C"),
                                         next(a["xyz"] for a in residues[y] if a["name"] == "N")) <= 2.0
                           for x, y in zip(seq, seq[1:])):
                    continue
                if math.dist(left["xyz"], right["xyz"]) <= 2.0:
                    continue
                d = min(distance(a["xyz"], points) for k in cut for a in residues[k] if a["element"] != "H")
                flank_d = min(distance(a["xyz"], points) for a in (left, right))
                b = min(box_distance(a["xyz"], center, size) for k in cut+flanks for a in residues[k])
                spec = {"operation": "remove_residues", "residues": [list(k) for k in cut],
                        "distance_to_reference_A": round(d, 4), "flank_distance_A": round(flank_d, 4),
                        "distance_to_box_A": round(b, 4), "c_n_after_cut_A": round(math.dist(left["xyz"], right["xyz"]), 4)}
                if c == chain and d <= 6 and flank_d <= 6:
                    near.append((d, start, spec))
                if c == chain and b > 15:
                    far.append((-b, start, spec))
        if near:
            add("hueco_en_el_sitio", min(near, key=lambda v: v[:2])[2])
        if far:
            add("hueco_lejano", min(far, key=lambda v: v[:2])[2], arm="B")
        sitechains = sorted(c for c, n in contributions.items() if n)
        if len(sitechains) > 1:
            remove = next(c for c in sitechains if c != chain)
            add("cadena_del_sitio_ausente", {"operation": "remove_chain", "chain": remove,
                                            "atoms_within_6A": contributions[remove]})
        species, waters, proton = [], [], []
        protein_polar = [a["xyz"] for a in aa if a["key"][3] in STANDARD and a["element"] in {"N", "O"}]
        ligand_polar = [points[i] for i, a in enumerate(mol.GetAtoms()) if a.GetSymbol() in {"N", "O"}]
        for key, rows in residues.items():
            heavy = [a for a in rows if a["element"] != "H"]
            d = min(distance(a["xyz"], points) for a in heavy)
            if key[3] in METALS | COFACTORS and d <= 6:
                species.append((d, key, {"operation": "remove_residues", "residues": [list(key)], "distance_to_reference_A": round(d, 4)}))
            if key[3] in WATER and ligand_polar:
                oxy = next((a for a in rows if a["element"] == "O"), None)
                if oxy:
                    dl, dp = distance(oxy["xyz"], ligand_polar), distance(oxy["xyz"], protein_polar)
                    if 1.8 < dl <= 3.5 and dp <= 3.5:
                        waters.append((dl, key, {"operation": "remove_residues", "residues": [list(key)],
                                                "distance_to_reference_A": round(dl, 4), "distance_to_protein_polar_A": round(dp, 4)}))
            if key[0] == chain and key[3] in {"HIS", "HID", "HIE", "ASP", "GLU"}:
                names = {a["name"]: a for a in rows}
                if key[3].startswith("HI") and {"ND1", "NE2"} <= names.keys():
                    hp = next((a for a in rows if a["name"] in {"HD1", "HE2"}), None)
                    nd = min(distance(names[n]["xyz"], points) for n in ("ND1", "NE2"))
                    if hp and nd <= 3.5 and not all(n in names for n in ("HD1", "HE2")):
                        proton.append((nd, key, {"operation": "flip_histidine", "residue": list(key), "hydrogen": hp["name"],
                                                "distance_to_reference_A": round(nd, 4)}))
                elif key[3] in {"ASP", "GLU"}:
                    ox = "OD2" if key[3] == "ASP" else "OE2"
                    if ox in names and distance(names[ox]["xyz"], points) <= 3.5:
                        proton.append((distance(names[ox]["xyz"], points), key,
                                       {"operation": "protonate_acid", "residue": list(key), "oxygen": ox,
                                        "distance_to_reference_A": round(distance(names[ox]["xyz"], points), 4)}))
        for category, found in (("metal_o_cofactor_retirado", species), ("agua_puente_retirada", waters), ("protonacion_del_sitio", proton)):
            if found:
                add(category, min(found, key=lambda v: (v[0], v[1]))[2])
        # RDKit enumera, pero una puntuación menor NO mide la población de equilibrio.
        # Este brazo se llama tautómero alternativo proxy y se publica fuera del gate de minoría.
        candidates = [(enumerator.ScoreTautomer(t), Chem.MolToSmiles(t)) for t in enumerator.Enumerate(mol)]
        distinct = sorted((s, sm) for s, sm in candidates if sm != system["smiles"])
        if distinct:
            score, sm = distinct[0]
            add("tautomero_alternativo_proxy", {"operation": "replace_smiles", "rdkit_score": score,
                                               "source": "RDKit TautomerEnumerator; no demuestra minoría"}, sm)
        stereo = [(i, tag) for i, tag in Chem.FindMolChiralCenters(mol, includeUnassigned=True) if tag != "?"]
        if stereo:
            i = stereo[0][0]
            variant = Chem.Mol(mol)
            variant.GetAtomWithIdx(i).SetChiralTag(Chem.ChiralType.CHI_UNSPECIFIED)
            add("estereo_sin_asignar", {"operation": "replace_smiles", "atom_index": i}, Chem.MolToSmiles(variant))
        # Estado opuesto al elegido por curadores: NO se atribuye un pKa individual sin fuente.
        for label, pattern in (("carboxilato", "[CX3](=O)[O-]"), ("amina_alifatica", "[NX4+;H1,H2,H3;!$(N-c);!$(N-C=O);!$(N-C=N)]")):
            matches = mol.GetSubstructMatches(Chem.MolFromSmarts(pattern))
            if not matches:
                continue
            i = matches[0][-1] if label == "carboxilato" else matches[0][0]
            variant = Chem.RWMol(mol)
            atom = variant.GetAtomWithIdx(i)
            atom.SetFormalCharge(0)
            atom.SetNumExplicitHs(1 if label == "carboxilato" else max(atom.GetTotalNumHs()-1, 0))
            Chem.SanitizeMol(variant)
            add("especie_opuesta_proxy", {"operation": "replace_smiles", "atom_index": i, "class": label,
                                         "source": "estado opuesto al archivo de curadores; pKa individual no verificado"}, Chem.MolToSmiles(variant))
            break
    declared = [line.split(":")[0] for line in (plb / "data/targets.yml").read_text().splitlines() if line and not line.startswith(" ")]
    public = [
        {"target": "tnks2", "ligand": "lig_7", "category": "especie_del_ligando", "url": "https://github.com/openforcefield/protein-ligand-benchmark/issues/101",
         "summary": "La incidencia comunica un N de amida sin H y carga negativa en lig_7 frente al resto de la serie; se comprueba su representación en el commit fijado, sin adjudicar su población a pH experimental."},
        {"target": "eg5", "ligand": "lig_CHEMBL1084935", "category": "estereoquimica_del_ligando", "url": "https://github.com/openforcefield/protein-ligand-benchmark/issues/101",
         "summary": "La incidencia pregunta por las dos representaciones de estereoquímica de una amina protonada y nombres repetidos. Es una preocupación publicada, no una demostración de que alguna sea incorrecta."},
        {"target": "thrombin", "ligand": "lig_7d", "category": "estereoquimica_del_ligando", "url": "https://github.com/openforcefield/protein-ligand-benchmark/issues/101",
         "summary": "La incidencia pregunta si la medida de lig_7d corresponde a un estereoisómero o una mezcla, ante varias entradas. Se documenta la incertidumbre experimental, sin atribuir un error a los autores."},
        {"target": "tyk2", "ligand": None, "category": "identidad_biologica_fuera_del_catalogo", "url": "https://github.com/openforcefield/protein-ligand-benchmark/issues/112",
         "summary": "La incidencia propone revisar D1023N respecto al sistema del ensayo. El auditor no declara comparar secuencia y construcción experimental; se mide como límite. La correspondencia de numeración con 4GIH no se ha probado."},
    ]
    source_cases = []
    for source in public:
        system = next(s for s in systems if s["target"] == source["target"])
        selected = [(system["record"], None)] if source["ligand"] is None else []
        if source["ligand"]:
            supplier = Chem.SDMolSupplier(system["sdf_path"], removeHs=False)
            selected = [(i, m) for i, m in enumerate(supplier) if m is not None and m.GetProp("_Name") == source["ligand"]]
        source["matched_records"] = [i for i, _ in selected]
        source["opened_on"] = "2026-10-11"
        for i, mol in selected:
            sm = Chem.MolToSmiles(Chem.RemoveHs(mol)) if mol is not None else system["smiles"]
            source_cases.append({"case_id": f"{source['target']}__public__{i}", "target": source["target"],
                                 "ligand": source["ligand"] or system["ligand"], "arm": "C", "category": source["category"],
                                 "repeat": 0, "defect": {"source": source}, "smiles": sm, "baseline_id": None})
    cases.extend(source_cases)
    return {"product_commit": PRODUCT, "plb_commit": actual, "rdkit": rdBase.rdkitVersion, "public_sources": public,
            "systems": systems, "excluded": [{"target": t, "reason": "falta receptor o SDF en rutas prescritas"} for t in declared if t not in targets],
            "cases": cases, "applicable": dict(Counter(c["category"] for c in cases))}


def materialize(plb, system, case, output):
    data, _, _, _ = read_target(plb, system["target"])
    spec = case["defect"]
    op = spec.get("operation")
    lines = data.decode("utf-8").splitlines(keepends=True)
    aa = atoms(data)
    if op in {"remove_residues", "remove_chain"}:
        remove = {tuple(k) for k in spec.get("residues", [])}
        indices = {a["line"] for a in aa if tuple(a["key"]) in remove or (op == "remove_chain" and a["key"][0] == spec["chain"])}
        removed_ids = {int(lines[i][6:11]) for i in indices}
        data = "".join(rewrite_conect(line, {}, removed_ids) if line.startswith("CONECT") else line
                       for i, line in enumerate(lines) if i not in indices).encode()
    elif op == "renumber_serials":
        mapping = {int(lines[a["line"]][6:11]): i+1001 for i, a in enumerate(aa)}
        for a in aa:
            line = lines[a["line"]]
            lines[a["line"]] = line[:6] + f"{mapping[int(line[6:11])]:5d}" + line[11:]
        data = "".join(rewrite_conect(line, mapping) if line.startswith("CONECT") else line for line in lines).encode()
    elif op in {"flip_histidine", "protonate_acid"}:
        key = tuple(spec["residue"])
        rows = [a for a in aa if tuple(a["key"]) == key]
        byname = {a["name"]: a for a in rows}
        if op == "flip_histidine":
            old = byname[spec["hydrogen"]]
            hname, nname = ("HE2", "NE2") if spec["hydrogen"] == "HD1" else ("HD1", "ND1")
            nxyz = byname[nname]["xyz"]
            neighbors = ("CD2", "CE1") if nname == "NE2" else ("CG", "CE1")
            midpoint = [sum(byname[n]["xyz"][j] for n in neighbors)/2 for j in range(3)]
            vec = [a-b for a, b in zip(nxyz, midpoint)]
            norm = math.sqrt(sum(v*v for v in vec))
            xyz = [a+v/norm for a, v in zip(nxyz, vec)]
            line = lines[old["line"]]
            lines[old["line"]] = line[:12] + f"{hname:>4}" + line[16:30] + "".join(f"{v:8.3f}" for v in xyz) + line[54:]
            name = "HIE" if nname == "NE2" else "HID"
            for a in rows:
                line = lines[a["line"]]
                lines[a["line"]] = line[:17] + name + line[20:]
        else:
            oxy = byname[spec["oxygen"]]
            name = "ASH" if key[3] == "ASP" else "GLH"
            hname = "HD2" if key[3] == "ASP" else "HE2"
            for a in rows:
                line = lines[a["line"]]
                lines[a["line"]] = line[:17] + name + line[20:]
            template = lines[oxy["line"]]
            carbon = byname["CG" if key[3] == "ASP" else "CD"]["xyz"]
            vec = [a-b for a, b in zip(oxy["xyz"], carbon)]
            norm = math.sqrt(sum(v*v for v in vec))
            xyz = [a+v/norm for a, v in zip(oxy["xyz"], vec)]
            serial = max(int(line[6:11]) for line in lines if line.startswith(("ATOM  ", "HETATM")))+1
            hline = template[:6] + f"{serial:5d} " + f"{hname:>4}" + template[16:30] + "".join(f"{v:8.3f}" for v in xyz) + template[54:76] + " H\n"
            lines.insert(oxy["line"]+1, hline)
        data = "".join(lines).encode()
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {"input_sha256": sha(data), "smiles_sha256": sha(case["smiles"].encode())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plb", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    plan = describe(args.plb.resolve())
    write_json(args.output, plan)
    print(json.dumps({"targets": len(plan["systems"]), "excluded": plan["excluded"], "applicable": plan["applicable"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
