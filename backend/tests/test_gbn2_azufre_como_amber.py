"""GBn2 con azufre: el OpenMM que viaja calcula el modelo de Amber sólo con la corrección.

MMGBSA-H13-AZUFRE-AMBER (sellado) midió que OpenMM 8.5.2 evalúa el
descreening de GBn2 en forma cerrada para todo par, mientras egb.F90 —el
código con el que se parametrizó GBn2— usa una serie para dij > 4*sj, y el
apantallamiento negativo del azufre hace que ese caso se dé SIEMPRE. En un
dipéptido ACE-Met-Cys-NME la diferencia es 0,92 kcal/mol. Estas pruebas
reproducen la referencia de sander con el runtime embebido, sin AmberTools
ni red, y exigen que el guardián vea el fallo cuando falta la corrección:
una prueba sólo con Ala, Gly o Leu no podría descubrirlo.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from services.chemistry.amber_compatibility import (
    apply_amber_gbn2_descreening,
    apply_amber_gbn2_phosphorus,
)

REFERENCIA = Path(__file__).resolve().parents[1] / "audits" / "amber_reference_azufre"
SIN_AZUFRE = Path(__file__).resolve().parents[1] / "audits" / "amber_reference" / "aspirin"
K_AMBER = 18.2223 ** 2
K_OPENMM_GB = 138.935485 * 10 / 4.184


def _gb(carpeta: Path, corregir: bool):
    openmm = pytest.importorskip("openmm")
    from openmm import app, unit
    topologia = app.AmberPrmtopFile(str(carpeta / "ligand.prmtop"))
    posiciones = app.AmberInpcrdFile(str(carpeta / "ligand.inpcrd")).positions
    sistema = topologia.createSystem(nonbondedMethod=app.NoCutoff, constraints=None, implicitSolvent=app.GBn2,
                                     soluteDielectric=1.0, solventDielectric=78.5, sasaMethod=None,
                                     removeCMMotion=False)
    apply_amber_gbn2_phosphorus(sistema, topologia.topology)
    if corregir:
        apply_amber_gbn2_descreening(sistema)
    for fuerza in sistema.getForces():
        fuerza.setForceGroup(1 if isinstance(fuerza, openmm.CustomGBForce) else 0)
    contexto = openmm.Context(sistema, openmm.VerletIntegrator(0.001), openmm.Platform.getPlatformByName("Reference"))
    contexto.setPositions(posiciones)
    estado = contexto.getState(getEnergy=True, getForces=True, groups={1})
    energia = estado.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole) * K_AMBER / K_OPENMM_GB
    fuerzas = estado.getForces(asNumpy=True).value_in_unit(unit.kilocalories_per_mole / unit.angstrom)
    return energia, fuerzas * K_AMBER / K_OPENMM_GB


def test_la_referencia_es_la_sellada():
    manifest = json.loads((REFERENCIA / "manifest.json").read_text())
    for nombre, esperado in manifest["artifacts"].items():
        assert hashlib.sha256((REFERENCIA / nombre).read_bytes()).hexdigest() == esperado
    assert manifest["protocol_status"] == "EXPERIMENTAL_NOT_ENABLED"


def test_con_la_correccion_openmm_reproduce_a_sander_con_met_y_cys():
    ref = json.loads((REFERENCIA / "pep_met_cys" / "sander_gbn2.json").read_text(encoding="utf-8"))
    energia, _ = _gb(REFERENCIA / "pep_met_cys", corregir=True)
    assert abs(energia - ref["sander_gb_kcal_mol"]) < 1e-3


def test_sin_la_correccion_el_azufre_discrepa():
    # El guardián demuestra que ve: sin la corrección, el mismo dipéptido se
    # separa de sander casi 1 kcal/mol en el término GB.
    ref = json.loads((REFERENCIA / "pep_met_cys" / "sander_gbn2.json").read_text(encoding="utf-8"))
    energia, _ = _gb(REFERENCIA / "pep_met_cys", corregir=False)
    assert abs(energia - ref["sander_gb_kcal_mol"]) > 0.5


def test_sin_azufre_la_correccion_no_cambia_nada():
    sin, f_sin = _gb(SIN_AZUFRE, corregir=False)
    con, f_con = _gb(SIN_AZUFRE, corregir=True)
    assert abs(con - sin) < 1e-5
    assert float(np.max(np.abs(f_con - f_sin))) < 1e-4


def test_se_niega_a_reescribir_una_expresion_que_no_conoce():
    openmm = pytest.importorskip("openmm")
    from openmm import app
    topologia = app.AmberPrmtopFile(str(REFERENCIA / "pep_met_cys" / "ligand.prmtop"))
    sistema = topologia.createSystem(nonbondedMethod=app.NoCutoff, implicitSolvent=app.GBn2, sasaMethod=None)
    gb = next(f for f in sistema.getForces() if isinstance(f, openmm.CustomGBForce))
    nombre, expresion, tipo = gb.getComputedValueParameters(0)
    gb.setComputedValueParameters(0, nombre, expresion + "+0", tipo)
    with pytest.raises(ValueError, match="refusing"):
        apply_amber_gbn2_descreening(sistema)
