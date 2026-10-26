"""CAL-D-01 R4: la ρ de peor caso (DP exacta) coincide con la enumeración de las 2^m asignaciones.

Es el requisito 1 del registro previo: se valida contra la enumeración completa, con empates de Ki y de Q,
copias de bootstrap y valores a ambos lados del umbral F, antes de ver un solo score real.
"""
import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "cal_d01r4"))
import rho_peor as rp  # noqa: E402


def _caso(rng, m, ties_ki, ties_q, cerca_umbral):
    base = [round(rng.uniform(1, 40), 1) for _ in range(m)]
    if ties_ki:
        base = [rng.choice(base[: max(2, m // 2)]) if rng.random() < 0.4 else v for v in base]
    if cerca_umbral:
        # pares a ambos lados de Ki·F, sin llegar a la igualdad exacta
        k = rng.choice(base)
        base[rng.randrange(m)] = round(k * 1.4438, 4)
        base[rng.randrange(m)] = round(k * 1.4439, 4)
        base[rng.randrange(m)] = round(k * 1.4437, 4)
    q = [round(rng.uniform(5, 10), 1 if ties_q else 3) for _ in range(m)]
    return base, q


def _igual(ki, q, copias=None):
    panel = rp.Panel(ki)
    dp = rp.rho_peor(panel, q, copias)
    fb, b = rp.rho_peor_fuerza_bruta(ki, q, copias)
    if math.isnan(fb):
        assert math.isnan(dp)
        return
    assert abs(dp - fb) < 1e-10, (ki, q, copias, dp, fb)
    # la asignación recuperada alcanza el mínimo
    asign, objetivo = rp.asignacion_peor(panel, q, copias)
    assert abs(rp.rho_asignacion(ki, q, asign, copias) - fb) < 1e-10


@pytest.mark.parametrize("semilla", range(40))
def test_dp_igual_a_la_enumeracion_sin_copias(semilla):
    rng = random.Random(semilla)
    m = rng.randint(3, 11)
    ki, q = _caso(rng, m, ties_ki=semilla % 2 == 0, ties_q=semilla % 3 == 0, cerca_umbral=semilla % 4 == 0)
    try:
        rp.Panel(ki)
    except ValueError:
        pytest.skip("par exactamente en el umbral")
    _igual(ki, q)


@pytest.mark.parametrize("semilla", range(40))
def test_dp_igual_a_la_enumeracion_con_copias_de_bootstrap(semilla):
    rng = random.Random(1000 + semilla)
    m = rng.randint(3, 9)
    ki, q = _caso(rng, m, ties_ki=True, ties_q=semilla % 2 == 0, cerca_umbral=semilla % 3 == 0)
    copias = [rng.choice([0, 1, 1, 2, 3]) for _ in range(m)]
    if sum(1 for c in copias if c) < 3:
        copias[:3] = [1, 2, 1]
    try:
        rp.Panel(ki)
    except ValueError:
        pytest.skip("par exactamente en el umbral")
    # la enumeración sólo sobre los presentes (un padre ausente no tiene b que importe)
    _igual(ki, q, copias)


def test_casos_conocidos_del_umbral():
    # 1 y 1,4438: interactúan; 1 y 1,4439 no (F = 1,443812…)
    assert rp.Panel([1, 1.4438]).inter[0, 1] and not rp.Panel([1, 1.4439]).inter[0, 1]
    # con Q ordenado como la potencia, la peor asignación puede bajar ρ y nunca la sube
    ki = [1, 1.2, 1.4, 2.0, 3.0]
    q = [9.0, 8.5, 8.4, 7.0, 6.0]
    peor = rp.rho_peor(rp.Panel(ki), q)
    sin_desplazar = rp.rho_asignacion(ki, q, [0] * 5)
    assert peor <= sin_desplazar + 1e-12 and sin_desplazar == pytest.approx(1.0)
    assert -1 <= peor <= 1


def test_umbral_exacto_se_rechaza():
    with pytest.raises(ValueError):
        rp.Panel([703, 1015])        # Ki_j = Ki_i·F exacto


def test_q_constante_no_tiene_rho():
    assert math.isnan(rp.rho_peor(rp.Panel([1, 2, 3, 4]), [5.0, 5.0, 5.0, 5.0]))


def test_bootstrap_reproducible_y_pareado():
    rng = random.Random(7)
    ki = [round(rng.uniform(1, 30), 1) for _ in range(14)]
    q = [round(rng.uniform(5, 10), 3) for _ in range(14)]
    a = rp.bootstrap(ki, q, n_rep=40)
    b = rp.bootstrap(ki, q, n_rep=40)
    assert a == b
    assert a["rho_peor"][0] <= a["rho"][0] + 1e-9 or a["rho_peor"][1] <= a["rho"][1] + 1e-9


def test_concordancia_solo_cuenta_pares_por_encima_de_f():
    ki = [1, 1.4, 2.1]                       # 1 vs 1,4: dentro de F -> no comparable; 1 vs 2: comparable
    comp = rp.pares_comparables(ki)
    assert comp[0, 2] and comp[1, 2] and not comp[0, 1]
    assert rp.concordancia(comp, [9.0, 8.0, 7.0]) == 1.0
    assert rp.concordancia(comp, [7.0, 8.0, 9.0]) == 0.0
