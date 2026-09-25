"""EF independiente del orden de entrada y del cruce entre dianas."""
from __future__ import annotations

import pytest

from api.routers.batch import _compute_ef_metrics
from scoring.enriquecimiento import ef_fraccional, roc_auc_midrank


def test_todos_empatados_dan_ef_uno_cualquiera_sea_orden():
    scores = [0.0] * 100
    labels = [True] * 5 + [False] * 95
    a, _, _ = ef_fraccional(scores, labels, 0.01)
    b, _, _ = ef_fraccional(scores, list(reversed(labels)), 0.01)
    assert a == pytest.approx(1.0)
    assert b == pytest.approx(1.0)
    assert roc_auc_midrank(scores, labels) == 0.5


def test_batch_no_mezcla_dianas_y_cuenta_activo_fallido():
    molecules = [
        {"name": "activo", "smiles": "CCO", "is_active": True},
        {"name": "inactivo", "smiles": "CCC", "is_active": False},
    ]
    rows = [
        {"name": "activo", "smiles": "CCO", "target": "A", "status": "success",
         "total_score": 10, "affinity_score": 10, "stacking_degraded": False},
        {"name": "inactivo", "smiles": "CCC", "target": "A", "status": "success",
         "total_score": 0, "affinity_score": 0, "stacking_degraded": False},
        {"name": "activo", "smiles": "CCO", "target": "B", "status": "success",
         "total_score": 110, "affinity_score": 110, "stacking_degraded": False},
        {"name": "inactivo", "smiles": "CCC", "target": "B", "status": "success",
         "total_score": 100, "affinity_score": 100, "stacking_degraded": False},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)
    assert result["por_diana"]["A"]["roc_auc"] == 1.0
    assert result["por_diana"]["B"]["roc_auc"] == 1.0
    assert result["roc_auc"] == 1.0
    assert result["aggregation"] == "mean_per_target"

    rows[2] = {**rows[2], "status": "failed", "error": "SA_ABORT", "total_score": None}
    failed = _compute_ef_metrics(rows, molecules, 0)
    assert failed["por_diana"]["B"]["n_total"] == 2
    assert failed["por_diana"]["B"]["excluidos"]["activos"] == 1
    assert failed["por_diana"]["B"]["excluidos"]["motivos"]["SA_ABORT"] == 1


def test_lote_mixto_usa_senal_comun_para_ef():
    molecules = [
        {"name": "A", "smiles": "CCO", "is_active": True},
        {"name": "B", "smiles": "CCC", "is_active": False},
    ]
    rows = [
        {"name": "A", "smiles": "CCO", "target": "T", "status": "success",
         "total_score": 48, "affinity_score": 60, "stacking_degraded": False},
        {"name": "B", "smiles": "CCC", "target": "T", "status": "success",
         "total_score": 58, "affinity_score": 50, "stacking_degraded": True},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)
    assert result["por_diana"]["T"]["score_basis"] == "affinity_score"
    assert result["roc_auc"] == 1.0


def test_batch_conserva_filas_identicas_con_etiquetas_distintas():
    molecules = [
        {"row_id": 0, "name": "misma", "smiles": "CCO", "is_active": True},
        {"row_id": 1, "name": "misma", "smiles": "CCO", "is_active": False},
    ]
    rows = [
        {"row_id": 0, "name": "misma", "smiles": "CCO", "target": "A",
         "status": "success", "total_score": 80, "stacking_degraded": False},
        {"row_id": 1, "name": "misma", "smiles": "CCO", "target": "A",
         "status": "success", "total_score": 20, "stacking_degraded": False},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)
    assert result["n_total"] == 2
    assert result["roc_auc"] == 1.0
