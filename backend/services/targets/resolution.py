"""Resolución del receptor de una corrida: el pedido, o ninguno.

EVAL-SCI-001. Antes, tres caminos de ejecución —`services/pipeline/runner.py`,
la rama heredada de `services/docking/queue_handler.py` y el docking
peptídico— terminaban igual cuando el receptor pedido no estaba en el catálogo
y la ingesta fallaba: ``repository.ensure_default_target()``. Eso acopla el
ligando contra 7E2Y (5-HT1A) y devuelve un `SUCCESS` ordinario. El resultado se
persiste, alimenta el dossier y el informe, y describe una proteína que el
investigador no eligió; peor, la caja de docking del caso pertenece a otra
estructura, así que las coordenadas tampoco significan lo que dicen.

La regla queda en un solo sitio:

* si el receptor existe, se devuelve;
* si no existe pero puede incorporarse, se incorpora y se devuelve;
* si es el receptor base del producto y la base está vacía, se siembra —eso no
  sustituye nada: es exactamente lo que se pidió;
* en cualquier otro caso, la corrida se detiene con un error explícito.

Detenerse es la respuesta correcta: un fallo se lee, se corrige y se repite;
un resultado contra otra proteína no se distingue de uno bueno.
"""

from __future__ import annotations

from typing import Any

from utils.logger import get_logger

log = get_logger(__name__)


class TargetUnavailableError(ValueError):
    """El receptor pedido no está disponible y no puede sustituirse."""


def _default_pdb_id() -> str:
    from core.config import get_settings

    return str(get_settings().default_target_pdb_id).strip().upper()


async def resolve_execution_target(
    repository: Any,
    db: Any,
    pdb_id: str | None,
) -> Any:
    """Devuelve el receptor EXACTO de la corrida o levanta el fallo.

    ``db`` se pasa a la ingesta porque escribe en la misma transacción del
    llamante; no se usa para nada más.
    """
    normalized = (pdb_id or _default_pdb_id()).strip().upper()

    target = await repository.get_target_by_pdb_id(normalized)
    if target is not None:
        return target

    # La auto-ingesta sigue siendo el camino natural para un PDB público que
    # todavía no está en el catálogo local.
    try:
        from services.targets.ingestion_manager import ingest_new_target

        result = await ingest_new_target(normalized, db)
        if result and result.get("success"):
            ingested = result.get("target")
            if ingested is None:
                ingested = await repository.get_target_by_pdb_id(normalized)
            if ingested is not None:
                log.info("target_auto_ingested", pdb_id=normalized)
                return ingested
    except Exception as exc:  # noqa: BLE001 — el motivo se reporta al usuario
        log.warning(
            "target_auto_ingest_failed", pdb_id=normalized, error=str(exc)[:200]
        )

    # Sembrar el receptor base cuando el receptor base es lo que se pidió: una
    # instalación nueva no tiene por qué fallar su primera corrida.
    if normalized == _default_pdb_id():
        return await repository.ensure_default_target()

    log.error("target_no_disponible_para_ejecutar", pdb_id=normalized)
    raise TargetUnavailableError(
        f"El receptor {normalized} no está disponible en este equipo y no se "
        "pudo incorporar al catálogo. La corrida se detiene: acoplar contra "
        "otro receptor produciría un resultado que no corresponde a la "
        "hipótesis. Comprueba la conexión o añade la estructura manualmente."
    )
