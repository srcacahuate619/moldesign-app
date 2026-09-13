#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rec03_preflight.py — Geometría previa de REC-03, declarada antes de ejecutar.

Precedente: REC-07 §6 («resultado geométrico ya computado, declarado antes de
ejecutar»). Este script NO hace docking: solo mide, para cada target de la
cohorte, dónde cae el pocket top-1 de MolPocket respecto del ligando nativo.

MolPocket (`backend/utils/pocket_detector.detect_pockets`) es **ligando-libre**
por construcción: `_parse_heavy_atoms` solo lee líneas ATOM, de modo que los
HETATM del ligando nativo no participan en la detección. Esa es la razón por la
que MolPocket puede definir el brazo reparador y los `hotspots` del catálogo no
(`discover_pocket_from_pdb` los deriva de los 15 residuos más cercanos al
ligando: usarlos sería circular).

Salida: scripts/artifacts_science/REC-03-PRE/geometria_preflight.json
"""

from __future__ import annotations

import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

R1_PER_COMPLEX = PROJECT_ROOT / "scripts" / "artifacts_science" / "REC-01-R1" / "per_complex.jsonl"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "REC-03-PRE"


def _leer_ligando(pdb_path: Path, codigo: str, lig_id: str) -> List[List[float]]:
    """Átomos pesados del ligando nativo.

    El identificador se reconstruye exactamente como en `structural.py`:
    `res_id = f"{chain}:{res_name}{res_seq}"`. No se usa el campo `codigo` de
    REC-01-R1 porque viene con los dígitos del resname eliminados
    (`E6C`→`EC`, `S58`→`S`), lo que impide identificar el residuo.
    """
    coords: List[List[float]] = []
    for line in pdb_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("HETATM") or len(line) < 54:
            continue
        res_name = line[17:20].strip().upper()
        chain = (line[21:22].strip() or "A").upper()
        res_seq = line[22:26].strip()
        if f"{chain}:{res_name}{res_seq}" != lig_id.upper():
            continue
        elem = (line[76:78].strip() or line[12:16].strip()[:1]).upper()
        if elem == "H":
            continue
        coords.append([float(line[30:38]), float(line[38:46]), float(line[46:54])])
    return coords


def _contencion(coords: List[List[float]], centro, tam) -> float:
    if not coords:
        return 0.0
    dentro = 0
    for x, y, z in coords:
        if (abs(x - centro[0]) <= tam[0] / 2
                and abs(y - centro[1]) <= tam[1] / 2
                and abs(z - centro[2]) <= tam[2] / 2):
            dentro += 1
    return round(dentro / len(coords), 4)


def _procesar(row: Dict[str, Any]) -> Dict[str, Any]:
    from utils.pocket_detector import detect_pockets  # import perezoso por proceso

    pdb_path = PROJECT_ROOT / row["pdb_ruta"]
    out: Dict[str, Any] = {
        "pdb_id": row["pdb_id"],
        "severidad": row["severidad"],
        "familia": row["familia"],
        "grid_centro": row["grid_centro"],
        "grid_tam": row["grid_tam"],
        "ligando": row["ligando_nativo"],
    }
    if not pdb_path.exists():
        out["error"] = "PDB_NO_ENCONTRADO"
        return out

    contenido = pdb_path.read_text(encoding="utf-8", errors="replace")
    lig = _leer_ligando(pdb_path, row["ligando_nativo"]["codigo"], row["ligando_nativo"]["id"])
    if not lig:
        out["error"] = "LIGANDO_NO_EXTRAIDO"
        return out
    out["n_atomos_pesados_extraidos"] = len(lig)
    cx = sum(c[0] for c in lig) / len(lig)
    cy = sum(c[1] for c in lig) / len(lig)
    cz = sum(c[2] for c in lig) / len(lig)
    out["centroide_ligando"] = [round(cx, 3), round(cy, 3), round(cz, 3)]

    pockets = detect_pockets(contenido, top_n=3)
    out["n_pockets"] = len(pockets)
    if not pockets:
        out["error"] = "SIN_POCKETS"
        return out

    tam = row["grid_tam"]
    detalle = []
    for i, p in enumerate(pockets, 1):
        d = math.dist(p.center, (cx, cy, cz))
        detalle.append({
            "rank": i,
            "centro": [round(v, 3) for v in p.center],
            "d_centroide_ligando": round(d, 3),
            "contencion_ligando": _contencion(lig, p.center, tam),
            "score": round(float(p.score), 4),
            "druggability": round(float(p.druggability), 4),
            "volumen": round(float(p.volume), 1),
        })
    out["pockets"] = detalle
    out["d_top1"] = detalle[0]["d_centroide_ligando"]
    out["contencion_top1"] = detalle[0]["contencion_ligando"]
    mejor = min(detalle, key=lambda x: x["d_centroide_ligando"])
    out["d_mejor_de_3"] = mejor["d_centroide_ligando"]
    out["rank_mejor_de_3"] = mejor["rank"]
    out["contencion_mejor_de_3"] = mejor["contencion_ligando"]
    # Referencia: el grid del catálogo sobre el mismo ligando
    out["d_catalogo"] = round(math.dist(row["grid_centro"], (cx, cy, cz)), 3)
    out["contencion_catalogo"] = _contencion(lig, row["grid_centro"], tam)
    return out


def main() -> int:
    rows = [json.loads(l) for l in R1_PER_COMPLEX.read_text(encoding="utf-8").splitlines() if l.strip()]
    cohorte = [
        r for r in rows
        if r["estrato"] == "HOLO" and r.get("ligando_nativo")
        and r["severidad"] in {"S1_CRITICO", "S2_GRAVE", "S0_SIN_EXCEPCION"}
    ]
    print(f"[REC-03-PRE] cohorte geométrica: {len(cohorte)} targets "
          f"(accionables + pool de control S0)", flush=True)

    resultados: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=8) as ex:
        for i, res in enumerate(ex.map(_procesar, cohorte, chunksize=2), 1):
            resultados.append(res)
            if i % 20 == 0 or i == len(cohorte):
                print(f"  [{i}/{len(cohorte)}]", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "geometria_preflight.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8", newline="\n")

    ok = [r for r in resultados if "error" not in r]
    print(f"\n[REC-03-PRE] {len(ok)}/{len(resultados)} con geometría completa")
    for sev in ("S1_CRITICO", "S2_GRAVE", "S0_SIN_EXCEPCION"):
        sub = [r for r in ok if r["severidad"] == sev]
        if not sub:
            continue
        ds = sorted(r["d_top1"] for r in sub)
        med = ds[len(ds) // 2]
        cerca = sum(1 for d in ds if d <= 8.0)
        cont = sum(1 for r in sub if r["contencion_top1"] >= 0.99)
        print(f"  {sev:<18} n={len(sub):<4} mediana d_top1={med:>7.2f} A | "
              f"d<=8A: {cerca}/{len(sub)} | contencion 100%: {cont}/{len(sub)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
