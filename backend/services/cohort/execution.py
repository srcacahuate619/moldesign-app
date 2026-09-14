"""
Ejecución durable de una cohorte congelada.

# La regla que gobierna este archivo

**El archivo original no se vuelve a leer. Nunca.**

Todo lo científico sale del snapshot congelado en 5B: la configuración del
`normalized_study_json`, las moléculas de las filas `eligible` y sus
`canonical_smiles`. Recanonicalizar con la versión de RDKit de hoy ejecutaría
una cohorte distinta de la que alguien aceptó —posiblemente con más filas,
posiblemente con menos— y el `cohort_fingerprint` dejaría de identificar lo que
de verdad corrió.

Por eso `source_bytes` no aparece en ninguna parte de este módulo. Está
guardado para poder auditar, mucho después, que la interpretación fue fiel; no
para volver a interpretarla.

# El pipeline es el del producto

Se llama a `services/pipeline/runner.py::run_pipeline`, que es el mismo motor
que usa el modo PRO. No hay una versión científica paralela de nada.

Se entra por la rama de `pipeline_config` y no por la heredada de
`_run_full_evaluation_async` por una razón concreta: la rama heredada llama a
`predict_early_exit` (MolGraph) antes de acoplar y puede saltarse moléculas.
Una cohorte con moléculas silenciosamente omitidas no es una cohorte.

    etapas pedidas   validation · properties · sa_filter · conformer · docking
    excluidas        clgnn (GNN) · openmm · selectivity
    ADMET-AI         desactivado por `stage_params`

**Limitación declarada:** `xgb` está marcado `required=True` en
`services/pipeline/registry.py`, así que el motor lo añade aunque no se pida.
No se puede excluir sin cambiar el registro, y cambiarlo alteraría el
comportamiento de la evaluación individual y del modo PRO, que este sprint no
toca. El rescoring XGBoost corre, y esta corrida **no lo usa para nada**: no
entra en el estado de la fila, ni en los contadores, ni en la salida.

# Qué NO produce

Ni ranking, ni `total_score`, ni ninguna métrica de enriquecimiento. Una fila
completada dice «el docking terminó», y eso **no demuestra actividad**.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)

#: Contrato de ejecución. Entra en el `run_fingerprint`: si cambia lo que este
#: módulo hace con una cohorte, cambia la identidad de sus corridas.
RUN_CONTRACT = "cohort_execution/v1"

#: Etapas de la cohorte. El runner recibe este conjunto también como contrato
#: de requeridas, por lo que XGBoost no se inyecta ni altera la afinidad Vina.
COHORT_RUN_STAGES = ("validation", "properties", "sa_filter", "conformer", "docking")

#: Techo duro de concurrencia. El motor local comparte CPU con la interfaz y
#: con el propio Vina, que ya es paralelo por dentro.
MAX_RUN_WORKERS = 4
DEFAULT_RUN_WORKERS = 2


# ── Vocabulario de estados ───────────────────────────────────────────

RUN_QUEUED = "queued"
RUN_RUNNING = "running"
RUN_COMPLETED = "completed"
RUN_COMPLETED_WITH_EXCEPTIONS = "completed_with_exceptions"
RUN_FAILED = "failed"
RUN_INTERRUPTED = "interrupted"
RUN_CANCELLED = "cancelled"

RUN_STATUSES = (
    RUN_QUEUED,
    RUN_RUNNING,
    RUN_COMPLETED,
    RUN_COMPLETED_WITH_EXCEPTIONS,
    RUN_FAILED,
    RUN_INTERRUPTED,
    RUN_CANCELLED,
)

#: Estados en los que una corrida sigue viva. Son los que impiden abrir otra
#: sobre la misma cohorte.
RUN_ACTIVE_STATUSES = (RUN_QUEUED, RUN_RUNNING)

ROW_PENDING = "pending"
ROW_RUNNING = "running"
ROW_COMPLETED = "completed"
ROW_FAILED = "failed"
ROW_NOT_EVALUATED = "not_evaluated"
ROW_DUPLICATE_REUSED = "duplicate_reused"
ROW_INTERRUPTED = "interrupted"
ROW_CANCELLED = "cancelled"

ROW_STATUSES = (
    ROW_PENDING,
    ROW_RUNNING,
    ROW_COMPLETED,
    ROW_FAILED,
    ROW_NOT_EVALUATED,
    ROW_DUPLICATE_REUSED,
    ROW_INTERRUPTED,
    ROW_CANCELLED,
)

#: Filas que ya no van a cambiar por sí solas.
ROW_TERMINAL = (ROW_COMPLETED, ROW_FAILED, ROW_NOT_EVALUATED, ROW_DUPLICATE_REUSED, ROW_CANCELLED)

#: Filas que la reanudación vuelve a intentar.
ROW_RESUMABLE = (ROW_PENDING, ROW_INTERRUPTED)


# ── Códigos de error de fila ─────────────────────────────────────────
#
# Estables, como el resto de taxonomías del paquete. Distinguen lo que le pasó
# a la MOLÉCULA de lo que le pasó al MOTOR: convertir un fallo de
# infraestructura en evidencia negativa es la afirmación que este producto no
# puede permitirse.

#: El pipeline terminó sin producir una molécula evaluable.
ERROR_SIN_RESULTADO = "SIN_RESULTADO"
#: El pipeline lanzó una excepción. Es del motor, no de la molécula.
ERROR_PIPELINE = "PIPELINE_FALLO"
#: El pipeline devolvió un resultado marcado como saltado.
ERROR_NO_EVALUADA = "NO_EVALUADA"
#: La corrida se canceló antes de llegar a esta fila.
ERROR_CANCELADA = "CANCELADA"


class ExecutionBlocked(Exception):
    """
    No se puede ABRIR la corrida. Se lanza antes de escribir nada.

    Lleva un código estable y un mensaje: el router lo traduce a 409 con los
    dos. Que sea una excepción y no un valor de retorno es deliberado — no hay
    forma de olvidarse de comprobarlo y seguir creando la corrida.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


