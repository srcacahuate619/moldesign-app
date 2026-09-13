"""Contrato de `pose_physical_validity`: que cuenta como aprobado y que no.

EXISTE POR UN DEFECTO REAL, encontrado el 2026-08-23 al propagar el corrigendum
`MF-33-H-COR`. PoseBusters no senala «no pude evaluar esto» con `None`: varios de sus
modulos devuelven **NaN**. `posebusters/modules/energy_ratio.py` pone `energy_ratio_passes`
a `float("nan")` en su `_empty_results`, y lo devuelve por cuatro caminos: molecula sin
conformero, molecula que no sanitiza, **UFF sin parametros para la molecula** e InChI que no
se puede construir. Un ligando con un metal cae ahi con toda naturalidad.

La deteccion anterior era `v is None`, y `nan is None` es `False`. Resultado: el control de
energia desaparecia de las tres listas -fallidos, de carga, no evaluados- y la pose se
reportaba como **CONTROLES SUPERADOS** con la bateria incompleta. Es exactamente el error
que la frase obligatoria del `docs/53` §6.3 existe para impedir, cometido por el modulo que
la emite.

Estas pruebas no necesitan PoseBusters ni RDKit: fijan el contrato de clasificacion, que es
donde estaba el fallo.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.chemistry.pose_physical_validity import (  # noqa: E402
    CHECKS_DE_CARGA,
    NOMBRE_PROXY,
    clasificar_resultado_pb,
)

NAN = float("nan")


class TestClasificarResultadoPB:
    def test_booleanos_se_clasifican_por_valor(self):
        assert clasificar_resultado_pb(True) == "PASA"
        assert clasificar_resultado_pb(False) == "FALLA"

    @pytest.mark.parametrize("valor", [NAN, None, 0.0, 1.0, "", "True", [], {}])
    def test_lo_que_no_es_booleano_nunca_aprueba(self, valor):
        """Ni siquiera los que son *truthy*: `bool(nan)` es True, y eso era la trampa."""
        assert clasificar_resultado_pb(valor) == "NO_EVALUADO"

    def test_el_nan_de_posebusters_no_se_cuenta_como_superado(self):
        """El caso exacto de `_empty_results`: energy_ratio_passes = nan."""
        assert NAN is not None          # la premisa del defecto anterior
        assert bool(NAN) is True        # y por que `if not v` tampoco habria servido
        assert clasificar_resultado_pb(NAN) == "NO_EVALUADO"

    def test_booleanos_de_numpy_siguen_siendo_booleanos(self):
        """`v is True` fallaba con numpy; la clasificacion por valor no debe romperse."""
        np = pytest.importorskip("numpy")
        assert clasificar_resultado_pb(np.bool_(True)) == "PASA"
        assert clasificar_resultado_pb(np.bool_(False)) == "FALLA"


class TestVeredictoAgregado:
    """La regla de agregacion sobre una fila de PoseBusters, sin ejecutarlo."""

    @staticmethod
    def _veredicto(fila: dict) -> str:
        clasif = {k: clasificar_resultado_pb(v) for k, v in fila.items()}
        fallan_quimica = [k for k, e in clasif.items()
                          if e == "FALLA" and k not in CHECKS_DE_CARGA]
        fallan_carga = [k for k, e in clasif.items()
                        if e == "FALLA" and k in CHECKS_DE_CARGA]
        no_eval = [k for k, e in clasif.items() if e == "NO_EVALUADO"]
        if fallan_quimica:
            return "failed"
        if fallan_carga or no_eval:
            return "review"
        return "passed"

    def test_bateria_completa_y_limpia_aprueba(self):
        assert self._veredicto({"mol_pred_loaded": True, "bond_lengths": True,
                                "internal_energy": True}) == "passed"

    def test_energia_en_nan_degrada_a_revision_y_no_a_aprobado(self):
        """El defecto, en una linea: antes esto devolvia `passed`."""
        fila = {"mol_pred_loaded": True, "bond_lengths": True, "internal_energy": NAN}
        assert self._veredicto(fila) == "review"

    def test_un_fallo_de_quimica_manda_sobre_lo_no_evaluado(self):
        fila = {"mol_pred_loaded": True, "bond_lengths": False, "internal_energy": NAN}
        assert self._veredicto(fila) == "failed"

    def test_fallo_de_carga_no_es_fallo_de_la_pose(self):
        fila = {"mol_cond_loaded": False, "bond_lengths": True, "internal_energy": True}
        assert self._veredicto(fila) == "review"


def test_el_proxy_no_se_llama_internal_energy():
    """Regresion de nombre: `internal_energy` es de PoseBusters, no del proxy RDKit.

    Llamarlo asi hacia pasar por oficial una cantidad que usa otro campo de fuerza, otro
    numero de conformeros y otra razon.
    """
    assert NOMBRE_PROXY != "internal_energy"
    assert "proxy" in NOMBRE_PROXY


def test_el_fallback_nunca_emite_falla():
    """Regla de producto disparada por `PROD-PV-H-01`, y esta medida, no supuesta.

    El proxy discrepa del control oficial en 33 de 232 poses, y las 33 en la misma
    direccion: proxy FALLA donde el oficial PASA. Son falsos rechazos. Un escalon degradado
    que rechaza el 14.2% de las poses buenas no puede emitir un veredicto de FALLA.
    """
    import inspect

    from services.chemistry import pose_physical_validity as mod

    fuente = inspect.getsource(mod.evaluar_pose_fisica)
    escalon2 = fuente[fuente.index("Escalon 2"):]
    assert '"status": "review"' in escalon2
    assert '"failed"' not in escalon2, "el escalon degradado no puede devolver `failed`"
    assert '"checks_que_fallan": []' in escalon2
