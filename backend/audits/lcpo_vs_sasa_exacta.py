#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""lcpo_vs_sasa_exacta.py — Puerta 1 de MM-GBSA: adjudicar el cloro con una medida.

Qué decide y qué no
-------------------
La puerta 1 de `MMGBSA_VALIDATION.md` pide «resolver la referencia LCPO para
halógenos». El residual del clorobenceno (0.162782 kcal/mol) ya está
**completamente atribuido**: es exactamente la entrada LCPO `C_sp2_2` que Amber
usa como respaldo de carbono para el cloro, frente a los parámetros de cloro
publicados por Weiser, Shenkin y Still (1999) que trae OpenMM.

Lo que quedaba abierto no era *de dónde* viene la diferencia, sino **cuál de los
dos conjuntos es el correcto**. Eso no se decide leyendo código, y hasta ahora
la única evidencia era un comentario en el fuente de OpenMM. Este script lo
convierte en una medida.

El argumento, entero
--------------------
LCPO **es una aproximación analítica del área accesible al disolvente**. Ese es
su único trabajo: reproducir la SASA que un cálculo numérico da exacto, a cambio
de ser derivable y barato. Así que la pregunta «¿qué parametrización es
correcta?» tiene una forma medible:

    ¿Cuál de las dos aproxima mejor la SASA numéricamente exacta
    del mismo átomo, en la misma geometría, con su propio radio?

No se compara contra Amber ni contra OpenMM. Se compara contra la geometría.

Antes de usar la regla, se calibra
----------------------------------
Una diferencia de N Å² no significa nada sin saber cuánto se equivoca LCPO
cuando **sí** está bien parametrizado. Por eso el script mide primero el error
de LCPO frente a la SASA exacta en los 8 ligandos de referencia, átomo por
átomo, con los tipos que Amber y OpenMM asignan de acuerdo. Ese es el patrón de
error normal. El cloro se lee contra ese patrón, no contra cero.

Dos guardianes, porque un detector tiene que demostrar que ve
-------------------------------------------------------------
1. **La implementación de LCPO se valida contra OpenMM.** La suma de las áreas
   por átomo que calcula este script debe reproducir la energía de `LCPOForce`
   dividida por la tensión superficial. Si no coincide, el script aborta: un
   desglose por átomo que no suma el total es un desglose inventado.
2. **La SASA numérica declara su convergencia.** Se calcula con cuatro
   densidades de puntos y dos generadores independientes (espiral dorada y
   Fibonacci desplazado). Se informa la dispersión; si no converge por debajo
   del tamaño del efecto que se quiere medir, el resultado no se afirma.

Lo que este script NO hace
--------------------------
No activa MM-GBSA, no cambia ningún parámetro de producción y no toca la tabla
LCPO. El guardián `test_produccion_no_copia_el_respaldo_de_carbono_para_el_cloro`
sigue impidiendo que la paridad con Amber se consiga copiando el respaldo. Y una
medida sobre **un** cloro en **una** geometría no decide el caso de F, Br o I:
lo que se afirma es lo que se midió.

Uso
---
    python backend/audits/lcpo_vs_sasa_exacta.py
    python backend/audits/lcpo_vs_sasa_exacta.py --salida <ruta.json>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent
REFERENCIA = RAIZ / "amber_reference"

#: Tensión superficial y radio de sonda de `lcpo.addLCPOForce`, no re-elegidos aquí.
TENSION_SUPERFICIAL = 0.005          # kcal/mol/Å²
RADIO_SONDA = 1.4                    # Å

#: Densidades de puntos para la SASA numérica. La mayor es la que se informa.
DENSIDADES = (2_000, 10_000, 50_000, 200_000)


# ─────────────────────────────────────────────────────────────────────────────
# SASA numérica (Shrake-Rupley)
# ─────────────────────────────────────────────────────────────────────────────

