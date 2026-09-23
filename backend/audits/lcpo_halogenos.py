#!/usr/bin/env python3
r"""lcpo_halogenos.py — Puerta 1 de MM-GBSA ampliada: F, Cl, Br e I en geometrías reales.

**Tipo: medición.** Extiende `lcpo_vs_sasa_exacta.py` (un cloro, en un
clorobenceno generado) a ligandos cristalográficos de PDBBind con los cuatro
halógenos, con el MISMO método: cada parametrización LCPO se compara contra la
SASA numéricamente exacta del mismo átomo, en la misma geometría y con su
propio radio, y se lee contra el error de fondo de LCPO en átomos bien
parametrizados de los mismos ligandos. Se reutilizan sus funciones
(`sasa_numerica`, `areas_lcpo`, `_desempaquetar`), no se reescriben.

# Lo que ya se sabía, y lo que este script mide

- **F**: OpenMM y Amber usan la entrada LCPO `F`, que el artículo de LCPO
  (Weiser, Shenkin y Still, 1999) NO publicó: la trae Amber. Nadie ha medido
  lo bien que aproxima la superficie.
- **Cl**: adjudicado sobre UN átomo (2026-09-19). Aquí, sobre muchos.
- **Br, I**: el OpenMM que viaja con el producto (8.5.2) **no tiene
  parámetros** y lanza excepción: el MM-GBSA candidato no puede puntuar hoy un
  ligando bromado o yodado. Qué hace Amber con ellos NO se supone: se mide con
  `sander`, probando cada entrada de la tabla LCPO como sustituta del halógeno
  hasta encontrar la que reproduce su término de superficie. El cloro, cuyo
  respaldo (`C_sp2_2`) ya está atribuido, es el control positivo del método.

# Curación automática, declarada antes de mirar

Universo: ligandos de PDBBind que RDKit lee (FEP-01-PDBBIND). Filtros:
elementos sólo H, C, N, O, S, P, F, Cl, Br, I; 8 a 35 átomos pesados;
|carga formal| ≤ 1; hidrógenos explícitos en el SDF. **Un ligando por diana**
(grupos de FEP-03-PDBBIND) para no medir casi-duplicados. Por halógeno, dos
estratos por entorno —unido a un aromático o a un alifático (p. ej. CF3)—, 6
por estrato en orden (átomos pesados, pid), completando con el otro estrato
hasta 12 si uno no llega. Se añaden los 7 ligandos fluorados de galectina-3
(6qln-6qlu), la cohorte recomendada por FEP-03-PDBBIND.

# Cargas Gasteiger, y por qué

El área LCPO y la SASA dependen de tipos, enlaces y coordenadas, no de las
cargas. AM1-BCC sólo añadiría horas de `sqm` y fallos de convergencia sin
cambiar nada de lo que se mide. Los tipos son GAFF2 y los radios mbondi3, como
en `amber_openmm_reference.py`.

# Etapas

    python backend/audits/lcpo_halogenos.py curar
    python backend/audits/lcpo_halogenos.py parametrizar --trabajo <dir>   # AmberTools
    python backend/audits/lcpo_halogenos.py medir --trabajo <dir>          # OpenMM + sander

`curar` escribe `halogenos_lcpo/seleccion.json`; `medir`, `halogenos_lcpo/
resultado.json`. Las coordenadas y topologías derivadas de PDBBind quedan en
`--trabajo`, fuera del repositorio: son datos de PDBBind y no se redistribuyen.

Lo que NO hace: no activa MM-GBSA, no cambia la tabla LCPO de producción y no
decide qué radio es el físico para Br o I, que es una pregunta de dominio. Mide
cuánto se equivoca cada parametrización en aproximar la superficie de su
propia esfera.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
from lcpo_vs_sasa_exacta import (  # noqa: E402
    RADIO_SONDA,
    TENSION_SUPERFICIAL,
    _desempaquetar,
    _TiposEnMayuscula,
    _valor,
    areas_lcpo,
    sasa_numerica,
)

SALIDA = AQUI / "halogenos_lcpo"
PDBBIND = RAIZ / "data" / "pdbbind"
F01 = RAIZ / "scripts" / "artifacts_science" / "FEP-01-PDBBIND" / "per_complex.jsonl"
F03 = RAIZ / "scripts" / "artifacts_science" / "FEP-03-PDBBIND" / "grupos.json"

HALOGENOS = {9: "F", 17: "Cl", 35: "Br", 53: "I"}
PERMITIDOS = {1, 6, 7, 8, 15, 16, 9, 17, 35, 53}
PESADOS_MIN, PESADOS_MAX, POR_ESTRATO, POR_HALOGENO = 8, 35, 6, 12
GALECTINA_3 = ("6qln", "6qlo", "6qlp", "6qlq", "6qlr", "6qlt", "6qlu")
DENSIDADES_MEDIDA = (2_000, 10_000, 50_000)
TOLERANCIA_ATRIBUCION = 1e-5          # kcal/mol entre sander y la sustitución


def _ahora() -> str:
    return datetime.now(UTC).isoformat()


# ── 1. Curación ──────────────────────────────────────────────────────────

def curar(_args) -> int:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    legibles = {}
    with open(F01, encoding="utf-8") as fh:
        for linea in fh:
            r = json.loads(linea)
            if "error" not in r:
                legibles[r["pid"]] = r
    grupo_de: dict[str, str] = {}
    for g in json.loads(F03.read_text(encoding="utf-8"))["grupos"]:
        for p in g:
            grupo_de[p] = g[0]

    candidatos: list[dict[str, Any]] = []
    descartes: dict[str, int] = defaultdict(int)
    for pid in sorted(legibles):
        sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
        mol = Chem.MolFromMolFile(str(sdf), removeHs=False)
        if mol is None:
            descartes["ilegible"] += 1
            continue
        numeros = {a.GetAtomicNum() for a in mol.GetAtoms()}
        if not numeros & set(HALOGENOS):
            continue
        pesados = mol.GetNumHeavyAtoms()
        if not numeros <= PERMITIDOS:
            descartes["elemento_no_permitido"] += 1
            continue
        if not PESADOS_MIN <= pesados <= PESADOS_MAX:
            descartes["tamano"] += 1
            continue
        if abs(Chem.GetFormalCharge(mol)) > 1:
            descartes["carga"] += 1
            continue
        if mol.GetNumAtoms() == pesados:
            descartes["sin_hidrogenos"] += 1
            continue
        entornos: dict[str, dict[str, int]] = defaultdict(lambda: {"arilo": 0, "alifatico": 0})
        for a in mol.GetAtoms():
            if a.GetAtomicNum() in HALOGENOS:
                vecino = a.GetNeighbors()[0] if a.GetDegree() == 1 else None
                clave = "arilo" if vecino is not None and vecino.GetIsAromatic() else "alifatico"
                entornos[HALOGENOS[a.GetAtomicNum()]][clave] += 1
        candidatos.append({
            "pid": pid, "grupo": grupo_de.get(pid, pid), "n_pesados": pesados,
            "carga_formal": Chem.GetFormalCharge(mol), "halogenos": dict(entornos),
            "sdf_sha256": hashlib.sha256(sdf.read_bytes()).hexdigest(),
        })

    elegidos: dict[str, dict[str, Any]] = {}
    grupos_usados: set[str] = set()
    por_halogeno: dict[str, list[str]] = {}
    for simbolo in ("F", "Cl", "Br", "I"):
        tomados: list[str] = []
        for entorno in ("arilo", "alifatico"):
            cupo = POR_ESTRATO
            for c in sorted(candidatos, key=lambda c: (c["n_pesados"], c["pid"])):
                if cupo == 0:
                    break
                if c["halogenos"].get(simbolo, {}).get(entorno) and c["grupo"] not in grupos_usados:
                    elegidos[c["pid"]] = {**c, "estrato": f"{simbolo}/{entorno}"}
                    grupos_usados.add(c["grupo"])
                    tomados.append(c["pid"])
                    cupo -= 1
        for c in sorted(candidatos, key=lambda c: (c["n_pesados"], c["pid"])):
            if len(tomados) >= POR_HALOGENO:
                break
            if simbolo in c["halogenos"] and c["grupo"] not in grupos_usados:
                elegidos[c["pid"]] = {**c, "estrato": f"{simbolo}/relleno"}
                grupos_usados.add(c["grupo"])
                tomados.append(c["pid"])
        por_halogeno[simbolo] = tomados
    fijos = [c for c in candidatos if c["pid"] in GALECTINA_3]
    for c in fijos:
        elegidos.setdefault(c["pid"], {**c, "estrato": "F/galectina-3"})

    seleccion = {
        "generado_utc": _ahora(),
        "criterios": {
            "universo": "ligandos de PDBBind legibles por RDKit (FEP-01-PDBBIND)",
            "elementos": "H C N O S P F Cl Br I", "pesados": [PESADOS_MIN, PESADOS_MAX],
            "carga_formal_max": 1, "un_ligando_por_diana": "grupos de FEP-03-PDBBIND",
            "estratos": f"{POR_ESTRATO} arilo + {POR_ESTRATO} alifatico por halogeno, relleno hasta {POR_HALOGENO}",
            "orden": "(n_pesados, pid)", "fijos": list(GALECTINA_3),
        },
        "n_candidatos": len(candidatos),
        "descartes": dict(descartes),
        "por_halogeno": por_halogeno,
        "galectina_3_incluidos": [c["pid"] for c in fijos],
        "ligandos": sorted(elegidos.values(), key=lambda c: c["pid"]),
    }
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / "seleccion.json").write_text(json.dumps(seleccion, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    print(f"{len(candidatos)} candidatos con halógeno tras los filtros; descartes {dict(descartes)}")
    for s, lista in por_halogeno.items():
        print(f"  {s}: {len(lista)} → {', '.join(lista)}")
    print(f"  galectina-3: {len(fijos)}; total {len(elegidos)} ligandos")
    return 0


# ── 2. Parametrización (AmberTools) ──────────────────────────────────────

def _orden(args: list[str], carpeta: Path, nombre: str, limite: int = 900) -> None:
    with open(carpeta / f"{nombre}.stdout", "w") as out, open(carpeta / f"{nombre}.stderr", "w") as err:
        r = subprocess.run(args, cwd=carpeta, stdout=out, stderr=err, timeout=limite, check=False)
    if r.returncode:
        cola = (carpeta / f"{nombre}.stderr").read_text(errors="replace")[-300:]
        raise RuntimeError(f"{nombre} rc={r.returncode}: {cola.strip()}")


def _parametrizar_uno(pid: str, trabajo: str) -> dict[str, Any]:
    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    carpeta = Path(trabajo) / pid
    if (carpeta / "ligand.prmtop").is_file():
        return {"pid": pid, "estado": "ya_estaba"}
    carpeta.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        mol = Chem.MolFromMolFile(str(PDBBIND / pid / f"{pid}_ligand.sdf"), removeHs=False)
        Chem.Kekulize(mol, clearAromaticFlags=True)
        (carpeta / "input.sdf").write_text(Chem.MolToMolBlock(mol, kekulize=True), encoding="utf-8")
        carga = Chem.GetFormalCharge(mol)
        _orden(["antechamber", "-i", "input.sdf", "-fi", "sdf", "-o", "ligand.mol2", "-fo", "mol2",
                "-at", "gaff2", "-c", "gas", "-nc", str(carga), "-rn", "LIG", "-s", "2"], carpeta, "antechamber")
        _orden(["parmchk2", "-i", "ligand.mol2", "-f", "mol2", "-o", "ligand.frcmod", "-s", "gaff2"],
               carpeta, "parmchk2")
        if "ATTN" in (carpeta / "ligand.frcmod").read_text(errors="replace"):
            raise RuntimeError("parmchk2 dejó parámetros sin resolver (ATTN)")
        (carpeta / "leap.in").write_text(
            "source leaprc.gaff2\nset default PBRadii mbondi3\nloadamberparams ligand.frcmod\n"
            "LIG = loadmol2 ligand.mol2\ncheck LIG\nsaveamberparm LIG ligand.prmtop ligand.inpcrd\nquit\n")
        _orden(["tleap", "-f", "leap.in"], carpeta, "tleap")
        import parmed
        amber = parmed.load_file(str(carpeta / "ligand.prmtop"), xyz=str(carpeta / "ligand.inpcrd"))
        if len(amber.atoms) != mol.GetNumAtoms():
            raise RuntimeError(f"cambió el número de átomos: {mol.GetNumAtoms()} -> {len(amber.atoms)}")
        origen = mol.GetConformer().GetPositions()
        desvio = float(np.max(np.linalg.norm(origen - np.asarray(amber.coordinates), axis=1)))
        mismos = all(a.GetAtomicNum() == b.atomic_number for a, b in zip(mol.GetAtoms(), amber.atoms, strict=True))
        if desvio > 1e-3 or not mismos:
            raise RuntimeError(f"coordenadas o elementos cambiaron (desvío {desvio:.4f} Å, elementos {mismos})")
        return {"pid": pid, "estado": "ok", "n_atomos": len(amber.atoms), "desvio_coordenadas_A": desvio,
                "tipos_halogeno": sorted({a.type for a in amber.atoms if a.atomic_number in HALOGENOS}),
                "duracion_s": round(time.time() - t0, 1)}
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"pid": pid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400],
                "duracion_s": round(time.time() - t0, 1)}


def parametrizar(args) -> int:
    seleccion = json.loads((SALIDA / "seleccion.json").read_text(encoding="utf-8"))
    pids = [c["pid"] for c in seleccion["ligandos"]]
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_parametrizar_uno, p, str(args.trabajo)) for p in pids]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{i}/{len(pids)}] {r['pid']}: {r['estado']} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["pid"])
    resumen = {"generado_utc": _ahora(), "n": len(resultados),
               "ok": sum(r["estado"] in ("ok", "ya_estaba") for r in resultados),
               "fallos": [r for r in resultados if r["estado"] == "fallo"], "ligandos": resultados}
    (SALIDA / "parametrizacion.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n",
                                                 encoding="utf-8", newline="\n")
    print(f"parametrizados {resumen['ok']}/{resumen['n']}; fallos {len(resumen['fallos'])}")
    return 0


# ── 3. Medida ────────────────────────────────────────────────────────────

def _energia_lcpo(topologia, coords, parametros) -> float:
    """Sólo el término LCPO de OpenMM, sin GB: no hace falta y no depende de él."""
    import openmm
    from openmm import app, unit
    from openmm.app.internal import lcpo
    sistema = topologia.createSystem(nonbondedMethod=app.NoCutoff, constraints=None,
                                     implicitSolvent=None, removeCMMotion=False)
    n = sistema.getNumForces()
    lcpo.addLCPOForce(sistema, parametros, usePeriodic=False)
    for i in range(n, sistema.getNumForces()):
        sistema.getForce(i).setForceGroup(11)
    integ = openmm.VerletIntegrator(0.001)
    ctx = openmm.Context(sistema, integ, openmm.Platform.getPlatformByName("Reference"))
    ctx.setPositions(coords * unit.angstrom)
    e = ctx.getState(getEnergy=True, groups={11}).getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    del ctx, integ
    return float(e)


def _superficie_sander(prmtop: Path, coords: np.ndarray) -> float:
    import sander
    opciones = sander.gas_input(8)
    opciones.cut = 999.0
    opciones.gbsa = 1
    opciones.extdiel = 78.5
    opciones.intdiel = 1.0
    with sander.setup(str(prmtop), coords.tolist(), None, opciones):
        energias, _ = sander.energy_forces()
    return float(energias.surf)


def _medir_uno(pid: str, trabajo: str, puntos: int) -> dict[str, Any]:
    from openmm import app, unit
    from openmm.app import element as elemento
    from openmm.app.internal import lcpo
    carpeta = Path(trabajo) / pid
    try:
        topologia = app.AmberPrmtopFile(str(carpeta / "ligand.prmtop"))
        coords = np.array(app.AmberInpcrdFile(str(carpeta / "ligand.inpcrd"))
                          .positions.value_in_unit(unit.angstrom), dtype=np.float64)
        elementos = list(topologia.elements)
        numeros = [0 if e is None else e.atomic_number for e in elementos]
        # Br e I no tienen entrada en OpenMM 8.5.2: se pone un cloro de marcador para
        # que la tabla se construya, y ese marcador se sustituye siempre por un brazo.
        marcador = [elemento.chlorine if z in (35, 53) else e for z, e in zip(numeros, elementos, strict=True)]
        base = lcpo.getLCPOParamsAmber(_TiposEnMayuscula(topologia._prmtop), marcador)
        tabla = lcpo.LCPO_PARAMETERS
        halos = {s: [i for i, z in enumerate(numeros) if z == n] for n, s in HALOGENOS.items()}
        halos = {s: v for s, v in halos.items() if v}

        # Guardián 1: la implementación propia reproduce a OpenMM con estos parámetros.
        radios, p1, p2, p3, p4 = _desempaquetar(base)
        propias = areas_lcpo(coords, radios, p1, p2, p3, p4)
        area_openmm = _energia_lcpo(topologia, coords, base) / TENSION_SUPERFICIAL
        if abs(propias.sum() - area_openmm) > 1e-6 * max(1.0, abs(area_openmm)):
            return {"pid": pid, "estado": "fallo",
                    "motivo": f"LCPO propio {propias.sum():.6f} != OpenMM {area_openmm:.6f}"}

        # Convergencia de la SASA numérica con los radios base.
        convergencia = {}
        for n in DENSIDADES_MEDIDA:
            if n <= puntos:
                a = sasa_numerica(coords, radios, n, 0.0).sum()
                b = sasa_numerica(coords, radios, n, 0.37).sum()
                convergencia[str(n)] = round(abs(float(a - b)), 4)

        # Error de fondo: átomos pesados no halógenos, con los parámetros de Amber/OpenMM.
        exactas = sasa_numerica(coords, radios, puntos, 0.0)
        todos_halos = {i for v in halos.values() for i in v}
        fondo = [round(float(propias[i] - exactas[i]), 4) for i in range(len(radios))
                 if radios[i] > 0.0 and i not in todos_halos]

        # Atribución de Amber: sander, sólo si hay un único tipo de halógeno.
        atribucion = None
        if len(halos) == 1:
            simbolo, indices = next(iter(halos.items()))
            surf = _superficie_sander(carpeta / "ligand.prmtop", coords)
            residuos = {}
            for nombre, fila in tabla.items():
                r_, a1, a2, a3, a4 = _desempaquetar(base, set(indices), fila)
                area = areas_lcpo(coords, r_, a1, a2, a3, a4).sum()
                residuos[nombre] = abs(area * TENSION_SUPERFICIAL - surf)
            orden = sorted(residuos, key=residuos.get)
            coinciden = [k for k in orden if residuos[k] < TOLERANCIA_ATRIBUCION]
            atribucion = {"halogeno": simbolo, "surf_sander_kcal_mol": surf,
                          "mejor": orden[0], "residuo_kcal_mol": float(f"{residuos[orden[0]]:.3e}"),
                          "coinciden_dentro_de_tolerancia": coinciden,
                          "segundo": orden[1], "residuo_segundo_kcal_mol": float(f"{residuos[orden[1]]:.3e}")}

        # Brazos por halógeno, cada uno contra la SASA exacta con su propio radio.
        brazos_de = {
            "F": {"F_Amber_y_OpenMM": tabla["F"], "diagnostico_C_sp3_1": tabla["C_sp3_1"]},
            "Cl": {"Cl_publicado_Weiser_1999": tabla["Cl"], "respaldo_Amber_C_sp2_2": tabla["C_sp2_2"],
                   "diagnostico_C_sp3_1": tabla["C_sp3_1"]},
            "Br": {"respaldo_C_sp2_2": tabla["C_sp2_2"], "diagnostico_Cl_publicado": tabla["Cl"],
                   "diagnostico_C_sp3_1": tabla["C_sp3_1"]},
            "I": {"respaldo_C_sp2_2": tabla["C_sp2_2"], "diagnostico_Cl_publicado": tabla["Cl"],
                  "diagnostico_C_sp3_1": tabla["C_sp3_1"]},
        }
        atomos = []
        for simbolo, indices in halos.items():
            for brazo, fila in brazos_de[simbolo].items():
                r_, a1, a2, a3, a4 = _desempaquetar(base, set(indices), fila)
                lc = areas_lcpo(coords, r_, a1, a2, a3, a4)
                ex = sasa_numerica(coords, r_, puntos, 0.0)
                ex_b = sasa_numerica(coords, r_, puntos, 0.37)
                for i in indices:
                    atomos.append({"indice": i, "halogeno": simbolo, "brazo": brazo,
                                   "tipo_amber": topologia._prmtop.getAtomType(i),
                                   "radio_sin_sonda_A": _valor(fila[0]),
                                   "sasa_exacta_A2": round(float(ex[i]), 4),
                                   "sasa_lcpo_A2": round(float(lc[i]), 4),
                                   "error_A2": round(float(lc[i] - ex[i]), 4),
                                   "incertidumbre_malla_A2": round(abs(float(ex[i] - ex_b[i])), 4)})
        return {"pid": pid, "estado": "ok", "n_atomos": len(numeros),
                "desvio_lcpo_contra_openmm_A2": float(f"{abs(propias.sum() - area_openmm):.3e}"),
                "convergencia_total_A2": convergencia, "fondo_error_A2": fondo,
                "atribucion_amber": atribucion, "halogenos": atomos}
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"pid": pid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400]}


def _estadistica(valores: list[float]) -> dict[str, float] | None:
    if not valores:
        return None
    v = np.abs(np.array(valores))
    return {"n": int(v.size), "mediana_abs_A2": round(float(np.median(v)), 4),
            "p90_abs_A2": round(float(np.percentile(v, 90)), 4), "max_abs_A2": round(float(v.max()), 4),
            "media_con_signo_A2": round(float(np.mean(valores)), 4)}


def medir(args) -> int:
    parametrizados = json.loads((SALIDA / "parametrizacion.json").read_text(encoding="utf-8"))
    pids = [r["pid"] for r in parametrizados["ligandos"] if r["estado"] in ("ok", "ya_estaba")]
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(_medir_uno, p, str(args.trabajo), args.puntos) for p in pids]
        for i, f in enumerate(as_completed(futuros), 1):
            r = f.result()
            resultados.append(r)
            print(f"  [{i}/{len(pids)}] {r['pid']}: {r['estado']} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["pid"])
    ok = [r for r in resultados if r["estado"] == "ok"]

    fondo = _estadistica([e for r in ok for e in r["fondo_error_A2"]])
    por_halogeno: dict[str, Any] = {}
    for simbolo in ("F", "Cl", "Br", "I"):
        filas = [a for r in ok for a in r["halogenos"] if a["halogeno"] == simbolo]
        if not filas:
            continue
        brazos = {}
        for brazo in sorted({a["brazo"] for a in filas}):
            errores = [a["error_A2"] for a in filas if a["brazo"] == brazo]
            est = _estadistica(errores)
            est["dentro_del_fondo_p90"] = bool(fondo and est["mediana_abs_A2"] <= fondo["p90_abs_A2"])
            brazos[brazo] = est
        atribuciones = [r["atribucion_amber"] for r in ok
                        if r["atribucion_amber"] and r["atribucion_amber"]["halogeno"] == simbolo]
        conteo: dict[str, int] = defaultdict(int)
        for a in atribuciones:
            conteo[",".join(a["coinciden_dentro_de_tolerancia"]) or "ninguna"] += 1
        por_halogeno[simbolo] = {
            "n_ligandos": len({(r["pid"]) for r in ok for a in r["halogenos"] if a["halogeno"] == simbolo}),
            "n_atomos": len({(r["pid"], a["indice"]) for r in ok for a in r["halogenos"]
                             if a["halogeno"] == simbolo}),
            "atribucion_amber_por_sander": {"n_ligandos": len(atribuciones), "coincidencias": dict(conteo)},
            "brazos": brazos,
            "mejor_brazo": min(brazos, key=lambda b: brazos[b]["mediana_abs_A2"]),
        }
    informe = {
        "experimento": "MMGBSA-LCPO-HALOGENOS-01",
        "pregunta": "¿Cuánto se equivoca cada parametrización LCPO de F, Cl, Br e I frente a la SASA exacta?",
        "generado_utc": _ahora(), "puntos_shrake_rupley": args.puntos,
        "tension_superficial": TENSION_SUPERFICIAL, "radio_sonda_A": RADIO_SONDA,
        "n_medidos": len(ok), "fallos": [r for r in resultados if r["estado"] != "ok"],
        "fondo": fondo, "por_halogeno": por_halogeno,
        "convergencia_max_diferencia_mallas_A2": max(
            (v for r in ok for v in r["convergencia_total_A2"].values()), default=None),
        "no_demuestra": ("Que MM-GBSA sea válido ni qué radio es el físico para Br o I. Mide cuánto se "
                         "equivoca cada parametrización en aproximar la superficie de su propia esfera, "
                         "en geometrías cristalográficas de PDBBind."),
        "ligandos": resultados,
    }
    (SALIDA / "resultado.json").write_text(json.dumps(informe, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
    print(f"\nFondo: {fondo}")
    for s, d in por_halogeno.items():
        print(f"\n== {s}: {d['n_ligandos']} ligandos, {d['n_atomos']} átomos; Amber por sander: "
              f"{d['atribucion_amber_por_sander']}")
        for b, e in d["brazos"].items():
            print(f"   {b:28s} mediana |err| {e['mediana_abs_A2']:7.3f}  p90 {e['p90_abs_A2']:7.3f}  "
                  f"media {e['media_con_signo_A2']:+7.3f}  {'dentro' if e['dentro_del_fondo_p90'] else 'FUERA'} del fondo")
    return 0


def main() -> int:
    # La consola de Windows usa cp1252: sin esto, una flecha en un print convierte
    # el informe en un traceback DESPUÉS de haber escrito el JSON.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    sub.add_parser("curar").set_defaults(func=curar)
    for nombre, func in (("parametrizar", parametrizar), ("medir", medir)):
        p = sub.add_parser(nombre)
        p.add_argument("--trabajo", type=Path, required=True)
        p.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
        p.add_argument("--puntos", type=int, default=50_000)
        p.set_defaults(func=func)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
