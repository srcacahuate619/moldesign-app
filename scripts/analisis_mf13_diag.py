#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf13_diag.py — MF-13-DIAG: ¿por qué gana el decoy en el ~30%?

**Tipo: medición.** Sin gates de aceptación y sin cómputo nuevo: lee el material ya
sellado (`MF-13`, receptores de `molflex_train_v2`, conjunto v2) y caracteriza
geométricamente los complejos en los que la pose dockeada puntúa mejor que la nativa.

La pregunta
-----------
`MF-13` dio diagnóstico MIXTO: en ~70% de los complejos difíciles la función de Vina
prefiere la pose nativa (fallo de búsqueda) y en ~30% prefiere un decoy. Ese 30% se
etiquetó provisionalmente como «fallo de puntuación», pero hay una explicación
alternativa que no se ha descartado y que tiene consecuencias muy distintas:

  **el decoy podría estar en un bolsillo distinto y genuinamente más enterrado**,
  dentro de la caja de 25 Å. Entonces la función no está equivocada —premia
  correctamente un sitio más enterrado— y el problema es que **la caja contiene un
  sitio competidor**. Eso es definición de bolsillo (cartera B), no función de
  puntuación.

Dos hipótesis previas ya descartadas antes de escribir esto, y se dejan registradas
para que no se vuelvan a probar:

  1. **«faltan metales o cofactores»** — falso: el PDBQT del receptor ya los contiene
     (`1ew8` tiene 4 Zn y 2 Mg dentro del receptor usado para dockear).
  2. **«las aguas cristalográficas chocan con la pose nativa»** — marginal: 5 de 10
     fallos tienen 1–2 aguas a <2.5 Å y 0 de 10 aciertos tienen alguna. Hay señal,
     pero 1–2 aguas no explican una desventaja de 7 kcal/mol.

Qué se mide
-----------
Por complejo, para la **pose cristalográfica** y para la **pose dockeada de mejor
score**, en el mismo receptor:

  * enterramiento: átomos pesados de proteína a <4 Å (total y por átomo de ligando);
  * aguas y metales del receptor a <2.5 y <4 Å;
  * distancia entre centroides de ambas poses — si es grande, son **sitios distintos**;
  * y el contraste entre los complejos donde gana el cristal y donde gana el decoy.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MAT = PROJECT_ROOT / "data" / "molflex_train_v2"
V2 = PROJECT_ROOT / "data" / "pose_selector_dataset" / "v2"
MF13 = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-13" / "per_complex.jsonl"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "MF-13-DIAG"
AGUAS = {"HOH", "WAT", "DOD"}
METALES = {"ZN", "MG", "MN", "FE", "CA", "CU", "NI", "CO", "CD", "NA", "K"}


def _leer_receptor(path: Path):
    """(proteina, aguas, metales) como listas de coordenadas de atomos pesados."""
    prot, ag, met = [], [], []
    for l in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if l[:6].strip() not in ("ATOM", "HETATM") or len(l) < 54:
            continue
        rn = l[17:20].strip()
        nm = l[12:16].strip()
        if nm.startswith("H"):
            continue
        try:
            p = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        except ValueError:
            continue
        if rn in AGUAS:
            ag.append(p)
        elif rn in METALES or nm in METALES:
            met.append(p)
        else:
            prot.append(p)
    return prot, ag, met


def _cerca(lig, otros, corte: float) -> int:
    c2 = corte * corte
    n = 0
    for o in otros:
        for p in lig:
            dx, dy, dz = o[0]-p[0], o[1]-p[1], o[2]-p[2]
            if dx*dx + dy*dy + dz*dz <= c2:
                n += 1
                break
    return n


def _centroide(v):
    return [sum(p[k] for p in v) / len(v) for k in range(3)]


