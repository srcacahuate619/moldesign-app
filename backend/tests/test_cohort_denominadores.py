"""
Los denominadores de una cohorte, dichos en voz alta.

Lo que protegen:

1. **Cada escalón del embudo se cuenta sobre el archivo COMPLETO**, no sobre el
   escalón anterior. Una cobertura del 100% sobre 2 de 40 moléculas es una
   cobertura del 5% del trabajo, y presentarla como completa sería mentir por
   omisión del denominador.

2. **Ninguna fila desaparece.** Fallidas, no evaluadas, excluidas en preflight y
   canceladas se cuentan con su causa. Un informe que sólo hablara de lo que
   salió bien no sería una cobertura.

3. **`not_evaluated` no es evidencia negativa.** Describe lo que le pasó al
   validador, nunca a la molécula.
"""

from __future__ import annotations

import uuid

import pytest

from services.cohort import evidence as cohort_ev
from services.cohort import execution as ex


class _Fila:
    """Fila de cohorte mínima. Sólo lo que `build_coverage` mira."""

    def __init__(self, indice, status, result_id=None, error_code=None, reused_from_row=None):
        self.id = uuid.uuid4()
        self.source_row_index = indice
        self.source_name = f"mol-{indice}"
        self.canonical_smiles = "CCO"
        self.status = status
        self.molecule_id = uuid.uuid4()
        self.result_id = result_id
        self.active_label = None
        self.control_role = "none"
        self.duplicate_of_row = None
        self.reused_from_row = reused_from_row
        self.error_code = error_code
        self.error_detail = None


class _Resultado:
    def __init__(self, poses=0, stage=None, selector=None):
        self.affinity_kcal = -8.0 if poses else None
        self.docking_poses = [
            {"rank": i + 1, "affinity": -8.0 + i} for i in range(poses)
        ]
        self.structural_evidence = (
            {"stage_status": stage, "poses_produced": poses, "poses_evaluated": poses}
            if stage else None
        )
        self.pose_selection = {"status": selector} if selector else None


class _Run:
    def __init__(self, total, elegibles):
        self.id = uuid.uuid4()
        self.total_rows = total
        self.eligible_rows = elegibles


@pytest.fixture
def cohorte():
    """
    8 filas de archivo, 6 elegibles. De las 6:
      · 3 completadas con poses (una passed, una review, una failed);
      · 1 completada sin poses;
      · 1 fallida;
      · 1 no evaluada.
    """
    ids = [uuid.uuid4() for _ in range(4)]
    resultados = {
        ids[0]: _Resultado(poses=3, stage="passed", selector="selected"),
        ids[1]: _Resultado(poses=3, stage="review", selector="abstained"),
        ids[2]: _Resultado(poses=2, stage="failed", selector="error"),
        ids[3]: _Resultado(poses=0, stage=None, selector=None),
    }
    filas = [
        _Fila(0, ex.ROW_COMPLETED, ids[0]),
        _Fila(1, ex.ROW_COMPLETED, ids[1]),
        _Fila(2, ex.ROW_COMPLETED, ids[2]),
        _Fila(3, ex.ROW_COMPLETED, ids[3]),
        _Fila(4, ex.ROW_FAILED, error_code="DOCKING_TIMEOUT"),
        _Fila(5, ex.ROW_NOT_EVALUATED, error_code="SA_FILTER_RECHAZO"),
    ]
    return _Run(total=8, elegibles=6), filas, resultados


def test_el_embudo_cuenta_cada_escalon_sobre_el_archivo_completo(cohorte):
    run, filas, resultados = cohorte
    cobertura = cohort_ev.build_coverage(run, filas, resultados)
    embudo = cobertura["structural_funnel"]

    assert embudo["input_rows"] == 8
    assert embudo["eligible_rows"] == 6
    assert embudo["executed_rows"] == 4
    # 3 filas conservaron poses; la cuarta completó sin ellas.
    assert embudo["rows_with_poses"] == 3
    # Seleccionable = el selector TENÍA con qué comparar (≥2 poses).
    assert embudo["selectable_rows"] == 3
    # Físicamente evaluadas: las que recibieron veredicto de verdad.
    assert embudo["physically_evaluated_rows"] == 3


def test_los_veredictos_fisicos_se_desglosan_uno_a_uno(cohorte):
    run, filas, resultados = cohorte
    veredictos = cohort_ev.build_coverage(run, filas, resultados)["structural_funnel"]["physical_verdicts"]

    assert veredictos["passed"] == 1
    assert veredictos["failed"] == 1
    assert veredictos["review"] == 1
    # La fila completada sin contrato cuenta como no evaluada, no como fallo.
    assert veredictos["not_evaluated"] == 1
    assert sum(veredictos.values()) == 4


