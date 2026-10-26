"""ABS-TR-01-VALIDEZ: el análisis decide con la regla del registro previo y los intervalos son los exactos.

`scripts/abs_tr_01/abs_tr_01.py` es el arnés del experimento sellado. Estas pruebas fijan lo que su análisis
afirma: el límite unilateral de Clopper-Pearson (contra una forma cerrada que no usa scipy), la decisión del
producto a partir de la auditoría de Preparación, y el cruce con la referencia de los revisores. No ejecutan
el producto.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "abs_tr_01"))
import abs_tr_01 as abs_  # noqa: E402


def _superior_cero_errores(n: int, alfa: float = 0.05) -> float:
    """Con 0 errores en n, el límite superior unilateral es 1 − α^(1/n) (forma cerrada)."""
    return 1 - alfa ** (1 / n)


@pytest.mark.parametrize("n", [7, 10, 16, 18, 29])
def test_el_limite_superior_con_cero_errores_es_la_forma_cerrada(n):
    inferior, superior = abs_._cp(0, n)
    assert inferior == 0.0
    assert superior == pytest.approx(_superior_cero_errores(n), abs=1e-9)


def test_con_18_negativos_el_limite_superior_no_baja_del_15_por_ciento():
    """Lo que el registro previo dice de antemano: con 18 negativos GO es inalcanzable."""
    assert abs_._cp(0, 18)[1] == pytest.approx(0.1534, abs=5e-4)
    assert abs_._cp(0, 18)[1] > abs_.OBJETIVO_FB


def test_el_resultado_publicado_3_de_18():
    inferior, superior = abs_._cp(3, 18)
    assert inferior == pytest.approx(0.047, abs=1e-3)
    assert superior == pytest.approx(0.377, abs=1e-3)


def test_todos_errores_y_el_intervalo_cubre_la_proporcion():
    assert abs_._cp(18, 18)[1] == 1.0
    for k in range(1, 18):
        inferior, superior = abs_._cp(k, 18)
        assert inferior < k / 18 < superior


def _audit(estado: str, solo_rutinaria: bool = False) -> dict:
    return {"preparacion": {"estado": estado, "solo_rutinaria": solo_rutinaria}}


def test_un_bloqueo_o_una_parada_del_preflight_es_detener():
    assert abs_.decision_del_producto(_audit("BLOQUEADO")) == "DETENER"
    assert abs_.decision_del_producto({"detenido_en": "preflight"}) == "DETENER"


def test_solo_las_revisiones_rutinarias_dejan_seguir():
    assert abs_.decision_del_producto(_audit("REVISION", solo_rutinaria=True)) == "SEGUIR"
    assert abs_.decision_del_producto(_audit("TRANSFERIBLE")) == "SEGUIR"
    assert abs_.decision_del_producto(_audit("REVISION", solo_rutinaria=False)) == "AVISAR"


def _fila(pdb: str, referencia: str, producto: str) -> dict:
    return {"pdb": pdb, "ref": referencia, "producto": producto}


def test_el_cruce_cuenta_cada_error_con_su_denominador():
    filas = ([_fila(f"N{i}", "NO_DETENER", "AVISAR") for i in range(15)]
             + [_fila(f"F{i}", "NO_DETENER", "DETENER") for i in range(3)]
             + [_fila(f"D{i}", "DETENER", "DETENER") for i in range(6)]
             + [_fila(f"A{i}", "DETENER", "AVISAR") for i in range(4)])
    c = abs_._cruce(filas, "ref")
    assert (c["falso_bloqueo"]["k"], c["falso_bloqueo"]["n"]) == (3, 18)
    assert (c["falsa_autorizacion"]["k"], c["falsa_autorizacion"]["n"]) == (0, 10)
    assert (c["aviso_sin_bloqueo"]["k"], c["bloqueo_correcto"]["k"]) == (4, 6)
    assert c["falsos_bloqueos"] == ["F0", "F1", "F2"]


def test_un_sistema_disputado_no_entra_en_ningun_denominador():
    filas = [_fila("X", "DISPUTADO", "DETENER"), _fila("Y", "NO_DETENER", "AVISAR"), _fila("Z", "DETENER", "SEGUIR")]
    c = abs_._cruce(filas, "ref")
    assert (c["falso_bloqueo"]["k"], c["falso_bloqueo"]["n"]) == (0, 1)
    assert (c["falsa_autorizacion"]["k"], c["falsa_autorizacion"]["n"]) == (1, 1)
    assert c["falsas_autorizaciones"] == ["Z"]


def test_la_correspondencia_de_controles_cubre_los_diez_y_sus_claves_existen():
    assert list(abs_.CORRESPONDENCIA) == abs_.CONTROLES
    texto =(Path(__file__).resolve().parents[2] / "backend" / "services" / "dossier" / "preparacion.py").read_text(encoding="utf-8")
    for control, claves in abs_.CORRESPONDENCIA.items():
        for clave in claves:
            assert f'"{clave}"' in texto, (control, clave)


def test_la_potencia_para_no_go_y_go_es_la_del_registro():
    assert math.isclose(abs_.OBJETIVO_FB, 0.10)
    assert abs_.MAX_FALLOS == 3
