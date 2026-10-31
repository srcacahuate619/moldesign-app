"""services/idempotencia.py

CR-06 — Idempotencia y reconciliación de operaciones con efectos.

La deduplicación vive donde vive el trabajo: en la base de datos de la
plataforma, no en la caché efímera del proceso. Si la respuesta se pierde
tras crear una operación (una propuesta, una aprobación que lanza una
evaluación), el reintento con la misma clave devuelve la operación original;
repetir a ciegas no duplica un cálculo costoso.

Semántica por cuenta (la identidad la impone la sesión, nunca el cuerpo):

- Misma clave + mismos parámetros ⇒ se devuelve la operación original.
- Misma clave + parámetros distintos ⇒ conflicto explícito (409).
- Reconciliar: dada la clave, consultar qué operación y qué trabajo existen.

El reclamo se commitea ANTES del efecto, copiando el patrón durable de
`submit_recorded_evaluation` (queue_handler): la constraint única
``(user_id, idempotency_key)`` es el árbitro entre reclamos concurrentes.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from core.database import commit_with_retry
from core.models import IdempotencyKeyORM
from utils.logger import get_logger

log = get_logger(__name__)

PENDIENTE = "PENDIENTE"
COMPLETADA = "COMPLETADA"
FALLIDA = "FALLIDA"


class IdempotenciaConflicto(Exception):
    """Misma clave con parámetros distintos, u operación aún en curso."""

    def __init__(self, detalle: str) -> None:
        super().__init__(detalle)
        self.status_code = 409
        self.detalle = detalle


def huella_de_peticion(documento: Any) -> str:
    """Huella canónica de los parámetros que la clave autoriza."""
    canonico = json.dumps(
        documento, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return "sha256:" + hashlib.sha256(canonico.encode("utf-8")).hexdigest()


async def _buscar(db: Any, user_id: str, clave: str) -> IdempotencyKeyORM | None:
    resultado = await db.execute(
        select(IdempotencyKeyORM).where(
            IdempotencyKeyORM.user_id == user_id,
            IdempotencyKeyORM.idempotency_key == clave,
        )
    )
    return resultado.scalar_one_or_none()


async def reclamar(
    *,
    db: Any,
    user_id: str,
    clave: str,
    operacion: str,
    request_hash: str,
) -> IdempotencyKeyORM | None:
    """Reclama la clave para esta cuenta antes de producir el efecto.

    Devuelve ``None`` si el reclamo es nuevo (o reintentable tras un fallo)
    y el llamador debe ejecutar la operación y después `completar` o
    `marcar_fallida`. Devuelve el registro existente si la operación ya
    terminó: su `response_json` es la respuesta original, para replay.
    Lanza `IdempotenciaConflicto` si la clave ya se usó con otros
    parámetros o si la operación sigue en curso.
    """
    existente = await _buscar(db, user_id, clave)
    if existente is not None:
        if existente.status == FALLIDA:
            if existente.operation != operacion or existente.request_hash != request_hash:
                raise IdempotenciaConflicto(
                    "Esta clave de idempotencia ya se usó con otros parámetros. "
                    "Usa una clave nueva para una operación distinta."
                )
            # El efecto no se produjo: la clave vuelve a PENDIENTE antes de
            # reintentar, para que un concurrente no ejecute a la vez.
            existente.status = PENDIENTE
            existente.error_message = None
            existente.finished_at = None
            await commit_with_retry(db)
            return None
        return _resolver_existente(existente, operacion=operacion, request_hash=request_hash)

    registro = IdempotencyKeyORM(
        user_id=user_id,
        idempotency_key=clave,
        operation=operacion,
        request_hash=request_hash,
        status=PENDIENTE,
    )
    db.add(registro)
    try:
        await commit_with_retry(db)
    except IntegrityError:
        # Otro reclamo concurrente ganó la constraint única. La sesión queda
        # revertida por commit_with_retry: se relee el registro ganador.
        ganador = await _buscar(db, user_id, clave)
        if ganador is None:  # pragma: no cover - la constraint dice que existe
            raise
        return _resolver_existente(ganador, operacion=operacion, request_hash=request_hash)
    return None


def _resolver_existente(
    registro: IdempotencyKeyORM, *, operacion: str, request_hash: str
) -> IdempotencyKeyORM | None:
    if registro.operation != operacion or registro.request_hash != request_hash:
        raise IdempotenciaConflicto(
            "Esta clave de idempotencia ya se usó con otros parámetros. "
            "Usa una clave nueva para una operación distinta."
        )
    if registro.status == COMPLETADA:
        return registro
    if registro.status == PENDIENTE:
        raise IdempotenciaConflicto(
            "Ya hay una operación en curso con esta clave. Reconcilia la clave "
            "para recuperar su resultado en vez de repetirla."
        )
    # FALLIDA la resuelve `reclamar` (vuelve a PENDIENTE antes del efecto).
    return None


async def completar(
    *,
    db: Any,
    user_id: str,
    clave: str,
    response: dict[str, Any],
    proposal_id: str | None = None,
    task_id: str | None = None,
) -> None:
    """Sella la operación con la respuesta que un reintento debe replayar."""
    registro = await _buscar(db, user_id, clave)
    if registro is None:  # pragma: no cover - completar sigue a reclamar
        log.warning("idempotencia_completar_sin_reclamo", clave=clave, cuenta=user_id)
        return
    registro.status = COMPLETADA
    registro.response_json = response
    registro.proposal_id = proposal_id
    registro.task_id = task_id
    registro.finished_at = datetime.now(timezone.utc)
    await commit_with_retry(db)


async def marcar_fallida(*, db: Any, user_id: str, clave: str, error: str) -> None:
    """Registra que el efecto no se produjo; la clave queda reintentable."""
    registro = await _buscar(db, user_id, clave)
    if registro is None:
        return
    registro.status = FALLIDA
    registro.error_message = error[:500]
    registro.finished_at = datetime.now(timezone.utc)
    await commit_with_retry(db)


async def reconciliar(*, db: Any, user_id: str, clave: str) -> dict[str, Any] | None:
    """Qué operación y qué trabajo existen para esta clave, o None.

    No revela claves de otra cuenta: para el llamador, una clave ajena es
    indistinguible de una que no existe.
    """
    registro = await _buscar(db, user_id, clave)
    if registro is None:
        return None
    return {
        "idempotency_key": registro.idempotency_key,
        "operation": registro.operation,
        "status": registro.status,
        "proposal_id": registro.proposal_id,
        "task_id": registro.task_id,
        "response": registro.response_json,
        "error": registro.error_message,
        "created_at": registro.created_at.isoformat() if registro.created_at else None,
        "finished_at": registro.finished_at.isoformat() if registro.finished_at else None,
    }
