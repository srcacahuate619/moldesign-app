#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf02a_conf_ceiling.py — MF-02A: ¿el ensemble ETKDG contiene la conformación bioactiva?

Prerrequisito formal: `scripts/artifacts_science/MF-02-PRE/PREREGISTRO.md` sellado.

Pregunta
--------
La cobertura del oráculo del conjunto de poses de train es 67.2% (78/116): en 38
complejos no existe ninguna pose a <=2 A del cristal. Ese fallo puede tener dos
causas y este experimento aísla la primera **sin docking**:

  (A) el ensemble ETKDG nunca contuvo la conformación bioactiva -> ningún
      presupuesto de búsqueda lo arregla (techo conformacional);
  (B) el ensemble sí la contenía y el docking no la colocó ni la rankeó
      -> lo mide MF-02B en la otra máquina.

Método
------
Se replica exactamente el ensemble de `molflex.py::construir_ensemble` (ETKDG con
preferencias de torsión CSD, `useBasicKnowledge`, `pruneRmsThresh=0.4`,
`randomSeed=42`) y se mide, para cada complejo, el **RMSD mínimo ALINEADO**
(`AllChem.GetBestRMS`, átomos pesados, simetría incluida) entre cualquier
confórmero y el ligando cristalográfico.

Aquí se alinea a propósito: la pregunta es sobre la **conformación interna**, no
sobre la colocación. Es la decisión contraria a REC-03, donde el RMSD se midió in
situ porque allí lo que se juzgaba era el acierto de colocación.

Curva: se embeben 150 confórmeros una sola vez y se reporta el mínimo acumulado
sobre los primeros n conformeros conservados, n en {5,15,30,60,90,150}. Leer la
curva de forma acumulada —en vez de embeber seis veces— es 6x mas barato y además
es como se comportaria un muestreador por lotes (MF-09).

Ejecuta solo con RDKit: no necesita Vina, por eso corre en el contenedor.
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
from typing import Any, Dict, List, Optional

EXPERIMENT_ID = "MF-02A"
N_CONF_MAX = 150
CURVA = (5, 15, 30, 60, 90, 150)
SEMILLA_ETKDG = 42
PRUNE_RMS = 0.4
UMBRAL_CONF_A = 1.0   # conformación considerada "disponible"
UMBRAL_POSE_A = 2.0   # umbral del oráculo de poses, para comparar


