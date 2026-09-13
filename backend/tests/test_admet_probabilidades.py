"""
Las cabezas de clasificación de ADMET-AI devuelven PROBABILIDADES.

El defecto que estas pruebas fijan se veía a simple vista con una molécula que
todo el mundo conoce. Con aspirina, el modelo empaquetado devuelve:

    BBB_Martins  0.658      HIA_Hou  0.960      hERG  0.021

y el código convertía cada una con `int()`, que trunca. `int(0.96)` es 0. Como
ninguna probabilidad llega a 1.0 exacto, TODAS las banderas de clasificación
valían 0 para toda molécula: BBB siempre «no permeable», HIA siempre «baja»,
hERG nunca, y ninguna alerta de CYP jamás.

La prueba no comprueba «que dé 1»: comprueba que la frontera esté en 0.5 y que
un 0.96 no se convierta en un 0, que es la forma que tenía el error.
"""

import pytest

from chem import blood_viability


class _ModeloFalso:
    """Devuelve exactamente lo que devuelve ADMET-AI: un dict de floats."""

    def __init__(self, salida: dict[str, float]):
        self._salida = salida

    def predict(self, smiles: str) -> dict[str, float]:  # noqa: ARG002
        return dict(self._salida)


@pytest.fixture(autouse=True)
def _cache_limpia():
    blood_viability._admet_cache.clear()
    yield
    blood_viability._admet_cache.clear()


def _predecir(monkeypatch, salida: dict[str, float]) -> dict:
    monkeypatch.setattr(blood_viability, "get_admet_model", lambda: _ModeloFalso(salida))
    return blood_viability.predict_admet_ai("CC(=O)Oc1ccccc1C(=O)O")


SALIDA_ASPIRINA = {
    "Solubility_AqSolDB": -1.624,
    "PPBR_AZ": 63.297,
    "BBB_Martins": 0.658,
    "HIA_Hou": 0.960,
    "hERG": 0.021,
    "Clearance_Hepatocyte_AZ": 12.0,
    "CYP3A4_Veith": 0.11,
    "CYP2D6_Veith": 0.07,
    "CYP2C9_Veith": 0.83,
    "CYP3A4_Substrate_CarbonMangels": 0.44,
    "CYP2D6_Substrate_CarbonMangels": 0.12,
    "CYP2C9_Substrate_CarbonMangels": 0.61,
}


def test_una_probabilidad_alta_no_se_trunca_a_cero(monkeypatch):
    """`int(0.96)` era 0. Ese es, literalmente, todo el defecto."""
    preds = _predecir(monkeypatch, SALIDA_ASPIRINA)
    assert preds["HIA"] == 1, "HIA_Hou=0.960 tiene que ser la clase positiva"
    assert preds["BBB"] == 1, "BBB_Martins=0.658 tiene que ser la clase positiva"


def test_una_probabilidad_baja_sigue_siendo_la_clase_negativa(monkeypatch):
    preds = _predecir(monkeypatch, SALIDA_ASPIRINA)
    assert preds["hERG"] == 0
    assert preds["CYP3A4_Inh"] == 0
    assert preds["CYP2D6_Inh"] == 0


def test_las_alertas_de_cyp_pueden_dispararse(monkeypatch):
    """Antes NINGUNA se disparaba nunca, con ninguna molécula."""
    preds = _predecir(monkeypatch, SALIDA_ASPIRINA)
    assert preds["CYP2C9_Inh"] == 1, "0.83 es inhibición predicha"
    assert preds["CYP2C9_Sub"] == 1, "0.61 es sustrato predicho"


@pytest.mark.parametrize(
    ("probabilidad", "clase"),
    [(0.0, 0), (0.49, 0), (0.4999, 0), (0.5, 1), (0.51, 1), (1.0, 1)],
)
def test_la_frontera_esta_en_cero_coma_cinco(monkeypatch, probabilidad, clase):
    salida = dict(SALIDA_ASPIRINA, BBB_Martins=probabilidad)
    assert _predecir(monkeypatch, salida)["BBB"] == clase


def test_los_valores_continuos_no_se_binarizan(monkeypatch):
    """Solubilidad, PPB y aclaramiento son magnitudes, no clases."""
    preds = _predecir(monkeypatch, SALIDA_ASPIRINA)
    assert preds["Solubility"] == pytest.approx(-1.624)
    assert preds["PPB"] == pytest.approx(63.297)
    assert preds["Clearance"] == pytest.approx(12.0)


def test_sin_modelo_no_se_fabrica_nada(monkeypatch):
    """La ausencia se declara con None; nunca con un valor por defecto plausible."""
    monkeypatch.setattr(blood_viability, "get_admet_model", lambda: None)
    preds = blood_viability.predict_admet_ai("CCO")
    assert set(preds.values()) == {None}