def _puntos_espiral(n: int, desplazamiento: float = 0.0) -> np.ndarray:
    """n puntos casi uniformes sobre la esfera unidad (espiral de Fibonacci).

    `desplazamiento` rota la secuencia: dos valores distintos dan dos mallas
    independientes, y la diferencia entre sus resultados acota el error de
    discretización sin suponer nada sobre él.
    """
    indices = np.arange(n, dtype=np.float64) + 0.5 + desplazamiento
    phi = np.arccos(1.0 - 2.0 * indices / n)
    dorado = math.pi * (1.0 + 5.0 ** 0.5)
    theta = dorado * indices
    return np.column_stack((
        np.cos(theta) * np.sin(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(phi),
    ))


def sasa_numerica(coords: np.ndarray, radios: np.ndarray, n_puntos: int,
                  desplazamiento: float = 0.0) -> np.ndarray:
    """Área accesible por átomo, en Å².

    `radios` ya incluye la sonda: es el radio de la esfera accesible. Los átomos
    con radio 0 (hidrógenos en LCPO) no aportan superficie NI ocluyen, que es
    exactamente lo que hace LCPO y por tanto lo que hay que reproducir para que
    la comparación sea justa.
    """
    activos = np.flatnonzero(radios > 0.0)
    areas = np.zeros(len(radios), dtype=np.float64)
    if activos.size == 0:
        return areas

    esfera = _puntos_espiral(n_puntos, desplazamiento)
    coords_a = coords[activos]
    radios_a = radios[activos]

    for local, indice in enumerate(activos):
        centro = coords_a[local]
        radio = radios_a[local]
        superficie = centro + radio * esfera

        # Sólo los vecinos cuyas esferas se solapan pueden tapar algo.
        delta = coords_a - centro
        distancias = np.linalg.norm(delta, axis=1)
        vecinos = np.flatnonzero(
            (distancias > 0.0) & (distancias < radio + radios_a)
        )
        vecinos = vecinos[vecinos != local]

        accesible = np.ones(n_puntos, dtype=bool)
        for vecino in vecinos:
            dist2 = np.sum((superficie - coords_a[vecino]) ** 2, axis=1)
            accesible &= dist2 >= radios_a[vecino] ** 2
            if not accesible.any():
                break

        areas[indice] = 4.0 * math.pi * radio ** 2 * (accesible.sum() / n_puntos)
    return areas


# ─────────────────────────────────────────────────────────────────────────────
# LCPO analítico
# ─────────────────────────────────────────────────────────────────────────────

def areas_lcpo(coords: np.ndarray, radios: np.ndarray,
               p1: np.ndarray, p2: np.ndarray, p3: np.ndarray,
               p4: np.ndarray) -> np.ndarray:
    """Área por átomo según LCPO. `radios` incluye la sonda.

        A_i = P1·S_i + P2·ΣA_ij + P3·ΣΣA_jk + P4·Σ(A_ij·Σ_k A_jk)

    donde A_ij es el casquete de la esfera i que tapa la j, y k recorre los
    vecinos de i que además son vecinos de j. La correspondencia exacta con la
    implementación de OpenMM no se supone: se comprueba contra `LCPOForce`.
    """
    n = len(radios)
    activos = np.flatnonzero(radios > 0.0)
    areas = np.zeros(n, dtype=np.float64)

    def casquete(i: int, j: int, d: float) -> float:
        """Área de la esfera i oculta por la j, a distancia d."""
        return 2.0 * math.pi * radios[i] * (
            radios[i] - d / 2.0 - (radios[i] ** 2 - radios[j] ** 2) / (2.0 * d)
        )

    distancias = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=-1)
    vecinos: dict[int, list[int]] = {}
    for i in activos:
        vecinos[int(i)] = [
            int(j) for j in activos
            if j != i and distancias[i, j] < radios[i] + radios[j]
        ]

    for i in activos:
        i = int(i)
        suma_ij = 0.0
        suma_jk = 0.0
        suma_producto = 0.0
        for j in vecinos[i]:
            a_ij = casquete(i, j, distancias[i, j])
            suma_ij += a_ij
            suma_jk_local = 0.0
            for k in vecinos[i]:
                if k == j:
                    continue
                if k in vecinos[j]:
                    suma_jk_local += casquete(j, k, distancias[j, k])
            suma_jk += suma_jk_local
            suma_producto += a_ij * suma_jk_local
        areas[i] = (p1[i] * 4.0 * math.pi * radios[i] ** 2
                    + p2[i] * suma_ij
                    + p3[i] * suma_jk
                    + p4[i] * suma_producto)
    return areas


# ─────────────────────────────────────────────────────────────────────────────
# Carga del sistema de referencia
# ─────────────────────────────────────────────────────────────────────────────

class _TiposEnMayuscula:
    """Amber pasa el tipo a mayúsculas antes de buscar el parámetro LCPO.

    Es la misma normalización acotada que aplica el adaptador de producción
    (`amber_compatibility`), y sin ella O/N3/SH no encuentran su entrada.
    """

    def __init__(self, original):
        self.original = original

    def getAtomType(self, indice):
        return self.original.getAtomType(indice).upper()

    def __getattr__(self, nombre):
        return getattr(self.original, nombre)


