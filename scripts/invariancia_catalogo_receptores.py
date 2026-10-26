#!/usr/bin/env python3
r"""Invariante del catálogo: el mismo receptor preparado, byte a byte, antes y después.

Los receptores propios (rama `claude/receptores-propios`) añaden modos de
preparación, pero la receta 7 del catálogo no puede moverse. Este script prepara
con `prepare_target` —la función que ejecuta cada corrida— los cinco receptores
que el encargo nombra (8HFI, 1C3R, 3F75, 5VA1 y 1HSG) en un directorio de datos
desechable y escribe el SHA-256 del PDBQT y el del informe de preparación.

Se ejecuta DOS veces, una con el código de la base y otra con el de la rama, y
`--comparar` exige que los dos JSON coincidan. Un hash que cambia es un defecto,
no una actualización.

Uso (con el Python embebido):

    python scripts/invariancia_catalogo_receptores.py --salida base.json
    python scripts/invariancia_catalogo_receptores.py --salida despues.json
    python scripts/invariancia_catalogo_receptores.py --comparar base.json despues.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RECEPTORES = ("8HFI", "1C3R", "3F75", "5VA1", "1HSG")


def _entorno(datos: Path) -> None:
    vina_tmp = datos / "vina-tmp"
    vina_tmp.mkdir(parents=True, exist_ok=True)
    scripts = Path(sys.executable).parent / "Scripts"
    os.environ.update({
        "MOLDESIGN_TESTING": "1",
        "ENVIRONMENT": "testing",
        "LOCAL_DATA_DIR": str(datos),
        "VINA_TEMP_DIR": str(vina_tmp),
        "VINA_EXECUTABLE_PATH": str(RAIZ / "tools" / "vina" / "vina.exe"),
        "MEEKO_PREPARE_RECEPTOR_PATH": str(scripts / "mk_prepare_receptor.exe"),
        "MEEKO_PREPARE_LIGAND_PATH": str(scripts / "mk_prepare_ligand.exe"),
        "MEEKO_EXPORT_PATH": str(scripts / "mk_export.exe"),
        "SECRET_KEY": "invariancia-catalogo-clave-de-prueba-de-al-menos-32-caracteres",
        "PYTHONUTF8": "1",
    })
    sys.path.insert(0, str(RAIZ / "backend"))


async def _preparar(datos: Path) -> dict[str, dict[str, str]]:
    from services.docking.preparer import (
        _meeko_report_path, prepare_target, resolve_effective_docking_box,
    )
    from utils.local_storage import path_for

    filas = {row["pdb_id"]: row for row in json.loads(
        (RAIZ / "curated_targets.json").read_text(encoding="utf-8"))}
    salida: dict[str, dict[str, str]] = {}
    for pdb_id in RECEPTORES:
        fila = filas[pdb_id]
        centro = tuple(float(fila[f"grid_center_{eje}"]) for eje in "xyz")
        tamano = tuple(float(fila[f"grid_size_{eje}"]) for eje in "xyz")
        sitio = list(fila.get("site_chains") or [])
        centro, tamano = resolve_effective_docking_box(
            pdb_id=pdb_id, chain_id=fila["chain"], center=centro, size=tamano,
            site_chains=sitio,
        )
        ruta = await prepare_target(
            pdb_id=pdb_id, chain_id=fila["chain"], center=centro, size=tamano,
            force_reprepare=True, cofactors_whitelist=list(fila.get("cofactors_whitelist") or []),
            site_chains=sitio,
        )
        pdbqt = path_for(ruta).read_bytes()
        informe = path_for(_meeko_report_path(ruta)).read_bytes()
        salida[pdb_id] = {
            "receptor_sha256": hashlib.sha256(pdbqt).hexdigest(),
            "informe_sha256": hashlib.sha256(informe).hexdigest(),
            "recipe_hash": json.loads(informe)["recipe_hash"],
        }
        print(pdb_id, salida[pdb_id]["receptor_sha256"], flush=True)
    return salida


def comparar(a: Path, b: Path) -> int:
    base = json.loads(a.read_text(encoding="utf-8"))
    despues = json.loads(b.read_text(encoding="utf-8"))
    cambian = [pdb for pdb in RECEPTORES if base.get(pdb) != despues.get(pdb)]
    for pdb in RECEPTORES:
        estado = "IGUAL" if pdb not in cambian else "CAMBIA"
        print(f"{pdb}: {estado}  {base.get(pdb, {}).get('receptor_sha256')}")
    print("invariante del catálogo:", "se cumple" if not cambian else f"ROTO en {cambian}")
    return 1 if cambian else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    parser.add_argument("--salida")
    parser.add_argument("--comparar", nargs=2, metavar=("BASE", "DESPUES"))
    args = parser.parse_args()
    if args.comparar:
        return comparar(Path(args.comparar[0]), Path(args.comparar[1]))
    if not args.salida:
        parser.error("indica --salida o --comparar")
    with tempfile.TemporaryDirectory(prefix="invariancia-catalogo-", ignore_cleanup_errors=True) as tmp:
        datos = Path(tmp)
        _entorno(datos)
        resultado = asyncio.run(_preparar(datos))
    Path(args.salida).write_text(json.dumps(resultado, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
