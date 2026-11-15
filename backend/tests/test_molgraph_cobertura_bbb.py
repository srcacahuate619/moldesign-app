"""El porcentaje de BBB de MolGraph cuenta las moléculas CON veredicto y declara la cobertura (auditoría 1.0.4, S2-4).

`query_admet_correlation` dividía los positivos entre TODAS las filas del grupo de logP, así que una abstención del
consenso (`blood_bbb_permeable = None`) contaba como un «no permeable». Con la capa 2b como conflicto, el consenso se
abstiene en casos reales, y el porcentaje describía otra cosa que lo que decía.
"""

from __future__ import annotations

import uuid

import pytest

from services import molgraph

ALICE = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def grafo_aislado(tmp_path, monkeypatch):
    monkeypatch.setattr(molgraph, "_PUBLIC_DB", tmp_path / "molgraph.db")
    monkeypatch.setattr(molgraph, "_PRIVATE_DB", tmp_path / "molgraph_private.db")
    monkeypatch.setattr(molgraph, "_SEED_DB", tmp_path / "molgraph_seed.db")
    molgraph.invalidar_cache_de_huellas()
    molgraph.init_graph()
    yield
    molgraph.invalidar_cache_de_huellas()


def _agregar(smiles: str, logp: float, bbb) -> None:
    molgraph.add_molecule_node(
        smiles, {"log_p": logp, "blood_bbb_permeable": bbb, "blood_hia_permeable": True, "molecular_weight": 200.0},
        user_id=ALICE,
    )


def test_un_nulo_no_cuenta_como_no_permeable():
    # grupo de logP alto (>= 3.5): 1 positivo, 1 negativo, 2 abstenciones
    _agregar("CCCCCCCC", 4.0, True)
    _agregar("CCCCCCCCC", 4.1, False)
    _agregar("CCCCCCCCCC", 4.2, None)
    _agregar("CCCCCCCCCCC", 4.3, None)

    grupo = molgraph.query_admet_correlation(user_id=ALICE)["high_logp"]

    assert grupo["count"] == 4
    assert grupo["bbb_con_veredicto"] == 2
    assert grupo["bbb_sin_veredicto"] == 2
    assert grupo["bbb_permeable_pct"] == 50.0, "1 de las 2 con veredicto, no 1 de las 4"


def test_sin_ningun_veredicto_no_hay_porcentaje_ni_un_cero():
    _agregar("CCCCCCCC", 4.0, None)
    _agregar("CCCCCCCCC", 4.1, None)

    grupo = molgraph.query_admet_correlation(user_id=ALICE)["high_logp"]

    assert grupo["bbb_con_veredicto"] == 0
    assert grupo["bbb_sin_veredicto"] == 2
    assert grupo["bbb_permeable_pct"] is None, "un 0 afirmaría «ninguna permeable»; no hay veredicto"


def test_con_todos_los_veredictos_el_porcentaje_no_cambia():
    _agregar("CCCCCCCC", 4.0, True)
    _agregar("CCCCCCCCC", 4.1, True)
    _agregar("CCCCCCCCCC", 4.2, False)

    grupo = molgraph.query_admet_correlation(user_id=ALICE)["high_logp"]

    assert grupo["bbb_con_veredicto"] == 3
    assert grupo["bbb_sin_veredicto"] == 0
    assert grupo["bbb_permeable_pct"] == pytest.approx(66.7)
