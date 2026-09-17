"""
Endpoints del flujo de evaluación del MVP.
"""

from __future__ import annotations

import uuid

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from chem.validator import validate_smiles_or_raise
from core.database import get_db
from core.models import EvaluationResultRead, JobStatus, UserORM, _coerce_hotspots
from db.repository import Repository
from utils.logger import bind_context, get_logger
from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import puede_operar, require_owned_molecule
from services.targets.access import get_target_for_user
from services.targets.calibracion import estado_de_calibracion
from services.pipeline.registry import admet_requested
from api.routers.evaluation_cohort_runs import cohort_router as evaluation_cohort_runs_on_cohorts
from api.routers.evaluation_cohort_runs import router as evaluation_cohort_runs_router
from api.routers.evaluation_cohorts import router as evaluation_cohorts_router
from api.routers.evaluation_dossier import router as evaluation_dossier_router
from api.routers.evaluation_files import router as evaluation_files_router
from api.routers.evaluation_reports import router as evaluation_reports_router

log = get_logger(__name__)

router = APIRouter(prefix="/evaluation", tags=["Evaluación científica"])
router.include_router(evaluation_files_router)
router.include_router(evaluation_reports_router)
# El dossier vive bajo /evaluation/dossier: depende del CASO, no del sello en
# cadena. Las rutas /blockchain/certificate se conservan como legado.
router.include_router(evaluation_dossier_router)
# La cohorte vive bajo /evaluation/cohorts. NO sustituye a /evaluation/batch en
# este sprint: el Batch histórico sigue publicado y la interfaz actual lo usa.
router.include_router(evaluation_cohorts_router)
# La EJECUCIÓN de una cohorte cuelga aparte: abrir una corrida es una acción
# sobre la cohorte (/cohorts/{id}/runs), pero consultarla, reanudarla o
# cancelarla son acciones sobre la CORRIDA, que tiene vida propia y sobrevive a
# los reinicios (/cohort-runs/{id}).
router.include_router(evaluation_cohort_runs_on_cohorts)
router.include_router(evaluation_cohort_runs_router)


from slowapi.util import get_remote_address

def get_real_ip(request: Request) -> str:
    """
    Obtiene la IP de forma segura delegando al utilitario de slowapi.
    Evita vulnerabilidad de IP spoofing mediante X-Forwarded-For crudo.
    """
    return get_remote_address(request)


# ── Inventario de motores ────────────────────────────────────────────────────
#
# ENG-001. El menú de opciones avanzadas ofrecía siete motores sin comprobar
# ninguno. Seis de ellos no existen en una instalación limpia: QuickVina 2 no se
# empaqueta, y DiffDock, ESMFold, ESMFold Pro/RFdiffusion y ColabFold son
# clientes HTTP de servicios externos que este instalador no levanta ni trae.
#
# Ofrecer un motor que no se puede ejecutar no es un detalle de interfaz: el
# investigador elige un método, la corrida sale por otro —o la bloquea el
# preflight después de configurarlo todo— y la promesa del menú no se cumple.
#
# Este inventario NO hace red. Dice qué puede ejecutar ESTA instalación:
# para un binario, si está; para un servicio externo, si hay URL configurada.
# Comprobar que además responde es otra pregunta, con su propio botón.

MOTORES_DE_SERVICIO_EXTERNO = {
    "diffdock": ("DiffDock", "diffdock_api_url", "docking"),
    "esmfold": ("ESMFold", "esmfold_api_url", "peptido"),
    "esmfold-pro": ("ESMFold Pro", "esmfold_pro_api_url", "peptido"),
    "esmfold-experimental": ("RFdiffusion", "esmfold_pro_api_url", "peptido"),
    "colabfold": ("ColabFold", "colabfold_api_url", "peptido"),
}


