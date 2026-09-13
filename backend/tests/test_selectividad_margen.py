"""
El margen de selectividad: ΔΔG, no un cociente de energías libres.

# El fallo

    selectivity_ratio = round(on_target_affinity / worst_off_affinity, 2)

Divide dos energías libres de unión. Como ΔG = −RT·ln K_d, ese cociente es
ln K_on / ln K_off: el logaritmo de una constante de disociación en la base de
la otra. No describe ninguna cantidad física.

Y falla de tres formas distintas que estas pruebas fijan:

  1. Da el MISMO número a márgenes que difieren por un factor de treinta.
  2. No ordena de forma consistente: dos moléculas con el mismo ΔΔG reciben
     cocientes distintos según lo fuerte que sea la unión.
  3. Se indefine justo en el mejor caso posible —que la molécula no se una a la
     anti-diana— porque no hay división que hacer.

# Y la escala estaba por duplicado, sin coincidir

    backend  (selectivity_verdict)   > 10   > 3    > 1.5  > 1.0
    frontend (ProSelectivityPanel)   > 1.8  > 1.2  > 0.9

Un cociente de 2.0 se guardaba en la base y en el dossier como «MODERADAMENTE
SELECTIVO» mientras la pantalla decía «ALTAMENTE SELECTIVO» para la misma
corrida.
"""

import pytest

from services.docking.selectividad_margen import (
    ESCALA_DE_MARGEN,
    KCAL_POR_DECADA,
    VEREDICTO_INVERTIDO,
    VEREDICTO_SIN_DATOS,
    factor_de_selectividad,
    margen_de_selectividad,
    veredicto_de_margen,
)


# ── El defecto, reproducido ────────────────────────────────────────────────

def test_el_cociente_confundia_margenes_que_difieren_treinta_veces():
    """Los dos casos que daban 2.00 y el mismo veredicto."""
    caso_a = margen_de_selectividad(-10.0, -5.0)
    caso_b = margen_de_selectividad(-6.0, -3.0)

    # El cociente que había: idéntico para los dos.
    assert round(-10.0 / -5.0, 2) == round(-6.0 / -3.0, 2) == 2.0

    # ΔΔG los separa: 5.0 frente a 3.0 kcal/mol.
    assert caso_a.delta_delta_g == 5.0
    assert caso_b.delta_delta_g == 3.0

    # Y eso son ~4700x frente a ~160x: un factor de treinta entre ellos.
    assert caso_a.factor / caso_b.factor == pytest.approx(29.5, rel=0.05)


def test_el_mismo_margen_da_el_mismo_resultado_una_el_ligando_como_una():
    """El cociente cambiaba con la potencia absoluta; ΔΔG no."""
    debil = margen_de_selectividad(-6.0, -4.0)
    fuerte = margen_de_selectividad(-12.0, -10.0)
    assert debil.delta_delta_g == fuerte.delta_delta_g == 2.0
    assert veredicto_de_margen(debil.delta_delta_g) == veredicto_de_margen(fuerte.delta_delta_g)
    # El cociente, en cambio, los separaba: 1.5 frente a 1.2.
    assert round(-6.0 / -4.0, 2) != round(-12.0 / -10.0, 2)


def test_no_unirse_a_la_anti_diana_es_el_mejor_caso_no_un_hueco():
    """Con ΔG_off ≥ 0 el cociente se indefinía y salía «sin datos»."""
    margen = margen_de_selectividad(-9.0, 0.5)
    assert margen is not None
    assert margen.delta_delta_g == 9.5
    assert veredicto_de_margen(margen.delta_delta_g) == ESCALA_DE_MARGEN[0][1]


# ── La física ──────────────────────────────────────────────────────────────

def test_el_signo_dice_quien_une_mas_fuerte():
    # Diana principal más fuerte -> positivo.
    assert margen_de_selectividad(-10.0, -6.0).delta_delta_g == 4.0
    # Anti-diana más fuerte -> negativo, y se nombra.
    invertido = margen_de_selectividad(-6.0, -10.0)
    assert invertido.delta_delta_g == -4.0
    assert veredicto_de_margen(invertido.delta_delta_g) == VEREDICTO_INVERTIDO


@pytest.mark.parametrize(
    ("ddg", "factor_esperado"),
    [(0.0, 1.0), (KCAL_POR_DECADA, 10.0), (2 * KCAL_POR_DECADA, 100.0)],
)
def test_una_decada_por_cada_1_3633_kcal(ddg, factor_esperado):
    assert factor_de_selectividad(ddg) == pytest.approx(factor_esperado, rel=1e-6)


def test_la_banda_del_factor_abarca_la_dispersion_de_vina():
    """±2 kcal/mol son casi tres órdenes de magnitud de anchura."""
    margen = margen_de_selectividad(-10.0, -6.0)
    assert margen.factor_min < margen.factor < margen.factor_max
    import math
    anchura = math.log10(margen.factor_max / margen.factor_min)
    assert anchura == pytest.approx(2 * 2.0 / KCAL_POR_DECADA, rel=1e-6)


def test_sin_afinidades_no_hay_margen():
    assert margen_de_selectividad(None, -6.0) is None
    assert margen_de_selectividad(-6.0, None) is None
    assert veredicto_de_margen(None) == VEREDICTO_SIN_DATOS


# ── La escala ──────────────────────────────────────────────────────────────

def test_los_cortes_estan_en_ordenes_de_magnitud_redondos():
    """No son números elegidos a ojo: 2.73 son 100x y 1.36 son 10x."""
    assert factor_de_selectividad(ESCALA_DE_MARGEN[0][0]) == pytest.approx(100, rel=0.02)
    assert factor_de_selectividad(ESCALA_DE_MARGEN[1][0]) == pytest.approx(10, rel=0.02)


def test_ninguna_etiqueta_promete_seguridad():
    """Un margen in silico con ±2 kcal/mol no autoriza la palabra «seguro»."""
    for _, veredicto in ESCALA_DE_MARGEN:
        bajo = veredicto.lower()
        assert "seguro" not in bajo
        assert "seguridad" not in bajo


def test_la_escala_es_monotona():
    umbrales = [u for u, _ in ESCALA_DE_MARGEN]
    assert umbrales == sorted(umbrales, reverse=True)


# ── Una sola escala en los dos lados ───────────────────────────────────────

def test_el_frontend_usa_exactamente_los_mismos_umbrales():
    """La divergencia backend/frontend es justo lo que se está arreglando."""
    import re
    from pathlib import Path

    ruta = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "selectividadMargen.ts"
    fuente = ruta.read_text(encoding="utf-8")

    bloque = re.search(r"ESCALA_DE_MARGEN[^=]*=\s*\[(.*?)\];", fuente, re.S)
    assert bloque, "no se encontró ESCALA_DE_MARGEN en el frontend"
    umbrales_ts = [float(x) for x in re.findall(r"\[\s*([0-9.]+)\s*,", bloque.group(1))]
    umbrales_py = [u for u, _ in ESCALA_DE_MARGEN]

    assert umbrales_ts == umbrales_py, (
        f"los umbrales divergieron otra vez: python={umbrales_py} typescript={umbrales_ts}"
    )

    # Y la constante de conversión, que decide el significado de cada corte.
    decada_ts = re.search(r"KCAL_POR_DECADA\s*=\s*([0-9.]+)", fuente)
    assert decada_ts and float(decada_ts.group(1)) == KCAL_POR_DECADA
