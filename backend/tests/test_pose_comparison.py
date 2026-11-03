"""La evidencia estructural y la comparación de dos poses, derivadas en el backend.

Lo que protegen, en orden de gravedad:

1. **El backend dice lo mismo que la pantalla.** `derive_structural_evidence` reproduce, escenario por escenario,
   la salida de `deriveStructuralEvidence` (TypeScript) guardada en el archivo dorado
   `backend/tests/data/pose_comparison_golden.json`. El archivo lo escribe el lado de TypeScript
   (`UPDATE_GOLDEN=1`); aquí sólo se exige. Si alguien cambia una regla en un lado, el otro falla.
2. **`review` y `not_evaluated` nunca son «válida».** Una comparación no llama válida a una pose que nadie midió.
3. **No se elige ganadora.** La diferencia dice cuál tiene la energía de Vina más baja y, aparte, qué dicen los
   controles físicos; nunca «mejor pose».
4. **Nada se inventa.** Un rango que la corrida no tiene sale `found: false`, sin diferencias.
"""
from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.routers import evaluation
from core.models import EvaluationResultRead, JobStatus
from services.evaluation.pose_comparison import (
    compare_two_poses,
    derive_structural_evidence,
    is_physically_valid,
)

GOLDEN = json.loads((Path(__file__).parent / "data" / "pose_comparison_golden.json").read_text(encoding="utf-8"))
SCENARIOS = {scenario["name"]: scenario for scenario in GOLDEN["scenarios"]}


def _result(name: str) -> dict:
    return copy.deepcopy(SCENARIOS[name]["result"])


# ── 1. Paridad con la pantalla ───────────────────────────────────────

@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_reproduce_la_derivacion_de_la_pantalla(name):
    expected = SCENARIOS[name]["expected"]
    assert expected is not None, "el archivo dorado no tiene `expected`: regenerarlo desde TypeScript"
    assert derive_structural_evidence(_result(name)) == expected


def test_el_guardian_ve_un_cambio_de_regla():
    """Control negativo: si una pose `review` contara como válida, el archivo dorado lo detecta."""
    result = _result("cobertura_parcial")
    result["structural_evidence"]["poses"][0]["status"] = "review"
    assert derive_structural_evidence(result) != SCENARIOS["cobertura_parcial"]["expected"]


def test_el_archivo_dorado_cubre_los_casos_que_importan():
    for name in ("todas_pasan", "todas_fallan", "sugerida_falla_con_alternativas", "cobertura_parcial",
                 "selector_se_abstiene", "corrida_anterior_sin_evidencia", "sin_semilla_ni_version"):
        assert name in SCENARIOS


# ── 2. Sólo `passed` es válida ───────────────────────────────────────

@pytest.mark.parametrize("status,valid", [("passed", True), ("review", False), ("failed", False),
                                          ("not_evaluated", False), (None, False), ("", False), ("PASSED", False)])
def test_solo_passed_es_fisicamente_valida(status, valid):
    assert is_physically_valid(status) is valid


def test_un_estado_desconocido_no_es_valido():
    view = derive_structural_evidence(_result("estado_de_etapa_desconocido"))
    assert view["physical"]["stage_status"] == "not_evaluated"
    assert view["decision"]["next_step"] == "review"


# ── 3. La comparación ────────────────────────────────────────────────

def test_compara_dos_poses_que_pasan():
    comparison = compare_two_poses(_result("todas_pasan"), 1, 2)
    assert comparison["left"]["found"] and comparison["right"]["found"]
    assert comparison["left"]["vina_affinity_kcal_mol"] == -8.3
    assert comparison["right"]["vina_affinity_kcal_mol"] == -7.9
    difference = dict(comparison["difference"])
    rmsd = difference.pop("vina_rmsd_between_poses")
    assert difference == {
        "right_minus_left_vina_kcal_mol": 0.4, "lower_vina_energy": 1,
        "physical_agreement": "both_passed", "within_near_tie": True,
    }
    # El archivo dorado no declara el motor ni una búsqueda única: sin eso no hay RMSD entre estas dos poses.
    assert rmsd["available"] is False and rmsd["reason_code"] == "ENGINE_NOT_DECLARED"
    assert comparison["left"]["is_vina_top1"] is True
    assert comparison["right"]["is_suggested"] is True
    assert comparison["right"]["selector_score"] == 0.52
    assert comparison["vina_top1_rank"] == 1


