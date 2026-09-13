#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf02d_generacion_registro.py — MF-02D: generación de registro de los 116 de train.

Prerrequisito formal: `scripts/artifacts_science/MF-02D-PRE/PREREGISTRO.md` sellado.

Aplica el pipeline MolFlex **congelado** a los 116 complejos de train **conservando
las poses en disco**. MF-02B demostró el efecto (cobertura 67.2% -> 93.1%) pero
corrió en directorios temporales: sus poses se perdieron y solo quedó el resumen.
Sin coordenadas no se puede reconstruir el dataset del selector ni re-puntuar la
unión con una función común, que es todo lo que viene después.

Corre los 116, no solo los 66 que faltaban: el pipeline es determinista con semilla
fija, de modo que **debe reproducir los 30 de 38 de MF-02B**. Esa reproducción es
un gate, no un subproducto.

Protocolo por complejo, idéntico a MF-02B: `n_conf=30`, caja 25 A,
`exhaustiveness=8`, `num_modes=9`, `top_k=3`, `cpu=1`, semillas 42, más
`--keep --out-dir` para conservar los artefactos de pose.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ID = "MF-02D"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
POSES_DIR = PROJECT_ROOT / "data" / "molflex_train_v2"      # material, fuera del arbol de artefactos
RESUMEN_DIR = OUT_DIR / "_resumen"
POSES_TRAIN = PROJECT_ROOT / "data" / "pose_selector_dataset" / "poses_train.jsonl"
MF02B_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02B"

N_CONF, TOP_K, EXH, UMBRAL_A = 30, 3, 8, 2.0
TIMEOUT_S = 5400


def cohorte() -> Dict[str, Any]:
    por = defaultdict(list)
    for l in POSES_TRAIN.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            por[r["pid"]].append(r)
    return {
        "pids": sorted(por),
        "mejor_dataset": {p: round(min(x["rmsd"] for x in v), 3) for p, v in por.items()},
        "fuentes": {p: sorted({x["source"] for x in v}) for p, v in por.items()},
    }


