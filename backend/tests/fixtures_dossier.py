"""
Fixtures compartidos del dossier: un caso completo y uno parcial.

Los dos son deliberados. El COMPLETO ejercita el camino feliz; el PARCIAL es el
que descubre los defectos de verdad: textos largos que parten tablas, campos
ausentes que no deben convertirse en «pasa», y una corrida que ya no
corresponde a los inputs del caso.

Se comparten entre las pruebas y el generador de QA visual para que lo que se
inspecciona a ojo sea exactamente lo que se prueba.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any

from core.models import EvaluationResultORM, MoleculeORM, TargetORM
from services.dossier.schemas import CaseProjection

RELOJ = datetime.datetime(2026, 8, 24, 12, 0, 0, tzinfo=datetime.timezone.utc)

_HUELLA = "sha256:" + "a1b2c3d4" * 8
_HUELLA_VIEJA = "sha256:" + "9f8e7d6c" * 8


def target_completo() -> TargetORM:
    return TargetORM(
        pdb_id="7E2Y",
        name="Receptor 5-HT1A acoplado a proteína G",
        chain="R",
        grid_center_x=103.03, grid_center_y=114.79, grid_center_z=108.36,
        grid_size_x=25.0, grid_size_y=25.0, grid_size_z=25.0,
        is_prepared=True,
        hotspots=[{"name": f"R:RES{i}", "importance": 0.5} for i in range(6)],
        spearman_rho=0.512,
    )


def molecula() -> MoleculeORM:
    mol = MoleculeORM(smiles="CC(=O)Oc1ccccc1C(=O)O", name="Aspirina", smiles_hash="d" * 64)
    mol.id = uuid.UUID("11111111-2222-4333-8444-555555555555")
    return mol


def resultado_completo() -> EvaluationResultORM:
    """Corrida con poses, trazas y un índice heredado que debe ir al apéndice."""
    return EvaluationResultORM(
        molecule_id=molecula().id,
        affinity_kcal=-9.42,
        affinity_score=87.3,
        total_score=84.5,
        adme_score=79.0,
        druglikeness_score=81.0,
        docking_poses=[
            {"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0,
             "pdbqt_block": "MODEL 1\nREMARK VINA RESULT: -9.5 0 0\nENDMDL\n"},
            {"rank": 2, "affinity": -8.1, "rmsd_lb": 1.2, "rmsd_ub": 1.9,
             "pdbqt_block": "MODEL 2\nREMARK VINA RESULT: -8.1 1.2 1.9\nENDMDL\n"},
            {"rank": 3, "affinity": -7.4, "rmsd_lb": 2.1, "rmsd_ub": 3.3,
             "pdbqt_block": "MODEL 3\nREMARK VINA RESULT: -7.4 2.1 3.3\nENDMDL\n"},
        ],
        poses_file_path="poses/abc/7E2Y/poses.sdf",
        parsing_source="sdf",
        vina_version="1.2.5",
        vina_random_seed=42,
        engine_used="vina",
        model_used="model_a_universal",
        in_applicability_domain=True,
        molecular_weight=180.16, log_p=1.4, tpsa=63.6, hbd=1, hba=4,
        rotatable_bonds=3, qed=0.93, sa_score=1.9,
        # ── Los dos contratos de P0-A y P0-B ─────────────────────────
        # Un fixture «completo» sin ellos dejó de ser completo: desde esas dos
        # etapas, toda corrida de producción los persiste. La pose sugerida es
        # la #2 y FALLA los controles, a propósito: es el caso que el dossier
        # tiene que saber contar sin sustituirla por otra.
        structural_evidence={
            "version_schema": 1,
            "stage_status": "review",
            "reason_code": None,
            "detail": None,
            "pose_strategy": "vina_top1",
            "primary_pose_rank": 1,
            "poses_produced": 3,
            "poses_evaluated": 3,
            "coverage": 1.0,
            "receptor_sha256": "e" * 64,
            "receptor_source": "targets/7E2Y/prepared.pdbqt",
            "validation_engine": "posebusters:1.0:dock",
            "evaluated_at": "2026-08-24T09:31:00+00:00",
            "poses": [
                {"rank": 1, "observed_vina_affinity_kcal_mol": -9.5, "status": "passed",
                 "label": "CONTROLES SUPERADOS", "engine": "posebusters:1.0:dock",
                 "checks": [{"check": "sanitization", "estado": "PASA"},
                            {"check": "internal_energy", "estado": "PASA"}],
                 "checks_que_fallan": [], "detail": "Ningun control falla.",
                 "reason_code": None},
                {"rank": 2, "observed_vina_affinity_kcal_mol": -8.1, "status": "failed",
                 "label": "CONTROLES FALLIDOS", "engine": "posebusters:1.0:dock",
                 "checks": [{"check": "sanitization", "estado": "PASA"},
                            {"check": "internal_energy", "estado": "FALLA"}],
                 "checks_que_fallan": ["internal_energy"],
                 "detail": "Falla 1 control de quimica o geometria: internal_energy.",
                 "reason_code": None},
                {"rank": 3, "observed_vina_affinity_kcal_mol": -7.4, "status": "passed",
                 "label": "CONTROLES SUPERADOS", "engine": "posebusters:1.0:dock",
                 "checks": [{"check": "sanitization", "estado": "PASA"},
                            {"check": "internal_energy", "estado": "PASA"}],
                 "checks_que_fallan": [], "detail": "Ningun control falla.",
                 "reason_code": None},
            ],
        },
        pose_selection={
            "version_schema": 1,
            "contract": "pose_selection/v1",
            "status": "selected",
            "strategy": "pose_selector_v06",
            "strategy_is_fallback": False,
            "vina_top1_rank": 1,
            "selected_pose_rank": 2,
            "confidence": 0.412233,
            "abstained": False,
            "abstention_reason": None,
            "detail": "El selector recomienda la pose 2 con un margen de 0.412233.",
            "pose_scores": [{"rank": 1, "score": 0.11}, {"rank": 2, "score": 0.52},
                            {"rank": 3, "score": 0.09}],
            "model": {"name": "pose_selector_v06", "version": "pose_selector_v06",
                      "model_path": "pose_selector_v06.xgb",
                      "model_sha256": "b" * 64, "meta_sha256": "c" * 64,
                      "abstention_threshold": 0.097663},
            "inputs": {"n_poses": 3, "pose_ranks": [1, 2, 3],
                       "vina_affinities": [-9.5, -8.1, -7.4],
                       "pose_pdbqt_source": "docking_poses[].pdbqt_block",
                       "receptor_source": "prepared.pdb",
                       "structural_evidence_contract": 1},
            "warnings": [],
            "suggested_pose_physical_status": "failed",
            "physical_review": True,
            "physically_valid_alternatives": [{"rank": 1, "physical_status": "passed"},
                                              {"rank": 3, "physical_status": "passed"}],
            "evaluated_at": "2026-08-24T09:32:00+00:00",
        },
        task_id="task-completa-0001",
        evaluated_at=datetime.datetime(2026, 8, 24, 9, 30, tzinfo=datetime.timezone.utc),
    )


def resultado_parcial() -> EvaluationResultORM:
    """
    Corrida sin poses, sin trazas, fuera de dominio y con fallback.

    Es el fixture que impide el peor defecto: que la ausencia de datos se lea
    como validez.
    """
    return EvaluationResultORM(
        molecule_id=molecula().id,
        affinity_kcal=None,
        docking_poses=[],
        parsing_source=None,
        vina_version=None,
        vina_random_seed=None,
        engine_used="vina",
        model_used=None,
        in_applicability_domain=False,
        fallback_reason="El rescoring GNN no cargó; se conservó la energía cruda de Vina.",
        scientific_warnings=[
            "El grid no fue validado contra un ligando co-cristalizado.",
            "La cadena seleccionada no contiene los residuos de referencia del catálogo.",
        ],
        error_message="El pipeline terminó sin serializar poses.",
        task_id="task-parcial-0002",
        evaluated_at=datetime.datetime(2026, 8, 24, 10, 15, tzinfo=datetime.timezone.utc),
    )


def proyeccion_completa() -> CaseProjection:
    return CaseProjection.model_validate({
        "projection_version": 1,
        "case_id": "caso-serie-a-001",
        "case_schema_version": 3,
        "name": "Serie A · exploración del bolsillo ortostérico",
        "created_at": "2026-08-20T08:00:00+00:00",
        "context": {
            "study_kind": "explore-hypothesis",
            "question": "¿El andamio de la serie A tolera un sustituyente polar en la posición 4 sin perder el anclaje al bolsillo ortostérico?",
            "decision": "Decidir si se sintetizan los tres análogos polares o si la serie se abandona a favor del andamio B.",
            "system_rationale": "7E2Y es la única estructura con el receptor en conformación activa y con densidad interpretable en el bolsillo.",
            "controls": "Redock del ligando cristalográfico y un negativo conocido de la misma serie.",
            "assumptions": "Se asume el receptor rígido y protonación estándar a pH 7.4.",
            "uncertainties": "No se conoce el efecto de las aguas estructurales del bolsillo.",
            "notes": "Serie heredada del proyecto anterior.",
        },
        "inputs": {
            "receptor": {"pdb_id": "7E2Y", "chain": "R", "origin": "curado",
                         "name": "Receptor 5-HT1A", "target_id": "t-7e2y"},
            "ligand": {"input_smiles": "CC(=O)Oc1ccccc1C(=O)O",
                       "canonical_smiles": "CC(=O)Oc1ccccc1C(=O)O", "name": "Aspirina"},
            "config": {"grid_center": [103.03, 114.79, 108.36], "grid_size": [25.0, 25.0, 25.0],
                       "custom_hotspots": ["R:TYR390", "R:ASP116"], "docking_engine": "vina",
                       "exhaustiveness": 8, "num_poses": 9, "seed": 42},
        },
        "preflight": {
            "fingerprint": _HUELLA,
            "generated_at": "2026-08-24T09:00:00+00:00",
            "schema_version": 1,
            "execution_route": "docking_vina",
            "blockers": [],
            "warnings": ["ESPECIES_DEL_SITIO_RETIRADAS"],
            "not_evaluated": ["ASSEMBLY_BIOLOGICA", "HUECOS_CERCA_DEL_SITIO"],
            "receptor_label": "7E2Y · cadena R",
            "ligand_label": "CC(=O)Oc1ccccc1C(=O)O",
            "grid_label": "(103.03, 114.79, 108.36) · 25 Å",
        },
        "run": {"task_id": "task-completa-0001", "input_fingerprint": _HUELLA,
                "execution_state": "completed", "started_at": "2026-08-24T09:20:00+00:00"},
        "decisions": [{
            "control_code": "ESPECIES_DEL_SITIO_RETIRADAS",
            "fingerprint": _HUELLA,
            "decision": "reconocida",
            "at": "2026-08-24T09:10:00+00:00",
            "note": "Las especies retiradas son detergentes de cristalización, no del sitio.",
        }],
        "run_inputs_relation": "corresponde",
    })


def proyeccion_parcial() -> CaseProjection:
    """
    Caso con contexto MUY largo, sin decisiones y con la corrida desfasada.

    El texto largo es intencional: es lo que parte tablas y produce encabezados
    huérfanos, y no se descubre con un fixture corto.
    """
    largo = (
        "El objetivo de este caso es determinar si la sustitución en la posición 4 del anillo "
        "aromático central mantiene el patrón de puentes de hidrógeno observado en la estructura "
        "cristalográfica, considerando que el bolsillo presenta dos aguas estructurales cuya "
        "posición no se conserva entre las estructuras depositadas del mismo receptor, y que la "
        "política de preparación del producto elimina todas las aguas antes de acoplar, de modo "
        "que cualquier conclusión sobre puentes mediados por agua queda fuera del alcance de esta "
        "corrida y debe declararse como tal en cualquier lectura posterior del expediente. "
    ) * 3
    return CaseProjection.model_validate({
        "projection_version": 1,
        "case_id": "caso-parcial-002",
        "case_schema_version": 3,
        "name": "Caso parcial · corrida sin poses y con hipótesis desfasada",
        "context": {
            "study_kind": "prepare-evidence",
            "question": largo,
            "decision": None,
            "system_rationale": None,
            "controls": None,
            "assumptions": largo[:900],
            "uncertainties": None,
            "notes": None,
        },
        "inputs": {
            "receptor": {"pdb_id": "7E2Y", "chain": "R", "origin": "curado"},
            "ligand": {"input_smiles": "CC(=O)Oc1ccccc1C(=O)O"},
            "config": {"docking_engine": "vina"},
        },
        "preflight": {
            "fingerprint": _HUELLA,
            "execution_route": "docking_vina",
            "blockers": ["RECEPTOR_CADENA_PRESENTE"],
            "warnings": ["METALES_ELIMINADOS", "ESPECIES_DEL_SITIO_RETIRADAS"],
            "not_evaluated": ["ASSEMBLY_BIOLOGICA"],
        },
        # Huella distinta a la del preflight: la corrida es de otra hipótesis.
        "run": {"task_id": "task-parcial-0002", "input_fingerprint": _HUELLA_VIEJA,
                "execution_state": "completed", "last_error": "El pipeline terminó sin poses."},
        "decisions": [],
        "run_inputs_relation": "corresponde",  # el cliente se equivoca; el backend lo corrige
    })


def caso_completo() -> dict[str, Any]:
    return {
        "projection": proyeccion_completa(),
        "molecule": molecula(),
        "eval_result": resultado_completo(),
        "target": target_completo(),
        "generated_at": RELOJ,
    }


def caso_parcial() -> dict[str, Any]:
    return {
        "projection": proyeccion_parcial(),
        "molecule": molecula(),
        "eval_result": resultado_parcial(),
        "target": TargetORM(pdb_id="7E2Y", name="Receptor 5-HT1A", chain="R"),
        "generated_at": RELOJ,
    }


def resultado_selector_abstenido() -> EvaluationResultORM:
    """
    El selector midió y NO recomendó. La referencia es Vina top-1 como fallback.

    Es distinto de que el selector no existiera: aquí corrió, y su abstención es
    un resultado que el dossier tiene que declarar como tal.
    """
    resultado = resultado_completo()
    resultado.pose_selection = {
        **resultado.pose_selection,
        "status": "abstained",
        "strategy": "vina_top1",
        "strategy_is_fallback": True,
        "selected_pose_rank": None,
        "abstained": True,
        "abstention_reason": "MARGEN_BAJO_UMBRAL",
        "confidence": 0.021,
        "would_have_suggested_rank": 2,
        "suggested_pose_physical_status": None,
        "physical_review": None,
        "detail": "El margen entre la primera y la segunda no llega al umbral.",
    }
    resultado.task_id = "task-abstenida-0003"
    return resultado


def resultado_validacion_parcial() -> EvaluationResultORM:
    """Sólo una de las tres poses recibió veredicto: cobertura 1/3."""
    resultado = resultado_completo()
    resultado.structural_evidence = {
        **resultado.structural_evidence,
        "stage_status": "review",
        "poses_evaluated": 1,
        "coverage": round(1 / 3, 6),
        "reason_code": "MAPA_SIN_HIDROGENOS_POLARES",
        "poses": [
            resultado.structural_evidence["poses"][0],
            {"rank": 2, "observed_vina_affinity_kcal_mol": -8.1, "status": "not_evaluated",
             "label": "NO EVALUADA", "engine": None, "checks": [],
             "checks_que_fallan": [], "detail": None,
             "reason_code": "MAPA_SIN_HIDROGENOS_POLARES"},
            {"rank": 3, "observed_vina_affinity_kcal_mol": -7.4, "status": "not_evaluated",
             "label": "NO EVALUADA", "engine": None, "checks": [],
             "checks_que_fallan": [], "detail": None,
             "reason_code": "MAPA_SIN_HIDROGENOS_POLARES"},
        ],
    }
    resultado.pose_selection = {
        **resultado.pose_selection,
        "selected_pose_rank": 1,
        "suggested_pose_physical_status": "passed",
        "physical_review": False,
        "physically_valid_alternatives": [],
    }
    resultado.task_id = "task-parcial-fisica-0004"
    return resultado


def resultado_antiguo() -> EvaluationResultORM:
    """
    Corrida anterior a P0-A y P0-B: NINGUNO de los dos contratos existe.

    En la base de datos son NULL, y así se quedan: la migración es aditiva y no
    reescribe historia. El dossier tiene que leerlo como «no se ejecutó», nunca
    como un fallo de las poses.
    """
    resultado = resultado_completo()
    resultado.structural_evidence = None
    resultado.pose_selection = None
    resultado.task_id = "task-antigua-0005"
    return resultado


def caso_selector_abstenido() -> dict[str, Any]:
    return {**caso_completo(), "eval_result": resultado_selector_abstenido()}


def caso_validacion_parcial() -> dict[str, Any]:
    return {**caso_completo(), "eval_result": resultado_validacion_parcial()}


def caso_antiguo() -> dict[str, Any]:
    return {**caso_completo(), "eval_result": resultado_antiguo()}