def test_la_comparacion_no_elige_ganadora_aunque_el_selector_sugiera_otra():
    comparison = compare_two_poses(_result("sugerida_falla_con_alternativas"), 1, 2)
    assert comparison["difference"]["lower_vina_energy"] == 1
    assert comparison["difference"]["physical_agreement"] == "only_left_passed"
    assert comparison["right"]["physical_status"] == "failed"
    assert comparison["right"]["failing_checks"] == ["internal_energy"]
    assert comparison["right"]["physically_valid"] is False
    assert comparison["selection"]["suggested_rank"] == 2
    assert comparison["selection"]["diverges_from_vina_top1"] is True
    assert comparison["decision"]["next_step"] == "review"
    assert "suggested_pose_not_passed" in comparison["decision"]["uncertainties"]
    # Nada sustituye a la sugerida: las alternativas se listan, no se eligen.
    assert comparison["decision"]["alternatives"] == [1, 3]
    assert not any("winner" in key or "best" in key for key in comparison["difference"])


def test_ninguna_de_las_dos_pasa():
    comparison = compare_two_poses(_result("todas_fallan"), 2, 3)
    assert comparison["difference"]["physical_agreement"] == "neither_passed"
    assert comparison["stage"]["status"] == "failed"
    assert comparison["decision"]["next_step"] == "abstain"


def test_una_pose_sin_evaluar_no_se_llama_valida():
    comparison = compare_two_poses(_result("cobertura_parcial"), 1, 3)
    assert comparison["right"]["physical_status"] == "not_evaluated"
    assert comparison["right"]["physically_valid"] is False
    assert (comparison["right"]["checks_passed"], comparison["right"]["checks_not_evaluated"]) == (1, 1)
    assert comparison["difference"]["physical_agreement"] == "only_left_passed"
    assert "partial_coverage" in comparison["decision"]["uncertainties"]


def test_una_pose_que_la_bateria_ni_listo_no_inventa_conteos_de_controles():
    comparison = compare_two_poses(_result("rangos_sin_pose_en_los_controles"), 1, 2)
    assert comparison["right"]["found"] is True
    assert comparison["right"]["physical_status"] == "not_evaluated"
    assert comparison["right"]["checks_passed"] is None
    assert comparison["right"]["checks_failed"] is None
    assert comparison["right"]["failing_checks"] == []


def test_el_orden_de_los_rangos_cambia_el_signo_y_no_el_veredicto():
    adelante = compare_two_poses(_result("todas_pasan"), 1, 3)["difference"]
    atras = compare_two_poses(_result("todas_pasan"), 3, 1)["difference"]
    assert adelante["right_minus_left_vina_kcal_mol"] == 2.2
    assert atras["right_minus_left_vina_kcal_mol"] == -2.2
    assert adelante["lower_vina_energy"] == 1 and atras["lower_vina_energy"] == 1
    assert adelante["within_near_tie"] is False and atras["within_near_tie"] is False


def test_el_casi_empate_se_declara_con_la_distancia_de_la_pantalla():
    comparison = compare_two_poses(_result("casi_empate"), 1, 2)
    assert comparison["difference"]["right_minus_left_vina_kcal_mol"] == 0.1
    assert comparison["difference"]["within_near_tie"] is True
    assert "near_tie" in comparison["decision"]["uncertainties"]


def test_dos_rangos_iguales_son_un_empate_exacto():
    difference = compare_two_poses(_result("todas_pasan"), 2, 2)["difference"]
    assert difference["right_minus_left_vina_kcal_mol"] == 0
    assert difference["lower_vina_energy"] == "equal"


def test_un_rango_que_la_corrida_no_tiene_no_inventa_diferencias():
    comparison = compare_two_poses(_result("todas_pasan"), 1, 7)
    assert comparison["right"] == {"rank": 7, "found": False}
    difference = dict(comparison["difference"])
    assert difference.pop("vina_rmsd_between_poses")["reason_code"] == "POSE_NOT_FOUND"
    assert difference == {
        "right_minus_left_vina_kcal_mol": None, "lower_vina_energy": None,
        "physical_agreement": "unavailable", "within_near_tie": None,
    }


def test_una_corrida_anterior_sin_evidencia_lo_declara_y_no_inventa_controles():
    comparison = compare_two_poses(_result("corrida_anterior_sin_evidencia"), 1, 2)
    assert comparison["legacy_run"] is True
    assert comparison["left"]["physical_status"] == "not_evaluated"
    assert comparison["left"]["physically_valid"] is False
    assert comparison["left"]["failing_checks"] == []
    assert comparison["selection"]["status"] == "unavailable"
    assert comparison["difference"]["physical_agreement"] == "neither_passed"
    assert "no_physical_validation" in comparison["decision"]["uncertainties"]