def _rmsd_min_curva(pid: str, sdf_path: str) -> Dict[str, Any]:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem

    RDLogger.logger().setLevel(RDLogger.ERROR)
    out: Dict[str, Any] = {"pid": pid}
    crystal = Chem.MolFromMolFile(sdf_path)
    if crystal is None:
        crystal = Chem.MolFromMolFile(sdf_path, sanitize=False, removeHs=False)
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out

    t0 = time.time()
    mh = Chem.AddHs(crystal)
    try:
        ids = list(AllChem.EmbedMultipleConfs(
            mh, numConfs=N_CONF_MAX, randomSeed=SEMILLA_ETKDG,
            useExpTorsionAnglePrefs=True, useBasicKnowledge=True,
            pruneRmsThresh=PRUNE_RMS, numThreads=1,
        ))
    except Exception as e:
        out["error"] = "EMBED_FALLO"
        out["detalle"] = str(e)[-200:]
        return out
    if not ids:
        out["error"] = "SIN_CONFORMEROS"
        return out

    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    out["n_conf_conservados"] = len(ids)
    out["n_heavy"] = len(pesados)

    rmsds: List[Optional[float]] = []
    for cid in ids:
        prb = Chem.Mol(crystal)
        conf = prb.GetConformer(0)
        try:
            for i in pesados:
                p = mh.GetConformer(cid).GetAtomPosition(i)
                conf.SetAtomPosition(i, p)
            rmsds.append(float(AllChem.GetBestRMS(prb, crystal, 0, 0)))
        except Exception:
            rmsds.append(None)

    validos = [r for r in rmsds if r is not None]
    if not validos:
        out["error"] = "RMSD_NO_CALCULABLE"
        return out

    curva = {}
    for n in CURVA:
        sub = [r for r in rmsds[:n] if r is not None]
        curva[str(n)] = round(min(sub), 3) if sub else None
    out["curva_rmsd_min"] = curva
    out["rmsd_min"] = round(min(validos), 3)
    out["rmsd_mediana"] = round(sorted(validos)[len(validos) // 2], 3)
    out["conformacion_disponible_1A"] = bool(out["rmsd_min"] <= UMBRAL_CONF_A)
    out["conformacion_disponible_2A"] = bool(out["rmsd_min"] <= UMBRAL_POSE_A)
    out["wall_s"] = round(time.time() - t0, 2)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-02A: techo conformacional del ensemble ETKDG")
    ap.add_argument("--workspace", default=".", help="Raíz del workspace (contenedor: /workspace)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out-name", default=EXPERIMENT_ID)
    ap.add_argument("--all-pdbbind", action="store_true",
                    help="MF-02A-EXT: todos los complejos con SDF bajo data/pdbbind "
                         "en vez de los 116 de train")
    args = ap.parse_args()

    ws = Path(args.workspace)
    if args.all_pdbbind:
        pids = sorted(p.parent.name for p in (ws / "data" / "pdbbind").glob("*/*_ligand.sdf"))
        print(f"[MF-02A] cohorte extendida: {len(pids)} complejos de PDBBind", flush=True)
    else:
        a_dir = ws / "scripts" / "artifacts_science" / "RS-03-PARAM-A"
        pids = sorted({
            json.loads(l)["pid"]
            for l in (a_dir / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        })
        print(f"[MF-02A] cohorte: {len(pids)} complejos train", flush=True)

    tareas = [(p, str(ws / "data" / "pdbbind" / p / f"{p}_ligand.sdf")) for p in pids]
    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_rmsd_min_curva, *zip(*tareas), chunksize=1), 1):
            filas.append(r)
            if i % 10 == 0 or i == len(tareas):
                print(f"  [{i}/{len(tareas)}] ({round(time.time() - t0)}s)", flush=True)

    ok = [f for f in filas if "error" not in f]
    fallos = [f for f in filas if "error" in f]

    def _frac(rows, clave):
        return round(sum(1 for r in rows if r[clave]) / len(rows), 4) if rows else None

    curva_global = {}
    for n in CURVA:
        vals = [r["curva_rmsd_min"][str(n)] for r in ok if r["curva_rmsd_min"].get(str(n)) is not None]
        curva_global[str(n)] = {
            "n": len(vals),
            "frac_<=1.0A": round(sum(1 for v in vals if v <= UMBRAL_CONF_A) / len(vals), 4) if vals else None,
            "frac_<=2.0A": round(sum(1 for v in vals if v <= UMBRAL_POSE_A) / len(vals), 4) if vals else None,
            "mediana": round(sorted(vals)[len(vals) // 2], 3) if vals else None,
        }

    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_total": len(filas),
        "n_ok": len(ok),
        "n_fallos": len(fallos),
        "config": {
            "n_conf_max": N_CONF_MAX, "curva": list(CURVA), "seed_etkdg": SEMILLA_ETKDG,
            "prune_rms_thresh": PRUNE_RMS,
            "rmsd": "AllChem.GetBestRMS ALINEADO sobre atomos pesados (mide conformacion, no colocacion)",
            "lectura_curva": "minimo acumulado sobre los primeros n conformeros conservados de un unico embebido de 150",
        },
        "curva_global": curva_global,
        "frac_conformacion_disponible_1A": _frac(ok, "conformacion_disponible_1A"),
        "frac_conformacion_disponible_2A": _frac(ok, "conformacion_disponible_2A"),
        "nota": ("Mide el techo conformacional, no la cobertura del oraculo. Un complejo con "
                 "conformacion disponible y sin pose buena es fallo de busqueda o colocacion, "
                 "no del ensemble: eso lo decide MF-02B."),
    }

    out_dir = ws / "scripts" / "artifacts_science" / args.out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in ok:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out_dir / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in fallos:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[MF-02A] {len(ok)}/{len(filas)} complejos medidos")
    for n in CURVA:
        g = curva_global[str(n)]
        print(f"  n_conf={n:>3}: mediana {g['mediana']} A | <=1.0A {g['frac_<=1.0A']:.1%} | <=2.0A {g['frac_<=2.0A']:.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