BLOQUEO_RECEPTOR_AUSENTE = "RECEPTOR_PREPARADO_AUSENTE"
BLOQUEO_RECEPTOR_ILEGIBLE = "RECEPTOR_PREPARADO_ILEGIBLE"
BLOQUEO_CAJA_NO_RESOLUBLE = "CAJA_NO_RESOLUBLE"
BLOQUEO_COHORTE_NO_LISTA = "COHORTE_NO_LISTA"
BLOQUEO_SIN_FILAS_ELEGIBLES = "SIN_FILAS_ELEGIBLES"
BLOQUEO_CORRIDA_ACTIVA = "CORRIDA_ACTIVA"


# ── Plan de ejecución ────────────────────────────────────────────────


@dataclass(frozen=True)
class ReceptorProvenance:
    """
    Qué receptor preparado se va a usar, congelado por su contenido.

    El `.pdbqt` preparado vive en un directorio MUTABLE: repreparar el receptor
    lo reescribe. Guardar la ruta no serviría de nada —dentro de un mes
    apuntaría a otro archivo con el mismo nombre—, así que lo que se congela es
    su **SHA-256**. Dos corridas con el mismo hash usaron el mismo receptor; con
    hashes distintos, no, por mucho que la ruta coincida.
    """

    pdb_id: str
    chain: str | None
    prepared_sha256: str
    prepared_size_bytes: int
    #: Nombre lógico del objeto en el almacenamiento del producto. NO es una
    #: ruta del disco de nadie: `targets/7E2Y/prepared.pdbqt`.
    prepared_object: str
    source_sha256: str | None
    catalog_target_id: str | None
    prepared_bytes: bytes = b""

    def as_dict(self) -> dict[str, Any]:
        return {
            "pdb_id": self.pdb_id,
            "chain": self.chain,
            "prepared_sha256": self.prepared_sha256,
            "prepared_size_bytes": self.prepared_size_bytes,
            "prepared_object": self.prepared_object,
            "source_sha256": self.source_sha256,
            "catalog_target_id": self.catalog_target_id,
        }


