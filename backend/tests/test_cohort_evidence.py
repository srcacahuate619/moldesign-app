"""
Evidencia, métricas y dossier de cohorte: qué se afirma y qué se abstiene.

Lo que protegen, en orden de gravedad:

1. **El resultado pertenece a ESTA ejecución.** `result_id` sale de lo que
   devolvió el pipeline, no de «el resultado más reciente de esta molécula».
   Buscar por molécula devolvería el de otra corrida y la evidencia describiría
   algo que no ocurrió.

2. **Las métricas se abstienen por defecto.** Sin etiquetas, sin positivos, sin
   negativos, con muestra corta o con etiquetas en conflicto: `not_evaluated`
   con razón estable. Un número calculado sin condiciones parece un resultado.

3. **Los duplicados no inflan nada.** Una molécula canónica es una observación,
   por muchas veces que aparezca en el archivo.

4. **El paquete es verificable con el MISMO verificador que el del caso.**
   Adulterar cualquier archivo —el manifiesto incluido— lo invalida.
"""

from __future__ import annotations

import json
import uuid
import zipfile

import pytest

from services.cohort import evidence as ev
from services.cohort import execution as ex


# ── Fábrica de evidencia sintética ───────────────────────────────────


def molecula(
    indice: int,
    *,
    smiles: str,
    afinidad: float | None = -8.0,
    activa: bool | None = None,
    control: str = "none",
    estado: str = ex.ROW_COMPLETED,
    reused_from: int | None = None,
) -> dict:
    return {
        "source_row_index": indice,
        "source_name": f"mol-{indice}",
        "canonical_smiles": smiles,
        "status": estado,
        "observed_vina_affinity_kcal_mol": afinidad,
        "molecule_id": str(uuid.uuid4()),
        "result_id": str(uuid.uuid4()),
        "active_label": activa,
        "control_role": control,
        "duplicate_of_row": None,
        "reused_from_row": reused_from,
        "error_code": None,
        "error_detail": None,
    }


def cohorte_etiquetada(n_activas: int, n_inactivas: int, **kwargs) -> list[dict]:
    """Cohorte con activas mejor acopladas que las inactivas, por construcción."""
    filas = []
    for i in range(n_activas):
        filas.append(molecula(len(filas), smiles=f"A{i}", afinidad=-10.0 + i * 0.1, activa=True, **kwargs))
    for i in range(n_inactivas):
        filas.append(molecula(len(filas), smiles=f"I{i}", afinidad=-6.0 + i * 0.1, activa=False, **kwargs))
    return filas


# ── 1. Métricas: abstenciones ────────────────────────────────────────


def test_sin_etiquetas_las_metricas_se_abstienen():
    filas = [molecula(i, smiles=f"M{i}") for i in range(20)]

    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)

    assert metricas["status"] == "not_evaluated"
    assert metricas["reason_code"] == ev.SIN_ETIQUETAS
    assert metricas["roc_auc"] is None
    assert metricas["enrichment_factors"] == []


def test_sin_positivos_o_sin_negativos_se_abstiene():
    solo_activas = ev.build_labeled_metrics(cohorte_etiquetada(15, 0), run_status=ex.RUN_COMPLETED)
    solo_inactivas = ev.build_labeled_metrics(cohorte_etiquetada(0, 15), run_status=ex.RUN_COMPLETED)

    assert solo_activas["reason_code"] == ev.SIN_NEGATIVOS
    assert solo_inactivas["reason_code"] == ev.SIN_POSITIVOS
    # Y aun absteniéndose, declara sus denominadores.
    assert solo_activas["n_total"] == 15
    assert solo_activas["n_positive"] == 15
    assert solo_activas["n_negative"] == 0


def test_una_muestra_corta_se_abstiene_en_vez_de_dar_un_numero():
    metricas = ev.build_labeled_metrics(cohorte_etiquetada(2, 2), run_status=ex.RUN_COMPLETED)

    assert metricas["reason_code"] == ev.MUESTRA_INSUFICIENTE
    assert str(ev.MIN_N_FOR_METRICS) in metricas["reason"]
    assert metricas["roc_auc"] is None


def test_sin_afinidad_no_hay_metrica():
    filas = cohorte_etiquetada(8, 8)
    for fila in filas:
        fila["observed_vina_affinity_kcal_mol"] = None

    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)

    assert metricas["reason_code"] == ev.SIN_AFINIDAD
    assert metricas["coverage"] == 0.0


def test_etiquetas_en_conflicto_entre_duplicados_abstienen():
    """
    Dos filas de la MISMA molécula canónica con etiquetas opuestas.

    No se elige una: no sabemos cuál es correcta, y elegir sería inventar la
    respuesta que la métrica después mediría.
    """
    filas = cohorte_etiquetada(8, 8)
    filas.append(molecula(99, smiles="A0", afinidad=-10.0, activa=False))

    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)

    assert metricas["reason_code"] == ev.ETIQUETAS_EN_CONFLICTO
    assert "A0" in metricas["conflicting_molecules"]


