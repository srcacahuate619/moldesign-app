"""
core/database.py

Conexión async a SQLite (plataforma de referencia, modo DESKTOP).

Hay tres cosas que viven aquí:

1. Engine async — el pool de conexiones a SQLite vía aiosqlite
2. Session factory — crea sesiones de DB para cada request/task
3. Dependency de FastAPI — inyecta una sesión en cada endpoint

Por qué async:
    FastAPI es async. Si usas SQLAlchemy síncrono, cada query bloquea
    el event loop completo — ningún otro request puede procesarse
    mientras esperas a la DB. Con aiosqlite + SQLAlchemy async,
    el event loop sigue procesando requests mientras la query corre.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import core.config as core_config
from core.exceptions import DatabaseConnectionError
from core.models import Base
from utils.logger import get_logger

log = get_logger(__name__)
# NOTE: settings se accede via get_settings() de forma lazy dentro de las
# funciones, no a nivel de módulo, para permitir importar este módulo sin
# que todas las variables de entorno estén presentes (critical para tests).


def get_settings():
    """Delegación tardía para respetar overrides de settings en tests."""
    return core_config.get_settings()


# ── Versión del esquema ───────────────────────────────────────────────────────

SCHEMA_VERSION = 22  # tabla operativa batch_runs; esquema científico intacto
"""
Versión del esquema SQLite. Es la plataforma de referencia (F-04): el ORM
(core/models.py) ES la fuente de verdad del schema, y esta constante sella
la versión "de facto" en la tabla schema_meta al arrancar.

v2 (F-21): 4 columnas aditivas nullable en evaluation_results
(engine_used, fallback_reason, in_applicability_domain, model_used).

v3 (C-08): ``evaluation_results.task_id`` sustituye el nombre heredado
``celery_task_id``. La migración añade la columna y copia los valores de las
bases existentes; no borra la columna antigua ni los resultados guardados.

v4 (Sprint 5B): tabla nueva ``cohorts`` — cohortes comprobadas y congeladas.
Es puramente aditiva: ninguna tabla existente cambia, y una DB v3 la recibe
por ``create_all`` al arrancar sin tocar nada de lo que ya guardaba.

v5 (Sprint 5C): tablas nuevas ``cohort_runs`` y ``cohort_run_rows`` — la
ejecución durable de una cohorte. También aditiva: ``cohorts`` no cambia, y no
puede cambiar, porque la cohorte congelada es inmutable por contrato.

v6 (corrigendum Sprint 5C): ``cohort_runs.receptor_prepared_bytes`` conserva
el PDBQT exacto. El hash solo demostraba identidad; no permitía reanudar si el
objeto mutable del catálogo era reemplazado.

Cómo hacer bump:
  1. Columnas NUEVAS (aditivas, nullable o con default): agrega la columna
     al ORM — `create_all` + `_migrate_sqlite_db` la crean en DB existentes
     al arrancar (ALTER TABLE ADD COLUMN). Incrementa SCHEMA_VERSION.
  2. Cambios estructurales (renombrar, eliminar, cambiar tipo o backfill de
     datos): requieren una migración explícita y testeada como v3. Las DB con
     sello menor solo reciben un warning con el delta en el arranque.

v15 (revalidación del consenso de BBB): dos columnas nuevas en
``evaluation_results`` — ``blood_bbb_motivo`` (qué regla decidió la
permeabilidad, con sus números) y ``blood_cns_mpo`` (el MPO de Pfizer, que
pasa a informar en vez de decidir). Aditivas y nullable. Las evaluaciones
anteriores las tienen a ``NULL``: su veredicto de BBB se calculó con el
consenso viejo y **no es comparable** con los nuevos. Ver
``chem/bbb_consenso.py``.