def test_el_selector_que_se_abstiene_no_deja_una_sugerida():
    comparison = compare_two_poses(_result("selector_se_abstiene"), 1, 2)
    assert comparison["selection"]["abstained"] is True
    assert comparison["selection"]["suggested_rank"] is None
    assert comparison["selection"]["would_have_suggested_rank"] == 2
    assert comparison["right"]["is_suggested"] is False


def test_sin_poses_no_hay_nada_que_comparar():
    comparison = compare_two_poses(_result("sin_poses_ni_evidencia"), 1, 2)
    assert comparison["left"]["found"] is False and comparison["right"]["found"] is False
    assert comparison["poses_produced"] == 0


@pytest.mark.parametrize("empty", [None, {}])
def test_un_resultado_vacio_no_rompe(empty):
    comparison = compare_two_poses(empty, 1, 2)
    assert comparison["difference"]["physical_agreement"] == "unavailable"
    assert derive_structural_evidence(empty)["has_anything"] is False


def test_las_cotas_de_rmsd_por_pose_son_las_que_vina_da_contra_su_mejor_pose():
    comparison = compare_two_poses(_result("todas_pasan"), 1, 2)
    assert (comparison["right"]["vina_rmsd_lb_vs_best"], comparison["right"]["vina_rmsd_ub_vs_best"]) == (1.1, 1.4)


def test_cada_pose_trae_sus_controles_fisicos_con_su_resultado():
    """«¿Qué controles superó cada pose?» se contesta con nombres, no con un recuento."""
    comparison = compare_two_poses(_result("sugerida_falla_con_alternativas"), 1, 2)
    assert comparison["left"]["checks_detail"] == [{"check": "sanitization", "result": "passed"},
                                                   {"check": "internal_energy", "result": "passed"}]
    assert comparison["right"]["checks_detail"] == [{"check": "sanitization", "result": "passed"},
                                                    {"check": "internal_energy", "result": "failed"}]
    parcial = compare_two_poses(_result("cobertura_parcial"), 1, 3)
    assert parcial["right"]["checks_detail"][1] == {"check": "internal_energy", "result": "not_evaluated"}


def test_un_estado_de_control_desconocido_no_se_lee_como_superado_y_sin_detalle_sale_vacio():
    result = _result("todas_pasan")
    result["structural_evidence"]["poses"][0]["checks"] = [{"check": "sanitization", "estado": "TAL VEZ"},
                                                           {"check": "", "estado": "PASA"}, {"estado": "PASA"}, "x"]
    assert compare_two_poses(result, 1, 2)["left"]["checks_detail"] == [{"check": "sanitization", "result": "unknown"}]
    del result["structural_evidence"]["poses"][1]["checks"]
    assert compare_two_poses(result, 1, 2)["right"]["checks_detail"] == []
    assert compare_two_poses(_result("corrida_anterior_sin_evidencia"), 1, 2)["left"]["checks_detail"] == []


#: Lo que la corrida real de 8T69 (clopidogrel) guardó del estado del ligando: dimorphite-dl a pH 7,4 protonó la amina.
_ESTADO_LIGANDO = {"smiles_entrada": "COC(=O)[C@H](c1ccccc1Cl)N1CCc2sccc2C1",
                   "smiles_acoplado": "COC(=O)[C@H](c1ccccc1Cl)[NH+]1CCc2sccc2C1", "cambio_respecto_a_la_entrada": True,
                   "protonacion": {"aplicada": True, "motor": "dimorphite-dl", "ph": 7.4, "alternativas": 2}}


def test_la_especie_acoplada_se_declara_sin_smiles_y_sin_inventar_lo_que_la_corrida_no_guardo():
    """Un puente salino sólo vale para la especie que se acopló: la comparación dice si no es la que se escribió."""
    result = _result("todas_pasan")
    result["ligand_state"] = copy.deepcopy(_ESTADO_LIGANDO)
    assert compare_two_poses(result, 1, 2)["ligand_species"] == {
        "available": True, "changed_from_input": True, "protonation_applied": True,
        "protonation_engine": "dimorphite-dl", "protonation_ph": 7.4, "alternatives_not_evaluated": 2}
    assert "NH+" not in json.dumps(compare_two_poses(result, 1, 2)["ligand_species"])
    sin_estado = compare_two_poses(_result("todas_pasan"), 1, 2)["ligand_species"]
    assert sin_estado == {"available": False, "reason_code": "LIGAND_STATE_NOT_STORED"}


