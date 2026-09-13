#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf22_presupuesto.py — MF-22: el presupuesto de error entre conformación y colocación.

**Tipo: medición.** Cruza dos cosas que ya están en disco, sin cómputo nuevo:

  * el **RMSD alineado** de cada confórmero ETKDG al ligando cristalográfico
    (error CONFORMACIONAL puro — `MF-21` lo midió a nivel de complejo, aquí por
    confórmero);
  * el **RMSD en marco de pocket** que ese mismo confórmero alcanzó al ser dockeado
    (error TOTAL: conformación + colocación).

Por qué este experimento y no el que se planeó
----------------------------------------------
Se iba a preregistrar `MF-22` como «dockear rígido cada confórmero del ensemble».
**Ese experimento ya está hecho: es el pipeline.** `molflex.dockear_conformero` dockea
`conf{cid}.rigid.pdbqt` — el PDBQT **rígido**, con `TORSDOF 0`. Repetirlo no mediría
nada nuevo.

Eso deja una contradicción aparente que este análisis resuelve:

  * `MF-09`: con el ensemble ETKDG, sólo **3 de 33** complejos difíciles obtienen una
    pose ≤2 Å entre ~751 candidatas;
  * `MF-19`: con el confórmero **cristalográfico** dockeado rígido, **24 de 33**;
  * `MF-21`: en **24 de 30** fallos el ensemble contiene un confórmero a ≤2 Å alineado.

Si el pipeline ya dockea rígido y el buen confórmero está ahí, ¿por qué falla?

La hipótesis es el **presupuesto de error**. El RMSD en marco de pocket acumula dos
fuentes que se suman: el error conformacional del confórmero de partida y el error de
colocación de la búsqueda rígida. Un confórmero a 1.36 Å —la mediana del mejor
disponible en los fallos, según `MF-21`— consume el 68% del presupuesto de 2.0 Å
**antes de colocar nada**. El cristal parte de 0 Å y lo deja entero.

Qué se mide
-----------
Por confórmero, emparejando `conf{cid}.rigid.pdbqt` (geometría de entrada) con
`conf{cid}.out.pdbqt` (poses de salida del mismo confórmero):

  * `rmsd_conf`  = RMSD **alineado** al cristal (`GetBestRMS`) — error conformacional;
  * `rmsd_pose`  = mejor RMSD **en marco de pocket** entre los modos emitidos — error total;
  * `colocacion` = `rmsd_pose − rmsd_conf`, el coste que añade la búsqueda.

Salida principal: la **curva de conversión** — probabilidad de obtener una pose ≤2 Å en
función del error conformacional de partida. De ahí sale la especificación que el
generador de confórmeros tiene que cumplir, que es lo que ningún experimento de la
línea ha dicho todavía.

Limitación declarada
--------------------
Correlacional sobre los confórmeros que el pipeline ya dockeó; no hay intervención. La
curva describe lo que pasó, no prueba que reducir el error conformacional cause la
conversión. La prueba causal exigiría generar confórmeros a un error objetivo y
dockearlos, que es un experimento distinto.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

