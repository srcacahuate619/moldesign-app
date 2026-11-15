"""Piloto DEC-104-D05-PROLIF sobre los seis depósitos y 30 top-1 archivados."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import prolif
from rdkit import Chem

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import calibracion_receptor as cal

SOURCE = ROOT / "scripts/artifacts_science/MET-01-R1-ION-DEL-SITIO"
TARGETS = ROOT / "data/targets"
INVENTORY = ROOT / "docs/auditorias/metales_junto_al_sitio_2026-10-11.json"
ARTIFACT = ROOT / "scripts/artifacts_science/DEC-104-D05-PROLIF"
CASES = {"1BN1": 555, "2AW1": 264, "4QA0": 404, "2JDI": 1511, "4WUD": 401, "4PHL": 1003}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entries():
    rows = [json.loads(line) for line in (SOURCE / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()]
    selected = [r for r in rows if r["entry"] in CASES and r["phase"] == "confirmatory" and r["arm"] == "CON"]
    if len(selected) != 30:
        raise ValueError("El contraste requiere las 30 poses CON congeladas")
    return selected


def inputs(data):
    out = {}
    for pdb, seq in CASES.items():
        name = f"{pdb}.sdf"
        out[name] = {"sha256": digest(data / name), "url":
                     f"https://models.rcsb.org/v1/{pdb}/ligand?auth_asym_id=A&auth_seq_id={seq}&encoding=sdf"}
        out[f"{pdb}.pdb.gz"] = {"sha256": digest(TARGETS / f"{pdb}.pdb.gz"), "url": f"https://www.rcsb.org/structure/{pdb}"}
    raw = {r["raw"]: digest(SOURCE / r["raw"]) for r in entries()}
    return {"depositos_cc0": out, "fecha_local": "2026-11-15", "crudos_MET01R1": raw,
            "geometria_fecha_repositorio": digest(INVENTORY)}


def coordinates(line):
    return np.array([float(line[i:i+8]) for i in (30, 38, 46)])


def reference(mol, pdb):
    lines = gzip.decompress((TARGETS / f"{pdb}.pdb.gz").read_bytes()).decode(errors="replace").splitlines()
    seq = CASES[pdb]
    ref = [coordinates(l) for l in lines if l.startswith("HETATM") and l[21] == "A"
           and l[22:26].strip() == str(seq) and l[16] in " A" and l[76:78].strip() not in {"H", "D"}]
    cp = mol.GetConformer().GetPositions()
    if len(ref) != len(cp) or np.linalg.norm(np.asarray(ref)[:,None] - cp[None,:], axis=2).min(axis=1).max() > .05:
        raise ValueError(f"SDF fuera de instancia RCSB: {pdb}")
    for r in json.loads(INVENTORY.read_text(encoding="utf-8"))["filas"]:
        if r["pdb_id"] != pdb:
            continue
        chain, num = r["metal_id"].split(":")
        line, = [l for l in lines if l.startswith("HETATM") and l[21] == chain and l[22:26].strip() == num
                 and l[76:78].strip() == r["metal"] and l[16] in " A"]
        yield r, coordinates(line)


def ion(element, xyz):
    editable = Chem.RWMol()
    atom = Chem.Atom(element.capitalize())
    atom.SetFormalCharge(2)
    editable.AddAtom(atom)
    m = editable.GetMol()
    Chem.SanitizeMol(m)
    conf = Chem.Conformer(1)
    conf.SetAtomPosition(0, xyz)
    m.AddConformer(conf)
    return prolif.Molecule.from_rdkit(m)


def find(mol, metal, xyz, fingerprint):
    lp = prolif.Molecule.from_rdkit(Chem.AddHs(mol, addCoords=True))
    ip = ion(metal, xyz)
    match = fingerprint.generate(lp, ip, metadata=True)
    hits = [
        {"tipo": kind, "distancia_A": float(hit["distance"])}
        for groups in match.values() for kind, hits in groups.items() for hit in hits
    ]
    indices = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetSymbol() in {"N", "O", "S"}]
    points = mol.GetConformer().GetPositions()[indices]
    geom = float(np.linalg.norm(points - xyz, axis=1).min()) if len(points) else None
    return {"hits": hits, "distancia_NOS_A": geom, "aviso_NOS": geom is not None and geom <= 2.8}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modo", choices=("entradas", "medir"))
    parser.add_argument("datos", type=Path)
    parser.add_argument("--archivar", action="store_true")
    args = parser.parse_args()
    sources = inputs(args.datos)
    if args.modo == "entradas":
        print(json.dumps(sources, ensure_ascii=True, indent=2))
        return
    if sources != json.loads((ARTIFACT / "entrada/fuentes.json").read_text(encoding="utf-8")):
        raise ValueError("Las entradas difieren")
    rows = []
    fp = prolif.Fingerprint(["MetalAcceptor", "MetalDonor"], count=True)
    archived = entries()
    for pdb in CASES:
        ligand = Chem.MolFromMolFile(str(args.datos / f"{pdb}.sdf"))
        ions = list(reference(ligand, pdb))
        shifted = Chem.Mol(ligand)
        conf = shifted.GetConformer()
        for i in range(shifted.GetNumAtoms()):
            xyz = np.array(conf.GetAtomPosition(i)) + [30, 0, 0]
            conf.SetAtomPosition(i, xyz)
        choices = [("cristal", None, ligand), ("trasladado", None, shifted)]
        for case in archived:
            if case["entry"] != pdb:
                continue
            raw = json.loads(gzip.decompress((SOURCE / case["raw"]).read_bytes()))
            mol, _, match = cal._top1(raw)
            if not match:
                raise ValueError(f"Top-1 de {case['id']} no mapea")
            choices.append(("CON", case["seed"], mol))
        for arm, seed, l in choices:
            for info, xyz in ions:
                rows.append({"pdb": pdb, "brazo": arm, "semilla": seed, "metal": info["metal"],
                             "id": info["metal_id"], "cristal_coordina": info["lo_coordina_el_ligando"],
                             **find(l, info["metal"], xyz, fp)})
    positives = [r for r in rows if r["brazo"] == "cristal" and r["cristal_coordina"]]
    negatives = [r for r in rows if r["brazo"] == "trasladado" or (r["brazo"] == "cristal" and not r["cristal_coordina"])]
    con = [r for r in rows if r["brazo"] == "CON"]
    tp, fp_n = sum(bool(r["hits"]) for r in positives), sum(bool(r["hits"]) for r in negatives)
    decision = "GO" if tp == len(positives) and not fp_n else "NO_GO"
    metrics = {"prolif": prolif.__version__, "n_cristales_positivos": len(positives), "positivos_detectados": tp,
               "n_pares_control_negativo": len(negatives), "falsos_positivos": fp_n, "decision": decision,
               "con_pares_ion_pose": len(con), "con_geometrica": sum(r["aviso_NOS"] for r in con),
               "con_ProLIF": sum(bool(r["hits"]) for r in con),
               "discordantes_con": [r for r in con if r["aviso_NOS"] != bool(r["hits"])]}
    if args.archivar:
        if json.loads((ARTIFACT / "procedencia.json").read_text(encoding="utf-8"))["salidas"]:
            raise SystemExit("Experimento ya cerrado")
        (ARTIFACT / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        (ARTIFACT / "per_complex.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
