"""Reanota los hotspots desde el ligando que ocupa la caja, y declara la procedencia.

# La procedencia real de los hotspots, que no es la que parecia

Ninguno de los hotspots del catalogo viene del RCSB. Los genero este repositorio:
`backend/scripts/recure_targets.py` corrio `discover_pocket_from_pdb` sobre los
387 y minó, para cada uno, «los 15 residuos mas cercanos al ligando holo»
detectado automaticamente. De ahi que la mediana del catalogo sea exactamente 15
hotspots.

Eso importa para no enganar al usuario en NINGUNA de las dos direcciones:

  * marcar solo los reanotados como «nuestros» sugeriria que los otros 372 son
    oficiales del PDB, y no lo son;
  * no marcar nada dejaria creer que todos tienen el mismo respaldo, y tampoco.

Por eso este script escribe `hotspots_source` en LOS 387, no solo en los que
toca. La transparencia es sobre el catalogo entero o no es transparencia.

# Que se reanota, y que no

15 objetivos tienen hotspots que no tocan el ligando de su caja. No son un
problema, son tres, y la diferencia decide el tratamiento:

    LA CAJA ESTA SOBRE UN LIGANDO QUE SI SE UNE (9)
        El grid apunta a un ligando concreto y los hotspots siguieron a otro
        -otra copia por simetria, u otro ligando distinto-. En 2VE3 los
        hotspots describen el sitio del HEMO mientras la caja esta centrada en
        el acido retinoico: dos bolsillos distintos de la misma proteina.
        La caja es el contrato -es lo que Vina muestrea-, asi que los hotspots
        tienen que describir el sitio de la caja. Se reanotan.

    LA CAJA NO ESTA SOBRE NINGUN LIGANDO (5)
        4JZD, 6MEO, 6VU4, 7ZYJ y 8WGR: el heteroatomo mas cercano al centro
        esta entre 6,2 y 15,9 A. Reanotar aqui seria FABRICAR hotspots para un
        sitio que nadie eligio: no hay ligando que sirva de testigo. El defecto
        es del grid y se arregla revisando el grid, no la anotacion.

    EL LIGANDO NO SE UNE A NADA (1)
        6SXG. El OHT -4-hidroxitamoxifeno, un farmaco de verdad- esta a 4,5 A
        del centro pero solo toca DOS residuos. Un ligando que apenas roza la
        proteina esta en la superficie o parcialmente ocupado: tampoco sirve de
        testigo, aunque su nombre invite a creer lo contrario.

# El criterio de reanotacion

Los residuos con algun atomo a <=4,5 A de algun atomo del ligando que ocupa la
caja. Es la misma distancia de contacto que usa `revisar_cadena_por_receptor.py`
para decidir la cadena, y es lo que un cristalografo llamaria el sitio.

La importancia se reparte por cercania -1,0 el mas proximo al ligando- para que
el visor y el filtro geometrico sigan teniendo con que ordenar.

# Uso

    python scripts/reanotar_hotspots_del_ligando.py [--aplicar]
"""

from __future__ import annotations

import argparse
import collections
import datetime
import gzip
import json
import math
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

from revisar_cadena_por_receptor import (  # noqa: E402
    CATALOGO,
    CORTE_CONTACTO,
    ESTRUCTURAS,
    NO_SON_LIGANDO,
    PREFIJOS_DETERGENTE,
    RESIDUOS_MODIFICADOS,
)

EXPEDIENTE = RAIZ / "docs" / "auditorias" / "expediente_de_receptores.json"
DECISIONES = RAIZ / "docs" / "auditorias" / "hotspots_reanotados.json"

#: Procedencia de la anotacion que ya existia: `discover_pocket_from_pdb`
#: minando los 15 residuos mas cercanos al ligando holo AUTODETECTADO.
FUENTE_HEREDADA = "auto_pocket_top15"
#: Procedencia de la que escribe este script: contactos del ligando que ocupa
#: LA CAJA DEL CATALOGO, que no siempre es el que autodetecto el generador.
FUENTE_REANOTADA = "box_ligand_contacts"

#: A cuanto del centro tiene que estar el ligando para que la caja «este sobre
#: el». Mas lejos, el grid apunta a otra cosa y reanotar taparia ese defecto.
CAJA_SOBRE_EL_LIGANDO_A = 5.0

#: Cuantos hotspots se conservan. Quince es lo que produjo el generador
#: heredado; mantenerlo hace comparables los receptores entre si.
CUANTOS = 15


def leer(pdb_id: str):
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        residuos: dict[tuple[str, str, int], list[tuple]] = collections.defaultdict(list)
        heteros: dict[tuple, list[tuple]] = collections.defaultdict(list)
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                if not linea.startswith(("ATOM", "HETATM")):
                    continue
                try:
                    punto = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
                    numero = int(linea[22:26])
                except ValueError:
                    continue
                nombre_res = linea[17:20].strip().upper()
                if linea.startswith("ATOM"):
                    residuos[(linea[21].strip(), nombre_res, numero)].append(punto)
                else:
                    if (nombre_res in NO_SON_LIGANDO or nombre_res in RESIDUOS_MODIFICADOS
                            or nombre_res.startswith(PREFIJOS_DETERGENTE)):
                        continue
                    heteros[(nombre_res, linea[21], numero)].append(punto)
        return dict(residuos), dict(heteros)
    return None


