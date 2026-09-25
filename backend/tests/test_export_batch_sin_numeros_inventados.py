"""ORQ-003: CSV y Excel distinguen cero medido de ausencia."""
from __future__ import annotations

import csv
import io

import pytest
from openpyxl import load_workbook

from api.routers import batch as batch_router


def _cliente(monkeypatch):
    resultados = [
        {"name": "fallida", "smiles": "c1ccccc1", "target": "1CBS",
         "status": "failed", "error": "SA > 7"},
        {"name": "etanol", "smiles": "CCO", "target": "1CBS",
         "status": "success", "total_score": 55.2, "affinity_kcal": -6.1,
         "molecular_weight": 46.1, "log_p": 0.0, "tpsa": 20.2,
         "ghose_pass": True, "egan_pass": False, "fsp3": 1.0,
         "adme_score": 44.0, "is_pains": False},
    ]

    async def get_batch(_id):
        return {"owner_id": "demo", "status": "completed",
                "results": resultados, "targets": ["1CBS"]}

    monkeypatch.setattr(batch_router, "_get_batch", get_batch)
    return batch_router


async def _contenido(response) -> bytes:
    partes = []
    async for parte in response.body_iterator:
        partes.append(parte.encode("utf-8") if isinstance(parte, str) else parte)
    return b"".join(partes)


@pytest.mark.asyncio
async def test_csv_no_fabrica_afinidad_y_copia_fsp3(monkeypatch):
    modulo = _cliente(monkeypatch)
    response = await modulo.export_batch_csv("test", current_user=None)
    rows = list(csv.DictReader(io.StringIO((await _contenido(response)).decode("utf-8"))))
    assert rows[0]["Name"] == "etanol"
    assert rows[0]["Fsp3"] == "1.0"
    assert rows[0]["ADME_Score"] == "44.0"
    assert rows[0]["LogP"] == "0.0"
    assert rows[1]["Status"] == "failed"
    assert rows[1]["Error"] == "SA > 7"
    assert rows[1]["Affinity_kcal"] == ""
    assert rows[1]["Ghose"] == ""


@pytest.mark.asyncio
async def test_excel_no_fabrica_afinidad(monkeypatch):
    modulo = _cliente(monkeypatch)
    response = await modulo.export_batch_excel("test", current_user=None)
    workbook = load_workbook(io.BytesIO(await _contenido(response)), read_only=True)
    rows = list(workbook.active.values)
    data = [dict(zip(rows[0], row)) for row in rows[1:]]
    assert data[0]["Fsp3"] == 1.0
    assert data[0]["ADME_Score"] == 44.0
    assert data[1]["Status"] == "failed"
    assert data[1]["Affinity_kcal"] is None
    workbook.close()
