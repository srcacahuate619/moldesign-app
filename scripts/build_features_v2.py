#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_features_v2.py — Las 224 features del conjunto v2 (Ruta C, Fase 0, v2).

Prerrequisito formal: `scripts/artifacts_science/RC-F0-V2-PRE/PREREGISTRO.md` sellado.

Calcula, por pose, las 215 features ricas del extractor v0.5 —shells RF-Score (96),
ECIF-lite (56), código poblacional por residuo (63)— reutilizando **su función**
`calcular_rich`, más las 9 baratas que ya trae el registro. Total 224.

Rigor sobre eficiencia: las poses heredadas de v1 **se recalculan** en vez de
tomarse del caché, y el resultado se compara contra el caché sellado
(`features_v05_progress.jsonl`, cuyos SHA de splits ya se verificaron). Reusar el
caché habría sido más barato; recalcular permite además **demostrar** que el
extractor sigue produciendo lo mismo. Cualquier discrepancia se reporta y aborta
el gate.

El receptor de la fuente `molflex` se resuelve al material nuevo (MF-02D/E),
porque `scripts/.work_molflex_v3/` ya no existe (PRE §5).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

DS = PROJECT_ROOT / "data" / "pose_selector_dataset"
OUT_DIR = DS / "v2"
RECORDS_V1 = DS / "records"
RECORDS_V2 = DS / "records_v2"
MATERIAL = [PROJECT_ROOT / "data" / "molflex_train_v2",
            PROJECT_ROOT / "data" / "molflex_valtest_v2"]
CACHE_V1 = DS / "features_v05_progress.jsonl"
FUENTES_V1 = ("flexible_redock", "ruta_a")
BASE_9 = ["vina_score", "pose_score_variance", "pose_score_range", "n_heavy",
          "n_contacts_4", "n_contacts_6", "contacts_per_ha_4", "n_clashes",
          "cluster_density"]


def _ruta_receptor_v2(pid: str, fuente: str, stem: str) -> Path:
    """Resolución de receptor para v2: molflex apunta al material nuevo."""
    if fuente == "molflex":
        for base in MATERIAL:
            p = base / pid / pid / "rec.pdbqt"
            if p.exists():
                return p
        return MATERIAL[0] / pid / pid / "rec.pdbqt"
    if fuente == "flexible_redock":
        return PROJECT_ROOT / "data" / "pdbbind" / "vina_redock_work" / pid / f"{pid}_rec.pdbqt"
    return PROJECT_ROOT / "tmp" / "ruta_a" / pid / stem / "rec.pdbqt"


