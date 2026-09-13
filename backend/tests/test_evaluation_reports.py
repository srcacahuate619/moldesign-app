"""Contratos del subrouter de reportes IA extraído en C-09."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from api.routers import evaluation_reports


class _Database:
    def __init__(self, molecule):
        self.molecule = molecule

    async def get(self, _model, _molecule_id):
        return self.molecule


class _Repository:
    def __init__(self, *, result, demo_user):
        self.result = result
        self.demo_user = demo_user

    async def get_evaluation_result(self, _molecule_id):
        return self.result

    async def get_or_create_test_user(self):
        return self.demo_user


def _cached_report_fixture(monkeypatch):
    molecule_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    molecule = SimpleNamespace(user_id=owner_id)
    repository = _Repository(
        result=SimpleNamespace(ai_report="Reporte en cache."),
        demo_user=SimpleNamespace(id=uuid.uuid4()),
    )
    monkeypatch.setattr(evaluation_reports, "Repository", lambda _db: repository)
    return molecule_id, SimpleNamespace(id=owner_id), _Database(molecule)


@pytest.mark.asyncio
async def test_cached_sync_and_sse_reports_keep_their_response_contract(monkeypatch):
    molecule_id, current_user, db = _cached_report_fixture(monkeypatch)

    # SlowAPI se prueba por integración; aquí verificamos el contrato propio
    # del handler sin requerir un Request ASGI completo.
    sync_response = await evaluation_reports.generate_ai_report_endpoint.__wrapped__(
        molecule_id,
        request=SimpleNamespace(),
        current_user=current_user,
        db=db,
    )
    stream_response = await evaluation_reports.generate_ai_report_stream_endpoint(
        molecule_id,
        current_user=current_user,
        db=db,
    )
    stream_chunks = [chunk async for chunk in stream_response.body_iterator]

    assert sync_response.ai_report == "Reporte en cache."
    assert stream_response.media_type == "text/event-stream"
    assert stream_chunks == ['data: "Reporte en cache."\n\n']


def test_report_routes_remain_under_evaluation_prefix_once():
    from api.routers.evaluation import router

    paths = [route.path for route in router.routes]
    for path in (
        "/evaluation/ai-report/{molecule_id}",
        "/evaluation/ai-report/{molecule_id}/stream",
    ):
        assert paths.count(path) == 1
