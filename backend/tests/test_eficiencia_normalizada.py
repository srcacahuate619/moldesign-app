"""Los coeficientes de Reynolds, atados a la tabla 3 del artículo.

Auditoría del 2026-09-04, caso «molécula pequeña», segunda parte. La primera
corrección dejó de emitir el veredicto de eficiencia de ligando donde el umbral
no discrimina, y citó las métricas normalizadas por tamaño como el siguiente
paso sin implementarlas: no había certeza sobre los coeficientes, y meter
constantes a medio recordar en un producto científico es peor que abstenerse.

Con los coeficientes verificados contra la fuente, `scoring/eficiencia.py`
implementa las dos. Estas pruebas son lo que impide que un cambio accidental de
signo o de dígito pase inadvertido: un error en el término cúbico no rompe
nada, sólo devuelve otro número.

═══════════════════════════════════════════════════════════════════════════
LO QUE SE MIDIÓ ANTES DE IMPLEMENTARLAS
═══════════════════════════════════════════════════════════════════════════

Sobre la cohorte de acoplamiento de este proyecto —8 dianas, 17 431 moléculas
con score de Vina y SMILES parseable, en `data/gnn_v31/checkpoints/`—
correlación de Spearman de cada métrica contra el número de átomos pesados,
promediada en valor absoluto por diana:

    métrica                 |rho| medio   peor diana   mejor diana
    |Vina| crudo               0.817        0.880        0.696
    LE = |Vina| / HA           0.824        0.949        0.594
    SILE (HA^0.3)              0.370        0.642        0.174
    FQ (Reynolds, proxy)       0.216        0.398        0.015

El resultado que justifica todo esto: **LE no reduce la dependencia con el
tamaño. La empeora ligeramente respecto del score crudo** (0.824 frente a
0.817). Lo único que hace es invertir el signo — el score crudo premia el
tamaño, LE lo castiga— con la misma magnitud. La métrica que el producto usaba
como normalizador no normalizaba nada.

FQ la reduce a 0.216, unas 3.8 veces menos que LE. SILE queda en medio.

Ninguna entra en `total_score`: son informativas y auditables, no veredictos.
"""

from __future__ import annotations

import math

import pytest

from scoring.eficiencia import (
    KCAL_POR_UNIDAD_LOG,
    REYNOLDS_A0,
    REYNOLDS_A1,
    REYNOLDS_A2,
    REYNOLDS_A3,
    REYNOLDS_HA_MAX,
    REYNOLDS_HA_MIN,
    SILE_EXPONENTE,
    calcular,
    le_scale_pki,
)

# Tabla 3 de Reynolds, Tounge, Bembenek, J. Med. Chem. 51 (2008) 2432.
# (átomos pesados, LE_scale en pKi, LE_scale en kcal/mol)
TABLA_3 = [
    (20, 0.4672, 0.6391),
    (30, 0.3378, 0.4621),
    (40, 0.2702, 0.3696),
    (50, 0.2295, 0.3140),
]


@pytest.mark.parametrize("ha,esperado_pki,_kcal", TABLA_3, ids=[f"HA{r[0]}" for r in TABLA_3])
def test_la_escala_reproduce_la_tabla_publicada(ha: int, esperado_pki: float, _kcal: float):
    """La comprobación que hace confiable a las otras: los cuatro coeficientes."""
    escala, sujetado, _ = le_scale_pki(ha)
    assert sujetado is False, f"HA={ha} está dentro del rango del ajuste"
    assert escala == pytest.approx(esperado_pki, abs=5e-5), (
        f"LE_scale({ha}) = {escala:.6f} y la tabla 3 dice {esperado_pki}. "
        "Revisa los coeficientes antes que esta prueba."
    )


def test_el_termino_cubico_es_negativo():
    """El error más fácil de cometer y el más difícil de ver.

    Con el signo cambiado, LE_scale(20) daría 0.5576 en vez de 0.4672: un 19 %
    más alto, un número perfectamente plausible, y todos los FQ del producto
    saldrían bajos sin que nada fallara.
    """
    assert REYNOLDS_A3 < 0, "el término en 1/HA³ es negativo en el artículo"

    con_signo_invertido = (
        REYNOLDS_A0 + REYNOLDS_A1 / 20 + REYNOLDS_A2 / 400 - REYNOLDS_A3 / 8000
    )
    assert not math.isclose(con_signo_invertido, 0.4672, abs_tol=5e-5), (
        "la prueba de la tabla 3 no distinguiría el signo: revísala"
    )


