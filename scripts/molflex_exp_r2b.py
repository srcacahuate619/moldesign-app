"""MolFlex R2b — política de pruning para mitigar R2 (bioactiva fuera del top-K energético).

Compara 3 políticas de selección de conformeros:
  P1: top-15 por energía MMFF (la ingenua que R2 refutó)
  P2: ventana 10 kcal/mol + dedup por Torsion Fingerprint Deviation (0.15)
  P3: ventana 12 kcal/mol + dedup TFD (0.15)

Métricas: nº medio de conformeros, cobertura de la bioactiva (<1.5A RMSD),
min-RMSD mediano. Sin docking — solo ETKDG + MMFF + TFD.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, TorsionFingerprints

RDLogger.logger().setLevel(RDLogger.ERROR)

PDBBIND = Path("data/pdbbind")
N_COMPLEX = 30
OUT = Path("scripts/artifacts_molflex_r2b.json")


def build_ensemble(pid: str, n: int = 120):
    sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
    m = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    if m is None:
        return None, None, []
    crystal = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    mh = Chem.AddHs(m)
    try:
        ids = list(AllChem.EmbedMultipleConfs(
            mh, numConfs=n, randomSeed=42,
            useExpTorsionAnglePrefs=True, useBasicKnowledge=True,
            pruneRmsThresh=0.4, numThreads=0,
        ))
    except Exception:
        return mh, crystal, []
    return mh, crystal, ids


def min_rmsd(mh, crystal, ids) -> float:
    ph = Chem.RemoveHs(mh)
    rh = Chem.RemoveHs(crystal)
    best = 999.0
    for cid in ids:
        try:
            r = AllChem.GetBestRMS(ph, rh, cid, -1)
            if r < best:
                best = r
        except Exception:
            pass
    return best


def dedup_tfd(mh, cids, dev_thresh: float = 0.15) -> list[int]:
    if not cids:
        return []
    kept = [cids[0]]
    for cid in cids[1:]:
        try:
            tfd = TorsionFingerprints.GetTFDBetweenConformers(mh, [kept[-1]], [cid])
            # GetTFDBetweenConformers retorna list[list[float]]
            dev = float(tfd[0][0])
        except Exception:
            dev = 1.0
        if dev > dev_thresh:
            kept.append(cid)
    return kept


def main() -> None:
    results = {
        "P1_top15": {"n_conf": [], "cov": [], "minrmsd": []},
        "P2_win10": {"n_conf": [], "cov": [], "minrmsd": []},
        "P3_win12": {"n_conf": [], "cov": [], "minrmsd": []},
    }
    done = 0
    for d in sorted(PDBBIND.iterdir()):
        if done >= N_COMPLEX:
            break
        if not d.is_dir() or len(d.name) != 4:
            continue
        if not (d / f"{d.name}_ligand.sdf").exists():
            continue
        mh, crystal, ids = build_ensemble(d.name)
        if mh is None or crystal is None or not ids:
            continue

        props = AllChem.MMFFGetMoleculeProperties(mh)
        es = []
        for cid in ids:
            try:
                ff = AllChem.MMFFGetMoleculeForceField(mh, props, confId=cid)
                if ff is not None:
                    es.append((ff.CalcEnergy(), cid))
            except Exception:
                continue
        if not es:
            continue
        es.sort(key=lambda x: x[0])
        emin = es[0][0]

        p1 = [cid for _, cid in es[:15]]
        results["P1_top15"]["n_conf"].append(len(p1))
        results["P1_top15"]["cov"].append(1 if min_rmsd(mh, crystal, p1) < 1.5 else 0)
        results["P1_top15"]["minrmsd"].append(min_rmsd(mh, crystal, p1))

        for name, win in (("P2_win10", 10.0), ("P3_win12", 12.0)):
            cand = [cid for e, cid in es if e <= emin + win]
            kept = dedup_tfd(mh, cand)
            results[name]["n_conf"].append(len(kept))
            results[name]["cov"].append(1 if min_rmsd(mh, crystal, kept) < 1.5 else 0)
            results[name]["minrmsd"].append(min_rmsd(mh, crystal, kept))
        done += 1

    summary = {}
    for name, r in results.items():
        n = len(r["cov"])
        summary[name] = {
            "n": n,
            "mean_n_conf": round(st.mean(r["n_conf"]), 1) if r["n_conf"] else None,
            "coverage_lt_1p5": round(sum(r["cov"]) / n, 3) if n else None,
            "median_minrmsd": round(st.median(r["minrmsd"]), 2) if r["minrmsd"] else None,
        }
        print(f"{name}: {summary[name]}")
    OUT.write_text(json.dumps(summary, indent=2))
    print(f"-> {OUT}")


if __name__ == "__main__":
    main()
