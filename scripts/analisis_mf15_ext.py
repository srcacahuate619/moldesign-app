#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf15_ext.py — MF-15-EXT: el embudo sobre el material denso (~751 poses).

**Tipo: medición.** Relectura del material sellado de `MF-02D` + `MF-02F`, el mismo
que leyeron `MF-09` y `MF-09-SYM`. Sin cómputo nuevo.

Por qué extender
----------------
`MF-15` midió el embudo sobre el conjunto v2 (~162 poses por complejo) y encontró
Spearman ≈ 0.21 en el estrato difícil frente a ≈ 0.50 en los controles. Ese número es
el eje de la lectura mecánica de toda la línea, y tenía dos debilidades:

  1. **Potencia**: 162 poses por complejo, y a radios pequeños quedaban 0 complejos
     con muestra suficiente en COLOCACION (a R≤2 Å) o 2 (a R≤3 Å). Ahí no se medía
     nada.
  2. El material denso tiene **~751 poses por complejo**, 4.6× más, que es justo lo
     que hace falta para resolver el embudo a radios cortos.

Aquí se rehace sobre ese material. Se reporta también el RMSD corregido por simetría
(`MF-09-SYM`, doc. 49 §5.1) además del ingenuo, porque el embudo es una correlación
con el RMSD y conviene saber si la elección de métrica lo mueve.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MATERIAL = PROJECT_ROOT / "data" / "molflex_reinicios"
MATERIAL_K30 = PROJECT_ROOT / "data" / "molflex_train_v2"
COHORTE = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-15-EXT"
RADIOS = (2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 1e9)
MIN_POSES = 8
MAX_AUTOS = 5000


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < MIN_POSES:
        return None

    def rangos(v):
        orden = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
                j += 1
            prom = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[orden[k]] = prom
            i = j + 1
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def _perms(crystal, pesados):
    pos = {i: k for k, i in enumerate(pesados)}
    out = []
    for a in crystal.GetSubstructMatches(crystal, uniquify=False, useChirality=True,
                                         maxMatches=MAX_AUTOS):
        try:
            out.append([pos[a[i]] for i in pesados])
        except KeyError:
            continue
    return out or [list(range(len(pesados)))]


def _analizar(job: Dict[str, str]) -> Dict[str, Any]:
    import molflex as mf
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"]}
    dirs = [d / pid / pid for d in (MATERIAL_K30, MATERIAL)]
    dirs = [d for d in dirs if (d / "index_map.json").exists()]
    if not dirs:
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    cf = crystal.GetConformer(0)
    ref = [[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
           for i in pesados]
    P = _perms(crystal, pesados)
    n_at = len(pesados)

    scores, ing, cor = [], [], []
    for w in dirs:
        s2m = {int(s): int(m) for s, m in
               json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
        for f in sorted(w.glob("conf*.out.pdbqt")):
            for sc, at in mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace")):
                if sc is None:
                    continue
                c = mf.coords_pose_a_por_mol(at, s2m)
                if not c or any(i not in c for i in pesados):
                    continue
                pose = [list(c[i]) for i in pesados]
                s = sum((ref[i][0]-pose[i][0])**2 + (ref[i][1]-pose[i][1])**2
                        + (ref[i][2]-pose[i][2])**2 for i in range(n_at))
                a = (s / n_at) ** 0.5
                mejor = a
                for p in P:
                    s2 = 0.0
                    for i in range(n_at):
                        j = p[i]
                        s2 += ((ref[i][0]-pose[j][0])**2 + (ref[i][1]-pose[j][1])**2
                               + (ref[i][2]-pose[j][2])**2)
                    r = (s2 / n_at) ** 0.5
                    if r < mejor:
                        mejor = r
                scores.append(float(sc))
                ing.append(a)
                cor.append(mejor)
    out["n_poses"] = len(ing)
    if len(ing) < MIN_POSES:
        out["error"] = "POCAS_POSES"
        return out
    for etiq, rms in (("ingenuo", ing), ("corregido", cor)):
        d = {}
        for R in RADIOS:
            idx = [i for i, x in enumerate(rms) if x <= R]
            k = "global" if R > 1e8 else str(R)
            d[k] = {"n": len(idx),
                    "rho": _spearman([rms[i] for i in idx], [scores[i] for i in idx])}
        out[f"spearman_{etiq}"] = d
    out["oraculo_ingenuo"] = round(min(ing), 3)
    out["oraculo_corregido"] = round(min(cor), 3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-15-EXT: embudo sobre material denso")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coh = json.loads(COHORTE.read_text(encoding="utf-8"))
    jobs = [{"pid": p, "estrato": "COLOCACION"} for p in coh["cohorte_colocacion"]] + \
           [{"pid": p, "estrato": "CONTROL"} for p in coh["control_cubiertos"]]
    print(f"[MF-15-EXT] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            g = r.get("spearman_ingenuo", {}).get("global", {})
            print(f"  [{i}/{len(jobs)}] {r['pid']} n={r.get('n_poses')} "
                  f"rho_global={g.get('rho')} ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        d: Dict[str, Any] = {"n": len(g),
                             "n_poses_mediana": int(median(r["n_poses"] for r in g))}
        for etiq in ("ingenuo", "corregido"):
            por_R = {}
            for R in RADIOS:
                k = "global" if R > 1e8 else str(R)
                vals = [r[f"spearman_{etiq}"][k]["rho"] for r in g
                        if r[f"spearman_{etiq}"][k]["rho"] is not None]
                por_R[k] = {"n_complejos": len(vals),
                            "rho_mediano": round(median(vals), 4) if vals else None}
            d[f"spearman_{etiq}"] = por_R
        resumen[est] = d
    metrics = {
        "experiment_id": "MF-15-EXT",
        "tipo": "medicion (relectura de material sellado, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "material": "MF-02D (prefijo K30) + MF-02F, ~751 poses por complejo",
        "convencion": "vina_score mas negativo = mejor; EMBUDO => rho POSITIVO",
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-15-EXT] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
