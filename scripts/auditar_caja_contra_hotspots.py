"""AUDITORIA: la caja de docking, contra los residuos que dicen donde esta el sitio.

# SUPERADO por D2 de `expediente_de_receptores.py`. Leer esto antes de usarlo.

El criterio de este script -que fraccion de los ATOMOS de hotspot cae fuera del
cubo- marcaba 28 objetivos y estaba mal calibrado: un residuo del borde del
bolsillo apunta su cadena lateral hacia fuera POR CONSTRUCCION, y siete de esos
28 tenian su ligando cristalizado a 0,0 A del centro de la caja.

El expediente lo reemplazo por la pregunta decisiva -si el ligando
co-cristalizado CABE ENTERO en la caja: 272 de 273 caben, con 8,1 A de margen
mediano- mas un desvio de centroide en semilados. Quedan ocho objetivos, y los
ocho tienen algo roto de verdad.

Este script se conserva porque produjo `docs/auditorias/caja_contra_hotspots.json`
y porque su medida por atomos sigue siendo util para mirar UN receptor de cerca.
Su VEREDICTO, en cambio, ya no es el del catalogo.

# La pregunta que ninguna herramienta anterior respondia

`revisar_cadena_por_receptor.py` pregunta QUE CADENA forma el sitio. Si la caja
esta mal puesta, esa pregunta no tiene respuesta buena: mide bien una cadena
equivocada. Para los 14 objetivos que el triaje mando a `REVISAR_LA_CAJA` -sin
ligando co-cristalizado dentro de la caja- hace falta preguntar antes otra cosa:

    **¿La caja esta donde dicen los hotspots que esta el sitio?**

Los hotspots son una anotacion INDEPENDIENTE del grid: los residuos que alguien
identifico como criticos para la union, con su cadena (`Q:TYR66`). Si la caja
esta sobre ellos, la caja es buena y el problema es de cadena. Si esta lejos, es
el grid lo que hay que reparar, y cambiar la cadena solo taparia el defecto.

# Esto no es codigo nuevo: es el visor, medido

`Web3DViewer.tsx:985` ya dibuja esa envolvente -centroide de los hotspots
ponderado por importancia, radio hasta el mas lejano- y la superpone a la caja
de docking. Lo que el investigador ve de un vistazo, aqui se mide para los 387.
El visor lo llama «ayuda de orientacion»; como criterio de auditoria es
exactamente lo que hace falta.

# Los tres veredictos

    CAJA_CONFIRMADA      el centroide cae dentro de la caja y practicamente
                         todos los atomos de hotspot tambien. Dos anotaciones
                         independientes -grid y hotspots- se sostienen.
    CAJA_CORTA           el centroide cae dentro pero una parte apreciable de
                         los atomos de hotspot queda fuera. O la caja se queda
                         corta, o los hotspots anotados abarcan mas de un
                         bolsillo.
    CAJA_EN_OTRO_SITIO   el centroide cae FUERA de la caja. El grid apunta a un
                         lugar que la anotacion de hotspots no reconoce.

# Por que el criterio NO es la distancia del centroide

La primera version comparaba la envolvente entera -centroide mas radio- contra
la caja, y daba 24 de 25 «desplazadas». Era un artefacto: el radio va hasta el
hotspot MAS LEJANO, y quince residuos que revisten un bolsillo tienen un radio
de 12 a 24 A por pura geometria, no porque la caja este mal. Lo que de verdad
distingue es CUANTOS atomos de hotspot se salen: 0 de 113 es una caja buena
aunque el radio no quepa; 78 de 315 es otra cosa.

Lo dejo escrito porque el error apunta al mismo sitio que el resto de este
trabajo: una medida que parece razonable y afirma algo falso.

# Una limitacion, dicha antes

Los hotspots no son verdad revelada: son otra anotacion, y el doc 71 la dejo sin
verificar. Que caja y hotspots discrepen dice que UNA de las dos esta mal, no
CUAL. Por eso este script no corrige nada: separa los casos en los que las dos
anotaciones se sostienen entre si de los que exigen abrir la estructura.

# Uso

    python scripts/auditar_caja_contra_hotspots.py [--solo-triaje] [--json f.json]
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

from revisar_cadena_por_receptor import CATALOGO, ESTRUCTURAS  # noqa: E402

TRIAJE = RAIZ / "docs" / "auditorias" / "triaje_receptores_al_vacio.json"

#: Que fraccion de los atomos de hotspot puede quedar fuera de la caja sin que
#: la caja deje de ser buena. No es cero: un residuo del borde del bolsillo
#: asoma medio anillo aromatico fuera del cubo sin que eso signifique nada.
FUERA_TOLERABLE = 0.10


def atomos_de_los_hotspots(pdb_id: str, hotspots: list[dict]) -> dict[str, list[tuple]]:
    """Coordenadas de cada hotspot, buscado en SU PROPIA cadena.

    La diferencia con `list_targets` importa: alli las coordenadas se buscan
    filtrando por `target.chain`, asi que un hotspot `H:THR1` en un receptor que
    declara 'A' encuentra el THR1 de A -otro residuo, otras coordenadas- o no
    encuentra nada. Aqui se usa la cadena que el propio hotspot declara, que es
    la unica lectura que no inventa.
    """
    buscados: dict[tuple[str, str], str] = {}
    for h in hotspots or []:
        nombre = (h.get("name") or "").strip().upper()
        if ":" not in nombre:
            continue
        cadena, residuo = nombre.split(":", 1)
        numero = "".join(ch for ch in residuo if ch.isdigit() or ch == "-")
        if not numero:
            continue
        buscados[(cadena.strip(), numero)] = nombre

    encontrados: dict[str, list[tuple]] = collections.defaultdict(list)
    for nombre_archivo in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre_archivo
        if not f.is_file():
            continue
        abrir = gzip.open if nombre_archivo.endswith(".gz") else open
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                if not linea.startswith("ATOM"):
                    continue
                clave = (linea[21].strip(), linea[22:26].strip())
                etiqueta = buscados.get(clave)
                if not etiqueta:
                    continue
                try:
                    encontrados[etiqueta].append(
                        (float(linea[30:38]), float(linea[38:46]), float(linea[46:54])))
                except ValueError:
                    continue
        break
    return dict(encontrados)


def auditar(objetivo: dict) -> dict | None:
    pdb = (objetivo.get("pdb_id") or "").upper()
    hotspots = objetivo.get("hotspots") or []
    centro = (objetivo.get("grid_center_x"), objetivo.get("grid_center_y"),
              objetivo.get("grid_center_z"))
    if centro[0] is None or not hotspots:
        return None
    medio = (float(objetivo.get("grid_size_x") or 25.0) / 2.0,
             float(objetivo.get("grid_size_y") or 25.0) / 2.0,
             float(objetivo.get("grid_size_z") or 25.0) / 2.0)

    coords = atomos_de_los_hotspots(pdb, hotspots)
    if len(coords) < 2:
        return {"pdb_id": pdb, "veredicto": "SIN_HOTSPOTS_LOCALIZABLES",
                "hotspots_declarados": len(hotspots), "hotspots_encontrados": len(coords)}

    planos = [p for lista in coords.values() for p in lista]
    cx = sum(p[0] for p in planos) / len(planos)
    cy = sum(p[1] for p in planos) / len(planos)
    cz = sum(p[2] for p in planos) / len(planos)
    radio = max(math.dist(p, (cx, cy, cz)) for p in planos)
    desvio = math.dist((cx, cy, cz), centro)

    dentro = all(abs(c - g) <= m for c, g, m in zip((cx, cy, cz), centro, medio))
    fuera = sum(1 for p in planos
                if any(abs(p[i] - centro[i]) > medio[i] for i in range(3)))
    fraccion_fuera = fuera / len(planos)

    if not dentro:
        veredicto = "CAJA_EN_OTRO_SITIO"
    elif fraccion_fuera <= FUERA_TOLERABLE:
        veredicto = "CAJA_CONFIRMADA"
    else:
        veredicto = "CAJA_CORTA"

    return {
        "pdb_id": pdb,
        "veredicto": veredicto,
        "hotspots_declarados": len(hotspots),
        "hotspots_encontrados": len(coords),
        "centroide_hotspots": [round(cx, 2), round(cy, 2), round(cz, 2)],
        "centro_de_la_caja": [round(v, 2) for v in centro],
        "desvio_A": round(desvio, 1),
        "radio_envolvente_A": round(radio, 1),
        "atomos_de_hotspot_fuera_de_la_caja": fuera,
        "atomos_de_hotspot": len(planos),
        "fraccion_fuera": round(fraccion_fuera, 3),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solo-triaje", action="store_true",
                    help="solo los receptores del triaje al vacio")
    ap.add_argument("--json", type=str, default=None)
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    filtro: set[str] | None = None
    if args.solo_triaje:
        triaje = json.loads(TRIAJE.read_text(encoding="utf-8"))
        filtro = {r["pdb_id"] for r in triaje["receptores"]}

    filas = []
    for objetivo in catalogo:
        pdb = (objetivo.get("pdb_id") or "").upper()
        if filtro is not None and pdb not in filtro:
            continue
        fila = auditar(objetivo)
        if fila:
            filas.append(fila)

    orden = {"CAJA_EN_OTRO_SITIO": 0, "CAJA_CORTA": 1,
             "SIN_HOTSPOTS_LOCALIZABLES": 2, "CAJA_CONFIRMADA": 3}
    filas.sort(key=lambda r: (orden[r["veredicto"]], -r.get("fraccion_fuera", 0)))

    resumen = collections.Counter(r["veredicto"] for r in filas)
    print(f"receptores auditados: {len(filas)}")
    for k, v in sorted(resumen.items(), key=lambda kv: orden[kv[0]]):
        print(f"  {k:26s} {v}")
    print()
    for r in filas:
        if r["veredicto"] == "CAJA_CONFIRMADA":
            continue
        print(f"{r['pdb_id']}  {r['veredicto']}", end="")
        if "desvio_A" in r:
            print(f"   centroide a {r['desvio_A']} A del centro de la caja"
                  f"   envolvente r={r['radio_envolvente_A']} A"
                  f"   {r['atomos_de_hotspot_fuera_de_la_caja']}/{r['atomos_de_hotspot']}"
                  " atomos de hotspot fuera")
        else:
            print(f"   {r['hotspots_encontrados']} de {r['hotspots_declarados']} hotspots"
                  " localizados en su propia cadena")

    if args.json:
        pathlib.Path(args.json).write_text(json.dumps({
            "fecha": "2026-09-02",
            "herramienta": "scripts/auditar_caja_contra_hotspots.py",
            "criterio": ("envolvente de los hotspots -centroide y radio, como la dibuja "
                         "Web3DViewer.tsx:985- contra la caja de docking del catalogo"),
            "resumen": dict(resumen),
            "receptores": filas,
        }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\ndetalle en {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
