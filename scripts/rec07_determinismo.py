#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rec07_determinismo.py — Evalúa el gate G6 de REC-07, que quedó sin medir.

El PREREGISTRO de REC-07 exige G6 («misma semilla → mismo score top-1 y misma
distancia de contacto al repetir») y la corrida principal lo dejó en `null`.
Este script repite la semilla 42 en los tres brazos con el MISMO receptor y el
MISMO ligando ya preparados en `_work/`, y compara contra `per_complex.jsonl`.

No modifica ningún criterio ni recalcula ningún otro gate: solo rellena G6.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_rec07_grid_5tun as R  # noqa: E402

OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "REC-07"
WD = OUT_DIR / "_work"
SEED = 42


def repetir(brazo: str) -> dict:
    c, s = R.GRIDS[brazo]
    out = WD / f"det_{brazo}_{SEED}.pdbqt"
    cmd = [str(R.VINA), "--receptor", str(WD / "5TUN_receptor.pdbqt"),
           "--ligand", str(WD / "E6C.pdbqt"),
           "--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
           "--size_x", str(s[0]), "--size_y", str(s[1]), "--size_z", str(s[2]),
           "--exhaustiveness", str(R.EXHAUSTIVENESS), "--num_modes", str(R.NUM_MODES),
           "--seed", str(SEED), "--cpu", str(R.CPU), "--out", str(out)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    fila = {"brazo": brazo, "seed": SEED, "rc": r.returncode,
            "wall_s": round(time.time() - t0, 2)}
    if r.returncode == 0 and out.exists():
        res = R.leer_atomos(R.PDB_5TUN)
        sg = res["A:CYS25"]["SG"]
        modos = R.parsear_poses(out)
        if modos:
            fila["score_top1"] = modos[0]["score"]
            fila["d_min_cys25_sg_top1"] = round(
                min(math.dist(a, sg) for a in modos[0]["atomos"]), 3)
            fila["n_modos"] = len(modos)
    return fila


def main() -> int:
    originales = {(r["brazo"], r["seed"]): r for r in (
        json.loads(l) for l in (OUT_DIR / "per_complex.jsonl").read_text(
            encoding="utf-8").splitlines() if l.strip())}

    with ThreadPoolExecutor(max_workers=3) as ex:
        repeticiones = list(ex.map(repetir, list(R.GRIDS)))

    comparacion = []
    for rep in repeticiones:
        orig = originales.get((rep["brazo"], SEED), {})
        comparacion.append({
            "brazo": rep["brazo"],
            "score_original": orig.get("score_top1"),
            "score_repeticion": rep.get("score_top1"),
            "d_original": orig.get("d_min_cys25_sg_top1"),
            "d_repeticion": rep.get("d_min_cys25_sg_top1"),
            "identico": (orig.get("score_top1") == rep.get("score_top1")
                         and orig.get("d_min_cys25_sg_top1") == rep.get("d_min_cys25_sg_top1")),
        })

    metrics = json.loads((OUT_DIR / "metrics.json").read_text(encoding="utf-8"))
    metrics["gates"]["G6_determinismo"] = {
        "criterio": "misma semilla -> mismo top1 y misma distancia",
        "n_brazos_repetidos": len(comparacion),
        "semilla": SEED,
        "comparacion": comparacion,
        "pass": all(c["identico"] for c in comparacion),
    }
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")

    for c in comparacion:
        print(f"  {c['brazo']:<10} score {c['score_original']} -> {c['score_repeticion']} | "
              f"d {c['d_original']} -> {c['d_repeticion']} | "
              f"{'IDENTICO' if c['identico'] else 'DIFIERE'}")
    print(f"[REC-07] G6 determinismo: {'PASS' if all(c['identico'] for c in comparacion) else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
