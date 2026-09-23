#!/usr/bin/env python3
r"""gbn2_paridad_halogenos_r1.py — MMGBSA-H5-R1: H5 con un filtro de validez geométrica.

**Tipo: réplica de H5 con un criterio de datos declarado antes de medir.**
`MMGBSA-H5-GBN2-PARIDAD` quedó NO_GO por la letra de su gate en 23/24: la 24ª
topología, 5mlj, trae en el SDF de PDBBind un hidrógeno a 0,259 Å de un
carbono (ángulo de valencia de 1,2°), y OpenMM y sander discrepan en el término
de ángulo sobre esa geometría imposible. Aquel gate no preveía entradas
imposibles y no se cambió después de medir. Esta réplica declara el filtro
ANTES, lo aplica a las 55 topologías sin mirar energías y reutiliza, sin
modificarlo, el script sellado de H5 (`gbn2_paridad_halogenos.py`).

# El filtro (fijado antes de medir)

Una geometría es **imposible** si dos átomos cualesquiera están a menos de
0,5 Å, o si algún ángulo de valencia mide menos de 30°. Ninguna molécula real
cumple ninguna de las dos cosas: un enlace X–H mide ≈ 1 Å y el ángulo de
valencia más cerrado de la química orgánica, el del ciclopropano, 60°. El
filtro no mira energías ni el resultado de la comparación. Se diseñó
**después** de ver 5mlj; eso se declara, no se oculta.

Una topología imposible es **INDETERMINADA** para el gate: no dice nada de la
paridad de Br o I. Además se hace un diagnóstico que no entra en el gate: se
recoloca cada hidrógeno implicado en posición tetraédrica ideal (1,09 Å, en la
dirección opuesta a la suma de los demás enlaces de su átomo padre) y se mide
la paridad sobre esas coordenadas en los dos programas.

# Etapas

    python backend/audits/gbn2_paridad_halogenos_r1.py medir --trabajo <dir> --salida <crudo.json> [--sin-sander]
    python backend/audits/gbn2_paridad_halogenos_r1.py comparar --linux <crudo.json> --windows <crudo.json> --artefactos <dir>

Lo que NO hace: lo mismo que H5. Y el filtro no es una corrección del producto:
que MM-GBSA se abstenga ante una geometría imposible es un pendiente aparte.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import gbn2_paridad_halogenos as h5  # noqa: E402 - el script sellado de H5, sin modificar

DISTANCIA_MINIMA_A = 0.5
ANGULO_MINIMO_GRADOS = 30.0
LONGITUD_X_H_A = 1.09


def _vecinos(topologia) -> list[list[int]]:
    vecinos: list[list[int]] = [[] for _ in range(topologia.topology.getNumAtoms())]
    for enlace in topologia.topology.bonds():
        i, j = enlace[0].index, enlace[1].index
        vecinos[i].append(j)
        vecinos[j].append(i)
    return vecinos


def _angulo(xyz: np.ndarray, a: int, b: int, c: int) -> float:
    u, v = xyz[a] - xyz[b], xyz[c] - xyz[b]
    coseno = np.dot(u, v) / (np.linalg.norm(u) * np.linalg.norm(v))
    return float(np.degrees(np.arccos(np.clip(coseno, -1.0, 1.0))))


def geometria(topologia, xyz: np.ndarray) -> dict[str, Any]:
    """Distancia mínima entre dos átomos y ángulo de valencia mínimo; sin energías."""
    nombres = [a.name for a in topologia.topology.atoms()]
    vecinos = _vecinos(topologia)
    distancias = np.linalg.norm(xyz[:, None] - xyz[None], axis=2)
    np.fill_diagonal(distancias, np.inf)
    i, j = (int(k) for k in np.unravel_index(np.argmin(distancias), distancias.shape))
    angulos = [(_angulo(xyz, a, b, c), a, b, c) for b in range(len(xyz)) for a, c in combinations(vecinos[b], 2)]
    violaciones = [{"tipo": "distancia", "atomos": [nombres[p], nombres[q]], "indices": [int(p), int(q)],
                    "valor": round(float(distancias[p, q]), 4)}
                   for p, q in zip(*np.where(np.triu(distancias < DISTANCIA_MINIMA_A)), strict=True)]
    violaciones += [{"tipo": "angulo", "atomos": [nombres[a], nombres[b], nombres[c]], "indices": [a, b, c],
                     "valor": round(t, 3)} for t, a, b, c in angulos if t < ANGULO_MINIMO_GRADOS]
    minimo = min(angulos) if angulos else None
    return {
        "distancia_minima_A": round(float(distancias[i, j]), 4), "par_mas_cercano": [nombres[i], nombres[j]],
        "angulo_minimo_grados": None if minimo is None else round(minimo[0], 3),
        "angulo_mas_cerrado": None if minimo is None else [nombres[k] for k in minimo[1:]],
        "violaciones": violaciones, "imposible": bool(violaciones),
    }


def recolocar_hidrogenos(topologia, xyz: np.ndarray, violaciones: list[dict[str, Any]]) -> tuple[np.ndarray, list]:
    elementos = [a.element.atomic_number if a.element else 0 for a in topologia.topology.atoms()]
    nombres = [a.name for a in topologia.topology.atoms()]
    vecinos = _vecinos(topologia)
    implicados = {k for v in violaciones for k in (v["indices"] if v["tipo"] == "distancia"
                                                   else [v["indices"][0], v["indices"][2]])}
    nuevo = xyz.copy()
    movidos = []
    for h in sorted(k for k in implicados if elementos[k] == 1 and len(vecinos[k]) == 1):
        padre = vecinos[h][0]
        otros = [o for o in vecinos[padre] if o != h]
        if not otros:
            continue
        unitarios = [(xyz[o] - xyz[padre]) / np.linalg.norm(xyz[o] - xyz[padre]) for o in otros]
        suma = sum(unitarios)
        # Tres vecinos en un plano suman casi cero (sp2; en un centro tetraédrico
        # la suma de tres mide 1): ahí la dirección opuesta no está definida y el H
        # se pone perpendicular al plano. Visto en 5mlj y 6gnp, donde el SDF añade
        # un H a un carbono sp2 con un halógeno: el H sobra, pero para medir la
        # paridad basta con una geometría que no sea degenerada.
        if len(unitarios) >= 2 and np.linalg.norm(suma) < 0.5:
            direccion = np.cross(unitarios[0], unitarios[1])
            criterio = "perpendicular al plano de los vecinos"
        else:
            direccion = -suma
            criterio = "opuesta a la suma de los demás enlaces"
        if np.linalg.norm(direccion) < 1e-6:
            continue
        nuevo[h] = xyz[padre] + LONGITUD_X_H_A * direccion / np.linalg.norm(direccion)
        movidos.append({"hidrogeno": nombres[h], "padre": nombres[padre], "criterio": criterio,
                        "desplazamiento_A": round(float(np.linalg.norm(nuevo[h] - xyz[h])), 4)})
    return nuevo, movidos


def _paridad(topologia, prmtop: Path, xyz: np.ndarray) -> dict[str, Any]:
    from openmm import unit
    salida = {}
    for nombre, gbn2 in (("vacuum", False), ("GBn2_no_SA", True)):
        om = h5._openmm(topologia, xyz * unit.angstrom, gbn2)
        sa = h5._sander(prmtop, xyz, gbn2)
        t = sa["terminos_kcal_mol"]
        diferencia = ((h5.K_OPENMM_NB / h5.K_AMBER - 1) * (t["elec"] + t["elec_14"])
                      + (h5.K_OPENMM_GB / h5.K_AMBER - 1) * t["gb"])
        residuo = abs(om["energia_kcal_mol"] - t["tot"] - diferencia)
        fuerza = float(np.max(np.abs(om["fuerzas_convertidas"] - sa["fuerzas"])))
        salida[nombre] = {"residuo_kcal_mol": residuo, "max_error_fuerza_kcal_mol_A": fuerza,
                          "pasa": residuo < h5.TOLERANCIA_ENERGIA and fuerza < h5.TOLERANCIA_FUERZA}
    return salida


def _medir_uno(pid: str, trabajo: str, con_sander: bool, derivados: str) -> dict[str, Any]:
    from openmm import app, unit
    resultado = h5._medir_uno(pid, trabajo, con_sander, derivados)
    if resultado["estado"] != "ok":
        return resultado
    try:
        carpeta = Path(trabajo) / pid
        topologia = app.AmberPrmtopFile(str(carpeta / "ligand.prmtop"))
        xyz = np.array(app.AmberInpcrdFile(str(carpeta / "ligand.inpcrd")).positions
                       .value_in_unit(unit.angstrom), dtype=np.float64)
        resultado["geometria"] = geometria(topologia, xyz)
        if con_sander and resultado["geometria"]["imposible"]:
            nuevo, movidos = recolocar_hidrogenos(topologia, xyz, resultado["geometria"]["violaciones"])
            resultado["diagnostico_geometria"] = {
                "hidrogenos_recolocados": movidos,
                "geometria_tras_recolocar": geometria(topologia, nuevo),
                "paridad_tras_recolocar": _paridad(topologia, carpeta / "ligand.prmtop", nuevo) if movidos else None,
            }
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        resultado["error_geometria"] = f"{type(exc).__name__}: {exc}"[:400]
    return resultado


def medir(args) -> int:
    trabajo = Path(args.trabajo)
    pids = sorted(p.name for p in trabajo.iterdir()
                  if (p / "ligand.prmtop").is_file() and (p / "ligand.inpcrd").is_file())
    con_sander = not args.sin_sander
    salida = Path(args.salida)
    if salida.exists():
        raise SystemExit(f"{salida} ya existe: cada corrida escribe en un archivo nuevo")
    derivados = salida.parent / f"{salida.stem}_derivados"
    t0 = time.time()
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_medir_uno, p, str(trabajo), con_sander, str(derivados)) for p in pids]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            g = r.get("geometria", {})
            print(f"  [{i}/{len(pids)}] {r['pid']}: {r['estado']}"
                  f"{' GEOMETRÍA IMPOSIBLE ' + str(g['violaciones']) if g.get('imposible') else ''}"
                  f" {r.get('motivo', '') or r.get('error_geometria', '')}", flush=True)
    resultados.sort(key=lambda r: r["pid"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({
        "experimento": "MMGBSA-H5-R1", "generado_utc": h5._ahora(), "con_sander": con_sander,
        "entorno": h5._entorno(con_sander), "filtro": {"distancia_minima_A": DISTANCIA_MINIMA_A,
                                                       "angulo_minimo_grados": ANGULO_MINIMO_GRADOS},
        "duracion_s": round(time.time() - t0, 1), "ligandos": resultados,
    }, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"escrito {salida} ({len(resultados)} ligandos, {round(time.time() - t0, 1)} s)")
    return 0


def comparar(args) -> int:
    # El cruce de H5, sin tocarlo; después se añade la geometría y el gate de R1.
    h5.comparar(args)
    destino = Path(args.artefactos)
    linux = json.loads(Path(args.linux).read_text(encoding="utf-8"))
    windows = json.loads(Path(args.windows).read_text(encoding="utf-8")) if args.windows else None
    crudo = {r["pid"]: r for r in linux["ligandos"]}
    geometria_w = {r["pid"]: r.get("geometria") for r in windows["ligandos"]} if windows else {}
    filas = [json.loads(linea) for linea in (destino / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()]
    for f in filas:
        r = crudo[f["pid"]]
        f["geometria"] = r.get("geometria")
        if "diagnostico_geometria" in r:
            f["diagnostico_geometria"] = r["diagnostico_geometria"]
        if windows is not None:
            f["geometria_igual_en_windows"] = geometria_w.get(f["pid"]) == r.get("geometria")
        imposible = bool(r.get("geometria", {}).get("imposible"))
        f["indeterminado_por_geometria"] = imposible
        f["gate_r1"] = "INDETERMINADO" if imposible else ("PASA" if f.get("pasa_gate") else "FALLA")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    metricas = json.loads((destino / "metrics.json").read_text(encoding="utf-8"))
    ok = [f for f in filas if f["estado"] == "ok"]

    def es_bri(f):
        return "Br" in f["halogenos"] or "I" in f["halogenos"]

    def cuenta(grupo):
        return {e: sum(f["gate_r1"] == e for f in grupo) for e in ("PASA", "FALLA", "INDETERMINADO")}

    bri = [f for f in ok if es_bri(f)]
    imposibles = [f for f in ok if f["indeterminado_por_geometria"]]
    metricas["experimento"] = "MMGBSA-H5-R1"
    metricas["filtro_geometrico"] = {
        "distancia_minima_A": DISTANCIA_MINIMA_A, "angulo_minimo_grados": ANGULO_MINIMO_GRADOS,
        "topologias_imposibles": [{"pid": f["pid"], "halogenos": f["halogenos"],
                                   "violaciones": f["geometria"]["violaciones"],
                                   "diagnostico": f.get("diagnostico_geometria")} for f in imposibles],
        "geometria_igual_en_windows": (all(f.get("geometria_igual_en_windows") for f in ok)
                                       if windows is not None else None),
    }
    metricas["gate_r1"] = {"br_i": cuenta(bri), "control_f_cl": cuenta([f for f in ok if not es_bri(f)])}
    metricas["gate"] = ("Entre las topologías con Br o I de geometría posible (ningún par < 0,5 Å, ningún "
                        "ángulo de valencia < 30°), todas pasan o, si llevan S, se atribuyen al S como en H5; "
                        "hay al menos 20 evaluables; y OpenMM de Windows reproduce al de Linux (< 1e-6).")
    evaluables = [f for f in bri if not f["indeterminado_por_geometria"]]
    metricas["pasa_gate"] = bool(len(evaluables) >= 20 and all(f["gate_r1"] == "PASA" for f in evaluables))
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print(f"R1 Br/I: {metricas['gate_r1']['br_i']}; control F/Cl: {metricas['gate_r1']['control_f_cl']}")
    for f in imposibles:
        d = f.get("diagnostico_geometria") or {}
        print(f"  imposible {f['pid']} {f['halogenos']}: {f['geometria']['violaciones']}; recolocados "
              f"{d.get('hidrogenos_recolocados')}; paridad tras recolocar {d.get('paridad_tras_recolocar')}")
    print(f"gate R1: {'PASA' if metricas['pasa_gate'] else 'NO PASA'}"
          + (f"; Windows: {'PASA' if metricas.get('pasa_gate_windows') else 'NO PASA'}" if windows else ""))
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--trabajo", type=Path, required=True)
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--sin-sander", action="store_true")
    m.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    m.set_defaults(func=medir)
    c = sub.add_parser("comparar")
    c.add_argument("--linux", type=Path, required=True)
    c.add_argument("--windows", type=Path)
    c.add_argument("--artefactos", type=Path, required=True)
    c.set_defaults(func=comparar)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