def _una(pid: str) -> Dict[str, Any]:
    out_json = RESUMEN_DIR / f"{pid}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    work = POSES_DIR / pid
    work.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["MOLFLEX_EXHAUSTIVENESS"] = str(EXH)
    cmd = [sys.executable, "-X", "utf8", str(PROJECT_ROOT / "scripts" / "molflex.py"),
           "--pdb-id", pid, "--n-conf", str(N_CONF), "--top-k", str(TOP_K), "--cpu", "1",
           "--out-dir", str(work), "--keep", "--out-json", str(out_json),
           "--experiment-id", EXPERIMENT_ID]
    t0 = time.time()
    fila: Dict[str, Any] = {"pid": pid}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S,
                           env=env, cwd=str(PROJECT_ROOT))
        fila["rc"] = r.returncode
    except subprocess.TimeoutExpired:
        fila["rc"] = -9
    fila["wall_s"] = round(time.time() - t0, 2)

    if not out_json.exists():
        fila.update({"ok": False, "reason": "SIN_SALIDA"})
        return fila
    res = json.loads(out_json.read_text(encoding="utf-8"))
    poses = [p for p in res.get("top_k_relaxed", []) if p.get("rmsd_to_crystal") is not None]
    rmsds = [p["rmsd_to_crystal"] for p in poses]
    if res.get("rmsd_best_to_crystal") is not None:
        rmsds.append(res["rmsd_best_to_crystal"])
    n_pdbqt = len(list((work / pid).glob("conf*.out.pdbqt"))) if (work / pid).exists() else 0
    fila.update({
        "ok": bool(res.get("ok")),
        "reason": res.get("reason"),
        "n_conf_efectivo": res.get("n_conf"),
        "ensemble_min_rmsd": res.get("ensemble_min_rmsd"),
        "rmsd_entregado": round(min(rmsds), 3) if rmsds else None,
        "poses_entregadas": [{"conf_id": p.get("conf_id"), "rigid_score": p.get("rigid_score"),
                              "relaxed_score": p.get("relaxed_score"),
                              "rmsd_to_crystal": p.get("rmsd_to_crystal")} for p in poses],
        "n_pdbqt_en_disco": n_pdbqt,
        "total_time_s": res.get("total_time_s"),
    })
    fila["exito"] = bool(fila["rmsd_entregado"] is not None and fila["rmsd_entregado"] <= UMBRAL_A)
    return fila


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-02D: generacion de registro de los 116 de train")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    POSES_DIR.mkdir(parents=True, exist_ok=True)
    coh = cohorte()
    pids = coh["pids"][:args.limite] if args.limite else coh["pids"]
    print(f"[MF-02D] {len(pids)} complejos de train, poses conservadas en {POSES_DIR}", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, f in enumerate(ex.map(_una, pids, chunksize=1), 1):
            filas.append(f)
            if i % 5 == 0 or i == len(pids):
                ok = sum(1 for x in filas if x.get("exito"))
                print(f"  [{i}/{len(pids)}] entregan <=2A: {ok} ({round(time.time() - t0)}s)",
                      flush=True)

    # ── Reproducción de MF-02B (gate) ──
    b_sin = {}
    if (MF02B_DIR / "per_complex.jsonl").exists():
        for r in (json.loads(l) for l in (MF02B_DIR / "per_complex.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()):
            if r["estrato"] == "SIN_COBERTURA":
                b_sin[r["pid"]] = bool(r["A8"]["exito"])
    ahora = {f["pid"]: bool(f.get("exito")) for f in filas}
    comparables = [p for p in b_sin if p in ahora]
    coincidencias = [p for p in comparables if b_sin[p] == ahora[p]]
    discrepancias = [{"pid": p, "mf02b": b_sin[p], "mf02d": ahora[p]}
                     for p in comparables if b_sin[p] != ahora[p]]

    resumen = []
    for pid in coh["pids"]:
        f = next((x for x in filas if x["pid"] == pid), None)
        base = coh["mejor_dataset"].get(pid)
        nuevo = f.get("rmsd_entregado") if f else None
        union = min([x for x in (base, nuevo) if x is not None], default=None)
        resumen.append({
            "pid": pid, "mejor_dataset": base, "mejor_molflex": nuevo,
            "mejor_union": round(union, 3) if union is not None else None,
            "cubierto_antes": bool(base is not None and base <= UMBRAL_A),
            "cubierto_despues": bool(union is not None and union <= UMBRAL_A),
            "n_pdbqt_en_disco": f.get("n_pdbqt_en_disco") if f else 0,
            "poses_entregadas": f.get("poses_entregadas") if f else [],
            "fuentes_dataset": coh["fuentes"].get(pid),
        })

    antes = sum(1 for r in resumen if r["cubierto_antes"])
    despues = sum(1 for r in resumen if r["cubierto_despues"])
    perdidos = [r["pid"] for r in resumen if r["cubierto_antes"] and not r["cubierto_despues"]]
    sin_disco = [r["pid"] for r in resumen if r["n_pdbqt_en_disco"] == 0]
    n_ok = sum(1 for f in filas if f.get("ok"))
    costes = [f["wall_s"] for f in filas if f.get("ok")]

    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"n_conf": N_CONF, "top_k": TOP_K, "exhaustiveness": EXH,
                   "umbral_A": UMBRAL_A, "poses_dir": str(POSES_DIR.relative_to(PROJECT_ROOT)),
                   "protocolo": "molflex congelado docs/40 con --keep"},
        "n_complejos": len(pids), "n_ok": n_ok,
        "cobertura_antes": {"n": antes, "de": len(resumen), "frac": round(antes / len(resumen), 4)},
        "cobertura_despues": {"n": despues, "de": len(resumen), "frac": round(despues / len(resumen), 4)},
        "reproduccion_mf02b": {"comparables": len(comparables), "coincidencias": len(coincidencias),
                               "discrepancias": discrepancias},
        "complejos_sin_pose_en_disco": sin_disco,
        "coste": {"n": len(costes), "mediana_s": round(median(costes), 1) if costes else None,
                  "total_s": round(sum(costes), 1) if costes else None},
        "fuera_de_alcance": ("No reconstruye poses_train.jsonl con features ni evalua ningun "
                             "selector: produce el material y mide la cobertura."),
    }
    metrics["gates"] = {
        "G1_validez": {"criterio": ">=95% completan sin error",
                       "tasa": round(n_ok / len(filas), 4) if filas else 0.0,
                       "pass": bool(filas and n_ok / len(filas) >= 0.95)},
        "G2_material": {"criterio": "todo complejo con exito deja sus pdbqt de pose en disco",
                        "sin_disco": sin_disco, "pass": not sin_disco},
        "G3_reproduccion": {"criterio": "reproduce la decision de MF-02B en los 38 sin cobertura",
                            "comparables": len(comparables), "coincidencias": len(coincidencias),
                            "pass": bool(comparables) and not discrepancias},
        "G4_no_regresion": {"criterio": "la union no reduce la cobertura de ningun complejo",
                            "perdidos": perdidos, "pass": not perdidos},
        "G5_cobertura": {"criterio": "cobertura de train con la union >= 90%",
                         "cobertura": metrics["cobertura_despues"]["frac"],
                         "pass": metrics["cobertura_despues"]["frac"] >= 0.90},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"

    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in resumen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "corridas.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            if not r.get("ok"):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[MF-02D] decision {metrics['decision']}")
    print(f"  cobertura del oraculo: {antes}/{len(resumen)} -> {despues}/{len(resumen)} "
          f"({metrics['cobertura_antes']['frac']:.1%} -> {metrics['cobertura_despues']['frac']:.1%})")
    print(f"  reproduccion de MF-02B: {len(coincidencias)}/{len(comparables)} "
          f"| discrepancias: {discrepancias or 'ninguna'}")
    print(f"  coste mediana {metrics['coste']['mediana_s']} s/complejo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
