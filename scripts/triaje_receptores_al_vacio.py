"""TRIAJE de los receptores cuya cadena declarada no pone un atomo en la caja.

# Que poblacion es esta, y por que se separa del resto

`revisar_cadena_por_receptor.py` clasifica los 387 objetivos del catalogo. De su
salida sale un subconjunto que NO esta esperando una decision cientifica: esta
averiado. Son los objetivos donde la cadena declarada aporta el **0%** del sitio
y aun asi quedaron sin corregir, porque la herramienta reserva `CORREGIR` para
cuando una sola cadena supera el 90% y estos caen por debajo.

Para ellos `preparer.py` conserva una cadena que no tiene NADA dentro de la caja
de docking. Vina acopla contra espacio vacio y devuelve una afinidad igualmente.
Es el modo de fallo A del doc 71 —el de 1IAS— todavia vivo en el catalogo.

# Que decide este triaje, y que NO decide

Decide **si el objetivo es recuperable y a que coste**, no cual es la cadena
correcta. Separa cuatro situaciones que exigen trabajo distinto:

    RESCATE_MECANICO      una sola cadena concentra el sitio y la evidencia lo
                          respalda. Cambiar la cadena declarada y listo. Es la
                          misma decision que ya se aplico 30 veces en c8a50da,
                          solo que aqui el lider no llega al 90% del umbral.

    RESCATE_MULTICADENA   el sitio lo forman varias cadenas de verdad. El
                          objetivo se recupera SOLO si el receptor multicadena
                          entra en el contrato de preparacion. Hasta entonces
                          no hay cadena unica que declarar y el objetivo sigue
                          averiado.

    REVISAR_LA_CAJA       la sospecha no recae sobre la cadena sino sobre el
                          GRID. Sin ligando en la caja, o con el ligando mas
                          cercano lejos del centro, cambiar de cadena podria
                          estar tapando un centro mal puesto. Recentrar es otra
                          decision, con otra evidencia.

    CONTRADICCION         las dos anotaciones independientes —el ligando y los
                          hotspots— senalan cadenas distintas. No es que el
                          objetivo sea irrecuperable: es que NINGUNA
                          herramienta puede arbitrar entre dos evidencias que
                          se contradicen. Hace falta que un humano mire la
                          estructura.

**Ninguna clase dice «irrecuperable».** Ese veredicto —y la baja del catalogo
que conlleva— no le corresponde a un script: exige mirar la estructura. Lo que
este triaje hace es decir, para cada uno, QUE trabajo haria falta y con que
evidencia se cuenta para hacerlo.

# Las tres evidencias que se cruzan, y por que hacen falta las tres

  1. **El ligando co-cristalizado.** Las cadenas que lo contactan a <=4,5 A
     forman el sitio. Es lo que miraria un cristalografo. Cuando existe, manda.
  2. **El volumen en la caja.** Solo cuando no hay ligando. Es mas debil: dos
     cadenas pueden aportar volumen parecido y solo una formar el bolsillo.
  3. **Los hotspots ya anotados.** Traen prefijo de cadena (`Q:TYR66`) y son
     una anotacion INDEPENDIENTE de las dos anteriores. Si el ligando y los
     hotspots senalan la misma cadena, la decision deja de depender de un solo
     criterio. Si se contradicen, el objetivo no es mecanico por definicion.

La tercera es la que este triaje anade sobre el repaso original, y es la que
convierte un recuento en una decision defendible.

# Uso

    python scripts/triaje_receptores_al_vacio.py [--json salida.json]
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

from revisar_cadena_por_receptor import (  # noqa: E402
    CATALOGO,
    leer_estructura,
    revisar,
)

#: Un lider por debajo de esto no concentra el sitio: lo comparte.
CONCENTRA = 0.80

#: Una cadena que aporta menos que esto al sitio no lo esta formando: lo roza.
#: Sin este suelo, un contacto de dos atomos convierte un monomero en interfaz.
APORTE_MINIMO = 0.15

#: El ligando tiene que estar en el sitio, no en cualquier sitio. Si el mas
#: cercano esta a mas de esto del centro, la caja es sospechosa.
LIGANDO_CENTRADO_A = 6.0


def cadenas_de_los_hotspots(objetivo: dict) -> collections.Counter:
    """Cadenas que nombran los hotspots ya anotados, con su peso.

    Los hotspots vienen como `Q:TYR66`. Los que no traen prefijo de cadena no
    dicen nada sobre este problema y se ignoran en vez de imputarseles una.
    """
    cuenta: collections.Counter = collections.Counter()
    for h in objetivo.get("hotspots") or []:
        nombre = (h.get("name") or "").strip()
        if ":" not in nombre:
            continue
        cadena = nombre.split(":", 1)[0].strip().upper()
        if cadena:
            cuenta[cadena] += 1
    return cuenta


def distancia_al_centro(proteina, cadena: str, centro) -> float | None:
    """Del centro de la caja al atomo mas cercano de esa cadena."""
    mejor = None
    for c, x, y, z in proteina:
        if c != cadena:
            continue
        d = math.dist((x, y, z), centro)
        if mejor is None or d < mejor:
            mejor = d
    return round(mejor, 1) if mejor is not None else None


def triar(objetivo: dict, repaso: dict) -> dict:
    pdb = repaso["pdb_id"]
    declarada = repaso["declarada"]
    centro = (objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"])
    proteina, _ = leer_estructura(pdb)
    cadenas_pdb = sorted({c for c, *_ in proteina})

    reparto = collections.Counter(repaso["contactos_del_ligando"] or repaso["atomos_en_caja"])
    total = sum(reparto.values())
    lider, n_lider = reparto.most_common(1)[0] if reparto else (None, 0)
    prop_lider = n_lider / total if total else 0.0
    forman = [c for c, n in reparto.items() if n / total >= APORTE_MINIMO] if total else []

    hotspots = cadenas_de_los_hotspots(objetivo)
    hs_lider = hotspots.most_common(1)[0][0] if hotspots else None
    hs_declarada = hotspots.get(declarada, 0)
    ligando = repaso["ligando"]
    tiene_ligando = bool(repaso["contactos_del_ligando"])
    lig_centrado = bool(ligando and ligando["dist_centro"] <= LIGANDO_CENTRADO_A)

    # --- El dictamen ---------------------------------------------------------
    # El orden importa: primero se descarta que el problema sea la CAJA, porque
    # cambiar la cadena sobre una caja mal puesta produce un objetivo que parece
    # arreglado y no lo esta.
    if not tiene_ligando:
        clase = "REVISAR_LA_CAJA"
        motivo = ("sin ligando co-cristalizado en la caja: la unica evidencia es el volumen, "
                  "y no distingue el bolsillo de la vecindad")
    elif not lig_centrado:
        clase = "REVISAR_LA_CAJA"
        motivo = (f"el ligando {ligando['residuo']} esta a {ligando['dist_centro']} A del centro: "
                  "la sospecha recae sobre el grid, no sobre la cadena")
    elif hotspots and hs_lider != lider:
        clase = "CONTRADICCION"
        motivo = (f"el ligando senala '{lider}' y los hotspots senalan '{hs_lider}': "
                  f"dos anotaciones independientes se contradicen "
                  f"({sum(hotspots.values())} hotspots anotados en total)")
    elif prop_lider >= CONCENTRA:
        clase = "RESCATE_MECANICO"
        motivo = (f"'{lider}' concentra el {prop_lider*100:.0f}% del sitio"
                  + (f" y {hotspots[lider]} de {sum(hotspots.values())} hotspots lo confirman"
                     if hotspots.get(lider) else " (sin hotspots que lo confirmen)"))
    elif len(forman) >= 2:
        clase = "RESCATE_MULTICADENA"
        motivo = ("el sitio lo forman " + " + ".join(
            f"{c} ({reparto[c]/total*100:.0f}%)" for c in sorted(forman, key=lambda c: -reparto[c])))
    else:
        clase = "CONTRADICCION"
        motivo = f"ninguna cadena concentra el sitio ni lo comparte con claridad ({dict(reparto)})"

    return {
        "pdb_id": pdb,
        "clase_triaje": clase,
        "motivo": motivo,
        "clase_repaso": repaso["clase"],
        "cadena_declarada": declarada,
        "cadena_declarada_existe": declarada in cadenas_pdb,
        "distancia_declarada_al_centro_A": distancia_al_centro(proteina, declarada, centro),
        "cadenas_del_pdb": cadenas_pdb,
        "cadena_sugerida": lider if clase == "RESCATE_MECANICO" else None,
        "cadenas_del_sitio": sorted(forman, key=lambda c: -reparto[c]),
        "reparto_del_sitio": dict(reparto.most_common()),
        "evidencia": repaso["evidencia"],
        "ligando": ligando,
        "hotspots_por_cadena": dict(hotspots.most_common()),
        "hotspots_en_la_declarada": hs_declarada,
        "atomos_en_caja": repaso["atomos_en_caja"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    por_id = {(t.get("pdb_id") or "").upper(): t for t in catalogo}

    afectados = []
    for objetivo in catalogo:
        repaso = revisar(objetivo)
        if not repaso:
            continue
        # La poblacion: declarada al 0% de la caja y sin corregir.
        if repaso["proporcion_declarada_en_caja"] == 0 and repaso["clase"] in {"MULTICADENA", "REVISAR"}:
            afectados.append(triar(por_id[repaso["pdb_id"]], repaso))

    orden = {"RESCATE_MECANICO": 0, "RESCATE_MULTICADENA": 1, "REVISAR_LA_CAJA": 2, "CONTRADICCION": 3}
    afectados.sort(key=lambda r: (orden[r["clase_triaje"]], r["pdb_id"]))

    resumen = collections.Counter(r["clase_triaje"] for r in afectados)
    print(f"receptores que acoplan contra el vacio: {len(afectados)}")
    for k, v in sorted(resumen.items(), key=lambda kv: orden[kv[0]]):
        print(f"  {k:22s} {v}")
    print()
    for r in afectados:
        lig = r["ligando"]
        print(f"{r['pdb_id']}  declara '{r['cadena_declarada']}'"
              f"{'' if r['cadena_declarada_existe'] else ' (NO EXISTE en el PDB)'}"
              f"  ->  {r['clase_triaje']}"
              + (f"  sugerida '{r['cadena_sugerida']}'" if r["cadena_sugerida"] else ""))
        print(f"    {r['motivo']}")
        print(f"    caja: {r['atomos_en_caja']}   declarada a "
              f"{r['distancia_declarada_al_centro_A']} A del centro")
        print(f"    ligando: " + (f"{lig['residuo']} ({lig['atomos']} at, {lig['dist_centro']} A)"
                                  if lig else "ninguno en la caja")
              + f"   hotspots: {r['hotspots_por_cadena']}")
        print()

    if args.json:
        salida = {
            "fecha": "2026-09-02",
            "herramienta": "scripts/triaje_receptores_al_vacio.py",
            "poblacion": "cadena declarada con 0% de los atomos de la caja de docking",
            "resumen": dict(resumen),
            "receptores": afectados,
        }
        pathlib.Path(args.json).write_text(
            json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"detalle en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
