"""
El dimensionado de ENS-PROD-01, fijado. Y por qué R2 no podía concluir.

LO QUE MIDE, Y LO QUE ESO CAMBIA
═══════════════════════════════════════════════════════════════════════════

La revisión del ensamble dejó ENS-PROD-01 en borrador con cuatro decisiones
pendientes. Tres necesitan datos, dinero o una decisión de dominio; la de
tamaño/potencia es aritmética sobre un artefacto ya sellado, así que se puede
cerrar sin mirar ningún conjunto nuevo —que es exactamente lo que el borrador
exige—.

Resultado, con la estructura de discordancia observada en MF-33-B-RET-R2
(TODOS, top-1: 7 pares a favor del ensemble, 3 a favor de una conformación,
48 complejos) y McNemar exacta a dos colas con α=0.05:

    potencia alcanzada con n=48        0.150
    n para 80% de potencia              248
    n para 90% de potencia              324

**R2 no «no demostró» mejora en top-1: no podía demostrarla.** Con 15% de
potencia, el resultado más probable era justamente el que salió. Es una lectura
distinta del mismo dato sellado, y no requiere volver a correr nada.

Las cifras son COTAS INFERIORES por dos razones independientes, ambas en el
informe: dimensionar con el efecto observado en la corrida que motivó el ensayo
sesga a la baja, y McNemar supone pares independientes mientras una cohorte con
series congenéricas tiene n efectivo menor que su n nominal.

Estas pruebas fijan la aritmética —que reproduce las p selladas y que la
potencia se calcula exacta y no por aproximación normal— para que nadie ajuste
un número del plan sin que se note.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from audits.ens_prod_01_potencia import (
    ALFA,
    _k_critico,
    informe,
    n_necesario,
    p_exacta_mcnemar,
    potencia_exacta,
)

AUDITS = Path(__file__).resolve().parents[1] / "audits"


# ── La aritmética, contra valores que se pueden comprobar a mano ──────


@pytest.mark.parametrize("b,c,esperado", [
    (7, 3, 0.34375),        # TODOS/top1 sellado
    (9, 0, 0.00390625),     # TODOS/top5 sellado
    (15, 0, 6.103515625e-05),  # TODOS/oraculo sellado
    (7, 2, 0.1796875),      # COLOCACION/top1 sellado
    (0, 0, 1.0),            # sin discordantes no hay prueba
    (1, 1, 1.0),            # simetria perfecta
])
def test_la_p_exacta_reproduce_las_selladas(b, c, esperado):
    """Si esta función no reproduce las p del artefacto, no es la misma prueba."""
    assert p_exacta_mcnemar(b, c) == pytest.approx(esperado, rel=1e-12)


@pytest.mark.parametrize("d,esperado", [
    (5, -1),   # con cinco discordantes, ni 0 a 5 rechaza a dos colas: 2/32=0.0625
    (6, 0),    # 2*(1/64) = 0.03125 <= 0.05
    (10, 1),   # 2*(1+10)/1024 = 0.0215
    (20, 5),
])
def test_la_region_de_rechazo_es_la_cola_exacta(d, esperado):
    """`_k_critico` define el rechazo, así que se comprueba contra la binomial.

    El caso d=5 es el que explica por qué el dimensionado importa: con cinco
    pares discordantes NINGÚN reparto alcanza significación a dos colas, por
    perfecto que sea. Un ensayo demasiado pequeño no puede ganar.
    """
    assert _k_critico(d, ALFA) == esperado
    if esperado >= 0:
        assert p_exacta_mcnemar(esperado, d - esperado) <= ALFA
    assert p_exacta_mcnemar(esperado + 1, d - esperado - 1) > ALFA


def test_la_potencia_crece_con_el_tamano_y_no_se_sale_de_rango():
    anterior = 0.0
    for n in (50, 100, 200, 400):
        potencia = potencia_exacta(n, 0.2083, 0.7)
        assert 0.0 <= potencia <= 1.0
        # No se exige monotonía estricta paso a paso -una prueba exacta salta-,
        # pero entre estos tamaños la tendencia tiene que ser clara.
        assert potencia > anterior
        anterior = potencia


def test_bajo_la_hipotesis_nula_la_potencia_no_pasa_del_nivel():
    """Con psi=0.5 no hay efecto: lo que quede es el tamaño real de la prueba.

    Tiene que quedar POR DEBAJO de α, no en α: la prueba exacta de McNemar es
    conservadora porque su estadístico es discreto. Si saliera por encima, el
    cálculo estaría inflando la potencia de todo el informe.
    """
    for n in (48, 100, 248):
        assert potencia_exacta(n, 0.2083, 0.5) <= ALFA


def test_sin_efecto_no_hay_n_que_alcance_la_potencia():
    assert n_necesario(0.2083, 0.5, 0.80, techo=400) is None


def test_la_potencia_analitica_coincide_con_una_simulacion_independiente():
    """La fórmula, comprobada por otro método. No basta que sea coherente consigo.

    Se simulan cohortes completas y se cuenta cuántas veces rechaza la MISMA
    prueba exacta. Es el único control que distingue «la aritmética está bien»
    de «la aritmética es consistente con su propio error».

    Medido con 20 000 repeticiones y semilla fija, sobre la estructura del
    contraste primario y sobre la hipótesis nula:

        n=48, psi=0.70    analítica 0.1501    simulada 0.1494
        n=48, psi=0.50    analítica 0.0221    simulada 0.0221

    La tolerancia es tres errores estándar de la simulación, que con 20 000
    repeticiones y p≈0.15 son ~0.0076.
    """
    import random

    def simulada(n: int, p_discordancia: float, psi: float,
                 repeticiones: int = 20000) -> float:
        rng = random.Random(20260917)
        rechazos = 0
        for _ in range(repeticiones):
            b = c = 0
            for _ in range(n):
                if rng.random() < p_discordancia:
                    if rng.random() < psi:
                        b += 1
                    else:
                        c += 1
            if p_exacta_mcnemar(b, c) <= ALFA:
                rechazos += 1
        return rechazos / repeticiones

    for psi in (0.7, 0.5):
        analitica = potencia_exacta(48, 0.2083, psi)
        montecarlo = simulada(48, 0.2083, psi)
        error_estandar = (montecarlo * (1 - montecarlo) / 20000) ** 0.5
        assert abs(analitica - montecarlo) <= max(3 * error_estandar, 0.005), (
            f"psi={psi}: la fórmula da {analitica:.4f} y la simulación "
            f"{montecarlo:.4f}. Una de las dos está mal."
        )


# ── El informe, con sus cifras ────────────────────────────────────────


@pytest.fixture(scope="module")
def datos():
    return informe()


def test_el_contraste_primario_necesita_248_complejos(datos):
    """La cifra que decide si ENS-PROD-01 se puede hacer."""
    top1 = datos["estratos"]["TODOS"]["top1"]
    assert top1["b_gana_ensemble"] == 7 and top1["c_gana_single"] == 3
    assert top1["n"] == 48
    assert top1["n_necesario"]["0.80"] == 248
    assert top1["n_necesario"]["0.90"] == 324


def test_r2_no_podia_concluir_sobre_top1(datos):
    """15% de potencia. El resultado que salió era el más probable.

    Es la conclusión que cambia la lectura del artefacto sellado sin tocar un
    solo byte suyo: «no demostró mejora» y «no podía demostrarla» no son lo
    mismo, y sólo la segunda es cierta.
    """
    top1 = datos["estratos"]["TODOS"]["top1"]
    assert top1["potencia_alcanzada_en_r2"] == pytest.approx(0.150, abs=0.001)
    # Los contrastes que SÍ alcanzaron significación estaban bien dimensionados:
    # no es que R2 fuera pequeño para todo, es que lo era para el primario.
    assert datos["estratos"]["TODOS"]["top5"]["potencia_alcanzada_en_r2"] > 0.90
    assert datos["estratos"]["TODOS"]["oraculo"]["potencia_alcanzada_en_r2"] > 0.99


def test_la_curva_pone_precio_a_cada_umbral_sin_elegirlo(datos):
    """El umbral de relevancia práctica sigue siendo una decisión, con su cifra."""
    curva = {fila["delta_pp"]: fila for fila in datos["curva_de_precio"]}
    assert curva[5.0]["n_080"] == 684
    assert curva[10.0]["n_080"] == 175
    assert curva[20.0]["n_080"] == 40
    # Más exigente cuesta más complejos, sin excepción.
    precios = [curva[d]["n_080"] for d in sorted(curva)]
    assert precios == sorted(precios, reverse=True)


def test_el_informe_declara_sus_dos_sesgos_y_lo_que_sigue_abierto(datos):
    """Un dimensionado sin sus supuestos es un número que engaña."""
    texto = " ".join(datos["advertencias"]).lower()
    assert "cotas inferiores" in texto
    assert "independientes" in texto
    assert "cohorte" in texto and "umbral" in texto
    assert datos["estado"].startswith("BORRADOR")
    assert "no es confirmacion ciega" in datos["fuente"]["no_es_ciego"].lower()


def test_el_artefacto_publicado_coincide_con_el_calculo(datos):
    """El JSON del repositorio no puede desviarse de lo que el script calcula."""
    publicado = json.loads(
        (AUDITS / "ens_prod_01_potencia.json").read_text(encoding="utf-8")
    )
    assert publicado == datos, (
        "el informe publicado no reproduce el cálculo actual: vuelve a generarlo "
        "con `python backend/audits/ens_prod_01_potencia.py --output backend/audits`"
    )
