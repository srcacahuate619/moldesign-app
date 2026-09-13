"""Aplica al catalogo los rescates MECANICOS del triaje, y solo esos.

# Que se aplica y con que regla

Los objetivos que `triaje_receptores_al_vacio.py` clasifica como
`RESCATE_MECANICO`: la cadena declarada aporta el 0% del sitio y otra cadena lo
concentra, con DOS evidencias independientes de acuerdo —el ligando
co-cristalizado y los hotspots ya anotados—.

La regla es una relajacion deliberada de la que aplico `c8a50da`, y conviene
decir cual y por que:

    c8a50da   una cadena >=90% del sitio, evidencia del ligando.
    aqui      una cadena >=80% del sitio, evidencia del ligando **Y** la
              mayoria de los hotspots senalando esa misma cadena.

Se baja el umbral de volumen porque se anade una tercera evidencia
independiente. No es «el mismo criterio, mas flojo»: es un criterio distinto,
con mas apoyo. Los siete casos que pasa tienen entre 10 y 14 de sus 15 hotspots
en la cadena sugerida.

# Por que estos no podian esperar

No estan esperando una decision cientifica: estan averiados. La cadena que
`preparer.py` conserva no tiene NI UN ATOMO dentro de la caja de docking. Vina
acopla contra espacio vacio y devuelve una afinidad igualmente. Dejarlos como
estan no es prudencia: es seguir emitiendo numeros sin sustento.

# Lo que NO se toca

Las otras tres clases del triaje. `RESCATE_MULTICADENA` depende de que el
receptor multicadena entre en el contrato de preparacion; `REVISAR_LA_CAJA`
sospecha del grid y no de la cadena, y cambiar la cadena ahi taparia el defecto
real; `CONTRADICCION` tiene dos anotaciones peleadas y ningun script puede
arbitrar entre ellas.

Tampoco se reanotan los hotspots. Es otra decision, con otra evidencia.

# Reversibilidad

Cada cambio queda en `docs/auditorias/cadena_receptor_decisiones_tanda2.json`
con su valor anterior, su valor nuevo y la evidencia que lo justifica. Volver
atras es leer ese archivo y reescribir `cadena_antes`.

# Uso

    python scripts/aplicar_rescates_mecanicos.py --dry-run   # por defecto
    python scripts/aplicar_rescates_mecanicos.py --aplicar
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "curated_targets.json"
TRIAJE = RAIZ / "docs" / "auditorias" / "triaje_receptores_al_vacio.json"
#: Por defecto la tanda 2. Cada tanda escribe SU archivo: sobrescribir el de una
#: tanda anterior borraria la evidencia de decisiones ya aplicadas, que es lo
#: unico que permite revertirlas.
DECISIONES_POR_DEFECTO = RAIZ / "docs" / "auditorias" / "cadena_receptor_decisiones_tanda2.json"
TANDA1 = "docs/auditorias/cadena_receptor_decisiones.json"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aplicar", action="store_true", help="escribe el catalogo (por defecto no)")
    ap.add_argument("--salida", type=str, default=None,
                    help="donde escribir la evidencia; por defecto la tanda 2")
    args = ap.parse_args()
    decisiones_en = pathlib.Path(args.salida) if args.salida else DECISIONES_POR_DEFECTO
    if decisiones_en.exists() and args.aplicar and not args.salida:
        print(f"{decisiones_en.name} ya existe. Pasa --salida para no borrar su evidencia.",
              file=sys.stderr)
        return 1

    if not TRIAJE.is_file():
        print(f"falta {TRIAJE}. Corre antes triaje_receptores_al_vacio.py --json", file=sys.stderr)
        return 1

    triaje = json.loads(TRIAJE.read_text(encoding="utf-8"))
    rescates = {r["pdb_id"]: r for r in triaje["receptores"]
                if r["clase_triaje"] == "RESCATE_MECANICO"}
    if not rescates:
        print("no hay rescates mecanicos que aplicar")
        return 0

    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    decisiones = []
    for objetivo in catalogo:
        pdb = (objetivo.get("pdb_id") or "").upper()
        r = rescates.get(pdb)
        if not r:
            continue
        antes = (objetivo.get("chain") or "").strip().upper()
        despues = r["cadena_sugerida"]
        if antes == despues:
            continue
        decisiones.append({
            "pdb_id": pdb,
            "clase": "RESCATE_MECANICO",
            "cadena_antes": antes,
            "cadena_despues": despues,
            "motivo": r["motivo"],
            "evidencia": r["evidencia"],
            "ligando": r["ligando"],
            "reparto_del_sitio": r["reparto_del_sitio"],
            "hotspots_por_cadena": r["hotspots_por_cadena"],
            "hotspots_en_la_cadena_anterior": r["hotspots_en_la_declarada"],
            "distancia_de_la_anterior_al_centro_A": r["distancia_declarada_al_centro_A"],
            "atomos_en_caja": r["atomos_en_caja"],
        })
        if args.aplicar:
            objetivo["chain"] = despues

    for d in decisiones:
        print(f"{d['pdb_id']}  {d['cadena_antes']} -> {d['cadena_despues']}"
              f"   (la anterior a {d['distancia_de_la_anterior_al_centro_A']} A del centro,"
              f" {d['hotspots_en_la_cadena_anterior']} hotspots)")
        print(f"    {d['motivo']}")

    if not args.aplicar:
        print(f"\n{len(decisiones)} cambios PREPARADOS. Nada escrito: falta --aplicar")
        return 0

    CATALOGO.write_text(json.dumps(catalogo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    decisiones_en.write_text(json.dumps({
        "fecha": datetime.date.today().isoformat(),
        "tanda": 2,
        "tanda_anterior": TANDA1,
        "herramienta": "scripts/aplicar_rescates_mecanicos.py",
        "triaje": "docs/auditorias/triaje_receptores_al_vacio.json",
        "poblacion": "cadena declarada con 0% de los atomos de la caja de docking",
        "criterio": ("una sola cadena concentra >=80% del sitio segun el ligando co-cristalizado "
                     "Y la mayoria de los hotspots ya anotados senalan esa misma cadena"),
        "total_aplicadas": len(decisiones),
        "decisiones": decisiones,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{len(decisiones)} cambios APLICADOS a {CATALOGO.name}")
    print(f"evidencia en {decisiones_en.relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
