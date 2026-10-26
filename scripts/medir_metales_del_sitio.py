"""Qué iones metálicos tiene el sitio de cada receptor del catálogo, y si el ligando del cristal los coordina.

# Por qué existe

La preparación elimina todo ion metálico que el catálogo no declara en `cofactors_whitelist`, y ninguna entrada lo
declara. Preparación se abstiene cuando el ion retirado estaba a 6 Å o menos del ligando. La pregunta que quedaba sin
medir era si esos iones forman parte de la unión o son periféricos: no es lo mismo quitar un Mg de la superficie que
el Zn al que se ancla un hidroxamato.

# Qué se mide, sobre el depósito sin preparar (`data/targets/*.pdb.gz`)

* el ligando del cristal es la instancia de `site_ligand` más cercana al centro de la caja del catálogo;
* un ion cuenta si es de un elemento metálico, no está en `cofactors_whitelist` y está a `MARGEN_A` (6 Å) o menos de
  algún átomo del ligando; es el mismo margen con el que `prepare_target` decide qué pertenece al sitio;
* **lo coordina el ligando** si algún N, O o S del ligando está a `COORDINACION_A` (2,8 Å) o menos del ion. Es una
  medida geométrica sobre el cristal: no distingue una coordinación directa de una mediada por agua más cercana, ni
  dice nada de la energía.
* se mira la conformación sin altloc o la A, y sólo el primer modelo.

No decide nada: no cambia la preparación ni el catálogo. Cifra la decisión que le toca al propietario.

Uso:
    python scripts/medir_metales_del_sitio.py --write   # escribe docs/auditorias/metales_junto_al_sitio_2026-10-11.json
    python scripts/medir_metales_del_sitio.py --check   # falla si los depósitos o el catálogo ya no dan esa evidencia
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CATALOGO = RAIZ / "curated_targets.json"
EVIDENCIA = RAIZ / "docs" / "auditorias" / "metales_junto_al_sitio_2026-10-11.json"

#: Mismo margen que `preparer.MARGEN_SITIO_A`: lo que está a esta distancia de la caja forma parte del sitio.
MARGEN_A = 6.0
COORDINACION_A = 2.8
METALES = frozenset({"ZN", "FE", "FE2", "MG", "MN", "CA", "CU", "CU1", "CO", "NI", "CD", "HG", "NA", "K"})


def _xyz(linea: str) -> tuple[float, float, float]:
    return tuple(float(linea[i:i + 8]) for i in (30, 38, 46))  # type: ignore[return-value]


def _elemento(linea: str) -> str:
    elemento = linea[76:78].strip().upper() if len(linea) >= 78 else ""
    return elemento or linea[12:16].strip()[:1].upper()


def medir_entrada(lineas: list[str], entrada: dict) -> list[dict]:
    """Una fila por ion metálico no declarado a `MARGEN_A` o menos del ligando del cristal de esta entrada."""
    if not entrada.get("site_ligand"):
        return []
    centro = tuple(entrada[f"grid_center_{e}"] for e in "xyz")
    instancias: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    for linea in lineas:
        if linea.startswith("HETATM") and linea[17:20].strip() == entrada["site_ligand"]:
            instancias[(linea[21], linea[22:27])].append(linea)
    if not instancias:
        return []
    ligando = min(instancias.values(), key=lambda v: min(math.dist(_xyz(a), centro) for a in v))
    declarados = {str(x).upper() for x in entrada.get("cofactors_whitelist") or []}
    filas = []
    for linea in lineas:
        nombre = linea[17:20].strip()
        if not (linea.startswith("HETATM") and nombre in METALES and nombre not in declarados):
            continue
        ion = _xyz(linea)
        distancia = min(math.dist(ion, _xyz(a)) for a in ligando)
        if distancia > MARGEN_A:
            continue
        coordinan = sorted({a[12:16].strip() for a in ligando
                            if _elemento(a) in ("N", "O", "S") and math.dist(ion, _xyz(a)) <= COORDINACION_A})
        filas.append({
            "pdb_id": entrada["pdb_id"].upper(), "metal": nombre, "metal_id": f"{linea[21]}:{linea[22:26].strip()}",
            "ligando": entrada["site_ligand"], "d_ligando_A": round(distancia, 2),
            "atomos_del_ligando_que_lo_coordinan": coordinan,
            "lo_coordina_el_ligando": bool(coordinan),
        })
    return filas


def _lineas_del_deposito(ruta: Path) -> list[str]:
    salida = []
    with gzip.open(ruta, "rt", encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            if linea.startswith("ENDMDL"):
                break
            if linea.startswith(("ATOM", "HETATM")) and linea[16] in (" ", "A"):
                salida.append(linea)
    return salida


def resumir(filas: list[dict]) -> dict:
    por_elemento: dict[str, dict[str, int]] = collections.defaultdict(lambda: {"iones": 0, "coordinados": 0})
    for f in filas:
        por_elemento[f["metal"]]["iones"] += 1
        por_elemento[f["metal"]]["coordinados"] += f["lo_coordina_el_ligando"]
    entradas = {f["pdb_id"] for f in filas}
    con_coordinado = {f["pdb_id"] for f in filas if f["lo_coordina_el_ligando"]}
    return {
        "entradas": len(entradas),
        "iones": len(filas),
        "iones_coordinados_por_el_ligando": sum(f["lo_coordina_el_ligando"] for f in filas),
        "entradas_con_algun_ion_coordinado": len(con_coordinado),
        "entradas_sin_ningun_ion_coordinado": sorted(entradas - con_coordinado),
        "por_elemento": dict(sorted(por_elemento.items())),
    }


def medir(raiz: Path = RAIZ) -> dict:
    catalogo = json.loads((raiz / "curated_targets.json").read_text(encoding="utf-8"))
    filas: list[dict] = []
    for entrada in catalogo:
        ruta = raiz / "data" / "targets" / f"{entrada['pdb_id'].upper()}.pdb.gz"
        if ruta.is_file():
            filas += medir_entrada(_lineas_del_deposito(ruta), entrada)
    filas.sort(key=lambda f: (f["pdb_id"], f["metal"], f["metal_id"]))
    return {
        "herramienta": "scripts/medir_metales_del_sitio.py",
        "criterio": (f"ion metálico no declarado en cofactors_whitelist a <= {MARGEN_A:g} Å de algún átomo del ligando "
                     f"del cristal (la instancia de site_ligand más cercana al centro de la caja); lo coordina el "
                     f"ligando si un N, O o S suyo está a <= {COORDINACION_A:g} Å del ion. Geométrico, sobre el "
                     "depósito sin preparar: no distingue coordinación directa de mediada por agua ni mide energía."),
        "resumen": resumir(filas),
        "filas": filas,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--write", action="store_true", help="escribe la evidencia")
    grupo.add_argument("--check", action="store_true", help="falla si la evidencia ya no coincide con los depósitos")
    args = ap.parse_args()
    medido = medir()
    r = medido["resumen"]
    print(f"{r['iones']} iones en {r['entradas']} entradas; el ligando coordina {r['iones_coordinados_por_el_ligando']} "
          f"(en {r['entradas_con_algun_ion_coordinado']} entradas)")
    if args.write:
        EVIDENCIA.write_text(json.dumps(medido, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        print(f"evidencia: {EVIDENCIA.relative_to(RAIZ)}")
        return 0
    guardado = json.loads(EVIDENCIA.read_text(encoding="utf-8"))
    if guardado != medido:
        print("La evidencia guardada no coincide con lo que dan hoy los depósitos y el catálogo.", file=sys.stderr)
        return 1
    print("Evidencia verificada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
