#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf21_techo_rigido.py — MF-21: ¿es alcanzable lo que MF-19 demuestra?

**Tipo: medición.** Lectura de los confórmeros ETKDG ya en disco. Sin cómputo nuevo de
docking.

La pregunta, y por qué es la más urgente ahora
----------------------------------------------
`MF-19` (en curso) muestra que si a Vina se le entrega el **confórmero cristalográfico**
y se le congelan las torsiones, coloca la pose nativa con precisión excelente — en
complejos donde `MF-09` estableció que no existe ninguna pose ≤2 Å entre ~751
candidatas. Eso apunta a que el cuello es la **dimensionalidad torsional**.

Pero `MF-19` usa el cristal, que en producción **no se conoce**. Así que su resultado
es un **techo**, y la pregunta que decide si ese techo sirve para algo es:

  **¿el ensemble ETKDG que ya generamos contiene algún confórmero suficientemente
  parecido al bioactivo como para que el docking rígido funcione?**

  * Si **sí**: `MF-19` señala una estrategia real —dockear rígido cada confórmero en
    vez de dejar que Vina busque torsiones— y la palanca es la selección de confórmero.
  * Si **no**: `MF-19` mide algo inalcanzable, y el cuello vuelve a ser la generación
    de confórmeros, no la búsqueda.

Qué se mide
-----------
Por complejo, sobre cada confórmero del ensemble ETKDG usado para dockear:

  * **RMSD alineado** al ligando cristalográfico (`GetBestRMS`, átomos pesados,
    simetría incluida). Aquí alinear es **correcto a propósito**: mide conformación
    interna, no colocación — la misma convención declarada en `MF-02A`/`MF-02A-EXT`, y
    la contraria a la del resto de la línea.

El **mejor** confórmero del ensemble es el **suelo teórico** del docking rígido: si su
RMSD alineado es 3 Å, ninguna colocación rígida de ese ensemble puede bajar de 3 Å,
por perfecta que sea la búsqueda.

Luego se cruza con el desenlace de `MF-09` (¿existe pose ≤2 Å?) para ver si el suelo
conformacional explica los fallos.
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
OUT_DIR = ART / "MF-21"
UMBRAL_A = 2.0
BANDAS = (0.5, 1.0, 1.5, 2.0, 3.0)


