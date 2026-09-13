"""EVAL-BE-005 — `/evaluation/evaluate` no es una puerta trasera del submit.

El endpoint síncrono ejecuta el MISMO pipeline que `/evaluation/submit`, pero
se saltaba todo lo que rodea a una corrida:

* la comprobación previa aceptada (`preflight_fingerprint`), que en el submit
  se recalcula en el backend antes de ejecutar;
* el registro del dueño del `task_id`, del que dependen `status`, `stream` y
  `cancel` para decidir quién puede operar la corrida.

Aceptar el campo `preflight_fingerprint` en el modelo y no comprobarlo es lo
peor de las dos opciones: el cliente cree que existe un gate que no existe.

TRANS-ANON-002 (2026-08-30) retiró un tercer gate que este archivo vigilaba: la
cuota anónima por IP. Se decidió que sin cuenta se evalúa sin límite —la cuenta
hace falta para guardar en Moldex y para certificar—, así que la prueba que
exigía el 403 se invirtió: ahora exige que **no** se bloquee.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.routers import evaluation


def _request(ip: str = "10.0.0.7") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/evaluation/evaluate",
            "raw_path": b"/evaluation/evaluate",
            "query_string": b"",
            "headers": [],
            "client": (ip, 5555),
            "server": ("testserver", 80),
        }
    )


class _Repositorio:
    """Repositorio que delata cualquier intento de volver a contar anónimos."""

    def __init__(self, count=0):
        self.consultas_de_cuota = 0

    async def get_anonymous_limit(self, _ip):  # pragma: no cover - no debe llamarse
        self.consultas_de_cuota += 1
        raise AssertionError("la cuota anónima se retiró en TRANS-ANON-002")

    async def increment_anonymous_count(self, _ip):  # pragma: no cover
        self.consultas_de_cuota += 1
        raise AssertionError("la cuota anónima se retiró en TRANS-ANON-002")


@pytest.mark.asyncio
async def test_la_evaluacion_sincrona_anonima_no_tiene_cupo(monkeypatch):
    """TRANS-ANON-002: sin cuenta se evalúa sin límite, y sin contar nada.

    Antes esta prueba exigía un 403 al superar la cuota. La cuota se contaba por
    IP, y en escritorio todo es `127.0.0.1`: medía máquinas, no personas. El
    repositorio espía de arriba lanza si alguien vuelve a consultarla.
    """
    repositorio = _Repositorio()
    monkeypatch.setattr(evaluation, "Repository", lambda _db: repositorio)

    async def _sin_receptor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(evaluation, "get_target_for_user", _sin_receptor)

    peticion = evaluation.EvaluationSubmitRequest(smiles="CC(=O)Oc1ccccc1C(=O)O", target_pdb_id="7E2Y")

    respuesta = await evaluation.evaluate_sync(
        data=peticion, request=_request(), current_user=None, db=None
    )

    assert respuesta.media_type == "text/event-stream"
    assert repositorio.consultas_de_cuota == 0


@pytest.mark.asyncio
async def test_la_evaluacion_sincrona_comprueba_la_huella_del_preflight(monkeypatch):
    repositorio = _Repositorio()
    monkeypatch.setattr(evaluation, "Repository", lambda _db: repositorio)

    async def _sin_receptor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(evaluation, "get_target_for_user", _sin_receptor)

    async def _preflight_distinto(**_kwargs):
        return {
            "technical_blockers": [],
            "input_fingerprint": "sha256:" + "b" * 64,
        }

    monkeypatch.setattr(evaluation, "evaluation_preflight", _preflight_distinto)

    peticion = evaluation.EvaluationSubmitRequest(
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        target_pdb_id="7E2Y",
        preflight_fingerprint="sha256:" + "a" * 64,
    )

    with pytest.raises(HTTPException) as error:
        await evaluation.evaluate_sync(
            data=peticion, request=_request(), current_user=None, db=None
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_la_revalidacion_conserva_la_cadena_aceptada_en_el_preflight(monkeypatch):
    """La huella del submit debe describir la misma cadena que vio la persona."""
    repositorio = _Repositorio()
    cadena_revalidada = None

    async def _preflight_misma_huella(*, data, **_kwargs):
        nonlocal cadena_revalidada
        cadena_revalidada = data.chain
        return {
            "technical_blockers": [],
            "input_fingerprint": "sha256:" + "a" * 64,
        }

    monkeypatch.setattr(evaluation, "evaluation_preflight", _preflight_misma_huella)
    peticion = evaluation.EvaluationSubmitRequest(
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        target_pdb_id="7E2Y",
        chain="R",
        preflight_fingerprint="sha256:" + "a" * 64,
    )

    await evaluation._enforce_submission_gates(
        data=peticion,
        canonical_smiles=peticion.smiles,
        request=_request(),
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=None,
        repository=repositorio,
        submission_target=SimpleNamespace(chain="R"),
    )

    assert cadena_revalidada == "R"


@pytest.mark.asyncio
async def test_submit_rechaza_una_cadena_distinta_a_la_del_receptor():
    peticion = evaluation.EvaluationSubmitRequest(
        smiles="CCO",
        target_pdb_id="7E2Y",
        chain="B",
    )

    with pytest.raises(HTTPException) as error:
        await evaluation._enforce_submission_gates(
            data=peticion,
            canonical_smiles=peticion.smiles,
            request=_request(),
            current_user=SimpleNamespace(id=uuid.uuid4()),
            db=None,
            repository=_Repositorio(count=0),
            submission_target=SimpleNamespace(chain="R"),
        )

    assert error.value.status_code == 409
    assert "cadena" in str(error.value.detail).lower()


@pytest.mark.asyncio
async def test_un_bloqueante_de_preparacion_detiene_la_evaluacion_sincrona(monkeypatch):
    repositorio = _Repositorio()
    monkeypatch.setattr(evaluation, "Repository", lambda _db: repositorio)

    async def _sin_receptor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(evaluation, "get_target_for_user", _sin_receptor)

    async def _preflight_bloqueado(**_kwargs):
        return {
            "technical_blockers": ["LIGANDO_INVALIDO"],
            "input_fingerprint": "sha256:" + "a" * 64,
        }

    monkeypatch.setattr(evaluation, "evaluation_preflight", _preflight_bloqueado)

    peticion = evaluation.EvaluationSubmitRequest(
        smiles="CC(=O)Oc1ccccc1C(=O)O",
        target_pdb_id="7E2Y",
        preflight_fingerprint="sha256:" + "a" * 64,
    )

    with pytest.raises(HTTPException) as error:
        await evaluation.evaluate_sync(
            data=peticion, request=_request(), current_user=None, db=None
        )

    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_el_dueno_de_la_tarea_queda_registrado_antes_de_ejecutar(monkeypatch):
    """De este registro dependen `status`, `stream` y `cancel`."""
    repositorio = _Repositorio()
    monkeypatch.setattr(evaluation, "Repository", lambda _db: repositorio)

    async def _sin_receptor(*_args, **_kwargs):
        return None

    monkeypatch.setattr(evaluation, "get_target_for_user", _sin_receptor)

    usuario = SimpleNamespace(id=uuid.uuid4())
    peticion = evaluation.EvaluationSubmitRequest(smiles="CC(=O)Oc1ccccc1C(=O)O", target_pdb_id="7E2Y")

    respuesta = await evaluation.evaluate_sync(
        data=peticion, request=_request(), current_user=usuario, db=None
    )

    assert repositorio.consultas_de_cuota == 0
    assert respuesta.media_type == "text/event-stream"
