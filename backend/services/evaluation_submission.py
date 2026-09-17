"""Un solo camino para registrar una corrida de evaluación.

MOLCHAT-INT-001 / D-08. Hasta ahora `POST /evaluation/submit` era el único
sitio donde se comprobaba la identidad de la cuenta, el acceso al receptor, el
preflight y la propiedad del `task_id` antes de encolar una corrida. La
herramienta de docking de MolChat intentaba entrar por debajo, llamando a una
función privada del pipeline que además **no existía**: el `ImportError` se
capturaba y el chat contestaba «pipeline de docking no disponible en este
modo», un motivo que no era el real.

D-08 decidió que MolChat sí lanza evaluaciones, y lo justificó por el eje
científico: la evaluación es el mecanismo por el que una respuesta deja de ser
generación y pasa a ser cálculo. Eso obliga a que el chat entre por la misma
puerta que la pestaña Evaluación, no por una parecida. Este módulo es esa
puerta, y ahora la usan las dos superficies: cambiar una gate cambia las dos.

Las dos funciones del router que se importan tarde —`_enforce_submission_gates`
y `_autorizar_corrida`— viven allí porque dependen del preflight HTTP y de sus
modelos. Importarlas dentro de la función evita el ciclo de importación y deja
claro que la política es una sola y tiene un solo dueño.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class CorridaRegistrada:
    """Lo que existe después de registrar una corrida: una identidad citable."""

    task_id: str
    target_pdb_id: str
    smiles_hash: str
    canonical_smiles: str
    #: SC-9. Qué respaldo científico tiene el receptor con el que se lanzó.
    #: Viaja con la corrida para que quien la muestre —incluido MolChat— no
    #: tenga que ir a buscarlo y pueda olvidarlo.
    calibracion: dict | None = None

    @property
    def aviso_de_calibracion(self) -> str:
        """Línea lista para anteponer a cualquier resultado. Vacía si calibrado."""
        if not self.calibracion or not self.calibracion.get("requiere_advertencia"):
            return ""
        return "  ⚠️ " + str(self.calibracion.get("advertencia", "")) + "\n"


async def registrar_corrida(
    *,
    data: Any,
    db: Any,
    current_user: Any | None,
    client_ip: str | None = None,
    exigir_preflight: bool = False,
) -> CorridaRegistrada:
    """Valida, comprueba y encola una evaluación; devuelve su `task_id`.

    ``exigir_preflight`` recalcula la comprobación previa aunque el llamador no
    traiga huella y rechaza la corrida si quedan bloqueantes técnicos. Lo usa
    MolChat, que no tiene una pantalla donde el investigador acepte el
    preflight: si nadie lo comprobó, lo comprueba el servidor.
    """
    from fastapi import HTTPException, status

    from chem.validator import validate_smiles_or_raise
    from db.repository import Repository
    from services.targets.access import get_target_for_user
    from utils.logger import bind_context

    # Importación tardía: la política de puertas vive en el router junto al
    # preflight del que depende. Aquí se usa, no se duplica.
    from api.routers.evaluation import _enforce_submission_gates

    validation = validate_smiles_or_raise(data.smiles)
    bind_context(endpoint="evaluation_submit", smiles_hash=validation.smiles_hash)

    repository = Repository(db)
    submission_target = await get_target_for_user(
        repository, data.target_pdb_id, current_user, allow_missing=True
    )

    await _enforce_submission_gates(
        data=data,
        canonical_smiles=validation.canonical_smiles,
        request=None,
        current_user=current_user,
        db=db,
        repository=repository,
        submission_target=submission_target,
        exigir_preflight=exigir_preflight,
    )

    try:
        from services.docking.queue_handler import submit_recorded_evaluation

        task = await submit_recorded_evaluation(
            db=db, client_ip=client_ip,
            smiles=validation.canonical_smiles,
            target_pdb_id=data.target_pdb_id,
            molecule_name=data.molecule_name,
            is_control=data.is_control,
            user_id=str(current_user.id) if current_user else None,
            grid_center=data.grid_center,
            grid_size=data.grid_size,
            custom_hotspots=data.custom_hotspots,
            peptide_docking_engine=data.peptide_docking_engine,
            pipeline_config=(
                data.pipeline_config.model_dump() if data.pipeline_config else None
            ),
        )
        # SEC-H03: guardar el owner de task_id en estado efímero local para
        # validar propiedad en status polling.
        from utils.cache import cache

        owner_id = str(current_user.id) if current_user else "demo"
        await cache.set(f"task_owner:{task.id}", owner_id, ttl=86400)
        if client_ip is not None:
            await cache.set(f"task_owner_ip:{task.id}", client_ip, ttl=86400)
    except (ConnectionError, ConnectionRefusedError, TimeoutError) as exc:
        log.error(
            "no se pudo registrar el job en la cache local",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de evaluación no está disponible en este momento. "
            "El dispatcher local no está disponible; revisa backend.latest.log.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        log.error(
            "error interno al enviar job de evaluación",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al procesar la solicitud de evaluación. "
            "Por favor intenta más tarde.",
        ) from exc

    log.info("job de evaluación enviado", task_id=task.id, target=data.target_pdb_id)
    from services.targets.calibracion import estado_de_calibracion

    return CorridaRegistrada(
        task_id=task.id,
        target_pdb_id=data.target_pdb_id,
        smiles_hash=validation.smiles_hash,
        canonical_smiles=validation.canonical_smiles,
        calibracion=estado_de_calibracion(submission_target).to_dict(),
    )
