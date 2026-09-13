#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep02ext_huecos_sitio.py — FEP-02-EXT: ¿el hueco está donde importa?

`FEP-02` midió que **86 de 203 receptores (42%) tienen huecos de numeración**. Ese numero
quedo como una de las dos razones por las que solo 83 de 203 estarian documentados para
FEP+.

Pero contó **existencia**, no **relevancia**. Un tramo de cadena ausente a cincuenta
residuos del bolsillo no afecta a un calculo de energia libre de union; uno que corta el
propio sitio, si. `FEP-02` lo declaro en su propia limitacion: «los 86 son candidatos, no
defectos confirmados».

Este experimento aplica a los huecos el mismo tratamiento que `FEP-01-EXT` aplico a los
tautomeros: medir la consecuencia en lugar de la existencia.

Qué se mide
-----------
Para cada receptor con huecos, se localiza el **sitio de union** por proximidad al ligando
cristalografico y se clasifica cada hueco por su distancia al sitio:

  * **EN EL SITIO**    — alguno de los dos residuos que flanquean el hueco esta a <= 8 A
                          de algun atomo del ligando;
  * **PERIFERICO**     — flanqueantes entre 8 y 15 A;
  * **LEJANO**         — mas de 15 A; irrelevante para el calculo.

El umbral de 8 A es el mismo radio con el que `FEP-02` definio «sitio» al contar cadenas,
metales y aguas, y se reusa por coherencia en vez de elegir uno nuevo.

Qué NO se afirma
----------------
Un hueco lejano **no** garantiza que la estructura sea utilizable: puede romper el
plegamiento o la dinamica global. Lo que se mide es la fraccion cuyo defecto toca
directamente la region que decide la union, que es la unica que obliga a reparar ANTES de
poder declarar el receptor. Un hueco lejano se declara; uno en el sitio se arregla.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

R_SITIO = 8.0        # mismo radio con el que FEP-02 definio "sitio"
R_PERIFERIA = 15.0


def _residuos(pdb: Path) -> Dict[Tuple[str, int], List[Tuple[float, float, float]]]:
    """(cadena, numero) -> coordenadas de sus atomos. Solo ATOM, sin aguas ni heteros."""
    res: Dict[Tuple[str, int], List[Tuple[float, float, float]]] = defaultdict(list)
    for l in pdb.read_text(encoding="utf-8", errors="replace").splitlines():
        if not l.startswith("ATOM") or len(l) < 54:
            continue
        try:
            cad = l[21]
            num = int(l[22:26])
            xyz = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
        except ValueError:
            continue
        res[(cad, num)].append(xyz)
    return res


def _huecos(res) -> List[Tuple[str, int, int]]:
    """(cadena, ultimo_antes, primero_despues) por salto de numeracion."""
    porcad: Dict[str, List[int]] = defaultdict(list)
    for (c, n) in res:
        porcad[c].append(n)
    out = []
    for c, nums in porcad.items():
        nums = sorted(set(nums))
        for a, b in zip(nums, nums[1:]):
            if b - a > 1:
                out.append((c, a, b))
    return out


