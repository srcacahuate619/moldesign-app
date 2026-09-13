#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf02b_apply_molflex.py — MF-02B: aplicar MolFlex a la cohorte que nunca lo recibió.

Prerrequisito formal: `scripts/artifacts_science/MF-02-PRE/PREREGISTRO.md` sellado.

Contexto (declarado en el PRE §5): MolFlex se aplicó a 13 de los 116 complejos de
train. En los otros 103 la cobertura del oráculo es la de `flexible_redock`. Este
experimento corre el pipeline MolFlex **congelado** sobre los 38 sin cobertura y
mide cuánta cobertura recupera, y a qué coste.

Brazos: A8 (exhaustiveness=8, protocolo congelado, primario) y A32 (32, solo para
el Pareto). Única variable: el presupuesto de búsqueda, vía la variable de entorno
`MOLFLEX_EXHAUSTIVENESS` que `molflex.py` emite en provenance.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ID = "MF-02B"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
WORK = OUT_DIR / "_work"
POSES_TRAIN = PROJECT_ROOT / "data" / "pose_selector_dataset" / "poses_train.jsonl"

N_CONF = 30
TOP_K = 3
UMBRAL_A = 2.0
N_CONTROL = 12
SEED_MUESTREO = 42
BRAZOS = {"A8": 8, "A32": 32}
TIMEOUT_S = 5400


def cohorte() -> Dict[str, List[str]]:
    por = defaultdict(list)
    for l in POSES_TRAIN.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            por[r["pid"]].append(r)
    sin = sorted(p for p, v in por.items() if min(x["rmsd"] for x in v) > UMBRAL_A)
    con = sorted(p for p, v in por.items() if min(x["rmsd"] for x in v) <= UMBRAL_A)
    control = sorted(random.Random(SEED_MUESTREO).sample(con, N_CONTROL))
    mejor = {p: round(min(x["rmsd"] for x in v), 3) for p, v in por.items()}
    fuentes = {p: sorted({x["source"] for x in v}) for p, v in por.items()}
    return {"sin_cobertura": sin, "control": control, "mejor_dataset": mejor,
            "fuentes_dataset": fuentes}


