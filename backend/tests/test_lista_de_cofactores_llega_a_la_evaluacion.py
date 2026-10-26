"""La lista de cofactores declarada llega a la evaluación (MET-01, 2026-10-11).

`cofactors_whitelist` es una lista de códigos de residuo (`["ZN"]`). El runner,
la cola y la comprobación previa la leían con `_coerce_hotspots`, que sólo
conserva dicts: la lista quedaba vacía y la evaluación volvía a preparar el
receptor sin el metal. MET-01 lo midió con Vina real sobre 1BN1: la variante
creada con `["ZN"]` tenía el receptor `e23dabe7…` y las seis tentativas CON
acoplaron el de la variante sin ion (`96e0aa31…`). Desde el 2026-08-13 ninguna
evaluación individual conservaba lo declarado; Lotes, que congela su receptor
por otro camino, sí.

Estas pruebas ejecutan el runner y el endpoint reales con dobles sólo para la
base de datos, y fallan con la lectura anterior.
"""
from __future__ import annotations

import types
import uuid
from contextlib import asynccontextmanager

import pytest

from core.models import _coerce_cofactores, _coerce_hotspots
from tests.conftest import rdkit_available


@pytest.mark.parametrize(
    "guardado, esperado",
    [
        (["ZN"], ["ZN"]),
        (["ZN", "MG"], ["ZN", "MG"]),
        ('["ZN", "MG"]', ["ZN", "MG"]),  # la columna JSON de SQLite puede llegar como texto
        (["zn", " ZN ", "hem"], ["ZN", "HEM"]),
        ([{"name": "HEM"}], ["HEM"]),
        ([], []),
        (None, []),
        ("", []),
        (["", None, 3], []),
    ],
)
def test_coerce_cofactores_conserva_los_codigos(guardado, esperado):
    assert _coerce_cofactores(guardado) == esperado


def test_la_lectura_de_hotspots_vaciaba_la_lista():
    """El mecanismo del fallo, fijado: por eso la lista no puede leerse como hotspots."""
    assert _coerce_hotspots(["ZN"]) == []


class _Parada(Exception):
    """Corta el runner justo después de congelar los parámetros de la corrida."""


def _diana(cofactores) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        pdb_id="USR_MET01", name="variante con zinc", chain="A", site_chains=["A"],
        structural_family=None, is_hot=False,
        grid_center_x=0.0, grid_center_y=0.0, grid_center_z=0.0,
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
        hotspots=[], hotspots_source=None, cofactors_whitelist=cofactores,
        affinity_threshold=-7.0, specificity_floor=0.5, spearman_rho=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("guardado", [["ZN"], '["ZN"]'])
async def test_el_runner_congela_la_lista_declarada(monkeypatch, guardado):
    from core.pipeline_params import PipelineParams
    from services.docking import queue_handler
    from services.pipeline import runner

    @asynccontextmanager
    async def _sesion():
        yield object()

    async def _diana_resuelta(_repo, _db, _pdb_id):
        return _diana(guardado)

    async def _molecula(**kwargs):
        return uuid.uuid4(), kwargs["smiles"], "0" * 64

    async def _nada(*_a, **_k):
        return None

    capturado: dict = {}

    def _congelar(cls, **kwargs):
        capturado.update(kwargs)
        raise _Parada

    monkeypatch.setattr(runner, "get_db_session", _sesion)
    monkeypatch.setattr(runner, "Repository", lambda db: object())
    monkeypatch.setattr(runner, "resolve_execution_target", _diana_resuelta)
    monkeypatch.setattr(runner, "_quick_get_or_create_molecule", _molecula)
    monkeypatch.setattr(runner, "commit_with_retry", _nada)
    monkeypatch.setattr(runner, "_run_mini_tx", _nada)
    monkeypatch.setattr(queue_handler, "register_job_molecule", lambda *_a: None)
    monkeypatch.setattr(PipelineParams, "from_orm", classmethod(_congelar))

    with pytest.raises(_Parada):
        await runner.run_pipeline(
            task_id=str(uuid.uuid4()), smiles="CCO", target_pdb_id="USR_MET01",
            user_id=str(uuid.uuid4()),
        )

    assert capturado["target_cofactors_whitelist"] == ["ZN"]


@pytest.mark.asyncio
@rdkit_available
async def test_la_comprobacion_previa_declara_la_lista_de_la_diana(monkeypatch):
    from api.routers import evaluation

    duenio = uuid.uuid4()
    diana = types.SimpleNamespace(
        id=uuid.uuid4(), pdb_id="USR_MET01", chain="A", is_private=True,
        is_community=False, creator_id=duenio,
        grid_center_x=None, grid_center_y=None, grid_center_z=None,
        grid_size_x=None, grid_size_y=None, grid_size_z=None,
        hotspots=None, cofactors_whitelist=["ZN"], site_chains=None, site_ligand=None,
        spearman_rho=None, structural_family=None, is_prepared=False,
    )

    class _Repositorio:
        def __init__(self, _db) -> None:
            pass

        async def get_target_by_pdb_id(self, pdb_id):
            return diana if str(pdb_id).strip().upper() == "USR_MET01" else None

    monkeypatch.setattr(evaluation, "Repository", _Repositorio)

    report = await evaluation.evaluation_preflight(
        data=evaluation.PreflightRequest(smiles="CCO", target_pdb_id="USR_MET01"),
        db=object(),
        current_user=types.SimpleNamespace(id=duenio),
    )

    politica = report["effective_config"]["heteroatom_policy"]
    assert politica["cofactors_whitelist_declared"] == ["ZN"]