def _features_de_pid(pid: str) -> Dict[str, Any]:
    """215 ricas por pose de un complejo. Devuelve {clave: lista}."""
    import ruta_c_fase1_5_v05 as V
    V.ruta_receptor_pdbqt = _ruta_receptor_v2  # PRE §5

    salida: Dict[str, Any] = {"pid": pid, "poses": [], "errores": []}
    for dirp, fuentes in ((RECORDS_V1, FUENTES_V1), (RECORDS_V2, None)):
        f = dirp / f"{pid}.json"
        if not f.exists():
            continue
        datos = json.loads(f.read_text(encoding="utf-8"))
        for _clave, regs in sorted(datos.get("registros", {}).items()):
            for r in regs:
                if fuentes is not None and r["source"] not in fuentes:
                    continue
                rec = V.obtener_receptor(pid, r["source"], r["file_stem"])
                if rec is None:
                    salida["errores"].append({"clave": [pid, r["source"], r["file_stem"],
                                                        r["model_idx"]],
                                              "razon": "receptor_ilegible"})
                    continue
                cl = V.coords_ligando_registro(r, pid)
                if cl is None:
                    salida["errores"].append({"clave": [pid, r["source"], r["file_stem"],
                                                        r["model_idx"]],
                                              "razon": "coords_ilegibles"})
                    continue
                coords, elems = cl
                shell, ecif, pop = V.calcular_rich(rec, coords, elems)
                salida["poses"].append({
                    "pid": pid, "source": r["source"], "file_stem": r["file_stem"],
                    "model_idx": r["model_idx"],
                    "rich": [round(float(x), 6) for x in np.concatenate([shell, ecif, pop])],
                })
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="224 features del conjunto v2")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pids = sorted({p.stem for p in RECORDS_V1.glob("*.json")} |
                  {p.stem for p in RECORDS_V2.glob("*.json")})
    if args.limite:
        pids = pids[:args.limite]
    print(f"[feat] {len(pids)} complejos", flush=True)

    filas: List[Dict[str, Any]] = []
    errores: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_features_de_pid, pids, chunksize=1), 1):
            filas.extend(r["poses"])
            errores.extend(r["errores"])
            if i % 20 == 0 or i == len(pids):
                print(f"  [{i}/{len(pids)}] {len(filas)} poses ({round(time.time() - t0)}s)",
                      flush=True)

    # ── Verificación contra el caché sellado de v1 ──
    # SOLO sobre las fuentes conservadas. La clave (pid, source, file_stem,
    # model_idx) COLISIONA entre la fuente `molflex` de v1 y la de v2: mismo
    # nombre de conformero y de modelo, pero cómputos distintos porque el
    # receptor de v1 ya no existe y v2 usa el de MF-02D/E (PRE §5). Compararlas
    # mediría esa diferencia declarada, no la reproducibilidad del extractor.
    cache: Dict[tuple, List[float]] = {}
    if CACHE_V1.exists():
        for l in CACHE_V1.read_text(encoding="utf-8").splitlines()[1:]:
            if l.strip():
                d = json.loads(l)
                if d["source"] not in FUENTES_V1:
                    continue
                cache[(d["pid"], d["source"], d["file_stem"], d["model_idx"])] = d["rich"]
    comparadas = iguales = 0
    difs: List[Dict[str, Any]] = []
    for f in filas:
        if f["source"] not in FUENTES_V1:
            continue
        k = (f["pid"], f["source"], f["file_stem"], f["model_idx"])
        if k in cache:
            comparadas += 1
            a = np.asarray(cache[k], dtype=np.float64)
            b = np.asarray(f["rich"], dtype=np.float64)
            if a.shape == b.shape and np.allclose(a, b, rtol=0, atol=1e-6):
                iguales += 1
            elif len(difs) < 5:
                d = np.abs(a - b) if a.shape == b.shape else None
                difs.append({"clave": list(k),
                             "max_abs_dif": float(d.max()) if d is not None else None,
                             "shape_cache": len(a), "shape_nuevo": len(b)})

    n_nan = sum(1 for f in filas if not np.all(np.isfinite(f["rich"])))
    with open(OUT_DIR / "features_rich_v2.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    metrics = {
        "experiment_id": "RC-F0-V2-FEATURES",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_poses": len(filas), "n_features_rich": 215, "n_features_total": 224,
        "por_fuente": dict(defaultdict(int, {s: sum(1 for f in filas if f["source"] == s)
                                             for s in {x["source"] for x in filas}})),
        "verificacion_cache_v1": {
            "criterio": "las poses heredadas de v1 recalculadas deben coincidir con el cache sellado (atol 1e-6)",
            "comparadas": comparadas, "iguales": iguales,
            "discrepancias": comparadas - iguales, "ejemplos": difs,
            "pass": comparadas > 0 and comparadas == iguales,
        },
        "errores": {"n": len(errores), "ejemplos": errores[:10]},
        "gates": {
            "G6_completitud": {"criterio": "cero poses sin features y cero NaN",
                               "n_errores": len(errores), "n_nan": n_nan,
                               "pass": not errores and n_nan == 0},
        },
    }
    metrics["gates"]["G2b_reproduccion_extractor"] = metrics["verificacion_cache_v1"]
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"
    (OUT_DIR / "metrics_features_v2.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print(f"\n[feat] decision {metrics['decision']} | {len(filas)} poses")
    print(f"  verificacion contra cache v1: {iguales}/{comparadas} identicas")
    print(f"  errores: {len(errores)} | NaN: {n_nan}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
