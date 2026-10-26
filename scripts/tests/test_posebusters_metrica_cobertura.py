"""SCI-B-016: `pb_valid_fisica` no aprueba una batería que no corrió entera.

La auditoría simuló tres respuestas de PoseBusters que la envoltura daba por
válidas: cero checks físicos, carga fallida y checks requeridos en NaN. Aquí se
usan esas tres más sus controles (un fallo físico y un fallo sólo de RMSD).

`posebusters_metrica.py` es código productor sellado (nueve manifiestos guardan su
hash), así que no se corrige en sitio: la regla nueva vive en
`posebusters_veredicto.py`, y un guardián impide que un experimento nuevo vuelva a
importar el módulo viejo.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import posebusters_metrica as viejo
import posebusters_veredicto as pm

CARGA_OK = {"mol_pred_loaded": True, "mol_true_loaded": True, "mol_cond_loaded": True}
FISICOS_OK = {"bond_lengths": True, "internal_steric_clash": True,
              "minimum_distance_to_protein": True, "internal_energy": True}
IMPORTA_EL_VIEJO = re.compile(r"^\s*(?:import|from)\s+posebusters_metrica\b", re.M)


def _fila(**extra):
    return {**CARGA_OK, **FISICOS_OK, "rmsd_≤_2å": True, **extra}


def _simular(monkeypatch, fila):
    pd = pytest.importorskip("pandas")

    class _Simulado:
        def bust(self, *_a, **_k):
            return pd.DataFrame([fila])

    monkeypatch.setattr(viejo, "disponible", lambda: True)
    monkeypatch.setattr(viejo, "_buster", lambda config="redock": _Simulado())


def test_bateria_completa_y_en_verde_es_valida():
    assert pm.veredicto_de_la_fila(_fila())["pb_valid_fisica"] is True


def test_sin_ningun_check_fisico_no_es_valida():
    r = pm.veredicto_de_la_fila({**CARGA_OK, "rmsd_≤_2å": True})
    assert r["pb_valid_fisica"] is None and r["motivo"] == "sin_checks_fisicos"


@pytest.mark.parametrize("carga", ["mol_pred_loaded", "mol_cond_loaded"])
def test_una_carga_fallida_no_es_valida(carga):
    r = pm.veredicto_de_la_fila(_fila(**{carga: False}))
    assert r["pb_valid_fisica"] is None and r["motivo"].startswith("carga_fallida")


@pytest.mark.parametrize("vacio", [float("nan"), None])
def test_un_check_fisico_sin_evaluar_deja_la_bateria_incompleta(vacio):
    r = pm.veredicto_de_la_fila(_fila(minimum_distance_to_protein=vacio))
    assert r["pb_valid_fisica"] is None and r["motivo"] == "bateria_incompleta"
    assert r["checks_sin_evaluar"] == ["minimum_distance_to_protein"]


def test_un_fallo_medido_sigue_siendo_un_fallo_aunque_falte_otro():
    r = pm.veredicto_de_la_fila(_fila(bond_lengths=False, internal_energy=float("nan")))
    assert r["pb_valid_fisica"] is False and r["checks_que_fallan"] == ["bond_lengths"]


def test_un_fallo_solo_de_rmsd_no_toca_la_validez_fisica():
    r = pm.veredicto_de_la_fila(_fila(**{"rmsd_≤_2å": False}))
    assert r["pb_valid_fisica"] is True and r["pb_rmsd_ok"] is False


def test_los_booleanos_de_numpy_cuentan_como_evaluados():
    np = pytest.importorskip("numpy")
    r = pm.veredicto_de_la_fila(_fila(bond_lengths=np.bool_(True)))
    assert r["pb_valid_fisica"] is True


def test_evaluar_pose_usa_la_misma_regla(monkeypatch):
    """Por la función pública, con una respuesta simulada de PoseBusters."""
    _simular(monkeypatch, _fila(minimum_distance_to_protein=math.nan))
    r = pm.evaluar_pose(object(), object(), "proteina.pdb")
    assert r["pb_valid_fisica"] is None and r["motivo"] == "bateria_incompleta"


@pytest.mark.parametrize("fila", [
    {**CARGA_OK, "rmsd_≤_2å": True},                                  # cero checks físicos
    {**CARGA_OK, "mol_cond_loaded": False, "bond_lengths": True},     # carga fallida
    {**CARGA_OK, "bond_lengths": True, "minimum_distance_to_protein": math.nan},
])
def test_el_modulo_sellado_conserva_su_defecto_y_por_eso_no_se_usa(monkeypatch, fila):
    """El viejo sigue dando True en los tres casos de la auditoría; el nuevo, None."""
    _simular(monkeypatch, fila)
    assert viejo.evaluar_pose(object(), object(), "p.pdb")["pb_valid_fisica"] is True
    assert pm.evaluar_pose(object(), object(), "p.pdb")["pb_valid_fisica"] is None


def test_solo_los_productores_ya_sellados_importan_el_modulo_viejo():
    """Un experimento nuevo no puede volver a medir con la regla que aprueba lo no medido."""
    raiz = Path(__file__).resolve().parents[2]
    manifiestos = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                            for p in (raiz / "scripts" / "artifacts_science").glob("*/manifest.json"))
    nuevos = []
    for script in sorted((raiz / "scripts").glob("*.py")):
        if script.name in {"posebusters_metrica.py", "posebusters_veredicto.py"}:
            continue
        if IMPORTA_EL_VIEJO.search(script.read_text(encoding="utf-8", errors="replace")) \
                and f"scripts/{script.name}" not in manifiestos:
            nuevos.append(script.name)
    assert nuevos == [], f"usan la regla vieja sin estar sellados: {nuevos}"


def test_el_guardian_ve_un_importador_nuevo():
    assert IMPORTA_EL_VIEJO.search("import os\nfrom posebusters_metrica import evaluar_pose\n")
    assert IMPORTA_EL_VIEJO.search("    import posebusters_metrica as pm\n")
    assert not IMPORTA_EL_VIEJO.search("import posebusters_veredicto\n")
    assert not IMPORTA_EL_VIEJO.search("import posebusters_metrica_v2\n")
