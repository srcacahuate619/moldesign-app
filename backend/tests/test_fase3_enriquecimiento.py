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
    # Las dos dianas puntúan en escalas distintas (-5 a -9 frente a -12 a -16): cada una se ordena por sí misma.
    rows = [
        {"name": "activo", "smiles": "CCO", "target": "A", "status": "success", "affinity_kcal": -9.0},
        {"name": "inactivo", "smiles": "CCC", "target": "A", "status": "success", "affinity_kcal": -5.0},
        {"name": "activo", "smiles": "CCO", "target": "B", "status": "success", "affinity_kcal": -16.0},
        {"name": "inactivo", "smiles": "CCC", "target": "B", "status": "success", "affinity_kcal": -12.0},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)
    assert result["por_diana"]["A"]["roc_auc"] == 1.0
    assert result["por_diana"]["B"]["roc_auc"] == 1.0
    assert result["roc_auc"] == 1.0
    assert result["aggregation"] == "mean_per_target"

    rows[2] = {**rows[2], "status": "failed", "error": "SA_ABORT", "affinity_kcal": None}
    failed = _compute_ef_metrics(rows, molecules, 0)
    assert failed["por_diana"]["B"]["n_total"] == 2
    assert failed["por_diana"]["B"]["excluidos"]["activos"] == 1
    assert failed["por_diana"]["B"]["excluidos"]["motivos"]["SA_ABORT"] == 1


def test_ef_se_ordena_por_la_afinidad_de_vina_y_no_por_el_indice_compuesto():
    """SUP-02: `total_score` no ordena mejor que Vina. Aquí el índice dice lo contrario que Vina, y manda Vina."""
    molecules = [
        {"name": "A", "smiles": "CCO", "is_active": True},
        {"name": "B", "smiles": "CCC", "is_active": False},
    ]
    # El activo tiene el peor índice compuesto y la mejor afinidad; el señuelo, al revés.
    rows = [
        {"name": "A", "smiles": "CCO", "target": "T", "status": "success", "affinity_kcal": -9.0,
         "total_score": 48, "affinity_score": 60, "stacking_degraded": False},
        {"name": "B", "smiles": "CCC", "target": "T", "status": "success", "affinity_kcal": -5.0,
         "total_score": 58, "affinity_score": 50, "stacking_degraded": False},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)
    assert result["por_diana"]["T"]["score_basis"] == "affinity_kcal"
    assert result["roc_auc"] == 1.0, "ordenó por el índice compuesto: con él el activo queda último"

    # Y al revés: si el índice dijera «perfecto» y Vina «pésimo», el resultado es el de Vina.
    invertidas = [{**rows[0], "affinity_kcal": -5.0, "total_score": 99}, {**rows[1], "affinity_kcal": -9.0, "total_score": 1}]
    assert _compute_ef_metrics(invertidas, molecules, 0)["roc_auc"] == 0.0


def test_la_base_de_ef_no_depende_de_los_pesos_del_apilado():
    """Antes cambiaba de `total_score` a `affinity_score` según si las filas mezclaban pesos: dos lotes, dos escalas."""
    molecules = [
        {"name": "A", "smiles": "CCO", "is_active": True},
        {"name": "B", "smiles": "CCC", "is_active": False},
    ]
    homogeneo = [
        {"name": "A", "smiles": "CCO", "target": "T", "status": "success", "affinity_kcal": -8.0, "stacking_degraded": False},
        {"name": "B", "smiles": "CCC", "target": "T", "status": "success", "affinity_kcal": -6.0, "stacking_degraded": False},
    ]
    mixto = [{**homogeneo[0]}, {**homogeneo[1], "stacking_degraded": True}]
    a, b = _compute_ef_metrics(homogeneo, molecules, 0), _compute_ef_metrics(mixto, molecules, 0)
    assert a["por_diana"]["T"]["score_basis"] == b["por_diana"]["T"]["score_basis"] == "affinity_kcal"
    assert a["roc_auc"] == b["roc_auc"] == 1.0


def test_una_afinidad_ausente_o_no_finita_cuenta_como_el_peor_score():
    molecules = [
        {"name": "A", "smiles": "CCO", "is_active": True},
        {"name": "B", "smiles": "CCC", "is_active": False},
        {"name": "C", "smiles": "CCCC", "is_active": False},
    ]
    rows = [
        {"name": "A", "smiles": "CCO", "target": "T", "status": "success", "affinity_kcal": float("nan")},
        {"name": "B", "smiles": "CCC", "target": "T", "status": "success", "affinity_kcal": -6.0},
        {"name": "C", "smiles": "CCCC", "target": "T", "status": "success", "affinity_kcal": None},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)["por_diana"]["T"]
    # El activo sin afinidad (peor score) pierde contra B y empata con C, que tampoco tiene: (0 + 0.5) / 2.
    assert result["roc_auc"] == 0.25
    assert result["excluidos"]["activos"] == 1 and result["excluidos"]["inactivos"] == 1


def test_batch_conserva_filas_identicas_con_etiquetas_distintas():
    molecules = [
        {"row_id": 0, "name": "misma", "smiles": "CCO", "is_active": True},
        {"row_id": 1, "name": "misma", "smiles": "CCO", "is_active": False},
    ]
    rows = [
        {"row_id": 0, "name": "misma", "smiles": "CCO", "target": "A",
         "status": "success", "affinity_kcal": -8.0, "stacking_degraded": False},
        {"row_id": 1, "name": "misma", "smiles": "CCO", "target": "A",
         "status": "success", "affinity_kcal": -4.0, "stacking_degraded": False},
    ]
    result = _compute_ef_metrics(rows, molecules, 0)
    assert result["n_total"] == 2
    assert result["roc_auc"] == 1.0