def test_un_estado_del_ligando_malformado_no_se_lee_como_cambio_ni_como_ausencia_de_cambio():
    result = _result("todas_pasan")
    result["ligand_state"] = {"cambio_respecto_a_la_entrada": "si", "protonacion": {"ph": True, "alternativas": True, "motor": 7}}
    assert compare_two_poses(result, 1, 2)["ligand_species"] == {
        "available": True, "changed_from_input": None, "protonation_applied": None,
        "protonation_engine": None, "protonation_ph": None, "alternatives_not_evaluated": None}
    result["ligand_state"] = "no es un diccionario"
    assert compare_two_poses(result, 1, 2)["ligand_species"]["available"] is False


def _busqueda_unica(name: str = "todas_pasan") -> dict:
    """Una corrida de Vina de un solo conformador, como la de la pantalla (docking_protocol/v2)."""
    result = _result(name)
    result["docking_protocol"] = {"engine": "vina", "conformers_generated": 1, "conformers_requested": 1}
    return result


def test_con_la_mejor_pose_de_vina_las_cotas_de_la_otra_son_la_comparacion_entre_ambas():
    """Caso de la corrida real de 8T69: pose 1 (la mejor, RMSD 0) frente a pose 2 (2,251 / 4,259 Å)."""
    result = _busqueda_unica()
    result["docking_poses"][1]["rmsd_lb"], result["docking_poses"][1]["rmsd_ub"] = 2.251, 4.259
    for left, right, other in ((1, 2, 2), (2, 1, 2)):
        rmsd = compare_two_poses(result, left, right)["difference"]["vina_rmsd_between_poses"]
        assert rmsd == {"available": True, "reason_code": None, "reference_rank": 1, "other_rank": other,
                        "lower_bound_angstrom": 2.251, "upper_bound_angstrom": 4.259}


@pytest.mark.parametrize("cambio,codigo", [
    (lambda r: r.pop("docking_protocol"), "ENGINE_NOT_DECLARED"),
    (lambda r: r["docking_protocol"].update(engine="esmfold"), "ENGINE_NOT_VINA"),
    (lambda r: r["docking_protocol"].update(conformers_generated=8), "ENSEMBLE_RUN"),
    (lambda r: r["docking_protocol"].pop("conformers_generated"), "CONFORMERS_NOT_DECLARED"),
    (lambda r: r["docking_poses"][1].update(conformer_index=3), "ENSEMBLE_RUN"),
    (lambda r: r["docking_poses"][0].update(rmsd_lb=0.8, rmsd_ub=1.2), "REFERENCE_RMSD_NOT_ZERO"),
    (lambda r: r["docking_poses"][0].update(rmsd_lb=None), "REFERENCE_RMSD_NOT_ZERO"),
    (lambda r: r["docking_poses"][1].update(rmsd_ub=None), "RMSD_NOT_REPORTED"),
])
def test_fuera_de_una_busqueda_unica_de_vina_no_hay_rmsd_entre_las_dos_poses(cambio, codigo):
    """Controles negativos: conjunto de conformadores, otro motor o una referencia que no vale 0 no inventan la cota."""
    result = _busqueda_unica()
    cambio(result)
    rmsd = compare_two_poses(result, 1, 2)["difference"]["vina_rmsd_between_poses"]
    assert rmsd["available"] is False and rmsd["reason_code"] == codigo
    assert rmsd["lower_bound_angstrom"] is None and rmsd["upper_bound_angstrom"] is None


def test_dos_poses_que_no_son_la_mejor_no_tienen_rmsd_entre_ellas():
    """Las cotas de la pose 2 y de la 3 son contra la 1: no dicen cuánto se separan la 2 y la 3."""
    comparison = compare_two_poses(_busqueda_unica(), 2, 3)
    assert comparison["difference"]["vina_rmsd_between_poses"]["reason_code"] == "NEITHER_IS_VINA_BEST"
    assert (comparison["left"]["vina_rmsd_lb_vs_best"], comparison["right"]["vina_rmsd_lb_vs_best"]) == (1.1, 2.1)


def test_una_pose_comparada_consigo_misma_o_ausente_no_tiene_rmsd():
    result = _busqueda_unica()
    assert compare_two_poses(result, 1, 1)["difference"]["vina_rmsd_between_poses"]["reason_code"] == "SAME_POSE"
    assert compare_two_poses(result, 1, 99)["difference"]["vina_rmsd_between_poses"]["reason_code"] == "POSE_NOT_FOUND"


