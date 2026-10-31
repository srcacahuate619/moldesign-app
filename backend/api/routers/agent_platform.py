"""Superficie de plataforma para agentes (Fase 6.6): propuestas, idempotencia y STT.

Lo que queda de `api/routers/ai.py` tras el corte: las puertas HTTP que son
plataforma y que el sidecar MolChat consume por contrato —propuestas de
docking revisables (CR-07), reconciliación idempotente (CR-06),
transcripción local y gestión del consentimiento de red por destino
(que usan los flujos de certificación blockchain)—. Mismas rutas `/ai/*`,
mismos modelos, mismo comportamiento; sólo cambió el hogar del código.

Diferencia única e intencionada: aprobar ya no anota el lanzamiento en el
historial del chat interno (murió con él); el expediente vive en el sidecar.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from core.database import get_db
from core.models import UserORM
from services.redaccion import redactar_secretos
from utils.logger import get_logger

log = get_logger(__name__)

#: MOLCHAT-AUD-01, higiene del §8. 25 MB son varios minutos de audio de un
#: dictado real; por encima de eso no es una pregunta, es un cuerpo sin tope
#: cargándose en memoria.
MAX_BYTES_AUDIO = 25 * 1024 * 1024

router = APIRouter(prefix="/ai", tags=["MolChat"])


@router.get("/consent/red")
async def listar_destinos_de_red(
    current_user: UserORM = Depends(get_current_user),
):
    """Destinos de las HERRAMIENTAS: servicio, host, finalidad y qué sale.

    `allow_web` seguía siendo un interruptor: autorizar «buscar en internet»
    autorizaba PubChem, ChEMBL, RCSB, UniProt y HuggingFace a la vez, sin decir
    cuáles ni qué mandaba a cada uno. Esto es lo que permite preguntarlo uno a
    uno, y `modo_offline` hace comprobable la afirmación «este equipo no habla
    con nadie».
    """
    from services import red

    return {
        "modo_offline": red.modo_offline(),
        "destinos": await asyncio.to_thread(red.estado_de_destinos, str(current_user.id)),
    }


@router.post("/consent/red")
async def otorgar_destino_de_red(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    """Autoriza un servicio externo concreto para esta cuenta."""
    from services import red

    servicio = str(payload.get("servicio", "")).strip()
    destino = red.destino_de_servicio(servicio)
    if destino is None:
        raise HTTPException(
            status_code=404,
            detail=f"'{servicio}' no es un destino declarado.",
        )

    visto = payload.get("host")
    if visto is not None and visto != destino.host:
        raise HTTPException(
            status_code=409,
            detail={
                "motivo": "destino_cambiado",
                "mensaje": (
                    "El destino cambió desde que lo viste; no autoricé el nuevo. "
                    f"Ahora sería {destino.host}."
                ),
                "destino": destino.to_dict(),
            },
        )

    registro = red.otorgar(servicio, str(current_user.id))
    return {"status": "ok", "destino": destino.to_dict(), "otorgado_en": registro["otorgado_en"]}


@router.delete("/consent/red/{servicio}")
async def revocar_destino_de_red(
    servicio: str,
    current_user: UserORM = Depends(get_current_user),
):
    from services import red

    retirado = red.revocar(servicio, str(current_user.id))
    return {"status": "ok", "revocado": retirado}


@router.post("/speech-to-text")
async def speech_to_text(
    request: Request,
    current_user: UserORM = Depends(get_current_user),
):
    """Transcribir audio a texto usando whisper local (offline, sin API key)."""
    from services.speech_to_text import get_transcriber, is_whisper_available

    if not is_whisper_available():
        raise HTTPException(
            status_code=501,
            detail="faster-whisper no está instalado. Ejecutá: pip install faster-whisper",
        )

    content_type = request.headers.get("content-type", "")
    lang = request.query_params.get("lang", "es")

    # MOLCHAT-AUD-01, higiene del §8. Aquí se leía `await request.body()` sin
    # tope y sin mirar el `content-type` —que se calculaba y no se usaba—: un
    # cuerpo de cualquier tamaño se cargaba entero en memoria antes de que nadie
    # comprobara qué era. Se rechaza por cabecera cuando se puede, y se corta al
    # leer cuando el cliente no la manda.
    if content_type and not content_type.split(";")[0].strip().startswith("audio/"):
        raise HTTPException(
            status_code=415,
            detail=f"Este endpoint sólo acepta audio; llegó '{content_type[:60]}'.",
        )

    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > MAX_BYTES_AUDIO:
        raise HTTPException(
            status_code=413,
            detail=f"El audio supera el máximo de {MAX_BYTES_AUDIO // (1024 * 1024)} MB.",
        )

    audio = bytearray()
    async for trozo in request.stream():
        audio.extend(trozo)
        if len(audio) > MAX_BYTES_AUDIO:
            raise HTTPException(
                status_code=413,
                detail=f"El audio supera el máximo de {MAX_BYTES_AUDIO // (1024 * 1024)} MB.",
            )
    audio_bytes = bytes(audio)
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio vacío")

    transcriber = get_transcriber()
    if not transcriber.load():
        raise HTTPException(
            status_code=503,
            detail="No se pudo cargar whisper: "
            + redactar_secretos(getattr(transcriber, "_load_error", ""))[:200],
        )

    text = transcriber.transcribe(audio_bytes, lang=lang)
    if not text:
        return {"text": "", "warning": "No se detectó voz en el audio."}

    return {"text": text, "lang": lang, "model": "faster-whisper-tiny"}


@router.get("/speech-to-text/status")
async def speech_to_text_status():
    from services.speech_to_text import is_whisper_available
    return {
        "available": is_whisper_available(),
        "model": "tiny",
        "models_dir": str(
            Path(__file__).parent.parent.parent.parent / "models" / "whisper"
        ),
    }


class AprobarPropuestaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
        description="Huella de la propuesta que se aprueba, tal como la mostró el chat.",
    )


# ── CR-07/CR-06: creación HTTP de propuestas e idempotencia ────────────────
#
# MolChat (el agente externo) crea propuestas por esta puerta, sin pasar por
# el chat interno. Crear NO encola ni ejecuta nada: la propuesta nace
# pendiente y sólo la aprobación existente la lanza. La clave de
# idempotencia (cabecera `Idempotency-Key`) es opcional; sin ella, el
# comportamiento es exactamente el anterior.


class CrearPropuestaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    smiles: str = Field(..., min_length=1, max_length=2000)
    target_pdb_id: str = Field(default="7E2Y", min_length=4, max_length=10)
    chain: str | None = Field(default=None, max_length=4)
    pipeline_config: dict[str, Any] | None = Field(
        default=None,
        description="Configuración del pipeline; la valida EvaluationSubmitRequest.",
    )


class ParametrosEfectivosRespuesta(BaseModel):
    motor: str | None = None
    exhaustividad: int | None = None
    poses: int | None = None
    semilla: int | None = None
    conformaciones: int | None = None
    caja: dict[str, Any] = Field(default_factory=dict)


class PreflightResumenRespuesta(BaseModel):
    technical_blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    not_evaluated: list[str] = Field(default_factory=list)


class PropuestaCreadaRespuesta(BaseModel):
    proposal_id: str
    id: str
    proposal_hash: str
    hash: str
    estado: str
    parametros_efectivos: ParametrosEfectivosRespuesta
    preflight: PreflightResumenRespuesta
    caduca_en: str
    expira_en_s: int


class ReconciliacionRespuesta(BaseModel):
    idempotency_key: str
    operation: str
    status: str
    proposal_id: str | None = None
    task_id: str | None = None
    response: dict[str, Any] | None = None
    error: str | None = None
    created_at: str | None = None
    finished_at: str | None = None


def _como_http(exc) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detalle)


async def _reclamar_clave(db, *, usuario, clave, operacion, documento):
    """Reclamo previo al efecto; devuelve la respuesta previa si ya terminó."""
    from services import idempotencia

    huella = idempotencia.huella_de_peticion(
        {"user_id": str(usuario.id), "operation": operacion, **documento}
    )
    try:
        previo = await idempotencia.reclamar(
            db=db, user_id=str(usuario.id), clave=clave,
            operacion=operacion, request_hash=huella,
        )
    except idempotencia.IdempotenciaConflicto as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detalle) from exc
    return previo.response_json if previo is not None else None


async def _sellar_clave(db, *, usuario, clave, respuesta, proposal_id=None, task_id=None):
    """Best effort tras el efecto: fallar el sello no debe tumbar la respuesta."""
    from services import idempotencia

    try:
        await idempotencia.completar(
            db=db, user_id=str(usuario.id), clave=clave, response=respuesta,
            proposal_id=proposal_id, task_id=task_id,
        )
    except Exception as exc:  # noqa: BLE001 - la operación ya ocurrió
        log.warning("idempotencia_sin_sellar", error=str(exc)[:160])


async def _fallar_clave(db, *, usuario, clave, error):
    from services import idempotencia

    try:
        await idempotencia.marcar_fallida(
            db=db, user_id=str(usuario.id), clave=clave, error=str(error)
        )
    except Exception as exc:  # noqa: BLE001 - no enmascarar el error original
        log.warning("idempotencia_sin_marcar_fallo", error=str(exc)[:160])


@router.post(
    "/proposals",
    status_code=201,
    response_model=PropuestaCreadaRespuesta,
)
async def crear_propuesta_de_docking(
    body: CrearPropuestaRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", max_length=200
    ),
):
    """CR-07: crea una propuesta revisable sin lanzar el cálculo.

    La identidad la impone la sesión; ningún `user_id` del cuerpo tiene
    efecto (el modelo lo rechaza). Si el preflight trae bloqueantes
    técnicos, responde 409 con el preflight completo y sin propuesta.
    """
    from pydantic import ValidationError

    from api.routers.evaluation import EvaluationSubmitRequest
    from services.evaluation import proposals as propuestas

    if idempotency_key:
        previa = await _reclamar_clave(
            db, usuario=current_user, clave=idempotency_key,
            operacion="crear_propuesta",
            documento={"body": body.model_dump(mode="json", exclude_none=True)},
        )
        if previa is not None:
            return previa

    try:
        peticion = EvaluationSubmitRequest(
            smiles=body.smiles,
            target_pdb_id=body.target_pdb_id,
            chain=body.chain,
            pipeline_config=body.pipeline_config,
        )
    except ValidationError as exc:
        if idempotency_key:
            await _fallar_clave(
                db, usuario=current_user, clave=idempotency_key, error="petición inválida"
            )
        raise HTTPException(status_code=422, detail="La petición de propuesta no es válida.") from exc

    try:
        vista = await propuestas.crear_estructurada(
            peticion=peticion, usuario=current_user, db=db
        )
    except propuestas.PropuestaBloqueada as bloqueada:
        if idempotency_key:
            await _fallar_clave(
                db, usuario=current_user, clave=idempotency_key,
                error="preflight con bloqueantes técnicos",
            )
        raise HTTPException(
            status_code=409,
            detail={
                "mensaje": "El preflight del servidor bloquea esta evaluación: "
                "no se creó ninguna propuesta aprobable.",
                "proposal_id": None,
                "preflight": bloqueada.informe,
            },
        ) from bloqueada
    except HTTPException as exc:
        if idempotency_key:
            await _fallar_clave(
                db, usuario=current_user, clave=idempotency_key, error=exc.detail
            )
        raise

    if idempotency_key:
        await _sellar_clave(
            db, usuario=current_user, clave=idempotency_key,
            respuesta=vista, proposal_id=vista["proposal_id"],
        )
    return vista


@router.get("/idempotency/{idempotency_key}", response_model=ReconciliacionRespuesta)
async def reconciliar_operacion(
    idempotency_key: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """CR-06: qué operación y qué trabajo existen para esta clave."""
    from services import idempotencia

    vista = await idempotencia.reconciliar(
        db=db, user_id=str(current_user.id), clave=idempotency_key
    )
    if vista is None:
        raise HTTPException(status_code=404, detail="Clave de idempotencia no encontrada.")
    return vista


@router.get("/proposals/{proposal_id}")
async def consultar_propuesta_de_docking(
    proposal_id: str,
    current_user: UserORM = Depends(get_current_user),
):
    from services.evaluation import proposals as propuestas

    try:
        return await propuestas.consultar(proposal_id, current_user)
    except propuestas.PropuestaNoAplicable as exc:
        raise _como_http(exc) from exc


@router.post("/proposals/{proposal_id}/reject")
async def rechazar_propuesta_de_docking(
    proposal_id: str,
    current_user: UserORM = Depends(get_current_user),
):
    from services.evaluation import proposals as propuestas

    try:
        await propuestas.rechazar(proposal_id, current_user)
    except propuestas.PropuestaNoAplicable as exc:
        raise _como_http(exc) from exc
    return {"status": "rejected", "id": proposal_id}


@router.post("/proposals/{proposal_id}/approve")
async def aprobar_propuesta_de_docking(
    proposal_id: str,
    body: AprobarPropuestaRequest,
    request: Request,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", max_length=200
    ),
):
    """Lanza la corrida que ESA propuesta describe, con la sesión de la cuenta.

    Con `Idempotency-Key` (CR-06), un reintento tras una respuesta perdida
    devuelve el `task_id` original sin lanzar una segunda evaluación.
    """
    from api.routers.evaluation import get_real_ip
    from services.evaluation import proposals as propuestas

    if idempotency_key:
        previa = await _reclamar_clave(
            db, usuario=current_user, clave=idempotency_key,
            operacion="aprobar_propuesta",
            documento={"proposal_id": proposal_id, "proposal_hash": body.proposal_hash},
        )
        if previa is not None:
            return previa

    try:
        corrida, _registro = await propuestas.aprobar(
            propuesta_id=proposal_id,
            huella=body.proposal_hash,
            usuario=current_user,
            db=db,
            client_ip=get_real_ip(request),
        )
    except propuestas.PropuestaNoAplicable as exc:
        if idempotency_key:
            await _fallar_clave(
                db, usuario=current_user, clave=idempotency_key, error=exc.detalle
            )
        raise _como_http(exc) from exc
    except HTTPException as exc:
        if idempotency_key:
            await _fallar_clave(
                db, usuario=current_user, clave=idempotency_key, error=exc.detail
            )
        raise

    # (Fase 6.6) Antes se anotaba el lanzamiento en el chat interno; sin chat,
    # el expediente vive en el sidecar. El mensaje sigue en la respuesta.
    mensaje = propuestas.mensaje_de_lanzamiento(corrida)
    respuesta = {
        "task_id": corrida.task_id,
        "target_pdb_id": corrida.target_pdb_id,
        "smiles_hash": corrida.smiles_hash,
        "message": mensaje,
    }
    if idempotency_key:
        await _sellar_clave(
            db, usuario=current_user, clave=idempotency_key,
            respuesta=respuesta, proposal_id=proposal_id, task_id=corrida.task_id,
        )
    return respuesta
