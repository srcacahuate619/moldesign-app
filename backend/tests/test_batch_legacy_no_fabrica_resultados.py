"""BATCH-SCI-001 — el batch heredado no inventa cifras ni mira las etiquetas.

Dos defectos que viajaban juntos en `/evaluation/batch`:

1. **Cifras fabricadas.** Una molécula saltada por el pre-filtro entraba en la
   tabla de resultados con ``total_score: 0`` y ``affinity_kcal: 0``. Nadie la
   acopló: ese cero no es una medida débil, es una medida que no existe. La
   tabla, el Excel exportado y cualquier lectura posterior la mostraban como si
   se hubiera calculado.

2. **Filtro dependiente de la etiqueta.** El pre-filtro sólo se aplicaba a las
   moléculas que NO venían marcadas como activas
   (``if early_exit and not mol.get("is_active")``). En un conjunto etiquetado,
   eso descarta señuelos usando la verdad que el benchmark pretende medir, y
   después se calculan EF y ROC-AUC sobre lo que quedó.

El pre-filtro sale del camino: es la misma decisión que en EVAL-SCI-002 —una
predicción de vecindad no sustituye al cálculo pedido—, y aquí además
contaminaba la métrica. El parámetro `early_exit` se conserva en el contrato,
pero la respuesta declara que no se aplicó.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from api.routers import batch as batch_mod
from tests.conftest import rdkit_available


ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"


def test_el_prefiltro_de_vecindad_ya_no_decide_que_se_acopla():
    fuente = (
        Path(__file__).resolve().parents[1] / "api/routers/batch.py"
    ).read_text(encoding="utf-8")

    assert "_check_early_exit(" not in fuente
    # La condición dependiente de la etiqueta desaparece con él.
    assert 'not mol.get("is_active")' not in fuente


def test_ninguna_fila_de_resultados_declara_un_score_sin_haberlo_calculado():
    fuente = (
        Path(__file__).resolve().parents[1] / "api/routers/batch.py"
    ).read_text(encoding="utf-8")

    assert '"total_score": 0,' not in fuente
    assert '"affinity_kcal": 0,' not in fuente


@rdkit_available
@pytest.mark.asyncio
async def test_una_molecula_con_vecinos_inactivos_se_acopla_igual(monkeypatch):
    """Aunque el grafo prediga inactividad, el batch la evalúa y la cuenta."""
    batch_id = str(uuid.uuid4())
    batch_mod._batches[batch_id] = {
        "id": batch_id, "targets": ["7E2Y"], "total": 2, "total_molecules": 2,
        "completed": 0, "failed": 0, "skipped_early_exit": 0, "invalid_input": 0,
        "status": "running", "results": [], "num_workers": 1, "early_exit": True,
        "has_labels": True, "ef_metrics": None,
    }

    evaluadas: list[str] = []

    async def _falsa_evaluacion(*_args, **kwargs):
        evaluadas.append(kwargs.get("smiles", ""))
        return {"molecule_id": str(uuid.uuid4()), "total_score": 60.0, "affinity_kcal": -7.5}

    def _prefiltro_agresivo(_smiles):  # pragma: no cover - no debe llamarse
        raise AssertionError("El pre-filtro de vecindad no puede seguir en el camino")

    import services.docking.queue_handler as qh

    monkeypatch.setattr(qh, "_run_full_evaluation_async", _falsa_evaluacion, raising=False)
    monkeypatch.setattr(
        "services.ai.molgraph.predict_early_exit", _prefiltro_agresivo, raising=False
    )

    try:
        await batch_mod._process_batch(
            batch_id,
            [
                {"smiles": ASPIRINA, "name": "aspirina", "original": ASPIRINA, "is_active": False},
                {"smiles": PARACETAMOL, "name": "paracetamol", "original": PARACETAMOL, "is_active": True},
            ],
            ["7E2Y"],
            num_workers=1,
            early_exit=True,
            has_labels=True,
        )
    finally:
        estado = batch_mod._batches.pop(batch_id)

    assert len(evaluadas) == 2
    assert estado["completed"] == 2
    assert estado["skipped_early_exit"] == 0
    # Ninguna fila puede ser un descarte disfrazado de resultado.
    assert all(fila.get("status") != "early_exit" for fila in estado["results"])


def test_la_respuesta_declara_que_el_prefiltro_no_se_aplica():
    """El cliente tiene que poder VER que el parámetro ya no filtra nada."""
    fuente = (
        Path(__file__).resolve().parents[1] / "api/routers/batch.py"
    ).read_text(encoding="utf-8")

    assert '"early_exit_enabled": False' in fuente


@pytest.fixture(autouse=True)
def _isolated_batch_checkpoints(monkeypatch):
    # These tests isolate API/scientific dispatch; real SQLite checkpoints are
    # covered by test_batch_persistence_hardening with temporary databases.
    from unittest.mock import AsyncMock
    from api.routers import batch
    monkeypatch.setattr(batch, "_persist_batch", AsyncMock())
    monkeypatch.setattr(batch, "_load_batch", AsyncMock(return_value=None))
