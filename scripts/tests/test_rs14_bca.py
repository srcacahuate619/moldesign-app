"""SCI-B-025: el «ci95_bca» sellado de RS-14 es el percentil; el BCa de verdad no cambia el gate."""
import numpy as np
import pytest

import analisis_rs14_bca as a


def test_con_muestra_simetrica_bca_y_percentil_casi_coinciden():
    # control: sin sesgo ni asimetría, z0 y a ~ 0 y el BCa se reduce al percentil
    dif = np.array([-1.0, 1.0] * 50)
    lo, hi, boot = a.percentil_como_el_runner(dif)
    blo, bhi, _, acel = a.bca(dif, boot)
    assert acel == pytest.approx(0.0, abs=1e-12)
    assert (blo, bhi) == pytest.approx((lo, hi), abs=0.02)


def test_con_muestra_sesgada_el_bca_se_desplaza():
    # control negativo: con una cola larga el BCa no puede ser el percentil
    dif = np.array([0.0] * 90 + [5.0] * 10)
    lo, hi, boot = a.percentil_como_el_runner(dif)
    blo, bhi, _, _ = a.bca(dif, boot)
    assert (blo, bhi) != pytest.approx((lo, hi), abs=1e-3)


def test_lo_sellado_es_el_percentil_y_el_gate_no_cambia():
    r = a.analizar()
    for exp in ("RS-14", "RS-14-R1"):
        assert r[exp]["percentil_recalculado"] == r[exp]["sellado_ci95_bca"]
        assert r[exp]["bca"] != r[exp]["sellado_ci95_bca"]
        assert not r[exp]["bca_excluye_cero"]
    assert r["RS-14"]["bca"] == [-0.1594, 0.0543]
