#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf02e_val_test.py — MF-02E: generación de registro en val y test.

Prerrequisito formal: `scripts/artifacts_science/RC-F0-V2-PRE/PREREGISTRO.md` §3.

MF-02D dejó los 116 de train con la salida del generador. Aplicar MolFlex solo a
train pondría train y val/test en regímenes distintos —número de candidatos por
complejo, distribución de `cluster_density`, dificultad del ranking— y un
selector medido así mediría el cambio de régimen, no su capacidad.

Reutiliza sin modificarlo el runner sellado de MF-02D (`_una`): protocolo
byte-idéntico (`n_conf=30`, caja 25 A, `exhaustiveness=8`, `top_k=3`, `cpu=1`,
semillas 42, `--keep`). Solo cambia el directorio de material y la cohorte.

Generar poses en val/test NO es fuga: no se ajusta ningún parámetro ni se mira
ninguna etiqueta para decidir. `D-RC-CONFIRM` no se toca.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_mf02d_generacion_registro as D  # noqa: E402  (runner sellado de MF-02D)

EXPERIMENT_ID = "MF-02E"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
DS = PROJECT_ROOT / "data" / "pose_selector_dataset"


MATERIAL_DIR = PROJECT_ROOT / "data" / "molflex_valtest_v2"
RESUMEN_DIR = OUT_DIR / "_resumen"


def _una_valtest(pid: str) -> Dict[str, Any]:
    """Worker spawn-safe: en Windows cada proceso REIMPORTA el módulo, así que
    reasignar `D.POSES_DIR` en el padre no llega al hijo. La redirección tiene
    que ocurrir dentro del worker, antes de llamar al runner sellado."""
    D.POSES_DIR = MATERIAL_DIR
    D.RESUMEN_DIR = RESUMEN_DIR
    MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    RESUMEN_DIR.mkdir(parents=True, exist_ok=True)
    return D._una(pid)


def pids_de(split: str) -> List[str]:
    p = DS / f"poses_{split}.jsonl"
    return sorted({json.loads(l)["pid"] for l in p.read_text(encoding="utf-8").splitlines() if l.strip()})


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-02E: MolFlex congelado en val y test")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--splits", nargs="*", default=["val", "test"])
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Redirige el material del runner de MF-02D sin tocar su código
    MATERIAL_DIR.mkdir(parents=True, exist_ok=True)
    RESUMEN_DIR.mkdir(parents=True, exist_ok=True)

    cohorte: List[Dict[str, str]] = []
    for s in args.splits:
        for pid in pids_de(s):
            cohorte.append({"pid": pid, "split": s})
    if args.limite:
        cohorte = cohorte[:args.limite]
    por_split = {s: sum(1 for c in cohorte if c["split"] == s) for s in args.splits}
    print(f"[MF-02E] cohorte: {len(cohorte)} complejos {por_split} | "
          f"material en {MATERIAL_DIR}", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, f in enumerate(ex.map(_una_valtest, [c["pid"] for c in cohorte], chunksize=1), 1):
            f["split"] = next(c["split"] for c in cohorte if c["pid"] == f["pid"])
            filas.append(f)
            if i % 5 == 0 or i == len(cohorte):
                ok = sum(1 for x in filas if x.get("exito"))
                print(f"  [{i}/{len(cohorte)}] entregan <=2A (alineado): {ok} "
                      f"({round(time.time() - t0)}s)", flush=True)

    n_ok = sum(1 for f in filas if f.get("ok"))
    sin_disco = [f["pid"] for f in filas if not f.get("n_pdbqt_en_disco")]
    costes = [f["wall_s"] for f in filas if f.get("ok")]
    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"protocolo": "identico a MF-02D (runner sellado, reutilizado sin modificar)",
                   "n_conf": D.N_CONF, "top_k": D.TOP_K, "exhaustiveness": D.EXH,
                   "material": str(MATERIAL_DIR.relative_to(PROJECT_ROOT))},
        "cohorte": por_split, "n_complejos": len(filas), "n_ok": n_ok,
        "complejos_sin_pose_en_disco": sin_disco,
        "coste": {"n": len(costes), "mediana_s": round(median(costes), 1) if costes else None,
                  "total_s": round(sum(costes), 1) if costes else None},
        "nota_metrica": ("Las cifras de exito de este runner usan el RMSD ALINEADO heredado de "
                         "molflex y NO son el resultado: la cobertura se mide en marco de pocket "
                         "sobre el material, igual que en MF-02D."),
        "nota_cuarentena": "Generacion con protocolo congelado; no se ajusta nada ni se miran etiquetas. D-RC-CONFIRM no se toca.",
    }
    metrics["gates"] = {
        "G1_validez": {"criterio": ">=95% completan sin error",
                       "tasa": round(n_ok / len(filas), 4) if filas else 0.0,
                       "pass": bool(filas and n_ok / len(filas) >= 0.95)},
        "G2_material": {"criterio": "todo complejo deja sus pdbqt de pose en disco",
                        "sin_disco": sin_disco, "pass": not sin_disco},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"

    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "corridas.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            if not r.get("ok"):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[MF-02E] decision {metrics['decision']} | {n_ok}/{len(filas)} ok | "
          f"coste mediana {metrics['coste']['mediana_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
