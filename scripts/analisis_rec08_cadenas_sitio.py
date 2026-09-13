#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rec08_cadenas_sitio.py — REC-08: ¿la preparación destruye sitios inter-cadena?

`FEP-02` midió que **43 de 203 complejos (21%) tienen el sitio de unión repartido entre
más de una cadena**, y su propio docstring dejó anotado el riesgo concreto: que
`_detect_dominant_chain` recorte una sola cadena y destruya un sitio inter-cadena.

Ese riesgo nunca se comprobó. Aquí se comprueba, y es barato porque el material ya existe:
basta comparar el receptor **preparado** (`rec.pdbqt`, el que Vina realmente usa) contra el
**original** (`protein.pdb` de PDBBind).

Qué se mide
-----------
Para cada complejo:

  1. **Cadenas que forman el sitio** — las que aportan algún residuo con un átomo a <= 8 A
     de algún átomo pesado del ligando cristalográfico, medido sobre el PDB original.
  2. **Cadenas presentes en el receptor preparado.**
  3. **Perdida** — cadenas del punto 1 ausentes del punto 2, y cuántos residuos de sitio
     se fueron con ellas.

El radio de 8 A se reusa de `FEP-02`, para que las dos mediciones sean comparables.

Lo que este experimento decide
------------------------------
Si alguna cadena que forma el sitio desaparece en la preparación, ese complejo se dockeó
contra un bolsillo **incompleto** y todo lo medido sobre él arrastra un error no declarado.
No es una cuestión de documentación como el resto de la cartera H: es un defecto de
produccion.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

R_SITIO = 8.0


def _atomos(p: Path, prefijos=("ATOM",)):
    """(cadena, resnum, x, y, z) de las lineas pedidas."""
    for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith(prefijos) and len(l) >= 54:
            try:
                yield (l[21], l[22:26].strip(),
                       float(l[30:38]), float(l[38:46]), float(l[46:54]))
            except ValueError:
                continue


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-08: cadenas del sitio tras la preparacion")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out = ws / "scripts" / "artifacts_science" / "REC-08"
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
                             "sitio_entre_cadenas_FEP02": bool(base.get("sitio_entre_cadenas")),
                             "cadenas_en_sitio_FEP02": base.get("cadenas_en_sitio")}
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
        if not lig:
            r["error"] = "LIGANDO_SIN_PESADOS"
            filas.append(r)
            continue

        # 1) cadenas y residuos que forman el sitio, sobre el ORIGINAL
        sitio_res: Set = set()
        cad_sitio: Set[str] = set()
        for c, n, x, y, z in _atomos(prot):
            for lx, ly, lz in lig:
                if (x - lx) ** 2 + (y - ly) ** 2 + (z - lz) ** 2 <= R_SITIO ** 2:
                    sitio_res.add((c, n))
                    cad_sitio.add(c)
                    break
        # 2) cadenas presentes en el PREPARADO
        cad_prep: Set[str] = {c for c, *_ in _atomos(rec, ("ATOM", "HETATM"))}
        # 3) perdida
        perdidas = sorted(cad_sitio - cad_prep)
        res_perdidos = sum(1 for (c, n) in sitio_res if c in perdidas)

        r["cadenas_del_sitio"] = sorted(cad_sitio)
        r["n_residuos_de_sitio"] = len(sitio_res)
        r["cadenas_en_preparado"] = sorted(cad_prep)
        r["cadenas_del_sitio_perdidas"] = perdidas
        r["n_residuos_de_sitio_perdidos"] = res_perdidos
        r["sitio_mutilado"] = len(perdidas) > 0
        filas.append(r)

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    err = [r for r in filas if "error" in r]
    mult = [r for r in ok if len(r["cadenas_del_sitio"]) > 1]
    mut = [r for r in ok if r["sitio_mutilado"]]
    mut_mult = [r for r in mult if r["sitio_mutilado"]]

    metrics = {
        "experiment_id": "REC-08",
        "tipo": "medicion de defecto de produccion, sin gates de decision",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_complejos": len(filas), "n_ok": len(ok), "n_error": len(err),
        "errores": {r["pid"]: r["error"] for r in err},
        "radio_sitio_A": R_SITIO,
        "sitios_multicadena": {
            "n": len(mult), "de": len(ok),
            "nota": "medido aqui sobre el PDB original; FEP-02 reporto 43 de 203"},
        "SITIO_MUTILADO": {
            "definicion": "alguna cadena que aporta residuos al sitio no esta en rec.pdbqt",
            "n": len(mut), "de": len(ok),
            "fraccion": round(len(mut) / len(ok), 4) if ok else None,
            "ids": [r["pid"] for r in mut][:60],
            "de_los_multicadena": len(mut_mult)},
        "residuos_de_sitio_perdidos": {
            "total": sum(r["n_residuos_de_sitio_perdidos"] for r in mut),
            "mediana_por_complejo_afectado": (
                sorted(r["n_residuos_de_sitio_perdidos"] for r in mut)[len(mut) // 2]
                if mut else 0)},
        "limitacion_declarada": (
            "Se compara presencia de CADENA, no identidad residuo a residuo. Una cadena "
            "presente pero recortada en su extremo no se detecta aqui. El resultado es una "
            "COTA INFERIOR del dano."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")

    print(f"[REC-08] {len(filas)} complejos en {metrics['duration_seconds']}s  "
          f"(ok {len(ok)}, error {len(err)})")
    print(f"  sitios formados por mas de una cadena : {len(mult)}/{len(ok)}")
    print(f"  SITIO MUTILADO por la preparacion     : {len(mut)}/{len(ok)}  "
          f"({metrics['SITIO_MUTILADO']['fraccion']})")
    print(f"    de ellos, con sitio multicadena     : {len(mut_mult)}")
    if mut:
        print(f"    residuos de sitio perdidos (total)  : "
              f"{metrics['residuos_de_sitio_perdidos']['total']}")
        print(f"    ids: {', '.join(r['pid'] for r in mut[:20])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