@dataclass(frozen=True)
class EffectiveConfig:
    """
    La configuración con la que corre TODA la cohorte. Una, no una por fila.

    `grid_center` y `grid_size` ya están resueltos: si la cohorte los omitió,
    aquí está lo que dijo el catálogo. La resolución ocurre UNA vez, al abrir la
    corrida, y se congela — resolverla por fila permitiría que dos moléculas de
    la misma cohorte se acoplaran en cajas distintas.
    """

    grid_center: tuple[float, float, float]
    grid_size: tuple[float, float, float]
    grid_origin: str
    docking_engine: str
    engine_version: str | None
    exhaustiveness: int
    num_poses: int
    seed: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "grid_center": [round(float(v), 3) for v in self.grid_center],
            "grid_size": [round(float(v), 3) for v in self.grid_size],
            "grid_origin": self.grid_origin,
            "docking_engine": self.docking_engine,
            "engine_version": self.engine_version,
            "exhaustiveness": self.exhaustiveness,
            "num_poses": self.num_poses,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class PlannedRow:
    """Una fila `eligible` del snapshot, lista para insertarse como trabajo."""

    source_row_index: int
    canonical_smiles: str
    source_name: str | None
    control_role: str
    active_label: bool | None
    duplicate_of_row: int | None
    #: Si otra fila de ESTA corrida acopla la misma molécula antes, aquí va su
    #: `source_row_index`. Se decide al planificar, no al ejecutar.
    reused_from_row: int | None


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _engine_version(engine: str) -> str | None:
    """
    Versión del motor, si el binario la puede decir. Si no, `None`.

    No se inventa: una versión inventada en el fingerprint haría que dos
    corridas con motores distintos parecieran la misma.
    """
    try:
        from services.docking.vina_service import _resolve_executable

        settings = get_settings()
        setting_name = {
            "vina": "vina_executable_path",
            "qvina2": "qvina2_executable_path",
        }.get(engine)
        ruta = getattr(settings, setting_name, None) if setting_name else None
        if not ruta:
            return None
        ejecutable = _resolve_executable(str(ruta))
        if not ejecutable:
            return None
        import subprocess

        salida = subprocess.run(
            [ejecutable, "--version"], capture_output=True, text=True, timeout=10
        )
        primera = (salida.stdout or salida.stderr or "").strip().splitlines()
        return primera[0][:120] if primera else None
    except Exception:
        return None


def resolve_receptor(pdb_id: str, chain: str | None, target: Any | None) -> ReceptorProvenance:
    """
    Localiza el receptor preparado y lo congela por su contenido.

    Si no hay `.pdbqt` preparado, se BLOQUEA. No se prepara al vuelo: preparar
    dentro de la apertura de una corrida convertiría un `POST` en un trabajo
    largo de resultado incierto, y dejaría al usuario sin saber si la cohorte
    quedó abierta o no.
    """
    from utils.file_handlers import StoragePath
    from utils.local_storage import path_for

    objeto = StoragePath.target_prepared(pdb_id)
    preparado = path_for(objeto)
    if not preparado.exists():
        raise ExecutionBlocked(
            BLOQUEO_RECEPTOR_AUSENTE,
            (
                f"El receptor {pdb_id} no tiene una preparación verificable en este equipo. "
                "Prepáralo antes de abrir la corrida: no se prepara al vuelo, porque una "
                "corrida abierta sobre un receptor que no existe no se puede reproducir."
            ),
        )
    try:
        contenido = preparado.read_bytes()
    except OSError as exc:
        raise ExecutionBlocked(
            BLOQUEO_RECEPTOR_ILEGIBLE,
            f"El receptor preparado de {pdb_id} existe pero no se puede leer: {exc}",
        ) from exc

    fuente_sha: str | None = None
    try:
        fuente = path_for(StoragePath.target_raw(pdb_id))
        if fuente.exists():
            fuente_sha = _sha256(fuente.read_bytes())
    except OSError:
        fuente_sha = None

    return ReceptorProvenance(
        pdb_id=pdb_id,
        chain=chain or (getattr(target, "chain", None) if target is not None else None),
        prepared_sha256=_sha256(contenido),
        prepared_size_bytes=len(contenido),
        prepared_object=objeto,
        source_sha256=fuente_sha,
        catalog_target_id=str(target.id) if target is not None and getattr(target, "id", None) else None,
        prepared_bytes=contenido,
    )