v16 (auditoría de procedencia del 2026-09-04): tres columnas nuevas en
``evaluation_results``, aditivas y nullable.

  ``ml_pki`` y ``ml_pki_aplicada`` — la regresión de XGBoost y si cayó dentro
  del dominio de aplicabilidad del modelo. Antes esta predicción NO se
  guardaba: se convertía con ``-1.36 x pKi`` y se escribía encima de
  ``affinity_kcal``, que es donde vive el score de Vina. **Las evaluaciones
  anteriores a esta versión tienen en ``affinity_kcal`` un valor que puede ser
  de XGBoost y no de Vina**, sin nada que permita distinguirlo. No son
  comparables con las nuevas, y su ``ml_pki`` queda a ``NULL`` porque el dato
  original se perdió al sobrescribirlo.

  ``blood_tabpfn_estado`` — "evaluado" | "fallo" | "no_evaluado". Una lista de
  alertas vacía tenía dos causas y la interfaz las pintaba iguales, en verde.
  A ``NULL`` en las evaluaciones anteriores, en las que TabPFN de hecho nunca
  llegó a clasificar (ver ``chem/blood_viability.py``).

Detalles en db/migrations/README.md.

v18 (M5-Zn deja de estar implementado y sin ejecutar, 2026-09-04): cuatro
columnas nuevas en ``evaluation_results``, aditivas y nullable.

  ``m5_protocol_id``, ``m5_score``, ``m5_scientific_status`` y ``ums_warhead``.
  El protocolo de metaloenzimas de zinc estaba escrito, probado, con manifiesto
  y con sus AUC reproducidas a precision de maquina — y ``zinc.py::calcular`` no
  tenia NINGUN llamador en produccion. El dossier llego a decir «calculado con
  el perfil exacto» sobre un calculo que no ocurria.

  ``ums_warhead`` es la senal SMARTS-only del §2 del ADR 75, que es la
  autorizada para los tres perfiles. Viaja aparte de ``ums_score`` —el UMS
  historico con donantes y MolChamb— porque mezclarlos es el error del §9.4.

  ``NULL`` en las cuatro significa que M5-Zn no se ejecuto en esa corrida: no
  era un caso de metal, o la corrida es anterior a esta version. Jamas «el
  score era cero».

v17 (auditoria de los pesos del stacking, 2026-09-04): columna nueva
``evaluation_results.stacking_clgnn_weight``, aditiva y nullable.

  El engine resuelve CUATRO pesos —``vina``, ``xgb``, la GNN legacy de RTMScore
  y CL-GNN— y solo se persistian tres. ``stacking_gnn_weight`` recibia el de la
  GNN LEGACY y se describia, se resumia y se IMPRIMIA EN EL PDF como si fuera el
  de CL-GNN. Con el artefacto vigente, GPCR asigna ``gnn: 0.40`` y no declara
  ``clgnn`` —que resuelve a 0.00—, asi que el documento de evidencia decia
  «CL-GNN 0.40» sobre un modelo cuyo peso era cero.

  ``NULL`` en las corridas anteriores significa **no registrado por separado**,
  jamas «el peso era cero»: en esas filas el peso de CL-GNN es indeterminado y
  no se puede reconstruir, porque el unico numero guardado pertenece al otro
  modelo.

v7 (Sprint P0-A): columna nueva ``evaluation_results.structural_evidence`` — la
evidencia geometrica/fisica por pose. Aditiva y nullable: ``_migrate_sqlite_db``
la anade con ``ALTER TABLE ADD COLUMN`` en bases existentes, y las evaluaciones
anteriores la tienen a ``NULL``, que se lee como «no evaluada» y nunca como un
fallo de la pose.
v19 (trazabilidad del stacking M4): tres columnas nuevas en
``evaluation_results``, aditivas y nullable.

  ``stacking_effective_weights`` conserva los pesos normalizados que se usaron
  realmente cuando la corrida excluyo componentes ausentes; los campos
  ``stacking_vina_weight`` etc. siguen siendo los pesos nominales del diseno.
  ``stacking_degraded`` y ``stacking_missing_components`` hacen explicita la
  degradacion y sus causas despues de recargar la corrida. En evaluaciones
  anteriores quedan a ``NULL``: no se reconstruye retrospectivamente una
  formula que no fue persistida.