def test_los_cuatro_coeficientes_son_los_publicados():
    """Anclados uno a uno: la tabla 3 sola no fija cada dígito."""
    assert REYNOLDS_A0 == 0.0715
    assert REYNOLDS_A1 == 7.5328
    assert REYNOLDS_A2 == 25.7079
    assert REYNOLDS_A3 == -361.4722


def test_la_columna_en_kcal_es_coherente_con_la_conversion():
    """Y deja escrito el 0.15 % de diferencia con el 1.37 convencional."""
    factores = []
    for ha, pki, kcal in TABLA_3:
        escala, _, _ = le_scale_pki(ha)
        factores.append(kcal / escala)

    implicito = sum(factores) / len(factores)
    assert implicito == pytest.approx(1.3679, abs=5e-4), (
        f"el factor implícito en la tabla 3 salió {implicito:.5f}"
    )
    # No son el mismo número, y la diferencia se documenta en el módulo.
    assert abs(KCAL_POR_UNIDAD_LOG - implicito) / implicito < 0.002


# ── El rango de validez del ajuste ───────────────────────────────────────

def test_por_debajo_de_15_atomos_la_escala_se_sujeta():
    """Reynolds ajustó sobre 10-50 y recomienda LE_scale(15) por debajo."""
    escala_15, _, _ = le_scale_pki(REYNOLDS_HA_MIN)
    for ha in (5, 7, 10, 14):
        escala, sujetado, ha_usado = le_scale_pki(ha)
        assert sujetado is True
        assert ha_usado == REYNOLDS_HA_MIN
        assert escala == pytest.approx(escala_15)


def test_por_encima_de_50_atomos_la_escala_se_sujeta():
    escala_50, _, _ = le_scale_pki(REYNOLDS_HA_MAX)
    for ha in (51, 64, 80):
        escala, sujetado, ha_usado = le_scale_pki(ha)
        assert sujetado is True
        assert ha_usado == REYNOLDS_HA_MAX
        assert escala == pytest.approx(escala_50)


def _polinomio_sin_sujetar(ha: int) -> float:
    return REYNOLDS_A0 + REYNOLDS_A1 / ha + REYNOLDS_A2 / ha**2 + REYNOLDS_A3 / ha**3


def test_extrapolar_el_polinomio_seria_absurdo_y_por_eso_se_sujeta():
    """Las dos razones mecánicas del límite inferior, medidas.

    Extrapolado por debajo del rango del ajuste, el polinomio hace dos cosas
    que lo inutilizan, y son distintas:

        HA    polinomio
         3      −7.9490     <- negativo
         4      −2.0866     <- negativo
         5      −0.2854     <- negativo
         6       0.3676
         8       0.7088
        10       0.7204     <- máximo: a partir de aquí ya no crece
        12       0.6686
        15       0.5808     <- extremo del ajuste

    1. **Por debajo de 6 átomos la escala sale negativa.** Dividir por ella
       daría un FQ con el signo cambiado. `chem/regimenes.py` admite moléculas
       desde 5 átomos pesados, así que este caso llega de verdad.
    2. **Entre 6 y 14 no es monótona**: tiene un máximo en 10 y baja hacia los
       extremos. Deja de ser una envolvente que decrece con el tamaño, que es
       lo único que la hace interpretable.
    """
    for ha in (3, 4, 5):
        assert _polinomio_sin_sujetar(ha) < 0, (
            f"a {ha} átomos el polinomio ya no da una escala negativa: la "
            "primera razón para sujetar habría desaparecido, revisa el ajuste"
        )

    assert _polinomio_sin_sujetar(10) > _polinomio_sin_sujetar(8), (
        "el polinomio dejó de ser no monótono por debajo del rango del ajuste"
    )
    assert _polinomio_sin_sujetar(10) > _polinomio_sin_sujetar(12)

    # Y lo que importa: sujetado, todo eso desaparece.
    for ha in (3, 5, 6, 10, 14):
        escala, sujetado, _ = le_scale_pki(ha)
        assert sujetado is True and escala > 0


