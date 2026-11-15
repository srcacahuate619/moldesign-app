"""Recuenta las lecturas de Chai-1 y compara NET con 8HFI según D01-contraste-NET.md."""
import argparse
import json
import sys
from pathlib import Path

import gemmi
import numpy as np
from Bio.Align import PairwiseAligner
from scipy.spatial.distance import cdist
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "colab_plddt"))

from analisis_plddt import leer_mmcif, series_del_archivo, sha256


def xyz(atom):
    return list(atom.pos)


def protein_residues(chain):
    return [
        r for r in chain
        if r.entity_type == gemmi.EntityType.Polymer and r.get_ca() is not None
    ]


def sequence(residues):
    return "".join(gemmi.find_tabulated_residue(r.name).one_letter_code for r in residues)


def score_net(cif, reference, producto, media):
    model = gemmi.read_structure(str(cif))
    model.setup_entities()
    pred = protein_residues(model[0]["A"])
    ref = protein_residues(reference[0]["A"])
    ligand = next(r for r in reference[0]["A"] if r.name == "DSM" and r.seqid.num == 701)
    ligand_coords = [xyz(a) for a in ligand if not a.element.is_hydrogen]

    aligner = PairwiseAligner(
        mode="global", match_score=2, mismatch_score=-3, open_gap_score=-8, extend_gap_score=-0.2
    )
    ref_seq, pred_seq = sequence(ref), sequence(pred)
    ref_i, pred_i = aligner.align(ref_seq, pred_seq)[0].indices
    pairs = [(i, j) for i, j in zip(ref_i, pred_i) if min(i, j) >= 0 and ref_seq[i] == pred_seq[j]]
    i, j = map(np.array, zip(*pairs))
    if len(pred) != len(producto) or any(r.label_seq != k + 1 for k, r in enumerate(pred)):
        raise ValueError("La serie de confianza y la cadena predicha no se pueden emparejar")

    observed = np.array([xyz(ref[k].get_ca()) for k in i])
    inferred = np.array([xyz(pred[k].get_ca()) for k in j])
    dref = cdist(observed, observed)
    mask = (dref < 15) & ~np.eye(len(i), dtype=bool)
    error = np.abs(dref - cdist(inferred, inferred))
    fractions = [(mask & (error < t)).sum(axis=1) / mask.sum(axis=1) for t in (0.5, 1, 2, 4)]
    lddt = np.mean(fractions, axis=0) * 100
    site = np.array([
        cdist([xyz(a) for a in ref[k] if not a.element.is_hydrogen], ligand_coords).min() <= 6
        for k in i
    ])

    def measure(values, scope):
        q, target = np.array(values)[j][scope], lddt[scope]
        truth = target < 70
        predicted = q < 70
        rho = spearmanr(q, target).statistic
        return {
            "n": int(len(q)), "referencia_bajo70": int(truth.sum()),
            "prediccion_bajo70": int(predicted.sum()),
            "tp": int((truth & predicted).sum()), "tn": int((~truth & ~predicted).sum()),
            "lddt_mediano": float(np.median(target)),
            "rho": float(rho) if np.isfinite(rho) else None,
        }

    return {
        "referencia_ca_resueltos": len(ref), "prediccion_ca": len(pred),
        "mapeados": len(i),
        "sitio_referencia_total": sum(
            cdist([xyz(a) for a in r if not a.element.is_hydrogen], ligand_coords).min() <= 6 for r in ref
        ).item(),
        "cadena": {k: measure(v, np.ones(len(i), dtype=bool)) for k, v in (("local", producto), ("media", media))},
        "sitio": {k: measure(v, site) for k, v in (("local", producto), ("media", media))},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archivo", type=Path, help="Directorio que contiene resultados/chai")
    args = parser.parse_args()
    ref_file = ROOT / "data" / "targets" / "8HFI.pdb.gz"
    ref = gemmi.read_structure(str(ref_file))
    ref.setup_entities()
    files = sorted((args.archivo / "resultados" / "chai").glob("*/*.cif"))
    if len(files) != 15:
        raise SystemExit(f"Se esperaban 15 muestras Chai-1, se encontraron {len(files)}")
    rows = []
    for cif in files:
        read = leer_mmcif(cif)
        values = series_del_archivo(read)
        local = next(v[0] for k, v in values.items() if k.startswith("ma_qa_metric_local["))
        mean = values["b_media_por_residuo_proteina"][0]
        ca = values["b_ca_por_residuo_proteina"][0]
        row = {
            "caso": cif.parent.name, "muestra": cif.name, "sha256": sha256(cif),
            "titulo": gemmi.cif.read_file(str(cif)).sole_block().find_value("_struct.title"),
            "residuos": len(local), "local_bajo70": sum(v < 70 for v in local),
            "media_bajo70": sum(v < 70 for v in mean),
            "max_abs_local_ca": max(abs(a - b) for a, b in zip(local, ca, strict=True)),
            "solo_media_bajo70": sum(a >= 70 > b for a, b in zip(local, mean, strict=True)),
            "solo_local_bajo70": sum(b >= 70 > a for a, b in zip(local, mean, strict=True)),
        }
        if cif.parent.name.startswith("net"):
            row["lddt_ca"] = score_net(cif, ref, local, mean)
        rows.append(row)
    print(json.dumps({"referencia_sha256": sha256(ref_file), "chai": rows}, indent=2))


if __name__ == "__main__":
    main()