def _analizar(job: Dict[str, Any]) -> Dict[str, Any]:
    import molflex as mf
    from rdkit import Chem
    from rdkit.Chem import AllChem
    pid = job["pid"]
    out: Dict[str, Any] = {"pid": pid, "estrato": job["estrato"]}
    w = MAT / pid / pid
    crystal = mf.leer_ligando(PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    mapa_f = w / "index_map.json"
    if not mapa_f.exists():
        out["error"] = "SIN_MATERIAL"
        return out
    s2m = {int(s): int(m) for s, m in json.loads(mapa_f.read_text(encoding="utf-8"))}
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]

    rmsds: List[float] = []
    # SOLO conformeros ETKDG de ENTRADA. El glob "conf*.rigid.pdbqt" tambien captura
    # "conf{N}.relax.rigid.pdbqt", que son poses YA DOCKEADAS Y RELAJADAS -salida del
    # pipeline-: incluirlas mide lo que el docking logro, no lo que el generador ofrece,
    # e infla el techo. Se filtra con regex estricta.
    entradas = [f for f in sorted(w.glob("conf*.rigid.pdbqt"))
                if re.match(r"conf\d+\.rigid\.pdbqt$", f.name)]
    for f in entradas:
        texto = f.read_text(encoding="utf-8", errors="replace")
        at = []
        for l in texto.splitlines():
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
                try:
                    at.append([int(l[6:11]), float(l[30:38]), float(l[38:46]),
                               float(l[46:54])])
                except ValueError:
                    continue
        c = mf.coords_pose_a_por_mol(at, s2m)
        if not c or any(i not in c for i in pesados):
            continue
        # se construye un mol con las coordenadas del conformero y se ALINEA al cristal:
        # aqui alinear es correcto, la pregunta es sobre conformacion interna
        probe = Chem.Mol(crystal)
        conf = probe.GetConformer(0)
        for i in pesados:
            x, y, z = c[i]
            conf.SetAtomPosition(i, (float(x), float(y), float(z)))
        try:
            r = AllChem.GetBestRMS(probe, crystal, 0, 0)
        except Exception:
            continue
        rmsds.append(round(float(r), 3))

    out["n_conformeros"] = len(rmsds)
    if not rmsds:
        out["error"] = "SIN_CONFORMEROS"
        return out
    out["rmsd_alineado_min"] = min(rmsds)
    out["rmsd_alineado_mediano"] = round(median(rmsds), 3)
    out["rmsd_alineado_max"] = max(rmsds)
    for b in BANDAS:
        out[f"n_bajo_{b}"] = sum(1 for r in rmsds if r <= b)
    out["techo_rigido_alcanzable"] = bool(min(rmsds) <= UMBRAL_A)
    out["rmsds"] = rmsds
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-21: suelo conformacional del docking rigido")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    coh = json.loads((ART / "MF-02F" / "cohorte.json").read_text(encoding="utf-8"))
    jobs = [{"pid": p, "estrato": "COLOCACION"} for p in coh["cohorte_colocacion"]] + \
           [{"pid": p, "estrato": "CONTROL"} for p in coh["control_cubiertos"]]
    # desenlace de MF-09
    des = {}
    for l in (ART / "MF-09" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            des[d["pid"]] = {"cubierto": bool(d.get("existe_pose_buena")),
                             "oraculo": d.get("oraculo_rmsd")}
    print(f"[MF-21] {len(jobs)} complejos, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, jobs), 1):
            r.update(des.get(r["pid"], {}))
            filas.append(r)
            print(f"  [{i}/{len(jobs)}] {r['pid']} confs={r.get('n_conformeros')} "
                  f"mejor={r.get('rmsd_alineado_min')} cubierto={r.get('cubierto')}", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    grupos: Dict[str, Any] = {}
    for etiq, sel in (("COLOCACION", lambda r: r["estrato"] == "COLOCACION"),
                      ("CONTROL", lambda r: r["estrato"] == "CONTROL"),
                      ("NO_CUBIERTO", lambda r: r.get("cubierto") is False),
                      ("CUBIERTO", lambda r: r.get("cubierto") is True)):
        g = [r for r in ok if sel(r)]
        if not g:
            continue
        grupos[etiq] = {
            "n": len(g),
            "n_conformeros_mediano": int(median(r["n_conformeros"] for r in g)),
            "mejor_rmsd_alineado_mediano": round(median(r["rmsd_alineado_min"] for r in g), 3),
            "complejos_con_conformero_bajo_2A": sum(1 for r in g if r["techo_rigido_alcanzable"]),
            "frac_alcanzable": round(
                sum(1 for r in g if r["techo_rigido_alcanzable"]) / len(g), 4),
            "n_conformeros_bajo_1.5A_mediano": int(median(r["n_bajo_1.5"] for r in g)),
        }
    metrics = {
        "experiment_id": "MF-21",
        "tipo": "medicion (lectura de los conformeros ETKDG en disco, sin docking nuevo)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "metrica": ("RMSD ALINEADO (GetBestRMS, simetria incluida) entre cada conformero del "
                    "ensemble y el ligando cristalografico. Alinear es CORRECTO aqui: mide "
                    "conformacion interna, no colocacion (convencion de MF-02A/MF-02A-EXT)"),
        "n_complejos": len(filas), "n_ok": len(ok),
        "grupos": grupos,
        "lectura": ("frac_alcanzable alta en los NO_CUBIERTO => el ensemble SI contiene un "
                    "conformero suficientemente bueno y la estrategia de MF-19 (dockear rigido) "
                    "es viable: el cuello seria la busqueda torsional. frac_alcanzable baja => "
                    "MF-19 mide un techo inalcanzable y el cuello vuelve a ser la GENERACION "
                    "de conformeros"),
    }
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-21] " + json.dumps(grupos, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