def _una(job: Dict[str, Any]) -> Dict[str, Any]:
    pid, brazo, sufijo = job["pid"], job["brazo"], job.get("sufijo", "")
    exh = BRAZOS[brazo]
    out_json = WORK / f"{pid}_{brazo}{sufijo}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["MOLFLEX_EXHAUSTIVENESS"] = str(exh)
    cmd = [sys.executable, "-X", "utf8", str(PROJECT_ROOT / "scripts" / "molflex.py"),
           "--pdb-id", pid, "--n-conf", str(N_CONF), "--top-k", str(TOP_K),
           "--cpu", "1", "--out-json", str(out_json),
           "--experiment-id", f"{EXPERIMENT_ID}-{brazo}"]
    t0 = time.time()
    fila: Dict[str, Any] = {"pid": pid, "brazo": brazo, "exhaustiveness": exh,
                            "estrato": job["estrato"]}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S,
                           env=env, cwd=str(PROJECT_ROOT))
        fila["rc"] = r.returncode
    except subprocess.TimeoutExpired:
        fila["rc"] = -9
    fila["wall_s"] = round(time.time() - t0, 2)

    if not out_json.exists():
        fila["ok"] = False
        fila["reason"] = "SIN_SALIDA"
        return fila
    try:
        res = json.loads(out_json.read_text(encoding="utf-8"))
    except Exception as e:
        fila["ok"] = False
        fila["reason"] = f"JSON_ILEGIBLE: {str(e)[-80:]}"
        return fila

    rmsds = [r.get("rmsd_to_crystal") for r in res.get("top_k_relaxed", [])
             if r.get("rmsd_to_crystal") is not None]
    if res.get("rmsd_best_to_crystal") is not None:
        rmsds.append(res["rmsd_best_to_crystal"])
    fila.update({
        "ok": bool(res.get("ok")),
        "reason": res.get("reason"),
        "n_conf_efectivo": res.get("n_conf"),
        "ensemble_min_rmsd": res.get("ensemble_min_rmsd"),
        "rigid_best_score": res.get("rigid_best"),
        "rmsd_entregado": round(min(rmsds), 3) if rmsds else None,
        "n_poses_entregadas": len(res.get("top_k_relaxed", [])),
        "time_fase1": res.get("time_fase1"),
        "time_fase2": res.get("time_fase2"),
        "time_fase3": res.get("time_fase3"),
        "total_time_s": res.get("total_time_s"),
    })
    fila["exito"] = bool(fila["rmsd_entregado"] is not None
                         and fila["rmsd_entregado"] <= UMBRAL_A)
    return fila


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-02B: aplicar MolFlex a la cohorte sin cobertura")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None, help="smoke test")
    ap.add_argument("--brazos", nargs="*", default=list(BRAZOS), help="brazos a ejecutar")
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    coh = cohorte()
    sin, control = coh["sin_cobertura"], coh["control"]
    if args.limite:
        sin, control = sin[:args.limite], control[:max(1, args.limite // 3)]
    print(f"[MF-02B] cohorte: {len(sin)} sin cobertura + {len(control)} control | "
          f"brazos {args.brazos}", flush=True)

    jobs = []
    for brazo in args.brazos:
        for pid in sin:
            jobs.append({"pid": pid, "brazo": brazo, "estrato": "SIN_COBERTURA"})
        for pid in control:
            jobs.append({"pid": pid, "brazo": brazo, "estrato": "CONTROL"})
    print(f"[MF-02B] {len(jobs)} corridas de MolFlex con {args.workers} procesos", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, f in enumerate(ex.map(_una, jobs, chunksize=1), 1):
            filas.append(f)
            if i % 5 == 0 or i == len(jobs):
                rec = sum(1 for x in filas
                          if x.get("exito") and x["estrato"] == "SIN_COBERTURA" and x["brazo"] == "A8")
                print(f"  [{i}/{len(jobs)}] recuperados A8={rec} ({round(time.time() - t0)}s)",
                      flush=True)

    # G4: determinismo sobre 2 complejos del brazo primario
    det_ids = sin[:2]
    det_jobs = [{"pid": p, "brazo": "A8", "estrato": "SIN_COBERTURA", "sufijo": "_det"}
                for p in det_ids if "A8" in args.brazos]
    determinismo = []
    if det_jobs:
        print(f"[MF-02B] determinismo: repitiendo {len(det_jobs)} corridas", flush=True)
        with ProcessPoolExecutor(max_workers=len(det_jobs)) as ex:
            for rep in ex.map(_una, det_jobs, chunksize=1):
                orig = next((f for f in filas if f["pid"] == rep["pid"] and f["brazo"] == "A8"), None)
                determinismo.append({
                    "pid": rep["pid"],
                    "rmsd_original": orig.get("rmsd_entregado") if orig else None,
                    "rmsd_repeticion": rep.get("rmsd_entregado"),
                    "score_original": orig.get("rigid_best_score") if orig else None,
                    "score_repeticion": rep.get("rigid_best_score"),
                    "identico": bool(orig and orig.get("rmsd_entregado") == rep.get("rmsd_entregado")
                                     and orig.get("rigid_best_score") == rep.get("rigid_best_score")),
                })

    escribir(filas, coh, sin, control, determinismo, args, t0)
    return 0


def escribir(filas, coh, sin, control, determinismo, args, t0):
    from statistics import median

    por_pid: Dict[str, Dict[str, Any]] = defaultdict(dict)
    for f in filas:
        por_pid[f["pid"]][f["brazo"]] = f

    resumen = []
    for pid, brazos in por_pid.items():
        estrato = "SIN_COBERTURA" if pid in sin else "CONTROL"
        fila = {"pid": pid, "estrato": estrato,
                "mejor_dataset": coh["mejor_dataset"].get(pid),
                "fuentes_dataset": coh["fuentes_dataset"].get(pid)}
        for brazo, f in brazos.items():
            fila[brazo] = {"rmsd_entregado": f.get("rmsd_entregado"),
                           "exito": f.get("exito"), "ok": f.get("ok"),
                           "ensemble_min_rmsd": f.get("ensemble_min_rmsd"),
                           "wall_s": f.get("wall_s")}
        # Unión con el dataset: la fuente nueva se AÑADE, nunca sustituye
        nuevos = [f.get("rmsd_entregado") for f in brazos.values()
                  if f.get("rmsd_entregado") is not None]
        base = coh["mejor_dataset"].get(pid)
        fila["mejor_union"] = round(min([base] + nuevos), 3) if nuevos and base is not None else base
        fila["cubierto_antes"] = bool(base is not None and base <= UMBRAL_A)
        fila["cubierto_despues"] = bool(fila["mejor_union"] is not None
                                        and fila["mejor_union"] <= UMBRAL_A)
        resumen.append(fila)

    def _rec(estrato, brazo):
        sub = [r for r in resumen if r["estrato"] == estrato and brazo in r]
        return sum(1 for r in sub if r[brazo]["exito"]), len(sub)

    rec_a8, n_sin = _rec("SIN_COBERTURA", "A8") if "A8" in args.brazos else (0, len(sin))
    rec_a32, _ = _rec("SIN_COBERTURA", "A32") if "A32" in args.brazos else (0, len(sin))
    ctl_a8, n_ctl = _rec("CONTROL", "A8") if "A8" in args.brazos else (0, len(control))
    n_ok = sum(1 for f in filas if f.get("ok"))
    perdidos = [r["pid"] for r in resumen
                if r["cubierto_antes"] and not r["cubierto_despues"]]

    def _coste(brazo):
        v = [f["wall_s"] for f in filas if f["brazo"] == brazo and f.get("ok")]
        return {"n": len(v), "mediana_s": round(median(v), 1) if v else None,
                "total_s": round(sum(v), 1) if v else None}

    cobertura_antes = 78
    cobertura_despues = cobertura_antes + rec_a8
    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"n_conf": N_CONF, "top_k": TOP_K, "umbral_A": UMBRAL_A,
                   "brazos": {b: BRAZOS[b] for b in args.brazos},
                   "seed_muestreo_control": SEED_MUESTREO,
                   "metrica": "mejor RMSD entre las poses ENTREGADAS (top-K relajadas)"},
        "cohorte": {"sin_cobertura": len(sin), "control": len(control),
                    "control_pids": control},
        "n_corridas": len(filas), "n_ok": n_ok,
        "recuperados_A8": rec_a8, "de_sin_cobertura": n_sin,
        "recuperados_A32": rec_a32,
        "control_A8_entrega": ctl_a8, "control_n": n_ctl,
        "cobertura_oraculo_antes": round(cobertura_antes / 116, 4),
        "cobertura_oraculo_despues_A8": round(cobertura_despues / 116, 4),
        "coste": {b: _coste(b) for b in args.brazos},
        "determinismo": determinismo,
    }
    metrics["gates"] = {
        "G1_validez": {"criterio": ">=95% de corridas completan sin error",
                       "tasa": round(n_ok / len(filas), 4) if filas else 0.0,
                       "pass": bool(filas and n_ok / len(filas) >= 0.95)},
        "G2_recuperacion": {"criterio": "A8 entrega pose <=2.0 A en >=10 de los 38 sin cobertura",
                            "recuperados": rec_a8, "de": n_sin, "pass": rec_a8 >= 10},
        "G3_no_regresion": {"criterio": "la union no reduce la cobertura de ningun complejo",
                            "perdidos": perdidos, "pass": not perdidos},
        "G4_determinismo": {"criterio": "misma semilla -> mismo RMSD y mismo score",
                            "n": len(determinismo),
                            "identicos": sum(1 for d in determinismo if d["identico"]),
                            "pass": bool(determinismo) and all(d["identico"] for d in determinismo)},
        "G5_coste": {"criterio": "descriptivo, sin umbral", "pass": True},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"

    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in sorted(resumen, key=lambda x: (x["estrato"], x["pid"])):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "corridas.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            if not r.get("ok"):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[MF-02B] decision {metrics['decision']}")
    print(f"  A8 recupera {rec_a8}/{n_sin} sin cobertura | control entrega {ctl_a8}/{n_ctl}")
    print(f"  cobertura del oraculo: {cobertura_antes}/116 -> {cobertura_despues}/116 "
          f"({metrics['cobertura_oraculo_antes']:.1%} -> {metrics['cobertura_oraculo_despues_A8']:.1%})")
    if "A32" in args.brazos:
        print(f"  A32 recupera {rec_a32}/{n_sin} | coste {metrics['coste']}")


if __name__ == "__main__":
    sys.exit(main())