def test_un_booleano_o_una_cadena_vacia_no_son_numeros():
    result = _result("todas_pasan")
    result["vina_random_seed"] = True
    result["structural_evidence"]["poses_evaluated"] = ""
    view = derive_structural_evidence(result)
    assert view["generation"]["seed"] is None
    assert "no_seed" in view["decision"]["uncertainties"]
    assert view["physical"]["poses_evaluated"] == 0


# ── 4. El endpoint ───────────────────────────────────────────────────

def _request():
    return Request({
        "type": "http", "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": "/evaluation/pose-comparison/task-1", "raw_path": b"/evaluation/pose-comparison/task-1",
        "query_string": b"", "headers": [], "client": ("127.0.0.1", 43210), "server": ("testserver", 80),
    })


def _read_model(name: str) -> EvaluationResultRead:
    payload = {key: None for key, field in EvaluationResultRead.model_fields.items() if field.is_required()}
    payload.update(id=str(uuid.uuid4()), molecule_id=str(uuid.uuid4()), evaluated_at="2026-08-24T10:00:00+00:00")
    payload.update(_result(name))
    return EvaluationResultRead.model_validate(payload)


@pytest.fixture
def servir(monkeypatch):
    """Instala una corrida que el endpoint puede leer, sin base de datos ni cola."""
    autorizadas: list[str] = []

    async def authorize(task_id, *_args, **_kwargs):
        autorizadas.append(task_id)

    monkeypatch.setattr(evaluation, "_authorize_task_access", authorize)

    def install(status):
        async def get_job_status(task_id):
            return status

        monkeypatch.setattr("services.docking.queue_handler.get_job_status", get_job_status)

    install.autorizadas = autorizadas
    return install


async def _call(left=1, right=2):
    return await evaluation.get_pose_comparison(
        "task-1", _request(), left=left, right=right, current_user=SimpleNamespace(id=uuid.uuid4()), db=object())


@pytest.mark.asyncio
async def test_el_endpoint_autoriza_la_corrida_y_compara_el_resultado_persistido(servir):
    model = _read_model("sugerida_falla_con_alternativas")
    servir(JobStatus(task_id="task-1", status="SUCCESS", progress=100, result=model))
    comparison = await _call(1, 2)
    assert servir.autorizadas == ["task-1"]
    assert comparison["difference"]["physical_agreement"] == "only_left_passed"
    assert comparison["right"]["failing_checks"] == ["internal_energy"]
    # Lo mismo que la derivación directa: el endpoint sólo añade los identificadores de la corrida y la distancia
    # entre las dos poses, que sale de las coordenadas guardadas (esta corrida de prueba no guarda un SDF).
    medido = comparison["difference"].pop("pose_rmsd_between_poses")
    assert medido["available"] is False and medido["reason_code"] == "POSES_NOT_AVAILABLE"
    assert comparison == {"task_id": "task-1", "molecule_id": str(model.molecule_id),
                          **compare_two_poses(model.model_dump(mode="json"), 1, 2)}


@pytest.mark.asyncio
async def test_el_endpoint_entrega_la_especie_que_la_corrida_acoplo(servir):
    model = _read_model("todas_pasan")
    model.ligand_state = copy.deepcopy(_ESTADO_LIGANDO)
    servir(JobStatus(task_id="task-1", status="SUCCESS", progress=100, result=model))
    species = (await _call(1, 2))["ligand_species"]
    assert species["changed_from_input"] is True and species["protonation_ph"] == 7.4 and species["alternatives_not_evaluated"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [
    JobStatus(task_id="task-1", status="STARTED", progress=40, result=None),
    JobStatus(task_id="task-1", status="FAILURE", progress=100, result=None, error="falló"),
    JobStatus(task_id="task-1", status="SUCCESS", progress=100, result=None),
])
async def test_sin_resultado_terminado_responde_409(servir, status):
    servir(status)
    with pytest.raises(HTTPException) as error:
        await _call()
    assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("left,right", [(0, 2), (1, 0), (-1, 2), (1, 101)])
async def test_un_rango_fuera_de_limites_responde_422_antes_de_leer_nada(servir, left, right):
    servir(None)
    with pytest.raises(HTTPException) as error:
        await _call(left, right)
    assert error.value.status_code == 422
    assert servir.autorizadas == []
