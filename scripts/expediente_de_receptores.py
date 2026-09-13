"""EXPEDIENTE: cada uno de los 387 receptores, contra todo lo que sabemos comprobar.

# Para que existe

«Los 387 tienen que estar bien» necesita una definicion de «bien» que no dependa
de quien mire. Este script la fija: cinco comprobaciones, cada una medida sobre
el PDB del RCSB, y un veredicto por receptor. Lo que pasa las cinco esta
cerrado; lo que falla alguna entra en una lista finita que se puede quemar uno a
uno.

No sustituye a las herramientas anteriores: las junta. `revisar_cadena_por_
receptor.py` decide cadena, `auditar_caja_contra_hotspots.py` decide grid; aqui
se corren las dos sobre el mismo recorrido de archivos y se anade la unica
comprobacion que faltaba —si los hotspots anotados tocan de verdad el ligando—.

# Las cinco comprobaciones, y que defecto caza cada una

    D1  la cadena que se prepara forma el sitio
        Si no, `preparer.py` conserva una cadena que no esta en el bolsillo y
        Vina acopla contra media cavidad o contra el vacio. Doc 71, modo A y C.

    D2  la caja de docking contiene el sitio
        Dos preguntas, y la primera es la decisiva cuando hay con que
        responderla:
          (a) si hay ligando co-cristalizado en la caja, tiene que caber
              ENTERO. Es el requisito fisico: el espacio de poses debe
              contener al ligando que ya se sabe que se une.
          (b) el centroide de los hotspots no puede estar a mas de 0,6
              semilados del centro. Por encima de eso, el grid y la anotacion
              describen lugares distintos.

        ESTE CRITERIO SE AFLOJO, y conviene decirlo. La primera version contaba
        cuantos ATOMOS de hotspot caian fuera del cubo y marcaba 28 objetivos.
        Estaba mal: un residuo del borde del bolsillo apunta su cadena lateral
        hacia fuera POR CONSTRUCCION, y siete de los 28 tenian su ligando
        cristalizado a 0,0 A del centro de la caja. No era un defecto, era
        geometria. El criterio nuevo no es solo mas laxo: atrapa un fallo que el
        viejo no veia -6MEO, cuya caja NO contiene su ligando- y descarta veinte
        falsos positivos. Los umbrales salen de la distribucion medida sobre los
        385: margen ligando-pared de 2,8 A el minimo y 8,1 A la mediana;
        desvio del centroide de 0,18 semilados la mediana y 0,43 el p95, con un
        hueco limpio entre 0,50 y 0,63.

    D3  los hotspots anotados tocan el ligando co-cristalizado
        Un hotspot es, por definicion, un residuo que participa en la union. Si
        no toca el ligando del cristal, no lo es. Solo se puede comprobar en los
        273 objetivos que tienen ligando en la caja.

    D4  los hotspots existen en la estructura, en su propia cadena
        Un hotspot que no se localiza no dibuja el sitio en el visor ni empareja
        en el dossier. `list_targets` los busca filtrando por `target.chain`, asi
        que un `H:THR1` en un receptor que declara 'A' encuentra otro residuo o
        no encuentra ninguno; aqui se busca en la cadena que el hotspot declara.

    D5  hay receptor donde se va a acoplar
        Una caja de 22 A sobre un cristal de seis residuos es un 97% de vacio.
        No es un defecto de anotacion: es que el objeto no es un receptor.

# Lo que este expediente NO comprueba

La integridad de las estructuras -ya la comprueba
`verificar_integridad_estructuras.py` contra el RCSB- ni si el grid esta
calibrado contra afinidad experimental, que es otra cosa y vive en `calibracion`.

# Uso

    python scripts/expediente_de_receptores.py [--json f.json] [--solo-fallos]
"""

from __future__ import annotations

import argparse
import collections
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
#: Cuanto puede alejarse del centro el centroide de los hotspots, en semilados
#: de la caja. La mediana del catalogo es 0,18 y el p95 0,43; por encima de 0,6
#: solo quedan siete, y son los que al abrirlos tienen algo roto de verdad.
DESVIO_TOLERABLE = 0.6

#: Cuantos hotspots tienen que tocar el ligando para que la anotacion valga.
#: La mediana del catalogo es 1,0 -todos tocan-, asi que medio es un suelo
#: generoso: por debajo, los hotspots describen otra cosa.
ACIERTO_MINIMO = 0.5

