#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf02f_reinicios.py — MF-02F: los confórmeros como reinicios de búsqueda.

Prerrequisito formal: `scripts/artifacts_science/MF-02F-PRE/PREREGISTRO.md` sellado.

Brazos K30 / K60 / K90 por **prefijos anidados** de un único ensemble de 90: se
verificó que el ensemble de 30 es prefijo byte-idéntico del de 90, así que K30 es
el material ya sellado de MF-02D y sólo se dockean los confórmeros posteriores al
prefijo.

Advertencia declarada en el prerregistro §4: con prefijos anidados la cobertura
sólo puede subir, de modo que la monotonía es **tautológica y no es evidencia**;
lo informativo es la magnitud y el coste por complejo recuperado.
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

EXPERIMENT_ID = "MF-02F"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
MATERIAL = PROJECT_ROOT / "data" / "molflex_reinicios"
MF02D_MAT = PROJECT_ROOT / "data" / "molflex_train_v2"
COHORTE = OUT_DIR / "cohorte.json"
UMBRAL_A = 2.0
K_MAX = 90
KS = (30, 60, 90)


def _oraculo(w: Path, crystal, s2m, cids_validos=None):
    """(min rmsd_pose_pocket, n_poses) sobre los conf*.out.pdbqt indicados."""
    import molflex as mf
    mejor, n = None, 0
    for f in sorted(w.glob("conf*.out.pdbqt")):
        try:
            cid = int(f.name[4:f.name.index(".")])
        except ValueError:
            continue
        if cids_validos is not None and cid not in cids_validos:
            continue
        for _sc, at in mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            n += 1
            rp = mf.rmsd_pose_pocket(crystal, c)
            if rp is not None and (mejor is None or rp < mejor):
                mejor = rp
    return mejor, n