MAT = PROJECT_ROOT / "data" / "molflex_train_v2"
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "MF-22"
UMBRAL_A = 2.0
BANDAS = ((0.0, 0.5), (0.5, 1.0), (1.0, 1.5), (1.5, 2.0), (2.0, 3.0), (3.0, 99.0))


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    from rdkit import Chem
    from rdkit.Chem import AllChem
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"], "conformeros": []}
    w = MAT / pid / pid
    if not (w / "index_map.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    # referencia SOLO de pesados; RemoveAllHs conserva el orden de los pesados, asi
    # que el k-esimo atomo de ref_heavy es el k-esimo indice de `pesados`
    ref_heavy = Chem.RemoveAllHs(Chem.Mol(crystal))
    if ref_heavy.GetNumAtoms() != len(pesados):
        out["error"] = "DESAJUSTE_PESADOS"
        return out

    def _coords_de(texto: str) -> Optional[Dict[int, Any]]:
        at = []
        for l in texto.splitlines():
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
                try:
                    at.append([int(l[6:11]), float(l[30:38]), float(l[38:46]),
                               float(l[46:54])])
                except ValueError:
                    continue
        c = mf.coords_pose_a_por_mol(at, s2m)
        return c if c and all(i in c for i in pesados) else None

    for f in sorted(w.glob("conf*.rigid.pdbqt")):
        m = re.match(r"conf(\d+)\.rigid\.pdbqt$", f.name)
        if not m:
            continue
        cid = int(m.group(1))
        c_in = _coords_de(f.read_text(encoding="utf-8", errors="replace"))
        if c_in is None:
            continue
        # error CONFORMACIONAL: alineado (mide geometria interna, no colocacion).
        # GetBestRMS usa TODOS los atomos del mol. En 6 complejos (1bju, 1c4u, 1eb2,
        # 1ezq, 1f0t, 1g3d) MolFromMolFile retiene un hidrogeno: si se deja, la sonda
        # queda con los pesados en la pose del conformero y ese H en la del cristal,
        # inflando el RMSD hasta violar el teorema de cuerpo rigido (pose < alineado
        # es imposible). Se compara sobre pesados exclusivamente.
        probe = Chem.Mol(ref_heavy)
        cf = probe.GetConformer(0)
        for k, i in enumerate(pesados):
            x, y, z = c_in[i]
            cf.SetAtomPosition(k, (float(x), float(y), float(z)))
        try:
            rconf = float(AllChem.GetBestRMS(probe, ref_heavy, 0, 0))
        except Exception:
            continue
        # error TOTAL: pocket-frame de las poses que ESE conformero produjo
        salida = w / f"conf{cid}.out.pdbqt"
        rpose = None
        if salida.exists():
            mejor = None
            for sc, at in mf.parsear_out_vina(
                    salida.read_text(encoding="utf-8", errors="replace")):
                cc = mf.coords_pose_a_por_mol(at, s2m)
                if not cc:
                    continue
                v = mf.rmsd_pose_pocket(crystal, cc)
                if v is not None and (mejor is None or v < mejor):
                    mejor = v
            rpose = round(mejor, 3) if mejor is not None else None
        fila = {"cid": cid, "rmsd_conf": round(rconf, 3), "rmsd_pose": rpose}
        if rpose is not None:
            fila["colocacion"] = round(rpose - rconf, 3)
            fila["convierte"] = bool(rpose <= UMBRAL_A)
        out["conformeros"].append(fila)
    out["n_conformeros"] = len(out["conformeros"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-22: presupuesto de error conformacion vs colocacion")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    coh = json.loads((ART / "MF-02F" / "cohorte.json").read_text(encoding="utf-8"))
    jobs = [{"pid": p, "estrato": "COLOCACION"} for p in coh["cohorte_colocacion"]] + \
           [{"pid": p, "estrato": "CONTROL"} for p in coh["control_cubiertos"]]
    print(f"[MF-22] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            filas.append(r)
            if i % 12 == 0:
                print(f"  [{i}/{len(jobs)}] ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    todos = [(r["estrato"], c) for r in filas for c in r.get("conformeros", [])
             if c.get("rmsd_pose") is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL", "TODOS"):
        g = [c for e, c in todos if est == "TODOS" or e == est]
        if not g:
            continue
        curva = {}
        for lo, hi in BANDAS:
            b = [c for c in g if lo <= c["rmsd_conf"] < hi]
            k = f"{lo}-{'inf' if hi > 90 else hi}"
            curva[k] = {
                "n": len(b),
                "convierten": sum(1 for c in b if c["convierte"]),
                "tasa": round(sum(1 for c in b if c["convierte"]) / len(b), 4) if b else None,
                "rmsd_pose_mediano": round(median(c["rmsd_pose"] for c in b), 3) if b else None,
                "coste_colocacion_mediano": round(median(c["colocacion"] for c in b), 3) if b else None,
            }
        resumen[est] = {
            "n_conformeros": len(g),
            "curva_de_conversion": curva,
            "coste_colocacion_mediano_global": round(median(c["colocacion"] for c in g), 3),
        }
    metrics = {
        "experiment_id": "MF-22",
        "tipo": "medicion correlacional (cruce de material sellado, sin computo nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "hallazgo_de_diseno": ("el MF-22 planeado -dockear rigido cada conformero- YA es el "
                               "pipeline: molflex.dockear_conformero dockea conf{cid}.rigid.pdbqt "
                               "con TORSDOF 0. Se redisenio para medir el presupuesto de error"),
        "definiciones": {
            "rmsd_conf": "RMSD ALINEADO conformero-cristal: error conformacional puro",
            "rmsd_pose": "mejor RMSD en marco de pocket de las poses de ESE conformero: error total",
            "colocacion": "rmsd_pose - rmsd_conf: lo que anade la busqueda",
        },
        "n_complejos": len(filas),
        "resumen": resumen,
        "limitacion": ("correlacional sobre lo ya dockeado; describe lo que paso, no prueba "
                       "que reducir el error conformacional CAUSE la conversion"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-22] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
