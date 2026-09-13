"""Pone el prefijo de cadena a los hotspots que no lo traen, cuando es inequivoco.

# El defecto

Dos objetivos del catalogo -2W96 y 3OSK- anotan sus hotspots como `LYS35` en vez
de `B:LYS35`. Sin la cadena:

  * `Web3DViewer` no puede dibujar la envolvente del bolsillo;
  * el expediente no puede comprobar D2 ni D3 y los da por no localizables;
  * y `vina_service.py:963`, que empareja por nombre y numero ignorando la
    cadena, elige el primero que encuentra. En 2W96 el LYS35 de la cadena A
    esta a 29,2 A del sitio: emparejar con ese es nombrar en el dossier un
    residuo que no participa en nada.

# Cuando es seguro anadirlo, y cuando no

Solo cuando **una sola cadena** contiene ese numero de residuo dentro de la
caja. Si dos cadenas lo tienen a distancia comparable no hay forma de decidir y
el objetivo se deja como esta: adivinar seria repetir el error que el doc 71
documenta.

Medido antes de aplicar, la separacion no deja lugar a dudas:

    2W96  declara 'B'   LYS35  A: 29,2 A   B: 5,9 A
                        VAL96  A: 44,6 A   B: 5,1 A
                        ILE12  A: 32,0 A   B: 4,0 A
    3OSK  declara 'A'   MET99  A:  1,7 A   B: 65,4 A
                        TYR104 A:  3,8 A   B: 62,8 A

# Lo que NO hace

No cambia que residuos son hotspots. Solo dice en que cadena estan, que es un
dato que el catalogo ya tenia en `chain` y que se habia perdido al escribirlos.

# Uso

    python scripts/normalizar_hotspots_sin_cadena.py [--aplicar]
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

from revisar_cadena_por_receptor import CATALOGO, ESTRUCTURAS  # noqa: E402

DECISIONES = RAIZ / "docs" / "auditorias" / "hotspots_normalizados.json"

#: Cuantas veces mas lejos tiene que estar la segunda candidata para que la
#: eleccion sea inequivoca. Con 3x, «5,9 A contra 29,2 A» pasa y un empate no.
MARGEN = 3.0


def residuos(pdb_id: str) -> dict[tuple[str, int], list[tuple]]:
    salida: dict[tuple[str, int], list[tuple]] = collections.defaultdict(list)
    for nombre in (f"{pdb_id}.pdb.gz", f"{pdb_id}.pdb"):
        f = ESTRUCTURAS / nombre
        if not f.is_file():
            continue
        abrir = gzip.open if nombre.endswith(".gz") else open
        with abrir(f, "rt", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                if not linea.startswith("ATOM"):
                    continue
                try:
                    salida[(linea[21].strip(), int(linea[22:26]))].append(
                        (float(linea[30:38]), float(linea[38:46]), float(linea[46:54])))
                except ValueError:
                    continue
        break
    return dict(salida)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    decisiones = []

    for objetivo in catalogo:
        hotspots = objetivo.get("hotspots") or []
        sin_cadena = [h for h in hotspots if ":" not in (h.get("name") or "")]
        if not sin_cadena:
            continue
        pdb = objetivo["pdb_id"].upper()
        centro = (objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"])
        atomos = residuos(pdb)

        cambios, dudosos = [], []
        for h in sin_cadena:
            nombre = (h.get("name") or "").strip().upper()
            numero = "".join(c for c in nombre if c.isdigit())
            if not numero:
                dudosos.append(nombre)
                continue
            candidatas = sorted(
                ((min(math.dist(p, centro) for p in v), cad)
                 for (cad, num), v in atomos.items() if num == int(numero)))
            if not candidatas:
                dudosos.append(nombre)
                continue
            if len(candidatas) > 1 and candidatas[1][0] < candidatas[0][0] * MARGEN:
                dudosos.append(nombre)
                continue
            distancia, cadena = candidatas[0]
            cambios.append({"antes": nombre, "despues": f"{cadena}:{nombre}",
                            "distancia_al_centro_A": round(distancia, 1),
                            "descartadas": [{"cadena": c, "distancia_A": round(d, 1)}
                                            for d, c in candidatas[1:]]})

        if dudosos:
            print(f"{pdb}: NO se toca, {len(dudosos)} hotspots ambiguos -> {dudosos}")
            continue

        decisiones.append({"pdb_id": pdb, "cadena_declarada": objetivo.get("chain"),
                           "hotspots": cambios})
        print(f"{pdb}  declara '{objetivo.get('chain')}'")
        for c in cambios:
            print(f"    {c['antes']:10s} -> {c['despues']:12s}  a {c['distancia_al_centro_A']} A"
                  f"   (descartadas: "
                  + ", ".join(f"{d['cadena']} {d['distancia_A']} A" for d in c["descartadas"]) + ")")

        if args.aplicar:
            renombra = {c["antes"]: c["despues"] for c in cambios}
            for h in hotspots:
                nuevo = renombra.get((h.get("name") or "").strip().upper())
                if nuevo:
                    h["name"] = nuevo

    if not args.aplicar:
        print(f"\n{sum(len(d['hotspots']) for d in decisiones)} hotspots PREPARADOS. "
              "Nada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    DECISIONES.write_text(json.dumps({
        "fecha": datetime.date.today().isoformat(),
        "herramienta": "scripts/normalizar_hotspots_sin_cadena.py",
        "criterio": (f"una sola cadena contiene ese numero de residuo cerca de la caja, con "
                     f"la siguiente candidata al menos {MARGEN}x mas lejos"),
        "total": sum(len(d["hotspots"]) for d in decisiones),
        "decisiones": decisiones,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\naplicado. Evidencia en {DECISIONES.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
