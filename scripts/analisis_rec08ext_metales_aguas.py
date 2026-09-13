#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rec08ext_metales_aguas.py — REC-08-EXT: ¿y los metales y las aguas del sitio?

`REC-08` comprobó que la preparación del receptor **no pierde cadenas** que formen el sitio
de unión. Queda la otra mitad de lo que `FEP-02` contó y nadie verificó:

  * **52 complejos con metales en el sitio.** Un ion de zinc o magnesio coordinado suele ser
    catalítico y suele coordinar directamente al ligando. Si desaparece al preparar, el
    docking de ese complejo se hizo contra un bolsillo que no existe.
  * **Mediana de 10 aguas en el sitio, ninguna documentada** como estructural o desplazable.

Mismo método que `REC-08`, distinta entidad: comparar el **original**
(`<pid>_protein.pdb`) contra el **preparado** (`rec.pdbqt`, el que Vina usa).

Qué se mide
-----------
Para cada complejo, con el radio de 8 A que `FEP-02` uso para definir «sitio»:

  1. metales y aguas a <= 8 A de algun atomo pesado del ligando, en el ORIGINAL;
  2. cuantos de esos sobreviven en el PREPARADO, emparejados por coordenada (<= 0.5 A);
  3. la diferencia.

El emparejamiento es por posicion y no por numero de residuo porque la preparacion
renumera: `REC-08` ya observo que `rec.pdbqt` tiene mas pares (cadena, resnum) distintos que
el PDB de origen.

Qué decide
----------
Perder un metal del sitio **no es documentacion pendiente**: es un defecto de produccion,
igual que lo habria sido perder una cadena. Perder aguas es ambiguo —quitarlas es una
decision legitima y frecuente— pero tiene que ser una decision **declarada**, y hoy no lo
esta.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

R_SITIO = 8.0
TOL = 0.5   # A, para emparejar por coordenada entre original y preparado

METALES = {"ZN", "MG", "MN", "FE", "CA", "CU", "NI", "CO", "CD", "HG",
           "NA", "K", "MO", "W", "V", "PT", "AU", "AG", "PB", "SR", "BA"}
AGUAS = {"HOH", "WAT", "DOD", "H2O"}


def _hetatm(p: Path) -> List[Tuple[str, str, float, float, float]]:
    """(resname, elemento, x, y, z) de las lineas HETATM."""
    out = []
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith("HETATM") and len(l) >= 54:
            try:
                el = (l[76:78].strip().upper() if len(l) >= 78 else "")
                out.append((l[17:20].strip().upper(), el,
                            float(l[30:38]), float(l[38:46]), float(l[46:54])))
            except ValueError:
                continue
    return out


def _todos(p: Path) -> List[Tuple[float, float, float]]:
    out = []
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
            try:
                out.append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
            except ValueError:
                continue
    return out