def _dmin(coords, lig) -> float:
    best = 1e9
    for x, y, z in coords:
        for lx, ly, lz in lig:
            d = (x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2
            if d < best:
                best = d
    return best ** 0.5


def main() -> int:
    ap = argparse.ArgumentParser(description="FEP-02-EXT: relevancia de los huecos de cadena")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out = ws / "scripts" / "artifacts_science" / "FEP-02-EXT"
    out.mkdir(parents=True, exist_ok=True)

    import molflex as mf

    fep02 = {}
    for l in (ws / "scripts" / "artifacts_science" / "FEP-02" /
              "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            fep02[r["pid"]] = r

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    for pid, base in sorted(fep02.items()):
        r: Dict[str, Any] = {"pid": pid, "split": base.get("split"),
                             "huecos_FEP02": base.get("huecos_numeracion", 0),
                             "tiene_huecos": bool(base.get("tiene_huecos"))}
        if not r["tiene_huecos"]:
            r["clasificacion"] = "SIN_HUECOS"
            filas.append(r)
            continue

        prot = ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb"
        m = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
        if not prot.exists() or m is None:
            r["error"] = "SIN_MATERIAL"
            filas.append(r)
            continue
        conf = m.GetConformer(0)
        lig = [(conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z)
               for i in range(m.GetNumAtoms()) if m.GetAtomWithIdx(i).GetAtomicNum() > 1]
        res = _residuos(prot)
        if not res or not lig:
            r["error"] = "PDB_ILEGIBLE"
            filas.append(r)
            continue

        det = []
        for (c, a, b) in _huecos(res):
            d = min(_dmin(res[(c, a)], lig), _dmin(res[(c, b)], lig))
            cls = ("EN_EL_SITIO" if d <= R_SITIO
                   else "PERIFERICO" if d <= R_PERIFERIA else "LEJANO")
            det.append({"cadena": c, "de": a, "a": b, "residuos_ausentes": b - a - 1,
                        "dist_min_al_ligando": round(d, 2), "clase": cls})
        r["huecos_detectados"] = len(det)
        r["detalle"] = det[:20]
        r["n_en_el_sitio"] = sum(1 for x in det if x["clase"] == "EN_EL_SITIO")
        r["n_periferico"] = sum(1 for x in det if x["clase"] == "PERIFERICO")
        r["n_lejano"] = sum(1 for x in det if x["clase"] == "LEJANO")
        r["dist_min_global"] = min((x["dist_min_al_ligando"] for x in det), default=None)
        r["clasificacion"] = ("EN_EL_SITIO" if r["n_en_el_sitio"] else
                              "PERIFERICO" if r["n_periferico"] else "LEJANO")
        filas.append(r)

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    con_huecos = [r for r in filas if r["tiene_huecos"] and "error" not in r]
    err = [r for r in filas if "error" in r]
    cls = defaultdict(int)
    for r in con_huecos:
        cls[r["clasificacion"]] += 1

    metrics = {
        "experiment_id": "FEP-02-EXT",
        "tipo": "medicion de consecuencia, sin gates de decision",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_complejos": len(filas),
        "n_con_huecos_segun_FEP02": sum(1 for r in filas if r["tiene_huecos"]),
        "n_analizables": len(con_huecos),
        "n_error": len(err),
        "errores": {r["pid"]: r["error"] for r in err},
        "umbrales": {"sitio_A": R_SITIO, "periferia_A": R_PERIFERIA,
                     "nota": "R_SITIO reusa el radio con que FEP-02 definio sitio"},
        "clasificacion_por_complejo": dict(cls),
        "fraccion_en_el_sitio": (round(cls["EN_EL_SITIO"] / len(con_huecos), 4)
                                 if con_huecos else None),
        "huecos_totales": sum(r.get("huecos_detectados", 0) for r in con_huecos),
        "huecos_en_el_sitio": sum(r.get("n_en_el_sitio", 0) for r in con_huecos),
        "limitacion_declarada": (
            "Un hueco LEJANO no garantiza que la estructura sea utilizable: puede romper "
            "plegamiento o dinamica global. Se mide que fraccion tiene el defecto EN la "
            "region que decide la union, que es la que obliga a reparar antes de declarar "
            "el receptor. Un hueco lejano se declara; uno en el sitio se arregla."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")

    print(f"[FEP-02-EXT] {len(filas)} receptores en {metrics['duration_seconds']}s")
    print(f"  con huecos segun FEP-02 : {metrics['n_con_huecos_segun_FEP02']}")
    print(f"  analizables             : {len(con_huecos)}   errores: {len(err)}")
    for k in ("EN_EL_SITIO", "PERIFERICO", "LEJANO"):
        print(f"    {k:12s} {cls[k]:3d}")
    print(f"  fraccion EN EL SITIO    : {metrics['fraccion_en_el_sitio']}")
    print(f"  huecos totales {metrics['huecos_totales']}, de ellos en el sitio "
          f"{metrics['huecos_en_el_sitio']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