def _una(job: Dict[str, Any]) -> Dict[str, Any]:
    import numpy as np
    import molflex as mf

    pid = job["pid"]
    fila: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"]}
    t0 = time.time()
    work = MATERIAL / pid
    work.mkdir(parents=True, exist_ok=True)
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return {**fila, "ok": False, "reason": "sdf_ilegible"}

    kept: Dict[str, int] = {}
    ens = {}
    for k in KS:
        mh, ids = mf.construir_ensemble(crystal, k)
        kept[str(k)] = len(ids)
        ens[k] = (mh, ids)
    fila["kept"] = kept

    # G5: el ensemble K30 debe ser prefijo exacto del K90
    mh30, ids30 = ens[30]
    mh90, ids90 = ens[90]
    anidado = True
    for i in range(min(len(ids30), len(ids90))):
        a = mh30.GetConformer(ids30[i]).GetPositions()
        b = mh90.GetConformer(ids90[i]).GetPositions()
        if a.shape != b.shape or not np.allclose(a, b, atol=1e-6):
            anidado = False
            break
    fila["anidado"] = anidado
    if not anidado:
        return {**fila, "ok": False, "reason": "prefijo_no_anidado"}

    prep = mf.preparar_complejo(pid, K_MAX, str(work), EXPERIMENT_ID)
    if not prep.get("ok"):
        return {**fila, "ok": False, "reason": prep.get("reason")}
    cids = prep["cids"]
    s2m = {int(s): int(m) for s, m in
           json.loads((work / pid / "index_map.json").read_text(encoding="utf-8"))}

    n30 = kept["30"]
    nuevos = cids[n30:]
    fallos = 0
    for cid in nuevos:
        r = mf.dock_rigido_archivo(pid, cid, str(work), 1)
        if not r.get("ok"):
            fallos += 1
    fila["n_dockeados_nuevos"] = len(nuevos) - fallos
    fila["fallos_dock"] = fallos

    # K30 sale del material sellado de MF-02D; K60/K90 de la unión con lo nuevo
    w02d = MF02D_MAT / pid / pid
    o30, n_p30 = None, 0
    if (w02d / "index_map.json").exists():
        s2m_d = {int(s): int(m) for s, m in
                 json.loads((w02d / "index_map.json").read_text(encoding="utf-8"))}
        o30, n_p30 = _oraculo(w02d, crystal, s2m_d)
    fila["K30"] = {"oraculo": round(o30, 3) if o30 is not None else None,
                   "n_poses": n_p30, "n_conf": kept["30"], "fuente": "MF-02D"}
    for k in (60, 90):
        cids_k = set(cids[:kept[str(k)]])
        ok_, np_ = _oraculo(work / pid, crystal, s2m, cids_k)
        cand = [x for x in (ok_, o30) if x is not None]
        fila[f"K{k}"] = {"oraculo": round(min(cand), 3) if cand else None,
                         "n_poses": np_ + n_p30, "n_conf": kept[str(k)], "fuente": "union"}
    for k in KS:
        v = fila[f"K{k}"]["oraculo"]
        fila[f"exito_K{k}"] = bool(v is not None and v <= UMBRAL_A)
    fila["ok"] = True
    fila["wall_s"] = round(time.time() - t0, 2)
    return fila


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-02F: conformeros como reinicios de busqueda")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MATERIAL.mkdir(parents=True, exist_ok=True)
    coh = json.loads(COHORTE.read_text(encoding="utf-8"))
    cohorte, control = coh["cohorte_colocacion"], coh["control_cubiertos"]
    if args.limite:
        cohorte, control = cohorte[:args.limite], control[:max(1, args.limite // 3)]
    jobs = ([{"pid": p, "estrato": "COLOCACION"} for p in cohorte]
            + [{"pid": p, "estrato": "CONTROL"} for p in control])
    print(f"[MF-02F] {len(cohorte)} colocacion + {len(control)} control = {len(jobs)} complejos "
          f"| K30 del material de MF-02D; solo se dockean los conformeros nuevos", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, f in enumerate(ex.map(_una, jobs, chunksize=1), 1):
            filas.append(f)
            if i % 5 == 0 or i == len(jobs):
                r = sum(1 for x in filas if x.get("exito_K90") and x["estrato"] == "COLOCACION")
                print(f"  [{i}/{len(jobs)}] K90 recupera {r} ({round(time.time() - t0)}s)", flush=True)

    def resumen(estrato: str, k: int) -> Dict[str, Any]:
        sub = [f for f in filas if f["estrato"] == estrato and f.get("ok")]
        cub = [f["pid"] for f in sub if f.get(f"exito_K{k}")]
        med = [f[f"K{k}"]["oraculo"] for f in sub if f.get(f"K{k}", {}).get("oraculo") is not None]
        nc = [f["kept"][str(k)] for f in sub]
        return {"n": len(sub), "cubiertos": len(cub), "pids": sorted(cub),
                "mediana_oraculo": round(median(med), 3) if med else None,
                "n_conf_mediano": round(median(nc), 1) if nc else None}

    res = {f"K{k}": {e: resumen(e, k) for e in ("COLOCACION", "CONTROL")} for k in KS}
    n_ok = sum(1 for f in filas if f.get("ok"))
    rec = {k: res[f"K{k}"]["COLOCACION"]["cubiertos"] for k in KS}
    no_anidan = [f["pid"] for f in filas if f.get("anidado") is False]

    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"ks": list(KS), "umbral_A": UMBRAL_A, "k_max_generado": K_MAX,
                   "metrica": "min rmsd_pose_pocket sobre todas las poses dockeadas del brazo",
                   "nota_K30": "material sellado de MF-02D; no se recomputa"},
        "cohorte": {"colocacion": len(cohorte), "control": len(control)},
        "n_complejos": len(filas), "n_ok": n_ok,
        "resumen_por_brazo": res,
        "coste": {"mediana_s": round(median([f["wall_s"] for f in filas if f.get("ok")]), 1)
                  if n_ok else None},
        "nota_monotonia": ("Con prefijos anidados K90 contiene a K60 y este a K30: la cobertura "
                           "solo puede subir. La monotonia es tautologica y NO es evidencia "
                           "(PRE seccion 4)."),
    }
    metrics["gates"] = {
        "G1_validez": {"criterio": ">=95% completan sin error",
                       "tasa": round(n_ok / len(filas), 4) if filas else 0.0,
                       "pass": bool(filas and n_ok / len(filas) >= 0.95)},
        "G2_recuperacion": {"criterio": "K90 recupera >=3 de los 33 sobre lo que ya daba K30",
                            "K30": rec[30], "K60": rec[60], "K90": rec[90],
                            "recuperados_sobre_K30": rec[90] - rec[30],
                            "pass": (rec[90] - rec[30]) >= 3},
        "G3_saturacion": {"criterio": "informativo: si K60->K90 no anade complejos, satura en K60",
                          "delta_K60_K90": rec[90] - rec[60],
                          "satura_en_K60": (rec[90] - rec[60]) == 0, "pass": True},
        "G5_anidamiento": {"criterio": "el ensemble K30 es prefijo exacto del K90 en toda la cohorte",
                           "no_anidan": no_anidan, "pass": not no_anidan},
    }
    metrics["decision"] = "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO"

    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            if not r.get("ok"):
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[MF-02F] decision {metrics['decision']}")
    for k in KS:
        c = res[f"K{k}"]["COLOCACION"]
        ct = res[f"K{k}"]["CONTROL"]
        print(f"  K{k}: cohorte {c['cubiertos']}/{c['n']} (mediana {c['mediana_oraculo']} A, "
              f"{c['n_conf_mediano']} conf) | control {ct['cubiertos']}/{ct['n']}")
    for k, g in metrics["gates"].items():
        print(f"  {k}: {'PASS' if g['pass'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
