"""Reanuda DEC-104-D03-R1 por semilla con el arnés y los parámetros sellados."""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from meeko import PDBQTMolecule, RDKitMolCreate
from rdkit import Chem
from rdkit.Chem import rdMolAlign

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import medir_d03 as base


def inspect_finished(path, logfile, ref, seed):
    """Una semilla existe sólo si hay poses completas y el log cerró con la tabla de Vina."""
    if not path.is_file() or not logfile.is_file():
        return None
    logfile = logfile.read_text(encoding="utf-8", errors="replace")
    if "mode |" not in logfile or "ERROR" in logfile or "Parse error" in logfile:
        return None
    text = path.read_text(encoding="ascii")
    scores = [float(line.split()[3]) for line in text.splitlines() if line.startswith("REMARK VINA RESULT:")]
    if not scores or text.count("ENDMDL") != len(scores):
        return None
    parsed = PDBQTMolecule.from_file(str(path), skip_typing=True)
    m, = [m for m in RDKitMolCreate.from_pdbqt_mol(parsed) if m is not None]
    m = Chem.RemoveHs(m)
    if len(scores) != m.GetNumConformers():
        return None
    rmsd = [rdMolAlign.CalcRMS(m, ref, prbId=c.GetId()) for c in m.GetConformers()]
    return dict(semilla=seed, rmsd_top1_A=rmsd[0], score_top1_kcal=scores[0],
                rmsd_oraculo_A=min(rmsd), n_poses=len(rmsd), segundos=None, reutilizada=True)


def setup(data):
    everything = {p: base.read(data, p) for p in base.HSP + base.BRD}
    pending = {}
    for pdb in base.INSTANCES:
        work = data / "corridas" / pdb
        if (work / "resultado.json").is_file():
            continue
        previous = {p: base.sha(p) for p in work.glob("*.pdbqt")
                    if p.stem in set(base.ARMS) | {"ligand"}}
        try:
            ref, center, water, ligand, receptors = base.prepare(data, work, pdb, everything)
            if any(base.sha(path) != digest for path, digest in previous.items()):
                raise RuntimeError("Los bytes de preparación difieren de los usados antes de reanudar")
        except Exception as exc:
            base_error = {"pdb": pdb, "familia": "HSP90" if pdb in base.HSP else "BRD4",
                          "error_preparacion": f"{type(exc).__name__}: {exc}"}
            (work / "resultado.json").write_text(json.dumps(base_error) + "\n", encoding="utf-8")
            continue
        pending[pdb] = (work, ref, center, water, ligand, receptors)
    return pending


def evaluate(work, arm, seed, ref, center, rec, lig):
    try:
        old = inspect_finished(work / f"{arm}-{seed}.pdbqt", work / f"{arm}-{seed}.log", ref, seed)
        return old if old is not None else base.dock(work, arm, seed, center, rec, lig, ref)
    except Exception as exc:
        return {"semilla": seed, "error": f"{type(exc).__name__}: {exc}"}


def write_case(pdb, case, result):
    work, _, center, water, ligand, receptors = case
    row = {"pdb": pdb, "familia": "HSP90" if pdb in base.HSP else "BRD4",
           "desplazamiento_control": pdb in base.CONTROLS, "centro": center.tolist(), "aguas": water,
           "sha_ligando": base.sha(ligand), "sha_receptores": {n: base.sha(p) for n, p in receptors.items()},
           "brazos": {}}
    for arm, receptor in receptors.items():
        cases = [result[receptor, seed] for seed in base.SEEDS]
        ok = [v for v in cases if "rmsd_top1_A" in v]
        row["brazos"][arm] = {"casos": cases, "exitos": sum(v["rmsd_top1_A"] <= 2 for v in ok) if len(ok) == 5 else None,
                             "rmsd_top1_mediano": float(np.median([v["rmsd_top1_A"] for v in ok])) if ok else None}
    file = work / "resultado.json"
    tmp = file.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(file)
    print(pdb, "hecho", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("datos", type=Path)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    frozen = base.ART / "entrada"
    if (HERE / "medir_d03.py").read_bytes() != (frozen / "medir_d03.py").read_bytes():
        raise SystemExit("El arnés no coincide con el sello")
    if base.inputs(args.datos) != json.loads((frozen / "fuentes.json").read_text(encoding="utf-8")):
        raise SystemExit("Las entradas no coinciden con el sello")
    pending = setup(args.datos)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures, results = {}, {}
        needs = {}
        for pdb, (work, ref, center, water, ligand, receptors) in pending.items():
            first = {}
            for arm, receptor in receptors.items():
                first.setdefault(receptor, arm)
            needs[pdb] = len(first) * len(base.SEEDS)
            results[pdb] = {}
            for receptor, arm in first.items():
                for seed in base.SEEDS:
                    task = pool.submit(evaluate, work, arm, seed, ref, center, receptor, ligand)
                    futures[task] = pdb, receptor, arm, seed
        for task in as_completed(futures):
            pdb, receptor, arm, seed = futures[task]
            result = task.result()
            results[pdb][receptor, seed] = result
            print(pdb, arm, seed, "ERROR" if "error" in result else "OK", flush=True)
            if len(results[pdb]) == needs[pdb]:
                write_case(pdb, pending[pdb], results[pdb])


if __name__ == "__main__":
    main()
