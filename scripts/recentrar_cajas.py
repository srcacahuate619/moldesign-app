"""Recentra la caja de docking sobre el ligando, cuando dos testigos lo piden.

# El estandar que el propio catalogo ya sigue

Medido sobre los 278 objetivos que tienen ligando dentro de su caja, la distancia
entre el centro de la caja y el centro del ligando es:

    mediana 0,0 A     p90 0,0 A     p95 4,8 A

Es decir: **nueve de cada diez cajas de este catalogo estan centradas EXACTAMENTE
sobre el ligando co-cristalizado.** No hace falta inventar un criterio nuevo; hay
que aplicar el que ya rige, a los que se quedaron fuera.

# Por que NO basta con «el ligando esta lejos»

Veinte objetivos tienen su ligando a mas de 3 A del centro, y seis de ellos a mas
de 19 A —5YUA a 46,7 A—. Recentrarlos todos seria un error: en esos seis **los
hotspots caen sobre la caja**, a 0,18-0,50 semilados. La caja apunta a un sitio
que la anotacion reconoce, y el ligando lejano esta en OTRO bolsillo de la misma
proteina. Moverla ahi cambiaria el objetivo cientifico del receptor sin que nadie
lo haya pedido.

Un citocromo P450 lo ilustra al reves: en 2VE3 el hemo y el acido retinoico estan
en sitios distintos, y cual es «el sitio» lo decide la caja, no la cercania.

# La regla: dos testigos independientes contra uno

Se recentra cuando **el ligando y los hotspots coinciden entre si y discrepan de
la caja**:

    1. hay un ligando unido de verdad -al menos cinco residuos en contacto-;
    2. su centro esta a mas de 3 A del centro de la caja;
    3. y el centroide de los hotspots esta MAS CERCA de ese ligando que del
       centro de la caja, por un margen que no sea ruido.

La tercera condicion es la que impide mover cajas legitimas: exige que la
anotacion de hotspots —que es independiente del grid— se ponga del lado del
ligando. Con dos testigos de acuerdo, el que sobra es el grid.

El margen no es decorativo. Sin el, 6SX7 entraba con los hotspots a 5,9 A de la
caja y 5,3 A del ligando: seis decimas de diferencia no son un testigo, son la
misma distancia medida dos veces.

# El desempate entre copias simetricas

En 7ZYJ y 8WGR el ligando aparece dos veces, ambas copias unidas y ambas a la
MISMA distancia del centro de la caja: 15,9 y 6,9 A respectivamente. `elegir_
ligando` no puede desempatarlas -por diseno, porque alli los hotspots no son
testigo-. Aqui si lo son, y ya se exige que lo sean: entre copias empatadas se
toma la que los hotspots senalan. En 8WGR una esta a 0,8 A del centroide de
hotspots y la otra a 14,3 A; no es un empate real, es que la caja mira al hueco
entre las dos.

# El tamano

Se conserva el que tiene, salvo que el ligando no quepa con holgura. El p10 del
catalogo es 4,2 A de margen entre el ligando y la pared; por debajo de eso la
caja se agranda hasta darselo. Una caja que roza el ligando no deja espacio para
explorar poses.

# Lo que esto cambia, dicho antes

Recentrar cambia el sitio que se acopla, y por tanto **cambia los numeros de
cualquier resultado anterior sobre ese receptor**. Exige el corrigendum del
doc 71 §2.3 sobre lo ya sellado. No es una correccion cosmetica.

# Uso

    python scripts/recentrar_cajas.py [--aplicar]
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
    MIN_CONTACTOS_PARA_ESTAR_UNIDO,
    NO_SON_LIGANDO,
    PREFIJOS_DETERGENTE,
    RESIDUOS_MODIFICADOS,
    elegir_ligando,
)

DECISIONES = RAIZ / "docs" / "auditorias" / "cajas_recentradas.json"

#: Por debajo de esto la caja ya esta sobre el ligando y moverla es ruido.
DESVIO_QUE_IMPORTA_A = 3.0
#: Margen minimo entre el ligando y la pared. Es el p10 del catalogo.
MARGEN_MINIMO_A = 4.2
#: Cuanto mas cerca del ligando que de la caja tienen que estar los hotspots
#: para contar como testigo. Menos que esto es la misma distancia con ruido.
MARGEN_DEL_TESTIGO_A = 1.5


def leer(pdb_id: str):
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        proteina, residuos = [], collections.defaultdict(list)
        heteros: dict[tuple, list[tuple]] = collections.defaultdict(list)
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                if not linea.startswith(("ATOM", "HETATM")):
                    continue
                try:
                    x, y, z = float(linea[30:38]), float(linea[38:46]), float(linea[46:54])
                    numero = int(linea[22:26])
                except ValueError:
                    continue
                cadena = linea[21].strip()
                nombre_res = linea[17:20].strip().upper()
                if linea.startswith("ATOM"):
                    proteina.append((cadena, x, y, z))
                    residuos[(cadena, numero)].append((x, y, z))
                else:
                    if (nombre_res in NO_SON_LIGANDO or nombre_res in RESIDUOS_MODIFICADOS
                            or nombre_res.startswith(PREFIJOS_DETERGENTE)):
                        continue
                    heteros[(nombre_res, cadena, numero)].append((x, y, z))
        return proteina, dict(residuos), dict(heteros)
    return None


def centroide_de_hotspots(objetivo: dict, residuos: dict):
    puntos = []
    for h in objetivo.get("hotspots") or []:
        nombre = (h.get("name") or "").strip().upper()
        if ":" not in nombre:
            continue
        cadena, resto = nombre.split(":", 1)
        numero = "".join(c for c in resto if c.isdigit())
        if numero:
            puntos += residuos.get((cadena.strip(), int(numero)), [])
    if len(puntos) < 10:
        return None
    return tuple(sum(p[i] for p in puntos) / len(puntos) for i in range(3))


def examinar(objetivo: dict) -> dict | None:
    pdb = objetivo["pdb_id"].upper()
    datos = leer(pdb)
    if datos is None:
        return None
    proteina, residuos, heteros = datos
    centro = (objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"])
    lados = (objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"])

    # Sin radio: interesa el ligando aunque hoy caiga fuera de la caja.
    elegido = elegir_ligando(heteros, proteina, centro, radio=float("inf"))
    if not elegido:
        return None
    clave, coords, desvio = elegido
    if desvio <= DESVIO_QUE_IMPORTA_A:
        return None

    ctr_hs = centroide_de_hotspots(objetivo, residuos)
    if ctr_hs is None:
        return None

    # Copias simetricas empatadas en distancia: desempata el centroide de
    # hotspots, que aqui ya es testigo obligatorio.
    empatadas = [
        (k, v) for k, v in heteros.items()
        if k[0] == clave[0]
        and abs(math.dist(tuple(sum(p[i] for p in v) / len(v) for i in range(3)), centro)
                - desvio) < 0.5
    ]
    if len(empatadas) > 1:
        clave, coords = min(
            empatadas,
            key=lambda kv: math.dist(
                tuple(sum(p[i] for p in kv[1]) / len(kv[1]) for i in range(3)), ctr_hs))
        desvio = math.dist(
            tuple(sum(p[i] for p in coords) / len(coords) for i in range(3)), centro)

    # (1) tiene que estar unido de verdad
    corte2 = CORTE_CONTACTO ** 2
    contactos = sum(
        1 for puntos in residuos.values()
        if any((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 <= corte2
               for p in puntos for q in coords))
    if contactos < MIN_CONTACTOS_PARA_ESTAR_UNIDO:
        return None

    # (3) los hotspots tienen que ponerse del lado del ligando, y con margen
    nuevo = tuple(sum(p[i] for p in coords) / len(coords) for i in range(3))
    d_hs_ligando = math.dist(ctr_hs, nuevo)
    d_hs_caja = math.dist(ctr_hs, centro)
    if d_hs_caja - d_hs_ligando < MARGEN_DEL_TESTIGO_A:
        return None

    # El tamano: el que tiene, salvo que el ligando no quepa con margen.
    extremos = [max(abs(p[i] - nuevo[i]) for p in coords) for i in range(3)]
    nuevos_lados = [max(lados[i], 2 * (extremos[i] + MARGEN_MINIMO_A)) for i in range(3)]

    return {
        "pdb_id": pdb,
        "ligando": clave[0],
        "contactos_del_ligando": contactos,
        "centro_antes": [round(v, 3) for v in centro],
        "centro_despues": [round(v, 3) for v in nuevo],
        "desplazamiento_A": round(desvio, 1),
        "lados_antes": [round(v, 1) for v in lados],
        "lados_despues": [round(v, 1) for v in nuevos_lados],
        "hotspots_al_ligando_A": round(d_hs_ligando, 1),
        "hotspots_a_la_caja_vieja_A": round(d_hs_caja, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    decisiones = []
    for objetivo in catalogo:
        d = examinar(objetivo)
        if not d:
            continue
        decisiones.append(d)
        if args.aplicar:
            objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"] = \
                (round(v, 3) for v in d["centro_despues"])
            objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"] = \
                (round(v, 1) for v in d["lados_despues"])

    for d in decisiones:
        print(f"{d['pdb_id']}  ligando {d['ligando']} ({d['contactos_del_ligando']} residuos)"
              f"   la caja se mueve {d['desplazamiento_A']} A")
        print(f"    los hotspots estaban a {d['hotspots_a_la_caja_vieja_A']} A de la caja vieja"
              f" y a {d['hotspots_al_ligando_A']} A del ligando")
        if d["lados_despues"] != d["lados_antes"]:
            print(f"    la caja crece de {d['lados_antes']} a {d['lados_despues']} A")
    print(f"\n{len(decisiones)} cajas a recentrar")

    if not args.aplicar:
        print("Nada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    DECISIONES.write_text(json.dumps({
        "fecha": datetime.date.today().isoformat(),
        "herramienta": "scripts/recentrar_cajas.py",
        "criterio": (f"ligando unido (>={MIN_CONTACTOS_PARA_ESTAR_UNIDO} residuos) a mas de "
                     f"{DESVIO_QUE_IMPORTA_A} A del centro, Y el centroide de los hotspots mas "
                     "cerca de ese ligando que de la caja"),
        "estandar": ("la mediana del catalogo es 0,0 A entre el centro de la caja y el del "
                     "ligando: nueve de cada diez ya estan centradas sobre el"),
        "advertencia": ("recentrar cambia el sitio que se acopla y por tanto los numeros de "
                        "cualquier resultado anterior sobre estos receptores; ver doc 71 §2.3"),
        "total": len(decisiones),
        "decisiones": decisiones,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"aplicado. Evidencia en {DECISIONES.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
