#!/usr/bin/env python3
r"""Qué dianas del catálogo no se pueden preparar hoy, y por qué.

# Qué genera

`backend/data/disponibilidad_catalogo.json`: las entradas de
`curated_targets.json` cuya preparación se detendría por un cofactor o residuo
modificado sin plantilla Meeko validada a `MARGEN_SITIO_A` o menos de la caja
(DOCK-003), y las que se preparan retirando uno lejano del sitio.

# Por qué un archivo generado

El catálogo conserva sus 380 dianas: una diana bloqueada se muestra como «no
disponible» con su motivo, en vez de desaparecer o de fallar al pulsar
«evaluar». Calcularlo al listar el catálogo costaría una unidad biológica por
diana en cada petición. El archivo se deriva con **la misma función** que usa
`prepare_target` (`cofactores_sin_plantilla`), así que no puede describir otra
política; `--check` falla si deja de coincidir con el catálogo o con el código.

# Uso

    python scripts/generate_catalog_availability.py --write
    python scripts/generate_catalog_availability.py --check
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "curated_targets.json"
DESTINO = RAIZ / "backend" / "data" / "disponibilidad_catalogo.json"

os.environ.setdefault("MOLDESIGN_TESTING", "1")
sys.path[:0] = [str(RAIZ / "backend"), str(RAIZ)]


def _fuente(pdb_id: str) -> str:
    for ruta in (RAIZ / "data" / "targets" / f"{pdb_id}.pdb.gz",
                 RAIZ / "data" / "targets" / f"{pdb_id}.pdb"):
        if ruta.is_file():
            if ruta.suffix == ".gz":
                with gzip.open(ruta, "rt", encoding="utf-8", errors="replace") as fh:
                    return fh.read()
            return ruta.read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError(f"{pdb_id}: sin estructura en data/targets")


def construir() -> dict:
    from services.chemistry.ensamblaje_biologico import generar_unidad_biologica
    from services.docking.preparer import (
        MARGEN_SITIO_A,
        RECEPTOR_RECIPE_VERSION,
        cofactores_sin_plantilla,
        resolve_effective_docking_box,
    )

    catalogo_bytes = CATALOGO.read_bytes()
    no_disponibles: dict[str, dict] = {}
    fuera_del_sitio: dict[str, list] = {}
    for entrada in json.loads(catalogo_bytes):
        pdb_id = str(entrada["pdb_id"]).upper()
        chain = (entrada.get("chain") or "A").strip()
        sitio = [c.strip() for c in (entrada.get("site_chains") or []) if c and c.strip()]
        cadenas = set(sitio) if len(set(sitio)) > 1 else {chain}
        center = tuple(float(entrada.get(f"grid_center_{e}") or 0.0) for e in "xyz")
        size = tuple(float(entrada.get(f"grid_size_{e}") or 20.0) for e in "xyz")
        if center == (0.0, 0.0, 0.0):
            center, size = resolve_effective_docking_box(
                pdb_id=pdb_id, chain_id=chain, center=center, size=size, site_chains=sitio,
            )
        raw = generar_unidad_biologica(_fuente(pdb_id), pdb_id=pdb_id).pdb
        en_sitio, fuera = cofactores_sin_plantilla(
            raw, cadenas=cadenas, site_ligand=entrada.get("site_ligand"),
            cofactors_whitelist=entrada.get("cofactors_whitelist") or [],
            center=center, size=size,
        )
        if en_sitio:
            no_disponibles[pdb_id] = {
                "motivo": (
                    "Cofactor o residuo modificado sin plantilla Meeko validada "
                    f"a {MARGEN_SITIO_A:g} Å o menos de la caja: "
                    + ", ".join(f"{f['name']} {f['chain']}{f['residue_number']} "
                                f"({f['distance_to_box_A']} Å)" for f in en_sitio)
                    + ". Acoplar sin él, o con una carga inventada, cambiaría la química del sitio."
                ),
                "cofactores": en_sitio,
            }
        elif fuera:
            fuera_del_sitio[pdb_id] = fuera
    for pdb_id in no_disponibles:
        no_disponibles[pdb_id]["origen"] = "cofactor_sin_plantilla"
    return {
        "_doc": (
            "Generado por scripts/generate_catalog_availability.py; no editar a mano. "
            "Una diana en `no_disponibles` sigue en el catálogo y se muestra con su motivo. "
            "`origen: cofactor_sin_plantilla` se recalcula en cada --check; "
            "`origen: preparacion_medida` sale de --barrido, que ejecuta Meeko sobre "
            "todo el catálogo y sólo vale para la receta y la versión de Meeko que declara. "
            "`truncadas_en_sitio` también sale del barrido: por diana disponible, las "
            "cadenas laterales que el cristal no resolvía y se truncaron a ALA o GLY a "
            "`margen_sitio_A` o menos de la caja. La cavidad acoplada pierde esos grupos."
        ),
        "catalogo_sha256": hashlib.sha256(catalogo_bytes).hexdigest(),
        "receta_receptor": RECEPTOR_RECIPE_VERSION,
        "margen_sitio_A": MARGEN_SITIO_A,
        "no_disponibles": dict(sorted(no_disponibles.items())),
        "cofactores_fuera_del_sitio": dict(sorted(fuera_del_sitio.items())),
    }


def motivo_compacto(paso: str, detalle: str, margen: float) -> str:
    """Una frase legible para la interfaz, sin rutas ni trazas de la máquina que midió."""
    if paso == "receptor_site_residues_missing":
        filas = re.findall(
            r'"chain": "(\w*)", "residue_number": "(-?\d+)", "insertion_code": "(\w*)", '
            r'"name": "(\w+)", "distance_to_box_A": ([\d.]+)', detalle)
        lista = ", ".join(f"{n} {c}{r}{i} ({d} Å)" for c, r, i, n, d in filas[:8])
        resto = f" y {len(filas) - 8} más" if len(filas) > 8 else ""
        return (f"Meeko elimina {len(filas)} residuo(s) a {margen:g} Å o menos de la caja, "
                f"del sitio: {lista}{resto}. "
                "No se acopla contra un sitio incompleto.")
    if paso == "mk_prepare_receptor":
        errores = re.findall(r"^(\w+(?:Error|Exception)): (.+)$", detalle, flags=re.M)
        causa = f"{errores[-1][0]}: {errores[-1][1]}" if errores else "error sin mensaje"
        return f"Meeko no puede construir el receptor ({causa[:200]})."
    return re.sub(r"[A-Za-z]:[\\/][^\s\"']+|/home/[^\s\"']+", "<ruta>", detalle)[:400]


def barrido(datos: dict, concurrencia: int = 3) -> dict:
    """Prepara de verdad cada diana disponible y añade las que Meeko no puede.

    Lento (Meeko sobre ~370 receptores). Escribe en un LOCAL_DATA_DIR propio:
    exige la variable para no tocar los datos del usuario.
    """
    import asyncio
    import datetime
    import importlib.metadata

    from core.exceptions import ProteinPreparationError
    from services.docking.preparer import _meeko_report_path, prepare_target
    from utils.local_storage import read_text

    if not os.environ.get("LOCAL_DATA_DIR"):
        raise SystemExit("--barrido exige LOCAL_DATA_DIR apuntando a un directorio desechable")
    catalogo = json.loads(CATALOGO.read_bytes())
    pendientes = [e for e in catalogo if str(e["pdb_id"]).upper() not in datos["no_disponibles"]]
    fallos: dict[str, dict] = {}
    truncadas: dict[str, list[str]] = {}
    semaforo = asyncio.Semaphore(concurrencia)

    async def una(entrada: dict) -> None:
        pdb_id = str(entrada["pdb_id"]).upper()
        async with semaforo:
            try:
                preparado = await prepare_target(
                    pdb_id, (entrada.get("chain") or "A").strip(),
                    tuple(float(entrada.get(f"grid_center_{e}") or 0.0) for e in "xyz"),
                    tuple(float(entrada.get(f"grid_size_{e}") or 20.0) for e in "xyz"),
                    force_reprepare=True,
                    cofactors_whitelist=entrada.get("cofactors_whitelist") or [],
                    site_chains=entrada.get("site_chains"),
                    site_ligand=entrada.get("site_ligand"),
                )
                informe = json.loads(await read_text(_meeko_report_path(preparado)))
                en_sitio = [
                    f"{f['chain']}:{f['residue_number']}{f.get('insertion_code') or ''} "
                    f"{f['name']}→{str(f['action']).split()[-1]} ({f['distance_to_box_A']} Å)"
                    for f in informe.get("truncated_sidechains") or []
                    if f.get("site_critical")
                ]
                if en_sitio:
                    truncadas[pdb_id] = en_sitio
            except ProteinPreparationError as exc:
                fallos[pdb_id] = {
                    "motivo": motivo_compacto(exc.step, str(exc.detail), datos["margen_sitio_A"]),
                    "paso": exc.step,
                    "origen": "preparacion_medida",
                }
            except Exception as exc:  # noqa: BLE001 - se registra, no se oculta
                fallos[pdb_id] = {
                    "motivo": motivo_compacto("error_inesperado", f"{type(exc).__name__}: {exc}",
                                              datos["margen_sitio_A"]),
                    "paso": "error_inesperado",
                    "origen": "preparacion_medida",
                }
            print(f"  {pdb_id}: {'NO' if pdb_id in fallos else 'ok'}", flush=True)

    async def todas() -> None:
        await asyncio.gather(*(una(e) for e in pendientes))

    asyncio.run(todas())
    datos["no_disponibles"] = dict(sorted({**datos["no_disponibles"], **fallos}.items()))
    datos["truncadas_en_sitio"] = dict(sorted(truncadas.items()))
    datos["barrido_meeko"] = {
        "fecha": datetime.date.today().isoformat(),
        "receta_receptor": datos["receta_receptor"],
        "meeko": importlib.metadata.version("meeko"),
        "dianas_preparadas": len(pendientes),
        "fallidas": len(fallos),
    }
    return datos


def conservar_medidas(nuevo: dict, anterior: dict) -> dict:
    """--write y --check recalculan los cofactores y conservan el barrido medido."""
    medido = anterior.get("barrido_meeko")
    if not medido:
        return nuevo
    if medido.get("receta_receptor") != nuevo["receta_receptor"]:
        raise SystemExit(
            f"El barrido se midió con la receta {medido.get('receta_receptor')} y el código "
            f"usa la {nuevo['receta_receptor']}: repite --barrido."
        )
    heredadas = {k: v for k, v in anterior.get("no_disponibles", {}).items()
                 if v.get("origen") == "preparacion_medida" and k not in nuevo["no_disponibles"]}
    nuevo["no_disponibles"] = dict(sorted({**nuevo["no_disponibles"], **heredadas}.items()))
    if "truncadas_en_sitio" in anterior:
        nuevo["truncadas_en_sitio"] = anterior["truncadas_en_sitio"]
    nuevo["barrido_meeko"] = medido
    return nuevo


def serializar(datos: dict) -> str:
    return json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--write", action="store_true")
    modo.add_argument("--check", action="store_true")
    modo.add_argument("--barrido", action="store_true",
                      help="prepara con Meeko todo el catálogo (lento; exige LOCAL_DATA_DIR)")
    args = parser.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    anterior = json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.is_file() else {}
    if args.barrido:
        texto = serializar(barrido(construir()))
        DESTINO.write_text(texto, encoding="utf-8", newline="\n")
        datos = json.loads(texto)
        print(f"Barrido: {datos['barrido_meeko']}; no disponibles: {len(datos['no_disponibles'])}")
        return 0
    texto = serializar(conservar_medidas(construir(), anterior))
    if args.write:
        DESTINO.write_text(texto, encoding="utf-8", newline="\n")
        datos = json.loads(texto)
        print(f"Generado: {DESTINO.relative_to(RAIZ)} — "
              f"{len(datos['no_disponibles'])} no disponibles, "
              f"{len(datos['cofactores_fuera_del_sitio'])} con cofactores retirados fuera del sitio")
        return 0
    actual = DESTINO.read_text(encoding="utf-8") if DESTINO.is_file() else ""
    if actual != texto:
        print("Disponibilidad del catálogo desactualizada: ejecuta "
              "python scripts/generate_catalog_availability.py --write y revisa el diff.")
        return 1
    print("Disponibilidad del catálogo al día.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
