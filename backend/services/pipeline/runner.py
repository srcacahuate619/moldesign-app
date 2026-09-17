from __future__ import annotations
import asyncio
from datetime import datetime, UTC
from typing import Any
import os

from core.models import MoleculeStatus, _coerce_hotspots
from core.database import (
    DB_WRITE_RETRY_DELAY,
    MAX_DB_WRITE_RETRIES,
    commit_with_retry,
    get_db_session,
)
from sqlalchemy.exc import SQLAlchemyError
from db.repository import Repository
from chem.properties import calculate_properties
from chem.conformer import generate_conformer


async def _generar_conformaciones(smiles: str, params_por_etapa) -> dict:
    """
    La etapa de generacion 3D, respetando el protocolo declarado.

    Con `conformers` = 1 —el defecto— delega en `generate_conformer` sin
    desviarse: es literalmente el mismo camino que corrio en todas las
    evaluaciones anteriores. Con K > 1 genera el ensemble.

    NUNCA lanza por el ensemble: si la generacion multiple falla, cae al
    conformero unico y lo declara. Perder la evaluacion entera porque la
    conformacion 17 de 30 no embebio seria un precio absurdo.
    """
    k = 1
    try:
        conf_params = (params_por_etapa or {}).get("conformer") or {}
        from chem.conformer_ensemble import normalizar_k

        k = normalizar_k(conf_params.get("conformers", 1))
    except Exception:                                              # noqa: BLE001
        k = 1

    # El pH de protonacion del ligando. Viaja por el MISMO canal que `conformers`
    # porque es un parametro del mismo paso; `chem/conformer.py::acotar_ph` lo
    # valida y deja dicho si hubo que acotarlo.
    ph = None
    try:
        ph = ((params_por_etapa or {}).get("conformer") or {}).get("ph")
    except Exception:                                              # noqa: BLE001
        ph = None

    if k <= 1:
        return await generate_conformer(smiles, ph)

    try:
        from chem.conformer_ensemble import generate_conformer_ensemble

        return await generate_conformer_ensemble(smiles, k, ph)
    except Exception as exc:                                       # noqa: BLE001
        log.warning("ensemble_no_disponible", error=str(exc)[:200], k=k)
        base = await generate_conformer(smiles, ph)
        base["conformer_warnings"] = [
            f"El ensemble de {k} conformaciones no se pudo generar "
            f"({type(exc).__name__}); la corrida sigue con una sola."
        ]
        return base
from services.docking.protocolo import construir_protocolo, es_motor_peptidico
from services.docking.vina_service import run_vina_docking
from services.targets.resolution import resolve_execution_target
from services.docking.rescoring_client import get_ml_rescore
from scoring.engine import calculate_score_breakdown
from services.docking.evaluation_lock import serialize_ligand_evaluation
from utils.cache import cache
from utils.logger import get_logger
from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
from utils.scientific import audit_scientific_quality

from .registry import (
    STAGE_REGISTRY,
    admet_requested,
    expand_legacy_alias,
    resolve_stage_order,
    skipped_stage_ids,
)

log = get_logger(__name__)


def _int_config_or_default(config: dict | None, key: str, default: int) -> int:
    """Lee enteros opcionales serializados por Pydantic sin convertir None."""
    if not config or config.get(key) is None:
        return default
    return int(config[key])


# El protocolo se construye en `services/docking/protocolo.py`, que es el único
# sitio donde vive el contrato. Este runner era el ÚNICO camino que lo sellaba;
# el del `queue_handler` no lo escribía nunca. Estos dos nombres se conservan
# porque hay pruebas que los importan, y delegan.
#
# ENG-003: sin `diffpepdock`. Estaba en la lista sin implementación, así que el
# nombre acababa en la procedencia de una corrida que ejecutaba ESMFold.
_is_explicit_peptide_engine = es_motor_peptidico


def _protocol_engine(
    peptide_engine: str | None,
    docking_params: dict | None,
    docking_engine: str,
) -> str:
    if es_motor_peptidico(peptide_engine):
        return str(peptide_engine)
    return str((docking_params or {}).get("engine") or docking_engine)


# ── v1.7.4: Mini-transacciones con retry operacional ──────────────────────────
# Cada escritura puntual abre SU PROPIA sesión corta. El retry se hace a nivel
# de OPERACIÓN (reintentar la sesión completa desde cero), NO a nivel de
# flush/commit en la misma sesión: tras un flush fallido, SQLAlchemy exige
# rollback para reusar la sesión ("transaction has been rolled back due to a
# previous exception"), así que reintentar SIN rollback es inútil, y reintentar
# CON rollback expira el identity map (DetachedInstanceError, lección v1.7.2).
# Con sesión nueva por intento, el identity map arranca limpio: el retry
# funciona de verdad y un lock transitorio de ms no mata la evaluación.
async def _run_mini_tx(fn):
    """Ejecuta `fn(db, repository)` en una mini-transacción con retry de
    operación completa. Cada intento abre una sesión nueva (get_db_session
    commitea al salir sin excepción — transacción de ms)."""
    last_error: SQLAlchemyError | None = None
    for attempt in range(MAX_DB_WRITE_RETRIES):
        try:
            async with get_db_session() as db:
                return await fn(db, Repository(db))
        except SQLAlchemyError as e:
            error_str = str(e)
            if "database is locked" in error_str and attempt < MAX_DB_WRITE_RETRIES - 1:
                log.warning("mini_tx_retry", op=fn.__name__, attempt=attempt + 1)
                await asyncio.sleep(DB_WRITE_RETRY_DELAY * (attempt + 1))
                last_error = e
                continue
            raise
    raise last_error  # type: ignore[misc]


async def _quick_set_molecule_status(molecule_id, status) -> None:
    """set_molecule_status en mini-transacción (idempotente → retry seguro)."""
    async def _op(db, repository):
        await repository.set_molecule_status(molecule_id, status)
    return await _run_mini_tx(_op)


async def _quick_upsert_evaluation_result(
    molecule_id,
    *,
    properties=None,
    docking=None,
    scores=None,
    is_control: bool = False,
    error_message: str | None = None,
    task_id: str | None = None,
    structural_evidence=None,
    pose_selection=None,
    docking_protocol=None,
    ligand_state=None,
    freeze_run: bool = False,
):
    """upsert_evaluation_result en mini-transacción (idempotente → retry seguro)."""
    async def _op(db, repository):
        await repository.upsert_evaluation_result(
            molecule_id=molecule_id,
            properties=properties,
            docking=docking,
            scores=scores,
            is_control=is_control,
            error_message=error_message,
            task_id=task_id,
            structural_evidence=structural_evidence,
            pose_selection=pose_selection,
            docking_protocol=docking_protocol,
            ligand_state=ligand_state,
        )
        if freeze_run and task_id is not None:
            snapshot = await repository.snapshot_evaluation_run(molecule_id, task_id)
            await repository.set_molecule_status(molecule_id, MoleculeStatus.EVALUATED)
            return snapshot.id
        return None
    return await _run_mini_tx(_op)


