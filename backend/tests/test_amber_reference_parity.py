"""Real Amber reference replay in the shipped Windows OpenMM, offline.

23/24 reference conditions pass; the chlorine LCPO reference discrepancy is
explicitly retained as a blocker, not included in successful parity cases.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from services.chemistry.amber_compatibility import apply_amber_gbn2_phosphorus

ROOT = Path(__file__).resolve().parents[1] / "audits" / "amber_reference"
REPORT = json.loads((ROOT / "report.json").read_text())
CASES = [(case, condition) for case in REPORT["results"] for condition in case["comparisons"]
         if condition["passed"]]


def test_reference_files_match_manifest():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for name, expected in manifest["artifacts"].items():
        assert "\\" not in name, "Manifest paths must also resolve on Linux"
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
    assert manifest["protocol_status"] == "EXPERIMENTAL_NOT_ENABLED"


@pytest.mark.parametrize("case,reference", CASES,
                         ids=[f"{case['name']}-{condition['condition']}" for case,condition in CASES])
def test_energy_and_forces_match_independent_amber(case, reference):
    openmm = pytest.importorskip("openmm")
    from openmm import app, unit
    directory = ROOT/case["name"]
    topology = app.AmberPrmtopFile(str(directory/"ligand.prmtop"))
    positions = app.AmberInpcrdFile(str(directory/"ligand.inpcrd")).positions
    solvent = app.GBn2 if reference["condition"].startswith("GBn2") else None
    system = topology.createSystem(nonbondedMethod=app.NoCutoff, constraints=None,
        implicitSolvent=solvent, soluteDielectric=1.0, solventDielectric=78.5,
        sasaMethod=None, removeCMMotion=False)
    if reference["condition"] == "GBn2_LCPO":
        from services.chemistry.amber_compatibility import add_gaff_lcpo_force
        add_gaff_lcpo_force(system, topology)
        with pytest.raises(ValueError, match="already present"):
            add_gaff_lcpo_force(system, topology)
    if solvent:
        changed = apply_amber_gbn2_phosphorus(system, topology.topology)
        assert changed == reference["phosphorus_parameters_corrected"]
        assert apply_amber_gbn2_phosphorus(system, topology.topology) == 0
    integrator = openmm.VerletIntegrator(0.001)
    context = openmm.Context(system,integrator,openmm.Platform.getPlatformByName("Reference"))
    context.setPositions(positions)
    state = context.getState(getEnergy=True,getForces=True)
    energy = state.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    force = state.getForces(asNumpy=True).value_in_unit(unit.kilocalories_per_mole/unit.angstrom)
    # Keep raw Amber energy intact; account explicitly for the documented SI
    # versus legacy Coulomb constants, not a fitted/calibrated offset.
    expected = reference["amber_kcal_mol"]+reference["documented_constant_difference_kcal_mol"]
    assert abs(energy-expected) < 0.001
    assert np.max(np.abs(force-np.array(reference["amber_forces_kcal_mol_A"]))) < 0.001



#: Los parámetros LCPO que Amber usa de verdad para el cloro, MEDIDOS.
#:
#: Amber avisa `Using carbon SA parms for atom type CL` y no dice cuáles. Con la
#: geometría de referencia, sustituir SÓLO los cinco valores LCPO del cloro por
#: cada entrada de carbono de la tabla y comparar contra sander deja una única
#: coincidencia: la entrada `C_sp2_2` completa, radio incluido. Las demás dejan
#: residuales de 0.013 a 0.176 kcal/mol.
#:
#: Esto NO se aplica en producción. Copiar el respaldo de carbono para conseguir
#: paridad sería elegir el parámetro por el resultado, que es exactamente lo que
#: el informe se negó a hacer. Vive aquí para que la atribución quede fijada: si
#: alguien cambia el adaptador, esta prueba dice qué se rompió.
RESPALDO_DE_CARBONO_PARA_CLORO = "C_sp2_2"


def test_el_desacuerdo_del_cloro_esta_completamente_atribuido():
    """El residual de 0.162782 kcal/mol es ESA divergencia y nada más.

    La diferencia entre «hay un residual que no sabemos explicar» y «el residual
    es exactamente esta divergencia de parámetros» es la diferencia entre un
    bloqueo abierto y un bloqueo acotado. Sin esta medida no se podía descartar
    que detrás del cloro hubiera un segundo error de implementación.

    Medido: con los parámetros de carbono de Amber aplicados sólo al cloro, la
    energía coincide con sander en 1.3e-8 kcal/mol y la fuerza máxima en
    6.5e-5 kcal/mol/A. Ambas dentro de los criterios declarados, que no se
    tocan. El caso sin término no polar (`GBn2_no_SA`) ya pasaba con residual
    7.1e-9, así que la divergencia está confinada al término de superficie.
    """
    openmm = pytest.importorskip("openmm")
    from openmm import app, unit
    from openmm.app.internal import lcpo

    caso = next(c for c in REPORT["results"] if c["name"] == "chlorobenzene")
    referencia = next(c for c in caso["comparisons"] if c["condition"] == "GBn2_LCPO")
    sin_sa = next(c for c in caso["comparisons"] if c["condition"] == "GBn2_no_SA")
    assert sin_sa["passed"], "sin el término no polar ya no coincide: el cloro no es el único problema"

    directorio = ROOT / "chlorobenzene"
    topologia = app.AmberPrmtopFile(str(directorio / "ligand.prmtop"))
    posiciones = app.AmberInpcrdFile(str(directorio / "ligand.inpcrd")).positions

    class TiposEnMayuscula:
        def __init__(self, original):
            self.original = original

        def getAtomType(self, indice):
            return self.original.getAtomType(indice).upper()

        def __getattr__(self, nombre):
            return getattr(self.original, nombre)

    def energia_y_fuerzas(parametros_del_cloro):
        sistema = topologia.createSystem(
            nonbondedMethod=app.NoCutoff, constraints=None,
            implicitSolvent=app.GBn2, soluteDielectric=1.0, solventDielectric=78.5,
            sasaMethod=None, removeCMMotion=False)
        parametros = lcpo.getLCPOParamsAmber(
            TiposEnMayuscula(topologia._prmtop), topologia.elements
        )
        cloros = [i for i, e in enumerate(topologia.elements)
                  if e is not None and e.atomic_number == 17]
        assert cloros, "el caso de referencia dejó de tener cloro"
        if parametros_del_cloro is not None:
            for indice in cloros:
                parametros[indice] = parametros_del_cloro
        lcpo.addLCPOForce(sistema, parametros, usePeriodic=False)
        apply_amber_gbn2_phosphorus(sistema, topologia.topology)
        integrador = openmm.VerletIntegrator(0.001)
        contexto = openmm.Context(
            sistema, integrador, openmm.Platform.getPlatformByName("Reference")
        )
        contexto.setPositions(posiciones)
        estado = contexto.getState(getEnergy=True, getForces=True)
        energia = estado.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
        fuerzas = estado.getForces(asNumpy=True).value_in_unit(
            unit.kilocalories_per_mole / unit.angstrom
        )
        del contexto, integrador
        return energia, fuerzas

    esperado = (referencia["amber_kcal_mol"]
                + referencia["documented_constant_difference_kcal_mol"])
    fuerzas_amber = np.array(referencia["amber_forces_kcal_mol_A"])

    # 1. Lo que hace producción hoy: parámetros Cl publicados, y NO coincide.
    energia_publicada, fuerzas_publicadas = energia_y_fuerzas(None)
    assert abs(energia_publicada - esperado) == pytest.approx(
        referencia["residual_after_constant_conversion_kcal_mol"], abs=1e-9
    ), "el residual dejó de ser el que el informe declara"

    # 2. Con el respaldo de carbono de Amber aplicado sólo al cloro: coincide.
    radio, *coeficientes = lcpo.LCPO_PARAMETERS[RESPALDO_DE_CARBONO_PARA_CLORO]
    energia, fuerzas = energia_y_fuerzas((
        radio * unit.angstrom, coeficientes[0], coeficientes[1], coeficientes[2],
        coeficientes[3] / unit.angstrom ** 2,
    ))
    assert abs(energia - esperado) < 0.001
    assert float(np.max(np.abs(fuerzas - fuerzas_amber))) < 0.001

    # 3. Y toda la diferencia entre ambas lecturas ES el residual publicado:
    #    no queda un segundo error escondido detrás del cloro.
    assert (energia_publicada - energia) == pytest.approx(
        referencia["residual_after_constant_conversion_kcal_mol"], abs=1e-6
    )
    # La tolerancia de esta última comparación es 1e-4 y no 1e-9 a propósito: se
    # comparan dos lecturas de OpenMM entre sí, y el respaldo de carbono
    # reproduce a Amber con 6.5e-5 kcal/mol/A de diferencia, no con cero. Afirmar
    # igualdad exacta sería afirmar más de lo medido.
    assert float(np.max(np.abs(fuerzas_publicadas - fuerzas))) == pytest.approx(
        referencia["max_force_error_kcal_mol_A"], abs=1e-4
    )


def test_produccion_no_copia_el_respaldo_de_carbono_para_el_cloro():
    """Atribuir la divergencia no autoriza a adoptarla.

    El adaptador conserva los parámetros Cl publicados en el artículo de LCPO.
    OpenMM 8.5.2 lo documenta en su propio código: «Cl is the only element in
    the LCPO paper not implemented in Amber». Que copiar el respaldo de carbono
    diera paridad exacta es una razón MÁS para no hacerlo sin una decisión de
    dominio: elegiría el parámetro por el resultado de la comparación.
    """
    from openmm.app.internal import lcpo

    import services.chemistry.amber_compatibility as adaptador

    fuente = Path(adaptador.__file__).read_text(encoding="utf-8")
    assert RESPALDO_DE_CARBONO_PARA_CLORO not in fuente
    assert "LCPO_PARAMETERS" not in fuente, (
        "el adaptador empezó a manipular la tabla LCPO: si alguien sustituye el "
        "cloro ahí, la comparación con Amber pasaría y el bloqueo científico "
        "desaparecería sin que nadie lo decidiera"
    )
    # La tabla que sí se usa sigue trayendo el cloro publicado.
    assert lcpo.LCPO_PARAMETERS["Cl"] == (
        1.8, 0.98318, -0.40437, 0.00011249, 0.00049901
    )


def test_chlorine_discrepancy_remains_an_explicit_activation_blocker():
    failures = [(case["name"],c) for case in REPORT["results"] for c in case["comparisons"] if not c["passed"]]
    assert len(failures) == 1
    name,comparison = failures[0]
    assert name == "chlorobenzene" and comparison["condition"] == "GBn2_LCPO"
    assert comparison["residual_after_constant_conversion_kcal_mol"] > 0.1
    assert json.loads((ROOT/"manifest.json").read_text())["protocol_status"] == "EXPERIMENTAL_NOT_ENABLED"
