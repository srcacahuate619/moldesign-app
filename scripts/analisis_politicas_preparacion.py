#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barrido de las TRES politicas de heteroatomos, sobre las mismas estructuras.

La auditoria del 2026-08-22 encontro que el programa aplica tres politicas distintas y
ninguna declarada, y que **la que valida la ciencia no es la que ejecuta el producto**.
Aquello fue lectura de codigo. Esto lo mide.

Las tres, sobre la MISMA fuente para que sean comparables:

  1. `dataset_experimental` : `data/molflex_train_v2/<pid>/<pid>/rec.pdbqt`, que es lo que
     consumieron REC-08-EXT, REC-09, REC-11 y toda la serie MF-33;
  2. `producto_docking`     : el filtro de `services/docking/preparer.py`, aplicado aqui sin
     ejecutar meeko. Lo que decide que se conserva es `_filter_pdb_content`, que es Python
     puro; meeko solo anade hidrogenos y cargas DESPUES, y no cambia que residuos entran.
     Se importa el modulo de produccion en vez de reimplementar el filtro;
  3. `producto_mmgbsa`      : `removeHeterogens(keepWater=False)` de MolChamb v2, que se
     modela aqui como "todo HETATM fuera" porque eso es exactamente lo que hace.

Sin computo pesado: es lectura de ficheros y conteo. No decide nada ni cambia ningun
receptor; produce el numero que `docs/53` §6.2 afirmaba a partir del codigo.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

from services.chemistry.preparation_report import (          # noqa: E402
    preparation_report, leer_atomos, clasificar, cargar_vocabulario)


def _politica_producto(pdb_text: str, chain: str) -> str | None:
    """El filtro real de produccion, importado y no reimplementado."""
    from services.docking.preparer import _filter_pdb_content
    try:
        return _filter_pdb_content(pdb_text, chain, keep_hetatm=True,
                                   cofactors_whitelist=None)
    except Exception:                                          # noqa: BLE001
        return None


def _politica_mmgbsa(pdb_text: str) -> str:
    """`removeHeterogens(keepWater=False)`: se queda solo con ATOM."""
    return "\n".join(l for l in pdb_text.splitlines() if l.startswith("ATOM")) + "\n"


def _cadena_mayoritaria(pdb_text: str) -> str:
    c = Counter(a.cadena for a in leer_atomos(pdb_text) if a.record == "ATOM")
    return c.most_common(1)[0][0] if c else "A"


def main() -> int:
    art = ROOT / "scripts" / "artifacts_science"
    out_dir = art / "PREP-01"
    out_dir.mkdir(parents=True, exist_ok=True)

    pids = sorted({json.loads(l)["pid"] for l in
                   (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
                   if l.strip()})

    filas: List[Dict[str, Any]] = []
    for pid in pids:
        fuente = ROOT / "data" / "rcsb" / f"{pid}.pdb"
        prep_exp = ROOT / "data" / "molflex_train_v2" / pid / pid / "rec.pdbqt"
        if not fuente.exists() or not prep_exp.exists():
            filas.append({"pid": pid, "error": "SIN_MATERIAL"})
            continue
        texto = fuente.read_text(encoding="utf-8", errors="replace")
        chain = _cadena_mayoritaria(texto)
        lig = ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
        coords = None
        if lig.exists():
            try:
                import molflex as mf
                cr = mf.leer_ligando(lig)
                if cr is not None:
                    cf = cr.GetConformer()
                    coords = [(cf.GetAtomPosition(a.GetIdx()).x,
                               cf.GetAtomPosition(a.GetIdx()).y,
                               cf.GetAtomPosition(a.GetIdx()).z)
                              for a in cr.GetAtoms() if a.GetAtomicNum() > 1]
            except Exception:                                  # noqa: BLE001
                coords = None

        fila: Dict[str, Any] = {"pid": pid, "cadena_mayoritaria": chain,
                                "sitio_delimitado": bool(coords)}
        rutas = {
            "dataset_experimental": prep_exp.read_text(encoding="utf-8", errors="replace"),
            "producto_docking": _politica_producto(texto, chain),
            "producto_mmgbsa": _politica_mmgbsa(texto),
        }
        for nombre, preparado in rutas.items():
            if preparado is None:
                fila[nombre] = {"error": "FILTRO_FALLO"}
                continue
            rep = preparation_report(texto, preparado, ruta=nombre, ligando_coords=coords)
            pol = rep["politica_observada"]
            fila[nombre] = {
                "atomos_pesados": rep["totales"]["atomos_pesados_preparado"],
                "aguas": pol["aguas"],
                "metales_conservados": pol["metales_conservados"],
                "metales_eliminados": pol["metales_eliminados"],
                "cofactores_conservados": pol["cofactores_conservados"],
                "cofactores_eliminados": pol["cofactores_eliminados"],
                "especies_del_sitio_perdidas": rep["resumen_sitio"]["especies_del_sitio_perdidas"],
                "alertas": [a["codigo"] for a in rep["alertas"]],
            }
        fila["atomos_pesados_fuente"] = preparation_report(
            texto, texto, ruta="desconocida")["totales"]["atomos_pesados_fuente"]
        filas.append(fila)
        print(f"  {pid}: exp={fila['dataset_experimental'].get('atomos_pesados')} "
              f"prod={fila['producto_docking'].get('atomos_pesados')} "
              f"mmgbsa={fila['producto_mmgbsa'].get('atomos_pesados')}", flush=True)

    ok = [f for f in filas if "error" not in f]

    def agrega(ruta: str) -> Dict[str, Any]:
        sub = [f[ruta] for f in ok if "error" not in f.get(ruta, {})]
        metal_perd = sum(1 for s in sub if s["metales_eliminados"])
        cof_perd = sum(1 for s in sub if s["cofactores_eliminados"])
        sitio = sum(1 for s in sub if s["especies_del_sitio_perdidas"])
        aguas = Counter(s["aguas"] for s in sub)
        return {"n": len(sub),
                "complejos_que_pierden_algun_metal": metal_perd,
                "complejos_que_pierden_algun_cofactor_conocido": cof_perd,
                "complejos_que_pierden_alguna_especie_del_sitio": sitio,
                "politica_de_aguas": dict(aguas),
                "atomos_pesados_mediana": (sorted(s["atomos_pesados"] for s in sub)[len(sub)//2]
                                           if sub else None)}

    metrics = {
        "analisis_id": "PREP-01",
        "tipo": "barrido descriptivo de politicas de preparacion; sin gate",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fuente": "data/rcsb/<pid>.pdb, la entrada original que REC-12-R1 descargo",
        "vocabulary_version": cargar_vocabulario()["vocabulary_version"],
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_ruta": {r: agrega(r) for r in
                     ("dataset_experimental", "producto_docking", "producto_mmgbsa")},
        "limites_declarados": [
            "descriptivo y sin gate: cuenta lo que cada politica conserva, no decide cual es correcta",
            "la ruta producto_docking aplica el filtro real de preparer.py pero NO ejecuta meeko; meeko anade hidrogenos y cargas despues y no cambia que residuos entran",
            "producto_mmgbsa modela removeHeterogens(keepWater=False) como 'solo ATOM', que es lo que hace",
            "el filtro de produccion se aplica sobre la cadena mayoritaria; en produccion la cadena la fija el catalogo por target y puede ser otra",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    (out_dir / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps({"pid": f["pid"], "error": f["error"]}, ensure_ascii=False) + "\n"
                for f in filas if "error" in f), encoding="utf-8", newline="\n")
    print("\n[PREP-01] " + json.dumps(metrics["por_ruta"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