async def _quick_get_evaluation_result(molecule_id):
    """get_evaluation_result en mini-transacción de SOLO LECTURA (no retry)."""
    async def _op(db, repository):
        return await repository.get_evaluation_result(molecule_id)
    return await _run_mini_tx(_op)


async def _quick_get_or_create_molecule(
    smiles: str,
    target_pdb_id: str,
    name: str | None,
    user_id,
) -> tuple:
    """create_or_get_molecule en mini-transacción con retry operacional.

    Devuelve data PURA (molecule_id, smiles, smiles_hash) — no ORM — para que
    el caller arme su snapshot sin depender de una sesión viva. Idempotente
    (busca por smiles_hash antes de insertar) → reintentar con sesión nueva
    es seguro.
    """
    async def _op(db, repository):
        mol = await repository.create_or_get_molecule(
            smiles=smiles,
            target_pdb_id=target_pdb_id,
            name=name,
            user_id=user_id,
        )
        return mol.id, str(mol.smiles), str(mol.smiles_hash)
    return await _run_mini_tx(_op)


@serialize_ligand_evaluation()
async def run_pipeline(
    task_id: str,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    user_id: str | None = None,
    enabled_stages: list[str] | None = None,
    stage_params: dict[str, dict] | None = None,
    stage_order: list[str] | None = None,
    is_control: bool = False,
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = None,
    docking_engine: str = "vina",
    pipeline_config: dict | None = None,
    required_stage_ids: set[str] | None = None,
    prepared_receptor_bytes: bytes | None = None,
) -> dict[str, Any]:

    # Resolver orden
    if stage_order is None:
        stage_order = list(STAGE_REGISTRY.keys())

    # ── v2.0: Legacy alias "rescoring" → xgb + clgnn en secuencia ──────────
    # Lógica en registry.expand_legacy_alias (función pura, cubierta por tests).
    # La expansión ocurre ANTES de resolve_stage_order para que el alias nunca
    # llegue filtrado por ids desconocidos (registry.validate_order).
    had_rescoring_alias = bool(enabled_stages and "rescoring" in enabled_stages)
    enabled_stages, stage_order, stage_params = expand_legacy_alias(enabled_stages, stage_order, stage_params)
    if had_rescoring_alias:
        log.info("legacy_alias_rescoring_expanded", enabled_stages=enabled_stages)

    selectivity_enabled = bool(pipeline_config and pipeline_config.get("pro_selectivity"))
    ordered_ids = resolve_stage_order(
        enabled_stages,
        stage_order,
        selectivity_enabled=selectivity_enabled,
        required_stage_ids=required_stage_ids,
    )

    context: dict[str, Any] = {
        "smiles": smiles,
        "properties": None,
        "conformer": None,
        "docking": None,
        "scientific_warnings": [],
        "scores": {}
    }

    async with get_db_session() as db:
        repository = Repository(db)
        # EVAL-SCI-001: resolver o detenerse. La auto-ingesta sigue viva dentro
        # de `resolve_execution_target`; lo que desaparece es la caída al
        # receptor base, que acoplaba contra 5-HT1A una hipótesis escrita para
        # otra proteína y la devolvía como corrida completa.
        target = await resolve_execution_target(repository, db, target_pdb_id)

        from uuid import UUID
        # v1.7.4: create_or_get_molecule va por MINI-TRANSACCIÓN con retry
        # operacional (sesión nueva por intento). El INSERT es el punto más
        # sensible al lock: un subprocess post-hoc (MM-GBSA/selectivity de la
        # evaluación anterior) que commitea en ese instante ya no mata la
        # evaluación. Idempotente (busca por smiles_hash antes de insertar).
        molecule_id, molecule_smiles, molecule_smiles_hash = (
            await _quick_get_or_create_molecule(
                smiles=smiles,
                target_pdb_id=target.pdb_id,
                name=molecule_name,
                user_id=UUID(user_id) if user_id else None,
            )
        )

        from services.docking.queue_handler import register_job_molecule
        register_job_molecule(task_id, molecule_id)

        # v1.7.4: Commit de la sesión de setup — libera cualquier write
        # residual (p.ej. target auto-ingestado por ingestion_manager).
        await commit_with_retry(db)

        from services.docking.projection_lifecycle import begin_evaluation_projection
        async def _begin_projection(_db, _repository):
            await begin_evaluation_projection(_repository, molecule_id, task_id, is_control=is_control)
        await _run_mini_tx(_begin_projection)

        if not user_id:
            ip_val = await cache.get(f"task_owner_ip:{task_id}")
            if ip_val:
                await cache.set(f"mol_owner_ip:{molecule_id}", ip_val, ttl=86400)

        # ── v1.7.3: PipelineParams snapshot ────────────────────────────────────
        # CAPTURAMOS todos los valores del ORM a data pura INMEDIATAMENTE,
        # antes de cualquier commit/flush intermedio. El pipeline completo
        # opera sobre este snapshot; NUNCA sobre target.* / molecule.* (ORM).
        # Esto elimina la clase entera de DetachedInstanceError.
        from core.pipeline_params import PipelineParams
        pipeline_params = PipelineParams.from_orm(
            target_pdb_id=target.pdb_id,
            target_name=target.name,
            target_chain=target.chain,
            target_site_chains=list(target.site_chains or []) or None,
            target_structural_family=target.structural_family,
            target_is_hot=target.is_hot,
            target_grid_center_x=target.grid_center_x,
            target_grid_center_y=target.grid_center_y,
            target_grid_center_z=target.grid_center_z,
            target_grid_size_x=target.grid_size_x,
            target_grid_size_y=target.grid_size_y,
            target_grid_size_z=target.grid_size_z,
            target_hotspots_base=_coerce_hotspots(target.hotspots) or [],
            target_cofactors_whitelist=_coerce_hotspots(target.cofactors_whitelist) or [],
            affinity_threshold=target.affinity_threshold,
            specificity_floor=target.specificity_floor if target.specificity_floor is not None else 0.5,
            target_spearman_rho=target.spearman_rho,
            molecule_id=molecule_id,
            molecule_smiles=molecule_smiles,
            molecule_smiles_hash=molecule_smiles_hash,
            is_control=is_control,
            grid_center_override=grid_center,
            grid_size_override=grid_size,
            custom_hotspots=custom_hotspots,
            peptide_docking_engine=peptide_docking_engine,
            docking_engine=docking_engine,
            enable_selectivity=selectivity_enabled,
            selected_anti_targets=(
                list(pipeline_config.get("pro_anti_targets", []))
                if pipeline_config and pipeline_config.get("pro_anti_targets")
                else []
            ),
            num_workers=int(pipeline_config.get("pro_workers")) if pipeline_config and pipeline_config.get("pro_workers") is not None else None,
            parallel_docks=int(pipeline_config.get("pro_parallel_docks")) if pipeline_config and pipeline_config.get("pro_parallel_docks") is not None else None,
            gnn_precision=pipeline_config.get("gnn_precision") if pipeline_config else None,
            mmgbsa_enabled=bool(pipeline_config.get("pro_mmgbsa", False)) if pipeline_config else False,
            mmgbsa_steps=_int_config_or_default(
                pipeline_config, "pro_mmgbsa_steps", 1000
            ),
            pipeline_config_raw=pipeline_config,
        )

        # Coordenadas efectivas (override del usuario gana sobre DB)
        box_center = pipeline_params.effective_grid_center
        box_size = pipeline_params.effective_grid_size

        from utils.structural import normalize_hotspots
        active_hotspots = normalize_hotspots(pipeline_params.target_hotspots_base)
        if pipeline_params.custom_hotspots:
            target_hotspots_map = {h.get("name"): h.get("importance", 1.0) for h in active_hotspots}
            active_hotspots = [{"name": h_name, "importance": target_hotspots_map.get(h_name, 1.0)} for h_name in pipeline_params.custom_hotspots]

        # ── v2.0: Helpers de stages ML (XGBoost y CL-GNN por separado) ──────
        async def _run_xgb_stage(params: dict) -> None:
            """Stage XGBoost: rescoring ML SIN GNN (CL-GNN es su propio stage)."""
            if not context.get("docking"):
                raise ValueError("Docking required for xgb")

            from services.docking.preparer import get_target_pdb_path
            pdb_path = str(get_target_pdb_path(pipeline_params.target_pdb_id))
            context["_pdb_path"] = pdb_path
            ml_result = await get_ml_rescore(
                smiles=smiles,
                target_pdb_path=pdb_path,
                poses=[p.model_dump() for p in context["docking"].poses],
                properties=context["properties"],
                grid_center=list(box_center),
                grid_size=list(box_size),
                run_gnn=params.get("run_gnn", False),  # GNN off: RTMScore ya no corre aquí
            )

            if not ml_result.get("fallback") and params.get("run_xgb", True):
                # ═══════════════════════════════════════════════════════════
                # XGBoost YA NO PISA LA AFINIDAD DE VINA
                # ═══════════════════════════════════════════════════════════
                #
                # Auditoría del 2026-09-04. Aquí decía:
                #
                #     context["docking"].best_affinity = -1.36 * pki_a
                #
                # y `affinity_kcal` se guarda desde ese campo. El número que se
                # persiste, se certifica y se imprime no era el de Vina.
                #
                # El motivo largo está en `queue_handler.py`, en el bloque
                # equivalente. Resumen: la función de Vina es empírica y ordena
                # poses; una regresión de pKi es otra cantidad, con otro error
                # y otro dominio. Compartir la unidad kcal/mol no las hace
                # intercambiables. Y la sustitución ocurría incluso con el
                # modelo fuera de su dominio de aplicabilidad.
                pki_a = ml_result.get("score_a", 0.0)
                en_dominio = ml_result.get("in_applicability_domain")
                if pki_a > 0:
                    context["scores"]["ml_pki"] = float(pki_a)
                    context["scores"]["ml_pki_aplicada"] = (
                        bool(en_dominio) if en_dominio is not None else None
                    )
                    if en_dominio is False:
                        from services.avisos import Severidad, aviso

                        context["docking"].scientific_warnings.append(aviso(
                            "ML_FUERA_DE_DOMINIO", Severidad.PRECAUCION,
                            f"La regresión de XGBoost (pKi {pki_a:.2f}, equivalente a "
                            f"{-1.36 * pki_a:.2f} kcal/mol) queda FUERA del dominio de "
                            "aplicabilidad del modelo: la molécula no se parece a las del "
                            "conjunto de entrenamiento. Se muestra como referencia, no "
                            "como predicción. La afinidad del caso es la de Vina.",
                        ))
                # classifier_prob alimenta el breakdown → xgb_score persistido
                context["scores"]["classifier_prob"] = ml_result.get("classifier_prob")
                context["scores"]["shap_values"] = ml_result.get("shap_values")

                # F-21: transparencia del modelo usado (familia vs universal),
                # dominio de aplicabilidad y fallback. engine_used no se produce
                # en este path (model_manager no usa el router gpu/cpu) → None.
                context["scores"]["in_applicability_domain"] = ml_result.get("in_applicability_domain")
                context["scores"]["model_used"] = ml_result.get("model_used")
                context["scores"]["fallback_reason"] = ml_result.get("fallback_reason")
                context["scores"]["engine_used"] = ml_result.get("engine_used")

                if ml_result.get("warnings"):
                    context["scientific_warnings"].extend(ml_result["warnings"])

        async def _run_clgnn_stage() -> None:
            """Stage CL-GNN: score contrastivo + explainability (antes post-loop).

            [A3] Sin fabricación: ante fallo, clgnn_prob = None (componente
            ausente); el engine re-normaliza pesos o degrada. El warning es
            explícito con molecule_id + error.
            """
            from services.ai.clgnn_inference import predict_clgnn
            try:
                # La POSE, no el SMILES: ver `predict_clgnn`. Sin pose devuelve
                # None, que es lo correcto para un scorer post-docking.
                _dock = context.get("docking")
                _mejor_pose = _dock.poses[0] if _dock and _dock.poses else None
                clgnn_prob = predict_clgnn(
                    pipeline_params.molecule_smiles,
                    context.get("_pdb_path", ""),
                    pose_sdf_path=_dock.poses_file_path if _dock else None,
                    pose_pdbqt_block=getattr(_mejor_pose, "pdbqt_block", None),
                )
            except Exception as _clgnn_err:
                clgnn_prob = None
                log.warning("clgnn_stage_failed",
                            molecule_id=str(pipeline_params.molecule_id)[:8],
                            smiles=pipeline_params.molecule_smiles,
                            error=str(_clgnn_err)[:200])

            context["scores"]["clgnn_prob"] = clgnn_prob

            try:
                from services.ai.gnn_explainability import generate_gnn_explainability
                att_w, att_svg, pharm_d = generate_gnn_explainability(pipeline_params.molecule_smiles, clgnn_prob)
                context["scores"]["gnn_attention"] = att_w
                context["scores"]["gnn_attention_svg"] = att_svg
                context["scores"]["gnn_pharmacophores"] = pharm_d
            except Exception as _gnn_exc_err:
                log.warning("gnn_explainability_failed",
                            molecule_id=str(pipeline_params.molecule_id)[:8],
                            error=str(_gnn_exc_err)[:200])

        # Emisión de evento inicial global
        await cache.push_stage_event(task_id, {"type": "pipeline_started", "timestamp": datetime.now(UTC).isoformat()})

        # ── v2.0: Etapas no habilitadas → stage_skipped con motivo ─────────
        # El frontend muestra los orbs con "no se calculó por X razón" en vez
        # de ocultarlos (contrato SSE: type, stage_id, label, reason).
        # La decisión de qué etapas quedan fuera vive en
        # registry.skipped_stage_ids (función pura, cubierta por tests).
        for skipped_id in skipped_stage_ids(ordered_ids):
            skipped_def = STAGE_REGISTRY[skipped_id]
            await cache.push_stage_event(task_id, {
                "stage_id": skipped_id,
                "type": "stage_skipped",
                "label": skipped_def.label,
                "reason": "Etapa no habilitada en la configuración",
                "timestamp": datetime.now(UTC).isoformat(),
            })

        for stage_id in ordered_ids:
            stage_def = STAGE_REGISTRY[stage_id]
            params = stage_params.get(stage_id, stage_def.params)

            await cache.push_stage_event(task_id, {
                "stage_id": stage_id,
                "type": "stage_start",
                "label": stage_def.label,
                "timestamp": datetime.now(UTC).isoformat()
            })

            start_time = datetime.now(UTC)
            error = None

            try:
                if stage_id == "validation":
                    await _quick_set_molecule_status(pipeline_params.molecule_id, MoleculeStatus.VALIDATED)
                    await cache.set_job_progress(task_id, 10, "validation")

                # ── Ejecución paralela: properties + conformer son independientes ──
                # Ambos solo necesitan el SMILES validado. Correrlos secuencialmente
                # suma ~2s innecesarios por evaluación.
                elif stage_id == "properties":
                    # Verificar si conformer está habilitado y aún no corrió
                    if "conformer" in [s for s in ordered_ids if s != "properties"] and context.get("conformer") is None:
                        # Ejecutar properties y conformer en paralelo
                        props_task = asyncio.to_thread(
                            calculate_properties, smiles,
                            run_admet_ai=admet_requested(params),
                        )
                        conf_task = _generar_conformaciones(smiles, stage_params)

                        props_result, conf_result = await asyncio.gather(props_task, conf_task)

                        context["properties"] = props_result
                        context["conformer"] = conf_result
                    else:
                        # Fallback secuencial (conformer deshabilitado)
                        context["properties"] = await asyncio.to_thread(
                            calculate_properties, smiles,
                            run_admet_ai=admet_requested(params),
                        )

                    await _quick_upsert_evaluation_result(
                        molecule_id=pipeline_params.molecule_id,
                        properties=context["properties"],
                        is_control=is_control,
                        task_id=task_id,
                    )
                    await cache.set_job_progress(task_id, 30, "conformer")

                elif stage_id == "sa_filter":
                    if context["properties"] and context["properties"].sa_score > 7.0:
                        from core.exceptions import SyntheticInfeasibilityError
                        raise SyntheticInfeasibilityError(
                            smiles=smiles,
                            sa_score=context["properties"].sa_score,
                        )

                elif stage_id == "conformer":
                    # Si ya corrió en paralelo con properties no se repite, pero
                    # la etapa debe alcanzar el evento stage_done común de abajo.
                    if context.get("conformer") is None:
                        await cache.set_job_progress(task_id, 30, "conformer")
                        context["conformer"] = await _generar_conformaciones(smiles, stage_params)

                elif stage_id == "docking":
                    await _quick_set_molecule_status(pipeline_params.molecule_id, MoleculeStatus.DOCKING)
                    await cache.set_job_progress(task_id, 50, "docking")

                    smiles_hash = context["conformer"]["smiles_hash"] if context.get("conformer") else "tmp_hash"

                    # ── Detección de tipo de molécula ────────────────────────────────
                    # Regla: la selección explícita del usuario SIEMPRE gana sobre la
                    # heurística estructural. El SMARTS solo genera un warning cuando
                    # el usuario eligió un engine de small-molecules (Vina/QuickVina)
                    # pero la molécula parece un péptido.
                    from rdkit import Chem
                    mol = Chem.MolFromSmiles(smiles)

                    # Intención explícita del usuario (primaria)
                    user_chose_peptide_engine = _is_explicit_peptide_engine(
                        peptide_docking_engine
                    )

                    # ── v1.8.1: Aviso de molécula grande (opción B) ──────────────
                    # Se calcula ANTES del branch péptido/Vina porque muchas
                    # moléculas grandes con amidas (Ritonavir, Deferoxamina) se
                    # clasifican como péptidos y van por otra ruta. El aviso debe
                    # cubrir ambas rutas (docking peptídico o Vina).
                    _n_rot_b = 0
                    _n_heavy_b = 0
                    if mol is not None:
                        from rdkit.Chem import rdMolDescriptors
                        _n_rot_b = rdMolDescriptors.CalcNumRotatableBonds(mol)
                        _n_heavy_b = mol.GetNumHeavyAtoms()
                        if _n_rot_b > 12 or _n_heavy_b > 35:
                            context["scientific_warnings"].append(
                                f"⚠️ Molécula grande ({_n_heavy_b} átomos pesados, {_n_rot_b} enlaces "
                                f"rotables) — el docking será lento (búsqueda conformacional extensa). "
                                f"Para mayor velocidad, usa el motor rápido en Opciones (QuickVina: "
                                f"reduce exhaustividad de 8→4, ~2-4x más rápido) a costa de menos "
                                f"exhaustividad de búsqueda. Para péptidos, ESMFold/DiffPepDock son "
                                f"más precisos."
                            )
                        elif _n_rot_b > 8 or _n_heavy_b > 25:
                            context["scientific_warnings"].append(
                                f"⚠️ Molécula con {_n_heavy_b} átomos pesados y {_n_rot_b} enlaces "
                                f"rotables — el docking puede tardar más de lo habitual. "
                                f"Considera el motor rápido (QuickVina, exhaustividad 4) "
                                f"si la velocidad es prioridad."
                            )

                    # Heurística estructural (secundaria — solo genera warning)
                    structure_looks_like_peptide = False
                    if mol:
                        peptide_backbone = Chem.MolFromSmarts("[NX3][CX4][CX3](=[OX1])")
                        matches = mol.GetSubstructMatches(peptide_backbone)
                        structure_looks_like_peptide = len(matches) >= 3

                    # Decisión de routing: consistente con queue_handler.py (OR lógico)
                    is_peptide = user_chose_peptide_engine or structure_looks_like_peptide

                    # Si el usuario eligió Vina/QuickVina pero la estructura parece
                    # péptido → respetar al usuario pero añadir warning científico
                    if structure_looks_like_peptide and not user_chose_peptide_engine:
                        context["scientific_warnings"].append(
                            "⚠️ Se detectaron ≥3 enlaces peptídicos en la molécula. "
                            "Si se trata de un péptido o peptidomimético, considera usar "
                            "ESMFold, ESMFold Pro o ColabFold para mayor precisión de pose."
                        )
                        is_peptide = False  # el usuario mandó — no redirigir

                    if is_peptide:
                        from services.docking.peptide_docking import run_peptide_docking_helper
                        docking = await run_peptide_docking_helper(
                            task_id=task_id,
                            smiles=smiles,
                            target_pdb_id=pipeline_params.target_pdb_id,
                            peptide_docking_engine=peptide_docking_engine or "esmfold",
                            grid_center=list(box_center),
                            grid_size=list(box_size),
                        )
                    else:
                        engine = params.get("engine", docking_engine)
                        if engine == "diffdock":
                            from services.diffdock.service import DiffDockService
                            from services.docking.preparer import get_target_pdb_path
                            from core.models import DockingResult, DockingPose

                            diffdock_svc = DiffDockService()
                            # Obtenemos la ruta real de los archivos
                            conformer_path = context["conformer"]["conformer_path"]
                            target_pdb_path = str(get_target_pdb_path(pipeline_params.target_pdb_id))

                            dd_result = await diffdock_svc.predict(
                                protein_pdb_path=target_pdb_path,
                                ligand_sdf_path=conformer_path,
                                num_poses=params.get("num_poses", 5)
                            )

                            if not dd_result.success:
                                raise RuntimeError(f"DiffDock falló: {dd_result.error}")

                            docking_poses = []
                            for p in dd_result.poses:
                                # Usamos la afinidad predicha si existe, de lo contrario un valor dummy negativo/cero
                                fake_affinity = p.affinity_predicted if p.affinity_predicted is not None else 0.0
                                if fake_affinity > 0: fake_affinity = -fake_affinity

                                docking_poses.append(DockingPose(
                                    rank=p.rank,
                                    affinity=fake_affinity,
                                    rmsd_lb=0.0,
                                    rmsd_ub=p.rmsd_from_input or 0.0,
                                    pdbqt_block=None
                                ))

                            docking = DockingResult(
                                best_affinity=docking_poses[0].affinity if docking_poses else 0.0,
                                poses=docking_poses,
                                poses_file_path=None, # DiffDock guarda poses individuales, no tenemos el multi-SDF aqui facilmente
                                parsing_source="sdf",
                                execution_time_s=dd_result.execution_time_s,
                                scientific_warnings=dd_result.warnings + [dd_result.scientific_context],
                            )
                        else:
                            num_poses = params.get("num_poses", 8)

                            async def _dock_una(smiles_hash: str, smiles: str | None = None):
                                """Una corrida de Vina. Es la unidad que el ensemble repite."""
                                return await run_vina_docking(
                                    smiles_hash=smiles_hash,
                                    target_pdb_id=pipeline_params.target_pdb_id,
                                    target_chain=pipeline_params.target_chain,
                                    site_chains=pipeline_params.target_site_chains,
                                    target_center=box_center,
                                    target_size=box_size,
                                    hotspots=active_hotspots,
                                    docking_engine=engine,
                                    exhaustiveness=params.get("exhaustiveness", 32),
                                    num_poses=num_poses,
                                    seed=params.get("seed", 42),
                                    smiles=smiles,
                                    prepared_receptor_bytes=prepared_receptor_bytes,
                                    cofactors_whitelist=pipeline_params.target_cofactors_whitelist,
                                )

                            # Ensemble SOLO si la etapa de generacion 3D produjo
                            # mas de una conformacion. `conformers` con un solo
                            # elemento, o ausente, entra por el camino de siempre.
                            conformaciones = (context.get("conformer") or {}).get("conformers") or []
                            if len(conformaciones) > 1:
                                from services.docking.ensemble import run_ensemble_docking

                                async def _avisar_progreso(hechas: int, total: int):
                                    """El recuento REAL, no una animación."""
                                    await cache.push_stage_event(task_id, {
                                        "type": "stage_progress",
                                        "stage_id": "docking",
                                        "done": hechas,
                                        "total": total,
                                        "timestamp": datetime.now(UTC).isoformat(),
                                    })

                                docking = await run_ensemble_docking(
                                    smiles=smiles,
                                    conformeros=conformaciones,
                                    num_poses=num_poses,
                                    dock_una=_dock_una,
                                    on_progress=_avisar_progreso,
                                )
                            else:
                                docking = await _dock_una(smiles_hash=smiles_hash, smiles=smiles)
                    context["docking"] = docking

                elif stage_id == "xgb":
                    await cache.set_job_progress(task_id, 80, "scoring")
                    await _run_xgb_stage(params)

                elif stage_id == "clgnn":
                    await _run_clgnn_stage()

                elif stage_id == "rescoring":
                    # Legacy alias (defensa): xgb + clgnn en secuencia
                    await cache.set_job_progress(task_id, 80, "scoring")
                    await _run_xgb_stage(params)
                    await _run_clgnn_stage()

                elif stage_id == "selectivity":
                    # ── v1.7.3: Selectivity Panel (Safety Profiling) ──────────────
                    # Docking contra anti-targets (hERG, CYP3A4, 5-HT2B, PDE3, NaV1.5)
                    # para calcular ratio de selectividad ON/OFF y flags de seguridad.
                    # Solo corre si el usuario lo activó en ProOptionsModal.
                    #
                    # v1.7.4: NO BLOQUEANTE (patrón MM-GBSA): el pipeline lanza el
                    # panel como SUBPROCESS en background y reporta "done" al
                    # instante. El subprocess persiste los resultados en DB cuando
                    # termina (selectivity_ran=True post-hoc) y el frontend los lee
                    # vía polling de /evaluation/result/{molecule_id}. Si el
                    # subprocess corre inline, el pipeline tarda +minutos y además
                    # DUPLICA el trabajo del ProSelectivityPanel del frontend.
                    if not pipeline_params.enable_selectivity:
                        log.info("selectivity_skipped_disabled")
                        continue

                    if not context.get("docking") or not context["docking"].poses:
                        context["scientific_warnings"].append(
                            "Selectividad omitida: sin poses de docking disponibles"
                        )
                        continue

                    import math
                    on_affinity = context["docking"].best_affinity
                    if (isinstance(on_affinity, bool)
                            or not isinstance(on_affinity, (int, float))
                            or not math.isfinite(on_affinity)):
                        context["scientific_warnings"].append(
                            "Selectividad no evaluada: falta afinidad principal finita"
                        )
                        continue
                    workers = pipeline_params.num_workers or params.get("num_workers", 2)
                    anti_ids = pipeline_params.selected_anti_targets or []

                    try:
                        import sys as _sys
                        import os as _os
                        import asyncio as _asyncio

                        _embed_python = _sys.executable
                        _wrapper = _os.path.join(
                            _os.path.dirname(_os.path.dirname(__file__)),
                            "docking", "selectivity_subprocess.py",
                        )
                        from services.docking.desktop_process_registry import (
                            register_process,
                            unregister_process,
                        )

                        _proc = await _asyncio.create_subprocess_exec(
                            _embed_python, _wrapper,
                            str(pipeline_params.molecule_id),
                            pipeline_params.molecule_smiles,
                            pipeline_params.molecule_smiles_hash,
                            pipeline_params.target_pdb_id,
                            str(on_affinity),
                            str(workers),
                            ",".join(anti_ids),
                            task_id,
                            stdout=_asyncio.subprocess.PIPE,
                            stderr=_asyncio.subprocess.DEVNULL,
                            creationflags=BANDERAS_SIN_VENTANA,
                        )
                        register_process(task_id, "selectivity", _proc)

                        async def _watch_selectivity_proc(proc, mol_id):
                            """Espera al subprocess y loguea el resultado (no persiste)."""
                            try:
                                _stdout_b, _ = await communicate_managed(proc, timeout=3600.0)
                            except _asyncio.TimeoutError:
                                log.warning("selectivity_bg_timeout_kill",
                                            molecule_id=str(mol_id)[:8])
                                try:
                                    proc.kill()
                                except Exception:
                                    pass
                                await proc.wait()
                                return
                            finally:
                                unregister_process(task_id, "selectivity", proc)
                            if proc.returncode == 0 and _stdout_b:
                                try:
                                    import json as _json
                                    _sel = _json.loads(_stdout_b.decode("utf-8", "replace"))
                                    log.info("selectivity_bg_computed",
                                             molecule_id=str(mol_id)[:8],
                                             ratio=_sel.get("selectivity_ratio"),
                                             flags=len(_sel.get("safety_flags") or []),
                                             elapsed_s=_sel.get("execution_time_s"))
                                except Exception as _json_err:
                                    log.debug("selectivity_bg_json_error",
                                              error=str(_json_err)[:200])

                        _asyncio.ensure_future(_watch_selectivity_proc(
                            _proc, pipeline_params.molecule_id,
                        ))
                        log.info("selectivity_bg_launched",
                                 molecule_id=str(pipeline_params.molecule_id)[:8])
                    except Exception as sel_err:
                        log.debug("selectivity_bg_launch_failed", error=str(sel_err)[:200])
                        context["scientific_warnings"].append(
                            f"Selectividad en background no disponible: {str(sel_err)[:120]}"
                        )

                elif stage_id == "openmm":
                    from utils.refinement import refine_complex_small_molecule
                    from utils.file_handlers import StoragePath
                    from utils.local_storage import read_text, write_text

                    if context.get("docking") and context["docking"].poses_file_path:
                        try:
                            # Leer target PDB y ligando SDF
                            target_pdb_content = await read_text(StoragePath.target_raw(pipeline_params.target_pdb_id))
                            ligand_sdf_content = await read_text(context["docking"].poses_file_path)

                            # Ejecutar refinamiento
                            refined_sdf = refine_complex_small_molecule(
                                target_pdb_content, ligand_sdf_content,
                                iterations=params.get("iterations", 100)
                            )

                            # Sobrescribir archivo de poses con el refinado
                            await write_text(context["docking"].poses_file_path, refined_sdf)
                            context["scientific_warnings"].append("L3 Refinement (OpenMM AMBER14SB) aplicado a las poses generadas.")
                        except Exception as ref_err:
                            log.warning("Fallo en refinement", error=str(ref_err))
                            context["scientific_warnings"].append(f"Fallo en Refinement L3: {str(ref_err)}")

            except Exception as e:
                error = str(e)
                log.error("Error en stage", stage_id=stage_id, error=error)
                await cache.push_stage_event(task_id, {
                    "stage_id": stage_id,
                    "type": "stage_error",
                    "error": error,
                    "timestamp": datetime.now(UTC).isoformat()
                })
                raise e # Propagar para fallar el pipeline

            end_time = datetime.now(UTC)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            await cache.push_stage_event(task_id, {
                "stage_id": stage_id,
                "type": "stage_done",
                "duration_ms": duration_ms,
                "timestamp": end_time.isoformat()
            })

        # Finalizar Pipeline
        if context.get("docking") and context.get("properties"):
            docking = context["docking"]
            props = context["properties"]

            # Auditoría científica final
            # Mismo régimen y misma función que en `queue_handler`: los
            # umbrales de la auditoría sólo significan algo dentro del espacio
            # para el que están calibrados. Ver `chem/regimenes.py`.
            from chem.regimenes import clasificar as _clasificar_regimen

            _reg = _clasificar_regimen(
                props.molecular_weight or 0.0, props.heavy_atom_count or 0
            )
            deep_warnings = audit_scientific_quality(
                affinity_kcal=docking.best_affinity,
                heavy_atom_count=props.heavy_atom_count,
                log_p=props.log_p,
                docking_poses=[p.model_dump() for p in docking.poses],
                hotspots=active_hotspots,
                hotspots_hit=docking.hotspots_hit,
                regimen=_reg.regimen.value,
                cumple_ro3=_reg.cumple_ro3,
            )
            docking.scientific_warnings.extend(context["scientific_warnings"])
            docking.scientific_warnings.extend(deep_warnings)

            target_specificity_floor = pipeline_params.specificity_floor

            quantum_score_val = None
            try:
                import sys
                _scripts_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
                if _scripts_path not in sys.path:
                    sys.path.insert(0, _scripts_path)
                from compute_quantum_features import compute_quantum_score
                quantum_score_val = compute_quantum_score(pipeline_params.molecule_smiles)
            except Exception as _quantum_err:
                # v1.7.5: loguear el fallo de quantum (antes era except: pass mudo)
                log.warning("quantum_features_failed_skipped",
                            molecule_id=str(pipeline_params.molecule_id)[:8],
                            error=str(_quantum_err)[:200])

            # UMS (Universal Metal Score) — scorer ortogonal SMARTS-only para
            # metaloenzimas (w5 del M5_gated, ver scoring/ums.py + PAPER_UMS.md).
            # Solo se aplica en engine.py si target_family es metaloenzima.
            ums_score_val = None
            try:
                from scoring.ums import compute_universal_metal_score
                _ums, _ = compute_universal_metal_score(
                    pipeline_params.molecule_smiles,
                    molchamb_score=quantum_score_val if quantum_score_val is not None else 0.5,
                    target_family=pipeline_params.target_structural_family,
                )
                ums_score_val = _ums
            except Exception as _ums_err:
                log.debug("ums_compute_failed", error=str(_ums_err)[:200])

            # ── v1.7.2: MM-GBSA real — OPCIONAL y por SUBPROCESS ──
            # Desactivado por defecto (el usuario lo activa en la pestaña).
            # v1.7.1 FIX: subprocess con timeout real (run_in_executor + wait_for
            # dejaba threads OpenMM huérfanos quemando CPU — mismo bug que
            # queue_handler).
            mmgbsa_score_value = None
            run_mmgbsa_stage = False
            if pipeline_config is not None:
                run_mmgbsa_stage = bool(pipeline_config.get("pro_mmgbsa", False))

            if run_mmgbsa_stage:
                try:
                    import asyncio as _asyncio
                    import json as _json
                    import os as _os
                    import sys as _sys

                    _embed_python = _sys.executable
                    _wrapper = _os.path.join(
                        _os.path.dirname(_os.path.dirname(__file__)),
                        "docking", "mmgbsa_subprocess.py",
                    )
                    # FIX v2.1 (2026-08-04): pasar el SDF de poses de Vina al
                    # subprocess para que MM-GBSA calcule sobre la pose REAL
                    # del docking (compute_mmgbsa_from_pose), no sobre la
                    # conformación arbitraria de RDKit que daba -27983 kcal/mol.
                    _poses_sdf = None
                    docking_for_mmgbsa = context.get("docking")
                    if docking_for_mmgbsa and docking_for_mmgbsa.poses_file_path:
                        _poses_sdf = docking_for_mmgbsa.poses_file_path
                    # `--poses` y no un posicional: el SDF caia en la
                    # posicion de `max_iter` y el wrapper moria con
                    # `ValueError: invalid literal for int()`. Ver el bloque de
                    # argumentos en `mmgbsa_subprocess.py`.
                    from utils.local_storage import path_for as _pose_path_for
                    _mmgbsa_args = [context.get("_pdb_path", ""), pipeline_params.molecule_smiles]
                    if _poses_sdf:
                        _mmgbsa_args += ["--poses", str(_pose_path_for(_poses_sdf))]
                    _proc = await _asyncio.create_subprocess_exec(
                        _embed_python, _wrapper, *_mmgbsa_args,
                        stdout=_asyncio.subprocess.PIPE,
                        stderr=_asyncio.subprocess.DEVNULL,
                        creationflags=BANDERAS_SIN_VENTANA,
                    )
                    try:
                        _stdout_b, _ = await communicate_managed(_proc, timeout=60.0)
                    except _asyncio.TimeoutError:
                        try:
                            _proc.kill()
                        except Exception:
                            pass
                        await _proc.wait()
                    else:
                        if _stdout_b:
                            try:
                                _mmgbsa_result = _json.loads(
                                    _stdout_b.decode("utf-8", "replace"))
                                mmgbsa_score_value = _mmgbsa_result.get("mmgbsa") if _proc.returncode == 0 else None
                                if mmgbsa_score_value is None:
                                    docking.scientific_warnings.append(
                                        "MM-GBSA no evaluado: " + _mmgbsa_result.get("error", "sin resultado")
                                    )
                                    log.warning("mmgbsa_not_evaluated", task_id=task_id,
                                                error=_mmgbsa_result.get("error"))
                            except Exception as _mmgbsa_parse_err:
                                # v1.7.5: loguear el fallo de parseo del subprocess MM-GBSA
                                log.warning("mmgbsa_subprocess_parse_failed",
                                            molecule_id=str(pipeline_params.molecule_id)[:8],
                                            error=str(_mmgbsa_parse_err)[:200])
                except Exception as _mmgbsa_run_err:
                    # v1.7.5: loguear el fallo de lanzamiento del subprocess MM-GBSA
                    log.warning("mmgbsa_subprocess_failed_skipped",
                                molecule_id=str(pipeline_params.molecule_id)[:8],
                                error=str(_mmgbsa_run_err)[:200])

            target_family_value = pipeline_params.target_structural_family

            breakdown = calculate_score_breakdown(
                docking,
                props,
                is_control=is_control,
                target_hotspots=active_hotspots,
                affinity_threshold=pipeline_params.affinity_threshold,
                specificity_floor=target_specificity_floor,
                gnn_score=context["scores"].get("gnn_score"),
                xgb_prob=context["scores"].get("classifier_prob"),
                clgnn_prob=context["scores"].get("clgnn_prob"),
                mmgbsa_score=mmgbsa_score_value,
                quantum_score=quantum_score_val,
                ums_score=ums_score_val,
                target_family=target_family_value,
            )

            # ── M5-Zn: el protocolo de metaloenzimas de zinc ─────────────
            #
            # La MISMA llamada que `queue_handler`, y por eso la decision vive
            # en `protocols/m5/ejecucion.py` y no aqui: hay dos ejecutores y
            # duplicar esta traduccion es lo que el doc 74 deshace.
            #
            # Envuelto: un fallo aqui no tumba un acoplamiento terminado. Las
            # cuatro columnas quedan a NULL, que se lee «no se ejecuto» y nunca
            # como un score de cero.
            m5_columnas: dict = {}
            try:
                from services.pipeline.protocols.m5.ejecucion import ejecutar as ejecutar_m5

                _salida_m5 = ejecutar_m5(
                    smiles=pipeline_params.molecule_smiles,
                    target_pdb_id=pipeline_params.target_pdb_id,
                    target_family=target_family_value,
                    vina_kcal_mol=docking.best_affinity if docking else None,
                    xgb_prob=context["scores"].get("classifier_prob"),
                    # GNN-D no tiene productor en produccion; solo CA2 la pide.
                    # El §4.1 del ADR prohibe sustituirla por CL-GNN.
                    gnn_d_prob=None,
                )
                if _salida_m5 is not None:
                    m5_columnas = _salida_m5.as_columns()
                    log.info(
                        "m5_zn_ejecutado",
                        protocol_id=_salida_m5.protocol_id,
                        estado=_salida_m5.estado,
                        score=_salida_m5.score,
                        ausentes=list(_salida_m5.componentes_ausentes),
                    )
            except Exception as _m5_err:
                log.warning("m5_zn_fallo", error=str(_m5_err)[:200])

            # ── Evidencia estructural ─────────────────────────────────────
            # AQUI y no antes: es el unico punto donde coexisten las poses con
            # su PDBQT, el receptor que se acoplo y la molecula persistida.
            #
            # ENVUELTO A PROPOSITO. Un fallo del validador NO puede tumbar un
            # docking que ya termino: la etapa se declara `not_evaluated` con su
            # razon y el resultado cientifico del acoplamiento se conserva
            # intacto. Es la regla que separa «no lo medimos» de «salio mal».
            structural_evidence = None
            try:
                from services.chemistry.structural_evidence import build_structural_evidence
                from utils.local_storage import read_bytes

                evidence_receptor_bytes = prepared_receptor_bytes
                receptor_snapshot = getattr(docking, "receptor_path", None)
                if evidence_receptor_bytes is None and receptor_snapshot:
                    evidence_receptor_bytes = await read_bytes(receptor_snapshot)

                structural_evidence = await asyncio.to_thread(
                    build_structural_evidence,
                    poses=list(docking.poses or []),
                    target_pdb_id=pipeline_params.target_pdb_id,
                    receptor_sha256=getattr(docking, "receptor_sha256", None),
                    smiles=pipeline_params.molecule_smiles,
                    receptor_bytes=evidence_receptor_bytes,
                )
            except Exception as exc:                                # noqa: BLE001
                log.warning("structural_evidence_fallo_no_fatal", error=str(exc)[:200])
                try:
                    from services.chemistry.structural_evidence import (
                        VALIDADOR_NO_DISPONIBLE,
                        _abstencion_de_etapa,
                    )

                    structural_evidence = _abstencion_de_etapa(
                        VALIDADOR_NO_DISPONIBLE,
                        f"La etapa de validacion estructural lanzo {type(exc).__name__}. "
                        f"El acoplamiento de esta evaluacion NO se ve afectado.",
                    )
                except Exception:                                   # noqa: BLE001
                    structural_evidence = None

            # ── Seleccion de pose (P0-B) ──────────────────────────────────
            # DESPUES de generar y validar las poses: la recomendacion lee el
            # estado fisico de cada una para poder decir si la que sugiere pasa
            # los controles, y para listar alternativas que si pasan.
            #
            # ENVUELTO IGUAL QUE LA ANTERIOR. El selector RECOMIENDA: si falta,
            # falla o se abstiene, la referencia sigue siendo Vina top-1 y el
            # docking no se ve afectado. Nada aqui reordena poses ni toca
            # afinidades.
            pose_selection = None
            try:
                from services.chemistry.pose_selection import build_pose_selection_for_run

                pose_selection = await asyncio.to_thread(
                    build_pose_selection_for_run,
                    poses=list(docking.poses or []),
                    target_pdb_id=pipeline_params.target_pdb_id,
                    receptor_sha256=getattr(docking, "receptor_sha256", None),
                    receptor_bytes=evidence_receptor_bytes,
                    structural_evidence=structural_evidence,
                )
            except Exception as exc:                                # noqa: BLE001
                log.warning("pose_selection_fallo_no_fatal", error=str(exc)[:200])
                pose_selection = None

            # ── Protocolo de generación 3D, tal como se ejecutó ──────────
            # Se sella lo PEDIDO y lo CONSEGUIDO por separado. Un ensemble de 30
            # que sólo embebió 22 tiene menos cobertura de la solicitada, y esa
            # diferencia es justo lo que se perdería contando sólo las
            # conformaciones representadas en el top-K entregado.
            # Lo EJECUTADO manda sobre lo pedido: si qvina2 cayó a Vina con
            # exhaustiveness=4, eso es lo que se sella, y lo solicitado queda
            # aparte. Ver `services/docking/protocolo.py`.
            docking_protocol = construir_protocolo(
                docking=docking,
                peptide_engine=peptide_docking_engine,
                docking_engine=docking_engine,
                docking_params=stage_params.get("docking"),
                conformer_ctx=context.get("conformer"),
            )

            # Guardar todo en DB (mini-transacción: transacción de ms)
            evaluation_run_id = await _quick_upsert_evaluation_result(
                molecule_id=pipeline_params.molecule_id,
                properties=props,
                docking=docking,
                scores={**breakdown.model_dump(), **context["scores"], **m5_columnas},
                is_control=is_control,
                task_id=task_id,
                structural_evidence=structural_evidence,
                pose_selection=pose_selection,
                docking_protocol=docking_protocol,
                # ── Qué especie se acopló ─────────────────────────────────
                # `ligand_state` sólo lo escribía `queue_handler.py`. Aquí
                # había cero apariciones, así que en modo PRO la columna
                # quedaba NULL sin error y el dossier no podía decir qué
                # tautómero ni qué estado de protonación se acoplaron — la
                # misma divergencia que tuvo `docking_protocol` hasta que se
                # buscó a mano. El contexto ya trae el conformer entero.
                # La especie química y la transferencia ESMFold→ligando deben
                # viajar juntas: el dossier no puede inferirlas desde la pose.
                ligand_state=(
                    lambda _base, _transfer: (
                        {**_base, "peptide_transfer": _transfer}
                        if _transfer else (_base or None)
                    )
                )(
                    (context.get("conformer") or {}).get("estado_del_ligando"),
                    getattr(docking, "peptide_transfer_manifest", None),
                ),
                freeze_run=True,
            )
            await cache.set_job_progress(task_id, 100, "done")
            await cache.push_stage_event(task_id, {"type": "pipeline_done", "timestamp": datetime.now(UTC).isoformat()})

            result = await _quick_get_evaluation_result(pipeline_params.molecule_id)
            return {
                "task_id": task_id,
                "molecule_id": str(pipeline_params.molecule_id),
                "smiles_hash": pipeline_params.molecule_smiles_hash,
                "target_pdb_id": pipeline_params.target_pdb_id,
                "total_score": breakdown.total_score,
                "best_affinity": docking.best_affinity,
                "evaluation_result_id": str(result.id) if result else None,
                "evaluation_run_id": str(evaluation_run_id),
            }
        else:
            raise ValueError("El pipeline finalizó pero no generó docking o propiedades.")
