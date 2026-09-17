"""El panel de selectividad persiste segun va saliendo, no al final.

DOC 71, DEFECTOS B1 y B2. El diagnostico inicial se quedo corto: se anadio un
aviso de "resultado sin guardar", que informa del problema en vez de resolverlo.
El problema real eran tres cosas encadenadas:

  1. `handleRunAll` corria los OCHO anti-targets y guardaba UNA sola vez, tras
     el ultimo. Un panel completo tarda minutos.
  2. El panel se monta dentro de `{advancedTab === "selectivity" && ...}`, asi
     que cambiar de pestana lo DESMONTA y su estado en memoria muere. A mitad
     de una tanda, todo lo acoplado hasta ahi se perdia sin llegar a la base.
  3. Al volver, solo se rehidrataba desde la base si `autoPoll` estaba activo
     -es decir, solo si el pipeline habia corrido el panel-. Quien lo lanzaba a
     mano encontraba el panel vacio AUNQUE el resultado estuviera guardado.

Estas pruebas cubren la mitad que vive en el backend: que guardar por partes no
pierda lo ya guardado. La mitad del frontend -persistir en cada vuelta del bucle
y rehidratar siempre al montar- vive en `ProSelectivityPanel.tsx`.
"""

from __future__ import annotations

import pytest

from api.routers.pro_features import SaveSelectivityRequest


class _Evaluacion:
    """Lo minimo de una fila de evaluacion para probar la fusion."""

    def __init__(self, previos=None):
        self.anti_target_results = previos
        self.selectivity_ratio = None
        self.selectivity_ran = False
        self.selectivity_verdict = None


def _fusionar(evaluacion: _Evaluacion, payload: SaveSelectivityRequest) -> list[dict]:
    """La fusion tal como la hace el endpoint, aislada para poder probarla.

    Se mantiene igual a proposito: si el endpoint cambia y esto no, la prueba
    deja de proteger nada. Ver `save_selectivity_results_endpoint`.
    """
    previos = {
        r.get("pdb_id"): r
        for r in (evaluacion.anti_target_results or [])
        if isinstance(r, dict) and r.get("pdb_id")
    }
    for r in payload.off_targets:
        if isinstance(r, dict) and r.get("pdb_id"):
            previos[r["pdb_id"]] = r
    return list(previos.values())


def test_guardar_por_partes_acumula_en_vez_de_reemplazar():
    """Es lo que permite que una tanda interrumpida no se pierda."""
    evaluacion = _Evaluacion()

    for pdb, afinidad in (("1ABC", -7.1), ("2DEF", -6.4), ("3GHI", -8.8)):
        payload = SaveSelectivityRequest(
            off_targets=[{"pdb_id": pdb, "affinity": afinidad, "status": "ok"}]
        )
        evaluacion.anti_target_results = _fusionar(evaluacion, payload)

    guardados = {r["pdb_id"] for r in evaluacion.anti_target_results}
    assert guardados == {"1ABC", "2DEF", "3GHI"}


def test_un_guardado_tardio_no_borra_lo_que_ya_estaba():
    """Dos peticiones pueden llegar desordenadas. Reemplazar a ciegas borraria
    anti-targets ya acoplados, que es minutos de trabajo del usuario."""
    evaluacion = _Evaluacion(previos=[
        {"pdb_id": "1ABC", "affinity": -7.1, "status": "ok"},
        {"pdb_id": "2DEF", "affinity": -6.4, "status": "ok"},
    ])
    # Una peticion mas antigua, con un solo objetivo, llega despues.
    tardia = SaveSelectivityRequest(off_targets=[{"pdb_id": "1ABC", "affinity": -7.1}])
    evaluacion.anti_target_results = _fusionar(evaluacion, tardia)

    assert {r["pdb_id"] for r in evaluacion.anti_target_results} == {"1ABC", "2DEF"}


def test_el_ultimo_valor_de_un_objetivo_gana():
    """Reacoplar un anti-target tiene que actualizarlo, no duplicarlo."""
    evaluacion = _Evaluacion(previos=[{"pdb_id": "1ABC", "affinity": None, "status": "failed"}])
    reintento = SaveSelectivityRequest(
        off_targets=[{"pdb_id": "1ABC", "affinity": -7.9, "status": "ok"}]
    )
    evaluacion.anti_target_results = _fusionar(evaluacion, reintento)

    assert len(evaluacion.anti_target_results) == 1
    assert evaluacion.anti_target_results[0]["affinity"] == -7.9
    assert evaluacion.anti_target_results[0]["status"] == "ok"


def test_las_filas_sin_pdb_id_no_entran():
    """Sin clave de fusion no hay forma de actualizarlas despues, y una fila
    anonima acumulada mil veces es basura que nadie puede limpiar."""
    evaluacion = _Evaluacion()
    payload = SaveSelectivityRequest(off_targets=[{"affinity": -7.1}, {"pdb_id": "1ABC"}])
    evaluacion.anti_target_results = _fusionar(evaluacion, payload)

    assert [r["pdb_id"] for r in evaluacion.anti_target_results] == ["1ABC"]


def test_el_endpoint_usa_commit_con_reintento():
    """Con SQLite, escribir mientras el pipeline trabaja es donde falla.

    Un `commit` pelado aqui borraba el unico rastro del panel, y el dossier
    declaraba despues que nunca se corrio -defecto B1-.
    """
    import inspect

    from api.routers import pro_features

    fuente = inspect.getsource(pro_features.save_selectivity_results_endpoint)
    assert "commit_with_retry" in fuente
    assert "await db.commit()" not in fuente


