"""La adjudicación del cloro, medida contra la geometría y no contra un código.

El residual del clorobenceno (0.162782 kcal/mol) ya estaba **atribuido**: es la
entrada LCPO `C_sp2_2` que Amber usa como respaldo de carbono para el cloro,
frente a los parámetros publicados por Weiser, Shenkin y Still (1999) que trae
OpenMM. Lo que quedaba abierto era cuál de los dos es el correcto, y hasta ahora
la única evidencia era un comentario en el fuente de OpenMM.

LCPO es una aproximación analítica de la SASA. Así que la pregunta tiene forma
medible: cuál de las dos parametrizaciones aproxima mejor la SASA numéricamente
exacta del mismo átomo, en la misma geometría, con su propio radio.

Estas pruebas fijan las tres piezas que hacen creíble la respuesta:

1. La implementación propia de LCPO reproduce la de OpenMM. Un desglose por
   átomo que no suma el total sería un desglose inventado.
2. La SASA numérica converge muy por debajo del efecto que se quiere medir. Una
   regla que se mueve más que lo que mide no mide nada.
3. Con la regla calibrada, la adjudicación se sostiene.

Ninguna de ellas activa MM-GBSA ni toca la tabla LCPO:
`test_produccion_no_copia_el_respaldo_de_carbono_para_el_cloro` sigue impidiendo
que la paridad con Amber se consiga copiando el respaldo.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from audits.lcpo_vs_sasa_exacta import (
    RADIO_SONDA,
    TENSION_SUPERFICIAL,
    _desempaquetar,
    areas_lcpo,
    cargar,
    sasa_numerica,
)

RAIZ = Path(__file__).resolve().parents[1] / "audits" / "amber_reference"
REPORT = json.loads((RAIZ / "report.json").read_text())

#: Densidad suficiente: el efecto a medir son ~27 Å² y a 10.000 puntos la
#: incertidumbre de malla está en centésimas. Subirla sólo alargaría la prueba.
PUNTOS = 10_000

LIGANDOS = sorted(d.name for d in RAIZ.iterdir()
                  if d.is_dir() and (d / "ligand.prmtop").exists())


@pytest.mark.parametrize("nombre", LIGANDOS)
def test_la_implementacion_propia_de_lcpo_reproduce_a_openmm(nombre):
    """El guardián tiene que demostrar que ve: se compara contra producción.

    No contra `lcpo.addLCPOForce` a secas, sino contra `add_gaff_lcpo_force`,
    que es el adaptador que el candidato usa de verdad. Si producción cambiara
    la derivación de parámetros, esta prueba lo nota.
    """
    openmm = pytest.importorskip("openmm")
    from openmm import app, unit

    from services.chemistry.amber_compatibility import add_gaff_lcpo_force

    topologia, coords, parametros = cargar(nombre)
    radios, p1, p2, p3, p4 = _desempaquetar(parametros)
    propias = areas_lcpo(coords, radios, p1, p2, p3, p4)

    sistema = topologia.createSystem(
        nonbondedMethod=app.NoCutoff, constraints=None,
        implicitSolvent=app.GBn2, soluteDielectric=1.0, solventDielectric=78.5,
        sasaMethod=None, removeCMMotion=False)
    n_antes = sistema.getNumForces()
    add_gaff_lcpo_force(sistema, topologia)
    grupo = 11
    for indice in range(n_antes, sistema.getNumForces()):
        sistema.getForce(indice).setForceGroup(grupo)

    integrador = openmm.VerletIntegrator(0.001)
    contexto = openmm.Context(sistema, integrador,
                              openmm.Platform.getPlatformByName("Reference"))
    contexto.setPositions(coords * unit.angstrom)
    energia = contexto.getState(getEnergy=True, groups={grupo}).getPotentialEnergy()
    energia = energia.value_in_unit(unit.kilocalories_per_mole)
    del contexto, integrador

    area_openmm = energia / TENSION_SUPERFICIAL
    assert propias.sum() == pytest.approx(area_openmm, rel=1e-9, abs=1e-6)


def test_la_sasa_numerica_converge_muy_por_debajo_del_efecto():
    """Dos mallas independientes sobre la misma geometría.

    Si difirieran en el orden del efecto (≈27 Å²), la adjudicación sería ruido
    de discretización con nombre de conclusión.
    """
    _, coords, parametros = cargar("chlorobenzene")
    radios, *_ = _desempaquetar(parametros)

    gruesa_a = sasa_numerica(coords, radios, 2_000, 0.0).sum()
    gruesa_b = sasa_numerica(coords, radios, 2_000, 0.37).sum()
    fina_a = sasa_numerica(coords, radios, PUNTOS, 0.0).sum()
    fina_b = sasa_numerica(coords, radios, PUNTOS, 0.37).sum()

    assert abs(gruesa_a - gruesa_b) < 2.0
    assert abs(fina_a - fina_b) < 0.5
    # Y la malla fina no se aleja de la gruesa: converge, no deriva.
    assert abs(fina_a - gruesa_a) < 2.0


def test_los_parametros_publicados_del_cloro_aproximan_mejor_la_superficie():
    """La adjudicación, leída contra el error normal de LCPO y no contra cero.

    Medido con 200.000 puntos por átomo: el cloro publicado se equivoca en
    2.29 Å² —la mediana del error de fondo es 2.29 Å²— y el respaldo de carbono
    en 29.12 Å², que es 3.2 veces el peor error de fondo observado (9.19 Å²).
    Los umbrales de abajo son holgados a propósito: fijan la CONCLUSIÓN, no la
    cifra, que depende de la densidad de malla y del ligando.
    """
    pytest.importorskip("openmm")
    from openmm.app.internal import lcpo

    topologia, coords, parametros = cargar("chlorobenzene")
    cloros = {i for i, e in enumerate(topologia.elements)
              if e is not None and e.atomic_number == 17}
    assert cloros, "el caso de referencia dejó de tener cloro"

    def error_del_cloro(fila) -> float:
        radios, p1, p2, p3, p4 = _desempaquetar(parametros, cloros, fila)
        estimada = areas_lcpo(coords, radios, p1, p2, p3, p4)
        exacta = sasa_numerica(coords, radios, PUNTOS, 0.0)
        indice = min(cloros)
        return float(estimada[indice] - exacta[indice])

    publicado = error_del_cloro(lcpo.LCPO_PARAMETERS["Cl"])
    respaldo = error_del_cloro(lcpo.LCPO_PARAMETERS["C_sp2_2"])

    # El error de fondo: los átomos cuyo tipo Amber y OpenMM asignan de acuerdo.
    radios, p1, p2, p3, p4 = _desempaquetar(parametros)
    estimada = areas_lcpo(coords, radios, p1, p2, p3, p4)
    exacta = sasa_numerica(coords, radios, PUNTOS, 0.0)
    fondo = np.array([abs(estimada[i] - exacta[i])
                      for i in range(len(radios))
                      if radios[i] > 0.0 and i not in cloros])

    assert abs(publicado) <= float(np.max(fondo)), (
        "el cloro publicado dejó de estar dentro del error normal de LCPO")
    assert abs(respaldo) > 3.0 * float(np.max(fondo)), (
        "el respaldo de carbono dejó de ser un caso atípico")
    assert abs(respaldo) - abs(publicado) > 20.0, (
        "la ventaja del cloro publicado dejó de ser inequívoca")


def test_la_diferencia_entre_las_dos_parametrizaciones_es_el_residual_declarado():
    """El ancla: la medida geométrica y el residual auditado son el mismo número.

    32.5565 Å² de superficie LCPO × 0.005 kcal/mol/Å² = 0.162782 kcal/mol, que
    es exactamente el residual que `report.json` declara para el clorobenceno
    con GBn2+LCPO. Sin esta prueba, la adjudicación sería un experimento
    paralelo; con ella, es el mismo hecho medido por otra vía.
    """
    pytest.importorskip("openmm")
    from openmm.app.internal import lcpo

    topologia, coords, parametros = cargar("chlorobenzene")
    cloros = {i for i, e in enumerate(topologia.elements)
              if e is not None and e.atomic_number == 17}

    def area_total(fila) -> float:
        radios, p1, p2, p3, p4 = _desempaquetar(parametros, cloros, fila)
        return float(areas_lcpo(coords, radios, p1, p2, p3, p4).sum())

    diferencia = (area_total(lcpo.LCPO_PARAMETERS["Cl"])
                  - area_total(lcpo.LCPO_PARAMETERS["C_sp2_2"])) * TENSION_SUPERFICIAL

    caso = next(c for c in REPORT["results"] if c["name"] == "chlorobenzene")
    referencia = next(c for c in caso["comparisons"]
                      if c["condition"] == "GBn2_LCPO")
    assert diferencia == pytest.approx(
        referencia["residual_after_constant_conversion_kcal_mol"], abs=1e-6)


def test_el_radio_de_sonda_y_la_tension_no_se_reeligen_aqui():
    """Las constantes salen de OpenMM, no de este experimento.

    Elegirlas aquí convertiría la adjudicación en un ajuste: cualquier respuesta
    sería alcanzable moviendo la sonda.
    """
    pytest.importorskip("openmm")
    import inspect

    from openmm.app.internal import lcpo

    firma = inspect.signature(lcpo.addLCPOForce)
    tension = firma.parameters["surfaceTension"].default
    sonda = firma.parameters["probeRadius"].default
    assert tension.value_in_unit(tension.unit) == TENSION_SUPERFICIAL
    assert sonda.value_in_unit(sonda.unit) == RADIO_SONDA
