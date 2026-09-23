#!/usr/bin/env python3
r"""gbn2_paridad_halogenos.py — MMGBSA-H5: OpenMM y sander coinciden en GBn2 con Br e I.

**Tipo: medición de implementación, no de física.** Es la hipótesis H5 de
`docs/validacion_mmgbsa.md`, la precondición de todas las demás: si con la
MISMA topología y las MISMAS coordenadas los dos programas no dan la misma
energía, cualquier error posterior es imposible de atribuir a la química.

Amplía `amber_openmm_reference.py` (ocho fixtures generados, un solo halógeno)
a las 55 topologías cristalográficas que `lcpo_halogenos.py parametrizar` ya
dejó en el servidor: 24 con Br o I y 31 con F o Cl como control. Mismas dos
condiciones sin término de superficie —`vacuum` y `GBn2_no_SA`— y la misma
conversión analítica de constantes de Coulomb, que no es un ajuste.

# Qué se compara y con qué tolerancia (fijado antes de medir)

- Energía: |E_OpenMM − E_sander − Δ_constantes| < 0,001 kcal/mol, con
  Δ_constantes calculada como en `amber_openmm_reference.py` (términos
  electrostáticos y GB de sander por la razón de constantes).
- Fuerzas: máx |F_OpenMM,conv − F_sander| < 0,001 kcal/mol/Å, donde
  F_OpenMM,conv escala la parte de Coulomb y la de GB de OpenMM por la razón
  exacta de constantes. Se separan por grupos de fuerza y la de Coulomb se
  obtiene restando una evaluación con las cargas a cero; es álgebra, no un
  ajuste. La diferencia bruta también se guarda.

# Lo que registra además

Los parámetros GB que cada halógeno recibe en la topología (RADII, SCREEN) y
en OpenMM (radio con desplazamiento, radio escalado, α, β, γ), para que H3
parta de lo que de verdad se usa y no de lo que se supone. Y los avisos de
OpenMM («Non-optimal GB parameters»), que se conservan, no se silencian.

# Etapas

    # servidor (AmberTools + pysander): OpenMM y sander sobre las topologías
    python backend/audits/gbn2_paridad_halogenos.py medir --trabajo <dir> --salida <crudo.json>
    # esta máquina (el Python que se entrega): sólo OpenMM, sobre copias byte a byte
    python backend/audits/gbn2_paridad_halogenos.py medir --trabajo <dir> --salida <crudo.json> --sin-sander
    # cruce: OpenMM Linux contra sander, OpenMM Windows contra sander y contra OpenMM Linux
    python backend/audits/gbn2_paridad_halogenos.py comparar --linux <crudo.json> [--windows <crudo.json>] --artefactos <dir>

Los crudos llevan fuerzas por átomo y se quedan fuera del repositorio junto a
las topologías, que son datos derivados de PDBBind. Al repositorio va el
resumen con los SHA-256 de los crudos y de cada prmtop/inpcrd.

Lo que NO hace: no decide qué radio es el físico para Br o I (eso es H3), no
toca el término de superficie (H1) y no activa MM-GBSA.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parent))

HALOGENOS = {9: "F", 17: "Cl", 35: "Br", 53: "I"}
TOLERANCIA_ENERGIA = 1e-3      # kcal/mol, tras la conversión de constantes
TOLERANCIA_FUERZA = 1e-3       # kcal/mol/Å, tras la conversión de constantes
TOLERANCIA_ENTRE_MAQUINAS = 1e-6   # kcal/mol y kcal/mol/Å: Reference en doble precisión

# Constantes de Coulomb: Amber guarda las cargas multiplicadas por 18.2223;
# OpenMM usa ONE_4PI_EPS0 en NonbondedForce y 138.935485 en la expresión GBn2.
K_AMBER = 18.2223 ** 2
K_OPENMM_NB = 138.93545764438198 * 10 / 4.184
K_OPENMM_GB = 138.935485 * 10 / 4.184
GRUPO_ENLACE, GRUPO_NB, GRUPO_GB = 0, 1, 2


def _ahora() -> str:
    return datetime.now(UTC).isoformat()


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


# ── OpenMM ───────────────────────────────────────────────────────────────

def _openmm(topologia, posiciones, gbn2: bool) -> dict[str, Any]:
    import openmm
    from openmm import app, unit

    from services.chemistry.amber_compatibility import apply_amber_gbn2_phosphorus

    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        sistema = topologia.createSystem(
            nonbondedMethod=app.NoCutoff, constraints=None,
            implicitSolvent=app.GBn2 if gbn2 else None, soluteDielectric=1.0,
            solventDielectric=78.5, sasaMethod=None, removeCMMotion=False)
    fosforo = apply_amber_gbn2_phosphorus(sistema, topologia.topology) if gbn2 else 0
    nb = None
    gb = None
    for fuerza in sistema.getForces():
        if isinstance(fuerza, openmm.NonbondedForce):
            fuerza.setForceGroup(GRUPO_NB)
            nb = fuerza
        elif isinstance(fuerza, openmm.CustomGBForce):
            fuerza.setForceGroup(GRUPO_GB)
            gb = fuerza
        else:
            fuerza.setForceGroup(GRUPO_ENLACE)
    if nb is None or (gbn2 and gb is None):
        raise RuntimeError("el sistema no tiene la forma esperada (NonbondedForce / CustomGBForce)")
    otras = [type(f).__name__ for f in sistema.getForces()
             if not isinstance(f, (openmm.NonbondedForce, openmm.CustomGBForce, openmm.HarmonicBondForce,
                                   openmm.HarmonicAngleForce, openmm.PeriodicTorsionForce))]
    if otras:
        raise RuntimeError(f"fuerzas no previstas en el sistema: {otras}")

    integrador = openmm.VerletIntegrator(0.001)
    contexto = openmm.Context(sistema, integrador, openmm.Platform.getPlatformByName("Reference"))
    contexto.setPositions(posiciones)

    kcal = unit.kilocalories_per_mole
    kcal_a = kcal / unit.angstrom

    def grupo(g: int) -> tuple[float, np.ndarray]:
        estado = contexto.getState(getEnergy=True, getForces=True, groups={g})
        return (estado.getPotentialEnergy().value_in_unit(kcal),
                estado.getForces(asNumpy=True).value_in_unit(kcal_a))

    e_enl, f_enl = grupo(GRUPO_ENLACE)
    e_nb, f_nb = grupo(GRUPO_NB)
    e_gb, f_gb = grupo(GRUPO_GB) if gbn2 else (0.0, np.zeros_like(f_nb))
    total = contexto.getState(getEnergy=True, getForces=True)
    e_tot = total.getPotentialEnergy().value_in_unit(kcal)
    f_tot = total.getForces(asNumpy=True).value_in_unit(kcal_a)

    # La parte de Lennard-Jones: la misma NonbondedForce con las cargas a cero.
    for i in range(nb.getNumParticles()):
        _, sigma, epsilon = nb.getParticleParameters(i)
        nb.setParticleParameters(i, 0.0, sigma, epsilon)
    for j in range(nb.getNumExceptions()):
        a, b, _, sigma, epsilon = nb.getExceptionParameters(j)
        nb.setExceptionParameters(j, a, b, 0.0, sigma, epsilon)
    nb.updateParametersInContext(contexto)
    e_lj, f_lj = grupo(GRUPO_NB)
    e_coul, f_coul = e_nb - e_lj, f_nb - f_lj

    parametros_gb = None
    if gbn2:
        nombres = [gb.getPerParticleParameterName(i) for i in range(gb.getNumPerParticleParameters())]
        parametros_gb = {i: dict(zip(nombres, gb.getParticleParameters(i), strict=True))
                         for i in range(gb.getNumParticles())}
    return {
        "energia_kcal_mol": e_tot,
        "grupos_kcal_mol": {"enlace": e_enl, "lennard_jones": e_lj, "coulomb": e_coul, "gb": e_gb},
        "fuerzas": f_tot,
        "fuerzas_convertidas": (f_enl + f_lj + f_coul * (K_AMBER / K_OPENMM_NB)
                                + f_gb * (K_AMBER / K_OPENMM_GB)),
        "energia_convertida_kcal_mol": (e_enl + e_lj + e_coul * (K_AMBER / K_OPENMM_NB)
                                        + e_gb * (K_AMBER / K_OPENMM_GB)),
        "desvio_suma_grupos_kcal_mol": abs(e_tot - (e_enl + e_nb + e_gb)),
        "desvio_suma_fuerzas_kcal_mol_A": float(np.max(np.abs(f_tot - (f_enl + f_nb + f_gb)))),
        "fosforo_corregido": fosforo,
        "avisos": sorted({str(a.message) for a in avisos}),
        "_parametros_gb": parametros_gb,
    }


# ── sander ───────────────────────────────────────────────────────────────

def _sander(prmtop: Path, coords: np.ndarray, gbn2: bool) -> dict[str, Any]:
    import sander
    opciones = sander.gas_input(8) if gbn2 else sander.gas_input()
    opciones.cut = 999.0
    opciones.gbsa = 0
    opciones.extdiel = 78.5
    opciones.intdiel = 1.0
    # Un array, no una lista: con NumPy 2 pysander hace np.array(copy=False).
    with sander.setup(str(prmtop), np.ascontiguousarray(coords, dtype=np.float64), None, opciones):
        e, f = sander.energy_forces()
    terminos = {k: float(getattr(e, k)) for k in
                ("tot", "bond", "angle", "dihedral", "vdw", "elec", "vdw_14", "elec_14", "gb", "surf")}
    return {"terminos_kcal_mol": terminos, "fuerzas": np.asarray(f, dtype=np.float64).reshape((-1, 3))}


# ── Atribución del azufre ────────────────────────────────────────────────
#
# Visto en el piloto (3 ligandos, antes del prerregistro): 1c5n (I + S) no
# pasa en GBn2 y los átomos con más error son el S y sus vecinos, no el I. En
# la tabla GBn2 de OpenMM el S es el único elemento con apantallamiento
# NEGATIVO (-0.703469). Conjetura, sin leer la fuente de sander: con sj < 0
# entra siempre en su desarrollo en serie de largo alcance (dij > 4·sj) y
# OpenMM evalúa la integral exacta.
#
# Prueba decisiva, en los DOS programas a la vez: el mismo prmtop con el
# número atómico del S cambiado a 34 (Se, sin parámetros GBn2 propios en
# ninguno de los dos: apantallamiento 0.5 y α, β, γ por defecto). Radios,
# tipos, cargas y términos de enlace no cambian. Si la paridad vuelve, el
# desacuerdo es del azufre. No es un parámetro propuesto: es un diagnóstico.

Z_SUSTITUTO_AZUFRE = 34


def _prmtop_azufre_generico(prmtop: Path, destino: Path) -> int:
    lineas = prmtop.read_text().splitlines(keepends=True)
    inicio = next(i for i, linea in enumerate(lineas) if linea.startswith("%FLAG ATOMIC_NUMBER"))
    if not lineas[inicio + 1].startswith("%FORMAT(10I8)"):
        raise RuntimeError("ATOMIC_NUMBER sin el formato 10I8 esperado")
    fin = next(i for i in range(inicio + 2, len(lineas)) if lineas[i].startswith("%FLAG"))
    valores = [int(linea[k:k + 8]) for linea in lineas[inicio + 2:fin]
               for k in range(0, len(linea.rstrip("\n")), 8)]
    cambiados = sum(1 for v in valores if v == 16)
    nuevos = [Z_SUSTITUTO_AZUFRE if v == 16 else v for v in valores]
    bloque = ["".join(f"{v:8d}" for v in nuevos[k:k + 10]) + "\n" for k in range(0, len(nuevos), 10)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("".join(lineas[:inicio + 2] + bloque + lineas[fin:]))
    return cambiados


def _atribuir_azufre(pid: str, prmtop: Path, inpcrd: Path, coords: np.ndarray, derivados: Path) -> dict[str, Any]:
    from openmm import app
    copia = derivados / pid / "ligand.S_como_Se.prmtop"
    n = _prmtop_azufre_generico(prmtop, copia)
    topologia = app.AmberPrmtopFile(str(copia))
    om = _openmm(topologia, app.AmberInpcrdFile(str(inpcrd)).positions, True)
    sa = _sander(copia, coords, True)
    t = sa["terminos_kcal_mol"]
    diferencia = ((K_OPENMM_NB / K_AMBER - 1) * (t["elec"] + t["elec_14"])
                  + (K_OPENMM_GB / K_AMBER - 1) * t["gb"])
    residuo = abs(om["energia_kcal_mol"] - t["tot"] - diferencia)
    fuerza = float(np.max(np.abs(om["fuerzas_convertidas"] - sa["fuerzas"])))
    return {"atomos_de_azufre": n, "prmtop_derivado_sha256": _sha(copia),
            "residuo_kcal_mol": residuo, "max_error_fuerza_kcal_mol_A": fuerza,
            "paridad_recuperada": residuo < TOLERANCIA_ENERGIA and fuerza < TOLERANCIA_FUERZA}


# ── Un ligando ───────────────────────────────────────────────────────────

def _medir_uno(pid: str, trabajo: str, con_sander: bool, derivados: str | None = None) -> dict[str, Any]:
    from openmm import app, unit
    carpeta = Path(trabajo) / pid
    t0 = time.time()
    try:
        prmtop, inpcrd = carpeta / "ligand.prmtop", carpeta / "ligand.inpcrd"
        topologia = app.AmberPrmtopFile(str(prmtop))
        coordenadas = app.AmberInpcrdFile(str(inpcrd))
        coords = np.array(coordenadas.positions.value_in_unit(unit.angstrom), dtype=np.float64)
        numeros = [0 if e is None else e.atomic_number for e in topologia.elements]
        crudo = topologia._prmtop._raw_data
        radios_top = [float(x) for x in crudo["RADII"]]
        screen_top = [float(x) for x in crudo["SCREEN"]]
        halos = [i for i, z in enumerate(numeros) if z in HALOGENOS]
        resultado: dict[str, Any] = {
            "pid": pid, "estado": "ok", "n_atomos": len(numeros),
            "halogenos": {s: sum(1 for z in numeros if z == n) for n, s in HALOGENOS.items()
                          if any(z == n for z in numeros)},
            "tiene_fosforo": 15 in numeros, "tiene_azufre": 16 in numeros,
            "prmtop_sha256": _sha(prmtop), "inpcrd_sha256": _sha(inpcrd),
            "condiciones": {},
        }
        for nombre, gbn2 in (("vacuum", False), ("GBn2_no_SA", True)):
            om = _openmm(topologia, coordenadas.positions, gbn2)
            parametros = om.pop("_parametros_gb")
            fila: dict[str, Any] = {
                "openmm_kcal_mol": om["energia_kcal_mol"],
                "openmm_convertida_kcal_mol": om["energia_convertida_kcal_mol"],
                "openmm_grupos_kcal_mol": om["grupos_kcal_mol"],
                "desvio_suma_grupos_kcal_mol": om["desvio_suma_grupos_kcal_mol"],
                "desvio_suma_fuerzas_kcal_mol_A": om["desvio_suma_fuerzas_kcal_mol_A"],
                "fosforo_corregido": om["fosforo_corregido"], "avisos_openmm": om["avisos"],
                "fuerzas_openmm": om["fuerzas"].tolist(),
                "fuerzas_openmm_convertidas": om["fuerzas_convertidas"].tolist(),
            }
            if parametros is not None:
                fila["parametros_gb_halogenos"] = [{
                    "indice": i, "elemento": HALOGENOS[numeros[i]],
                    "tipo_amber": topologia._prmtop.getAtomType(i),
                    "radio_prmtop_A": radios_top[i], "screen_prmtop": screen_top[i],
                    "openmm": {k: (v * 10 if k in ("or", "sr") else v) for k, v in parametros[i].items()
                               if k not in ("charge", "radindex")},
                } for i in halos]
            if con_sander:
                sa = _sander(prmtop, coords, gbn2)
                t = sa["terminos_kcal_mol"]
                diferencia = ((K_OPENMM_NB / K_AMBER - 1) * (t["elec"] + t["elec_14"])
                              + (K_OPENMM_GB / K_AMBER - 1) * t["gb"])
                fila.update({
                    "sander_terminos_kcal_mol": t,
                    "fuerzas_sander": sa["fuerzas"].tolist(),
                    "error_bruto_kcal_mol": abs(om["energia_kcal_mol"] - t["tot"]),
                    "diferencia_de_constantes_kcal_mol": diferencia,
                    "residuo_kcal_mol": abs(om["energia_kcal_mol"] - t["tot"] - diferencia),
                    "residuo_conversion_exacta_kcal_mol": abs(om["energia_convertida_kcal_mol"] - t["tot"]),
                    "max_error_fuerza_bruto_kcal_mol_A":
                        float(np.max(np.abs(om["fuerzas"] - sa["fuerzas"]))),
                    "max_error_fuerza_kcal_mol_A":
                        float(np.max(np.abs(om["fuerzas_convertidas"] - sa["fuerzas"]))),
                    "gb_openmm_convertido_menos_sander_kcal_mol":
                        om["grupos_kcal_mol"]["gb"] * (K_AMBER / K_OPENMM_GB) - t["gb"],
                })
                fila["pasa"] = (fila["residuo_kcal_mol"] < TOLERANCIA_ENERGIA
                                and fila["max_error_fuerza_kcal_mol_A"] < TOLERANCIA_FUERZA)
            resultado["condiciones"][nombre] = fila
        if con_sander and 16 in numeros and derivados:
            resultado["atribucion_azufre"] = _atribuir_azufre(pid, prmtop, inpcrd, coords, Path(derivados))
        resultado["duracion_s"] = round(time.time() - t0, 2)
        return resultado
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"pid": pid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:500],
                "duracion_s": round(time.time() - t0, 2)}


def _entorno(con_sander: bool) -> dict[str, Any]:
    import openmm
    entorno = {"python": sys.version.split()[0], "ejecutable": sys.executable,
               "plataforma": platform.platform(), "openmm": openmm.__version__,
               "numpy": np.__version__, "sander": None}
    if con_sander:
        import sander
        entorno["sander"] = getattr(sander, "__file__", None)
        for var in ("AMBERHOME",):
            entorno[var] = os.environ.get(var)
    return entorno


def medir(args) -> int:
    trabajo = Path(args.trabajo)
    pids = sorted(p.name for p in trabajo.iterdir()
                  if (p / "ligand.prmtop").is_file() and (p / "ligand.inpcrd").is_file())
    if args.solo:
        pids = [p for p in pids if p in set(args.solo)]
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
            estado = r["estado"] if r["estado"] != "ok" or not con_sander else (
                "PASA" if all(c["pasa"] for c in r["condiciones"].values()) else "NO PASA")
            print(f"  [{i}/{len(pids)}] {r['pid']}: {estado} {r.get('motivo', '')}", flush=True)
    resultados.sort(key=lambda r: r["pid"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps({
        "experimento": "MMGBSA-H5-GBN2-PARIDAD", "generado_utc": _ahora(),
        "con_sander": con_sander, "entorno": _entorno(con_sander),
        "duracion_s": round(time.time() - t0, 1), "ligandos": resultados,
    }, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"escrito {salida} ({len(resultados)} ligandos, {round(time.time() - t0, 1)} s)")
    return 0


# ── Cruce y resumen ──────────────────────────────────────────────────────

def _max(valores) -> float | None:
    valores = [v for v in valores if v is not None]
    return float(max(valores)) if valores else None


def comparar(args) -> int:
    linux_ruta = Path(args.linux)
    linux = json.loads(linux_ruta.read_text(encoding="utf-8"))
    if not linux["con_sander"]:
        raise SystemExit("--linux debe ser la corrida con sander")
    windows_ruta = Path(args.windows) if args.windows else None
    windows = json.loads(windows_ruta.read_text(encoding="utf-8")) if windows_ruta else None
    por_pid_w = {r["pid"]: r for r in windows["ligandos"]} if windows else {}

    filas = []
    for r in linux["ligandos"]:
        fila: dict[str, Any] = {"pid": r["pid"], "estado": r["estado"]}
        if r["estado"] != "ok":
            fila["motivo"] = r.get("motivo")
            filas.append(fila)
            continue
        fila.update({"halogenos": r["halogenos"], "n_atomos": r["n_atomos"],
                     "tiene_fosforo": r["tiene_fosforo"],
                     "prmtop_sha256": r["prmtop_sha256"], "inpcrd_sha256": r["inpcrd_sha256"],
                     "condiciones": {}})
        w = por_pid_w.get(r["pid"])
        if windows is not None:
            fila["mismas_entradas_en_windows"] = bool(
                w and w["estado"] == "ok" and w["prmtop_sha256"] == r["prmtop_sha256"]
                and w["inpcrd_sha256"] == r["inpcrd_sha256"])
        for nombre, c in r["condiciones"].items():
            cf: dict[str, Any] = {k: c[k] for k in (
                "openmm_kcal_mol", "error_bruto_kcal_mol", "diferencia_de_constantes_kcal_mol",
                "residuo_kcal_mol", "residuo_conversion_exacta_kcal_mol",
                "max_error_fuerza_bruto_kcal_mol_A", "max_error_fuerza_kcal_mol_A",
                "gb_openmm_convertido_menos_sander_kcal_mol", "fosforo_corregido", "avisos_openmm",
                "desvio_suma_grupos_kcal_mol", "pasa")}
            cf["sander_tot_kcal_mol"] = c["sander_terminos_kcal_mol"]["tot"]
            cf["sander_gb_kcal_mol"] = c["sander_terminos_kcal_mol"]["gb"]
            if "parametros_gb_halogenos" in c:
                cf["parametros_gb_halogenos"] = c["parametros_gb_halogenos"]
            if w and w["estado"] == "ok" and nombre in w["condiciones"]:
                cw = w["condiciones"][nombre]
                fs = np.asarray(c["fuerzas_sander"])
                fw = np.asarray(cw["fuerzas_openmm"])
                fwc = np.asarray(cw["fuerzas_openmm_convertidas"])
                fl = np.asarray(c["fuerzas_openmm"])
                t = c["sander_terminos_kcal_mol"]
                residuo_w = abs(cw["openmm_kcal_mol"] - t["tot"] - c["diferencia_de_constantes_kcal_mol"])
                cf["windows"] = {
                    "openmm_kcal_mol": cw["openmm_kcal_mol"],
                    "residuo_contra_sander_kcal_mol": residuo_w,
                    "max_error_fuerza_contra_sander_kcal_mol_A": float(np.max(np.abs(fwc - fs))),
                    "diferencia_energia_contra_openmm_linux_kcal_mol":
                        abs(cw["openmm_kcal_mol"] - c["openmm_kcal_mol"]),
                    "max_diferencia_fuerza_contra_openmm_linux_kcal_mol_A": float(np.max(np.abs(fw - fl))),
                    "avisos_openmm": cw["avisos_openmm"],
                }
                cf["windows"]["pasa"] = (residuo_w < TOLERANCIA_ENERGIA
                                         and cf["windows"]["max_error_fuerza_contra_sander_kcal_mol_A"]
                                         < TOLERANCIA_FUERZA)
            fila["condiciones"][nombre] = cf
        fila["pasa"] = all(cf["pasa"] for cf in fila["condiciones"].values())
        fila["tiene_azufre"] = r["tiene_azufre"]
        if "atribucion_azufre" in r:
            fila["atribucion_azufre"] = r["atribucion_azufre"]
        # El criterio del gate, declarado antes de la corrida completa: pasa, o
        # el vacío pasa y el desacuerdo de GBn2 desaparece con el S genérico.
        fila["pasa_gate"] = fila["pasa"] or bool(
            r["tiene_azufre"] and fila["condiciones"]["vacuum"]["pasa"]
            and r.get("atribucion_azufre", {}).get("paridad_recuperada"))
        if windows is not None:
            fila["pasa_windows"] = all(cf.get("windows", {}).get("pasa", False)
                                       for cf in fila["condiciones"].values())
        filas.append(fila)

    ok = [f for f in filas if f["estado"] == "ok"]

    def es_bri(f):
        return "Br" in f["halogenos"] or "I" in f["halogenos"]

    def resumen(grupo: list[dict[str, Any]]) -> dict[str, Any]:
        con_s = [f for f in grupo if f["tiene_azufre"]]
        salida: dict[str, Any] = {
            "n": len(grupo), "pasan": sum(f["pasa"] for f in grupo),
            "pasan_gate": sum(f["pasa_gate"] for f in grupo),
            "con_azufre": {"n": len(con_s), "pasan": sum(f["pasa"] for f in con_s),
                           "paridad_recuperada_con_S_generico": sum(
                               bool(f.get("atribucion_azufre", {}).get("paridad_recuperada")) for f in con_s),
                           "max_residuo_con_S_generico_kcal_mol": _max(
                               f.get("atribucion_azufre", {}).get("residuo_kcal_mol") for f in con_s)},
            "sin_azufre": {"n": len(grupo) - len(con_s),
                           "pasan": sum(f["pasa"] for f in grupo if not f["tiene_azufre"])},
        }
        for nombre in ("vacuum", "GBn2_no_SA"):
            cs = [f["condiciones"][nombre] for f in grupo]
            salida[nombre] = {
                "pasan": sum(c["pasa"] for c in cs),
                "max_residuo_kcal_mol": _max(c["residuo_kcal_mol"] for c in cs),
                "max_error_fuerza_kcal_mol_A": _max(c["max_error_fuerza_kcal_mol_A"] for c in cs),
                "max_error_fuerza_bruto_kcal_mol_A": _max(c["max_error_fuerza_bruto_kcal_mol_A"] for c in cs),
            }
            if windows is not None:
                ws = [c.get("windows") for c in cs]
                salida[nombre]["windows"] = {
                    "pasan": sum(bool(x and x["pasa"]) for x in ws),
                    "max_residuo_contra_sander_kcal_mol": _max(x and x["residuo_contra_sander_kcal_mol"] for x in ws),
                    "max_diferencia_energia_contra_linux_kcal_mol":
                        _max(x and x["diferencia_energia_contra_openmm_linux_kcal_mol"] for x in ws),
                    "max_diferencia_fuerza_contra_linux_kcal_mol_A":
                        _max(x and x["max_diferencia_fuerza_contra_openmm_linux_kcal_mol_A"] for x in ws),
                }
        if windows is not None:
            salida["pasan_windows"] = sum(f.get("pasa_windows", False) for f in grupo)
        return salida

    parametros = {}
    for f in ok:
        for p in f["condiciones"]["GBn2_no_SA"].get("parametros_gb_halogenos", []):
            clave = (p["elemento"], p["tipo_amber"], p["radio_prmtop_A"], p["screen_prmtop"],
                     tuple(round(v, 6) for v in p["openmm"].values()))
            parametros.setdefault(clave, {"elemento": p["elemento"], "tipo_amber": p["tipo_amber"],
                                          "radio_prmtop_A": p["radio_prmtop_A"],
                                          "screen_prmtop": p["screen_prmtop"],
                                          "openmm": p["openmm"], "n_atomos": 0})["n_atomos"] += 1

    bri = [f for f in ok if es_bri(f)]
    control = [f for f in ok if not es_bri(f)]
    crudos = {"linux": {"archivo": linux_ruta.name, "sha256": _sha(linux_ruta), "entorno": linux["entorno"]}}
    if windows_ruta:
        crudos["windows"] = {"archivo": windows_ruta.name, "sha256": _sha(windows_ruta),
                             "entorno": windows["entorno"]}
    metricas = {
        "experimento": "MMGBSA-H5-GBN2-PARIDAD", "generado_utc": _ahora(),
        "tolerancias": {"energia_kcal_mol": TOLERANCIA_ENERGIA, "fuerza_kcal_mol_A": TOLERANCIA_FUERZA},
        "constantes": {"K_AMBER": K_AMBER, "K_OPENMM_NB": K_OPENMM_NB, "K_OPENMM_GB": K_OPENMM_GB},
        "n_topologias": len(filas), "fallos": [f for f in filas if f["estado"] != "ok"],
        "br_i": resumen(bri), "control_f_cl": resumen(control),
        "parametros_gb_por_halogeno": sorted(parametros.values(),
                                             key=lambda p: (p["elemento"], p["tipo_amber"])),
        "crudos": crudos,
        "gate": ("24/24 topologías con Br o I pasan en vacuum y GBn2_no_SA, o —sólo si llevan S— el "
                 "vacío pasa y el desacuerdo de GBn2 desaparece con el S como elemento genérico en ambos "
                 "programas; y OpenMM de Windows reproduce al de Linux (< 1e-6)"),
        "pasa_gate": bool(bri) and len(bri) == 24 and all(f["pasa_gate"] for f in bri),
        "no_demuestra": ("Que GBn2 describa bien la solvatación de Br o I. Demuestra, si pasa, que OpenMM "
                         "y sander calculan lo mismo con los mismos parámetros, y registra cuáles son."),
    }
    if windows is not None:
        entre = [cf.get("windows") for f in ok for cf in f["condiciones"].values()]
        metricas["windows_reproduce_linux"] = {
            "tolerancia": TOLERANCIA_ENTRE_MAQUINAS,
            "comparaciones": sum(x is not None for x in entre),
            "esperadas": 2 * len(ok),
            "mismas_entradas": sum(bool(f.get("mismas_entradas_en_windows")) for f in ok),
            "max_diferencia_energia_kcal_mol": _max(x and x["diferencia_energia_contra_openmm_linux_kcal_mol"] for x in entre),
            "max_diferencia_fuerza_kcal_mol_A": _max(x and x["max_diferencia_fuerza_contra_openmm_linux_kcal_mol_A"] for x in entre),
        }
        w = metricas["windows_reproduce_linux"]
        metricas["pasa_gate_windows"] = bool(
            w["comparaciones"] == w["esperadas"] and w["mismas_entradas"] == len(ok)
            and w["max_diferencia_energia_kcal_mol"] < TOLERANCIA_ENTRE_MAQUINAS
            and w["max_diferencia_fuerza_kcal_mol_A"] < TOLERANCIA_ENTRE_MAQUINAS)
    destino = Path(args.artefactos)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    for grupo in ("br_i", "control_f_cl"):
        d = metricas[grupo]
        print(f"{grupo}: pasan {d['pasan']}/{d['n']} (gate {d['pasan_gate']}/{d['n']}); sin S {d['sin_azufre']['pasan']}"
              f"/{d['sin_azufre']['n']}; con S {d['con_azufre']['pasan']}/{d['con_azufre']['n']}, paridad con S "
              f"genérico {d['con_azufre']['paridad_recuperada_con_S_generico']}/{d['con_azufre']['n']}")
    print(f"fallos de ejecución: {len(metricas['fallos'])}")
    if windows is not None:
        print(f"Windows contra Linux: {metricas['windows_reproduce_linux']}")
    def num(v):
        return "—" if v is None else f"{v:.2e}"

    for grupo in ("br_i", "control_f_cl"):
        for nombre in ("vacuum", "GBn2_no_SA"):
            d = metricas[grupo][nombre]
            linea = (f"  {grupo:13s} {nombre:11s} pasan {d['pasan']:2d}  residuo máx {num(d['max_residuo_kcal_mol'])}"
                     f"  fuerza máx {num(d['max_error_fuerza_kcal_mol_A'])} (bruta {num(d['max_error_fuerza_bruto_kcal_mol_A'])})")
            if "windows" in d:
                linea += f"  | Windows pasan {d['windows']['pasan']:2d}"
            print(linea)
    for p in metricas["parametros_gb_por_halogeno"]:
        print(f"  {p['elemento']:2s} {p['tipo_amber']:3s} radio {p['radio_prmtop_A']} screen {p['screen_prmtop']}"
              f"  OpenMM {p['openmm']}  ({p['n_atomos']} átomos)")
    print(f"gate: {'PASA' if metricas['pasa_gate'] else 'NO PASA'}"
          + (f"; Windows: {'PASA' if metricas['pasa_gate_windows'] else 'NO PASA'}" if windows else ""))
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
    m.add_argument("--solo", nargs="*")
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