def _cerca(x, y, z, pts, r) -> bool:
    r2 = r * r
    for px, py, pz in pts:
        if (x - px) ** 2 + (y - py) ** 2 + (z - pz) ** 2 <= r2:
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-08-EXT: metales y aguas del sitio tras preparar")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out = ws / "scripts" / "artifacts_science" / "REC-08-EXT"
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
                             "metales_en_sitio_FEP02": base.get("metales_en_sitio"),
                             "aguas_en_sitio_FEP02": base.get("aguas_en_sitio")}
        prot = ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb"
        rec = ws / "data" / "molflex_train_v2" / pid / pid / "rec.pdbqt"
        m = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
        if not prot.exists() or not rec.exists() or m is None:
            r["error"] = "SIN_MATERIAL"
            filas.append(r)
            continue
        conf = m.GetConformer(0)
        lig = [(conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z)
               for i in range(m.GetNumAtoms()) if m.GetAtomWithIdx(i).GetAtomicNum() > 1]
        prep = _todos(rec)

        met_sitio, agua_sitio = [], []
        for resn, el, x, y, z in _hetatm(prot):
            if not _cerca(x, y, z, lig, R_SITIO):
                continue
            if resn in AGUAS:
                agua_sitio.append((x, y, z))
            elif el in METALES or resn in METALES:
                met_sitio.append((resn or el, x, y, z))

        met_viven = sum(1 for _n, x, y, z in met_sitio if _cerca(x, y, z, prep, TOL))
        agua_viven = sum(1 for x, y, z in agua_sitio if _cerca(x, y, z, prep, TOL))

        r["metales_sitio"] = len(met_sitio)
        r["metales_conservados"] = met_viven
        r["metales_perdidos"] = len(met_sitio) - met_viven
        r["especies_metal"] = sorted({n for n, *_ in met_sitio})
        r["aguas_sitio"] = len(agua_sitio)
        r["aguas_conservadas"] = agua_viven
        r["aguas_perdidas"] = len(agua_sitio) - agua_viven
        r["pierde_metal"] = r["metales_perdidos"] > 0
        filas.append(r)

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    con_met = [r for r in ok if r["metales_sitio"] > 0]
    pierde = [r for r in con_met if r["pierde_metal"]]
    con_agua = [r for r in ok if r["aguas_sitio"] > 0]
    ag_tot = sum(r["aguas_sitio"] for r in con_agua)
    ag_viv = sum(r["aguas_conservadas"] for r in con_agua)

    metrics = {
        "experiment_id": "REC-08-EXT",
        "tipo": "medicion de defecto de produccion, sin gates de decision",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_complejos": len(filas), "n_ok": len(ok),
        "n_error": len(filas) - len(ok),
        "umbrales": {"sitio_A": R_SITIO, "emparejado_por_coordenada_A": TOL},
        "METALES": {
            "complejos_con_metal_en_sitio": len(con_met),
            "metales_totales": sum(r["metales_sitio"] for r in con_met),
            "conservados": sum(r["metales_conservados"] for r in con_met),
            "PERDIDOS": sum(r["metales_perdidos"] for r in con_met),
            "complejos_que_pierden_alguno": len(pierde),
            "ids": [r["pid"] for r in pierde][:60],
            "especies": sorted({e for r in con_met for e in r["especies_metal"]})},
        "AGUAS": {
            "complejos_con_agua_en_sitio": len(con_agua),
            "aguas_totales": ag_tot, "conservadas": ag_viv, "perdidas": ag_tot - ag_viv,
            "fraccion_conservada": round(ag_viv / ag_tot, 4) if ag_tot else None},
        "limitacion_declarada": (
            "El emparejamiento es POR COORDENADA con 0.5 A de tolerancia, no por identidad "
            "de residuo, porque la preparacion renumera. Un atomo desplazado mas de 0.5 A "
            "por la preparacion contaria como perdido: el recuento de perdidas es una COTA "
            "SUPERIOR. Perder un metal del sitio es defecto de produccion; perder aguas es "
            "una decision legitima que hoy NO esta declarada, que es el hallazgo de FEP-02."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")

    M, A = metrics["METALES"], metrics["AGUAS"]
    print(f"[REC-08-EXT] {len(filas)} complejos en {metrics['duration_seconds']}s "
          f"(ok {len(ok)}, error {metrics['n_error']})")
    print(f"  METALES: {M['complejos_con_metal_en_sitio']} complejos con metal en sitio, "
          f"{M['metales_totales']} iones")
    print(f"           conservados {M['conservados']}  PERDIDOS {M['PERDIDOS']}  "
          f"-> complejos afectados: {M['complejos_que_pierden_alguno']}")
    print(f"           especies: {', '.join(M['especies'])}")
    print(f"  AGUAS  : {A['aguas_totales']} en sitio, conservadas {A['conservadas']} "
          f"({A['fraccion_conservada']})")
    if pierde:
        print(f"  ids que pierden metal: {', '.join(r['pid'] for r in pierde[:20])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