def inventario_de_motores() -> dict[str, list[dict]]:
    """Qué motores puede ejecutar de verdad esta instalación, y por qué no los demás."""
    from core.config import get_settings
    from services.docking import preparer

    settings = get_settings()

    def _binario(ruta: str) -> bool:
        try:
            return bool(preparer.resolve_executable(ruta))
        except Exception:
            return False

    vina_ok = _binario(settings.vina_executable_path)
    qvina_ok = _binario(settings.qvina2_executable_path)

    docking = [
        {
            "id": "vina",
            "etiqueta": "AutoDock Vina 1.2.7",
            "familia": "docking",
            "estado": "listo" if vina_ok else "error",
            "disponible": vina_ok,
            "accion": None,
            "bytes_descarga": 0,
            "archivos_faltantes": [],
            "dependencias_faltantes": [],
            "modulo_launcher": None,
            "requiere": "binario_empaquetado",
            "motivo": None if vina_ok else (
                "No se encontró el ejecutable de AutoDock Vina que el instalador "
                "empaqueta. Sin él no se puede ejecutar ninguna corrida."
            ),
        },
        {
            "id": "qvina2",
            "etiqueta": "QuickVina 2",
            "familia": "docking",
            "estado": "listo" if qvina_ok else "no_instalado",
            "disponible": qvina_ok,
            "accion": None,
            "bytes_descarga": 0,
            "archivos_faltantes": [],
            "dependencias_faltantes": [],
            "modulo_launcher": None,
            "requiere": "binario_externo",
            "motivo": None if qvina_ok else (
                "QuickVina 2 no viene con esta versión y no se encontró en el "
                "sistema. El preflight bloquea la corrida antes de ejecutarla, "
                "porque caer a Vina en silencio cambiaría el método sin decirlo."
            ),
        },
    ]

    peptido: list[dict] = []

    # Los motores DESCARGABLES tienen su propio catálogo: pesan de más para el
    # instalador, se bajan bajo demanda y viven en un proceso aparte. Su estado
    # no es un sí/no —«no instalado», «instalado y apagado», «listo» y «faltan
    # dependencias» llevan a acciones distintas— y por eso lo calcula
    # `services.motores` en un solo sitio.
    from services.motores import POR_ID as MOTORES_DESCARGABLES
    from services.motores import estados_de_motores_descargables

    descargables = {e["id"]: e for e in estados_de_motores_descargables()}

    for engine_id, (etiqueta, ajuste, familia) in MOTORES_DE_SERVICIO_EXTERNO.items():
        if engine_id in descargables:
            estado = dict(descargables[engine_id])
            estado["requiere"] = "descarga_bajo_demanda"
            (docking if familia == "docking" else peptido).append(estado)
            continue

        url = getattr(settings, ajuste, None)
        configurado = bool(url and str(url).strip())
        entrada = {
            "id": engine_id,
            "etiqueta": etiqueta,
            "familia": familia,
            "estado": "servicio_no_instalado",
            # Configurado NO es disponible: la URL por defecto apunta a un
            # sidecar que esta versión no instala ni arranca.
            "disponible": False,
            "requiere": "servicio_externo",
            "url_configurada": str(url) if configurado else None,
            "accion": None,
            "bytes_descarga": 0,
            "archivos_faltantes": [],
            "dependencias_faltantes": [],
            "modulo_launcher": None,
            "motivo": (
                f"{etiqueta} se ejecuta en un servicio aparte que esta versión no "
                "instala. La aplicación sabe hablar con él, pero hay que levantarlo "
                + (f"y ahora mismo apunta a {url}." if configurado
                   else "y todavía no hay ninguna dirección configurada.")
            ),
        }
        (docking if familia == "docking" else peptido).append(entrada)

    # Un motor descargable que el mapa anterior no nombre igual tiene que salir:
    # el catálogo manda sobre la lista heredada.
    ya_listados = {e["id"] for e in docking + peptido}
    for motor_id, estado in descargables.items():
        if motor_id in ya_listados:
            continue
        entrada = dict(estado)
        entrada["requiere"] = "descarga_bajo_demanda"
        (docking if MOTORES_DESCARGABLES[motor_id].familia == "docking" else peptido).append(entrada)

    return {"docking": docking, "peptido": peptido}


@router.get(
    "/engines",
    summary="Qué motores de docking puede ejecutar esta instalación",
)
async def listar_motores() -> dict[str, list[dict]]:
    return inventario_de_motores()


@router.post(
    "/engines/{motor_id}/encender",
    summary="Encender un motor descargable que ya está instalado",
)
async def encender_motor(
    motor_id: str,
    current_user: UserORM | None = Depends(get_current_user_optional),
) -> dict:
    """Arranca el proceso del motor y espera a que responda.

    Encender es explícito: nadie levanta un modelo de 8 GB porque se abrió una
    pantalla. La llamada es idempotente —si ya está sirviendo, contesta que sí—
    y devuelve el estado completo, no un booleano: quien la llamó necesita saber
    si lo que falta es descargar, encender o mirar el error.
    """
    from services.motores import sidecar_de

    sc = sidecar_de(motor_id)
    if sc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"'{motor_id}' no es un motor descargable de esta versión.",
        )

    import anyio

    encendido = await anyio.to_thread.run_sync(sc.encender)
    estado = sc.estado().como_dict()
    estado["encendido"] = encendido
    return estado


