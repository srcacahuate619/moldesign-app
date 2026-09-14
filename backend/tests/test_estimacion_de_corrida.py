r"""La estimacion que se le ensena al usuario ANTES de pulsar «Evaluar».

# Que protege, en orden de importancia

1. **Que no promete lo que no sabe.** Sin corridas previas en este equipo, las
   constantes son de OTRA maquina y la banda tiene que ser ancha y decirlo. Una
   estimacion estrecha y equivocada es peor que no dar ninguna: contradice
   justamente lo que este producto vende, que es saber cuando no fiarse.

2. **Que avisa del limite duro.** Vina se mata a los 600 s por acoplamiento. Una
   configuracion que lo supere no es lenta: falla, y hay que decirlo ANTES de
   que el usuario espere diez minutos para nada.

3. **Que el coste de UNA vez se declara aparte.** Preparar un receptor cuesta
   ~8.8 s medidos y se paga una sola vez. Es la diferencia que hizo que una
   primera corrida pareciera rota al lado de la segunda.

4. **Que se calibra sola.** A partir de tres acoplamientos reales, la estimacion
   deja de salir de una tabla y sale de lo observado en esa maquina.

# Las medidas de las que sale el modelo

2026-09-14, 1WBM, mismo ligando y misma caja, variando solo los nucleos:

    12 nucleos   36.2 s   ex 8        4 nucleos   55.2 s   ex 8
     8 nucleos   34.2 s   ex 8        2 nucleos  102.7 s   ex 8
    12 nucleos  101.9 s   ex 32
"""

from __future__ import annotations

import json

import pytest

from services import estimacion


@pytest.fixture(autouse=True)
def _calibracion_aislada(tmp_path, monkeypatch):
    """Cada prueba estrena su fichero de calibracion.

    Sin esto, una prueba que registra observaciones cambiaria el resultado de
    las siguientes —y, peor, la suite leeria la calibracion REAL de la maquina
    donde corre, que es distinta en cada una.
    """
    monkeypatch.setattr(
        estimacion, "_fichero_de_calibracion", lambda: tmp_path / "docking.json"
    )
    yield


# ── Sin historial: ancha, y lo dice ─────────────────────────────────────────


def test_sin_historial_la_banda_es_ancha_y_lo_declara():
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    assert e["apoyo"] == "modelo"
    assert "otra máquina" in e["detalle_apoyo"]
    # Al menos 2x entre los extremos: es una estimacion, no una promesa.
    assert e["segundos_max"] >= e["segundos_min"] * 2


def test_la_banda_cubre_lo_que_se_midio_de_verdad():
    """El caso de 2 nucleos que el estimador viejo erraba por 2.3x."""
    e = estimacion.estimar_corrida(cpu=2, exhaustiveness=8)
    # Medido: 102.7 s de acoplamiento. Tiene que caer DENTRO.
    assert e["segundos_min"] <= 102.7 <= e["segundos_max"]


def test_cubre_tambien_el_caso_de_muchos_nucleos():
    e = estimacion.estimar_corrida(cpu=12, exhaustiveness=8)
    assert e["segundos_min"] <= 36.2 <= e["segundos_max"]


def test_cubre_la_exhaustiveness_alta_que_la_tabla_vieja_ignoraba():
    e = estimacion.estimar_corrida(cpu=12, exhaustiveness=32)
    assert e["segundos_min"] <= 101.9 <= e["segundos_max"]


# ── Lo que el modelo tiene que capturar ─────────────────────────────────────


def test_la_exhaustiveness_pesa_y_no_se_ignora():
    poca = estimacion.estimar_corrida(cpu=4, exhaustiveness=8)
    mucha = estimacion.estimar_corrida(cpu=4, exhaustiveness=32)
    assert mucha["segundos_min"] > poca["segundos_min"] * 2


def test_mas_nucleos_que_exhaustiveness_no_compra_nada():
    """Medido: 12 nucleos y 8 dan el mismo tiempo con exhaustiveness 8."""
    ocho = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    doce = estimacion.estimar_corrida(cpu=12, exhaustiveness=8)
    assert ocho["segundos_min"] == doce["segundos_min"]


def test_la_caja_pesa_poco_porque_asi_se_midio():
    chica = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, volumen_caja=11391)
    grande = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, volumen_caja=27000)
    proporcion = grande["segundos_min"] / chica["segundos_min"]
    # Medido 1.25x para 2.37x de volumen. Ni lo ignora ni lo exagera.
    assert 1.1 < proporcion < 1.45


def test_los_conformeros_multiplican_los_acoplamientos():
    uno = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, conformers=1)
    cinco = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, conformers=5)
    assert cinco["segundos_min"] > uno["segundos_min"] * 3


# ── El coste de una sola vez ────────────────────────────────────────────────


def test_el_receptor_sin_preparar_se_declara_aparte_y_como_unico():
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, receptor_preparado=False)
    assert e["una_vez"] is not None
    assert "una sola vez" in e["una_vez"]["nota"]
    # Y suma al total: si no sumara, el usuario volveria a llevarse la sorpresa.
    preparado = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    assert e["segundos_min"] > preparado["segundos_min"]


def test_un_receptor_ya_preparado_no_inventa_un_coste_que_no_existe():
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, receptor_preparado=True)
    assert e["una_vez"] is None


# ── Los avisos ──────────────────────────────────────────────────────────────


