"""Reusa los modelos Chai-1 archivados y compara CDK2 con 1HCL y 1H1Q."""
import argparse
import json
import sys
from pathlib import Path

import gemmi
import numpy as np
from Bio.Align import PairwiseAligner
from scipy.spatial.distance import cdist
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from medir_d01 import leer_mmcif, protein_residues, sequence, series_del_archivo, sha256, xyz


def load(path):
    structure = gemmi.read_structure(str(path))
    structure.setup_entities()
    return structure[0]["A"]


def correspond(first, second):
    a, b = sequence(first).upper(), sequence(second).upper()
    aligner = PairwiseAligner(
        mode="global", match_score=2, mismatch_score=-3, open_gap_score=-8, extend_gap_score=-0.2
    )
    i, j = aligner.align(a, b)[0].indices
    pairs = [(x, y) for x, y in zip(i, j) if min(x, y) >= 0 and a[x] == b[y]]
    return np.array(pairs).T


def quantify(prediction, ref, selected, confidence):
    a, b = correspond(ref, prediction)
    rc = [xyz(ref[k].get_ca()) for k in a]
    pc = [xyz(prediction[k].get_ca()) for k in b]
    dr = cdist(rc, rc)
    dp = cdist(pc, pc)
    eligible = (dr < 15) & ~np.eye(len(a), dtype=bool)
    deltas = abs(dr - dp)
    lddt = 100 * np.mean([(eligible & (deltas < t)).sum(axis=1) / eligible.sum(axis=1)
                          for t in (0.5, 1, 2, 4)], axis=0)
    site = np.array([k in selected for k in a])
    out = {}
    for area, mask in {"cadena": np.ones(len(a), dtype=bool), "sitio": site}.items():
        truth = lddt[mask] < 70
        values = {"n": int(mask.sum()), "lddt_mediano": float(np.median(lddt[mask])), "observados_bajo70": int(truth.sum())}
        for key, scores in confidence.items():
            p = np.array(scores)[b][mask]
            event = p < 70
            rho = spearmanr(p, lddt[mask]).statistic
            values[key] = {
                "rho": float(rho) if np.isfinite(rho) else None, "predichos_bajo70": int(event.sum()),
                "tp": int((event & truth).sum()), "tn": int((~event & ~truth).sum()),
            }
        out[area] = values
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo_chai", type=Path)
    parser.add_argument("pdb", type=Path)
    args = parser.parse_args()
    apo = args.pdb / "1HCL.pdb"
    holo = args.pdb / "1H1Q.pdb"
    apo_protein, holo_protein = protein_residues(load(apo)), protein_residues(load(holo))
    ligand, = [r for r in load(holo) if r.name == "2A6"]
    ligand_xyz = [xyz(a) for a in ligand if not a.element.is_hydrogen]
    holo_site = {i for i, r in enumerate(holo_protein)
                 if cdist([xyz(a) for a in r if not a.element.is_hydrogen], ligand_xyz).min() <= 6}
    a, b = correspond(holo_protein, apo_protein)
    apo_site = {j for i, j in zip(a, b) if i in holo_site}
    rows = []
    files = sorted((args.archivo_chai / "resultados" / "chai").glob("cdk2*/*.cif"))
    if len(files) != 10:
        raise ValueError("El archivo debe contener diez muestras CDK2")
    for file in files:
        protein = protein_residues(load(file))
        values = series_del_archivo(leer_mmcif(file))
        confidence = {
            "campo_local": next(v[0] for key, v in values.items() if key.startswith("ma_qa_metric_local[")),
            "media": values["b_media_por_residuo_proteina"][0],
        }
        if any(r.label_seq != i + 1 for i, r in enumerate(protein)) or len(protein) != len(confidence["media"]):
            raise ValueError("No se puede emparejar confianza con residuos")
        rows.append({"caso": file.parent.name, "muestra": file.name, "sha256": sha256(file),
                     "1HCL": quantify(protein, apo_protein, apo_site, confidence),
                     "1H1Q": quantify(protein, holo_protein, holo_site, confidence)})
    print(json.dumps({"fuentes": {
        "1HCL": {"url": "https://www.rcsb.org/structure/1HCL", "sha256": sha256(apo)},
        "1H1Q": {"url": "https://www.rcsb.org/structure/1H1Q", "sha256": sha256(holo)},
    }, "licencia": "CC0 1.0", "fecha_local": "2026-11-15", "sitio": {"1HCL": len(apo_site), "1H1Q": len(holo_site)},
        "filas": rows}, indent=2))


if __name__ == "__main__":
    main()