class PipelineConfigRequest(BaseModel):
    enabled_stages: list[str] = Field(default_factory=lambda: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"])
    stage_params: dict[str, dict] = Field(default_factory=dict)
    stage_order: list[str] | None = None
    docking_engine: str = Field(default="vina", description="Motor de docking: 'vina', 'qvina2' o 'diffdock'")
    pro_workers: int | None = Field(default=None)
    pro_parallel_docks: int | None = Field(default=None)
    pro_selectivity: bool | None = Field(default=None)
    pro_anti_targets: list[str] | None = Field(default=None)
    pro_mmgbsa: bool | None = Field(default=None)
    pro_mmgbsa_steps: int | None = Field(default=None)
    gnn_precision: str | None = Field(default=None)
    peptide_docking_engine: str | None = Field(default=None)

class EvaluationGeometry(BaseModel):
    @field_validator("grid_center", "grid_size", check_fields=False)
    @classmethod
    def valid_geometry(cls, value, info):
        import math
        if value is not None:
            if not all(math.isfinite(v) for v in value):
                raise ValueError("La caja debe contener sólo números finitos")
            if info.field_name == "grid_size" and any(v <= 0 for v in value):
                raise ValueError("Las dimensiones de la caja deben ser positivas")
        return value


class EvaluationSubmitRequest(EvaluationGeometry):
    smiles: str = Field(..., min_length=1, max_length=2000)
    target_pdb_id: str = Field(default="7E2Y", min_length=4, max_length=10)
    chain: str | None = Field(
        default=None,
        max_length=4,
        description=(
            "Cadena del receptor que fue aceptada en el preflight. Debe "
            "coincidir con la cadena registrada del target."
        ),
    )
    molecule_name: str | None = Field(default=None, max_length=200)
    is_control: bool = Field(default=False, description="Si es True, se ignora el score químico (ADME/Drug-likeness) al calcular el score total.")
    grid_center: tuple[float, float, float] | None = Field(default=None, description="Centro de la Grid Box override (X, Y, Z)")
    grid_size: tuple[float, float, float] | None = Field(default=None, description="Tamaño de la Grid Box override (dX, dY, dZ)")
    custom_hotspots: list[str] | None = Field(default=None, description="Lista de hotspots seleccionados por el usuario")
    patient_profile: dict | None = Field(default=None, description="Datos clínicos y genómicos del paciente (Capa 0)")
    # ENG-003. La lista tenía un motor de más, y no era un motor: se aceptaba, se
    # registraba como método de la corrida y el despacho lo mandaba a ESMFold por
    # el `elif` final. La procedencia nombraba un método que no se ejecutó.
    # Vuelve cuando exista, con implementación y pesos.
    peptide_docking_engine: Literal["esmfold", "esmfold-pro", "esmfold-experimental", "colabfold"] | None = Field(default=None, description="Motor de docking peptídico elegido explícitamente. Ausente conserva la ruta de small molecules (Vina/QuickVina).")
    pipeline_config: PipelineConfigRequest | None = Field(default=None, description="Configuración manual del pipeline de ejecución (Modo PRO)")
    preflight_fingerprint: str | None = Field(
        default=None,
        min_length=71,
        max_length=71,
        pattern=r"^sha256:[0-9a-f]{64}$",
        description=(
            "Huella de la comprobación previa aceptada por el usuario. Si se envía, "
            "el backend la recalcula antes de registrar la corrida."
        ),
    )


class EvaluationSubmitResponse(BaseModel):
    task_id: str
    status: str
    target_pdb_id: str
    smiles_hash: str


class CancelEvaluationRequest(BaseModel):
    """Identidad de la corrida que el cliente quiere cancelar.

    El identificador va en el body para que el contrato coincida con el cliente
    desktop y no dependa de que FastAPI interprete un escalar como query param.
    """

    task_id: str = Field(..., min_length=1, max_length=128)


from api.dynamic_limiter import get_dynamic_limit, limiter

# ── Evaluación síncrona local ───────────────────────────────────────────────

@router.post("/evaluate", summary="Evaluacion sincrona con SSE progress")
async def evaluate_sync(
    data: EvaluationSubmitRequest,
    request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluacion sincrona: ejecuta el pipeline completo y retorna el resultado.
    Envia eventos SSE durante el progreso.
    Si la persistencia local falla, el error queda explícito en el stream.
    """
    validation = validate_smiles_or_raise(data.smiles)
    smiles = validation.canonical_smiles
    repository = Repository(db)
    submission_target = await get_target_for_user(
        repository, data.target_pdb_id, current_user, allow_missing=True
    )
    # EVAL-BE-005: mismas puertas que `/evaluation/submit`. Este endpoint
    # ejecuta el mismo pipeline; saltarse la huella del preflight convertía el
    # camino síncrono en una puerta trasera del asíncrono.
    await _enforce_submission_gates(
        data=data,
        canonical_smiles=smiles,
        request=request,
        current_user=current_user,
        db=db,
        repository=repository,
        submission_target=submission_target,
    )

    task_id = str(uuid.uuid4())
    # El dueño se registra ANTES de ejecutar: `status`, `stream` y `cancel`
    # deciden con esta entrada quién puede operar la corrida.
    from utils.cache import cache as _cache

    await _cache.set(
        f"task_owner:{task_id}",
        str(current_user.id) if current_user else "demo",
        ttl=86400,
    )
    await _cache.set(f"task_owner_ip:{task_id}", get_real_ip(request), ttl=86400)

    async def event_generator():
        import time
        import json
        from services.docking.queue_handler import _run_full_evaluation_async

        t0 = time.monotonic()

        # SSE: start
        yield f"data: {json.dumps({'type': 'start', 'task_id': task_id[:8], 'smiles': smiles[:30]})}\n\n"

        # Execute pipeline
        try:
            pipeline_result = await _run_full_evaluation_async(
                task_id=task_id, smiles=smiles,
                target_pdb_id=data.target_pdb_id,
                molecule_name=data.molecule_name or smiles[:20],
                is_control=data.is_control,
                user_id=str(current_user.id) if current_user else None,
                grid_center=data.grid_center,
                grid_size=data.grid_size,
                custom_hotspots=data.custom_hotspots,
                peptide_docking_engine=data.peptide_docking_engine,
                pipeline_config=data.pipeline_config.model_dump() if data.pipeline_config else None,
                docking_engine=data.pipeline_config.docking_engine if data.pipeline_config else "vina",
                run_admet_ai=admet_requested(
                    data.pipeline_config.model_dump().get("stage_params", {}).get("properties")
                    if data.pipeline_config else None
                ),
            )
        except Exception as e:
            elapsed = time.monotonic() - t0
            yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'elapsed': round(elapsed,1)})}\n\n"
            return

        molecule_id = pipeline_result.get("molecule_id")
        db_saved = False
        db_warning = None
        result = None  # v1.7.3: inicializado explícitamente (fix scoping frágil 'result' in dir())

        # El resultado ya fue persistido por el pipeline; se relee localmente.
        if molecule_id:
            try:
                from uuid import UUID
                from core.database import get_db_session
                from db.repository import Repository
                from core.models import EvaluationResultRead

                async with get_db_session() as db2:
                    repo = Repository(db2)
                    eval_data = await repo.get_evaluation_result(UUID(molecule_id))
                    if eval_data:
                        result = EvaluationResultRead.model_validate(eval_data)
                        db_saved = True
            except Exception as e:
                db_warning = f"Resultados no guardados: DB offline ({str(e)[:60]})"

        # SSE: done
        elapsed = time.monotonic() - t0
        result_data = None
        if db_saved and result is not None:
            result_data = {
                "affinity_kcal": result.affinity_kcal,
                "total_score": result.total_score,
                "molecular_weight": result.molecular_weight,
                "log_p": result.log_p,
                "tpsa": result.tpsa,
                "lipinski_pass": result.lipinski_pass,
                "veber_pass": result.veber_pass,
                "ghose_pass": result.ghose_pass,
                "egan_pass": result.egan_pass,
                "muegge_pass": result.muegge_pass,
                "muegge_score": result.muegge_score,
                "fsp3": result.fsp3,
                "is_pains": result.is_pains,
                "admet_score": result.blood_viability_score,
                "qed": result.qed,
                "sa_score": result.sa_score,
                "poses": len(result.docking_poses) if result.docking_poses else 0,
            }
        else:
            result_data = {"note": "DB offline — resultado parcial"}

        final = {
            "type": "done",
            "task_id": task_id[:8],
            "elapsed": round(elapsed, 1),
            "db_saved": db_saved,
            "db_warning": db_warning,
            "result": result_data,
        }
        yield f"data: {json.dumps(final, default=str)}\n\n"

    from starlette.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")

async def _authorize_task_access(
    task_id: str,
    request: Request | None,
    current_user: UserORM | None,
    db: AsyncSession | None,
) -> None:
    """Aplica una única política de propiedad a status, stream y cancelación."""
    if request is None or not hasattr(request, "scope"):
        return
    await _autorizar_corrida(
        task_id,
        current_user=current_user,
        db=db,
        client_ip=get_real_ip(request),
    )


async def _autorizar_corrida(
    task_id: str,
    *,
    current_user: UserORM | None,
    db: AsyncSession | None,
    client_ip: str | None,
) -> None:
    """La política de propiedad, sin depender de una `Request` HTTP.

    MOLCHAT-INT-001: MolChat también consulta corridas, y no tiene una
    `Request` que ofrecer. Duplicar aquí la comprobación habría creado la
    segunda puerta con reglas distintas que EVAL-BE-005 ya cerró una vez, así
    que la política se extrajo y las dos superficies entran por ella.
    """
    from utils.cache import cache
    owner_id = await cache.get(f"task_owner:{task_id}")
    owner_ip = await cache.get(f"task_owner_ip:{task_id}")
    expected_owner = str(current_user.id) if current_user else "demo"
    if owner_id is not None:
        if owner_id != expected_owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para operar esta evaluación.")
        if owner_id == "demo" and owner_ip and owner_ip != client_ip:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para operar esta evaluación anónima.")
        return
    if db is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La evaluación ya no está disponible.")
    from core.models import EvaluationRequestORM
    recorded = await db.get(EvaluationRequestORM, task_id)
    if recorded is not None:
        if recorded.owner_id != expected_owner or (
            expected_owner == "demo" and recorded.client_ip and recorded.client_ip != client_ip
        ):
            raise HTTPException(status_code=403, detail="No tienes permiso para operar esta evaluación.")
        return
    from core.models import EvaluationResultORM, EvaluationRunORM, MoleculeORM
    repository = Repository(db)
    stmt = (
        select(MoleculeORM)
        .join(
            EvaluationRunORM,
            EvaluationRunORM.molecule_id == MoleculeORM.id,
        )
        .where(EvaluationRunORM.task_id == task_id)
    )
    result = await db.execute(stmt)
    molecule = result.scalar_one_or_none()
    if molecule is None:
        # Compatibilidad con corridas creadas antes de que existiera la tabla
        # inmutable ``evaluation_runs`` (schema v11).
        legacy_stmt = (
            select(MoleculeORM)
            .join(EvaluationResultORM)
            .where(EvaluationResultORM.task_id == task_id)
        )
        legacy_result = await db.execute(legacy_stmt)
        molecule = legacy_result.scalar_one_or_none()
    if molecule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La evaluación no existe o ya no está disponible.")
    demo_user = await repository.get_or_create_test_user()
    if not puede_operar(molecule, current_user, demo_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para operar esta evaluación.")
    if molecule.user_id == demo_user.id:
        molecule_ip = await cache.get(f"mol_owner_ip:{molecule.id}")
        if molecule_ip and molecule_ip != client_ip:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para operar esta evaluación anónima.")


@router.post("/cancel", summary="Cancelar una evaluación desktop por task_id")
async def cancel_evaluation(
    data: CancelEvaluationRequest | None = None,
    task_id: str | None = None,
    # FastAPI requires the Request annotation to remain concrete.  A ``None``
    # default keeps direct unit invocations backwards-compatible while HTTP
    # requests always receive the Starlette request instance.
    request: Request = None,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession | None = Depends(get_db),
):
    """
    Cancela una tarea concreta: termina sus subprocesses auxiliares conocidos
    y conserva FAILURE como estado terminal aunque el worker principal llegue
    a terminar. Sin task_id se rechaza la petición: ya no existe cancelación
    global en un dispatcher concurrente.
    """
    task_id = data.task_id if data is not None else task_id
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id es requerido para cancelar")

    await _authorize_task_access(task_id, request, current_user, db)

    from services.docking.queue_handler import (
        cancel_active_mmgbsa,
        cancel_active_selectivity,
        request_desktop_job_cancellation,
    )

    killed = cancel_active_mmgbsa(task_id)
    killed += cancel_active_selectivity(task_id)
    job_cancelled = request_desktop_job_cancellation(task_id)

    log.info("evaluacion_cancelada", task_id=task_id, mmgbsa_killed=killed)
    return {"cancelled": bool(job_cancelled or killed), "mmgbsa_killed": killed}

async def _enforce_submission_gates(
    *,
    data: "EvaluationSubmitRequest",
    canonical_smiles: str,
    request: Request,
    current_user: UserORM | None,
    db: AsyncSession,
    repository: Repository,
    submission_target: object | None = None,
    exigir_preflight: bool = False,
) -> None:
    """Todo lo que hay que comprobar ANTES de ejecutar una corrida.

    EVAL-BE-005. Vive fuera de `submit_evaluation` porque `/evaluation/evaluate`
    ejecuta el mismo pipeline y se saltaba las dos comprobaciones: la huella
    del preflight aceptado y la cuota anónima. Dos puertas al mismo cálculo con
    reglas distintas no es un atajo, es un agujero.

    La huella se RECALCULA en el backend: el cliente no puede prometer por sí
    solo que la caja, el motor y los artefactos siguen siendo los mismos.
    """
    if data.chain is not None and submission_target is not None:
        expected_chain = str(getattr(submission_target, "chain", "") or "").strip().upper()
        submitted_chain = data.chain.strip().upper()
        if not expected_chain or submitted_chain != expected_chain:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La cadena del receptor ya no coincide con la configuración "
                    "registrada. Vuelve a seleccionar el receptor y comprobar la preparación."
                ),
            )

    # MOLCHAT-INT-001: `exigir_preflight` recalcula la comprobación aunque el
    # llamador no traiga huella. La pestaña Evaluación tiene una pantalla donde
    # el investigador acepta el preflight; MolChat no, así que si nadie lo
    # comprobó lo comprueba el servidor antes de encolar nada.
    if data.preflight_fingerprint is not None or exigir_preflight:
        docking_params: dict = {}
        docking_engine = "vina"
        if data.pipeline_config is not None:
            docking_engine = data.pipeline_config.docking_engine
            docking_params = data.pipeline_config.stage_params.get("docking", {})

        fresh_report = await evaluation_preflight(
            data=PreflightRequest(
                smiles=canonical_smiles,
                target_pdb_id=data.target_pdb_id,
                chain=data.chain,
                grid_center=data.grid_center,
                grid_size=data.grid_size,
                custom_hotspots=data.custom_hotspots,
                docking_engine=docking_engine,
                exhaustiveness=docking_params.get("exhaustiveness"),
                num_poses=docking_params.get("num_poses"),
                conformers=(
                    (data.pipeline_config.stage_params.get("conformer") or {}).get("conformers")
                    if data.pipeline_config else None
                ),
                pipeline_config=(data.pipeline_config if data.pipeline_config else None),
            ),
            db=db,
            current_user=current_user,
        )
        if fresh_report["technical_blockers"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La preparación ya no permite ejecutar esta corrida. "
                    "Vuelve a comprobarla y revisa los bloqueantes."
                ),
            )
        if (
            data.preflight_fingerprint is not None
            and fresh_report["input_fingerprint"] != data.preflight_fingerprint
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "La hipótesis o la preparación cambió desde la última comprobación. "
                    "Vuelve a comprobar antes de ejecutar."
                ),
            )

    # TRANS-ANON-002: aquí vivía un cupo de evaluaciones gratuitas contado por
    # dirección IP. En un producto de escritorio local la IP es siempre
    # `127.0.0.1`, así que el cupo no medía personas sino máquinas, y el ajuste
    # ya estaba neutralizado con `default=999`. Sin cuenta se evalúa sin límite;
    # la cuenta hace falta para guardar en Moldex y para certificar.


@router.post(
    "/submit",
    response_model=EvaluationSubmitResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enviar evaluación molecular asíncrona",
)
@limiter.limit(get_dynamic_limit)
async def submit_evaluation(
    data: EvaluationSubmitRequest,
    request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> EvaluationSubmitResponse:
    # MOLCHAT-INT-001: el cuerpo de este endpoint vive ahora en
    # `services.evaluation_submission.registrar_corrida`, porque MolChat tiene
    # que entrar por la MISMA puerta y no por una parecida. Aquí sólo queda lo
    # que es propio de HTTP: la IP del cliente y la forma de la respuesta.
    from services.evaluation_submission import registrar_corrida

    corrida = await registrar_corrida(
        data=data,
        db=db,
        current_user=current_user,
        client_ip=get_real_ip(request),
    )
    return EvaluationSubmitResponse(
        task_id=corrida.task_id,
        status="submitted",
        target_pdb_id=corrida.target_pdb_id,
        smiles_hash=corrida.smiles_hash,
    )


from fastapi.responses import StreamingResponse

@router.get(
    "/stream/{task_id}",
    summary="Suscribirse al flujo de eventos del pipeline (SSE)",
)
async def stream_pipeline_events(
    task_id: str,
    raw_request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession | None = Depends(get_db),
):
    import json
    import asyncio

    await _authorize_task_access(task_id, raw_request, current_user, db)

    async def event_generator():
        from utils.cache import cache

        # Subscribe before sending the replay so an event cannot disappear in
        # the replay-to-live handoff. This is the desktop event bus.
        replay, subscriber = await cache.subscribe_stage_events(task_id)

        try:
            for event in replay:
                yield f"data: {json.dumps(event)}\n\n"
                # Una suscripción tardía debe cerrar al reproducir el terminal.
                # Antes entregaba pipeline_done y luego esperaba para siempre un
                # evento nuevo que nunca iba a existir.
                if event.get("type") in ("pipeline_done", "pipeline_error"):
                    return

            while True:
                if await raw_request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(subscriber.get(), timeout=1.0)
                except TimeoutError:
                    continue
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("pipeline_done", "pipeline_error"):
                    break
        finally:
            await cache.unsubscribe_stage_events(task_id, subscriber)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get(
    "/status/{task_id}",
    response_model=JobStatus,
    summary="Consultar estado de un job de evaluación",
)
async def get_evaluation_status(
    task_id: str,
    raw_request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> JobStatus:
    bind_context(endpoint="evaluation_status", task_id=task_id)

    await _authorize_task_access(task_id, raw_request, current_user, db)

    from services.docking.queue_handler import get_job_status
    status_obj = await get_job_status(task_id)

    # FIX UI-7 (2026-08-04): el payload del polling NO debe incluir el SVG de
    # atención GNN (50-200 KB) en cada getJobStatus cada 2s. Se excluye aquí
    # del JobStatus; el frontend lo fétcha on-demand desde
    # GET /evaluation/gnn-attention/{molecule_id} solo cuando abre el tab
    # Explicabilidad. El campo completo sigue en /evaluation/result/{id}.
    if status_obj and status_obj.result and getattr(status_obj.result, "gnn_attention_svg", None):
        status_obj.result = status_obj.result.model_copy(
            update={"gnn_attention_svg": None}
        )

    return status_obj


@router.get(
    "/result/{molecule_id}",
    response_model=EvaluationResultRead,
    summary="Leer resultado persistido de una molécula",
)
async def get_evaluation_result(
    molecule_id: uuid.UUID,
    raw_request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
    task_id: str | None = None,
) -> EvaluationResultRead:
    repository = Repository(db)

    # SEC-H03: Validar propiedad del resultado
    from utils.cache import cache
    from core.models import MoleculeORM
    mol_row = await db.get(MoleculeORM, molecule_id)
    if mol_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe molécula con id={molecule_id}",
        )

    demo_user = await repository.get_or_create_test_user()

    # El filtro era `!= cuenta AND != demo`, es decir: cualquier cuenta
    # registrada leía todo lo anónimo. Una molécula tiene un dueño y sólo uno.
    if not puede_operar(mol_row, current_user, demo_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para acceder a este resultado.",
        )

    if mol_row.user_id == demo_user.id:
        # Validar IP para anónimos
        mol_ip = await cache.get(f"mol_owner_ip:{molecule_id}")
        client_ip = get_real_ip(raw_request)
        if mol_ip and mol_ip != client_ip:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para acceder a este resultado anónimo.",
            )

    if task_id is not None:
        run = await repository.get_evaluation_run(task_id, molecule_id)
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No existe una corrida persistida con ese task_id para "
                    f"molecule_id={molecule_id}"
                ),
            )
        if (run.status or "SUCCESS") == "FAILURE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=run.error_message or "La corrida solicitada no produjo un resultado válido.",
            )

        try:
            data = EvaluationResultRead.model_validate(run.snapshot_json)
        except Exception as exc:
            log.error(
                "evaluation_run_snapshot_invalid",
                task_id=task_id,
                molecule_id=str(molecule_id),
                error=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="El snapshot persistido de la corrida no se pudo serializar.",
            ) from exc

        molecule = await repository.get_molecule(molecule_id)
        if molecule and molecule.target:
            data.target_hotspots = _coerce_hotspots(molecule.target.hotspots)
            data.target_name = molecule.target.name
            data.target_spearman_rho = molecule.target.spearman_rho
            data.target_calibracion = estado_de_calibracion(molecule.target).to_dict()
        return data

    result = await repository.get_evaluation_result(molecule_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado persistido para molecule_id={molecule_id}",
        )

    # Mapeo manual de target_hotspots si existe la relación cargada
    data = EvaluationResultRead.model_validate(result)
    if result.molecule and result.molecule.target:
        data.target_hotspots = _coerce_hotspots(result.molecule.target.hotspots)
        data.target_name = result.molecule.target.name
        data.target_spearman_rho = result.molecule.target.spearman_rho
        data.target_calibracion = estado_de_calibracion(
            result.molecule.target
        ).to_dict()

    return data


class GnnAttentionResponse(BaseModel):
    """Respuesta del endpoint on-demand de atención GNN (UI-7)."""
    gnn_attention_svg: str | None = None
    gnn_attention: list[float] | None = None


@router.get(
    "/gnn-attention/{molecule_id}",
    response_model=GnnAttentionResponse,
    summary="Leer SVG de atención GNN on-demand (UI-7, fuera del polling)",
)
async def get_gnn_attention(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> GnnAttentionResponse:
    """Devuelve el SVG de atención GNN de una molécula.

    UI-7 (2026-08-04): el SVG (50-200 KB) NO viaja en el JobStatus del polling
    (se excluye en /evaluation/status/{task_id}). El frontend (ProXaiTab) llama
    a este endpoint SOLO cuando el usuario abre el tab "Explicabilidad" —
    on-demand, no en cada poll. Ver docs/36 UI-7.
    """
    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado persistido para molecule_id={molecule_id}",
        )

    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="No tienes permiso para acceder a esta atención.",
        missing_detail="No existe molécula",
    )

    return GnnAttentionResponse(
        gnn_attention_svg=result.gnn_attention_svg,
        gnn_attention=result.gnn_attention,
    )




# ── Comprobación previa (preflight) ─────────────────────────────────────────
#
# Un endpoint, un contrato. Responde qué va a entrar en la corrida SIN
# ejecutarla: sin docking, sin rescoring, sin GNN, sin MM-GBSA. Todo lo que
# devuelve sale de la ruta real de preparación (`services/docking/preflight.py`
# lo explica en detalle); lo que no puede saberse se declara `no_evaluado` en
# lugar de darse por bueno.


class PreflightRequest(EvaluationGeometry):
    smiles: str = Field(..., min_length=1, max_length=2000)
    target_pdb_id: str = Field(..., min_length=4, max_length=10)
    chain: str | None = Field(
        default=None,
        max_length=4,
        description="Cadena a acoplar. Por defecto, la que declare el receptor.",
    )
    grid_center: tuple[float, float, float] | None = None
    grid_size: tuple[float, float, float] | None = None
    custom_hotspots: list[str] | None = None
    docking_engine: str = Field(default="vina", max_length=32)
    exhaustiveness: int | None = Field(default=None, ge=1, le=128)
    num_poses: int | None = Field(default=None, ge=1, le=20)
    #: Conformaciones de entrada. 1 = confórmero único (protocolo por defecto).
    #: K > 1 activa el ensemble: amplía cobertura geométrica y cuesta K veces el
    #: tiempo de docking, sin mejorar por sí solo la elección de la pose top-1.
    conformers: int | None = Field(default=None, ge=1, le=64)
    pipeline_config: PipelineConfigRequest | None = None


@router.post(
    "/preflight",
    summary="Comprobación previa factual de una corrida (no ejecuta docking)",
)
async def evaluation_preflight(
    data: PreflightRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM | None = Depends(get_current_user_optional),
) -> dict:
    """
    Inspecciona receptor, ligando y configuración efectiva antes de ejecutar.

    No valida el SMILES con `validate_smiles_or_raise`: un SMILES inválido no
    puede terminar en un 422 sin informe. Tiene que salir como un bloqueante
    dentro del propio preflight, que es donde el usuario lo va a leer.
    """
    from services.docking.preflight import build_preflight

    repository = Repository(db)
    target = await get_target_for_user(
        repository, data.target_pdb_id, current_user, allow_missing=True
    )

    # El receptor puede no estar en el catálogo todavía (la corrida lo
    # auto-ingesta). Eso NO es un error del preflight: es un origen
    # `desconocido` y unos cuantos controles `no_evaluado`.
    if target is not None:
        chain = data.chain or target.chain or "A"
        origin = (
            "privado" if getattr(target, "is_private", False)
            else "comunidad" if getattr(target, "is_community", False)
            else "curado"
        )
        reference = str(target.id) if getattr(target, "id", None) else None
        catalog_center = (
            (target.grid_center_x, target.grid_center_y, target.grid_center_z)
            if target.grid_center_x is not None
            else None
        )
        catalog_size = (
            (target.grid_size_x, target.grid_size_y, target.grid_size_z)
            if target.grid_size_x is not None
            else None
        )
        catalog_hotspots = [
            h.get("name") for h in (_coerce_hotspots(target.hotspots) or []) if h.get("name")
        ]
        whitelist = _coerce_hotspots(target.cofactors_whitelist) or []
        # `cofactors_whitelist` es una lista de cadenas, no de dicts: se
        # normaliza aquí porque el ORM la guarda como JSON libre.
        whitelist = [w if isinstance(w, str) else w.get("name") for w in whitelist]
        whitelist = [w for w in whitelist if w]
    else:
        chain = data.chain or "A"
        origin = "desconocido"
        reference = None
        catalog_center = None
        catalog_size = None
        catalog_hotspots = []
        whitelist = []

    report = build_preflight(
        smiles=data.smiles,
        target_pdb_id=data.target_pdb_id,
        chain=chain,
        target_origin=origin,
        target_reference=reference,
        grid_center=data.grid_center,
        grid_size=data.grid_size,
        custom_hotspots=data.custom_hotspots,
        catalog_grid_center=catalog_center,
        catalog_grid_size=catalog_size,
        catalog_hotspots=catalog_hotspots,
        cofactors_whitelist=whitelist,
        # SC-9: el respaldo científico del receptor entra en el informe con el
        # resto de los controles. Se calcula en un solo sitio para que ninguna
        # superficie tenga que deducirlo —ni pueda olvidarlo—.
        calibracion=estado_de_calibracion(target).to_dict(),
        docking_engine=data.docking_engine,
        exhaustiveness=data.exhaustiveness,
        num_poses=data.num_poses,
        conformers=data.conformers,
        pipeline_config=(data.pipeline_config.model_dump(exclude_none=True) if data.pipeline_config else None),
    )
    log.info(
        "preflight_generado",
        target_pdb_id=data.target_pdb_id,
        fingerprint=report["input_fingerprint"][:23],
        blockers=len(report["technical_blockers"]),
        warnings=len(report["warnings"]),
        not_evaluated=len(report["not_evaluated"]),
    )
    return report