def test_avisa_cuando_la_corrida_va_a_reventar_contra_el_timeout():
    e = estimacion.estimar_corrida(cpu=1, exhaustiveness=64, volumen_caja=125000)
    assert any("fallaría" in a for a in e["avisos"])


def test_no_avisa_de_timeout_cuando_no_lo_hay():
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    assert not any("fallaría" in a for a in e["avisos"])


def test_sugiere_bajar_la_exhaustiveness_cuando_no_cabe_en_los_nucleos():
    e = estimacion.estimar_corrida(cpu=2, exhaustiveness=16)
    assert any("tandas" in a for a in e["avisos"])


def test_un_ligando_atipico_ensancha_la_banda_en_vez_de_mover_el_centro():
    """No se midio, asi que no se multiplica: se declara la incertidumbre."""
    normal = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, rotables_del_ligando=5)
    raro = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, rotables_del_ligando=25)
    assert raro["segundos_min"] == normal["segundos_min"]
    assert raro["segundos_max"] > normal["segundos_max"]
    assert any("rotables" in a for a in raro["avisos"])


# ── La calibracion ──────────────────────────────────────────────────────────


def test_tres_observaciones_cambian_el_apoyo_de_modelo_a_historial():
    assert estimacion.estimar_corrida(cpu=8, exhaustiveness=8)["apoyo"] == "modelo"
    for _ in range(3):
        estimacion.registrar_docking(
            segundos=60.0, cpu=8, exhaustiveness=8, volumen_caja=27000
        )
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    assert e["apoyo"] == "historial"
    assert "este equipo" in e["detalle_apoyo"]


def test_una_maquina_lenta_acaba_estimando_como_una_maquina_lenta():
    for _ in range(5):
        estimacion.registrar_docking(
            segundos=300.0, cpu=8, exhaustiveness=8, volumen_caja=27000
        )
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    # Sin calibrar, el modelo daba del orden de 20-80 s de acoplamiento.
    assert e["segundos_min"] > 150


def test_dos_observaciones_no_bastan_para_fiarse_de_una_muestra_diminuta():
    for _ in range(2):
        estimacion.registrar_docking(
            segundos=300.0, cpu=8, exhaustiveness=8, volumen_caja=27000
        )
    assert estimacion.estimar_corrida(cpu=8, exhaustiveness=8)["apoyo"] == "modelo"


def test_la_calibracion_descuenta_nucleos_y_caja_antes_de_guardar():
    """Dos maquinas iguales con distinta caja deben calibrar a lo mismo."""
    estimacion.registrar_docking(segundos=34.0, cpu=8, exhaustiveness=8, volumen_caja=27000)
    guardado = json.loads((estimacion._fichero_de_calibracion()).read_text(encoding="utf-8"))
    muestra = guardado["observaciones"][0]
    assert muestra["tandas"] == 1
    assert muestra["segundos_por_tanda"] == pytest.approx(34.0, abs=0.5)

    # Cuatro tandas del mismo coste por tanda: la observacion es la misma.
    estimacion.registrar_docking(segundos=136.0, cpu=2, exhaustiveness=8, volumen_caja=27000)
    guardado = json.loads((estimacion._fichero_de_calibracion()).read_text(encoding="utf-8"))
    assert guardado["observaciones"][1]["segundos_por_tanda"] == pytest.approx(34.0, abs=0.5)


def test_una_corrida_absurda_no_envenena_la_calibracion():
    estimacion.registrar_docking(segundos=0, cpu=8, exhaustiveness=8, volumen_caja=27000)
    estimacion.registrar_docking(segundos=-5, cpu=8, exhaustiveness=8, volumen_caja=27000)
    estimacion.registrar_docking(segundos=30, cpu=0, exhaustiveness=8, volumen_caja=27000)
    assert estimacion._leer_observaciones() == []


def test_la_calibracion_no_crece_sin_limite():
    for i in range(estimacion.MAXIMO_OBSERVACIONES + 20):
        estimacion.registrar_docking(
            segundos=30.0 + i, cpu=8, exhaustiveness=8, volumen_caja=27000
        )
    assert len(estimacion._leer_observaciones()) == estimacion.MAXIMO_OBSERVACIONES


def test_un_fichero_de_calibracion_roto_no_tumba_la_estimacion():
    ruta = estimacion._fichero_de_calibracion()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("{ esto no es json", encoding="utf-8")
    e = estimacion.estimar_corrida(cpu=8, exhaustiveness=8)
    assert e["apoyo"] == "modelo"


# ── Cohortes: es el mismo calculo con N ligandos ────────────────────────────


def test_una_cohorte_de_cincuenta_cuesta_mas_que_una_molecula():
    una = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, ligandos=1)
    cohorte = estimacion.estimar_corrida(cpu=8, exhaustiveness=8, ligandos=50)
    assert cohorte["segundos_min"] > una["segundos_min"] * 20
    assert cohorte["ligandos"] == 50


def test_el_paralelismo_de_la_cohorte_reduce_el_reloj():
    en_serie = estimacion.estimar_corrida(
        cpu=8, exhaustiveness=8, ligandos=20, docks_en_paralelo=1
    )
    en_paralelo = estimacion.estimar_corrida(
        cpu=8, exhaustiveness=8, ligandos=20, docks_en_paralelo=4
    )
    assert en_paralelo["segundos_min"] < en_serie["segundos_min"]
