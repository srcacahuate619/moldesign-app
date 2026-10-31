"""Cola de evaluación local para el MVP (modo DESKTOP).

Las evaluaciones se ejecutan en un ThreadPoolExecutor / event loop local:
sin Celery, sin Redis, sin modo cloud.
"""

from __future__ import annotations

# `asyncio` se usa a nivel de modulo en `_run_full_evaluation_async` (la ruta SIN
# `pipeline_config`). Faltaba: los cinco `import asyncio as _asyncio` de este
# fichero son LOCALES a otras funciones y no ligan el nombre alli, asi que toda
# evaluacion por la ruta por defecto moria con `NameError` antes de calcular
# propiedades. El gate no lo veia porque solo ejercitaba la ruta CON
# `pipeline_config`, que retorna antes hacia `services/pipeline/runner.py`.
import asyncio
import hashlib
import json
import os
import threading
import uuid as _uuid_mod
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from chem.conformer import generate_conformer
from chem.properties import calculate_properties
from core.config import get_settings
from core import config as core_config
from core.database import commit_with_retry, get_db_session
from core.models import JobStatus, MoleculeStatus, _coerce_cofactores, _coerce_hotspots
from db.repository import Repository
from services.docking.protocolo import construir_protocolo, declarar_residuos_de_referencia, validar_motor_solicitado
from scoring.engine import calculate_score_breakdown
from services.docking.desktop_job_status import get_desktop_job_status
from services.docking.desktop_process_registry import (
    cancel_processes,
    register_process,
    unregister_process,
)
from services.docking.vina_service import run_vina_docking
from services.pipeline.registry import admet_requested
# Re-export deliberado (C-09): queue_handler.run_peptide_docking_helper es el
# alias de compatibilidad que test_peptide_docking.py verifica explícitamente.
# No es un import muerto aunque no se llame por nombre dentro de este módulo.
from services.docking.peptide_docking import run_peptide_docking_helper  # noqa: F401
from services.docking.rescoring_client import get_ml_rescore
from services.docking.evaluation_lock import serialize_ligand_evaluation
from utils.cache import cache
from services.avisos import Severidad, aviso
from utils.procesos import BANDERAS_SIN_VENTANA, communicate_managed
from utils.logger import get_logger
from utils.scientific import audit_scientific_quality

log = get_logger(__name__)
settings = get_settings()

# ── DESKTOP mode state ──────────────────────────────────────────────────────────
_desktop_executor: ThreadPoolExecutor | None = None
_desktop_jobs: dict[str, dict[str, Any]] = {}
_molecule_job_owners: dict[str, str] = {}
_desktop_lock = threading.Lock()
_DESKTOP_JOB_MAX_AGE_HOURS = 24

# Cuatro evaluaciones simultáneas como máximo. El semáforo es cross-loop;
# adquirirlo se sondea sin bloquear un hilo. El watchdog conserva el límite
# histórico de 20 minutos TOTALES, cancela y espera la limpieza del pipeline.
# Los cálculos nativos en hilos requieren aislamiento adicional para poder
# detenerlos físicamente; cancelar asyncio por sí solo no los termina.
DESKTOP_MAX_CONCURRENCY = 4          # v1.8.1: 1→4 — screenings masivos (387 targets) sin espera serial
EVAL_WATCHDOG_TIMEOUT_S = 20 * 60    # límite total de ejecución
# Timeout de espera en cola: si no se adquiere el semáforo en este tiempo
# (otra evaluación atascada que nunca libera), la evaluación falla con un
# error claro en vez de quedar PENDING para siempre (carga infinita).
EVAL_QUEUE_WAIT_TIMEOUT_S = 45   # 45s esperando el semáforo (antes 3 min — fallar rápido si hay cola)
# FIX (deadlock desktop): antes era asyncio.Semaphore(1). Ese semáforo se usaba
# desde DOS event loops distintos: el principal de FastAPI (via create_task) y
# el loop NUEVO del ThreadPoolExecutor fallback (executor.submit(lambda:
# _asyncio.run(...))). asyncio.Semaphore NO es thread-safe ni cross-loop: el
# release() en un loop no despierta un acquire() pendiente en otro loop → el
# semáforo quedaba en 0 y la SIGUIENTE evaluación esperaba PENDING 3 min y
# fallaba "Cola saturada" (aunque no hubiera evaluación activa).
# v1.8.1: threading.Semaphore(DESKTOP_MAX_CONCURRENCY) es thread-safe en
# cualquier thread/loop (misma garantía que el Lock del fix anterior) y permite
# N evaluaciones concurrentes (4) para screenings masivos sin contención SQLite
# (WAL soporta múltiples lectores + 1 escritor; busy_timeout=60000ms).
_desktop_eval_semaphore = threading.Semaphore(DESKTOP_MAX_CONCURRENCY)

def cancel_active_mmgbsa(task_id: str) -> int:
    """Mata únicamente subprocesses MM-GBSA asociados a ``task_id``."""
    killed = cancel_processes(task_id, "mmgbsa")
    if killed:
        log.info("mmgbsa_procs_cancelados", task_id=task_id, count=killed)
    return killed


def cancel_active_selectivity(task_id: str) -> int:
    """Mata únicamente subprocesses de selectividad de ``task_id``."""
    killed = cancel_processes(task_id, "selectivity")
    if killed:
        log.info("selectivity_procs_cancelados", task_id=task_id, count=killed)
    return killed


def cancel_active_structural_evidence(task_id: str) -> int:
    """Mata el proceso de validación estructural de ``task_id`` (al cancelar o al vencer el plazo de la evaluación)."""
    killed = cancel_processes(task_id, "structural_evidence")
    if killed:
        log.info("structural_evidence_procs_cancelados", task_id=task_id, count=killed)
    return killed


def request_desktop_job_cancellation(task_id: str) -> bool:
    """Marca una tarea activa para que no vuelva a publicarse como éxito."""
    with _desktop_lock:
        job = _desktop_jobs.get(task_id)
        if not job or job.get("status") not in ("PENDING", "STARTED", "submitted"):
            return False
        job["cancel_requested"] = True
        job["status"] = "FAILURE"
        job["error"] = "Cancelado por el usuario"
        job["finished_at"] = datetime.now(UTC).isoformat()
        running = job.get("async_task")
    if running is not None and not running.done():
        running.get_loop().call_soon_threadsafe(running.cancel)
    return True


def register_job_molecule(task_id: str, molecule_id) -> None:
    """Asocia el job con su fila antes de comenzar las etapas costosas."""
    with _desktop_lock:
        job = _desktop_jobs.get(task_id)
        if job is not None:
            job["molecule_id"] = str(molecule_id)
            _molecule_job_owners[str(molecule_id)] = task_id


def _is_desktop_job_cancelled(task_id: str) -> bool:
    with _desktop_lock:
        job = _desktop_jobs.get(task_id)
        return bool(job and job.get("cancel_requested"))


async def _persist_molecule_failed(
    molecule_id: str | None,
    reason: str,
    *,
    task_id: str | None = None,
    overwrite_terminal_status: bool = False,
) -> bool:
    """Persiste un fallo sin borrar el resultado o archivos ya existentes."""
    if not molecule_id:
        return False
    try:
        from uuid import UUID as _UUID

        async with get_db_session() as db:
            from core.database import flush_with_retry

            repo = Repository(db)
            molecule = await repo.get_molecule(_UUID(molecule_id))
            if not molecule or (
                molecule.status not in (
                    MoleculeStatus.PENDING, MoleculeStatus.VALIDATED, MoleculeStatus.DOCKING
                ) and not overwrite_terminal_status
            ):
                return False
            if task_id is not None:
                await repo.mark_evaluation_run_failed(task_id, reason)
                result = await repo.get_evaluation_result(molecule.id)
                # Un auxiliar tardío nunca debe cambiar la proyección de otra corrida.
                with _desktop_lock:
                    active_owner = _molecule_job_owners.get(str(molecule.id))
                # Al comenzar una reevaluación aún puede existir la proyección
                # ANTERIOR. Su task_id no impide cerrar el fallo del nuevo dueño.
                if (active_owner not in (None, task_id) or (
                    active_owner is None and result is not None
                    and result.task_id not in (None, task_id)
                )):
                    await db.commit()
                    return False
                await repo.upsert_evaluation_result(
                    molecule_id=molecule.id, error_message=reason, task_id=task_id
                )
            molecule.status = MoleculeStatus.FAILED
            await flush_with_retry(db)
            await db.commit()
            log.warning(
                "molecule_marcada_failed",
                molecule_id=molecule_id[:8],
                reason=reason,
            )
            return True
    except Exception as exc:
        log.warning(
            "molecule_failed_persist_failed",
            molecule_id=molecule_id[:8],
            reason=reason,
            error=str(exc),
        )
        return False


def _clean_old_desktop_jobs() -> int:
    cutoff = datetime.now(UTC).timestamp() - (_DESKTOP_JOB_MAX_AGE_HOURS * 3600)
    expired = []
    with _desktop_lock:
        for task_id, job in list(_desktop_jobs.items()):
            started = job.get("started_at")
            if started:
                try:
                    ts = datetime.fromisoformat(started).timestamp()
                    if ts < cutoff:
                        expired.append(task_id)
                except (ValueError, TypeError):
                    expired.append(task_id)
        for task_id in expired:
            job = _desktop_jobs.pop(task_id)
            molecule_id = job.get("molecule_id")
            if _molecule_job_owners.get(molecule_id) == task_id:
                _molecule_job_owners.pop(molecule_id, None)
    return len(expired)