def test_los_estados_del_selector_se_declaran_por_separado(cohorte):
    run, filas, resultados = cohorte
    selector = cohort_ev.build_coverage(run, filas, resultados)["structural_funnel"]["selector_states"]

    assert selector["selected"] == 1
    assert selector["abstained"] == 1
    assert selector["error"] == 1
    # Sin contrato = no disponible. Abstenerse y no existir no son lo mismo.
    assert selector["unavailable"] == 1


def test_ninguna_fila_desaparece_del_recuento(cohorte):
    run, filas, resultados = cohorte
    exclusiones = cohort_ev.build_coverage(run, filas, resultados)["exclusions"]

    por_causa = exclusiones["by_cause"]
    assert por_causa["DOCKING_TIMEOUT"] == 1
    assert por_causa["SA_FILTER_RECHAZO"] == 1
    # Las 2 filas que el preflight declaró no elegibles siguen contadas.
    assert por_causa["no_elegible_en_preflight"] == 2
    assert exclusiones["total"] == 4


def test_una_cohorte_sin_resultados_no_inventa_cobertura():
    """Sin resultados, todo es «no evaluado»: nunca «passed» por defecto."""
    run = _Run(total=3, elegibles=3)
    filas = [_Fila(i, ex.ROW_COMPLETED) for i in range(3)]

    embudo = cohort_ev.build_coverage(run, filas, {})["structural_funnel"]

    assert embudo["rows_with_poses"] == 0
    assert embudo["physically_evaluated_rows"] == 0
    assert embudo["physical_verdicts"]["passed"] == 0


def test_el_llamador_por_defecto_sigue_funcionando():
    """`resultados` es opcional: los llamadores antiguos no se rompen."""
    run = _Run(total=2, elegibles=2)
    cobertura = cohort_ev.build_coverage(run, [_Fila(0, ex.ROW_COMPLETED)])

    assert cobertura["structural_funnel"]["physically_evaluated_rows"] == 0
    assert cobertura["source_rows"] == 2


def test_el_embudo_declara_su_regla_de_denominador(cohorte):
    run, filas, resultados = cohorte
    nota = cohort_ev.build_coverage(run, filas, resultados)["structural_funnel"]["note"]

    assert "archivo COMPLETO" in nota
    # Y la frase que impide leer `not_evaluated` como evidencia negativa.
    assert "nunca a la molécula" in nota


def test_el_pdf_de_cohorte_imprime_el_embudo_y_las_exclusiones(cohorte):
    """El PDF no puede quedarse con los recuentos bonitos."""
    pypdf = pytest.importorskip("pypdf")
    import io as _io

    from services.cohort.dossier import render_cohort_dossier_pdf

    run, filas, resultados = cohorte
    evidencia = {
        "contract": "cohort_evidence/v1",
        "run_id": str(run.id),
        "cohort_id": str(uuid.uuid4()),
        "cohort_name": "Cohorte de prueba",
        "run_status": "completed",
        "sorted_by": "source_row_index",
        "cohort_fingerprint": "sha256:" + "a" * 64,
        "run_fingerprint": "sha256:" + "b" * 64,
        "effective_config": {"exhaustiveness": 8, "num_poses": 9, "seed": 42},
        "receptor": {"pdb_id": "7E2Y"},
        "coverage": cohort_ev.build_coverage(run, filas, resultados),
        "molecules": cohort_ev.build_molecule_evidence(filas, resultados),
        "labeled_metrics": {"status": "not_evaluated", "reason_code": "SIN_ETIQUETAS",
                            "reason": "El archivo no traía etiquetas."},
        "provenance": {"cohort": {}, "preflight_summary": None,
                       "execution_contract": "x", "evidence_contract": "y",
                       "stages": ["validation", "docking"]},
        "limits": ["Completar un acoplamiento no demuestra actividad."],
    }

    datos = render_cohort_dossier_pdf(evidencia).getvalue()
    assert datos.startswith(b"%PDF")
    texto = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(_io.BytesIO(datos)).pages)

    assert "Embudo estructural" in texto
    assert "Seleccionables" in texto
    assert "Físicamente evaluadas" in texto
    assert "Exclusiones y sus causas" in texto
    assert "DOCKING_TIMEOUT" in texto
    assert "no_elegible_en_preflight" in texto
    # Y la advertencia que impide leer «revisión» como aprobado.
    assert "no es una pose aprobada" in texto.lower()