#: Atomos de proteina que tiene que haber dentro de la caja para que haya algo
#: contra lo que acoplar. La mediana del catalogo es 669 y el segundo peor caso
#: legitimo tiene 153; por debajo de cien solo quedan dos cristales de peptido
#: de seis residuos, que no son receptores. El suelo no separa «poco» de
#: «mucho»: separa «hay proteina» de «no la hay».
ATOMOS_MINIMOS_EN_LA_CAJA = 100


def leer(pdb_id: str):
    """Residuos de proteina y heteroatomos candidatos a ligando, en una pasada."""
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        residuos: dict[tuple[str, int], list[tuple]] = collections.defaultdict(list)
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
                    residuos[(linea[21].strip(), numero)].append(punto)
                else:
                    if (nombre_res in NO_SON_LIGANDO or nombre_res in RESIDUOS_MODIFICADOS
                            or nombre_res.startswith(PREFIJOS_DETERGENTE)):
                        continue
                    heteros[(nombre_res, linea[21], numero)].append(punto)
        return residuos, heteros
    return None


def claves_de_hotspots(objetivo: dict) -> list[tuple[str, int]]:
    """`Q:TYR66` -> ('Q', 66). Los que no traen cadena no se pueden comprobar."""
    claves = []
    for h in objetivo.get("hotspots") or []:
        nombre = (h.get("name") or "").strip().upper()
        if ":" not in nombre:
            continue
        cadena, resto = nombre.split(":", 1)
        numero = "".join(c for c in resto if c.isdigit())
        if numero:
            claves.append((cadena.strip(), int(numero)))
    return claves