def test_el_endpoint_fusiona_y_no_reemplaza():
    """Guardia sobre la implementacion real, no sobre la copia de esta prueba."""
    import inspect

    from api.routers import pro_features

    fuente = inspect.getsource(pro_features.save_selectivity_results_endpoint)
    assert "evaluation.anti_target_results = payload.off_targets" not in fuente, (
        "el endpoint volvio a reemplazar la lista entera: una tanda interrumpida "
        "perderia los anti-targets ya acoplados"
    )
    assert "fusionados" in fuente


@pytest.mark.parametrize("previos", [None, [], [{"sin_pdb": 1}]])
def test_arranca_bien_desde_cualquier_estado_previo(previos):
    evaluacion = _Evaluacion(previos=previos)
    payload = SaveSelectivityRequest(off_targets=[{"pdb_id": "1ABC", "affinity": -7.0}])
    evaluacion.anti_target_results = _fusionar(evaluacion, payload)
    assert [r["pdb_id"] for r in evaluacion.anti_target_results] == ["1ABC"]


# ── Quien hace el trabajo es quien lo guarda ─────────────────────────────────

def test_el_docking_de_un_anti_target_lo_guarda_el_servidor():
    """DOC 71, B2, en su forma estructural.

    `dock_single_anti_target` devolvia el resultado y se desentendia: guardar
    era tarea del navegador. Si el usuario cerraba la pestana, cambiaba de vista
    o se le caia la conexion entre un objetivo y el siguiente, ese docking -que
    ya se habia PAGADO en CPU- se perdia sin dejar rastro.

    Ahora persiste el endpoint. El resultado sobrevive aunque el cliente
    desaparezca a mitad de la tanda, que es exactamente lo que pasa al cambiar
    de pestana en un panel que se desmonta.
    """
    import inspect

    from api.routers import pro_features

    fuente = inspect.getsource(pro_features.dock_single_anti_target)
    assert "_persistir_anti_target" in fuente, (
        "el docking de un anti-target ya no se guarda en el servidor: si el "
        "cliente desaparece, el trabajo se pierde"
    )
    assert '"persisted"' in fuente, "el cliente no puede saber si quedo guardado"


def test_el_helper_fusiona_y_no_pisa():
    """Reacoplar un objetivo lo actualiza; los demas siguen ahi."""
    import inspect

    from api.routers import pro_features

    fuente = inspect.getsource(pro_features._persistir_anti_target)
    assert "commit_with_retry" in fuente
    assert "merge_selectivity_for_task" in fuente
    # Sin `pdb_id` no hay clave de fusion: se rechaza en vez de acumular basura.
    assert 'resultado.get("pdb_id")' in fuente


def test_ninguna_escritura_del_panel_se_traga_su_fallo():
    """Habia TRES copias del mismo `except Exception: pass` sobre la unica
    escritura del resultado, en tres endpoints distintos.

    La comprobacion NO es «que no haya ningun `pass`»: dentro de estos endpoints
    hay limpiezas de directorios temporales y lecturas de archivo con
    alternativa, y tragar el fallo ahi es correcto -no es trabajo del usuario lo
    que se pierde-. La primera version de esta prueba los marcaba y habria
    obligado a ensuciar codigo sano.

    Lo que se exige es la propiedad que importa: **toda funcion que escriba el
    resultado tiene que registrar el fallo de esa escritura y decirselo al
    cliente**. Un fallo que nadie registra no existe, y un resultado que el
    cliente cree guardado sin estarlo es peor que uno que se sabe perdido.
    """
    import inspect

    from api.routers import pro_features

    escriben = (
        pro_features.run_selectivity,
        pro_features.save_selectivity_results_endpoint,
        pro_features.dock_single_anti_target,
        pro_features._persistir_anti_target,
        pro_features.run_mmgbsa_endpoint,
    )
    for funcion in escriben:
        fuente = inspect.getsource(funcion)
        assert "commit_with_retry" in fuente or "_persistir_anti_target" in fuente, (
            f"{funcion.__name__} escribe sin reintentar: con SQLite eso es donde falla"
        )
        assert "log." in fuente, (
            f"{funcion.__name__} no registra nada: un fallo que nadie registra no existe"
        )

    # NO se escanea el patron `except Exception: pass` en el cuerpo entero.
    # Se intento y era falso positivo cinco veces: dentro de estos endpoints hay
    # limpiezas de temporales y lecturas de archivo con alternativa donde tragar
    # el fallo es lo correcto. Prohibir una forma sintactica en vez de exigir una
    # propiedad habria obligado a ensuciar codigo sano para callar una prueba.


def test_el_mmgbsa_bajo_demanda_se_guarda():
    """Costaba mil pasos de minimizacion y vivia solo en el estado del componente.

    Recargar la pagina lo borraba y habia que repetirlo. Peor: el dossier lee
    `mmgbsa_score` del ORM, asi que el informe declaraba «no calculado» un
    MM-GBSA que el usuario habia visto en pantalla.
    """
    import inspect

    from api.routers import pro_features

    fuente = inspect.getsource(pro_features.run_mmgbsa_endpoint)
    assert "update_evaluation_for_task" in fuente and "mmgbsa_score=" in fuente, (
        "el MM-GBSA bajo demanda vuelve a no persistirse"
    )
    assert "commit_with_retry" in fuente
    assert '"persisted"' in fuente
