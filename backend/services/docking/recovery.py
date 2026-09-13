"""Reconciliación de evaluaciones interrumpidas al arrancar el backend.

EVAL-BE-004. Los estados intermedios de una molécula (`pending`, `validated`,
`docking`) sólo tienen sentido mientras el proceso que los escribió sigue vivo:
en escritorio los workers viven dentro de este mismo proceso, así que al
arrancar no puede quedar ninguno en marcha. Lo que sobreviva a un reinicio
pertenece a una corrida que murió.

Dejarlos como estaban no era neutral: el historial sólo lista `evaluated` y
`failed`, de modo que la corrida desaparecía de la vista sin dejar rastro, y el
polling —que sí concluye que la tarea ya no existe— contradecía a la fila
persistida.

Se cierran, por tanto, con el único hecho comprobable: se interrumpieron. No se
inventa resultado, no se toca lo terminal y no se borra nada.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import MoleculeStatus
from db.repository import Repository
from utils.logger import get_logger

log = get_logger(__name__)


#: Estados que no pueden sobrevivir al arranque de un proceso nuevo.
NON_TERMINAL_STATUSES = (
    MoleculeStatus.PENDING,
    MoleculeStatus.VALIDATED,
    MoleculeStatus.DOCKING,
)

INTERRUPTED_MESSAGE = (
    "La evaluación se interrumpió antes de terminar (la aplicación se cerró o "
    "el proceso murió durante el cálculo). No hay resultado científico que "
    "leer: vuelve a ejecutarla si sigues interesado en esta hipótesis."
)


async def reconcile_interrupted_evaluations(db: AsyncSession) -> int:
    """Cierra las evaluaciones a medias y devuelve cuántas eran.

    El llamante decide cuándo commitear: en el arranque se hace junto al resto
    de la reconciliación, y en las pruebas permite inspeccionar la transacción.
    """
    repository = Repository(db)
    cerradas = 0

    for status_value in NON_TERMINAL_STATUSES:
        for molecule in await repository.list_molecules_by_status(status_value):
            molecule.status = MoleculeStatus.FAILED
            db.add(molecule)
            # El motivo se persiste donde el producto ya lo lee: el resultado
            # de la evaluación. Sin él, la corrida aparecería como un fallo
            # científico sin explicación.
            await repository.upsert_evaluation_result(
                molecule_id=molecule.id,
                error_message=INTERRUPTED_MESSAGE,
            )
            cerradas += 1

    if cerradas:
        log.info("evaluaciones_interrumpidas_reconciliadas", count=cerradas)
    return cerradas