v20 (detalle M5-Zn): columna nueva ``evaluation_results.m5_missing_components``,
aditiva y nullable. Conserva los componentes requeridos que faltaron en una corrida
de perfil; no se reconstruye en evaluaciones anteriores.



v8 (Sprint P0-B): columna nueva ``evaluation_results.pose_selection`` — la
recomendacion del selector de pose. Aditiva y nullable, igual que la anterior:
las evaluaciones previas la tienen a ``NULL`` y se leen como ``unavailable``.

v9: columna nueva ``evaluation_results.docking_protocol`` — el protocolo de
generacion 3D que la corrida ejecuto (conformaciones pedidas y conseguidas).
Aditiva y nullable: las corridas anteriores la tienen a ``NULL`` y el dossier
las declara «no informado», que es exactamente lo que decia antes de existir la
columna. Nunca se lee como «confórmero único confirmado».

v10: columnas ``evaluation_results.receptor_path`` y ``receptor_sha256``.
Conservan una ruta content-addressed a los bytes exactos del receptor usado;
la ruta mutable del catálogo ya no se presenta como input reproducible.

v11: tabla aditiva ``evaluation_runs``. Cada ``task_id`` terminado conserva un
snapshot inmutable del resultado; ``evaluation_results`` permanece como la
proyección más reciente compatible con clientes anteriores.

v12: ``evaluation_runs.status`` y ``error_message`` conservan el terminal de la
corrida. Son necesarios cuando cancelación/watchdog ganan después de congelar
el snapshot: una corrida fallida no puede resucitar como éxito tras reiniciar.

v13: metadatos aditivos de preparación en ``targets``. Las variantes privadas
conservan receptor padre, hashes de fuente/preparado, receta canónica y
toolchain sin cambiar la semántica de los targets existentes.

v14 (MOLDEX-SCI-001): columnas aditivas ``evaluation_results.certified_task_id`` y
``certified_total_score``. El sello vivía en una fila que ``upsert_evaluation_result``
reescribe al reevaluar la molécula, así que sobrevivía a su propia corrida: la
cadena atestiguaba un score y la ficha mostraba otro bajo la misma insignia.
Estas columnas anclan el sello a lo que certificó. Los sellos anteriores las
tienen a ``NULL`` y **no se rellenan**: no se puede saber qué corrida cubrieron,
y suponerlo reintroduciría el defecto. Se leen como «indeterminado».