def instruir(objetivo: dict) -> dict:
    pdb = (objetivo.get("pdb_id") or "").upper()
    expediente: dict = {"pdb_id": pdb, "fallos": []}

    datos = leer(pdb)
    if datos is None:
        expediente["fallos"].append("SIN_ESTRUCTURA")
        return expediente
    residuos, heteros = datos

    centro = (objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"])
    medio = (float(objetivo.get("grid_size_x") or 25.0) / 2.0,
             float(objetivo.get("grid_size_y") or 25.0) / 2.0,
             float(objetivo.get("grid_size_z") or 25.0) / 2.0)

    # ── D5: hay receptor donde se va a acoplar ──────────────────────────────
    en_la_caja = sum(
        1 for puntos in residuos.values() for p in puntos
        if all(abs(p[i] - centro[i]) <= medio[i] for i in range(3))
    )
    expediente["atomos_en_la_caja"] = en_la_caja
    if en_la_caja < ATOMOS_MINIMOS_EN_LA_CAJA:
        expediente["fallos"].append("D5_NO_HAY_RECEPTOR_EN_LA_CAJA")

    # ── D1: la cadena que se prepara forma el sitio ──────────────────────────
    declarada = (objetivo.get("chain") or "").strip().upper()
    del_sitio = objetivo.get("site_chains") or []
    expediente["cadena"] = declarada
    expediente["cadenas_del_sitio"] = del_sitio
    if declarada not in del_sitio:
        expediente["fallos"].append("D1_LA_CADENA_NO_FORMA_EL_SITIO")

    # ── El ligando co-cristalizado que ocupa la caja ─────────────────────────
    ligando = None
    mejor, mejor_dist = None, 1e9
    for clave, coords in heteros.items():
        if len(coords) < 6:
            continue
        medio_lig = tuple(sum(p[i] for p in coords) / len(coords) for i in range(3))
        d = math.dist(medio_lig, centro)
        if d < mejor_dist:
            mejor, mejor_dist = (clave, coords), d
    if mejor and mejor_dist <= max(medio):
        # Cuanto sobra entre el atomo mas extremo del ligando y la pared. Si es
        # negativo, el ligando NO cabe: el espacio de poses excluye una parte
        # del unico modo de union que conocemos con certeza.
        holgura = min(medio[i] - max(abs(p[i] - centro[i]) for p in mejor[1]) for i in range(3))
        ligando = {"residuo": mejor[0][0], "dist_centro": round(mejor_dist, 1),
                   "holgura_hasta_la_pared_A": round(holgura, 1)}

    # ── D4: los hotspots existen, en su propia cadena ────────────────────────
    claves = claves_de_hotspots(objetivo)
    localizados = [k for k in claves if k in residuos]
    expediente["hotspots_declarados"] = len(objetivo.get("hotspots") or [])
    expediente["hotspots_localizados"] = len(localizados)
    if len(localizados) < 2:
        expediente["fallos"].append("D4_HOTSPOTS_NO_LOCALIZABLES")

    # ── D2: la caja contiene el sitio ────────────────────────────────────────
    semilado = min(medio)
    if ligando and ligando["holgura_hasta_la_pared_A"] < 0:
        expediente["fallos"].append("D2_EL_LIGANDO_NO_CABE_EN_LA_CAJA")
    if len(localizados) >= 2:
        puntos = [p for k in localizados for p in residuos[k]]
        centroide = tuple(sum(p[i] for p in puntos) / len(puntos) for i in range(3))
        desvio = math.dist(centroide, centro)
        expediente["desvio_centroide_A"] = round(desvio, 1)
        expediente["desvio_en_semilados"] = round(desvio / semilado, 2)
        expediente["fraccion_de_hotspot_fuera_de_la_caja"] = round(
            sum(1 for p in puntos
                if any(abs(p[i] - centro[i]) > medio[i] for i in range(3))) / len(puntos), 3)
        if desvio / semilado > DESVIO_TOLERABLE:
            expediente["fallos"].append("D2_LA_CAJA_Y_LOS_HOTSPOTS_NO_COINCIDEN")

    # ── D3: los hotspots tocan el ligando ────────────────────────────────────
    if ligando and localizados:
        corte2 = CORTE_CONTACTO ** 2
        coords_lig = mejor[1]
        del_cristal = {
            k for k, v in residuos.items()
            if any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 <= corte2
                   for p in v for q in coords_lig)
        }
        aciertos = sum(1 for k in localizados if k in del_cristal)
        expediente["hotspots_que_tocan_el_ligando"] = f"{aciertos}/{len(localizados)}"
        expediente["residuos_del_sitio_cristalografico"] = len(del_cristal)
        if aciertos / len(localizados) < ACIERTO_MINIMO:
            expediente["fallos"].append("D3_LOS_HOTSPOTS_NO_TOCAN_EL_LIGANDO")

    expediente["ligando"] = ligando
    expediente["evidencia"] = objetivo.get("site_evidence")
    expediente["veredicto"] = "PASA" if not expediente["fallos"] else "REVISAR"
    return expediente


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=str, default=None)
    ap.add_argument("--solo-fallos", action="store_true")
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    expedientes = [instruir(t) for t in catalogo]

    pasan = [e for e in expedientes if e["veredicto"] == "PASA"]
    fallan = [e for e in expedientes if e["veredicto"] != "PASA"]
    fallan.sort(key=lambda e: (-len(e["fallos"]), e["pdb_id"]))

    por_defecto: collections.Counter = collections.Counter()
    for e in fallan:
        for f in e["fallos"]:
            por_defecto[f] += 1

    print(f"receptores: {len(expedientes)}   PASA: {len(pasan)}   REVISAR: {len(fallan)}")
    for k, v in por_defecto.most_common():
        print(f"  {k:36s} {v}")
    print()
    for e in fallan:
        print(f"{e['pdb_id']}  {', '.join(e['fallos'])}")
        if not args.solo_fallos:
            print(f"    prepara '{e.get('cadena')}' · sitio {e.get('cadenas_del_sitio')}"
                  f" · hotspots {e.get('hotspots_localizados')}/{e.get('hotspots_declarados')}"
                  + (f" · tocan el ligando {e['hotspots_que_tocan_el_ligando']}"
                     if "hotspots_que_tocan_el_ligando" in e else "")
                  + (f" · centroide a {e['desvio_centroide_A']} A"
                     if "desvio_centroide_A" in e else ""))

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({
            "fecha": "2026-09-02",
            "herramienta": "scripts/expediente_de_receptores.py",
            "comprobaciones": {
                "D1": "la cadena que se prepara forma el sitio",
                "D2": ("la caja contiene el sitio: el ligando co-cristalizado cabe entero, "
                       f"y el centroide de los hotspots no se aleja mas de {DESVIO_TOLERABLE} "
                       "semilados del centro"),
                "D3": "los hotspots tocan el ligando co-cristalizado",
                "D4": "los hotspots existen en la estructura, en su propia cadena",
                "D5": "hay atomos de receptor dentro de la caja de docking",
            },
            "resumen": {"pasan": len(pasan), "revisar": len(fallan),
                        "por_defecto": dict(por_defecto)},
            "receptores": expedientes,
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nexpediente completo en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
