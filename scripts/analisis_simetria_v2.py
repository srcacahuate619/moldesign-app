#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_simetria_v2.py — RC-F0-SYM: la cobertura del conjunto v2 con simetría corregida.

**Tipo: medición.** Sin gates de aceptación y sin cómputo nuevo: relee el material que
`RC-F0-V2` usó para construir el conjunto v2 y recalcula la **cobertura del oráculo**
—una propiedad del **generador**— bajo la métrica corregida de la §5.1 del doc. 49.
No entrena ni evalúa ningún selector; no consume val ni test en el sentido del §3
(la lectura única de `val` es para gates de selector, no para medir el generador, que
es exactamente lo que `RC-F0-V2` ya publicó para los tres splits).

Por qué importa
---------------
La §9 del doc. 49 demuestra que `Top-1 = cobertura × precisión condicional`, y su
tabla de factibilidad decide si el gate confirmatorio de `>=0.70` es **aritméticamente
posible**: con oráculo 0.672 un selector perfecto no llega; con 0.872 sí. `RS-14` midió
la precisión condicional sobre 92 complejos cubiertos de train.

Todos esos denominadores se calcularon con `rmsd_pose_pocket` **sin corregir
simetría**. `MF-09-SYM` mostró que la corrección mueve la cobertura de la cohorte
difícil de 3/33 a 4/33 y el top-1 de Vina de 7/15 a 9/15 en el control. Este análisis
lleva la misma pregunta a los tres splits completos.

Cobertura, alcance y honestidad del número
------------------------------------------
Sólo son recomputables las poses de fuente `molflex` (94% del conjunto), porque son las
únicas trazables al material por `(pid, file_stem, model_idx)`. Las de
`flexible_redock` y `ruta_a` conservan su RMSD ingenuo almacenado.

Eso hace que la cobertura corregida que se reporta sea una **cota inferior**: corregir
simetría sólo puede **bajar** el RMSD, así que las poses no recomputadas sólo podrían
añadir cobertura, nunca quitarla. La dirección del sesgo residual es conocida y va en
contra del hallazgo, que es la dirección segura.

Verificación de validez obligatoria
-----------------------------------
Antes de comparar nada, el RMSD **ingenuo** recomputado debe reproducir el `rmsd`
almacenado en `poses_{split}.jsonl`. Sin eso, cualquier diferencia sería
indistinguible de un error de emparejamiento.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

DS = PROJECT_ROOT / "data" / "pose_selector_dataset" / "v2"
MATERIALES = [PROJECT_ROOT / "data" / "molflex_train_v2",
              PROJECT_ROOT / "data" / "molflex_valtest_v2"]
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "RC-F0-SYM"
UMBRAL_A = 2.0
MAX_AUTOS = 5000
TOL_REPRO = 0.01          # A; el dataset guarda 3 decimales


def _permutaciones(crystal, pesados) -> List[List[int]]:
    pos = {i: k for k, i in enumerate(pesados)}
    perms: List[List[int]] = []
    for a in crystal.GetSubstructMatches(crystal, uniquify=False, useChirality=True,
                                         maxMatches=MAX_AUTOS):
        try:
            perms.append([pos[a[i]] for i in pesados])
        except KeyError:
            continue
    return perms or [list(range(len(pesados)))]


