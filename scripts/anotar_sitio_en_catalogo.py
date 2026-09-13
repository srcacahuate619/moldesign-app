"""Anota en el catalogo QUE cadenas forman el sitio, y CON QUE EVIDENCIA se sabe.

# Que se anota, y por que el hecho y no la politica

El catalogo guarda hoy `chain`: **una** cadena, la que se prepara. Eso mezcla dos
cosas distintas —el hecho de que sitio forma quien, y la decision de que
conservar— y la mezcla es la que produjo los defectos del doc 71.

Aqui se anota el HECHO, medido:

    site_chains        las cadenas que forman el sitio, en orden de aporte
    site_chain_atoms   cuanto aporta cada una, para poder rederivar el umbral
                       sin volver a correr nada
    site_evidence      COMO se sabe: `cocrystal_ligand` o `box_volume`
    site_ligand        el ligando co-cristalizado que lo demuestra, si lo hay

El modo de preparacion —una cadena o varias— se DERIVA de `site_chains`. No se
anota, porque una politica congelada en la tabla obliga a reanotar 387 filas el
dia que cambie el umbral, y nadie sabria con que criterio se puso cada una.

# Por que `site_evidence` no es un detalle de auditoria

Son dos afirmaciones de fuerza muy distinta:

    cocrystal_ligand   las cadenas que contactan el ligando cristalizado a
                       <=4,5 A. Es lo que miraria un cristalografo, y es
                       reproducible sobre el archivo del RCSB.
    box_volume         las cadenas que ponen atomos dentro de la caja. No
                       distingue el bolsillo de la vecindad: una cadena puede
                       llenar la caja sin formar el sitio.

Un catalogo que presenta las dos como si fueran lo mismo esta afirmando de mas
en el segundo caso. Por eso el campo viaja hasta la tarjeta del receptor: el
investigador tiene derecho a saber si lo que le estamos diciendo lo respalda un
cristal o un recuento de volumen.

# La resolucion, de paso

387 de 387 estructuras traen su resolucion en el `REMARK 2` del PDB, y 367 del
catalogo la tenian a `null` —la tarjeta mostraba «N/A» en el 95% de los casos—.
No falta el dato: se perdio al ingerir. Se recupera en el mismo recorrido de
archivos, sin red.

# Lo que este script NO hace

No cambia `chain`. No decide el modo de preparacion. No reanota hotspots. Solo
anade hechos medidos a filas que ya existen.

# Uso

    python scripts/anotar_sitio_en_catalogo.py            # dry-run
    python scripts/anotar_sitio_en_catalogo.py --aplicar
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "backend"))

from revisar_cadena_por_receptor import CATALOGO, ESTRUCTURAS, revisar  # noqa: E402
from triaje_receptores_al_vacio import APORTE_MINIMO  # noqa: E402

RESOLUCION = re.compile(r"([\d.]+)\s*ANGSTROM")


def resolucion_del_header(pdb_id: str) -> float | None:
    """La resolucion que declara el propio archivo, en su `REMARK 2`."""
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                if linea.startswith("REMARK   2 RESOLUTION"):
                    m = RESOLUCION.search(linea)
                    if m:
                        try:
                            return float(m.group(1))
                        except ValueError:
                            return None
                if linea.startswith(("ATOM", "HETATM")):
                    return None
    return None


def anotar(objetivo: dict) -> dict | None:
    """Los campos del sitio para un objetivo, o None si no hay con que medirlo.

    **Delega en `services/targets/sitio_de_union.py`, que es la unica
    implementacion.** Aqui vivia una copia que reconstruia lo mismo desde
    `revisar()`, y las dos coincidieron en los 385 objetivos... hasta que una de
    ellas empezo a generar la unidad biologica y la otra no. La copia se quedo
    midiendo sobre las coordenadas depositadas y el catalogo no recibia las
    cadenas de simetria: exactamente el modo de fallo que este repositorio lleva
    toda la sesion persiguiendo, en el sitio donde mas facil era pasarlo por
    alto.

    Duplicar una medida no es redundancia: es una divergencia esperando a
    ocurrir.
    """
    from services.targets.sitio_de_union import anotar_sitio

    pdb_id = (objetivo.get("pdb_id") or "").upper()
    contenido = leer_pdb(pdb_id)
    if contenido is None:
        return None
    centro = objetivo.get("grid_center_x"), objetivo.get("grid_center_y"), objetivo.get("grid_center_z")
    if centro[0] is None:
        return None
    tamano = (
        objetivo.get("grid_size_x") or 25.0,
        objetivo.get("grid_size_y") or 25.0,
        objetivo.get("grid_size_z") or 25.0,
    )
    return anotar_sitio(contenido, centro, tamano)


def leer_pdb(pdb_id: str) -> str | None:
    """La estructura completa, sin filtrar. El ensamblaje lo genera `anotar_sitio`."""
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    anotados = 0
    sin_medir: list[str] = []
    resoluciones = 0
    evidencia: collections.Counter = collections.Counter()
    n_cadenas: collections.Counter = collections.Counter()

    for objetivo in catalogo:
        pdb = (objetivo.get("pdb_id") or "").upper()
        campos = anotar(objetivo)
        if campos is None:
            sin_medir.append(pdb)
        else:
            anotados += 1
            evidencia[campos["site_evidence"]] += 1
            n_cadenas[len(campos["site_chains"])] += 1
            if args.aplicar:
                objetivo.update(campos)

        if objetivo.get("resolution") is None:
            r = resolucion_del_header(pdb)
            if r is not None:
                resoluciones += 1
                if args.aplicar:
                    objetivo["resolution"] = r

    print(f"objetivos anotados: {anotados} de {len(catalogo)}")
    print(f"  evidencia: " + ", ".join(f"{k}={v}" for k, v in evidencia.most_common()))
    print(f"  cadenas que forman el sitio: " + ", ".join(
        f"{k} cadena{'s' if k != 1 else ''}={v}" for k, v in sorted(n_cadenas.items())))
    print(f"resoluciones recuperadas del header: {resoluciones}")
    if sin_medir:
        print(f"sin medir ({len(sin_medir)}): {', '.join(sin_medir)}")

    if not args.aplicar:
        print("\nNada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nescrito {CATALOGO.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
