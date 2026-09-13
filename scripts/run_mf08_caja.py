#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf08_caja.py — MF-08: ¿una caja generosa admite subsitios competidores?

Prerrequisito formal: `scripts/artifacts_science/MF-08-PRE/PREREGISTRO.md` sellado.

Brazos: `B20` (intervención) y `B30` (falsación). `B25` es el material ya
computado por MF-02D y no se recomputa.

El tamaño de caja se fija parcheando `molflex.BOX_SIZE` **dentro del worker**:
en Windows `ProcessPoolExecutor` usa spawn y cada proceso reimporta el módulo,
así que un parcheo en el padre no llegaría al hijo (incidencia de MF-02E).
`molflex.py` no se modifica: sigue siendo el asset sellado de MF-02D.
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

EXPERIMENT_ID = "MF-08"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
MATERIAL = PROJECT_ROOT / "data" / "molflex_caja"
MF02D_POCKET = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02D" / "pocket_frame.jsonl"
COHORTE_JSON = OUT_DIR / "cohorte.json"
UMBRAL_A = 2.0
BRAZOS = {"B20": 20.0, "B30": 30.0, "B_ADAPT": None}  # None = adaptativa por ligando


def caja_adaptativa(pid: str) -> float:
    """Lado = dimension maxima del ligando + 4 A de margen de solvatacion por lado.
    Criterio de `moldesign-app/docs/propuestas_de_mejora.md` seccion 3 (jul-2026),
    anterior a estos resultados: si la dimension del ligando mas el margen supera
    la caja, Vina recorta la estructura."""
    import numpy as np
    import molflex as mf
    m = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    cf = m.GetConformer(0)
    P = np.array([[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
                  for i, a in enumerate(m.GetAtoms()) if a.GetAtomicNum() > 1])
    return float((P.max(0) - P.min(0)).max()) + 8.0
N_CONF, TOP_K = 30, 3


def _una(job: Dict[str, Any]) -> Dict[str, Any]:
    """Una corrida de MolFlex con la caja del brazo. Parcheo dentro del worker."""
    import molflex as mf
    mf.BOX_SIZE = BRAZOS[job["brazo"]] or caja_adaptativa(job["pid"])

    pid, brazo = job["pid"], job["brazo"]
    work = MATERIAL / brazo / pid
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fila: Dict[str, Any] = {"pid": pid, "brazo": brazo, "box": mf.BOX_SIZE,
                            "estrato": job["estrato"]}
    try:
        res = mf.ejecutar_complejo(pid, N_CONF, TOP_K, 1, str(work), True,
                                   f"{EXPERIMENT_ID}-{brazo}")
    except Exception as e:
        fila.update({"ok": False, "reason": f"EXCEPCION: {str(e)[-160:]}",
                     "wall_s": round(time.time() - t0, 2)})
        return fila
    fila["wall_s"] = round(time.time() - t0, 2)
    fila["ok"] = bool(res.get("ok"))
    fila["reason"] = res.get("reason")
    fila["n_conf_efectivo"] = res.get("n_conf")

    # Oráculo en marco de pocket sobre TODAS las poses dockeadas
    w = work / pid
    mejor = None
    n_poses = 0
    try:
        crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
        raw = json.loads((w / "index_map.json").read_text(encoding="utf-8"))
        s2m = {int(s): int(m) for s, m in raw}
        for f in sorted(w.glob("conf*.out.pdbqt")):
            for _sc, at in mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace")):
                c = mf.coords_pose_a_por_mol(at, s2m)
                if not c:
                    continue
                n_poses += 1
                rp = mf.rmsd_pose_pocket(crystal, c)
                if rp is not None and (mejor is None or rp < mejor):
                    mejor = rp
    except Exception as e:
        fila["error_oraculo"] = str(e)[-160:]
    fila["n_poses"] = n_poses
    fila["oraculo_pocket"] = round(mejor, 3) if mejor is not None else None
    fila["exito"] = bool(mejor is not None and mejor <= UMBRAL_A)
    return fila


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-08: efecto del tamano de caja")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--brazos", nargs="*", default=list(BRAZOS))
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coh = json.loads(COHORTE_JSON.read_text(encoding="utf-8"))
    cohorte = coh["cohorte_colocacion"]
    control = coh["control_cubiertos"]
    if args.limite:
        cohorte, control = cohorte[:args.limite], control[:max(1, args.limite // 3)]
    print(f"[MF-08] {len(cohorte)} colocacion-dominados + {len(control)} control | "
          f"brazos {args.brazos} | prediccion declarada: {coh['n_prediccion']}/{len(coh['cohorte_colocacion'])}",
          flush=True)

    jobs = []
    for brazo in args.brazos:
        jobs += [{"pid": p, "brazo": brazo, "estrato": "COLOCACION"} for p in cohorte]
        jobs += [{"pid": p, "brazo": brazo, "estrato": "CONTROL"} for p in control]
    print(f"[MF-08] {len(jobs)} corridas con {args.workers} procesos", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, f in enumerate(ex.map(_una, jobs, chunksize=1), 1):
            filas.append(f)
            if i % 5 == 0 or i == len(jobs):
                rec = sum(1 for x in filas
                          if x.get("exito") and x["brazo"] == "B20" and x["estrato"] == "COLOCACION")
                print(f"  [{i}/{len(jobs)}] B20 recupera {rec} ({round(time.time() - t0)}s)", flush=True)

    # B25: material ya computado por MF-02D
    b25 = {}
    for l in MF02D_POCKET.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            if r.get("oraculo_generacion_pocket") is not None:
                b25[r["pid"]] = r["oraculo_generacion_pocket"]

    def cobertura(brazo: str, estrato: str) -> Dict[str, Any]:
        pids = cohorte if estrato == "COLOCACION" else control
        if brazo == "B25":
            vals = {p: b25.get(p) for p in pids}
        else:
            vals = {f["pid"]: f.get("oraculo_pocket") for f in filas
                    if f["brazo"] == brazo and f["estrato"] == estrato}
        ok = [p for p, v in vals.items() if v is not None and v <= UMBRAL_A]
        med = [v for v in vals.values() if v is not None]
        return {"n": len(pids), "cubiertos": len(ok), "pids": sorted(ok),
                "cobertura": round(len(ok) / len(pids), 4) if pids else None,
                "mediana_oraculo": round(median(med), 3) if med else None}

    brazos_todos = ["B_ADAPT", "B20", "B25", "B30"]
    resumen = {b: {e: cobertura(b, e) for e in ("COLOCACION", "CONTROL")} for b in brazos_todos}
    rec20 = resumen["B20"]["COLOCACION"]["cubiertos"]
    ctl25 = set(resumen["B25"]["CONTROL"]["pids"])
    ctl20 = set(resumen["B20"]["CONTROL"]["pids"])
    perdidos = sorted(ctl25 - ctl20)
    n_ok = sum(1 for f in filas if f.get("ok"))
    c20 = resumen["B20"]["COLOCACION"]["cobertura"]
    c25 = resumen["B25"]["COLOCACION"]["cobertura"]
    c30 = resumen["B30"]["COLOCACION"]["cobertura"] if "B30" in args.brazos else None

    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"brazos": {b: BRAZOS.get(b, 25.0) for b in brazos_todos},
                   "n_conf": N_CONF, "top_k": TOP_K, "umbral_A": UMBRAL_A,
                   "metrica": "min rmsd_pose_pocket sobre todas las poses dockeadas",
                   "nota_B25": "material de MF-02D, no recomputado"},
        "cohorte": {"colocacion": len(cohorte), "control": len(control),
                    "excluidos_no_caben": coh["excluidos_no_caben_20A"],
                    "prediccion_decoy_excluido_20A": coh["prediccion_decoy_excluido_20A"]},
        "n_corridas": len(filas), "n_ok": n_ok,
        "resumen_por_brazo": resumen,
        "coste": {b: {"mediana_s": round(median([f["wall_s"] for f in filas if f["brazo"] == b]), 1)}
                  for b in args.brazos},
    }
    cad = resumen["B_ADAPT"]["COLOCACION"]["cobertura"] if "B_ADAPT" in args.brazos else None
    ctlad = set(resumen["B_ADAPT"]["CONTROL"]["pids"]) if "B_ADAPT" in args.brazos else set()
    perdidos_ad = sorted(ctl25 - ctlad)
    metrics["gates"] = {
        "G1_validez": {"criterio": ">=95% completan sin error",
                       "tasa": round(n_ok / len(filas), 4) if filas else 0.0,
                       "pass": bool(filas and n_ok / len(filas) >= 0.95)},
        "G2_recuperacion": {
            "criterio": "B_ADAPT recupera >=7 de los 33 dominados por colocacion",
            "recuperados": resumen["B_ADAPT"]["COLOCACION"]["cubiertos"] if "B_ADAPT" in args.brazos else None,
            "de": len(cohorte), "B20_referencia": rec20,
            "pass": bool("B_ADAPT" in args.brazos
                         and resumen["B_ADAPT"]["COLOCACION"]["cubiertos"] >= 7)},
        "G3_monotonia": {
            "criterio": "cobertura B_ADAPT >= B20 >= B25 >= B30 (mecanismo: menos margen de deslizamiento, mas cobertura)",
            "B_ADAPT": cad, "B20": c20, "B25": c25, "B30": c30,
            "pass": (None not in (cad, c20, c25, c30) and cad >= c20 >= c25 >= c30)},
        "G4_no_regresion": {"criterio": "B_ADAPT pierde como mucho 1 del control",
                            "perdidos": perdidos_ad, "perdidos_B20": perdidos,
                            "pass": len(perdidos_ad) <= 1},
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

    print(f"\n[MF-08] decision {metrics['decision']}")
    for b in brazos_todos:
        r = resumen[b]["COLOCACION"]
        rc = resumen[b]["CONTROL"]
        print(f"  {b}: cohorte {r['cubiertos']}/{r['n']} ({r['cobertura']:.1%}, mediana "
              f"{r['mediana_oraculo']} A) | control {rc['cubiertos']}/{rc['n']}")
    for k, g in metrics["gates"].items():
        print(f"  {k}: {'PASS' if g['pass'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