def test_una_corrida_a_medias_no_produce_metricas():
    metricas = ev.build_labeled_metrics(cohorte_etiquetada(8, 8), run_status=ex.RUN_RUNNING)

    assert metricas["reason_code"] == ev.CORRIDA_NO_TERMINAL


# ── 2. Métricas: cálculo y política de duplicados ────────────────────


def test_con_condiciones_cumplidas_se_calculan_ef_y_roc():
    metricas = ev.build_labeled_metrics(cohorte_etiquetada(10, 40), run_status=ex.RUN_COMPLETED)

    assert metricas["status"] == "evaluated"
    assert metricas["n_total"] == 50
    assert metricas["n_positive"] == 10
    assert metricas["n_negative"] == 40
    # Las activas están mejor acopladas por construcción: separación perfecta.
    assert metricas["roc_auc"] == 1.0
    assert metricas["coverage"] == 1.0
    assert [ef["fraction"] for ef in metricas["enrichment_factors"]] == [0.01, 0.05, 0.10]
    # EF@10% con separación perfecta y tasa base 0.2 → 1.0/0.2 = 5.0
    ef10 = next(ef for ef in metricas["enrichment_factors"] if ef["fraction"] == 0.10)
    assert ef10["value"] == 5.0
    # Y la métrica lleva su límite pegado, no en una nota al pie.
    assert "no es validación prospectiva" in metricas["interpretation_limit"].lower()


def test_los_duplicados_no_inflan_la_metrica():
    """La misma molécula diez veces sigue siendo UNA observación."""
    base = cohorte_etiquetada(10, 40)
    sin_duplicados = ev.build_labeled_metrics(base, run_status=ex.RUN_COMPLETED)

    # Se repite la mejor activa nueve veces más, como haría un archivo con
    # entradas repetidas.
    con_duplicados = list(base)
    for i in range(9):
        con_duplicados.append(
            molecula(100 + i, smiles="A0", afinidad=-10.0, activa=True,
                     estado=ex.ROW_DUPLICATE_REUSED, reused_from=0)
        )
    resultado = ev.build_labeled_metrics(con_duplicados, run_status=ex.RUN_COMPLETED)

    assert resultado["n_total"] == sin_duplicados["n_total"] == 50
    assert resultado["n_positive"] == sin_duplicados["n_positive"] == 10
    assert resultado["roc_auc"] == sin_duplicados["roc_auc"]
    assert resultado["enrichment_factors"] == sin_duplicados["enrichment_factors"]


def test_los_controles_se_reportan_aparte_y_no_entran_en_la_poblacion():
    filas = cohorte_etiquetada(10, 40)
    filas.append(molecula(200, smiles="REF", afinidad=-12.0, activa=True, control="reference"))
    filas.append(molecula(201, smiles="NEG", afinidad=-3.0, activa=False, control="negative"))

    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)

    # La población de la métrica sigue siendo la cohorte, sin los controles.
    assert metricas["n_total"] == 50
    # Y los controles están, con su afinidad, en su propia lista.
    roles = {c["control_role"] for c in metricas["controls"]}
    assert roles == {"reference", "negative"}
    assert len(metricas["controls"]) == 2


# ── 3. Cobertura y orden ─────────────────────────────────────────────


def test_el_orden_por_afinidad_observada_se_llama_exactamente_asi():
    assert ev.SORT_BY_OBSERVED_AFFINITY == "afinidad_vina_observada"

    filas = [
        molecula(0, smiles="A", afinidad=-6.0),
        molecula(1, smiles="B", afinidad=None, estado=ex.ROW_FAILED),
        molecula(2, smiles="C", afinidad=-9.5),
    ]

    ordenadas = ev.sort_by_observed_affinity(filas)

    # Más negativa primero; las que no tienen afinidad al final, conservando su
    # estado. No se les asigna un valor para poder colocarlas.
    assert [e["source_row_index"] for e in ordenadas] == [2, 0, 1]
    assert ordenadas[-1]["observed_vina_affinity_kcal_mol"] is None
    assert ordenadas[-1]["status"] == ex.ROW_FAILED


def test_ninguna_superficie_de_evidencia_habla_de_score_ni_de_mejores_farmacos():
    filas = cohorte_etiquetada(10, 40)
    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)
    plano = json.dumps({"molecules": filas, "labeled_metrics": metricas}).lower()

    for prohibido in ("total_score", "mejor fármaco", "mejores fármacos", "probabilidad",
                      "éxito", "candidato clínico"):
        assert prohibido not in plano
