"""Prepara TODOS los receptores del catalogo como en una instalacion limpia.

Almacenamiento nuevo, estructuras sembradas desde las `.pdb.gz` que viajan en el
instalador, y el camino real: `prepare_target` con Meeko de verdad. Comprueba lo
que el usuario recibe: que el receptor preparado contiene EXACTAMENTE las cadenas
que el catalogo declara como formadoras del sitio.

    python-embed/python.exe scripts/barrido_preparacion_instalacion_limpia.py [directorio]

Deja `barrido.json` en el directorio de trabajo -por defecto
`tmp/barrido-instalacion-limpia`- con una fila por objetivo. La copia de la
corrida del 2026-09-03 esta en `docs/auditorias/preparacion_en_instalacion_limpia.json`.

No toca `~/MolDesign`: crea su propio `LOCAL_DATA_DIR`. Tarda ~30 min y ocupa
~1 GB entre las estructuras sembradas y los receptores preparados.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SANDBOX = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tmp" / "barrido-instalacion-limpia"
(SANDBOX / "data").mkdir(parents=True, exist_ok=True)
(SANDBOX / "vina").mkdir(parents=True, exist_ok=True)

os.environ.update({
    "MOLDESIGN_TESTING": "1",
    "ENVIRONMENT": "testing",
    "LOCAL_DATA_DIR": str(SANDBOX / "data"),
    "VINA_TEMP_DIR": str(SANDBOX / "vina"),
    "MEEKO_PREPARE_RECEPTOR_PATH": str(ROOT / "python-embed" / "Scripts" / "mk_prepare_receptor.exe"),
    "MEEKO_PREPARE_LIGAND_PATH": str(ROOT / "python-embed" / "Scripts" / "mk_prepare_ligand.exe"),
    "MEEKO_EXPORT_PATH": str(ROOT / "python-embed" / "Scripts" / "mk_export.exe"),
    "SECRET_KEY": "runtime-gate-secret-key-2026-at-least-32-characters",
    "PYTHONUTF8": "1",
    "LOG_LEVEL": "ERROR",
})

sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")

ESTRUCTURAS = ROOT / "data" / "targets"


async def main() -> int:
    from services.docking.preparer import prepare_target, prepared_receptor_chains
    from utils.local_storage import data_dir

    catalogo = json.loads((ROOT / "curated_targets.json").read_text(encoding="utf-8"))
    destino = data_dir()

    # La siembra del instalador, pero solo de lo que se va a usar.
    for objetivo in catalogo:
        pdb = objetivo["pdb_id"].upper()
        comprimido = ESTRUCTURAS / f"{pdb}.pdb.gz"
        crudo = destino / "targets" / pdb / "raw.pdb"
        if crudo.exists() or not comprimido.is_file():
            continue
        crudo.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(comprimido, "rt", encoding="utf-8", errors="replace") as entrada:
            crudo.write_text(entrada.read(), encoding="utf-8")

    filas: list[dict] = []
    inicio = time.monotonic()
    for indice, objetivo in enumerate(catalogo, start=1):
        pdb = objetivo["pdb_id"].upper()
        site_chains = objetivo.get("site_chains") or []
        esperadas = set(site_chains) if len(set(site_chains)) > 1 else {objetivo["chain"].strip()}
        fila = {"pdb_id": pdb, "esperadas": sorted(esperadas), "multicadena": len(set(site_chains)) > 1}
        try:
            ruta = await prepare_target(
                pdb_id=pdb,
                chain_id=objetivo["chain"],
                center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
                size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
                cofactors_whitelist=objetivo.get("cofactors_whitelist") or None,
                site_chains=site_chains or None,
            )
            contenido = (destino / ruta).read_text(encoding="utf-8", errors="replace")
            obtenidas = prepared_receptor_chains(contenido)
            fila["obtenidas"] = sorted(obtenidas)
            fila["atomos"] = sum(1 for l in contenido.splitlines() if l.startswith(("ATOM", "HETATM")))
            fila["estado"] = "OK" if obtenidas == esperadas else "CADENAS"
        except Exception as exc:  # noqa: BLE001
            fila["estado"] = "ERROR"
            fila["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        filas.append(fila)
        print(f"[{indice}/{len(catalogo)}] {pdb} {fila['estado']}", flush=True)

    (SANDBOX / "barrido.json").write_text(
        json.dumps(filas, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    cuenta: dict[str, int] = {}
    for fila in filas:
        cuenta[fila["estado"]] = cuenta.get(fila["estado"], 0) + 1
    print(f"\n== {cuenta} en {round(time.monotonic() - inicio)} s ==")
    for fila in filas:
        if fila["estado"] != "OK":
            print(" ", fila)
    return 0 if cuenta.get("OK") == len(filas) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