def _rmsd_par(ref, pose, perms) -> Tuple[float, float]:
    n = len(ref)
    ing = (sum((ref[i][0] - pose[i][0]) ** 2 + (ref[i][1] - pose[i][1]) ** 2
               + (ref[i][2] - pose[i][2]) ** 2 for i in range(n)) / n) ** 0.5
    mejor = ing
    for p in perms:
        s = 0.0
        for i in range(n):
            j = p[i]
            s += ((ref[i][0] - pose[j][0]) ** 2 + (ref[i][1] - pose[j][1]) ** 2
                  + (ref[i][2] - pose[j][2]) ** 2)
        r = (s / n) ** 0.5
        if r < mejor:
            mejor = r
    return ing, mejor


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    pid, split = job["pid"], job["split"]
    esperadas: Dict[Tuple[str, int], float] = {
        (k[0], k[1]): v for k, v in job["molflex"]}
    out: Dict[str, Any] = {"pid": pid, "split": split,
                           "n_molflex_dataset": len(esperadas),
                           "n_otras_fuentes": job["n_otras"],
                           "mejor_otras_fuentes": job["mejor_otras"]}
    dirs = [d / pid / pid for d in MATERIALES]
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
    perms = _permutaciones(crystal, pesados)
    out["n_automorfismos"] = len(perms)

    ing: List[float] = []
    cor: List[float] = []
    repro_err: List[float] = []
    claves: List[Tuple[Tuple[str, int], float, float]] = []
    vistas = 0
    for w in dirs:
        s2m = {int(s): int(m) for s, m in
               json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
        for f in sorted(w.glob("conf*.out.pdbqt")):
            stem = f.name[:-len(".pdbqt")]          # "conf0.out"
            modelos = mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace"))
            for midx, (sc, at) in enumerate(modelos):
                clave = (stem, midx)
                if clave not in esperadas:
                    continue
                c = mf.coords_pose_a_por_mol(at, s2m)
                if not c or any(i not in c for i in pesados):
                    continue
                pose = [list(c[i]) for i in pesados]
                a, b = _rmsd_par(ref, pose, perms)
                ing.append(a)
                cor.append(b)
                repro_err.append(abs(a - esperadas[clave]))
                claves.append((clave, a, b))
                vistas += 1

    out["n_recomputadas"] = vistas
    if job.get("emitir"):
        out["_poses"] = [{"pid": pid, "split": split, "file_stem": k[0], "model_idx": k[1],
                          "rmsd": round(a, 3), "rmsd_sym": round(b, 3),
                          "positiva": bool(a <= UMBRAL_A), "positiva_sym": bool(b <= UMBRAL_A)}
                         for k, a, b in claves]
    if not ing:
        out["error"] = "SIN_EMPAREJAR"
        return out
    out.update({
        "repro_err_max": round(max(repro_err), 4),
        "repro_ok": bool(max(repro_err) <= TOL_REPRO),
        "oraculo_ingenuo": round(min(ing), 3),
        "oraculo_corregido": round(min(cor), 3),
        "sesgo_mediano": round(median([a - b for a, b in zip(ing, cor)]), 4),
        "sesgo_max": round(max(a - b for a, b in zip(ing, cor)), 3),
        "poses_que_cruzan": sum(1 for a, b in zip(ing, cor) if a > UMBRAL_A >= b),
        "n_poses_le2_ingenuo": sum(1 for a in ing if a <= UMBRAL_A),
        "n_poses_le2_corregido": sum(1 for b in cor if b <= UMBRAL_A),
    })
    # el complejo puede estar cubierto por una pose de otra fuente (rmsd ingenuo)
    mejor_ing = min([out["oraculo_ingenuo"]] + ([job["mejor_otras"]] if job["mejor_otras"] is not None else []))
    mejor_cor = min([out["oraculo_corregido"]] + ([job["mejor_otras"]] if job["mejor_otras"] is not None else []))
    out["cubierto_ingenuo"] = bool(mejor_ing <= UMBRAL_A)
    out["cubierto_corregido"] = bool(mejor_cor <= UMBRAL_A)
    return out


def _cargar_split(split: str):
    porpid_molflex = defaultdict(list)
    otras = defaultdict(list)
    for l in (DS / f"poses_{split}.jsonl").read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if d.get("source") == "molflex":
            porpid_molflex[d["pid"]].append(((d["file_stem"], d["model_idx"]), d["rmsd"]))
        else:
            otras[d["pid"]].append(d["rmsd"])
    jobs = []
    for pid in sorted(set(porpid_molflex) | set(otras)):
        o = otras.get(pid, [])
        jobs.append({"pid": pid, "split": split,
                     "molflex": porpid_molflex.get(pid, []),
                     "n_otras": len(o),
                     "mejor_otras": min(o) if o else None})
    return jobs


def main() -> int:
    ap = argparse.ArgumentParser(description="RC-F0-SYM: cobertura de v2 con simetria corregida")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--splits", default="train,val,test")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--emitir-poses", action="store_true",
                    help="escribe poses_rmsd_sym.jsonl con el RMSD corregido por pose")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jobs: List[Dict[str, Any]] = []
    for s in args.splits.split(","):
        jobs.extend(_cargar_split(s.strip()))
    for j in jobs:
        j["emitir"] = bool(args.emitir_poses)
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[RC-F0-SYM] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            print(f"  [{i}/{len(jobs)}] {r['split']}/{r['pid']} "
                  f"orac {r.get('oraculo_ingenuo')} -> {r.get('oraculo_corregido')} "
                  f"({r.get('n_recomputadas')} poses, {round(time.time()-t0)}s)", flush=True)
            with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for x in filas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    if args.emitir_poses:
        with open(OUT_DIR / "poses_rmsd_sym.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in filas:
                for p in r.pop("_poses", []):
                    fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    for r in filas:
        r.pop("_poses", None)

    ok = [r for r in filas if "error" not in r]
    resumen: Dict[str, Any] = {}
    for s in sorted({r["split"] for r in ok}):
        g = [r for r in ok if r["split"] == s]
        ci = sum(1 for r in g if r["cubierto_ingenuo"])
        cc = sum(1 for r in g if r["cubierto_corregido"])
        resumen[s] = {
            "n_complejos": len(g),
            "n_poses_recomputadas": sum(r["n_recomputadas"] for r in g),
            "reproduccion_ok": all(r["repro_ok"] for r in g),
            "repro_err_max": round(max(r["repro_err_max"] for r in g), 4),
            "cobertura_ingenua": round(ci / len(g), 4),
            "cobertura_corregida": round(cc / len(g), 4),
            "n_cubiertos_ingenuo": ci,
            "n_cubiertos_corregido": cc,
            "complejos_que_ganan": [r["pid"] for r in g
                                    if r["cubierto_corregido"] and not r["cubierto_ingenuo"]],
            "poses_que_cruzan": sum(r["poses_que_cruzan"] for r in g),
            "sesgo_max": round(max(r["sesgo_max"] for r in g), 3),
        }
    metrics = {
        "experiment_id": "RC-F0-SYM",
        "tipo": "medicion (relectura del material de RC-F0-V2, sin computo nuevo, sin selector)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "umbral_A": UMBRAL_A,
        "alcance": ("solo poses de fuente molflex (94% del conjunto) son recomputables; "
                    "las de flexible_redock y ruta_a conservan su RMSD ingenuo, por lo que "
                    "la cobertura corregida es una COTA INFERIOR"),
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "errores": [r for r in filas if "error" in r],
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[RC-F0-SYM] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
