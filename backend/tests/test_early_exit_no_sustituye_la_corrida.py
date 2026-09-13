"""EVAL-SCI-002 — una heurística de vecindad no cancela el cálculo pedido.

La rama heredada de `_run_full_evaluation_async` consultaba `predict_early_exit`
—media de los scores de los vecinos de Tanimoto ≥ 0.6 en el grafo local— y, si
predecía inactividad, devolvía `{"skipped": True}` SIN acoplar y SIN persistir
resultado. Las consecuencias medidas:

1. El dispatcher marcaba el job `SUCCESS` con ese diccionario;
2. `get_desktop_job_status` no encontraba resultado persistido y lo convertía
   en `FAILURE` con «revisa los logs del backend y reintenta»;
3. la molécula quedaba en `validated`, que el historial no lista.

Es decir: una PREDICCIÓN sustituía a la OBSERVACIÓN pedida, y el usuario veía
un fallo técnico inventado en lugar de su docking. El pre-filtro sale del
camino de ejecución; el grafo sigue disponible para MolChat y para el análisis.
"""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from core.models import JobStatus


BACKEND = Path(__file__).resolve().parents[1]


def test_el_pipeline_heredado_no_consulta_el_prefiltro_de_molgraph():
    fuente = (BACKEND / "services/docking/queue_handler.py").read_text(encoding="utf-8")

    # Se comprueba la LLAMADA, no la palabra: el comentario que explica por qué
    # el pre-filtro se retiró tiene que poder nombrarlo.
    assert "predict_early_exit(" not in fuente
    assert "import predict_early_exit" not in fuente
    assert 'set_job_progress(task_id, 100, "early_exit")' not in fuente


def test_el_runner_pro_tampoco_lo_consulta():
    fuente = (BACKEND / "services/pipeline/runner.py").read_text(encoding="utf-8")

    assert "predict_early_exit(" not in fuente


def test_ninguna_salida_del_pipeline_declara_una_corrida_saltada():
    """`skipped` era la única salida que prometía éxito sin evidencia."""
    from services.docking import queue_handler

    fuente = inspect.getsource(queue_handler)

    assert '"skipped": True' not in fuente


@pytest.mark.asyncio
async def test_un_exito_sin_enlace_durable_sigue_siendo_un_fallo_explicito():
    """SUCCESS sin ``molecule_id`` sigue siendo una violación permanente.

    Una fila todavía no visible se reintenta de forma acotada; sin identificador
    no existe, en cambio, ninguna consulta futura que pueda recuperar evidencia.
    """
    from services.docking.desktop_job_status import get_desktop_job_status

    class _Lock:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class _Cache:
        def __init__(self):
            self.escrito = {}

        async def get(self, _key):
            return None

        async def set(self, key, value, ttl=None):
            self.escrito[key] = value

    jobs = {
        "tarea-sin-resultado": {
            "status": "SUCCESS",
            "progress": 100,
            "result": {"total_score": 88.0},
            "error": None,
        }
    }

    estado = await get_desktop_job_status(
        "tarea-sin-resultado", jobs=jobs, lock=_Lock(), cache=_Cache()
    )

    assert isinstance(estado, JobStatus)
    assert estado.status == "FAILURE"
    assert estado.result is None


def test_no_existe_borrado_automatico_de_resultados_por_score():
    """EVAL-BE-007 — el historial es del usuario: nada se borra solo.

    `_schedule_cleanup` programaba, una hora después de evaluar, el borrado de
    toda molécula no guardada con `total_score < 50`. Estaba desconectado, pero
    seguía en el módulo listo para volver a enchufarse.
    """
    fuente = (BACKEND / "services/docking/queue_handler.py").read_text(encoding="utf-8")

    assert "_schedule_cleanup(" not in fuente
    assert "async def _cleanup_molecule_direct" not in fuente
    assert "delete_molecule(" not in fuente
