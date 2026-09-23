"""
api/main.py

Entrypoint principal de FastAPI para el MVP de MolDesign.

Objetivos de esta fase:
- arrancar correctamente,
- exponer el servicio químico existente,
- proveer health checks reales,
- inicializar recursos base,
- manejar errores de forma consistente.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# TabPFN no debe abrir un navegador ni enviar telemetria desde una app de escritorio.
os.environ.setdefault("TABPFN_NO_BROWSER", "true")
os.environ.setdefault("TABPFN_DISABLE_TELEMETRY", "1")

# F-14: los paths del sidecar rescoring/ y los defaults RESCORING_*_PATH se
# encapsularon en services/rescoring_bridge.py (único módulo autorizado a
# mutar sys.path e inicializar env). main.py no toca sys.path ni RESCORING_*.
# Ver services/rescoring_bridge.py para el detalle de las convenciones
# "flat" / "prefix".

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.dynamic_limiter import limiter
from api.middleware import register_middleware
from api.moldex import router as moldex_router
from api.routers.auth import router as auth_router
from api.routers.blockchain import router as blockchain_router
from api.routers.evaluation import router as evaluation_router
from api.routers.history import router as history_router
from api.routers.interactions import router as interactions_router
from api.routers.pro_features import router as pro_router
from api.routers.batch import router as batch_router
from api.routers.sar import router as sar_router
from api.routers.stats import router as stats_router
from api.routers.suggestions import router as suggestions_router
from api.routers.targets import router as targets_router
from api.routers.rescoring import router as rescoring_router  # v1.3: unified, no sidecar
from api.routers.ai import router as ai_router  # v1.4: MolChat chatbot
# steam / diffdock / colabfold NO se importan aquí: ver el bloque
# «Integraciones dormidas» más abajo, junto a los include_router.
from api.routers.protein_surgery import router as protein_surgery_router  # v1.7: Protein Surgery
from chem.router import router as chem_router
from core.config import get_settings
from core.database import (
    close_engine,
    create_all_tables,
)
from core.hardware import detect_hardware, estimate_evaluation_time
from core.exceptions import MolDesignError
from utils.logger import get_logger, setup_logging

settings = get_settings()
log = get_logger(__name__)

# Versión única de la aplicación. F-07: el launcher Tauri valida esta versión
# (junto con app_mode e identidad "mol-design") en /health ANTES de dar el
# backend por listo — evita conectar contra un proceso ajeno o una instancia
# obsoleta que ocupe el puerto. Reusa la misma versión que ya exponen
# FastAPI() y el endpoint raíz; no introduce un esquema nuevo.
APP_VERSION = "1.0.1"

# ── Política 0-telemetría: NO hay crash reporting externo (Sentry eliminado,
#    2026-08-13). Los errores los reporta el usuario; el launcher captura
#    logs locales con rotación (backend.latest.log). Premisa de producto:
#    MolDesign no envía datos del usuario a terceros. ──


def _check_vina_health() -> dict[str, Any]:
    path = settings.vina_executable_path
    resolved_path = None

    if os.path.exists(path):
        resolved_path = path
    else:
        resolved_path = shutil.which(path)
        if resolved_path is None:
            scripts_dir = Path(sys.executable).resolve().parent
            candidate = scripts_dir / f"{path}.exe"
            if candidate.exists():
                resolved_path = str(candidate)

    exists = resolved_path is not None
    return {
        "status": "healthy" if exists else "unhealthy",
        "path": resolved_path or path,
        "exists": exists,
    }


def _check_open_babel_health() -> dict[str, Any]:
    """Estado del conversor estructural externo, para la UI y para un informe.

    Open Babel viaja en el instalador, así que su ausencia o su alteración
    describen una **instalación dañada**, no una función que no se compró. Por
    eso se publica su estado con nombre propio, con la licencia y la procedencia
    del programa que de verdad hay en disco.

    NO es un componente `core`. Que falte no debe impedir abrir la aplicación:
    el respaldo sólo se ejecuta cuando la exportación de Meeko falla, y una
    corrida que lo necesite y no lo tenga se abstiene con motivo explícito
    (`CONVERSOR_ESTRUCTURAL_NO_DISPONIBLE`). El arranque ya lo exige antes, en
    `bundled_layout` del contenedor Tauri.
    """
    from services.external_tools.open_babel import EstadoOpenBabel, estado_actual

    estado = estado_actual(verificar_version=True)
    return {
        "status": "healthy" if estado.estado is EstadoOpenBabel.AVAILABLE else "degraded",
        "estado": estado.estado.value,
        "detalle": estado.detalle,
        "version": estado.version_declarada,
        "version_reportada": estado.version_reportada,
        "licencia_spdx": estado.licencia_spdx,
        "path": estado.ruta_relativa,
        "sha256": estado.sha256,
        "invocacion": "subproceso CLI",
        "programa_independiente": True,
    }


def _check_rdkit_health() -> dict[str, Any]:
    try:
        from rdkit import Chem
        from rdkit import __version__ as rdkit_version

        test_mol = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
        ok = test_mol is not None
        return {
            "status": "healthy" if ok else "unhealthy",
            "rdkit_version": rdkit_version,
            "test_passed": ok,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def _safe_health_check(name: str, checker) -> dict[str, Any]:
    try:
        result = checker()
        import inspect
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as e:
        log.warning("health check falló", component=name, error=str(e))
        return {
            "status": "unhealthy",
            "error": str(e),
        }


async def _bootstrap_runtime_resources() -> None:
    Path(settings.vina_temp_dir).mkdir(parents=True, exist_ok=True)

    await create_all_tables()
    await _auto_seed_molgraph_if_missing()
    await _auto_seed_curated_targets_if_empty()
    await _resincronizar_catalogo_curado()
    await _sanitize_legacy_hotspots_in_db()

    _bootstrap_providers_and_tools()

    # Background preloading de modelos pesados
    asyncio.create_task(_background_preload()).add_done_callback(
        lambda t: log.warning("background_preload_failed", error=str(t.exception()))
        if t.exception()
        else None
    )


def _bootstrap_providers_and_tools() -> None:
    try:
        from api.routers.ai import _bootstrap_providers, _bootstrap_tools
        _bootstrap_providers()
        _bootstrap_tools()
        log.info("providers_and_tools_bootstrapped")
    except Exception as e:
        log.warning("bootstrap_providers_or_tools_failed", error=str(e))


async def _background_preload() -> None:
    """Precarga catálogos químicos ligeros en background."""
    await asyncio.sleep(2)
    try:
        from chem.pains import _get_pains_catalog
        loop = asyncio.get_running_loop()
        catalog = await loop.run_in_executor(None, _get_pains_catalog)
        log.info("PAINS catalog preloaded", entries=catalog.GetNumEntries())
    except Exception as e:
        log.warning("PAINS preload failed", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # La reconciliación sólo es válida si no hay otro backend vivo que siga
    # ejecutando los trabajos del mismo almacén.
    from utils.workspace_lock import WorkspaceLock
    with WorkspaceLock(settings.local_data_dir):
        async with _lifespan_owned(app):
            yield


@asynccontextmanager
async def _lifespan_owned(app: FastAPI):
    setup_logging()
    log.info("iniciando aplicacion MolDesign", environment=settings.environment)
    log.info(
        "modo de ejecución resuelto",
        app_mode=settings.app_mode,
        local_data_dir=settings.local_data_dir,
        storage_backend="SQLite + local_disk",
        queue_backend="local_dispatcher",
    )
    await _bootstrap_runtime_resources()

    # EVAL-BE-004: ninguna evaluación puede seguir declarándose en marcha.
    # Antes se reconciliaba sólo `pending`; una corrida que murió mientras
    # calculaba propiedades (`validated`) o acoplaba (`docking`) quedaba
    # atrapada en ese estado, fuera del historial y en contradicción con lo
    # que el polling ya sabía. Los workers viven en ESTE proceso: al arrancar
    # no queda ninguno vivo.
    try:
        if settings.is_desktop:
            from core.database import get_db_session
            from services.docking.recovery import reconcile_interrupted_evaluations

            async with get_db_session() as db:
                cerradas = await reconcile_interrupted_evaluations(db)
                if cerradas:
                    await db.commit()
                    log.info("evaluaciones_interrumpidas_cerradas", count=cerradas)
    except Exception as e:
        log.warning("reconciliacion_evaluaciones_fallo", error=str(e)[:200])

    # 5C: ninguna corrida de cohorte puede fingir que sigue en marcha.
    # Lo que quedó `queued` o `running` en disco pertenece a un proceso que ya
    # no existe: se marca `interrupted` —lo único cierto es que no sabemos cómo
    # acabó— y los contadores se recalculan desde las filas, que son la única
    # fuente que sobrevivió. Lo `completed` se conserva y `resume` no lo repite.
    try:
        from services.cohort.runs import reconcile_interrupted_runs

        reconciliadas = await reconcile_interrupted_runs()
        if reconciliadas:
            log.info("cohort_runs_interrumpidas_reconciliadas", count=reconciliadas)
    except Exception as e:
        log.warning("reconciliacion_cohort_runs_fallo", error=str(e)[:200])

    # v1.3: Pre-cargar ModelManager una sola vez en el startup
    # (antes se instanciaba y cargaba en CADA /rescore — 5s por request)
    # FIX: antes hacia `from rescoring.model_manager import ModelManager`
    # directo, que rompia si el repo root no estaba en sys.path
    # (cwd de uvicorn es backend/, no el repo root). Ahora usamos el
    # bridge services/rescoring_bridge.py que normaliza los paths, los
    # env vars y cachea via lru_cache, así el startup y el primer
    # request comparten la misma instancia.
    # El precalentamiento NO bloquea el arranque.
    #
    # POR QUE CAMBIO. Cargar aqui el ModelManager costaba 4,45 s de los 5,03 s
    # que tardaba el `lifespan` entero (medido con el log de arranque del
    # 2026-09-01). Durante esos segundos la ventana de la aplicacion no se abre:
    # el supervisor de Rust espera a que /health conteste. Y lo que se estaba
    # esperando eran unos modelos que NADIE necesita para abrir la aplicacion —
    # solo hacen falta cuando se rescorea una pose, al final de un docking que
    # dura minutos.
    #
    # Sigue siendo un precalentamiento, no una carga perezosa: se lanza en
    # cuanto la aplicacion esta sirviendo y termina mucho antes de que la
    # primera evaluacion llegue a necesitarlo. Lo que se elimina es la espera.
    #
    # `asyncio.to_thread` y no `create_task` a secas: `get_model_manager()` es
    # trabajo bloqueante (lee JSON, instancia xgboost) y en el bucle de eventos
    # congelaria el servidor los mismos 4,45 s, que es justo lo que se quiere
    # evitar.
    #
    # Si una peticion a /rescore llegara ANTES de que termine, su fallback
    # perezoso —que ya existia— la resuelve por el mismo bridge cacheado. En el
    # peor caso se carga dos veces una sola vez; nunca da un resultado distinto.
    app.state.model_manager = None

    # La siembra de estructuras va en el mismo hilo de fondo: son copias de
    # archivo, no pueden bloquear la ventana, y tienen que estar hechas antes
    # de que nadie pulse «Comprobar preparacion».
    async def _sembrar_estructuras() -> None:
        try:
            from services.semilla_estructuras import sembrar_estructuras_empaquetadas
            recuento = await asyncio.to_thread(sembrar_estructuras_empaquetadas)
            if recuento["sembradas"]:
                log.info("estructuras_empaquetadas_sembradas", **recuento)
        except Exception as e:
            log.warning("siembra_de_estructuras_fallo", error=str(e)[:200])

    app.state._siembra_estructuras = asyncio.create_task(_sembrar_estructuras())

    async def _precalentar_model_manager() -> None:
        try:
            from services.rescoring_bridge import get_model_manager
            mgr, _, _, _ = await asyncio.to_thread(get_model_manager)
            app.state.model_manager = mgr
            if mgr is not None and getattr(mgr, "is_loaded", False):
                log.info("ModelManager precalentado en segundo plano",
                         models=list(getattr(mgr, "models", {}).keys())
                         if hasattr(mgr, "models") else [])
            else:
                log.warning("ModelManager no disponible, /rescore hara fallback",
                            error="rescoring_bridge.get_model_manager returned None")
        except Exception as e:
            log.warning("ModelManager no pudo precalentarse, /rescore hara fallback",
                        error=str(e)[:200])
            app.state.model_manager = None

    # La referencia se guarda en `app.state`: una tarea sin referencias fuertes
    # puede ser recolectada a mitad de ejecucion.
    app.state._precalentado_rescoring = asyncio.create_task(_precalentar_model_manager())

    yield

    app.state.model_manager = None
    await close_engine()
    log.info("aplicacion MolDesign detenida limpiamente")


app = FastAPI(
    title="MolDesign API",
    version=APP_VERSION,
    summary="Plataforma de diseño molecular asistido con pipeline científico reproducible.",
    description=(
        "MolDesign expone un pipeline científico basado en RDKit, AutoDock Vina y "
        "scoring explícito. La IA interpreta resultados ya calculados y no genera "
        "métricas químicas por sí misma."
    ),
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_middleware(app)
app.include_router(auth_router)
app.include_router(blockchain_router)
app.include_router(chem_router)
app.include_router(evaluation_router)
app.include_router(history_router)
app.include_router(moldex_router)
app.include_router(targets_router)
app.include_router(suggestions_router)
app.include_router(batch_router)
app.include_router(sar_router)
app.include_router(stats_router)
app.include_router(interactions_router)
app.include_router(pro_router)
app.include_router(rescoring_router)  # v1.3: unified rescoring
app.include_router(ai_router)  # v1.4: MolChat chatbot
app.include_router(protein_surgery_router)  # v1.7: Protein Surgery

# ── Integraciones dormidas ──────────────────────────────────────────────────
#
# Steam (distribución, ~Q4 2026), DiffDock y ColabFold (motores externos que
# esta versión no instala). El código está entero y las pruebas lo importan;
# lo que no ocurre por defecto es publicar la ruta HTTP. El motivo largo, con
# lo que costaba tenerlas montadas en una máquina sin red, está en
# `core/config.py` sobre `montar_routers_dormidos`.
#
# El import va DENTRO del `if` a propósito: `services/diffdock` y
# `services/colabfold` traen `httpx` consigo, y no hay razón para pagar ese
# import en el arranque de una instalación que no los usa.
if settings.montar_routers_dormidos:
    from api.routers.colabfold import router as colabfold_router
    from api.routers.diffdock import router as diffdock_router
    from api.routers.steam import router as steam_router

    app.include_router(steam_router)
    app.include_router(diffdock_router)
    app.include_router(colabfold_router)
    log.warning(
        "routers_dormidos_montados",
        rutas=["/steam", "/docking/diffdock", "/docking/colabfold"],
        aviso=(
            "Describen servicios que esta instalación no levanta. "
            "Se montaron porque MONTAR_ROUTERS_DORMIDOS está activo."
        ),
    )


# ── Rescoring inline (backend desktop) ──────────────────────────────────────
@app.post("/rescore", tags=["Rescoring"])
async def rescore_inline(request: Request):
    """ML rescoring inline — sin sidecar separado.

    ModelManager se carga una sola vez en el lifespan de la app
    (app.state.model_manager), no por request.
    """
    body = await request.json()
    mgr = getattr(request.app.state, "model_manager", None)
    if mgr is None:
        # Fallback: si el startup no pudo cargar, cargar lazy una vez
        # via el mismo bridge que usa el startup (consistencia + cache).
        try:
            from services.rescoring_bridge import get_model_manager
            mgr, _, _, _ = get_model_manager()
            request.app.state.model_manager = mgr
        except Exception as e:
            return {"fallback": True, "error": f"ModelManager unavailable: {str(e)[:100]}",
                    "score_a": 0.0, "gnn_score": None, "warnings": []}
        if mgr is None:
            return {"fallback": True, "error": "ModelManager unavailable: rescoring module not loaded",
                    "score_a": 0.0, "gnn_score": None, "warnings": []}

    poses = body.get("poses", [])
    target_pdb = body.get("target_pdb_path", "")
    smiles = body.get("smiles", "")

    # FIX: arg-order bug. Firma real: extract_from_pose(pose_pdbqt_block,
    # target_pdb_path, smiles=""), NO (smiles, poses[0], target_pdb).
    pose_block = poses[0].get("pdbqt_block", "") if poses else ""

    try:
        from services.rescoring_bridge import get_interaction_feature_extractor
        InteractionFeatureExtractor = get_interaction_feature_extractor()
        extractor = InteractionFeatureExtractor()
        features = extractor.extract_from_pose(
            pose_block, target_pdb, smiles=smiles, skip_prolif=True,
        )
        result = mgr.predict(features, smiles)
        return {
            "score_a": result.score_a,
            "gnn_score": result.gnn_score,
            "warnings": result.warnings or [],
        }
    except Exception as e:
        return {
            "fallback": True, "error": str(e)[:100],
            "score_a": 0.0, "gnn_score": None, "warnings": [],
        }


@app.exception_handler(RequestValidationError)
async def handle_invalid_request(request: Request, exc) -> JSONResponse:
    # Un NaN/Infinity rechazado por Pydantic tampoco es JSON de respuesta válido.
    # Sanitizar sólo la representación del error, nunca los datos científicos.
    import math
    from fastapi.encoders import jsonable_encoder

    def safe(value):
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, dict):
            return {key: safe(item) for key, item in value.items()}
        if isinstance(value, list):
            return [safe(item) for item in value]
        return value

    return JSONResponse(status_code=422, content={"detail": safe(jsonable_encoder(exc.errors()))})


@app.exception_handler(MolDesignError)
async def handle_moldesign_error(request: Request, exc: MolDesignError) -> JSONResponse:
    log.warning(
        "error controlado de aplicación",
        error_type=type(exc).__name__,
        message=exc.message,
        detail=exc.detail,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.http_code,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # v1.7.4c: el logging structlog/colorama crashea con UnicodeEncodeError
    # (cp1252) cuando el error contiene caracteres no-ASCII — eso ocultaba el
    # traceback real de los 500 (p.ej. ValidationError de target_hotspots).
    # Loggeamos con fallback seguro para nunca enmascarar el error original.
    try:
        log.exception(
            "error inesperado no controlado",
            error_type=type(exc).__name__,
            path=request.url.path,
        )
    except Exception:
        try:
            log.error(
                "error inesperado (log.exception falló)",
                error_type=type(exc).__name__,
                path=request.url.path,
            )
        except Exception:
            print(f"[handle_unexpected_error] {type(exc).__name__} at {request.url.path} (log unavailable)", flush=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "Ocurrió un error interno no controlado",
            "detail": str(exc) if settings.is_development else None,
        },
    )


@app.get("/", tags=["Meta"])
async def root() -> dict[str, Any]:
    return {
        "name": "MolDesign API",
        "version": APP_VERSION,
        "environment": settings.environment,
        "mission": "pipeline científico reproducible para diseño molecular asistido",
    }


@app.get("/hardware", tags=["Meta"], summary="Hardware detection and recommendations")
async def hardware_info() -> dict[str, Any]:
    hw = detect_hardware()
    return {
        "cpu": {
            "model": hw.cpu_model,
            "cores_physical": hw.cpu_cores_physical,
            "cores_logical": hw.cpu_cores_logical,
        },
        "ram": {
            "total_gb": hw.ram_total_gb,
            "available_gb": hw.ram_available_gb,
        },
        "gpu": {
            "available": hw.gpu_available,
            "name": hw.gpu_name if hw.gpu_available else None,
            "vram_gb": hw.gpu_vram_gb,
            "cuda": hw.gpu_cuda,
            "opencl": hw.gpu_opencl,
            "openmm_platforms": hw.openmm_gpu_platforms,
        },
        "recommendations": {
            "workers": hw.recommended_workers,
            "parallel_docks": hw.recommended_parallel_docks,
        },
        "warnings": hw.warnings,
    }


@app.get("/hardware/estimate", tags=["Meta"], summary="Estimate evaluation time")
async def estimate_time(
    mode: str = "pro",
    anti_targets: int = 0,
    mmgbsa: bool = False,
) -> dict[str, Any]:
    hw = detect_hardware()
    return estimate_evaluation_time(
        hw,
        mode=mode,
        num_anti_targets=anti_targets,
        use_mmgbsa=mmgbsa,
    )


@app.get(
    "/evaluation/estimate",
    tags=["Meta"],
    summary="Cuánto tardaría esta corrida en ESTE equipo",
)
async def estimar_esta_corrida(
    exhaustiveness: int = 8,
    conformers: int = 1,
    target_pdb_id: str | None = None,
    grid_size_x: float = 30.0,
    grid_size_y: float = 30.0,
    grid_size_z: float = 30.0,
    rotables: int | None = None,
    anti_targets: int = 0,
    mmgbsa: bool = False,
    ligandos: int = 1,
) -> dict[str, Any]:
    """Estimación para una evaluación, un ensemble o una cohorte.

    `ligandos` es lo único que separa los tres casos. Y `target_pdb_id` no es
    decorativo: con él se comprueba EN DISCO si el receptor ya está preparado,
    que es el coste de una sola vez —medido en 8.8 s— responsable de que una
    primera corrida parezca rota al lado de la segunda.
    """
    from core.config import get_settings as _ajustes
    from services.estimacion import estimar_corrida

    hw = detect_hardware()

    receptor_preparado = True
    if target_pdb_id:
        try:
            from utils.file_handlers import StoragePath
            from utils.local_storage import data_dir

            ruta = data_dir() / StoragePath.target_prepared(target_pdb_id.strip().upper())
            receptor_preparado = ruta.is_file()
        except Exception:  # noqa: BLE001
            # No saberlo se trata como «ya está»: es preferible quedarse corto
            # en la estimación a inventar un coste que quizá no exista.
            receptor_preparado = True

    return estimar_corrida(
        cpu=int(getattr(_ajustes(), "vina_cpu", 0) or hw.cpu_cores_logical or 1),
        exhaustiveness=exhaustiveness,
        conformers=conformers,
        volumen_caja=float(grid_size_x) * float(grid_size_y) * float(grid_size_z),
        receptor_preparado=receptor_preparado,
        rotables_del_ligando=rotables,
        anti_targets=anti_targets,
        docks_en_paralelo=hw.recommended_parallel_docks,
        usa_mmgbsa=mmgbsa,
        gpu_cuda=hw.gpu_cuda,
        gpu_opencl=hw.gpu_opencl,
        ligandos=ligandos,
    )


@app.get("/health", tags=["Meta"], summary="Estado integral del sistema")
async def health() -> JSONResponse:
    rdkit_health = await _safe_health_check("rdkit", _check_rdkit_health)
    vina_health = await _safe_health_check("vina", _check_vina_health)
    open_babel_health = await _safe_health_check("open_babel", _check_open_babel_health)

    # F-19: exponer el manifiesto de modelos (hash + métricas honestas) para
    # que un release pueda asociar resultados a la versión exacta del modelo.
    model_manifest = None
    manifest_verification = {
        "valid": False,
        "manifest_version": None,
        "models": [],
        "errors": ["verification_unavailable"],
    }
    try:
        from services.rescoring_bridge import (
            get_model_manifest,
            get_model_manifest_verification,
        )

        model_manifest = get_model_manifest()
        manifest_verification = get_model_manifest_verification()
    except Exception:
        model_manifest = None

    components = {
        "mode": {"status": "healthy", "value": settings.app_mode},
        "rdkit": rdkit_health,
        "vina": vina_health,
        "open_babel": open_babel_health,
        "database": {"status": "healthy", "engine": "SQLite"},
        "storage": {"status": "healthy", "engine": "local_disk"},
        "model_manifest": {
            "status": "healthy" if manifest_verification["valid"] else "degraded",
            "manifest_version": manifest_verification["manifest_version"],
            "models": manifest_verification["models"],
            "errors": manifest_verification["errors"],
        },
    }
    core_components = {"rdkit", "vina", "database"}

    unhealthy_components = [
        name for name, payload in components.items()
        if name in core_components and payload.get("status") != "healthy"
    ]

    return JSONResponse(
        status_code=status.HTTP_200_OK if not unhealthy_components else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if not unhealthy_components else "degraded",
            # F-07: identidad semántica para el probe del launcher Tauri.
            # El launcher solo acepta el backend si app == "mol-design",
            # version está presente, app_mode == "DESKTOP" y la base de datos
            # (SQLite) está healthy. Sin estos campos el puerto NO se da por listo.
            "app": "mol-design",
            "version": APP_VERSION,
            "app_mode": settings.app_mode,
            "components": components,
        },
    )


async def _resincronizar_catalogo_curado() -> None:
    """Lleva las correcciones del catalogo a una base que ya existe.

    `_auto_seed_curated_targets_if_empty` siembra SOLO en el primer arranque y
    salta cualquier `pdb_id` existente, asi que el catalogo se escribia una vez y
    nunca mas. Todo lo corregido despues -50 cadenas, siete rescates, once cajas
    recentradas, 367 resoluciones, los cuatro campos del sitio- no llegaba a
    ninguna maquina que hubiera abierto la aplicacion alguna vez.

    Se salta entera si la huella del catalogo no cambio, asi que el coste en un
    arranque normal es un SELECT.

    Un fallo aqui NO puede impedir que la aplicacion arranque: se registra y se
    sigue con el catalogo que haya. Es preferible una base desactualizada a una
    aplicacion que no abre.
    """
    from pathlib import Path

    from core.database import get_db_session
    from services.targets.resincronizacion import resincronizar_catalogo

    ruta = Path(__file__).resolve().parent.parent.parent / "curated_targets.json"
    try:
        async with get_db_session() as db:
            resumen = await resincronizar_catalogo(db, ruta)
        if resumen.get("estado") == "aplicado":
            log.info(
                "catalogo_curado_resincronizado",
                actualizados=resumen["actualizados"],
                anadidos=resumen["anadidos"],
                retirados=len(resumen["retirados"]),
                preparacion_invalidada=len(resumen["preparacion_invalidada"]),
            )
        else:
            log.debug("catalogo_curado_sin_cambios", estado=resumen.get("estado"))
    except Exception as exc:  # noqa: BLE001 - se registra, no se traga
        log.error(
            "catalogo_curado_no_resincronizado",
            error=f"{type(exc).__name__}: {exc}",
            detalle="la aplicacion sigue con el catalogo que ya tenia",
        )


async def _auto_seed_curated_targets_if_empty() -> None:
    """Importa curated_targets.json (o curated_targets.csv) a SQLite en el primer inicio en modo DESKTOP."""
    from core.database import get_db_session
    from db.repository import Repository
    from core.models import TargetORM
    import json
    import csv

    # Rutas de recursos
    json_path = Path(__file__).resolve().parent.parent.parent / "curated_targets.json"
    csv_path = Path(__file__).resolve().parent.parent.parent / "curated_targets.csv"

    async with get_db_session() as db:
        repo = Repository(db)
        existing_targets = await repo.get_all_targets()

        # Si ya existen más targets de los básicos, omitir
        if len(existing_targets) > 10:
            return

        # Priorizar importación desde JSON (completo con 386 targets)
        if json_path.exists():
            log.info("auto_seed: iniciando importación masiva de targets desde JSON...")
            registered = 0
            with open(json_path, encoding="utf-8") as f:
                rows = json.load(f)
                for row in rows:
                    pdb_id = row.get("pdb_id", "").strip().upper()
                    if not pdb_id:
                        continue

                    existing = await repo.get_target_by_pdb_id(pdb_id)
                    if existing:
                        continue

                    # v1.7.2: sanear hotspots — si el JSON trae "null"/vacío/[]
                    # (bug histórico que dejó 380 targets sin hotspots), NO
                    # lo seteeamos: queda None y el pipeline lo regenera.
                    # SC-8 + UNIFICACIÓN (2026-08-04): REGLA ÚNICA para columnas
                    # JSONB — asignar SIEMPRE objetos Python crudos (listas),
                    # NUNCA strings serializados. El serializer de la columna
                    # (core/database.py:_json_serializer) ya hace json.dumps; si
                    # asignamos un string, se serializa 2 veces → doble escape
                    # (el bug histórico). Este bloque normaliza los 3 formatos
                    # posibles del JSON fuente (lista, doble serializado,
                    # literal "null") a una sola forma: lista cruda o None.
                    raw_hs = row.get("hotspots")
                    hotspots_ok = None  # lista cruda o None (NUNCA string)
                    if isinstance(raw_hs, str):
                        _hs_stripped = raw_hs.strip()
                        if _hs_stripped and _hs_stripped not in ("null", "[]"):
                            try:
                                _first = json.loads(_hs_stripped)
                                if isinstance(_first, str):
                                    # Doble serializado → parsear de nuevo
                                    _second = json.loads(_first)
                                    if isinstance(_second, list) and len(_second) > 0:
                                        hotspots_ok = _second  # lista cruda
                                elif isinstance(_first, list) and len(_first) > 0:
                                    hotspots_ok = _first  # lista cruda
                            except (json.JSONDecodeError, TypeError):
                                hotspots_ok = None
                    elif isinstance(raw_hs, list) and len(raw_hs) > 0:
                        hotspots_ok = raw_hs  # lista cruda

                    target = TargetORM(
                        pdb_id=pdb_id,
                        name=row.get("name", pdb_id).strip(),
                        chain=row.get("chain", "A").strip() or "A",
                        description=row.get("description", ""),
                        grid_center_x=row.get("grid_center_x", 0.0),
                        grid_center_y=row.get("grid_center_y", 0.0),
                        grid_center_z=row.get("grid_center_z", 0.0),
                        grid_size_x=row.get("grid_size_x", 20.0),
                        grid_size_y=row.get("grid_size_y", 20.0),
                        grid_size_z=row.get("grid_size_z", 20.0),
                        requires_cns=row.get("requires_cns", False),
                        structural_family=row.get("structural_family"),
                        organism=row.get("organism", "Homo sapiens"),
                        resolution=row.get("resolution"),
                        hotspots=hotspots_ok,
                        affinity_threshold=row.get("affinity_threshold"),
                        specificity_floor=row.get("specificity_floor"),
                        is_hot=row.get("is_hot", False),
                        spearman_rho=row.get("spearman_rho"),
                        calibration_date=row.get("calibration_date"),
                        prepared_file_path=row.get("prepared_file_path"),
                        is_prepared=row.get("is_prepared", False),
                        cofactors_whitelist=row.get("cofactors_whitelist"),
                        is_private=row.get("is_private", False),
                        is_community=row.get("is_community", False),
                        is_anti_target=row.get("is_anti_target", False),
                        anti_target_risk=row.get("anti_target_risk"),
                        # Composición del sitio (doc 71). Se copia tal cual: si
                        # el JSON no la trae, queda None y la interfaz dirá «sin
                        # medir» en vez de suponer una sola cadena.
                        site_chains=row.get("site_chains"),
                        site_chain_atoms=row.get("site_chain_atoms"),
                        site_evidence=row.get("site_evidence"),
                        site_ligand=row.get("site_ligand"),
                        hotspots_source=row.get("hotspots_source"),
                    )
                    db.add(target)
                    registered += 1
            await db.commit()
            log.info("auto_seed: importación desde JSON completada con éxito", registrados=registered)
            return

        # Fallback al CSV original
        if not csv_path.exists():
            log.warning("auto_seed: ni curated_targets.json ni curated_targets.csv encontrados en resources")
            return

        log.info("auto_seed: iniciando importación masiva de targets desde CSV...")
        registered = 0
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pdb_id = row.get("pdb_id", "").strip().upper()
                if not pdb_id:
                    continue

                existing = await repo.get_target_by_pdb_id(pdb_id)
                if existing:
                    continue

                try:
                    cx = float(row.get("grid_cx", 0) or 0)
                    cy = float(row.get("grid_cy", 0) or 0)
                    cz = float(row.get("grid_cz", 0) or 0)
                    sx = float(row.get("grid_sx", 20) or 20)
                    sy = float(row.get("grid_sy", 20) or 20)
                    sz = float(row.get("grid_sz", 20) or 20)
                except (ValueError, TypeError):
                    cx = cy = cz = 0.0
                    sx = sy = sz = 20.0

                hotspots_count = int(row.get("hotspots", 0) or 0)
                target = TargetORM(
                    pdb_id=pdb_id,
                    name=row.get("name", pdb_id).strip(),
                    chain=row.get("chain", "A").strip() or "A",
                    description=f"Target pre-curado ({row.get('area', '')}). Hotspots: {hotspots_count}.",
                    grid_center_x=cx, grid_center_y=cy, grid_center_z=cz,
                    grid_size_x=sx, grid_size_y=sy, grid_size_z=sz,
                    structural_family=row.get("family", "").strip() or None,
                    organism="Homo sapiens",
                    is_prepared=True,
                    is_hot=hotspots_count > 0,
                )
                db.add(target)
                registered += 1

            await db.commit()
            log.info("auto_seed: importación desde CSV completada con éxito", registrados=registered)


async def _sanitize_legacy_hotspots_in_db() -> None:
    """SC-8 (2026-08-04): corrige hotspots legacy 'null' en una DB existente.

    PROBLEMA: el bug histórico guardó hotspots como el string literal "null"
    en ~380/387 targets (tanto vía seed viejo como vía JSON doble serializado).
    El pipeline usa `hotspots_hit` contra `target.hotspots` → sin hotspots, el
    análisis de interacción con residuos clave del bolsillo no tiene anclaje.

    SOLUCIÓN: en cada startup, detectar targets con hotspots literal "null" o
    doble serializado y:
      - si el string contiene JSON válido (lista) → parsearlo y guardarlo bien;
      - si es literal "null"/vacío → dejarlo None (el pipeline lo regenera con
        discover_pocket_from_pdb cuando se usa el target).
    Es idempotente: no toca targets con hotspots válidos ni añade nuevos.
    """
    import json as _json

    from core.database import get_db_session
    from db.repository import Repository

    try:
        async with get_db_session() as db:
            repo = Repository(db)
            from sqlalchemy import select
            from core.models import TargetORM

            res = await db.execute(select(TargetORM))
            targets = list(res.scalars().all())
            fixed = 0
            for t in targets:
                hs = t.hotspots
                if not isinstance(hs, str) or not hs.strip():
                    continue
                s = hs.strip()
                if s in ("null", "[]"):
                    # Literal vacío → None para que el pipeline lo regenere
                    t.hotspots = None
                    fixed += 1
                    continue
                if s.startswith('"') or (s.startswith("[") and s != "[]"):
                    # Posible doble serializado: intentar parsear a lista.
                    # UNIFICACIÓN (2026-08-04): asignar SIEMPRE lista cruda,
                    # NUNCA string — el serializer JSONB de la columna ya hace
                    # json.dumps (core/database.py). Asignar string = doble
                    # escape (el bug histórico).
                    try:
                        first = _json.loads(s)
                        if isinstance(first, str):
                            second = _json.loads(first)
                            if isinstance(second, list) and len(second) > 0:
                                t.hotspots = second  # lista cruda
                                fixed += 1
                        elif isinstance(first, list) and len(first) > 0:
                            t.hotspots = first  # lista cruda
                            fixed += 1
                    except (_json.JSONDecodeError, TypeError):
                        pass  # no es JSON válido → dejar como está
            if fixed:
                await db.commit()
                log.info("sanitize_legacy_hotspots", corregidos=fixed)
    except Exception as e:
        log.warning("sanitize_legacy_hotspots_failed", error=str(e)[:200])


async def _auto_seed_molgraph_if_missing() -> None:
    """Copia el molgraph_seed.db a la carpeta local de MolDesign en el primer inicio."""
    import shutil

    from services.ai import molgraph

    # Las mismas rutas que lee el grafo: antes esta copia iba siempre a
    # ~/MolDesign/data y no respetaba LOCAL_DATA_DIR ni la guardia de pruebas.
    local_molgraph_path = molgraph._PUBLIC_DB
    if local_molgraph_path.exists():
        return  # Ya existe, no sobreescribir

    seed_path = molgraph._SEED_DB
    if not seed_path.exists():
        log.warning("auto_seed: molgraph_seed.db no encontrado en resources", path=str(seed_path))
        return

    try:
        local_molgraph_path.parent.mkdir(parents=True, exist_ok=True)
        # Copiar de forma síncrona
        shutil.copy(seed_path, local_molgraph_path)
        log.info("auto_seed: molgraph_seed.db copiado con éxito", dest=str(local_molgraph_path))
    except Exception as e:
        log.error("auto_seed: error copiando molgraph_seed.db", error=str(e))
