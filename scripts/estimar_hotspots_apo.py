"""Estima los hotspots de las estructuras APO con MolPocket, y lo declara.

# El problema, con nombre y apellido desde hace un ano

`discover_pocket_from_pdb` ancla los 15 hotspots en el ligando co-cristalizado.
En una estructura **apo** no hay ligando que los ancle, y el resultado es una
anotacion suelta: en 5TUN, 1C3P y 6PSD los hotspots cercanos aciertan el centro
de la caja y sobra una cola de residuos a 14-18 A; en 1TW7 estan directamente en
otro sitio, a 16-25 A de la triada catalitica del dimero.

`docs/35_GRID_APO_5TUN_PENDIENTE.md` dejo esto abierto el 2026-08-02 sobre 5TUN.
Aqui se cierra, para los siete que lo tienen.

# El detector no siempre sabe, y hay que dejarle decirlo

Corrido sobre los siete, MolPocket NO da un resultado uniforme, y tratarlo como
si lo diera seria el error:

    1C3P   cavidad rango 1 de 18, druggability 0,79   conserva 15 de 15 hotspots
    5TUN   cavidad rango 1 de 15, druggability 0,81   conserva 15 de 15 hotspots
    1TW7   cavidad rango 1 de 19, druggability 0,10   conserva  0 de 10
    6PSD   cavidad rango 1 de 59, druggability 0,30   conserva  0 de 15
    5T4X   cavidad rango 8 de  8, druggability 0,25   conserva  2 de 15

Son tres situaciones y cada una pide otra cosa:

  * **El detector CONFIRMA la anotacion** (1C3P, 5TUN). Quince de quince, con
    una cavidad bien puntuada. Entonces los hotspots no son el problema: **la
    caja lo es**, y hay dos testigos independientes -la anotacion y el detector-
    contra ella. Se recentra la caja sobre la cavidad. Para 5TUN esto confirma,
    por otra via, lo que `docs/35` midio hace un ano: el grid esta ~7 A fuera.

  * **El detector CONTRADICE con confianza**. Rango 1 y druggability alta pero
    ningun hotspot en comun: ahi si se reanota.

  * **El detector NO SABE** (1TW7, 6PSD, 5T4X). Druggability de 0,10 a 0,30, o
    la cavidad peor puntuada de las ocho que encontro. Sustituir una anotacion
    posiblemente buena por una estimacion mala no es mejorar: es cambiar un
    problema conocido por uno oculto. No se toca, y se dice.

En 1TW7 ademas sabemos por quimica que la caja esta bien -su centro cae sobre la
triada catalitica del dimero, `B:THR26` y `A:THR26` a 2,0 A-, asi que una
cavidad con druggability 0,10 a 12 A de ahi no es candidata a nada.

# La estimacion no es una medida, y por eso se etiqueta

MolPocket -`utils/pocket_detector.py`, reimplementacion propia de fpocket- da los
residuos que revisten una cavidad detectada geometricamente. Eso es una
**prediccion**, no una observacion: no hay cristal que confirme que un farmaco se
una ahi. Su mediana de error sobre PDBbind es de 5-6 A.

Por eso cada receptor tocado aqui queda con `hotspots_source: molpocket_apo`, y
la interfaz lo dice donde el investigador lo va a leer. Presentar una estimacion
geometrica con la misma cara que un contacto cristalografico seria exactamente el
tipo de afirmacion de mas que este trabajo lleva toda la sesion desmontando.

# Que cavidad, y por que no la mejor

`detect_pockets` ordena por score y su top-1 es la mejor cavidad de TODA la
proteina, que no tiene por que ser la del objetivo. Aqui se toma la cavidad
**mas cercana al centro de la caja del catalogo**, porque la caja es el contrato:
es lo que Vina muestrea y lo que el curador eligio como sitio.

Si ninguna cavidad cae cerca de la caja, no se anota nada. Inventar hotspots para
un sitio que el detector no reconoce seria peor que no tener ninguno.

# Uso

    python scripts/estimar_hotspots_apo.py [--aplicar]
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
import math
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ / "backend"))

from revisar_cadena_por_receptor import CATALOGO, ESTRUCTURAS  # noqa: E402

EXPEDIENTE = RAIZ / "docs" / "auditorias" / "expediente_de_receptores.json"
DECISIONES = RAIZ / "docs" / "auditorias" / "hotspots_apo_estimados.json"

FUENTE = "molpocket_apo"

#: A cuantos semilados de caja puede estar la cavidad para aceptarla. Mas lejos,
#: el detector esta describiendo otro bolsillo y no el que se va a acoplar.
CERCA_EN_SEMILADOS = 1.0

#: Para hacerle caso al detector: la mejor cavidad de la proteina y una
#: druggability que no sea de bolsillo marginal. Con 0,10 -1TW7- o 0,25 -5T4X,
#: y ademas la peor de ocho- no se toca una anotacion existente.
DRUGGABILITY_MINIMA = 0.5

#: Cuanto tiene que solapar con la anotacion existente para leerse como
#: CONFIRMACION en vez de como contradiccion.
SOLAPE_QUE_CONFIRMA = 0.5


def leer(pdb_id: str) -> str | None:
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    return None


def estimar(objetivo: dict) -> dict | str:
    from utils.pocket_detector import detect_pockets

    pdb = objetivo["pdb_id"].upper()
    contenido = leer(pdb)
    if contenido is None:
        return "sin estructura local"

    centro = (objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"])
    semilado = min(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]) / 2

    cavidades = detect_pockets(contenido, top_n=None)
    if not cavidades:
        return "MolPocket no encontro ninguna cavidad"

    ordenadas = sorted(cavidades, key=lambda p: math.dist(p.center, centro))
    mejor = ordenadas[0]
    desvio = math.dist(mejor.center, centro)
    if desvio > semilado * CERCA_EN_SEMILADOS:
        return (f"la cavidad mas cercana esta a {desvio:.1f} A del centro "
                f"({desvio / semilado:.2f} semilados): el detector no reconoce este sitio")
    if len(mejor.hotspots) < 5:
        return f"la cavidad solo reviste {len(mejor.hotspots)} residuos"

    return {
        "pdb_id": pdb,
        "hotspots": mejor.hotspots,
        "cavidad": {
            "es_de_fiar": bool(
                sorted(cavidades, key=lambda p: -p.score).index(mejor) == 0
                and float(mejor.druggability) >= DRUGGABILITY_MINIMA),
            "centro": [round(float(v), 2) for v in mejor.center],
            "desvio_del_centro_de_la_caja_A": round(desvio, 1),
            "radio_A": round(float(mejor.radius), 1),
            "score": round(float(mejor.score), 3),
            "druggability": round(float(mejor.druggability), 3),
            "n_esferas": int(mejor.n_spheres),
            "rango_por_score": sorted(cavidades, key=lambda p: -p.score).index(mejor) + 1,
            "cavidades_totales": len(cavidades),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    expediente = json.loads(EXPEDIENTE.read_text(encoding="utf-8"))["receptores"]
    # Los que fallan por la anotacion del sitio Y no tienen ligando que la ancle.
    candidatos = {
        e["pdb_id"] for e in expediente
        if not e.get("ligando")
        and any(f.startswith(("D2", "D3", "D4")) for f in e["fallos"])
    }
    if not candidatos:
        print("no hay apos que estimar")
        return 0

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    decisiones, rechazados = [], []
    for objetivo in catalogo:
        pdb = objetivo["pdb_id"].upper()
        if pdb not in candidatos:
            continue
        r = estimar(objetivo)
        if isinstance(r, str):
            rechazados.append({"pdb_id": pdb, "motivo": r})
            continue
        antes = [h["name"] for h in objetivo.get("hotspots") or []]
        despues = [h["name"] for h in r["hotspots"]]
        comunes = sorted(set(antes) & set(despues))
        solape = len(comunes) / len(antes) if antes else 0.0
        fiable = r["cavidad"]["es_de_fiar"]

        if not fiable:
            veredicto, accion = "NO_CONCLUYENTE", (
                "el detector no da una cavidad de fiar; no se toca la anotacion")
        elif solape >= SOLAPE_QUE_CONFIRMA:
            veredicto, accion = "CONFIRMA_LOS_HOTSPOTS", (
                "la anotacion es buena y la caja no: recentrarla sobre la cavidad")
        else:
            veredicto, accion = "REANOTA", "se sustituyen los hotspots por los de la cavidad"

        decisiones.append({
            "pdb_id": pdb, "veredicto": veredicto, "accion": accion,
            "solape_con_lo_anotado": round(solape, 2),
            "hotspots_antes": antes,
            "hotspots_despues": despues if veredicto == "REANOTA" else None,
            "conservados": comunes,
            "cavidad": r["cavidad"],
        })
        if args.aplicar and veredicto == "REANOTA":
            objetivo["hotspots"] = r["hotspots"]
            objetivo["hotspots_source"] = FUENTE
        elif args.aplicar and veredicto == "CONFIRMA_LOS_HOTSPOTS":
            centro = r["cavidad"]["centro"]
            objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"] = centro

    for d in decisiones:
        c = d["cavidad"]
        print(f"{d['pdb_id']}  {d['veredicto']}")
        print(f"    cavidad a {c['desvio_del_centro_de_la_caja_A']} A del centro"
              f"  ·  druggability {c['druggability']}"
              f"  ·  rango {c['rango_por_score']} de {c['cavidades_totales']}"
              f"  ·  conserva {len(d['conservados'])} de {len(d['hotspots_antes'])}")
        print(f"    {d['accion']}")
    for r in rechazados:
        print(f"{r['pdb_id']}  NO se anota: {r['motivo']}")
    print(f"\nestimados: {len(decisiones)}   sin estimar: {len(rechazados)}")

    if not args.aplicar:
        print("Nada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    DECISIONES.write_text(json.dumps({
        "fecha": datetime.date.today().isoformat(),
        "herramienta": "scripts/estimar_hotspots_apo.py",
        "motor": "utils/pocket_detector.py (MolPocket), mediana de error 5-6 A sobre PDBbind",
        "naturaleza": ("ESTIMACION geometrica, no observacion. No hay cristal que confirme "
                       "que un farmaco se una ahi; la interfaz lo declara."),
        "criterio": ("la cavidad detectada mas cercana al centro de la caja del catalogo, "
                     f"si cae dentro de {CERCA_EN_SEMILADOS} semilados"),
        "estimados": len(decisiones),
        "sin_estimar": rechazados,
        "decisiones": decisiones,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"aplicado. Evidencia en {DECISIONES.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