def reanotar(objetivo: dict) -> dict | str:
    """Los hotspots nuevos, o el MOTIVO por el que no se puede reanotar.

    Los dos motivos son distintos y no deben confundirse en el informe: que la
    caja no este sobre un ligando es un defecto del grid; que el ligando apenas
    toque la proteina significa que ese heteroatomo no es el ligando del sitio
    -esta en la superficie, o parcialmente ocupado- y tampoco sirve de testigo.
    """
    pdb = objetivo["pdb_id"].upper()
    datos = leer(pdb)
    if datos is None:
        return "sin estructura local"
    residuos, heteros = datos
    centro = (objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"])

    mejor, mejor_dist = None, 1e9
    for clave, coords in heteros.items():
        if len(coords) < 6:
            continue
        medio = tuple(sum(p[i] for p in coords) / len(coords) for i in range(3))
        d = math.dist(medio, centro)
        if d < mejor_dist:
            mejor, mejor_dist = (clave, coords), d
    if not mejor:
        return "sin ningun heteroatomo con pinta de ligando"
    if mejor_dist > CAJA_SOBRE_EL_LIGANDO_A:
        return f"la caja no esta sobre el ligando ({mejor[0][0]} a {mejor_dist:.1f} A del centro)"

    (nombre_lig, _, _), coords_lig = mejor
    corte2 = CORTE_CONTACTO ** 2
    contactos = []
    for (cadena, nombre_res, numero), puntos in residuos.items():
        d2 = min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
                 for p in puntos for q in coords_lig)
        if d2 <= corte2:
            contactos.append((math.sqrt(d2), f"{cadena}:{nombre_res}{numero}"))
    if len(contactos) < 3:
        return (f"el ligando {nombre_lig} solo toca {len(contactos)} residuos: no es el ligando "
                "del sitio, no puede servir de testigo")

    contactos.sort()
    elegidos = contactos[:CUANTOS]
    lejano = elegidos[-1][0] or 1.0
    return {
        "ligando": nombre_lig,
        "dist_centro": round(mejor_dist, 1),
        "hotspots": [
            {"name": nombre, "importance": round(max(0.1, 1.0 - (d / (lejano * 1.15))), 2)}
            for d, nombre in elegidos
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    expediente = json.loads(EXPEDIENTE.read_text(encoding="utf-8"))["receptores"]
    a_reanotar = {e["pdb_id"] for e in expediente
                  if any(f.startswith("D3") for f in e["fallos"])}

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    decisiones, sin_testigo = [], []

    for objetivo in catalogo:
        pdb = objetivo["pdb_id"].upper()
        # La procedencia se declara en TODOS, no solo en los que se tocan.
        fuente = FUENTE_HEREDADA
        if pdb in a_reanotar:
            nuevo = reanotar(objetivo)
            if isinstance(nuevo, str):
                sin_testigo.append({"pdb_id": pdb, "motivo": nuevo})
            else:
                antes = [h["name"] for h in objetivo.get("hotspots") or []]
                despues = [h["name"] for h in nuevo["hotspots"]]
                decisiones.append({
                    "pdb_id": pdb,
                    "ligando_de_la_caja": nuevo["ligando"],
                    "distancia_del_ligando_al_centro_A": nuevo["dist_centro"],
                    "hotspots_antes": antes,
                    "hotspots_despues": despues,
                    "conservados": sorted(set(antes) & set(despues)),
                })
                fuente = FUENTE_REANOTADA
                if args.aplicar:
                    objetivo["hotspots"] = nuevo["hotspots"]
        if args.aplicar:
            objetivo["hotspots_source"] = fuente

    for d in decisiones:
        print(f"{d['pdb_id']}  ligando {d['ligando_de_la_caja']} a "
              f"{d['distancia_del_ligando_al_centro_A']} A del centro"
              f"   conserva {len(d['conservados'])} de {len(d['hotspots_antes'])}")
    print(f"\nreanotados: {len(decisiones)}")
    print(f"NO se tocan: {len(sin_testigo)}")
    for r in sorted(sin_testigo, key=lambda r: r["pdb_id"]):
        print(f"   {r['pdb_id']}  {r['motivo']}")

    if not args.aplicar:
        print("\nNada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    DECISIONES.write_text(json.dumps({
        "fecha": datetime.date.today().isoformat(),
        "herramienta": "scripts/reanotar_hotspots_del_ligando.py",
        "procedencia_heredada": (
            "backend/scripts/recure_targets.py corrio discover_pocket_from_pdb sobre los 387 "
            "y minó los 15 residuos mas cercanos al ligando holo AUTODETECTADO. Ningun hotspot "
            "del catalogo viene del RCSB."),
        "criterio": (f"residuos a <={CORTE_CONTACTO} A del ligando que ocupa la caja, "
                     f"solo cuando ese ligando esta a <={CAJA_SOBRE_EL_LIGANDO_A} A del centro"),
        "reanotados": len(decisiones),
        "no_tocados": sorted(sin_testigo, key=lambda r: r["pdb_id"]),
        "decisiones": decisiones,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\naplicado. Evidencia en {DECISIONES.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