# EVAL-BE-007. Aqui vivian `_schedule_cleanup` y `_cleanup_molecule_direct`:
# una tarea diferida que, una hora despues de evaluar, borraba de la base de
# datos toda molecula no guardada cuyo `total_score` fuera menor que 50. Nadie
# las llamaba —quedaron desconectadas al cambiar la politica de historial— pero
# seguian ahi, listas para reconectarse por error. El historial es del usuario:
# nada se borra automaticamente, y menos por un umbral de una metrica 0-100 que
# el producto ya no usa para gobernar decisiones (docs/60).


def _get_desktop_executor() -> ThreadPoolExecutor:
    global _desktop_executor
    if _desktop_executor is None:
        # v1.8.1: max_workers 1→4 para screenings masivos (387 targets).
        # SQLite está en WAL mode (lectores concurrentes OK) y el semáforo
        # threading.Lock sigue serializando los accesos críticos por tarea.
        # El cambio reduce el tiempo de un barrido completo de ~9h a ~2h.
        _desktop_executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="moldesign-worker",
        )
    return _desktop_executor


class _DesktopTask:
    """Tarea del dispatcher local: identificador de job DESKTOP (task_id)."""
    def __init__(self, task_id: str):
        self.id = task_id


@serialize_ligand_evaluation(delegate_pro=True)
async def _run_full_evaluation_async(
    task_id: str,
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = None,
    pipeline_config: dict | None = None,
    docking_engine: str = "vina",
    run_admet_ai: bool = False,
    enable_mmgbsa: bool = False,
    ph: float | None = None,
) -> dict[str, Any]:
    if enable_mmgbsa or (pipeline_config or {}).get("pro_mmgbsa"):
        raise ValueError("MM-GBSA no disponible (MMGBSA_CONDICION): parametrización legacy inconsistente.")
    validar_motor_solicitado(
        docking_engine=(pipeline_config or {}).get("docking_engine", docking_engine),
        peptide_engine=peptide_docking_engine,
    )
    if "engine" in ((pipeline_config or {}).get("stage_params") or {}).get("docking", {}):
        raise ValueError("El motor se declara en docking_engine, no en stage_params.docking.engine")
    from services.docking.protocolo import resolver_modo_tautomero
    mode = resolver_modo_tautomero(((pipeline_config or {}).get("stage_params") or {}).get("conformer"))
    # Siempre explícito: el valor por defecto del conformador ya no es «canonico».
    tautomer_kwargs = {"tautomero": mode}
    # ── Pipeline resource signal ────────────────────────────────────
    try:
        from services.llm.resource_manager import get_resource_manager
        get_resource_manager().on_pipeline_start()
    except ImportError:
        pass

    # PROV-004: ambos modos ejecutan el mismo runner. El perfil normal conserva
    # el presupuesto de búsqueda histórico y CL-GNN; toda evidencia científica
    # y sus avisos se producen por el mismo conjunto de etapas.
    if pipeline_config is None:
        from services.docking.protocolo import configuracion_pipeline_predeterminada

        default_settings = core_config.get_settings()
        pipeline_config = configuracion_pipeline_predeterminada(
            default_settings, docking_engine=docking_engine, run_admet_ai=run_admet_ai,
        )
    # --- ÚNICO EJECUTOR CIENTÍFICO ---
    if pipeline_config:
        from services.pipeline.runner import run_pipeline
        if ph is not None:
            pipeline_config = dict(pipeline_config)
            stage_params = dict(pipeline_config.get("stage_params") or {})
            conformer_params = dict(stage_params.get("conformer") or {})
            conformer_params["ph"] = ph
            stage_params["conformer"] = conformer_params
            pipeline_config["stage_params"] = stage_params
        _engine = pipeline_config.get("docking_engine", docking_engine)
        return await run_pipeline(
            task_id=task_id,
            smiles=smiles,
            target_pdb_id=target_pdb_id,
            molecule_name=molecule_name,
            user_id=user_id,
            enabled_stages=pipeline_config.get("enabled_stages", []),
            stage_params=pipeline_config.get("stage_params", {}),
            stage_order=pipeline_config.get("stage_order"),
            is_control=is_control,
            grid_center=grid_center,
            grid_size=grid_size,
            custom_hotspots=custom_hotspots,
            peptide_docking_engine=peptide_docking_engine,
            docking_engine=_engine,
            pipeline_config=pipeline_config,
        )
    # --- END PRO MODE PIPELINE ---

    async with get_db_session() as db:
        repository = Repository(db)
        # EVAL-SCI-001: misma regla que el runner PRO. Un receptor que no se
        # puede resolver detiene la corrida en vez de convertirla en una
        # corrida contra el receptor base.
        from services.targets.resolution import resolve_execution_target

        target = await resolve_execution_target(repository, db, target_pdb_id)

        molecule = await repository.create_or_get_molecule(
            smiles=smiles,
            target_pdb_id=target.pdb_id,
            name=molecule_name,
            user_id=UUID(user_id) if user_id else None,
        )

        from services.docking.projection_lifecycle import begin_evaluation_projection
        await begin_evaluation_projection(repository, molecule.id, task_id, is_control=is_control)

        # SEC-H03: Asociar la IP del creador anónimo con la molécula creada
        if not user_id:
            ip_val = await cache.get(f"task_owner_ip:{task_id}")
            if ip_val:
                await cache.set(f"mol_owner_ip:{molecule.id}", ip_val, ttl=86400)

        # v1.7.4: Liberamos el lock de escritura INMEDIATAMENTE después del
        # INSERT de create_or_get_molecule. Antes, la transacción quedaba
        # abierta durante TODO el pipeline (docking, rescoring...) y otros
        # writers (increment_anonymous_count, cleanup, subprocesses MM-GBSA /
        # selectivity) recibían "database is locked". expire_on_commit=False
        # garantiza que los objetos ORM sigan accesibles tras el commit.
        await commit_with_retry(db)
        register_job_molecule(task_id, molecule.id)

        # ── v1.7.3: PipelineParams snapshot ────────────────────────────────────
        # CAPTURAMOS todos los valores del ORM a data pura INMEDIATAMENTE,
        # antes de cualquier commit/flush intermedio (commit_with_retry en
        # línea ~786). El resto del pipeline opera sobre este snapshot;
        # NUNCA sobre target.* / molecule.* (ORM). Esto elimina la clase
        # entera de DetachedInstanceError en el flujo legacy.
        # v1.7.4: el commit de create_or_get_molecule (arriba) NO expira los
        # objetos (expire_on_commit=False) — el snapshot sigue siendo seguro.
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
            target_hotspots_source=getattr(target, "hotspots_source", None),
            target_cofactors_whitelist=_coerce_cofactores(target.cofactors_whitelist),
            affinity_threshold=target.affinity_threshold,
            specificity_floor=target.specificity_floor if target.specificity_floor is not None else 0.5,
            target_spearman_rho=target.spearman_rho,
            molecule_id=molecule.id,
            molecule_smiles=str(molecule.smiles),
            molecule_smiles_hash=str(molecule.smiles_hash),
            is_control=is_control,
            grid_center_override=grid_center,
            grid_size_override=grid_size,
            custom_hotspots=custom_hotspots,
            peptide_docking_engine=peptide_docking_engine,
            docking_engine=docking_engine,
            enable_selectivity=False,
            selected_anti_targets=[],
            mmgbsa_enabled=enable_mmgbsa,
            mmgbsa_steps=1000,
            pipeline_config_raw=None,
        )

        # El smiles_hash puede ser actualizado por protonación (línea ~786).
        # Esta variable local es la única fuente de verdad para el resto.
        effective_smiles_hash = pipeline_params.molecule_smiles_hash
        scientific_warnings = []

        try:
            # EVAL-SCI-002. Aqui vivia un pre-filtro que consultaba el grafo
            # quimico local (`predict_early_exit`) y, si la media de los
            # vecinos de Tanimoto >= 0.6 quedaba por debajo de un umbral,
            # devolvia la corrida como «saltada» sin acoplar y sin persistir
            # nada. Esa salida prometia exito al dispatcher, no dejaba
            # resultado que leer, y el polling la traducia en un fallo tecnico
            # inventado; la molecula quedaba en `validated`, invisible en el
            # historial. Una prediccion no puede reemplazar a la observacion
            # que el investigador pidio: el docking se ejecuta siempre.
            properties = await asyncio.to_thread(
                calculate_properties, smiles, run_admet_ai=run_admet_ai
            )
            await repository.set_molecule_status(pipeline_params.molecule_id, MoleculeStatus.VALIDATED)
            await commit_with_retry(db)  # v1.7.4: transacción corta

            # SA > 7 señala dificultad, no imposibilidad demostrada.
            if properties.sa_score > 7.0:
                scientific_warnings.append(aviso(
                    "SA_ALTO", Severidad.PRECAUCION,
                    f"SA Score RDKit {properties.sa_score:.2f} > 7: síntesis potencialmente difícil. "
                    "La evaluación estructural continúa; SA no demuestra inviabilidad sintética.",
                ))

            await repository.upsert_evaluation_result(
                molecule_id=pipeline_params.molecule_id,
                properties=properties,
                is_control=is_control,
                task_id=task_id,
            )
            await commit_with_retry(db)  # v1.7.4: transacción corta (propiedades)

            # ── v1.7: Metal-binding features ──
            # Detectar grupos quelantes de metales (sulfonamida, tiol, etc.)
            # para alimentar scoring de metaloenzimas y enriquecer warnings.
            metal_binding = None
            try:
                from services.chemistry.protein_surgery import metal_features
                metal_binding = metal_features(pipeline_params.molecule_smiles)
                if metal_binding and metal_binding.get("has_metal_binding_potential"):
                    log.info("metal_binding_detected",
                             smiles=pipeline_params.molecule_smiles[:80],
                             groups=metal_binding.get("zn_binding_groups_total", 0))
            except Exception as exc:
                log.warning("metal_features_failed", error=str(exc)[:200])
                scientific_warnings.append(aviso(
                    "METAL_FEATURES_NO_EVALUADO", Severidad.PRECAUCION,
                    "No se pudieron calcular los grupos quelantes; la ausencia de señal no es negativa.",
                ))

            # Pre-calcular hotspots en scope (v1.7.3: desde snapshot, no ORM)
            box_center = pipeline_params.effective_grid_center
            box_size = pipeline_params.effective_grid_size

            from utils.structural import normalize_hotspots
            active_hotspots = normalize_hotspots(pipeline_params.target_hotspots_base)
            if custom_hotspots is not None:
                target_hotspots_map = {h.get("name"): h.get("importance", 1.0) for h in active_hotspots}
                active_hotspots = [
                    {"name": h_name, "importance": target_hotspots_map.get(h_name, 1.0)}
                    for h_name in custom_hotspots
                ]

            # Detección autónoma de tipo de molécula (péptido u organometálica)
            is_peptide = False
            is_organometallic = False
            metals_in_mol = set()
            # Se rellena en el paso del conformer; `None` si esa rama no corrió
            # (péptidos, cachés), y entonces el upsert no lo toca.
            _estado_del_ligando_persistible: dict | None = None
            _peptide_transfer_manifest: dict | None = None
            conformer_prepared: dict | None = None
            peptide_smiles = smiles
            docking = None

            try:
                from rdkit import Chem
                mol = Chem.MolFromSmiles(smiles)
                if mol:
                    # v1.8.1: Aviso de molécula grande (opción B) — aplica a TODOS
                    # los flujos (estándar + PRO). Umbral combinado: rotables
                    # (flexibilidad) + heavy atoms (tamaño). El test de estrés
                    # mostró que los timeouts vienen de moléculas con >25-35
                    # heavy atoms (Warfarina/Captopril/Erlotinib/Deferoxamina).
                    from rdkit.Chem import rdMolDescriptors
                    _n_rot_b = rdMolDescriptors.CalcNumRotatableBonds(mol)
                    _n_heavy_b = mol.GetNumHeavyAtoms()
                    if _n_rot_b > 12 or _n_heavy_b > 35:
                        scientific_warnings.append(aviso(
                            "MOLECULA_GRANDE", Severidad.INFO,
                            f"Molécula grande ({_n_heavy_b} átomos pesados, {_n_rot_b} enlaces "
                            f"rotables) — el docking será lento (búsqueda conformacional extensa). "
                            f"Si el tiempo es un límite, revisa el tamaño de la caja y la "
                            f"exhaustividad de Vina; reducirlos limita la búsqueda y puede "
                            f"cambiar las poses.",
                        ))
                    elif _n_rot_b > 8 or _n_heavy_b > 25:
                        scientific_warnings.append(aviso(
                            "MOLECULA_FLEXIBLE", Severidad.INFO,
                            f"Molécula con {_n_heavy_b} átomos pesados y {_n_rot_b} enlaces "
                            f"rotables — el docking puede tardar más de lo habitual. "
                            f"Si necesitas reducir el tiempo, revisa la caja y la "
                            f"exhaustividad de Vina; una búsqueda menor puede cambiar las poses.",
                        ))

                    # La detección sólo avisa; nunca cambia el motor elegido.
                    # Exige una cadena lineal legible de >=3 residuos estándar,
                    # no tres coincidencias SMARTS independientes.
                    from services.chemistry.peptides import es_peptido_lineal
                    from services.docking.protocolo import es_motor_peptidico
                    structure_looks_like_peptide = es_peptido_lineal(smiles)
                    is_peptide = es_motor_peptidico(peptide_docking_engine)
                    if structure_looks_like_peptide and not is_peptide:
                        scientific_warnings.append(aviso(
                            "PEPTIDO_LINEAL_DETECTADO", Severidad.INFO,
                            "Se detectó una secuencia peptídica lineal compatible con "
                            "ESMFold; se respeta el motor Vina solicitado. La ruta "
                            "ESMFold es exploratoria y no valida precisión de poses.",
                        ))

                    # Detectar metales
                    metals_in_mol = {atom.GetSymbol() for atom in mol.GetAtoms()} & {
                        "Fe", "Cu", "Zn", "Mn", "Co", "Ni", "Cr", "V", "Ti", "Mo", "W", "Pt"
                    }
                    is_organometallic = len(metals_in_mol) > 0
            except Exception as e:
                log.warning("Fallo al inspeccionar tipo de molécula", error=str(e))

            # Nivel 3: Docking Peptídico Autónomo
            if is_peptide:
                # Elegir el microestado antes de bifurcar: ESMFold y el respaldo
                # Vina reciben el mismo grafo, con su estado y hash persistidos.
                conformer_prepared = await generate_conformer(smiles, ph, **tautomer_kwargs)
                _estado_del_ligando_persistible = conformer_prepared.get("estado_del_ligando")
                peptide_smiles = conformer_prepared["canonical_smiles"]
                effective_smiles_hash = conformer_prepared["smiles_hash"]
                log.info({"event": "routing_to_level_3_peptide", "molecule_id": str(pipeline_params.molecule_id), "engine": peptide_docking_engine})
                await cache.set_job_progress(task_id, 40, "peptide_folding")

                from utils.file_handlers import StoragePath, download_pdb_from_rcsb
                from utils.local_storage import exists, read_text, write_text
                raw_path = StoragePath.target_raw(pipeline_params.target_pdb_id)

                temp_pdb_path = ""
                try:
                    if await exists(raw_path):
                        pdb_content = await read_text(raw_path)
                    else:
                        pdb_content = await download_pdb_from_rcsb(pipeline_params.target_pdb_id)
                        await write_text(raw_path, pdb_content)

                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8") as temp_pdb:
                        temp_pdb.write(pdb_content)
                        temp_pdb_path = temp_pdb.name
                except Exception as e:
                    log.warning("No se pudo preparar PDB temporal del target para Nivel 3", error=str(e))

                ml_res = None
                try:
                    if peptide_docking_engine == "colabfold" and temp_pdb_path:
                        from services.colabfold.service import get_colabfold_service
                        ml_res = await get_colabfold_service().predict(temp_pdb_path, peptide_smiles)
                    elif peptide_docking_engine == "esmfold-experimental" and temp_pdb_path:
                        from services.esmfold_pro.service import get_esmfold_pro_service
                        ml_res = await get_esmfold_pro_service().predict(
                            temp_pdb_path, peptide_smiles, grid_center=box_center, grid_size=box_size
                        )
                    elif temp_pdb_path:
                        from services.esmfold.service import get_esmfold_service
                        ml_res = await get_esmfold_service().predict(
                            temp_pdb_path, peptide_smiles, grid_center=box_center, grid_size=box_size
                        )
                finally:
                    # [FIX #2] Limpiar el archivo temporal del disco para evitar leak de espacio
                    if temp_pdb_path:
                        try:
                            os.unlink(temp_pdb_path)
                        except OSError:
                            pass

                _peptide_transfer_manifest = getattr(ml_res, "transfer_manifest", None) if ml_res else None
                if ml_res and ml_res.success and ml_res.poses:
                    log.info("Predicción de Nivel 3 completada con éxito")
                    from core.config import get_settings

                    settings = get_settings()
                    if settings.peptide_refinement_enabled:
                        scientific_warnings.append(aviso(
                            "PEPTIDE_REFINEMENT_NO_VALIDADO", Severidad.PRECAUCION,
                            "Se solicitó refinamiento peptídico, pero la ruta "
                            "OpenMM/Amber no está validada. Se conserva la pose "
                            "original de Vina sin marcarla como refinada.",
                        ))
                    # SCI-A-034: el SDF lleva las poses acopladas y sólo ellas, en
                    # el orden del resultado (`poses_acopladas_y_sdf`).
                    from services.docking.peptide_docking import (
                        peptide_poses_run_path, poses_acopladas_y_sdf,
                    )
                    _aceptadas, sdf_content, _cuentas = poses_acopladas_y_sdf(
                        ml_res.poses, peptide_smiles)
                    poses_path = peptide_poses_run_path(
                        effective_smiles_hash, pipeline_params.target_pdb_id, task_id,
                    )
                    if _aceptadas:
                        await write_text(poses_path, sdf_content)
                    from core.models import DockingPose, DockingResult

                    poses = []
                    _sin_afinidad = _cuentas["sin_afinidad"] + _cuentas["sin_geometria"]
                    _solo_plegado = _cuentas["solo_plegado"]
                    for _p in _aceptadas:
                        _rmsd = getattr(_p, "rmsd", None)
                        poses.append(DockingPose(
                            rank=_p.rank,
                            affinity=float(_p.vina_affinity_kcal_mol),
                            rmsd_lb=_rmsd,
                            rmsd_ub=_rmsd,
                        ))

                    _plddt = ml_res.best_confidence
                    _detalle = (
                        f"confianza estructural (pLDDT/100): {_plddt:.2f}"
                        if _plddt is not None else "confianza estructural no reportada"
                    )
                    if peptide_docking_engine == "colabfold" and ml_res.best_iptm is not None:
                        _detalle = f"ipTM de interfaz: {ml_res.best_iptm:.2f}"

                    if poses:
                        scientific_warnings.append(aviso(
                            "PEPTIDO_PLEGADO_Y_ACOPLADO", Severidad.PRECAUCION,
                            f"Ruta peptídica ({peptide_docking_engine}): la estructura "
                            f"la predijo el modelo y el acoplamiento lo hizo AutoDock "
                            f"Vina. La afinidad reportada es la de Vina, sin transformar. "
                            f"La {_detalle} describe el PLEGADO, no la unión, y no se "
                            f"convierte a kcal/mol. Resultado exploratorio: no hay "
                            f"benchmark de poses ni de repetibilidad para este protocolo.",
                        ))
                        if _sin_afinidad:
                            scientific_warnings.append(aviso(
                                "PEPTIDO_POSES_PARCIALES", Severidad.PRECAUCION,
                                f"{_sin_afinidad} de {len(ml_res.poses)} conformaciones "
                                "no pasaron por el acoplamiento y se descartaron en vez "
                                "de entrar con una afinidad inventada.",
                            ))
                    else:
                        # Estructura sí, acoplamiento no. `DockingResult` exige
                        # una afinidad y al menos una pose, y hace bien. Se cae
                        # al camino de sustitución de abajo, que corre Vina de
                        # verdad, en vez de rellenar el contrato con −4.0.
                        scientific_warnings.append(aviso(
                            "PEPTIDO_SIN_ACOPLAMIENTO", Severidad.CRITICA,
                            f"Ruta peptídica ({peptide_docking_engine}): se obtuvo la "
                            f"estructura plegada pero NINGUNA pose pasó por un motor de "
                            f"acoplamiento ({_solo_plegado} sin acoplar, {_sin_afinidad} "
                            f"sin afinidad). No se fabrica una afinidad: antes se "
                            f"devolvía −4.0 kcal/mol. La {_detalle} describe el plegado.",
                        ))
                        ml_res = None

                    if poses:
                        docking = DockingResult(
                            best_affinity=poses[0].affinity,
                            poses=poses,
                            poses_file_path=poses_path,
                            execution_provenance={
                                "poses_sha256": hashlib.sha256(
                                    sdf_content.encode("utf-8")).hexdigest(),
                                "box_center": None,
                                "box_size": None,
                                "source": "peptide_transfer",
                            },
                            parsing_source="sdf",
                            engine_efectivo="esmfold",
                            vina_version=getattr(ml_res, "vina_version", None),
                            vina_random_seed=getattr(ml_res, "vina_seed", None),
                            exhaustiveness_efectiva=getattr(ml_res, "vina_exhaustiveness", None),
                            scientific_warnings=scientific_warnings,
                            peptide_transfer_manifest=getattr(ml_res, "transfer_manifest", None),
                        )

                if docking is None:
                    # Dos motivos distintos llegan aquí: el servicio no
                    # respondió, o respondió con estructura y sin ninguna pose
                    # acoplada. El aviso ya dijo cuál; el mensaje no puede
                    # afirmar el primero cuando fue el segundo.
                    from services.docking.peptide_docking import motivo_de_la_sustitucion
                    msg, _respondio = motivo_de_la_sustitucion(ml_res, scientific_warnings)
                    log.warning("Fallo en Nivel 3, cayendo a Vina estándar", error=msg)
                    scientific_warnings.append(aviso(
                        "MOTOR_SUSTITUIDO", Severidad.CRITICA,
                        f"Fallo en Docking Peptídico ({msg}). Se usó AutoDock Vina como fallback.",
                    ))

            if docking is not None and _estado_del_ligando_persistible:
                from services.docking.ligand_state_warnings import avisos_estado_ligando
                scientific_warnings.extend(avisos_estado_ligando(
                    _estado_del_ligando_persistible
                ))

            # Nivel 4: Detección de compuestos organometálicos
            # [FIX] El warning anterior implicaba que xtb+AD4 estaban corriendo.
            # Honestidad: los detectamos, pero actualmente corremos Vina como aproximación.
            # AD4 + cargas GFN2-xTB está planificado para una versión futura.
            if is_organometallic and not is_peptide:
                log.info({"event": "metal_detected_vina_fallback", "molecule_id": str(pipeline_params.molecule_id), "metals": list(metals_in_mol)})
                scientific_warnings.append(aviso(
                    "METALES_SIN_MOTOR_ADECUADO", Severidad.PRECAUCION,
                    f"Metales de transición detectados: {list(metals_in_mol)}. "
                    "Se usa AutoDock Vina como aproximación. "
                    "El docking cuántico con GFN2-xTB + AutoDock 4 está en desarrollo "
                    "y se activará automáticamente en una versión futura. "
                    "Los resultados de afinidad pueden ser menos precisos para compuestos de coordinación.",
                ))

            # Si no se ejecutó Nivel 3, corremos Vina de forma estándar
            if docking is None:
                await cache.set_job_progress(task_id, 20, "conformer")
                conformer = conformer_prepared or await generate_conformer(smiles, ph, **tautomer_kwargs)
                log.info({
                    "event": "conformer listo para docking",
                    "conformer_path": conformer["conformer_path"]
                })

                # ── La molécula que se acopla no siempre es la que se escribió ──
                #
                # `generate_conformer` canonicaliza el tautómero y protona a pH
                # 7.4, y las dos operaciones ELIGEN una alternativa y descartan
                # el resto. Medido con aspirina:
                #
                #     entrada    CC(=O)Oc1ccccc1C(=O)O
                #     acoplada   CC(=O)Oc1ccccc1C(=O)[O-]     (2 tautómeros)
                #
                # Es decir: se acopló una especie con carga −1 que el usuario no
                # escribió. La sustitución es defendible —a pH fisiológico ese
                # ácido está ionizado—, pero hasta ahora no se declaraba en
                # ninguna parte, y el hash de entrada se recalcula sobre la forma
                # transformada. Un dossier que no dice qué especie se acopló no
                # describe la corrida que dice describir.
                _estado_ligando = conformer.get("estado_del_ligando") or {}
                _estado_del_ligando_persistible = _estado_ligando or None
                if _estado_ligando.get("cambio_respecto_a_la_entrada"):
                    _taut = _estado_ligando.get("tautomeria") or {}
                    _prot = _estado_ligando.get("protonacion") or {}
                    _detalles = []
                    if _taut.get("aplicada"):
                        _n = _taut.get("alternativas")
                        _detalles.append(
                            "se eligió el tautómero canónico de RDKit"
                            + (f" entre {_n} enumerados" if _n else "")
                        )
                    if _prot.get("aplicada"):
                        _n = _prot.get("alternativas")
                        # El aviso decía «se usó el primero», que fue cierto
                        # hasta que se midió que `[0]` no es el estado
                        # fisiológico —y que ni siquiera es el mismo entre
                        # corridas. Ahora lo elige `chem/ionizacion.py`; ver
                        # `test_microestado_de_protonacion.py`.
                        _sel = _prot.get("seleccion") or {}
                        if str(_sel.get("criterio", "")).startswith("cargas_esperadas_ph_"):
                            _como = (
                                f"se eligió el que coincide con los centros "
                                f"ionizados esperados a pH {_prot.get('ph')} "
                                f"(+{_sel.get('cationes_esperados')}/"
                                f"−{_sel.get('aniones_esperados')})"
                            )
                        elif _sel.get("criterio") == "grupo_reconocido_sin_pka":
                            _como = "grupo reconocido sin pKa verificado: menor carga formal, en revisión"
                        else:
                            _como = "sin centros reconocidos: selección alfabética reproducible, sin población estimada"
                        _detalles.append(
                            f"se protonó a pH {_prot.get('ph')} con {_prot.get('motor')}"
                            + (f" ({_n} estados devueltos, {_como})" if _n else "")
                        )
                    scientific_warnings.append(aviso(
                        "ESPECIE_ACOPLADA_DISTINTA", Severidad.PRECAUCION,
                        f"La especie acoplada no es la que se escribió: "
                        f"{_estado_ligando.get('smiles_entrada')} → "
                        f"{_estado_ligando.get('smiles_acoplado')}. "
                        + ("; ".join(_detalles) or "se aplicó una normalización")
                        + ". Las alternativas descartadas no se evaluaron.",
                    ))
                # Que dimorphite no esté también cambia la especie —deja la
                # neutra— y eso hay que decirlo igual, aunque no cambie el texto.
                elif (_estado_ligando.get("protonacion") or {}).get("motivo"):
                    scientific_warnings.append(aviso(
                        "SIN_CORRECCION_DE_PROTONACION", Severidad.PRECAUCION,
                        (_estado_ligando["protonacion"]["motivo"]),
                    ))

                from services.docking.ligand_state_warnings import avisos_estado_ligando
                scientific_warnings.extend(avisos_estado_ligando(_estado_ligando))

                # La identidad de la fila es la entrada validada; la especie
                # transformada pertenece a esta corrida y ya está en
                # ligand_state. Los archivos de poses/conformero usan el hash
                # local de la especie acoplada, sin secuestrar la fila ORM.
                if conformer.get("smiles_hash"):
                    effective_smiles_hash = conformer["smiles_hash"]

                await repository.set_molecule_status(pipeline_params.molecule_id, MoleculeStatus.DOCKING)
                await commit_with_retry(db)  # v1.7.4: transacción corta (docking)
                await cache.set_job_progress(task_id, 55, "docking")

                docking = await run_vina_docking(
                    smiles_hash=conformer["smiles_hash"],
                    target_pdb_id=pipeline_params.target_pdb_id,
                    target_chain=pipeline_params.target_chain,
                    site_chains=pipeline_params.target_site_chains,
                    target_center=box_center,
                    target_size=box_size,
                    hotspots=active_hotspots,
                    docking_engine=docking_engine,
                    cofactors_whitelist=pipeline_params.target_cofactors_whitelist,
                )

                if _peptide_transfer_manifest:
                    docking.peptide_transfer_manifest = _peptide_transfer_manifest

                # Unir advertencias si existen
                if scientific_warnings:
                    docking.scientific_warnings.extend(scientific_warnings)

            await cache.set_job_progress(task_id, 80, "scoring")

            # Un fallo del cliente ML no puede convertir una corrida Vina válida
            # en NameError durante la persistencia posterior.
            ml_result: dict | None = None
            # --- [NUEVO PASO] ML Rescoring Correction + GNN (Nivel 2) ---
            # Paso 1: XGBoost rescoring corrige la afinidad de Vina.
            # Paso 2: RTMScore GNN evalúa la geometría continua de la pose.
            gnn_score_value: float | None = None
            # La regresion de XGBoost, guardada aparte de la afinidad de Vina.
            ml_pki_value: float | None = None
            ml_pki_aplicada_value: bool | None = None
            shap_values_dict: dict | None = None
            shap_output_value: str | None = None
            shap_model_id_value: str | None = None
            gnn_attention_list: list | None = None
            gnn_attention_svg_data: str | None = None
            gnn_pharmacophores_dict: dict | None = None
            _target_pdb_path: str | None = None
            try:
                from services.docking.preparer import pdb_para_rescoring
                _target_pdb_path = str(pdb_para_rescoring(pipeline_params.target_pdb_id))
                target_family = pipeline_params.target_structural_family
                ml_result = await get_ml_rescore(
                    smiles=smiles,
                    target_pdb_path=pdb_para_rescoring(pipeline_params.target_pdb_id),
                    poses=[p.model_dump() for p in docking.poses],
                    properties=properties,
                    grid_center=list(box_center),
                    grid_size=list(box_size),
                    run_gnn=True,  # [FIX] Activa RTMScore GNN (Nivel 2)
                    target_family=target_family,
                )

                if not ml_result.get("fallback"):
                    # ═══════════════════════════════════════════════════════
                    # XGBoost YA NO PISA LA AFINIDAD DE VINA
                    # ═══════════════════════════════════════════════════════
                    #
                    # Auditoría del 2026-09-04. Aquí decía:
                    #
                    #     corrected_kcal = -1.36 * pki_a
                    #     docking.best_affinity = corrected_kcal
                    #
                    # y `repository.upsert_evaluation_result` guarda
                    # `affinity_kcal = docking.best_affinity`. Es decir: el
                    # número que se persiste, se certifica en Solana y se
                    # imprime en el PDF no era el score de Vina, era una
                    # regresión de pKi convertida a kcal. En una corrida real
                    # Vina dio −5.885 y lo guardado fue −5.305.
                    #
                    # Tres cosas están mal a la vez, y la tercera es la peor:
                    #
                    #   1. El dato primario se DESTRUYE. No se guardaba en
                    #      ningún sitio: no se podía recuperar ni comparar.
                    #   2. El aviso de `utils/scientific.py` sigue llamándolo
                    #      «afinidad en la escala de Vina», con un comentario
                    #      encima que explica con cuidado cómo NO sobreleer un
                    #      score de Vina — aplicado a un número que ya no lo es.
                    #   3. La sustitución ocurría también con el modelo FUERA
                    #      de su dominio de aplicabilidad. Medido en una
                    #      corrida: Mahalanobis 52.6 contra un umbral de 16.2,
                    #      y aun así el pKi reemplazaba a Vina.
                    #
                    # No son intercambiables. La función de Vina es empírica y
                    # está entrenada para ORDENAR poses; una regresión de pKi
                    # es otra cantidad, con otro error y otro dominio. Que
                    # ambas se escriban en kcal/mol no las hace la misma
                    # medida.
                    #
                    # Ahora se conservan las dos, por separado, y
                    # `docking.best_affinity` no lo toca nadie más que el
                    # acoplamiento.
                    pki_a = ml_result.get("score_a")
                    en_dominio = ml_result.get("in_applicability_domain")
                    if pki_a is not None and pki_a > 0:
                        ml_pki_value = float(pki_a)
                        ml_pki_aplicada_value = bool(en_dominio) if en_dominio is not None else None
                        log.info({
                            "event": "ml_rescoring_registrado",
                            "vina_kcal": docking.best_affinity,
                            "ml_pki": pki_a,
                            "ml_kcal_equivalent": -1.36 * pki_a,
                            "in_applicability_domain": en_dominio,
                            "nota": "no sustituye a affinity_kcal",
                        })
                        if en_dominio is False:
                            docking.scientific_warnings.append(aviso(
                                "ML_FUERA_DE_DOMINIO", Severidad.PRECAUCION,
                                f"La regresión de XGBoost (pKi {pki_a:.2f}, equivalente a "
                                f"{-1.36 * pki_a:.2f} kcal/mol) queda FUERA del dominio de "
                                "aplicabilidad del modelo: la molécula no se parece a las del "
                                "conjunto de entrenamiento. Se muestra como referencia, no "
                                "como predicción. La afinidad del caso es la de Vina.",
                            ))

                    # --- GNN: capturar score geométrico ---
                    raw_gnn = ml_result.get("gnn_score")
                    if raw_gnn is not None:
                        gnn_score_value = float(raw_gnn)
                        log.info({
                            "event": "gnn_score_captured",
                            "gnn_score": gnn_score_value,
                        })

                    # --- XAI: capturar explicabilidad ---
                    shap_values_dict = ml_result.get("shap_values")
                    shap_output_value = ml_result.get("shap_output")
                    shap_model_id_value = ml_result.get("shap_model_id")

                    # Warnings científicos del microservicio
                    if ml_result.get("warnings"):
                        # Vienen como cadenas desde el sidecar de rescoring, que
                        # es otro proceso con su propio contrato. Se etiquetan al
                        # cruzar la frontera —aquí— en vez de dejar que la
                        # interfaz adivine su severidad por la redacción.
                        docking.scientific_warnings.extend(
                            aviso("RESCORING_SIDECAR", Severidad.INFO, str(w))
                            for w in ml_result["warnings"]
                            if str(w).strip()
                        )

            except Exception as ml_err:
                log.warning({"event": "ml_rescoring_skipped", "error": str(ml_err)})

            # CL-GNN inference (post-docking, lightweight).
            # [A3] Sin fabricación: si la inferencia falla, el valor es None
            # (componente ausente) y el engine re-normaliza pesos / degrada.
            clgnn_prob_value = None
            try:
                from services.clgnn_inference import predict_clgnn

                # La POSE, no el SMILES. Antes se le pasaba sólo el SMILES y
                # la función se fabricaba un confórmero ETKDG en otro marco de
                # coordenadas: el «bolsillo» salía vacío y devolvía None
                # siempre. Ver el docstring de `predict_clgnn`.
                _mejor_pose = docking.poses[0] if docking.poses else None
                if _target_pdb_path and _mejor_pose is not None:
                    # En un hilo, como en `services/pipeline/runner.py` (2026-10-10).
                    clgnn_prob_value = await asyncio.to_thread(
                        predict_clgnn,
                        pipeline_params.molecule_smiles,
                        _target_pdb_path,
                        pose_sdf_path=docking.poses_file_path,
                        pose_pdbqt_block=getattr(_mejor_pose, "pdbqt_block", None),
                    )
            except Exception as clgnn_err:
                log.warning({
                    "event": "clgnn_inference_failed",
                    "molecule_id": str(pipeline_params.molecule_id),
                    "smiles": pipeline_params.molecule_smiles,
                    "error": str(clgnn_err)[:200],
                })
            if clgnn_prob_value is None:
                log.warning({
                    "event": "clgnn_unavailable",
                    "molecule_id": str(pipeline_params.molecule_id),
                    "reason": "predict_clgnn returned None",
                })

            # No attribution is published without model and input provenance.

            # Quantum features (xTB + MMFF94) — lightweight, only for certain targets
            quantum_score_value = None
            try:
                import sys
                _scripts_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
                if _scripts_path not in sys.path:
                    sys.path.insert(0, _scripts_path)
                from compute_quantum_features import compute_quantum_score
                quantum_score_value = compute_quantum_score(pipeline_params.molecule_smiles)
            except Exception as quantum_err:
                log.warning("quantum_features_failed_skipped",
                            molecule_id=str(pipeline_params.molecule_id)[:8],
                            error=str(quantum_err)[:200])
            if quantum_score_value is None:
                scientific_warnings.append(aviso(
                    "QUANTUM_NO_EVALUADO", Severidad.INFO,
                    "Índice cuántico no evaluado: faltan descriptores xTB verificables.",
                ))

            # UMS (Universal Metal Score) — scorer ortogonal SMARTS-only para
            # metaloenzimas (w5 del M5_gated, ver scoring/ums.py + PAPER_UMS.md).
            # Sin xTB verificable se abstiene: 0.5 no es una medición.
            ums_score_value = None
            if quantum_score_value is not None:
                try:
                    from scoring.ums import compute_universal_metal_score
                    _ums, _ums_feats = compute_universal_metal_score(
                        pipeline_params.molecule_smiles,
                        molchamb_score=quantum_score_value,
                        target_family=pipeline_params.target_structural_family,
                    )
                    ums_score_value = _ums
                except Exception as ums_err:
                    log.debug("ums_compute_failed", error=str(ums_err)[:200])

            # Ruta histórica de ΔE potencial GBn2+ACE (ε_in=1, sin entropía).
            # No es ΔG. La guardia inicial rechaza enable_mmgbsa=True con
            # MMGBSA_NO_DISPONIBLE; este bloque se conserva sólo para trazabilidad.
            # El motivo original para ejecutarlo en segundo plano era:
            # OpenMM MM-GBSA tarda >180s en CPU (sin GPU) — bloquear el
            # pipeline hasta terminarlo degrada la UX. Por eso:
            #   - enable_mmgbsa=False → mmgbsa_score=None, sin subprocess.
            #   - enable_mmgbsa=True  → se lanza un SUBPROCESS en background;
            #     el pipeline reporta "done" INMEDIATAMENTE (el resultado se
            #     persiste con mmgbsa_score=None) y el subprocess actualiza el
            #     score en DB/cache cuando termina. El proceso se registra en
            #     registro task-scoped para que el botón Cancelar afecte sólo
            #     a los hijos de esta evaluación.
            #
            # v1.7.1 FIX ESTABILIDAD: subprocess con timeout real (antes
            # run_in_executor + wait_for dejaba threads OpenMM huérfanos
            # quemando ~1288% CPU).
            mmgbsa_score_value = None
            if enable_mmgbsa:
                try:
                    import asyncio as _asyncio
                    import os as _os
                    import sys as _sys

                    _embed_python = _sys.executable
                    _wrapper = _os.path.join(
                        _os.path.dirname(__file__), "mmgbsa_subprocess.py"
                    )
                    _target_pdb = str(pdb_para_rescoring(pipeline_params.target_pdb_id))

                    async def _launch_mmgbsa_background(mol_id, tgt_pdb, smiles_str, poses_sdf=None):
                        """Corre MM-GBSA en subprocess y persiste el resultado.
                        FIX v2.1 (2026-08-04): poses_sdf es el archivo .sdf con
                        las poses reales de Vina → el subprocess usa
                        compute_mmgbsa_from_pose (pose real) en vez de
                        compute_mmgbsa (conformación arbitraria de RDKit que
                        daba ΔG absurdos como -27983 kcal/mol).
                        """
                        # `--poses` y no un posicional: el SDF caia en la
                        # posicion de `max_iter` y el wrapper moria con
                        # `ValueError: invalid literal for int()`, asi que
                        # MM-GBSA no corrio nunca en este camino. Ver el bloque
                        # de argumentos en `mmgbsa_subprocess.py`.
                        from utils.local_storage import path_for as _pose_path_for
                        _args = [tgt_pdb, smiles_str]
                        if poses_sdf:
                            _args += ["--poses", str(_pose_path_for(poses_sdf))]
                        _proc = await _asyncio.create_subprocess_exec(
                            _embed_python, _wrapper, *_args,
                            stdout=_asyncio.subprocess.PIPE,
                            stderr=_asyncio.subprocess.DEVNULL,
                            creationflags=BANDERAS_SIN_VENTANA,
                        )
                        register_process(task_id, "mmgbsa", _proc)
                        try:
                            _stdout_b, _ = await communicate_managed(_proc, timeout=300.0)
                        except _asyncio.TimeoutError:
                            log.warning("mmgbsa_bg_timeout_kill",
                                        molecule_id=str(mol_id)[:8])
                            async with get_db_session() as _db:
                                await Repository(_db).append_run_addendum(
                                    mol_id, task_id, "mmgbsa",
                                    {"mmgbsa_score": None, "status": "timeout",
                                     "reason": "El subproceso excedió 300 segundos"},
                                )
                                await _db.commit()
                            try:
                                _proc.kill()
                            except Exception:
                                pass
                            await _proc.wait()
                            return
                        finally:
                            try:
                                unregister_process(task_id, "mmgbsa", _proc)
                            except Exception:
                                pass
                        if _stdout_b:
                            try:
                                _mmgbsa_result = json.loads(
                                    _stdout_b.decode("utf-8", "replace"))
                                _score = _mmgbsa_result.get("mmgbsa") if _proc.returncode == 0 else None
                                if _score is None:
                                    log.warning("mmgbsa_not_evaluated", task_id=task_id,
                                                error=_mmgbsa_result.get("error"))
                                log.info("mmgbsa_bg_computed",
                                         molecule_id=str(mol_id)[:8],
                                         mmgbsa=round(_score, 2) if _score else None,
                                         elapsed_s=_mmgbsa_result.get("time_sec"))
                                # Sólo se publica un valor si también quedó en la BD.
                                persisted = False
                                try:
                                    async with get_db_session() as _db:
                                        _repo = Repository(_db)
                                        if not _is_desktop_job_cancelled(task_id):
                                            await _repo.append_run_addendum(
                                                mol_id, task_id, "mmgbsa",
                                                {"mmgbsa_score": _score,
                                                 "status": "evaluated" if _score is not None else "unavailable",
                                                 "reason": _mmgbsa_result.get("error") if _score is None else None},
                                            )
                                            await _repo.update_evaluation_for_task(
                                                mol_id, task_id, mmgbsa_score=_score,
                                            )
                                            await _db.commit()
                                            persisted = True
                                except Exception as _db_err:
                                    log.error("mmgbsa_bg_db_update_failed",
                                              error=str(_db_err)[:200])
                                try:
                                    await cache.set_job_progress(
                                        task_id, 100, "done",
                                        extra={"mmgbsa_score": _score} if persisted else
                                              {"mmgbsa_status": "persistence_failed"})
                                except Exception:
                                    pass
                            except Exception as _json_err:
                                log.warning("mmgbsa_bg_json_error",
                                            error=str(_json_err)[:200])

                    from uuid import UUID as _UUID
                    _mol_uuid = pipeline_params.molecule_id if isinstance(pipeline_params.molecule_id, _UUID) else _UUID(str(pipeline_params.molecule_id))
                    # FIX v2.1: pasar el SDF de poses al subprocess para que
                    # MM-GBSA use la pose real de docking (no conformación
                    # arbitraria de RDKit que daba -27983 kcal/mol).
                    _poses_sdf_qh = None
                    if docking is not None and getattr(docking, "poses_file_path", None):
                        _poses_sdf_qh = docking.poses_file_path
                    _mmgbsa_job = _asyncio.ensure_future(_launch_mmgbsa_background(
                        _mol_uuid, _target_pdb, pipeline_params.molecule_smiles,
                        _poses_sdf_qh,
                    ))
                    def _report_mmgbsa_failure(completed):
                        if not completed.cancelled() and completed.exception() is not None:
                            log.error("mmgbsa_background_failed", task_id=task_id,
                                      error=str(completed.exception()))
                    _mmgbsa_job.add_done_callback(_report_mmgbsa_failure)
                    log.info("mmgbsa_bg_launched", molecule_id=str(pipeline_params.molecule_id)[:8])
                except Exception as mmgbsa_err:
                    log.debug("mmgbsa_bg_launch_failed", error=str(mmgbsa_err)[:200])

            # Leer specificity_floor del target (v1.7.3: desde snapshot, no ORM)
            target_specificity_floor = pipeline_params.specificity_floor
            target_family_value = pipeline_params.target_structural_family

            breakdown = calculate_score_breakdown(
                docking,
                properties,
                is_control=is_control,
                target_hotspots=active_hotspots,
                target_hotspots_source=pipeline_params.target_hotspots_source,
                affinity_threshold=pipeline_params.affinity_threshold,
                specificity_floor=target_specificity_floor,
                gnn_score=gnn_score_value,
                xgb_prob=ml_result.get("classifier_prob") if ml_result and not ml_result.get("fallback") else None,
                clgnn_prob=clgnn_prob_value,
                mmgbsa_score=mmgbsa_score_value,
                quantum_score=quantum_score_value,
                ums_score=ums_score_value,
                target_family=target_family_value,
            )

            # Historial completo: TODAS las evaluaciones se registran (score
            # bajo o no). El historial es la base del usuario — borrar por score
            # bajo destruía el historial y rompía el re-docking (cambio de
            # política: el botón "guardar" solo promueve a moldex, no gatea
            # la persistencia).
            # --- [NUEVO] Auditoría Científica Profunda ---
            # El régimen de tamaño decide para qué están calibrados los
            # umbrales que la auditoría aplica (eficiencia de ligando, corte de
            # afinidad débil). Se deriva de las mismas magnitudes que ya viajan
            # en `properties`, con la misma función que usa el validador, para
            # que las dos partes no puedan discrepar. Ver `chem/regimenes.py`.
            from chem.regimenes import clasificar as _clasificar_regimen

            _reg = _clasificar_regimen(
                properties.molecular_weight or 0.0, properties.heavy_atom_count or 0
            )
            deep_warnings = audit_scientific_quality(
                affinity_kcal=docking.best_affinity,
                heavy_atom_count=properties.heavy_atom_count,
                log_p=properties.log_p,
                docking_poses=[p.model_dump() for p in docking.poses],
                hotspots=active_hotspots,
                hotspots_hit=docking.hotspots_hit,
                regimen=_reg.regimen.value,
                cumple_ro3=_reg.cumple_ro3,
                hotspots_source=pipeline_params.target_hotspots_source,
            )
            # Combinamos advertencias técnicas con las científicas de valor añadido
            docking.scientific_warnings.extend(deep_warnings)

            # ── El protocolo, que este camino no sellaba ─────────────────
            #
            # `docking_protocol` sólo lo escribía `services/pipeline/runner.py`
            # (modo PRO). Aquí no aparecía ni una vez, y como el argumento es
            # opcional y el repositorio no sobrescribe con `None`, la columna
            # quedaba NULL sin error ni aviso — pero el dossier la lee. Toda
            # evaluación del modo normal salía con la sección del protocolo
            # vacía y sin decir por qué.
            #
            # Este camino no genera ensemble: `generate_conformer` devuelve uno.
            # Se declara así en vez de omitirlo, que es lo que hace legible la
            # diferencia con una corrida PRO de treinta.
            from utils.structural import normalize_hotspots as _normalizar_hotspots

            docking_protocol = construir_protocolo(
                docking=docking,
                peptide_engine=peptide_docking_engine,
                docking_engine=docking_engine,
                conformer_ctx={"conformers_requested": 1, "conformers_generated": 1},
                # Los residuos que ENTRARON en el análisis de contactos, no los del catálogo.
                residuos_de_referencia=declarar_residuos_de_referencia(
                    activos=active_hotspots,
                    elegidos=pipeline_params.custom_hotspots,
                    catalogo=_normalizar_hotspots(pipeline_params.target_hotspots_base),
                    fuente_del_catalogo=pipeline_params.target_hotspots_source,
                ),
            )

            # ── M5-Zn: el protocolo de metaloenzimas de zinc ─────────────
            #
            # Estuvo implementado y SIN LLAMADOR: `zinc.py::calcular` no lo
            # invocaba nadie, y el dossier llego a decir «calculado con el
            # perfil exacto» sobre un calculo que no ocurria. Se ejecuta aqui,
            # se persiste, y el dossier LEE lo persistido.
            #
            # Devuelve `None` cuando la corrida no es un caso de metal. Cuando
            # si lo es, devuelve siempre un estado —incluso si no hay score—
            # porque «no se pudo puntuar y este es el motivo» es informacion.
            #
            # Envuelto: un fallo aqui no puede tumbar un acoplamiento que ya
            # termino. Si falla, las cuatro columnas quedan a NULL, que se lee
            # como «no se ejecuto» y nunca como un score de cero.
            m5_columnas: dict = {}
            try:
                from services.pipeline.protocols.m5.ejecucion import ejecutar as ejecutar_m5

                _salida_m5 = ejecutar_m5(
                    smiles=pipeline_params.molecule_smiles,
                    target_pdb_id=pipeline_params.target_pdb_id,
                    target_family=target_family_value,
                    vina_kcal_mol=docking.best_affinity if docking else None,
                    xgb_prob=ml_result.get("classifier_prob") if ml_result and not ml_result.get("fallback") else None,
                    xgb_in_domain=ml_result.get("in_applicability_domain") is True if ml_result else False,
                    xgb_features_ok=bool(ml_result and ml_result.get("classifier_prob") is not None and not ml_result.get("fallback")),
                    # GNN-D no tiene productor en produccion; solo CA2 la pide y
                    # por eso CA2 devuelve NOT_EVALUATED_MISSING_COMPONENT. El
                    # §4.1 del ADR prohibe sustituirla por CL-GNN.
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

            _peptide_transfer = getattr(docking, "peptide_transfer_manifest", None)
            if _peptide_transfer:
                _estado_del_ligando_persistible = {
                    **(_estado_del_ligando_persistible or {}),
                    "peptide_transfer": _peptide_transfer,
                }

            await repository.upsert_evaluation_result(
                molecule_id=pipeline_params.molecule_id,
                properties=properties,
                docking=docking,
                scores={
                    **breakdown.model_dump(),
                    **m5_columnas,
                    "gnn_score": gnn_score_value,  # persistir en DB
                    # La regresión de XGBoost, en su propia unidad y en su
                    # propia columna. Antes se convertía a kcal y se escribía
                    # sobre `affinity_kcal`; ver el bloque de arriba.
                    "ml_pki": ml_pki_value,
                    "ml_pki_aplicada": ml_pki_aplicada_value,
                    "shap_values": shap_values_dict,
                    "shap_output": shap_output_value,
                    "shap_model_id": shap_model_id_value,
                    "gnn_attention": gnn_attention_list,
                    "gnn_attention_svg": gnn_attention_svg_data,
                    "gnn_pharmacophores": gnn_pharmacophores_dict,
                },
                is_control=is_control,
                task_id=task_id,
                # La especie que de verdad se acopló, con sus alternativas
                # descartadas. Sin esto sólo viajaba como aviso de texto.
                ligand_state=_estado_del_ligando_persistible,
                docking_protocol=docking_protocol,
            )
            evaluation_run = await repository.snapshot_evaluation_run(
                pipeline_params.molecule_id, task_id
            )
            await repository.set_molecule_status(pipeline_params.molecule_id, MoleculeStatus.EVALUATED)
            await commit_with_retry(db)  # v1.7.4: transacción corta (resultado final)

            result = await repository.get_evaluation_result(pipeline_params.molecule_id)
            await cache.set_job_progress(task_id, 100, "done")

            # MolGraph: indexar evaluacion en el knowledge graph quimico
            try:
                from services.molgraph import add_evaluation_node
                add_evaluation_node(
                    smiles=pipeline_params.molecule_smiles,
                    target_pdb=pipeline_params.target_pdb_id,
                    affinity=docking.best_affinity if docking else None,
                    score=breakdown.total_score if breakdown else None,
                    properties={
                        "target_name": pipeline_params.target_name or pipeline_params.target_pdb_id,
                    },
                    # MOLCHAT-BE-009: el grafo dejó de ser un archivo compartido.
                    # Una evaluación se registra en el almacén de quien la
                    # lanzó, no en el corpus público que leen todas las cuentas.
                    user_id=user_id,
                )
            except Exception:
                pass

            return {
                "task_id": task_id,
                "molecule_id": str(pipeline_params.molecule_id),
                "smiles_hash": pipeline_params.molecule_smiles_hash,
                "target_pdb_id": pipeline_params.target_pdb_id,
                "total_score": breakdown.total_score,
                "best_affinity": docking.best_affinity,
                "evaluation_result_id": str(result.id) if result else None,
                "evaluation_run_id": str(evaluation_run.id),
            }

        except Exception as exc:
            # ── Error recovery: garantiza que la molécula no quede en
            # estado intermedio (VALIDATED/DOCKING) sin explicación. ──────
            detail = getattr(exc, 'detail', None)
            # Forzar que detail sea string para logging y DB
            if detail is None:
                detail_str = '(sin detail)'
            elif not isinstance(detail, str):
                detail_str = str(detail)
            else:
                detail_str = detail
            log.error(
                "pipeline de evaluación falló",
                task_id=task_id,
                molecule_id=str(pipeline_params.molecule_id),
                error=str(exc),
                error_type=type(exc).__name__,
                error_detail=detail_str,
            )
            try:
                await repository.set_molecule_status(
                    pipeline_params.molecule_id, MoleculeStatus.FAILED
                )
                await repository.upsert_evaluation_result(
                    molecule_id=pipeline_params.molecule_id,
                    error_message=f"{type(exc).__name__}: {exc}\nDetail: {detail_str}",
                    task_id=task_id,
                )
                # v1.7.4 FIX: commit EXPLÍCITO antes del raise. Antes, el
                # rollback del context manager (get_db_session) revertía este
                # persist y el historial de fallos NUNCA se guardaba.
                await commit_with_retry(db)
                # El registro del fallo queda en el historial (política:
                # no se borra nada automáticamente — el usuario decide)
            except Exception as db_exc:
                log.error(
                    "no se pudo persistir estado FAILED en DB",
                    molecule_id=str(pipeline_params.molecule_id),
                    db_error=str(db_exc),
                )
            raise exc


async def submit_recorded_evaluation(*, db, client_ip=None, **configuration):
    """Persiste configuración y propietario ANTES de aceptar/enqueue."""
    from core.models import EvaluationRequestORM
    task_id = str(_uuid_mod.uuid4())
    record = EvaluationRequestORM(
        task_id=task_id, owner_id=configuration.get("user_id") or "demo",
        client_ip=client_ip, configuration_json=configuration, status="PENDING",
    )
    db.add(record)
    await commit_with_retry(db)
    try:
        return _submit_evaluation_desktop(task_id=task_id, **configuration)
    except Exception as exc:
        record.status = "FAILURE"
        record.error_message = f"No se pudo encolar: {exc}"
        record.finished_at = datetime.now(UTC)
        await commit_with_retry(db)
        raise


async def _record_job_terminal(task_id, status, error=None):
    from sqlalchemy import update
    from core.models import EvaluationRequestORM
    try:
        async with get_db_session() as db:
            statement = update(EvaluationRequestORM).where(EvaluationRequestORM.task_id == task_id)
            if status == "SUCCESS":
                statement = statement.where(EvaluationRequestORM.status != "FAILURE")
            await db.execute(statement.values(status=status, error_message=error, finished_at=datetime.now(UTC)))
            await commit_with_retry(db)
    except Exception as exc:
        log.error("evaluation_request_terminal_failed", task_id=task_id, error=str(exc))


def submit_evaluation_job(
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = None,
    pipeline_config: dict | None = None,
    ph: float | None = None,
) -> _DesktopTask:
    """
    Encola una tarea de evaluacion en el dispatcher local DESKTOP.

    Antes existía una rama CLOUD (Celery apply_async). Eliminada en F-02:
    MolDesign es desktop-only y el submit local es EL único camino.
    """
    return _submit_evaluation_desktop(
        smiles=smiles,
        target_pdb_id=target_pdb_id,
        ph=ph,
        molecule_name=molecule_name,
        is_control=is_control,
        user_id=user_id,
        grid_center=grid_center,
        grid_size=grid_size,
        custom_hotspots=custom_hotspots,
        peptide_docking_engine=peptide_docking_engine,
        pipeline_config=pipeline_config,
    )


def _submit_evaluation_desktop(
    smiles: str,
    target_pdb_id: str,
    molecule_name: str | None = None,
    is_control: bool = False,
    user_id: str | None = None,
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] | None = None,
    custom_hotspots: list[str] | None = None,
    peptide_docking_engine: str | None = None,
    pipeline_config: dict | None = None,
    task_id: str | None = None,
    ph: float | None = None,
) -> _DesktopTask:
    task_id = task_id or str(_uuid_mod.uuid4())
    task = _DesktopTask(task_id)

    # Clean old jobs (24h TTL)
    expired = _clean_old_desktop_jobs()
    if expired > 0:
        log.debug("desktop_jobs_cleaned", expired=expired)

    # Extraer config del pipeline_config
    run_admet_ai = False
    if pipeline_config:
        stage_params = pipeline_config.get("stage_params", {})
        props_params = stage_params.get("properties", {})
        run_admet_ai = admet_requested(props_params)

    with _desktop_lock:
        _desktop_jobs[task_id] = {
            "status": "PENDING",
            "progress": 0,
            "result": None,
            "error": None,
            "cancel_requested": False,
            "started_at": datetime.now(UTC).isoformat(),
        }

    # v1.8.1: Registrar job_status en el cache INMEDIATAMENTE. Sin esto, si el
    # semáforo está retenido por otra evaluación, el job espera en silencio y
    # el frontend ve "Procesando" sin progreso (job_status cache miss) → el
    # usuario cancela a los 60s pensando que falló. Con el registro temprano,
    # el frontend siempre ve PENDING y el watchdog puede vigilar.
    try:
        import asyncio as _aw
        try:
            _aw.get_running_loop()
        except RuntimeError:
            pass
        # set en fire-and-forget — no bloquear el submit
        async def _seed_job_status():
            await cache.set(f"job_status:{task_id}", {
                "task_id": task_id,
                "status": "PENDING",
                "progress": 0,
                "result": None,
                "error": None,
                "started_at": datetime.now(UTC).isoformat(),
            }, ttl=86400)
        try:
            _aw.get_running_loop().create_task(_seed_job_status())
        except RuntimeError:
            pass
    except Exception as _seed_err:
        log.debug("job_status_seed_failed", task_id=task_id, error=str(_seed_err)[:80])

    # Execute on the main event loop via asyncio.create_task
    # (avoids ThreadPoolExecutor which creates a new event loop
    #  incompatible with aiosqlite's connection ownership)
    # Serialización DESKTOP: max DESKTOP_MAX_CONCURRENCY evaluación a la vez.
    # Las demás esperan en cola — evita "database is locked" por escritores
    # concurrentes (SQLite WAL: 1 escritor a la vez).
    async def _run_serialized_wrapper():
        import time

        acquired = False
        with _desktop_lock:
            job = _desktop_jobs.get(task_id)
            if job is not None:
                job["async_task"] = asyncio.current_task()

        async def fail(reason):
            with _desktop_lock:
                job = _desktop_jobs.get(task_id)
                if job is None:
                    return
                if job.get("cancel_requested"):
                    reason = job.get("error") or reason
                job.update(status="FAILURE", error=reason,
                           finished_at=datetime.now(UTC).isoformat())
                molecule_id = job.get("molecule_id")
            await _record_job_terminal(task_id, "FAILURE", reason)
            cancel_active_mmgbsa(task_id)
            cancel_active_selectivity(task_id)
            cancel_active_structural_evidence(task_id)
            await _persist_molecule_failed(
                molecule_id, reason, task_id=task_id, overwrite_terminal_status=True
            )
            await cache.push_stage_event(task_id, {
                "type": "pipeline_error", "error": reason,
                "timestamp": datetime.now(UTC).isoformat(),
            })

        try:
            # No dejar un acquire bloqueado en un hilo: cancelar to_thread no
            # cancela ese hilo y podía robar un permiso después de terminar el job.
            deadline = time.monotonic() + EVAL_QUEUE_WAIT_TIMEOUT_S
            while not acquired:
                if _is_desktop_job_cancelled(task_id):
                    await fail("Cancelado por el usuario")
                    return
                acquired = _desktop_eval_semaphore.acquire(blocking=False)
                if not acquired:
                    if time.monotonic() >= deadline:
                        await fail(f"Cola de evaluaciones saturada: no se pudo iniciar en {EVAL_QUEUE_WAIT_TIMEOUT_S}s.")
                        return
                    await asyncio.sleep(0.05)

            # El watchdog anterior ya medía tiempo total (no heartbeat). Se
            # conserva su límite, pero ahora cancela y espera la limpieza del hijo.
            result = await asyncio.wait_for(
                _run_full_evaluation_async(
                    task_id=task_id, smiles=smiles, target_pdb_id=target_pdb_id,
                    ph=ph,
                    molecule_name=molecule_name, is_control=is_control,
                    user_id=user_id, grid_center=grid_center, grid_size=grid_size,
                    custom_hotspots=custom_hotspots,
                    peptide_docking_engine=peptide_docking_engine,
                    pipeline_config=pipeline_config, run_admet_ai=run_admet_ai,
                    enable_mmgbsa=bool((pipeline_config or {}).get("pro_mmgbsa", False)),
                ),
                timeout=EVAL_WATCHDOG_TIMEOUT_S,
            )
            if result.get("error"):
                await fail(str(result["error"]))
                return
            with _desktop_lock:
                job = _desktop_jobs.get(task_id)
                failed = bool(job and job.get("status") == "FAILURE")
                if job is not None and not failed:
                    job.update(status="SUCCESS", progress=100, result=result,
                               finished_at=datetime.now(UTC).isoformat())
            if failed:
                await fail("Evaluación cancelada o interrumpida")
                return
            await _record_job_terminal(task_id, "SUCCESS")
            # (Fase 6.6) Aquí se anotaba la corrida en la memoria del asistente
            # interno (`memory_store.store_evaluation`, catálogo `ai_catalog`
            # para su LLM). Sin asistente interno no hay lector: el historial
            # de plataforma (`history`) es el registro que queda.
        except asyncio.CancelledError:
            await fail("Evaluación interrumpida o cancelada")
            raise
        except TimeoutError:
            await fail(f"Timeout: evaluación excedió {EVAL_WATCHDOG_TIMEOUT_S}s de ejecución.")
        except Exception as exc:
            log.exception("Error en tarea DESKTOP", task_id=task_id)
            await fail(f"{type(exc).__name__}: {exc}")
        finally:
            if acquired:
                _desktop_eval_semaphore.release()
            with _desktop_lock:
                job = _desktop_jobs.get(task_id)
                if job is not None:
                    job.pop("async_task", None)


    import asyncio as _asyncio
    try:
        _ = _asyncio.get_running_loop()
        _asyncio.create_task(_run_serialized_wrapper())
    except RuntimeError:
        # No running loop (should not happen in FastAPI context)
        executor = _get_desktop_executor()
        executor.submit(lambda: _asyncio.run(_run_serialized_wrapper()))
    return task



async def await_recorded_evaluation(task_id: str, *, timeout_s: float | None = None) -> JobStatus:
    """Wait for a recorded desktop job; keep the dispatcher in charge of work."""
    import time

    timeout_s = timeout_s or EVAL_QUEUE_WAIT_TIMEOUT_S + EVAL_WATCHDOG_TIMEOUT_S + 10
    deadline = time.monotonic() + timeout_s
    while True:
        state = await get_job_status(task_id)
        if state.status in {"SUCCESS", "FAILURE"}:
            return state
        if time.monotonic() >= deadline:
            request_desktop_job_cancellation(task_id)
            raise TimeoutError("La evaluación excedió el plazo de ejecución.")
        await asyncio.sleep(0.25)


async def get_job_status(task_id: str) -> JobStatus:
    """Contrato público de polling del dispatcher desktop."""
    return await _get_job_status_desktop(task_id)


async def _get_job_status_desktop(task_id: str) -> JobStatus:
    """Alias interno conservado para consumidores históricos del dispatcher."""
    return await get_desktop_job_status(
        task_id,
        jobs=_desktop_jobs,
        lock=_desktop_lock,
        cache=cache,
    )