"""


# ── Engine ────────────────────────────────────────────────────────────────────

def _create_engine() -> AsyncEngine:
    settings = get_settings()
    from pathlib import Path
    data_dir = Path(getattr(settings, "local_data_dir", str(Path.home() / "MolDesign" / "data")))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "moldesign_local.db"

    # Un test no debe abrir la base persistente del usuario. Las suites que
    # ejercitan SQLite deben inyectar un engine temporal o configurar
    # LOCAL_DATA_DIR antes del primer get_engine(). Este guard evita que un
    # error de orden de imports convierta una prueba en una mutación de datos
    # reales de escritorio.
    production_db_path = (Path.home() / "MolDesign" / "data" / "moldesign_local.db").resolve()
    if (
        os.environ.get("MOLDESIGN_TESTING") == "1"
        and db_path.resolve() == production_db_path
    ):
        raise RuntimeError(
            "Tests cannot open the persistent desktop database. "
            "Inject a temporary engine or set LOCAL_DATA_DIR."
        )

    from sqlalchemy.pool import NullPool
    from sqlalchemy import event as sa_event

    _connect_args = {
        "check_same_thread": False,
        "timeout": 60,
    }

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=settings.db_echo_sql,
        connect_args=_connect_args,
        poolclass=NullPool,
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _setup_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


    log.info("engine SQLite creado", db_path=str(db_path))
    return engine


def _patch_jsonb_for_sqlite() -> None:
    """
    NO-OP de compatibilidad (F-04).

    Antes registraba un @compiles que emitía JSONB→TEXT para SQLite. Tras
    F-04 los modelos usan core.models.SQLiteJSON, cuyo @compiles se registra
    al importar core.models — este parche ya no es necesario.

    Se conserva la firma porque tests legacy (F-02) la importan y la llaman;
    debe permanecer idempotente y sin efectos.
    """
    log.debug("patch JSONB-TEXT obsoleto tras F-04: SQLiteJSON se registra en core/models.py")



def _json_serializer(obj: Any) -> str:
    """
    Serializa objetos Python a JSON para columnas JSON (SQLite, modo DESKTOP).
    El serializer por defecto de SQLAlchemy no maneja UUID ni datetime.
    """
    import json
    import uuid
    from datetime import datetime

    def default(o: Any) -> Any:
        if isinstance(o, uuid.UUID):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Tipo no serializable: {type(o)}")

    return json.dumps(obj, default=default)


def _json_deserializer(s: str) -> Any:
    """Deserializa JSON a Python (listas/dicts). El default es suficiente."""
    import json
    return json.loads(s)


# ── Engine (lazy singleton) ───────────────────────────────────────────────────
#
# IMPORTANTE: el engine NO se crea al importar el módulo.
# Se crea la primera vez que se llama a get_engine(). Esto permite:
# 1. Importar core.database en tests sin abrir la base persistente del usuario.
# 2. Overridear settings/env vars antes de que el engine exista.
# 3. Evitar efectos secundarios al importar cualquier módulo del backend.

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Retorna el engine singleton, creándolo en la primera llamada."""
    global _engine
    if _engine is None:
        _engine = _create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker:
    """Retorna el session factory singleton, creándolo en la primera llamada."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def set_engine(engine: AsyncEngine) -> None:
    """
    Permite inyectar un engine externo (para tests).
    Debe llamarse ANTES de que cualquier código use get_engine().
    """
    global _engine, _session_factory
    _engine = engine
    _session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def reset_engine() -> None:
    """Cierra y elimina el singleton de engine y su fábrica de sesiones.

    Es el punto de lifecycle para tests y para reinicios controlados. Deja el
    módulo en el mismo estado que tras importarlo: el siguiente ``get_engine``
    crea un engine nuevo con la configuración vigente. Nunca usar asignaciones
    directas a ``_engine``/``_session_factory`` desde una fixture, porque eso
    deja conexiones SQLite abiertas y permite que otra suite herede su DB.
    """
    global _engine, _session_factory
    engine = _engine
    _engine = None
    _session_factory = None
    if engine is not None:
        await engine.dispose()


# ── Dependency de FastAPI ─────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency de FastAPI que inyecta una sesión de DB en cada endpoint.

    Uso en un endpoint:
        from core.database import get_db
        from sqlalchemy.ext.asyncio import AsyncSession
        from fastapi import Depends

        @router.post("/molecules")
        async def create_molecule(
            data: MoleculeCreate,
            db: AsyncSession = Depends(get_db),
        ):
            # 'db' es una sesión activa, única para este request
            ...

    El bloque try/except/finally garantiza que:
    - Si el endpoint termina bien → commit automático
    - Si lanza una excepción → rollback automático
    - En cualquier caso → la sesión se cierra y la conexión vuelve al pool

    NUNCA hagas commit manualmente en un endpoint si usas esta dependency.
    El commit lo gestiona esta función.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await commit_with_retry(session)
        except BaseException:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Context manager para uso fuera de FastAPI ─────────────────────────────────

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager para obtener una sesión de DB fuera del contexto
    de un endpoint de FastAPI (scripts, subprocesos, tests).

    Un fallo de escritura revierte la transacción y se propaga. Sólo una
    operación completa e idempotente puede reintentarse en una sesión nueva;
    repetir commit después de rollback perdería silenciosamente los cambios.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await commit_with_retry(session)
        except BaseException:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Health check ──────────────────────────────────────────────────────────────

async def check_database_health() -> dict[str, Any]:
    """
    Verifica que la conexión a SQLite (plataforma de referencia desktop) funciona.

    Retorna un dict con el estado y la versión de SQLite.
    Si falla, lanza DatabaseConnectionError.
    """
    try:
        async with get_engine().connect() as conn:
            result = await conn.execute(text("SELECT sqlite_version()"))
            row = result.fetchone()
            sqlite_version = row[0]

        log.debug("health check de DB exitoso", engine="SQLite")
        return {
            "status": "healthy",
            "engine": "SQLite",
            "sqlite_version": sqlite_version,
        }

    except OperationalError as e:
        log.error("health check de DB falló", error=str(e))
        raise DatabaseConnectionError(
            "No se puede abrir la base SQLite local. "
            "Revisa backend.latest.log y los permisos de local_data_dir."
        ) from e


def _migrate_sqlite_db(db_path: Path) -> None:
    """
    Compara las columnas de los modelos SQLAlchemy (Base.metadata) con las tablas
    reales de SQLite y añade de forma dinámica cualquier columna faltante.
    Esto previene caídas por desincronización de esquemas locales sin Alembic en desktop.
    """
    import json
    import sqlite3
    from sqlalchemy.types import Integer, Boolean, Float, LargeBinary, Numeric

    if not db_path.exists():
        return

    log.info("Iniciando verificación de esquema SQLite", db_path=str(db_path))
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        for table_name, table_obj in Base.metadata.tables.items():
            # Verificar si la tabla existe
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                continue

            # Obtener columnas existentes en SQLite
            cursor.execute(f"PRAGMA table_info({table_name})")
            existing_cols = {row[1].lower() for row in cursor.fetchall()}

            # Verificar si faltan columnas del modelo
            for col in table_obj.columns:
                col_name = col.name
                if col_name.lower() in existing_cols:
                    continue

                # Determinar tipo SQLite
                sqlite_type = "TEXT"
                if isinstance(col.type, (Integer, Boolean)):
                    sqlite_type = "INTEGER"
                elif isinstance(col.type, (Float, Numeric)):
                    sqlite_type = "REAL"
                elif isinstance(col.type, LargeBinary):
                    sqlite_type = "BLOB"

                alter_query = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {sqlite_type} DEFAULT NULL"
                log.warning(
                    "Migrando esquema SQLite: agregando columna faltante",
                    table=table_name,
                    column=col_name,
                    type=sqlite_type,
                )
                cursor.execute(alter_query)

        # C-08 / schema v3: ``celery_task_id`` sólo era el ID del dispatcher
        # local. SQLite no tiene RENAME COLUMN portable para todas las bases
        # soportadas, así que el rollout seguro es aditivo: se agrega task_id y
        # se rellena desde la columna legacy. Nunca se borra datos del usuario.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evaluation_results'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(evaluation_results)")
            result_columns = {row[1].lower() for row in cursor.fetchall()}
            if {"task_id", "celery_task_id"}.issubset(result_columns):
                cursor.execute(
                    "UPDATE evaluation_results "
                    "SET task_id = celery_task_id "
                    "WHERE task_id IS NULL AND celery_task_id IS NOT NULL"
                )
                if cursor.rowcount:
                    log.info(
                        "sqlite_task_id_legacy_backfilled",
                        rows=cursor.rowcount,
                    )

        # v12: los snapshots creados antes de que existiera un terminal sólo
        # se escribían al completar con éxito. Por eso el backfill correcto es
        # SUCCESS; las cancelaciones nuevas actualizan su fila explícitamente.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evaluation_runs'")
        if cursor.fetchone():
            cursor.execute("PRAGMA table_info(evaluation_runs)")
            run_columns = {row[1].lower() for row in cursor.fetchall()}
            if "status" in run_columns:
                cursor.execute(
                    "UPDATE evaluation_runs SET status = 'SUCCESS' "
                    "WHERE status IS NULL OR TRIM(status) = ''"
                )

        # Sprint 3 / contrato receptor: una recalibración histórica escribió
        # para 7E2Y la cadena A y el centro de la proteína G, aunque el target
        # curado y el PDBQT distribuido corresponden al receptor 5-HT1A en la
        # cadena R. Sólo se corrige la firma exacta conocida; cualquier 7E2Y
        # editado por el usuario queda intacto.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='targets'")
        if cursor.fetchone():
            canonical_hotspots = json.dumps(
                [
                    {"name": "R:MET97", "importance": 0.8},
                    {"name": "R:ASP116", "importance": 1.0},
                    {"name": "R:VAL117", "importance": 0.7},
                    {"name": "R:SER190", "importance": 0.6},
                    {"name": "R:PHE361", "importance": 0.9},
                ],
                separators=(",", ":"),
            )
            cursor.execute(
                "UPDATE targets SET "
                "chain = 'R', "
                "grid_center_x = 103.03, grid_center_y = 114.79, grid_center_z = 108.36, "
                "grid_size_x = 25.0, grid_size_y = 25.0, grid_size_z = 25.0, "
                "hotspots = ? "
                "WHERE UPPER(pdb_id) = '7E2Y' AND UPPER(chain) = 'A' "
                "AND ABS(grid_center_x - 84.25) < 0.02 "
                "AND ABS(grid_center_y - 106.49) < 0.02 "
                "AND ABS(grid_center_z - 89.97) < 0.02",
                (canonical_hotspots,),
            )
            if cursor.rowcount:
                log.warning(
                    "sqlite_target_7e2y_legacy_repaired",
                    rows=cursor.rowcount,
                    chain="R",
                    reason="firma exacta de recalibración incompatible",
                )

        # No basta con que los ALTER no hayan lanzado: antes de sellar la
        # versión verificamos que cada tabla existente tenga todas las columnas
        # declaradas por el ORM. Una DB parcial nunca debe anunciarse como
        # actualizada.
        missing_columns: list[str] = []
        for table_name, table_obj in Base.metadata.tables.items():
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            )
            if not cursor.fetchone():
                continue
            cursor.execute(f"PRAGMA table_info({table_name})")
            actual = {row[1].lower() for row in cursor.fetchall()}
            missing_columns.extend(
                f"{table_name}.{column.name}"
                for column in table_obj.columns
                if column.name.lower() not in actual
            )
        if missing_columns:
            raise RuntimeError(
                "La migración dejó columnas pendientes: " + ", ".join(missing_columns)
            )

        conn.commit()
        log.info("Migración de esquema SQLite completada exitosamente")
    except Exception as e:
        conn.rollback()
        log.error("Error durante la migración del esquema SQLite", error=str(e))
        raise RuntimeError(
            "No se pudo migrar la base SQLite; no se actualizará su versión de esquema."
        ) from e
    finally:
        conn.close()


# ── Inicialización de tablas ──────────────────────────────────────────────────

async def _stamp_schema_version(conn: AsyncConnection) -> None:
    """
    Sella la versión del esquema en la tabla schema_meta (F-04).

    - DB nueva o sin sello: INSERT de SCHEMA_VERSION con timestamp.
    - DB con sello menor: log.warning con el delta y actualiza el sello.
      NO auto-migra datos arbitrarios — desktop no tiene runner de
      migraciones; los cambios estructurales pasan por create_all
      (columnas aditivas) o SQL manual documentado (ver SCHEMA_VERSION).
    """
    await conn.execute(text(
        "CREATE TABLE IF NOT EXISTS schema_meta ("
        " schema_version INTEGER NOT NULL,"
        " applied_at TEXT NOT NULL"
        ")"
    ))
    result = await conn.execute(
        text("SELECT schema_version FROM schema_meta LIMIT 1")
    )
    row = result.fetchone()
    applied_at = datetime.now(UTC).isoformat()
    if row is None:
        await conn.execute(
            text("INSERT INTO schema_meta (schema_version, applied_at) VALUES (:v, :t)"),
            {"v": SCHEMA_VERSION, "t": applied_at},
        )
        log.info("schema_version_sellada", version=SCHEMA_VERSION)
        return
    stored = int(row[0])
    if stored < SCHEMA_VERSION:
        log.warning(
            "schema_version_anterior",
            version_en_db=stored,
            version_esperada=SCHEMA_VERSION,
            delta=SCHEMA_VERSION - stored,
        )
        await conn.execute(
            text("UPDATE schema_meta SET schema_version=:v, applied_at=:t"),
            {"v": SCHEMA_VERSION, "t": applied_at},
        )
    else:
        log.debug("schema_version_al_dia", version=stored)


async def create_all_tables() -> None:
    from pathlib import Path
    settings = get_settings()
    data_dir = Path(getattr(settings, "local_data_dir", str(Path.home() / "MolDesign" / "data")))
    db_path = data_dir / "moldesign_local.db"
    # Fail closed: si la base existente no se puede migrar, el backend no abre
    # con un ORM incompatible ni sella SCHEMA_VERSION como si todo estuviera
    # bien. El error llega al launcher, que puede mostrar una recuperación.
    _migrate_sqlite_db(db_path)

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _stamp_schema_version(conn)
    log.info("tablas creadas o verificadas y versión de esquema sellada en la base de datos")


async def drop_all_tables() -> None:
    """
    Elimina todas las tablas. SOLO para tests.

    En conftest.py:
        @pytest.fixture(autouse=True)
        async def reset_db():
            await create_all_tables()
            yield
            await drop_all_tables()
    """
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    log.warning("todas las tablas eliminadas de la base de datos")


# ── Cierre limpio del engine ──────────────────────────────────────────────────

async def close_engine() -> None:
    """
    Cierra el pool de conexiones limpiamente al apagar la app.

    Llamado en el lifespan de main.py al hacer shutdown:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            yield
            await close_engine()   # <- aqui

    Sin esto, las conexiones SQLite y archivos WAL pueden quedar abiertos.
    """
    if _engine is not None:
        # v1.7: WAL checkpoint + VACUUM para SQLite (reduce .db-wal a 0 bytes)
        try:
            settings = get_settings()
            import sqlite3
            from pathlib import Path
            db_path = str(Path(settings.local_data_dir) / "moldesign_local.db")
            raw = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)
            raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            raw.execute("PRAGMA optimize")
            raw.close()
            log.debug("sqlite_wal_checkpoint_complete")
        except Exception as e:
            log.warning("sqlite_wal_checkpoint_failed", error=str(e)[:200])

        await reset_engine()
        log.info("pool de conexiones cerrado limpiamente")


# La espera por el escritor SQLite ocurre en busy_timeout. Tras un error de
# flush/commit NO se puede repetir sólo esa llamada: rollback descarta cambios
# y SQLAlchemy puede dejar la sesión inactiva. El retry válido repite la unidad
# de trabajo completa en otra sesión (services.pipeline.runner._run_mini_tx).
MAX_DB_WRITE_RETRIES = 3
DB_WRITE_RETRY_DELAY = 2.0


async def flush_with_retry(session: AsyncSession) -> None:
    """Nombre conservado por compatibilidad; nunca anuncia un flush vacío como éxito."""
    try:
        await session.flush()
    except SQLAlchemyError:
        await session.rollback()
        raise


async def commit_with_retry(session: AsyncSession) -> None:
    """Confirma una vez; el llamador debe repetir la operación entera si falla."""
    try:
        await session.commit()
    except SQLAlchemyError:
        await session.rollback()
        raise