def test_la_escala_decrece_con_el_tamano_dentro_del_rango():
    valores = [le_scale_pki(ha)[0] for ha in range(REYNOLDS_HA_MIN, REYNOLDS_HA_MAX + 1)]
    assert all(a > b for a, b in zip(valores, valores[1:])), (
        "LE_scale tiene que ser monótona decreciente: es la envolvente de "
        "eficiencia máxima, y las moléculas grandes alcanzan menos por átomo"
    )


# ── SILE ─────────────────────────────────────────────────────────────────

def test_el_exponente_de_sile_es_el_publicado():
    assert SILE_EXPONENTE == 0.3, "Nissink, J. Chem. Inf. Model. 49 (2009) 1617"


def test_sile_se_calcula_como_lo_define_nissink():
    metricas = calcular(-9.0, 30)
    assert metricas is not None
    assert metricas.sile_vina == pytest.approx(9.0 / 30**0.3, abs=1e-4)


def test_sile_no_trae_umbral():
    """Nissink no publica uno; inventarlo sería volver al defecto anterior."""
    import scoring.eficiencia as modulo

    sospechosos = [
        n for n in dir(modulo)
        if "SILE" in n.upper() and any(p in n.upper() for p in ("MIN", "MAX", "UMBRAL", "ALTA", "BAJA"))
    ]
    assert not sospechosos, f"apareció un umbral de SILE inventado: {sospechosos}"


# ── El proxy, y que se llame proxy ───────────────────────────────────────

def test_el_nombre_declara_que_es_un_proxy():
    """Reynolds ajustó contra Ki experimental, no contra scores de Vina."""
    metricas = calcular(-9.0, 30)
    assert hasattr(metricas, "fq_vina_proxy")
    assert not hasattr(metricas, "fit_quality"), (
        "el campo no puede llamarse `fit_quality` a secas: la escala está "
        "ajustada contra afinidades experimentales y aquí se evalúa sobre un "
        "proxy de pKi derivado de Vina"
    )


def test_las_dos_formulaciones_del_proxy_coinciden():
    """Algebraicamente equivalentes; se comprueba que la implementada lo es."""
    vina, ha = -9.5, 34
    metricas = calcular(vina, ha)
    escala_pki, _, _ = le_scale_pki(ha)

    # Vía pKi
    le_pki = (abs(vina) / KCAL_POR_UNIDAD_LOG) / ha
    fq_a = le_pki / escala_pki
    # Vía kcal, escalando la escala
    le_kcal = abs(vina) / ha
    fq_b = le_kcal / (KCAL_POR_UNIDAD_LOG * escala_pki)

    assert fq_a == pytest.approx(fq_b)
    assert metricas.fq_vina_proxy == pytest.approx(fq_a, abs=1e-4)


def test_la_procedencia_viaja_con_los_numeros():
    """Un FQ suelto en un dossier no dice en qué unidades está."""
    metricas = calcular(-9.0, 30)
    procedencia = metricas.procedencia
    assert "Reynolds" in procedencia["fq_vina_proxy"]
    assert "Nissink" in procedencia["sile_vina"]
    assert "Hopkins" in procedencia["ligand_efficiency_vina"]
    assert "PROXY" in procedencia["fq_vina_proxy"]
    assert "sin transformar" in procedencia["afinidad"], (
        "tiene que decir que la afinidad es la de Vina y no la de XGBoost"
    )


def test_sin_datos_devuelve_none_y_no_un_cero():
    assert calcular(-9.0, 0) is None
    assert calcular(None, 30) is None


def test_ninguna_metrica_entra_en_el_score_total():
    """Decisión explícita: son informativas hasta validarlas en cohorte."""
    from pathlib import Path

    engine = (
        Path(__file__).resolve().parents[1] / "scoring" / "engine.py"
    ).read_text(encoding="utf-8")
    codigo = [l for l in engine.splitlines() if not l.strip().startswith("#")]
    culpables = [
        l.strip() for l in codigo
        if ("fq_vina_proxy" in l or "sile_vina" in l)
        and ("stacking_raw" in l or "total_score" in l)
    ]
    assert not culpables, (
        f"una métrica normalizada entró al score: {culpables}. Antes hay que "
        "validar que la mejora en dependencia con HA se traduce en mejor "
        "ranking, no sólo en menor correlación."
    )