def _mejor_pose_dockeada(pid: str) -> Optional[Tuple[float, List]]:
    """Coordenadas de la pose con mejor vina_score, leidas del material."""
    import molflex as mf
    mejor = (1e9, None)
    w = MAT / pid / pid
    if not (w / "index_map.json").exists():
        return None
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
    for f in sorted(w.glob("conf*.out.pdbqt")):
        for sc, at in mf.parsear_out_vina(f.read_text(encoding="utf-8", errors="replace")):
            if sc is None or float(sc) >= mejor[0]:
                continue
            c = mf.coords_pose_a_por_mol(at, s2m)
            if c:
                mejor = (float(sc), [list(v) for v in c.values()])
    return mejor if mejor[1] else None


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"],
                           "cristal_gana": job["cristal_gana"],
                           "ventaja": job["ventaja"]}
    rec = MAT / pid / pid / "rec.pdbqt"
    if not rec.exists():
        out["error"] = "SIN_RECEPTOR"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    cf = crystal.GetConformer(0)
    lig_c = [[cf.GetAtomPosition(i).x, cf.GetAtomPosition(i).y, cf.GetAtomPosition(i).z]
             for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    md = _mejor_pose_dockeada(pid)
    if md is None:
        out["error"] = "SIN_POSE_DOCKEADA"
        return out
    score_d, lig_d = md
    prot, ag, met = _leer_receptor(rec)
    n = len(lig_c)
    out.update({
        "n_heavy": n, "score_mejor_dock": round(score_d, 3),
        "prot_4A_cristal": _cerca(lig_c, prot, 4.0),
        "prot_4A_dock": _cerca(lig_d, prot, 4.0),
        "aguas_25_cristal": _cerca(lig_c, ag, 2.5),
        "aguas_25_dock": _cerca(lig_d, ag, 2.5),
        "aguas_4A_cristal": _cerca(lig_c, ag, 4.0),
        "aguas_4A_dock": _cerca(lig_d, ag, 4.0),
        "metales_4A_cristal": _cerca(lig_c, met, 4.0),
        "metales_4A_dock": _cerca(lig_d, met, 4.0),
        "n_aguas_receptor": len(ag), "n_metales_receptor": len(met),
    })
    out["enterramiento_cristal"] = round(out["prot_4A_cristal"] / n, 3)
    out["enterramiento_dock"] = round(out["prot_4A_dock"] / n, 3)
    out["delta_enterramiento"] = round(out["enterramiento_dock"] - out["enterramiento_cristal"], 3)
    cc, cd = _centroide(lig_c), _centroide(lig_d)
    out["dist_centroides"] = round(math.dist(cc, cd), 3)
    out["sitio_distinto"] = bool(out["dist_centroides"] > 8.0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-13-DIAG: por que gana el decoy")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = []
    for l in MF13.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        d = json.loads(l)
        if d["estrato"] in ("COLOCACION", "CONTROL") and "cristal_local_gana" in d:
            jobs.append({"pid": d["pid"], "estrato": d["estrato"],
                         "cristal_gana": d["cristal_local_gana"],
                         "ventaja": d["ventaja_cristal_local"]})
    print(f"[MF-13-DIAG] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            print(f"  [{i}/{len(jobs)}] {r['pid']} gana={r.get('cristal_gana')} "
                  f"dent={r.get('delta_enterramiento')} dist={r.get('dist_centroides')}", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    grupos = {}
    for etiq, cond in (("GANA_CRISTAL", True), ("GANA_DECOY", False)):
        g = [r for r in ok if r["cristal_gana"] is cond]
        if not g:
            continue
        grupos[etiq] = {
            "n": len(g),
            "enterramiento_cristal_mediano": round(median(r["enterramiento_cristal"] for r in g), 3),
            "enterramiento_dock_mediano": round(median(r["enterramiento_dock"] for r in g), 3),
            "delta_enterramiento_mediano": round(median(r["delta_enterramiento"] for r in g), 3),
            "dist_centroides_mediana": round(median(r["dist_centroides"] for r in g), 3),
            "complejos_en_sitio_distinto": sum(r["sitio_distinto"] for r in g),
            "aguas_25_cristal_mediana": median(r["aguas_25_cristal"] for r in g),
            "metales_4A_cristal_mediana": median(r["metales_4A_cristal"] for r in g),
        }
    metrics = {
        "experiment_id": "MF-13-DIAG",
        "tipo": "medicion (relectura de material sellado, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_complejos": len(filas), "n_ok": len(ok),
        "hipotesis_descartadas_antes_de_ejecutar": [
            "faltan metales o cofactores en el receptor: FALSO, el PDBQT ya los contiene",
            "las aguas chocan con la pose nativa: MARGINAL, 1-2 aguas no explican 7 kcal/mol",
        ],
        "grupos": grupos,
        "lectura": ("si GANA_DECOY tiene delta_enterramiento claramente positivo y/o "
                    "distancia de centroides grande, el decoy esta en un sitio distinto y mas "
                    "enterrado: la funcion no se equivoca y el problema es que la caja "
                    "contiene un sitio competidor (cartera B). Si no, el 30% sigue siendo "
                    "fallo de puntuacion sin explicar."),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-13-DIAG] " + json.dumps(grupos, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
