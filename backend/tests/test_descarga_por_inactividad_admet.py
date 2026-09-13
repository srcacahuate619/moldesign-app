"""
El temporizador de inactividad de ADMET-AI se colgaba con el candado en la mano.

# El fallo

    _admet_idle_lock = threading.Lock()          # NO reentrante

    def unload_admet_model():
        with _admet_idle_lock:        # (2) lo pide otra vez
            ...

    def _idle_check_loop():
        while True:
            time.sleep(60)
            with _admet_idle_lock:    # (1) lo tiene
                if idle > _admet_idle_timeout:
                    unload_admet_model()   # -> (2), y aquí se queda

`threading.Lock` no es reentrante: el mismo hilo que lo tiene se bloquea al
pedirlo de nuevo. Y el efecto no es sólo que el modelo no se descargue. El hilo
queda colgado **para siempre** con el candado tomado, y `_start_idle_timer`
también lo pide — así que, como `get_admet_model()` lo llama en cada uso:

    minuto 0    se carga el modelo, arranca el temporizador
    minuto 5    el temporizador decide descargar y se cuelga con el candado
    después     cualquier predicción ADMET se bloquea indefinidamente

Cinco minutos de inactividad y la siguiente evaluación colgaba la petición. La
memoria tampoco se liberaba nunca, que era lo único que el temporizador existía
para hacer.

# Y el motivo por el que se reportó

Recargar ADMET-AI cuesta unos 20 s. Con la espera en cinco minutos, una sesión
de evaluaciones espaciadas pagaba esa recarga varias veces. Ahora son 30 minutos
y se puede configurar con `MOLDESIGN_ADMET_IDLE_MINUTOS` (0 la desactiva).
"""

from __future__ import annotations

import threading
import time

import pytest

from chem import blood_viability as bv


@pytest.fixture
def sin_torch(monkeypatch):
    """`unload_admet_model` importa torch y llama a `gc.collect()`.

    Las dos cosas tardan —el import de torch son unos 12 s— y no son lo que se
    está probando. El candado, que sí lo es, se ejercita igual. De hecho el
    primer intento de esta prueba falló por el import, no por el candado: sin
    esto, «no vuelve en 10 s» no distingue un bloqueo de una importación lenta.
    """
    import sys
    import types

    falso = types.ModuleType("torch")
    falso.cuda = types.SimpleNamespace(
        is_available=lambda: False, empty_cache=lambda: None
    )
    monkeypatch.setitem(sys.modules, "torch", falso)
    monkeypatch.setattr(bv.gc, "collect", lambda *_a, **_k: 0)
    yield


@pytest.fixture(autouse=True)
def _estado_limpio():
    previo = (bv._ADMET_MODEL, bv._admet_en_uso, bv._last_admet_use)
    bv._admet_en_uso = 0
    yield
    bv._ADMET_MODEL, bv._admet_en_uso, bv._last_admet_use = previo


def test_el_candado_es_reentrante():
    """El bucle lo tiene tomado cuando llama a lo que vuelve a pedirlo."""
    assert isinstance(bv._admet_idle_lock, type(threading.RLock())), (
        "con un Lock no reentrante, el hilo de inactividad se cuelga para siempre"
    )


def test_descargar_con_el_candado_tomado_no_bloquea(sin_torch):
    """La reproducción exacta del fallo: el bucle decidía y llamaba desde dentro."""
    bv._ADMET_MODEL = object()
    bv._last_admet_use = 0.0

    terminado = threading.Event()

    def descargar():
        with bv._admet_idle_lock:      # como hacía `_idle_check_loop`
            bv.unload_admet_model()
        terminado.set()

    hilo = threading.Thread(target=descargar, daemon=True)
    hilo.start()
    assert terminado.wait(timeout=10), (
        "`unload_admet_model` no vuelve cuando se llama con el candado tomado"
    )
    assert bv._ADMET_MODEL is None


def test_una_prediccion_en_curso_impide_la_descarga(sin_torch):
    """El modelo no puede desaparecer entre `get_admet_model()` y `predict()`."""
    bv._ADMET_MODEL = object()
    with bv._EnUso():
        bv.unload_admet_model()
        assert bv._ADMET_MODEL is not None, "descargó con una predicción dentro"
    bv.unload_admet_model()
    assert bv._ADMET_MODEL is None


def test_el_contador_de_uso_soporta_predicciones_solapadas(sin_torch):
    """Dos peticiones a la vez: la primera en salir no puede abrir la puerta."""
    bv._ADMET_MODEL = object()
    with bv._EnUso():
        with bv._EnUso():
            assert bv._admet_en_uso == 2
        assert bv._admet_en_uso == 1
        bv.unload_admet_model()
        assert bv._ADMET_MODEL is not None
    assert bv._admet_en_uso == 0


def test_salir_de_una_prediccion_reinicia_la_cuenta_de_inactividad():
    """La inactividad se mide desde que TERMINA el trabajo, no desde que empieza."""
    bv._last_admet_use = 0.0
    with bv._EnUso():
        pass
    assert time.time() - bv._last_admet_use < 1.0


def test_la_espera_por_defecto_cubre_una_sesion_de_trabajo():
    """Cinco minutos hacían pagar los ~20 s de recarga varias veces por sesión."""
    assert bv._admet_idle_timeout >= 20 * 60


def test_se_puede_configurar_y_desactivar(monkeypatch):
    monkeypatch.setenv("MOLDESIGN_ADMET_IDLE_MINUTOS", "5")
    assert bv._timeout_por_configuracion() == 300.0
    monkeypatch.setenv("MOLDESIGN_ADMET_IDLE_MINUTOS", "0")
    assert bv._timeout_por_configuracion() == 0.0
    monkeypatch.setenv("MOLDESIGN_ADMET_IDLE_MINUTOS", "no es un numero")
    assert bv._timeout_por_configuracion() == 1800.0, "un valor ilegible no rompe el arranque"


def test_con_la_descarga_desactivada_no_se_arranca_el_hilo(monkeypatch):
    monkeypatch.setattr(bv, "_admet_idle_timeout", 0.0)
    monkeypatch.setattr(bv, "_admet_idle_thread", None)
    bv._start_idle_timer()
    assert bv._admet_idle_thread is None


def test_el_trabajo_pesado_ocurre_fuera_del_candado():
    """Sostener el candado durante `gc.collect()` bloquea a quien pida una predicción."""
    import inspect

    fuente = inspect.getsource(bv.unload_admet_model)
    cuerpo = fuente.split("with _admet_idle_lock:")[1]
    # Todo lo que quede con la indentación del `with` ya está fuera de él.
    fuera = [l for l in cuerpo.splitlines() if l.startswith("    ") and not l.startswith("        ")]
    assert any("gc.collect()" in l for l in fuera), (
        "`gc.collect()` sigue dentro del candado"
    )