def resolve_effective_config(study: dict[str, Any], target: Any | None) -> EffectiveConfig:
    """
    Caja efectiva y parámetros comunes.

    La cohorte pudo omitir la caja para que se derivara del receptor. Aquí se
    resuelve del CATÁLOGO, que es lo que el producto ya sabe de ese receptor. Si
    el catálogo tampoco la tiene, se bloquea: acoplar en una caja que nadie ha
    declarado produciría un resultado que no describe ninguna hipótesis.
    """
    config = study.get("config") or {}
    centro = config.get("grid_center")
    tamano = config.get("grid_size")
    origen = "cohorte"

    if centro is None or tamano is None:
        if target is None or getattr(target, "grid_center_x", None) is None:
            raise ExecutionBlocked(
                BLOQUEO_CAJA_NO_RESOLUBLE,
                (
                    "La cohorte no declaró caja y el catálogo no tiene una para este "
                    "receptor. No se acopla en una región que nadie ha declarado."
                ),
            )
        centro = centro or [target.grid_center_x, target.grid_center_y, target.grid_center_z]
        tamano = tamano or [target.grid_size_x, target.grid_size_y, target.grid_size_z]
        origen = "catalogo"

    motor = config.get("docking_engine", "vina")
    return EffectiveConfig(
        grid_center=tuple(float(v) for v in centro),  # type: ignore[arg-type]
        grid_size=tuple(float(v) for v in tamano),  # type: ignore[arg-type]
        grid_origin=origen,
        docking_engine=motor,
        engine_version=_engine_version(motor),
        exhaustiveness=int(config["exhaustiveness"]),
        num_poses=int(config["num_poses"]),
        seed=int(config.get("seed", get_settings().vina_seed)),
    )


def plan_rows(snapshot: dict[str, Any]) -> list[PlannedRow]:
    """
    Convierte las filas `eligible` del snapshot en trabajo, y sólo ésas.

    # Duplicados

    Cada `canonical_smiles` se acopla UNA vez. La primera fila elegible que lo
    trae ejecuta; las siguientes quedan atadas a ella por `reused_from_row` y
    heredarán su resultado. Conservan su propio `active_label` y su propio
    `control_role`: son filas distintas del archivo aunque compartan molécula.

    El primero se decide **entre las elegibles**, que no es lo mismo que
    `duplicate_of_row` del snapshot —aquél mira todas las filas con canónico,
    incluidas las que el validador rechazó—. Los dos se conservan porque
    responden a preguntas distintas: uno es procedencia del archivo, el otro es
    linaje de ejecución.
    """
    planificadas: list[PlannedRow] = []
    primera_por_canonico: dict[str, int] = {}

    for fila in snapshot.get("rows", []):
        if fila.get("eligibility") != "eligible":
            continue
        canonico = fila.get("canonical_smiles")
        if not canonico:
            # Una fila elegible sin canónico sería una contradicción del
            # snapshot. No se ejecuta ni se inventa: se deja fuera del trabajo.
            continue
        indice = int(fila["row_index"])
        reutiliza = primera_por_canonico.get(canonico)
        if reutiliza is None:
            primera_por_canonico[canonico] = indice
        planificadas.append(
            PlannedRow(
                source_row_index=indice,
                canonical_smiles=canonico,
                source_name=fila.get("source_name"),
                control_role=fila.get("control_role") or "none",
                active_label=fila.get("active_label"),
                duplicate_of_row=fila.get("duplicate_of_row"),
                reused_from_row=reutiliza,
            )
        )
    return planificadas


# ── Fingerprint de la corrida ────────────────────────────────────────


