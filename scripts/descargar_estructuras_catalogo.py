"""Descarga del RCSB las estructuras del catalogo que falten, y las guarda comprimidas.

# Por que existe

`curated_targets.json` declara 387 objetivos y el repositorio solo tenia 87
estructuras. En una instalacion limpia eso significaba que 300 de los 387
bloqueaban la comprobacion previa con «el PDB todavia no esta en disco», porque
el preflight NO descarga nada por diseño.

# Por que comprimidas

Las 387 sin comprimir son ~183 MB y dejarian el runtime empaquetado en ~2065
MiB. `makensis` es un compilador de 32 bits y muere a los 2 GiB: ya nos paso una
vez con el bytecode precompilado, y el resultado no fue un instalador grande
sino NINGUN instalador.

Un PDB es texto y comprime ~4x. Las 387 en gzip son ~45 MB, menos que los 67 MB
que hoy ocupan 111 sin comprimir: el instalador ENCOGE llevando 3,5 veces mas
estructuras.

# Uso

    python scripts/descargar_estructuras_catalogo.py [--dry-run] [--forzar]

Es idempotente: lo que ya esta no se vuelve a pedir. Se ejecuta a mano cuando el
catalogo crece, no en cada build — un build no puede depender de la red.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "curated_targets.json"
DESTINO = RAIZ / "data" / "targets"
ID_PDB = re.compile(r"^[0-9][A-Za-z0-9]{3}$")

# RCSB sirve el PDB ya comprimido: se descarga menos y se guarda tal cual.
URL = "https://files.rcsb.org/download/{pdb_id}.pdb.gz"
AGENTE = "MolDesign/1.0 (empaquetado de catalogo; contacto en el repositorio)"


def ids_del_catalogo() -> list[str]:
    datos = json.loads(CATALOGO.read_text(encoding="utf-8"))
    vistos = {t["pdb_id"].upper() for t in datos if t.get("pdb_id")}
    return sorted(i for i in vistos if ID_PDB.fullmatch(i))


def ya_tenemos(pdb_id: str) -> bool:
    return (DESTINO / f"{pdb_id}.pdb.gz").is_file() or (DESTINO / f"{pdb_id}.pdb").is_file()


def descargar(pdb_id: str) -> tuple[str, str, int]:
    destino = DESTINO / f"{pdb_id}.pdb.gz"
    peticion = urllib.request.Request(URL.format(pdb_id=pdb_id), headers={"User-Agent": AGENTE})
    try:
        with urllib.request.urlopen(peticion, timeout=60) as respuesta:
            crudo = respuesta.read()
    except urllib.error.HTTPError as exc:
        return pdb_id, f"HTTP {exc.code}", 0
    except Exception as exc:  # noqa: BLE001
        return pdb_id, f"{type(exc).__name__}", 0

    # Se comprueba que el gzip abre y que dentro hay un PDB de verdad, para no
    # guardar una pagina de error con extension .gz.
    try:
        texto = gzip.decompress(crudo).decode("utf-8", errors="replace")
    except OSError:
        return pdb_id, "gzip ilegible", 0
    # Se recorre el archivo ENTERO, no las primeras lineas.
    #
    # La primera version miraba solo las 2000 primeras y descarto 10 estructuras
    # validas como «sin coordenadas»: en complejos grandes -1IRU, el proteasoma
    # 20S, o 9F9T- la cabecera pasa de 2000 lineas y las coordenadas empiezan
    # despues. 1IRU tiene 47.757 lineas ATOM/HETATM. El fallo estaba en la
    # comprobacion, no en el dato, y por poco tiramos diez receptores buenos.
    if "ATOM  " not in texto and "HETATM" not in texto:
        return pdb_id, "sin coordenadas", 0

    destino.write_bytes(crudo)
    return pdb_id, "ok", len(crudo)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="solo dice que falta")
    parser.add_argument("--forzar", action="store_true", help="vuelve a bajar lo que ya esta")
    args = parser.parse_args()

    DESTINO.mkdir(parents=True, exist_ok=True)
    todos = ids_del_catalogo()
    pendientes = todos if args.forzar else [i for i in todos if not ya_tenemos(i)]

    print(f"catalogo         : {len(todos)} objetivos")
    print(f"ya en disco      : {len(todos) - len(pendientes)}")
    print(f"por descargar    : {len(pendientes)}")
    if args.dry_run or not pendientes:
        return 0

    print(f"\nfuente: {URL.format(pdb_id='XXXX')}\n")
    ok = fallos = 0
    bytes_totales = 0
    fallidos: list[tuple[str, str]] = []
    inicio = time.monotonic()

    # Concurrencia moderada: es un servicio publico y gratuito, no una diana.
    with ThreadPoolExecutor(max_workers=4) as pool:
        futuros = {pool.submit(descargar, i): i for i in pendientes}
        for n, futuro in enumerate(as_completed(futuros), start=1):
            pdb_id, estado, tam = futuro.result()
            if estado == "ok":
                ok += 1
                bytes_totales += tam
            else:
                fallos += 1
                fallidos.append((pdb_id, estado))
            if n % 25 == 0 or n == len(pendientes):
                print(f"  {n}/{len(pendientes)}  ok={ok} fallos={fallos}  "
                      f"{bytes_totales/1e6:.1f} MB")

    print(f"\ndescargadas: {ok}   fallos: {fallos}   "
          f"{bytes_totales/1e6:.1f} MB en {time.monotonic()-inicio:.0f} s")
    if fallidos:
        print("\nno se pudieron traer (se dicen, no se ocultan):")
        for pdb_id, motivo in sorted(fallidos)[:40]:
            print(f"  {pdb_id}  {motivo}")
        print("\nEsos objetivos seguiran exigiendo `POST /targets/ingest` en la aplicacion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
