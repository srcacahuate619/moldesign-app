"""DEC-104-D03-R1. Redocking pareado en HSP90 y BRD4 con aguas conservadas."""
import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from meeko import MoleculePreparation, PDBQTMolecule, PDBQTWriterLegacy, RDKitMolCreate
from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign
from scipy.spatial.distance import cdist
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "scripts/artifacts_science/DEC-104-D03-R1"
VINA = ROOT / "tools/vina/vina.exe"
ARMS = ("SIN", "SELECTIVAS", "TODAS")
SEEDS = (42, 43, 44, 45, 46)
HSP = ("2JJC", "2WI2", "2YE4", "2YE5", "2YE6", "2YEA", "2YEB", "2YEC", "2YED", "3B24", "4FCP")
BRD = ("4BJX", "5WA5", "4PS5", "5D0C", "5U28", "6MH1", "5I88", "4GPJ", "5DLZ", "3ZYU", "5NNE")
CONTROLS = {"6MH1", "5I88", "4GPJ", "5DLZ"}
INSTANCES = {
    "2JJC": ("LGA", 1225), "2WI2": ("ZZ3", 1226), "2YE4": ("2FY", 1224), "2YE5": ("2A7", 1224),
    "2YE6": ("2AE", 1224), "2YEA": ("2A9", 1224), "2YEB": ("2K4", 1224), "2YEC": ("XQ0", 1226),
    "2YED": ("ADE", 1225), "3B24": ("B2J", 237), "4FCP": ("42C", 301), "4BJX": ("73B", 1169),
    "5WA5": ("4K4", 201), "4PS5": ("2TA", 201), "5D0C": ("E0B", 206), "5U28": ("82V", 201),
    "6MH1": ("JQP", 201), "5I88": ("69G", 205), "4GPJ": ("0Q1", 201), "5DLZ": ("5D1", 201), "3ZYU": ("1GH", 1173),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(data):
    files = {}
    for pdb in HSP + BRD:
        name = f"{pdb}.pdb"
        files[name] = {"sha256": sha(data / name), "url": f"https://files.rcsb.org/download/{name}"}
        if pdb in INSTANCES:
            ccd, seq = INSTANCES[pdb]
            name = f"{pdb}.sdf"
            files[name] = {
                "ccd": ccd, "sha256": sha(data / name),
                "url": f"https://models.rcsb.org/v1/{pdb}/ligand?auth_asym_id=A&auth_seq_id={seq}&encoding=sdf",
            }
    return {"vina": sha(VINA), "licencia": "CC0 1.0", "fecha_local": "2026-11-14", "archivos": files}


def position(line):
    return [float(line[i:i+8]) for i in (30, 38, 46)]


def read(data, pdb):
    positions = {}
    for line in (data / f"{pdb}.pdb").read_text(encoding="ascii", errors="replace").splitlines():
        if line[:6] not in {"ATOM  ", "HETATM"} or line[21] != "A" or line[16] not in " A":
            continue
        key = line[:6], line[12:16], line[17:27]
        if key not in positions or positions[key][16] == "A":
            positions[key] = line
    protein = [line for line in positions.values() if line.startswith("ATOM")]
    alpha = {line[17:27]: position(line) for line in protein if line[12:16].strip() == "CA"}
    water = [(line[21:27].strip(), position(line), float(line[54:60])) for line in positions.values()
             if line[17:20].strip() in {"HOH", "WAT", "DOD"} and line[76:78].strip() == "O"]
    return protein, alpha, water, list(positions.values())


def align(target, comparable):
    shared = sorted(set(target) & set(comparable))
    if len(shared) < 30:
        return None
    a = np.array([comparable[k] for k in shared])
    b = np.array([target[k] for k in shared])
    x, y = a.mean(axis=0), b.mean(axis=0)
    u, _, vt = np.linalg.svd((a-x).T @ (b-y))
    if np.linalg.det(u @ vt) < 0:
        u[:, -1] *= -1
    r = u @ vt
    d = np.sqrt(np.mean(np.sum(((a-x) @ r + y-b)**2, axis=1)))
    if d > 1.5:
        return None
    return x, y, r


def water_sets(pdb, all_records, lig, pol, family):
    protein, alpha, waters, _ = all_records[pdb]
    donor = [position(l) for l in protein if l[76:78].strip() in {"N", "O", "S"}]
    aligned = {}
    for other in family:
        if other == pdb or not all_records[other][2]:
            continue
        result = align(alpha, all_records[other][1])
        if result is not None:
            x, y, rot = result
            coords = [c for _, c, o in all_records[other][2] if o >= .5]
            if coords:
                aligned[other] = (coords-x) @ rot + y
    all_water = []
    for res, xyz, occ in waters:
        d_lig = float(cdist([xyz], lig).min())
        if d_lig > 8:
            continue
        d_pol = float(cdist([xyz], pol).min()) if len(pol) else math.inf
        d_prot = float(cdist([xyz], donor).min())
        also = [name for name, pts in aligned.items() if cdist([xyz], pts).min() <= 1]
        all_water.append(dict(res=res, xyz=xyz, ocupacion=occ, d_lig_A=d_lig, d_polar_lig_A=d_pol,
                              d_polar_prot_A=d_prot, otros_depositos=also,
                              selectiva=occ >= .5 and d_pol <= 3.5 and d_prot <= 3.5 and len(also) >= 2))
    return all_water


def append_water(protein, rows):
    lines = [l for l in protein.splitlines() if l.strip() not in {"END", "TER"}]
    serial = max(int(l[6:11]) for l in lines if l.startswith(("ATOM", "HETATM")))
    for i, row in enumerate(rows, 1):
        x, y, z = row["xyz"]
        lines.append(f"ATOM  {serial+i:5d}  O   HOH W{i:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 OA")
    return "\n".join(lines) + "\n"


def prepare(data, work, pdb, all_records):
    work.mkdir(parents=True, exist_ok=True)
    ccd, seq = INSTANCES[pdb]
    protein, _, _, records = all_records[pdb]
    deposited = [position(l) for l in records if l[17:20].strip() == ccd and l[22:26].strip() == str(seq)
                 and l[76:78].strip() not in {"H", "D"}]
    ref = Chem.MolFromMolFile(str(data / f"{pdb}.sdf"))
    xy = ref.GetConformer().GetPositions()
    if len(deposited) != len(xy) or cdist(deposited, xy).min(axis=1).max() > .05:
        raise ValueError(f"SDF fuera de la instancia {pdb}/{ccd}/A/{seq}")
    pol = [p for i, p in enumerate(xy) if ref.GetAtomWithIdx(i).GetAtomicNum() in (7, 8, 16)]
    is_hsp = pdb in HSP
    waters = water_sets(pdb, all_records, xy, pol, HSP if is_hsp else BRD)
    dry = work / "SIN.pdbqt"
    p = work / "protein.pdb"
    p.write_text("\n".join(protein) + "\nEND\n", encoding="ascii")
    cmd = [sys.executable, "-m", "meeko.cli.mk_prepare_receptor", "--read_pdb", str(p), "-p", str(dry),
           "--default_altloc", "A", "-a"]
    process = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    (work / "meeko.log").write_text(process.stdout + "\n" + process.stderr, encoding="utf-8")
    if process.returncode or not dry.is_file():
        raise RuntimeError(f"Meeko {(process.stdout + process.stderr)[-650:]}")
    before = dry.read_text(encoding="ascii")
    mapping = {"SIN": dry}
    for arm, chosen in (("SELECTIVAS", [w for w in waters if w["selectiva"]]), ("TODAS", waters)):
        path = work / f"{arm}.pdbqt"
        if chosen:
            path.write_text(append_water(before, chosen), encoding="ascii")
        mapping[arm] = path if chosen else dry

    mol = Chem.Mol(ref)
    mol.RemoveAllConformers()
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise ValueError("No se pudo generar conformero del CCD")
    setup, = MoleculePreparation().prepare(mol)
    pdbqt, ok, error = PDBQTWriterLegacy.write_string(setup)
    if not ok:
        raise RuntimeError(error)
    ligand = work / "ligand.pdbqt"
    ligand.write_text(pdbqt, encoding="ascii")
    return ref, xy.mean(axis=0), waters, ligand, mapping


def dock(work, arm, seed, center, receptor, ligand, ref):
    output = work / f"{arm}-{seed}.pdbqt"
    cmd = [str(VINA), "--receptor", str(receptor), "--ligand", str(ligand), "--cpu", "1",
           "--out", str(output), "--num_modes", "9", "--exhaustiveness", "8", "--seed", str(seed)]
    for axis, coordinate in zip("xyz", center, strict=True):
        cmd += [f"--center_{axis}", str(coordinate), f"--size_{axis}", "22.0"]
    start = time.monotonic()
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
    (work / f"{arm}-{seed}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode or not output.is_file():
        raise RuntimeError((result.stderr or result.stdout)[-400:])
    parsed = PDBQTMolecule.from_file(str(output), skip_typing=True)
    molecules = RDKitMolCreate.from_pdbqt_mol(parsed)
    m, = [m for m in molecules if m is not None]
    m = Chem.RemoveHs(m)
    scores = [float(l.split()[3]) for l in output.read_text(encoding="ascii").splitlines() if l.startswith("REMARK VINA RESULT:")]
    if not scores or len(scores) != m.GetNumConformers():
        raise ValueError("Poses/energías no coinciden")
    rmsd = [rdMolAlign.CalcRMS(m, ref, prbId=c.GetId()) for c in m.GetConformers()]
    return dict(semilla=seed, rmsd_top1_A=rmsd[0], score_top1_kcal=scores[0],
                rmsd_oraculo_A=min(rmsd), n_poses=len(rmsd), segundos=time.monotonic()-start)


def measure(data, pdb, all_records):
    work = data / "corridas" / pdb
    out = work / "resultado.json"
    if out.is_file():
        return json.loads(out.read_text(encoding="utf-8"))
    row = {"pdb": pdb, "familia": "HSP90" if pdb in HSP else "BRD4", "desplazamiento_control": pdb in CONTROLS}
    try:
        ref, center, water, ligand, receptors = prepare(data, work, pdb, all_records)
        row.update(centro=center.tolist(), aguas=water, sha_ligando=sha(ligand),
                   sha_receptores={n: sha(p) for n, p in receptors.items()}, brazos={})
        cache = {}
        for arm, rec in receptors.items():
            values = []
            for seed in SEEDS:
                try:
                    key = rec, seed
                    if key not in cache:
                        cache[key] = dock(work, arm, seed, center, rec, ligand, ref)
                    values.append(cache[key])
                except Exception as exc:
                    values.append({"semilla": seed, "error": f"{type(exc).__name__}: {exc}"})
            ok = [x for x in values if "rmsd_top1_A" in x]
            row["brazos"][arm] = {
                "casos": values,
                "exitos": sum(v["rmsd_top1_A"] <= 2 for v in ok) if len(ok) == 5 else None,
                "rmsd_top1_mediano": float(np.median([v["rmsd_top1_A"] for v in ok])) if ok else None,
            }
    except Exception as exc:
        row["error_preparacion"] = f"{type(exc).__name__}: {exc}"
    out.write_text(json.dumps(row, ensure_ascii=True) + "\n", encoding="utf-8")
    return row


def summary(rows):
    measured = [r for r in rows if r.get("brazos") and all(r["brazos"][a]["exitos"] is not None for a in ARMS)]
    points = [{a: r["brazos"][a]["exitos"] >= 3 for a in ARMS} for r in measured]
    a = sum(s["SELECTIVAS"] and not s["SIN"] for s in points)
    b = sum(s["SIN"] and not s["SELECTIVAS"] for s in points)
    p = binomtest(a, a+b).pvalue if a+b else 1.0
    control_harm = [r["pdb"] for r, s in zip(measured, points, strict=True)
                    if r["desplazamiento_control"] and s["SIN"] and not s["SELECTIVAS"]]
    decision = "INCONCLUSIVE"
    if len(measured) >= .8*len(INSTANCES) and p < .05:
        if a > b and not control_harm:
            decision = "GO"
        elif b > a:
            decision = "NO_GO"
    return {"n": len(INSTANCES), "pareados": len(measured), "cobertura": {a: sum(s[a] for s in points) for a in ARMS},
            "favor_selectivas": a, "favor_sin": b, "p": p, "perdidas_en_controles": control_harm,
            "decision_tecnica": decision, "decision_receta": "INCONCLUSIVE",
            "inyectaron_agua": sum(any(w["selectiva"] for w in r["aguas"]) for r in measured)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modo", choices=("entradas", "medir", "analizar"))
    parser.add_argument("datos", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--archivar", action="store_true")
    args = parser.parse_args()
    if args.modo == "entradas":
        print(json.dumps(inputs(args.datos), indent=2))
        return
    if inputs(args.datos) != json.loads((ART / "entrada/fuentes.json").read_text(encoding="utf-8")):
        raise SystemExit("Los datos brutos difieren del sello")
    if args.modo == "medir":
        all_records = {p: read(args.datos, p) for p in HSP + BRD}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = [pool.submit(measure, args.datos, p, all_records) for p in INSTANCES]
            for task in as_completed(jobs):
                r = task.result()
                print(r["pdb"], "ERROR" if "error_preparacion" in r else "hecho", flush=True)
    rows = [json.loads(path.read_text(encoding="utf-8")) for p in INSTANCES
            if (path := args.datos / "corridas" / p / "resultado.json").is_file()]
    metrics = summary(rows)
    print(json.dumps(metrics, indent=2))
    if args.archivar:
        if len(rows) != len(INSTANCES) or json.loads((ART / "procedencia.json").read_text(encoding="utf-8"))["salidas"]:
            raise SystemExit("La campaña está incompleta o ya cerrada")
        (ART / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
        (ART / "per_complex.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