def canonical_run_document(
    *,
    cohort_fingerprint: str,
    config: EffectiveConfig,
    receptor: ReceptorProvenance,
) -> str:
    """
    Documento canónico del `run_fingerprint`.

    Entra el CÓMO: la caja efectiva, el receptor preparado por su hash, el
    motor con su versión, la semilla y el contrato de ejecución. Y el QUÉ, por
    referencia: el `cohort_fingerprint`.

    NO entra el número de trabajadores —cambia cuánto tarda, no qué se calcula—,
    ni la hora, ni el usuario, ni el estado. Si entrara cualquiera de ellos, dos
    corridas idénticas ejecutadas en dos máquinas parecerían distintas.
    """
    documento = {
        "contract": RUN_CONTRACT,
        "cohort_fingerprint": cohort_fingerprint,
        "config": {
            "grid_center": [round(float(v), 3) for v in config.grid_center],
            "grid_size": [round(float(v), 3) for v in config.grid_size],
            "docking_engine": config.docking_engine,
            "engine_version": config.engine_version,
            "exhaustiveness": int(config.exhaustiveness),
            "num_poses": int(config.num_poses),
            "seed": None if config.seed is None else int(config.seed),
        },
        "receptor": {
            "pdb_id": receptor.pdb_id,
            "chain": receptor.chain,
            "prepared_sha256": receptor.prepared_sha256,
        },
        "stages": list(COHORT_RUN_STAGES),
    }
    return json.dumps(
        documento, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def run_fingerprint(
    *,
    cohort_fingerprint: str,
    config: EffectiveConfig,
    receptor: ReceptorProvenance,
) -> str:
    documento = canonical_run_document(
        cohort_fingerprint=cohort_fingerprint, config=config, receptor=receptor
    )
    return _sha256(documento.encode("utf-8"))


def clamp_workers(solicitados: int | None) -> int:
    """Techo explícito. Operacional: no entra en ningún fingerprint."""
    if solicitados is None:
        return DEFAULT_RUN_WORKERS
    return max(1, min(int(solicitados), MAX_RUN_WORKERS))


# ── El ejecutor ──────────────────────────────────────────────────────


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def _evaluate_one(
    *,
    canonical_smiles: str,
    molecule_name: str | None,
    receptor: ReceptorProvenance,
    config: EffectiveConfig,
    user_id: str | None,
) -> dict[str, Any]:
    """
    Una molécula por el pipeline REAL del producto.

    Se entra por `run_pipeline` con las etapas explícitas — nunca por la rama
    heredada, que lleva Early Exit dentro y podría saltarse la molécula sin que
    la corrida se enterara.
    """
    from services.pipeline.runner import run_pipeline

    return await run_pipeline(
        task_id=str(uuid.uuid4()),
        smiles=canonical_smiles,
        target_pdb_id=receptor.pdb_id,
        molecule_name=molecule_name,
        user_id=user_id,
        enabled_stages=list(COHORT_RUN_STAGES),
        # ADMET-AI es un modelo: se apaga por el parámetro que el propio
        # pipeline expone, sin tocar el registro de etapas.
        stage_params={
            "properties": {"run_admet_ai": False},
            "docking": {
                "exhaustiveness": config.exhaustiveness,
                "num_poses": config.num_poses,
                "seed": config.seed,
            },
        },
        stage_order=list(COHORT_RUN_STAGES),
        is_control=False,
        grid_center=config.grid_center,
        grid_size=config.grid_size,
        custom_hotspots=None,
        docking_engine=config.docking_engine,
        pipeline_config={
            "enabled_stages": list(COHORT_RUN_STAGES),
            "docking_engine": config.docking_engine,
            "stage_params": {
                "docking": {
                    "exhaustiveness": config.exhaustiveness,
                    "num_poses": config.num_poses,
                    "seed": config.seed,
                }
            },
        },
        required_stage_ids=set(COHORT_RUN_STAGES),
        prepared_receptor_bytes=receptor.prepared_bytes,
    )


def classify_outcome(resultado: dict[str, Any] | None) -> tuple[str, str | None, str | None]:
    """
    Traduce lo que devolvió el pipeline a un estado de fila.

    Las tres salidas son deliberadamente distintas:

        completed       hay `molecule_id`: el docking produjo un resultado
        not_evaluated   el pipeline declaró que no evaluó esta molécula
        failed          no hay resultado utilizable

    `not_evaluated` NO es evidencia negativa. Que el motor no pudiera evaluar
    una molécula no dice nada sobre esa molécula, y mezclarlo con `failed`
    —o peor, contarlo como «no se une»— sería exactamente la afirmación sin
    comprobar que este producto existe para no hacer.
    """
    if not resultado:
        return ROW_FAILED, ERROR_SIN_RESULTADO, "El pipeline no devolvió resultado."
    if resultado.get("skipped"):
        return (
            ROW_NOT_EVALUATED,
            ERROR_NO_EVALUADA,
            str(resultado.get("reason") or "El pipeline declaró la molécula como no evaluada."),
        )
    if not resultado.get("molecule_id"):
        return ROW_FAILED, ERROR_SIN_RESULTADO, "El pipeline terminó sin `molecule_id`."
    return ROW_COMPLETED, None, None


def decide_run_status(
    *,
    completed: int,
    failed: int,
    not_evaluated: int,
    cancelled: int,
    cancel_requested: bool,
) -> str:
    """
    Estado final de la corrida, a partir de sus filas. UN solo sitio.

    `failed` se reserva para «no se obtuvo NINGÚN resultado científico
    utilizable». Una cohorte de 300 moléculas con 299 acopladas y una caída no
    es una cohorte fallida; decirlo así tiraría 299 resultados buenos.
    """
    if cancel_requested and cancelled:
        return RUN_CANCELLED
    if completed == 0 and (failed or not_evaluated):
        return RUN_FAILED
    if failed or not_evaluated:
        return RUN_COMPLETED_WITH_EXCEPTIONS
    return RUN_COMPLETED
