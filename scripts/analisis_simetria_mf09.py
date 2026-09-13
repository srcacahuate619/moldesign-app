#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_simetria_mf09.py — MF-09-SYM: ¿cambia «30 de 33» al corregir simetría?

**Tipo: medición.** Sin gates de aceptación y sin cómputo nuevo: relee el mismo
material sellado de `MF-02D` + `MF-02F` que leyó `MF-09`, con la misma cohorte y el
mismo umbral, cambiando **una sola cosa** — la métrica.

Por qué
-------
La auditoría de `MF-10` (2026-08-18, doc. 49 §5.1) encontró que `rmsd_pose_pocket`
compara átomo *i* contra átomo *i* **por índice de fichero** y por tanto no corrige
**simetría**: un fenilo girado 180°, un carboxilato o un *tert*-butilo intercambiados
se penalizan aunque la pose sea físicamente idéntica. La auditoría del 2026-08-14
hizo bien en rechazar `GetBestRMS` porque **alinea**, pero `GetBestRMS` hacía dos
cosas y se descartaron ambas.

Sobre las 878 poses de `MF-10` el sesgo mediano es despreciable (0.004 Å) pero la
cola es pesada: 10 poses con sesgo > 1.0 Å, máximo 3.04 Å, y **1 complejo** (`1l83`)
gana cobertura sólo por corregir — su mejor pose mide 2.106 Å ingenua y **0.498 Å**
corregida.

`MF-09` concluyó que **en 30 de 33 complejos difíciles no existe pose ≤2 Å entre ~751
candidatas**, y esa frase sostiene el cierre de toda la cartera C. Se midió con la
métrica ingenua sobre ~34,000 poses. Este análisis rehace exactamente ese número con
la métrica corregida.

Qué se mide
-----------
Por complejo y sobre **todas** las poses de los dos directorios (el prefijo K30 vive
en el material de `MF-02D`; sólo los confórmeros posteriores se dockearon en
`MF-02F` — leer uno solo deja fuera la mitad, incidencia ya documentada en `MF-09`):

  * oráculo ingenuo vs corregido (mejor RMSD disponible);
  * si existe pose ≤2 Å bajo cada métrica;
  * RMSD del top-1 por score bajo cada métrica.

La métrica corregida es el **mínimo sobre automorfismos del RMSD sin alinear**:
conserva la propiedad que el programa exige —medir colocación en el marco del
pocket— y elimina la penalización por etiquetado de átomos.
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
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MATERIAL = Path(os.environ.get("MVS_MATERIAL", str(PROJECT_ROOT / "data" / "molflex_reinicios")))
MATERIAL_K30 = PROJECT_ROOT / "data" / "molflex_train_v2"
COHORTE = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-09-SYM"
UMBRAL_A = 2.0
MAX_AUTOS = 5000


def _permutaciones(crystal, pesados) -> List[List[int]]:
    """Automorfismos del grafo restringidos a los átomos pesados, como permutaciones
    de las POSICIONES dentro de `pesados` (no de los índices de átomo)."""
    pos = {i: k for k, i in enumerate(pesados)}
    perms: List[List[int]] = []
    for a in crystal.GetSubstructMatches(crystal, uniquify=False, useChirality=True,
                                         maxMatches=MAX_AUTOS):
        try:
            perms.append([pos[a[i]] for i in pesados])
        except KeyError:
            continue
    return perms or [list(range(len(pesados)))]


def _rmsd_par(ref: List[List[float]], pose: List[List[float]], perms) -> tuple:
    """(ingenuo, corregido) sobre los mismos átomos, ninguno alineado."""
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
    perms = _permutaciones(crystal, pesados)
    out["n_automorfismos"] = len(perms)

    scores: List[float] = []
    ing: List[float] = []
    cor: List[float] = []
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
                a, b = _rmsd_par(ref, pose, perms)
                scores.append(float(sc))
                ing.append(a)
                cor.append(b)

    n = len(ing)
    out["n_poses"] = n
    if not n:
        out["error"] = "SIN_POSES"
        return out
    k = min(range(n), key=lambda i: scores[i])
    out.update({
        "oraculo_ingenuo": round(min(ing), 3),
        "oraculo_corregido": round(min(cor), 3),
        "cubierto_ingenuo": bool(min(ing) <= UMBRAL_A),
        "cubierto_corregido": bool(min(cor) <= UMBRAL_A),
        "top1_rmsd_ingenuo": round(ing[k], 3),
        "top1_rmsd_corregido": round(cor[k], 3),
        "top1_acierta_ingenuo": bool(ing[k] <= UMBRAL_A),
        "top1_acierta_corregido": bool(cor[k] <= UMBRAL_A),
        "sesgo_mediano": round(median([a - b for a, b in zip(ing, cor)]), 4),
        "sesgo_max": round(max(a - b for a, b in zip(ing, cor)), 3),
        "poses_que_cruzan_por_simetria": sum(
            1 for a, b in zip(ing, cor) if a > UMBRAL_A >= b),
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-09-SYM: MF-09 releido con simetria corregida")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coh = json.loads(COHORTE.read_text(encoding="utf-8"))
    jobs: List[Dict[str, str]] = []
    for clave, estrato in (("cohorte_colocacion", "COLOCACION"), ("control_cubiertos", "CONTROL")):
        for pid in coh.get(clave, []):
            jobs.append({"pid": pid if isinstance(pid, str) else pid.get("pid"),
                         "estrato": estrato})
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-09-SYM] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            print(f"  [{i}/{len(jobs)}] {r['pid']} "
                  f"orac {r.get('oraculo_ingenuo')} -> {r.get('oraculo_corregido')} "
                  f"({r.get('n_poses')} poses, {round(time.time()-t0)}s)", flush=True)
            with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for x in filas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        resumen[est] = {
            "n": len(g),
            "n_poses_mediana": int(median([r["n_poses"] for r in g])),
            "oraculo_mediano_ingenuo": round(median([r["oraculo_ingenuo"] for r in g]), 3),
            "oraculo_mediano_corregido": round(median([r["oraculo_corregido"] for r in g]), 3),
            "existe_pose_buena_ingenuo": sum(1 for r in g if r["cubierto_ingenuo"]),
            "existe_pose_buena_corregido": sum(1 for r in g if r["cubierto_corregido"]),
            "top1_acierta_ingenuo": sum(1 for r in g if r["top1_acierta_ingenuo"]),
            "top1_acierta_corregido": sum(1 for r in g if r["top1_acierta_corregido"]),
            "complejos_que_ganan_cobertura": [
                r["pid"] for r in g if r["cubierto_corregido"] and not r["cubierto_ingenuo"]],
            "sesgo_mediano_de_medianas": round(median([r["sesgo_mediano"] for r in g]), 4),
            "sesgo_max": round(max(r["sesgo_max"] for r in g), 3),
        }
    metrics = {
        "experiment_id": "MF-09-SYM",
        "tipo": "medicion (relectura de material sellado, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "umbral_A": UMBRAL_A,
        "metrica_ingenua": "rmsd_pose_pocket (indice a indice, sin alinear)",
        "metrica_corregida": "minimo sobre automorfismos del RMSD sin alinear",
        "n_complejos": len(filas), "n_ok": len(ok),
        "n_poses_total": sum(r.get("n_poses", 0) for r in ok),
        "resumen": resumen,
        "errores": [r for r in filas if "error" in r],
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-09-SYM] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