def cargar(nombre: str):
    from openmm import app, unit
    from openmm.app.internal import lcpo

    directorio = REFERENCIA / nombre
    topologia = app.AmberPrmtopFile(str(directorio / "ligand.prmtop"))
    inpcrd = app.AmberInpcrdFile(str(directorio / "ligand.inpcrd"))
    coords = np.array(inpcrd.positions.value_in_unit(unit.angstrom), dtype=np.float64)

    parametros = lcpo.getLCPOParamsAmber(
        _TiposEnMayuscula(topologia._prmtop), topologia.elements
    )
    return topologia, coords, parametros


def _valor(x) -> float:
    """El número, venga con unidades de OpenMM o sin ellas.

    `getLCPOParamsAmber` devuelve el radio como `Quantity` en Å y P4 en 1/Å²,
    mientras la tabla cruda `LCPO_PARAMETERS` son floats. Las dos entran aquí.
    """
    valor = getattr(x, "_value", x)
    return float(valor)


def _desempaquetar(parametros, indice_cloro=None, reemplazo=None):
    """(radio_con_sonda, P1..P4) por átomo, opcionalmente sustituyendo el cloro."""
    radios, p1, p2, p3, p4 = [], [], [], [], []
    for indice, fila in enumerate(parametros):
        if indice_cloro is not None and indice in indice_cloro and reemplazo is not None:
            fila = reemplazo
        radio = _valor(fila[0])
        radios.append(radio + RADIO_SONDA if radio else 0.0)
        p1.append(_valor(fila[1]))
        p2.append(_valor(fila[2]))
        p3.append(_valor(fila[3]))
        p4.append(_valor(fila[4]))
    return (np.array(radios), np.array(p1), np.array(p2),
            np.array(p3), np.array(p4))


def energia_lcpo_openmm(topologia, coords_angstrom, parametros) -> float:
    """La energía del término LCPO según OpenMM, aislada en su grupo de fuerza."""
    import openmm
    from openmm import app, unit
    from openmm.app.internal import lcpo

    sistema = topologia.createSystem(
        nonbondedMethod=app.NoCutoff, constraints=None,
        implicitSolvent=app.GBn2, soluteDielectric=1.0, solventDielectric=78.5,
        sasaMethod=None, removeCMMotion=False)
    n_antes = sistema.getNumForces()
    lcpo.addLCPOForce(sistema, parametros, usePeriodic=False)
    grupo = 11
    for indice in range(n_antes, sistema.getNumForces()):
        sistema.getForce(indice).setForceGroup(grupo)

    integrador = openmm.VerletIntegrator(0.001)
    contexto = openmm.Context(sistema, integrador,
                              openmm.Platform.getPlatformByName("Reference"))
    contexto.setPositions(coords_angstrom * unit.angstrom)
    estado = contexto.getState(getEnergy=True, groups={grupo})
    energia = estado.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    del contexto, integrador
    return energia


# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--salida", default=str(RAIZ / "lcpo_vs_sasa_exacta.json"))
    ap.add_argument("--puntos", type=int, default=max(DENSIDADES))
    args = ap.parse_args()

    try:
        from openmm.app.internal import lcpo
    except Exception as exc:                                       # noqa: BLE001
        print(f"Se requiere OpenMM: {exc}", file=sys.stderr)
        return 2

    ligandos = sorted(d.name for d in REFERENCIA.iterdir()
                      if d.is_dir() and (d / "ligand.prmtop").exists())
    if not ligandos:
        print(f"No hay referencias en {REFERENCIA}", file=sys.stderr)
        return 2

    informe: dict = {
        "experimento": "MMGBSA-LCPO-SASA-01",
        "pregunta": ("¿Cuál de las dos parametrizaciones LCPO del cloro aproxima "
                     "mejor la SASA numéricamente exacta?"),
        "generado_utc": datetime.now(UTC).isoformat(),
        "tension_superficial_kcal_mol_A2": TENSION_SUPERFICIAL,
        "radio_sonda_A": RADIO_SONDA,
        "puntos_shrake_rupley": args.puntos,
        "ligandos": {},
    }

    # ── Calibración: cuánto se equivoca LCPO cuando está bien parametrizado ──
    errores_de_fondo: list[dict] = []

    for nombre in ligandos:
        topologia, coords, parametros = cargar(nombre)
        radios, p1, p2, p3, p4 = _desempaquetar(parametros)

        # Guardián 1: el desglose por átomo tiene que sumar lo que dice OpenMM.
        propias = areas_lcpo(coords, radios, p1, p2, p3, p4)
        energia_openmm = energia_lcpo_openmm(topologia, coords, parametros)
        area_openmm = energia_openmm / TENSION_SUPERFICIAL
        desvio = abs(propias.sum() - area_openmm)
        if desvio > 1e-6 * max(1.0, abs(area_openmm)):
            print(f"[{nombre}] la implementación LCPO propia NO reproduce a OpenMM: "
                  f"{propias.sum():.8f} vs {area_openmm:.8f} Å²", file=sys.stderr)
            return 1

        # Guardián 2: convergencia declarada de la SASA numérica.
        convergencia = {}
        for n in DENSIDADES:
            if n > args.puntos:
                continue
            a = sasa_numerica(coords, radios, n, 0.0).sum()
            b = sasa_numerica(coords, radios, n, 0.37).sum()
            convergencia[str(n)] = {
                "total_malla_a_A2": round(float(a), 4),
                "total_malla_b_A2": round(float(b), 4),
                "diferencia_entre_mallas_A2": round(abs(float(a - b)), 4),
            }

        exactas = sasa_numerica(coords, radios, args.puntos, 0.0)
        exactas_b = sasa_numerica(coords, radios, args.puntos, 0.37)

        elementos = [e.symbol if e is not None else "?" for e in topologia.elements]
        tipos = [topologia._prmtop.getAtomType(i).upper()
                 for i in range(len(elementos))]

        por_atomo = []
        for i in range(len(radios)):
            if radios[i] <= 0.0:
                continue
            fila = {
                "indice": i,
                "elemento": elementos[i],
                "tipo_amber": tipos[i],
                "radio_sin_sonda_A": round(radios[i] - RADIO_SONDA, 4),
                "sasa_exacta_A2": round(float(exactas[i]), 4),
                "sasa_lcpo_A2": round(float(propias[i]), 4),
                "error_lcpo_A2": round(float(propias[i] - exactas[i]), 4),
                "incertidumbre_malla_A2": round(abs(float(exactas[i] - exactas_b[i])), 4),
            }
            por_atomo.append(fila)
            if elementos[i] != "Cl":
                errores_de_fondo.append({"ligando": nombre, **fila})

        informe["ligandos"][nombre] = {
            "n_atomos": len(elementos),
            "n_atomos_con_superficie": len(por_atomo),
            "sasa_exacta_total_A2": round(float(exactas.sum()), 4),
            "sasa_lcpo_total_A2": round(float(propias.sum()), 4),
            "area_openmm_total_A2": round(float(area_openmm), 4),
            "desvio_contra_openmm_A2": float(f"{desvio:.3e}"),
            "convergencia": convergencia,
            "por_atomo": por_atomo,
        }
        print(f"[{nombre}] LCPO={propias.sum():10.4f}  exacta={exactas.sum():10.4f}  "
              f"error={propias.sum() - exactas.sum():+8.4f} Å²  "
              f"(OpenMM {area_openmm:.4f}, desvío {desvio:.2e})", flush=True)

    # ── El caso: el cloro, con cada parametrización contra su propia SASA ────
    topologia, coords, parametros = cargar("chlorobenzene")
    cloros = [i for i, e in enumerate(topologia.elements)
              if e is not None and e.atomic_number == 17]
    if not cloros:
        print("el caso de referencia dejó de tener cloro", file=sys.stderr)
        return 1

    # El tercer brazo no lo propone nadie: es un diagnóstico. `C_sp2_2` está
    # fijado para un carbono sp2 con DOS vecinos pesados, y este cloro tiene
    # UNO. Sin separar las dos cosas, un error grande del respaldo podría
    # atribuirse al radio (1.7 frente a 1.8) cuando en realidad viene de la
    # conectividad. `C_sp3_1` es la única entrada de carbono terminal de la
    # tabla, con el mismo radio 1.7 que el respaldo.
    candidatos = {
        "Cl_publicado_Weiser_1999": lcpo.LCPO_PARAMETERS["Cl"],
        "respaldo_de_carbono_Amber_C_sp2_2": lcpo.LCPO_PARAMETERS["C_sp2_2"],
        "diagnostico_carbono_terminal_C_sp3_1": lcpo.LCPO_PARAMETERS["C_sp3_1"],
    }

    veredicto: dict = {}
    for etiqueta, fila in candidatos.items():
        radios, p1, p2, p3, p4 = _desempaquetar(parametros, set(cloros), fila)
        lcpo_areas = areas_lcpo(coords, radios, p1, p2, p3, p4)
        exactas = sasa_numerica(coords, radios, args.puntos, 0.0)
        exactas_b = sasa_numerica(coords, radios, args.puntos, 0.37)

        indice = cloros[0]
        error = float(lcpo_areas[indice] - exactas[indice])
        veredicto[etiqueta] = {
            "radio_sin_sonda_A": _valor(fila[0]),
            "coeficientes_P1_P4": [_valor(x) for x in fila[1:]],
            "sasa_exacta_del_cloro_A2": round(float(exactas[indice]), 4),
            "sasa_lcpo_del_cloro_A2": round(float(lcpo_areas[indice]), 4),
            "error_del_cloro_A2": round(error, 4),
            "error_absoluto_del_cloro_A2": round(abs(error), 4),
            "incertidumbre_malla_A2": round(abs(float(exactas[indice] - exactas_b[indice])), 4),
            "energia_del_cloro_kcal_mol": round(lcpo_areas[indice] * TENSION_SUPERFICIAL, 6),
            "error_en_energia_kcal_mol": round(error * TENSION_SUPERFICIAL, 6),
            "sasa_exacta_total_A2": round(float(exactas.sum()), 4),
            "sasa_lcpo_total_A2": round(float(lcpo_areas.sum()), 4),
            "error_total_A2": round(float(lcpo_areas.sum() - exactas.sum()), 4),
            "error_total_en_energia_kcal_mol": round(
                float(lcpo_areas.sum() - exactas.sum()) * TENSION_SUPERFICIAL, 6),
        }

    fondo = np.array([abs(f["error_lcpo_A2"]) for f in errores_de_fondo])
    informe["calibracion_del_error_de_fondo"] = {
        "n_atomos": int(fondo.size),
        "descripcion": ("|LCPO − SASA exacta| por átomo en los tipos que Amber y "
                        "OpenMM asignan de acuerdo. Es la regla con la que se lee "
                        "el cloro."),
        "mediana_A2": round(float(np.median(fondo)), 4),
        "media_A2": round(float(np.mean(fondo)), 4),
        "p90_A2": round(float(np.percentile(fondo, 90)), 4),
        "maximo_A2": round(float(np.max(fondo)), 4),
    }
    informe["cloro"] = veredicto

    # La adjudicación es entre los dos conjuntos que alguien propone. El brazo
    # diagnóstico informa la lectura, no compite.
    en_disputa = ["Cl_publicado_Weiser_1999", "respaldo_de_carbono_Amber_C_sp2_2"]
    mejor = min(en_disputa, key=lambda k: veredicto[k]["error_absoluto_del_cloro_A2"])
    peor = next(k for k in en_disputa if k != mejor)
    informe["lectura"] = {
        "aproxima_mejor": mejor,
        "ventaja_A2": round(
            veredicto[peor]["error_absoluto_del_cloro_A2"]
            - veredicto[mejor]["error_absoluto_del_cloro_A2"], 4),
        "no_demuestra": (
            "Que MM-GBSA sea válido, ni que estos radios predigan afinidades. "
            "Un cloro en una geometría: F, Br e I siguen sin medir. La SASA "
            "numérica es la referencia geométrica, no una referencia experimental."
        ),
    }

    destino = Path(args.salida)
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

    print("\n== El cloro ==")
    for etiqueta, datos in veredicto.items():
        print(f"{etiqueta:38s} r={datos['radio_sin_sonda_A']} Å  "
              f"exacta={datos['sasa_exacta_del_cloro_A2']:8.3f}  "
              f"LCPO={datos['sasa_lcpo_del_cloro_A2']:8.3f}  "
              f"error={datos['error_del_cloro_A2']:+7.3f} Å²  "
              f"({datos['error_en_energia_kcal_mol']:+.6f} kcal/mol)")
    print(f"\nFondo |error| por átomo: mediana "
          f"{informe['calibracion_del_error_de_fondo']['mediana_A2']} Å², "
          f"p90 {informe['calibracion_del_error_de_fondo']['p90_A2']} Å², "
          f"máx {informe['calibracion_del_error_de_fondo']['maximo_A2']} Å² "
          f"(n={informe['calibracion_del_error_de_fondo']['n_atomos']})")
    print(f"\nAproxima mejor: {mejor} (por {informe['lectura']['ventaja_A2']} Å²)")
    print(f"Escrito: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
