from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from api.dependencies import get_current_user, get_current_user_optional
from core.identity import es_invitado
from core.config import get_settings
from core.models import AIChatRequest, AIChatResponse, ProviderInfoResponse, UserORM
from services.ai import consent
from services.ai.chat_service import get_chat_service
from services.ai.memory_store import PersistenciaFallida
from services.ai.redaccion import redactar_secretos
from services.ai.providers.registry import get_provider_registry
from services.ai.startup_detection import detect_startup_mode
from utils.logger import get_logger

log = get_logger(__name__)

#: MOLCHAT-AUD-01, higiene del §8. 25 MB son varios minutos de audio de un
#: dictado real; por encima de eso no es una pregunta, es un cuerpo sin tope
#: cargándose en memoria.
MAX_BYTES_AUDIO = 25 * 1024 * 1024
settings = get_settings()

router = APIRouter(prefix="/ai", tags=["MolChat"])


def _vista_de(user: UserORM | None) -> dict:
    """Con qué identidad se mira el registro de proveedores (D-09).

    Sin sesión —las dos sondas de arranque— se mira el catálogo desnudo: sin
    `user_id` no se puede afirmar `configured`, porque desde D-09 eso es un dato
    de cuenta. La cuenta invitada además hereda la configuración anterior a que
    existieran las cuentas, igual que hereda las conversaciones (D-07).
    """
    if user is None:
        return {"user_id": None, "incluir_heredadas": False}
    return {"user_id": str(user.id), "incluir_heredadas": es_invitado(user)}


def _get_provider_config_from_settings(provider_id: str) -> dict:
    from services.ai.providers.base import ProviderConfig

    config_map = {
        "local": ProviderConfig(
            model="qwen2.5-1.5b-instruct-q4_k_m.gguf",
            temperature=0.1,
            max_tokens=4096,
        ),
        "ollama": ProviderConfig(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            temperature=0.1,
            max_tokens=4096,
        ),
        "claude": ProviderConfig(
            api_key=settings.anthropic_api_key or "",
            model=settings.anthropic_model,
            temperature=0.5,
            max_tokens=4096,
        ),
        "gemini": ProviderConfig(
            api_key=settings.gemini_api_key or "",
            model=settings.gemini_model,
            temperature=0.5,
            max_tokens=4096,
        ),
        "openai": ProviderConfig(
            api_key=settings.groq_api_key or settings.openai_api_key or "",
            base_url=settings.groq_base_url if not settings.openai_api_key else settings.openai_base_url,
            model=settings.groq_default_model if not settings.openai_api_key else settings.openai_default_model,
            temperature=0.5,
            max_tokens=4096,
        ),
    }
    return config_map.get(provider_id, ProviderConfig())


def _bootstrap_providers():
    registry = get_provider_registry()

    from services.ai.providers.local_llm_provider import LocalLLMProvider
    from services.ai.providers.ollama_provider import OllamaProvider
    from services.ai.providers.claude_provider import ClaudeProvider
    from services.ai.providers.gemini_provider import GeminiProvider
    from services.ai.providers.openai_provider import OpenAIProvider

    for pid, cls in [
        ("local", LocalLLMProvider),
        ("ollama", OllamaProvider),
        ("claude", ClaudeProvider),
        ("gemini", GeminiProvider),
        ("openai", OpenAIProvider),
    ]:
        if not registry.get(pid):
            config = _get_provider_config_from_settings(pid)
            registry.register(cls(config=config))

    # D-09: el catálogo se queda con los valores del entorno. La configuración
    # de cada cuenta se aplica al resolver el proveedor, no aquí.
    registry.apply_env_defaults()


def _bootstrap_tools():
    """Registrar todas las tools de MolChat (offline-first)."""
    try:
        from services.ai.tools.rdkit_tools import register_rdkit_tools
        register_rdkit_tools()
    except ImportError:
        pass
    try:
        from services.ai.tools.docking_tools import register_docking_tools
        register_docking_tools()
    except ImportError:
        pass
    try:
        from services.ai.tools.admet_tools import register_admet_tools
        register_admet_tools()
    except ImportError:
        pass
    try:
        from services.ai.tools.web_tools import register_web_tools
        register_web_tools()
    except ImportError:
        pass
    try:
        from services.ai.tools.web_tools import register_web_tools_extended
        register_web_tools_extended()
    except ImportError:
        pass
    try:
        from services.ai.tools.molgraph_tool import register_molgraph_tools
        register_molgraph_tools()
    except ImportError:
        pass
    try:
        # Slim descriptions para ahorrar tokens (~100 vs ~250)
        from services.ai.tools.analog_tools import register_analog_tools
        register_analog_tools(verbose=False)
    except ImportError:
        pass
    try:
        from services.ai.tools.suggest_tools import register_suggest_tools
        register_suggest_tools()
    except ImportError:
        pass
    try:
        from services.ai.tools.evaluation_tools import register_evaluation_tools
        register_evaluation_tools()
    except ImportError:
        pass
    try:
        from services.ai.tools.session_tools import register_session_tools
        register_session_tools()
    except ImportError:
        pass


@router.get("/startup")
async def startup_detection(
    current_user: UserORM | None = Depends(get_current_user_optional),
):
    """Sonda de arranque. La identidad es opcional, pero cambia lo que sale.

    Es la llamada más temprana del producto y sondeaba a Anthropic, Google y
    OpenAI con un turno real antes de que nadie autorizara nada. Ahora se
    resuelve con la cuenta que pregunta: sin sesión no hay consentimiento
    posible, así que no se consulta ningún destino remoto y MolChat arranca en
    local.
    """
    _bootstrap_providers()
    _bootstrap_tools()
    return await detect_startup_mode(**_vista_de(current_user))


@router.get("/providers", response_model=list[ProviderInfoResponse])
async def list_providers(
    current_user: UserORM | None = Depends(get_current_user_optional),
):
    """Sonda de arranque: la interfaz la llama antes del auto-login.

    D-09 hace que `configured` y `active` sean datos de cuenta, así que la
    identidad es **opcional**: con sesión se responde la vista de esa cuenta;
    sin sesión, el catálogo de la máquina y `configured=False`. Así la sonda
    sigue sirviendo al arranque sin publicar de quién es la clave.
    """
    _bootstrap_providers()
    _bootstrap_tools()
    registry = get_provider_registry()
    return registry.list_providers(**_vista_de(current_user))


@router.get("/providers/active")
async def get_active_provider(
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    registry = get_provider_registry()
    info = registry.get_active_info(**_vista_de(current_user))
    return info or {"id": None, "name": "Sin proveedor", "configured": False, "active": False}


@router.post("/providers/active")
async def set_active_provider(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    provider_id = payload.get("provider_id", "")
    _bootstrap_providers()
    registry = get_provider_registry()
    ok = registry.set_active(provider_id, user_id=str(current_user.id))
    if not ok:
        raise HTTPException(status_code=404, detail=f"Proveedor '{provider_id}' no encontrado")
    return {"status": "ok", "active_provider": provider_id}


@router.post("/providers/configure")
async def configure_provider(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    provider_id = payload.get("provider_id", "")
    _bootstrap_providers()
    registry = get_provider_registry()
    if not registry.get(provider_id):
        raise HTTPException(status_code=404, detail=f"Proveedor '{provider_id}' no encontrado")

    vista = _vista_de(current_user)
    user_id = str(current_user.id)

    # MOLCHAT-BE-003, la mitad que faltaba: el `base_url` no es un ajuste, es el
    # destino de los datos. Cambiarlo exige confirmación explícita, y el 409
    # declara a dónde iría para que la interfaz no pueda callarlo.
    destino_previo = consent.destino_de(registry.resolve_for_user(provider_id, **vista))
    if "base_url" in payload:
        propuesto = consent.destino_propuesto(provider_id, payload["base_url"])
        if propuesto.host != destino_previo.host and not payload.get("confirmar_destino"):
            raise HTTPException(
                status_code=409,
                detail={
                    "motivo": "cambio_de_destino",
                    "mensaje": (
                        f"Esto cambia a dónde salen los datos del chat: de "
                        f"{destino_previo.host or 'esta máquina'} a "
                        f"{propuesto.host or 'esta máquina'}. Confirmalo para aplicarlo."
                    ),
                    "destino_actual": destino_previo.como_dict(),
                    "destino_propuesto": propuesto.como_dict(),
                },
            )

    from services.ai.provider_config_store import save_provider_config
    save_provider_config(
        provider_id=provider_id,
        user_id=user_id,
        api_key=payload.get("api_key"),
        base_url=payload.get("base_url"),
        model=payload.get("model"),
        temperature=float(payload["temperature"]) if "temperature" in payload else None,
    )

    resuelto = registry.resolve_for_user(provider_id, **vista)
    destino = consent.destino_de(resuelto)

    # Si el destino cambió, el permiso anterior no viaja con él: era para otro
    # sitio. Se retira aquí para que nadie dependa de acordarse de revocarlo.
    consentimiento_revocado = False
    if destino.host != destino_previo.host:
        consentimiento_revocado = consent.revocar(provider_id, user_id)

    return {
        "status": "ok",
        "provider_id": provider_id,
        "configured": resuelto.validate_config()[0],
        "destino": destino.como_dict(),
        "consentido": consent.hay_consentimiento(destino, user_id),
        "consentimiento_revocado": consentimiento_revocado,
    }


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
    from services.ai import red

    return {
        "modo_offline": red.modo_offline(),
        "destinos": red.estado_de_destinos(str(current_user.id)),
    }


@router.post("/consent/red")
async def otorgar_destino_de_red(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    """Autoriza un servicio externo concreto para esta cuenta."""
    from services.ai import red

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
    from services.ai import red

    retirado = red.revocar(servicio, str(current_user.id))
    return {"status": "ok", "revocado": retirado}


@router.get("/consent")
async def listar_consentimientos(
    current_user: UserORM = Depends(get_current_user),
):
    """A dónde iría cada proveedor y si esta cuenta autorizó ese destino.

    Es lo que permite a la interfaz declarar el destino de forma permanente en
    vez de dejarlo implícito (MOLCHAT-NET-005 y la mitad abierta de BE-003).
    """
    _bootstrap_providers()
    registry = get_provider_registry()
    return {"destinos": consent.estado_de_destinos(registry, **_vista_de(current_user))}


@router.post("/consent")
async def otorgar_consentimiento(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    """Autoriza el destino **que el investigador vio**, no el que haya ahora.

    El cuerpo trae el `host` que la interfaz mostró. Si entretanto cambió, se
    responde 409 en vez de autorizar un destino distinto del que se consintió.
    """
    provider_id = payload.get("provider_id", "")
    _bootstrap_providers()
    registry = get_provider_registry()
    resuelto = registry.resolve_for_user(provider_id, **_vista_de(current_user))
    if resuelto is None:
        raise HTTPException(status_code=404, detail=f"Proveedor '{provider_id}' no encontrado")

    destino = consent.destino_de(resuelto)
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
                "destino": destino.como_dict(),
            },
        )

    if not destino.es_remoto:
        return {"status": "ok", "destino": destino.como_dict(), "consentido": True}

    registro = consent.otorgar(destino, str(current_user.id))
    return {
        "status": "ok",
        "destino": destino.como_dict(),
        "consentido": True,
        "otorgado_en": registro["otorgado_en"],
    }


@router.delete("/consent/{provider_id}")
async def revocar_consentimiento(
    provider_id: str,
    current_user: UserORM = Depends(get_current_user),
):
    """Retira la autorización. A partir del siguiente turno no sale nada por ahí."""
    revocado = consent.revocar(provider_id, str(current_user.id))
    return {"status": "ok", "provider_id": provider_id, "revocado": revocado}


@router.get("/models")
async def list_models(
    provider_id: str | None = Query(None),
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    registry = get_provider_registry()
    provider = registry.resolve_for_user(provider_id, **_vista_de(current_user))
    if not provider:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    models = await provider.list_models()
    return {"provider": provider.id, "models": models}


# ── Model Registry (HuggingFace search + download) ─────────────────

@router.get("/models/search")
async def search_models(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=16, le=30),
    current_user: UserORM = Depends(get_current_user),
):
    from services.ai.model_registry import _get_hf_list_models, _scan_logical_gguf_files
    cuenta = str(current_user.id)
    results = _get_hf_list_models(q, limit, user_id=cuenta)
    enriched = []
    for r in results:
        files = _scan_logical_gguf_files(r["id"], user_id=cuenta)
        r["gguf_files"] = files
        enriched.append(r)
    return {"query": q, "results": enriched, "total": len(enriched)}


@router.get("/models/local")
async def list_local_models(
    current_user: UserORM = Depends(get_current_user),
):
    from services.ai.model_registry import get_local_models
    return {"models": get_local_models()}


@router.post("/models/download")
async def start_model_download(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    model_id = payload.get("model_id", "")
    filename = payload.get("filename", "")
    if not model_id or not filename:
        raise HTTPException(status_code=400, detail="model_id y filename requeridos")
    from services.ai.model_registry import start_download
    dl = start_download(model_id, filename)
    return dl


@router.get("/models/download/{dl_id}")
async def get_model_download_status(
    dl_id: str,
    current_user: UserORM = Depends(get_current_user),
):
    from services.ai.model_registry import get_download_status
    dl = get_download_status(dl_id)
    if dl is None:
        raise HTTPException(status_code=404, detail="Descarga no encontrada o expirada")
    return dl


@router.get("/models/recommend-quant")
async def recommend_quantization(
    current_user: UserORM = Depends(get_current_user),
):
    """Recomendar nivel de cuantización según RAM/VRAM disponible."""
    from services.ai.model_registry import recommend_quantization as rec_quant

    ram_free = 0.0
    vram_free = -1.0
    try:
        from services.ai.resource_manager import get_resource_manager
        rm = get_resource_manager()
        status = rm.get_status()
        ram_free = status.get("ram_free_gb", 0.0)
        vram_free = status.get("vram_free_gb", -1.0)
    except ImportError:
        pass

    return rec_quant(ram_free_gb=ram_free, vram_free_gb=vram_free)


@router.post("/speech-to-text")
async def speech_to_text(
    request: Request,
    current_user: UserORM = Depends(get_current_user),
):
    """Transcribir audio a texto usando whisper local (offline, sin API key)."""
    from services.ai.speech_to_text import get_transcriber, is_whisper_available

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
    from services.ai.speech_to_text import is_whisper_available
    return {
        "available": is_whisper_available(),
        "model": "tiny",
        "models_dir": str(
            Path(__file__).parent.parent.parent.parent / "models" / "whisper"
        ),
    }


@router.post("/chat")
async def chat_completion(
    request: AIChatRequest,
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    _bootstrap_tools()
    chat_service = get_chat_service()
    # MOLCHAT-BE-002: el endpoint exige sesión, así que la identidad ya no es
    # opcional y las herramientas dejan de caer al usuario demo. Antes esto era
    # siempre `None` en la práctica, porque el cliente no enviaba token en
    # ninguna llamada.
    user_id = str(current_user.id)
    # D-09: la cuenta invitada hereda la configuración de proveedor anterior a
    # que existieran las cuentas, igual que hereda las conversaciones (D-07).
    hereda = es_invitado(current_user)

    if request.stream:
        async def event_stream():
            async for token in chat_service.chat(
                messages=[{"role": m.role, "content": m.content} for m in request.messages],
                provider_id=request.provider_id,
                molecule_context=request.molecule_context,
                mode=request.mode,
                allow_web=request.allow_web,
                user_id=user_id,
                incluir_heredadas=hereda,
            ):
                if token.startswith("__WARNING__:"):
                    warning = token[len("__WARNING__:"):]
                    yield f"event: warning\ndata: {warning}\n\n"
                elif token:
                    # SSE válido: las respuestas deterministas (build_*_response)
                    # son multi-línea ("Propiedades de aspirina:\n- MW: 180.2...").
                    # El parser del frontend (AIContext.tsx) corta por "\n\n" y
                    # une las líneas "data: " de un MISMO evento con "\n". Si
                    # emitimos el token crudo con newlines internos, el parser
                    # antiguo descartaba todo tras la primera línea (bug SSE).
                    yield "data: " + "\ndata: ".join(token.split("\n")) + "\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    else:
        from services.ai.providers.registry import get_provider_registry
        registry = get_provider_registry()
        provider = registry.resolve_for_user(request.provider_id, **_vista_de(current_user))

        content, fb_info = await chat_service.chat_with_info(
            messages=[{"role": m.role, "content": m.content} for m in request.messages],
            provider_id=request.provider_id,
            molecule_context=request.molecule_context,
            allow_web=request.allow_web,
            user_id=user_id,
            incluir_heredadas=hereda,
            mode=request.mode,
        )

        provider_name = provider.name if provider else "desconocido"
        if fb_info.fallback_used:
            provider_name = "local (fallback)"
        return AIChatResponse(
            content=content,
            provider=provider_name,
            conversation_id=(
                chat_service.get_conversation(user_id=user_id).id
                if chat_service.get_conversation(user_id=user_id)
                else None
            ),
            warning=fb_info.warning or None,
            fallback_used=fb_info.fallback_used,
        )


@router.post("/conversations")
async def create_conversation(
    payload: dict | None = None,
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    chat_service = get_chat_service()
    ctx = payload.get("molecule_context") if payload else None
    # MOLCHAT-BE-008: si el historial local no acepta la conversación, no se
    # devuelve un id. Antes esto se tragaba el error y el investigador recibía
    # una conversación que existía sólo en memoria.
    try:
        conv = chat_service.create_conversation(ctx, user_id=str(current_user.id))
    except PersistenciaFallida as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo crear la conversación en el historial local: {exc}",
        ) from exc
    return {
        "id": conv.id,
        "created_at": conv.created_at,
        "message_count": 0,
    }


@router.get("/conversations")
async def list_conversations(
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    chat_service = get_chat_service()
    # D-07: sólo el invitado ve las conversaciones anteriores a que existiera
    # la columna de dueño. No se les asigna propietario por suposición.
    try:
        return chat_service.list_conversations(
            user_id=str(current_user.id), incluir_heredadas=es_invitado(current_user)
        )
    except PersistenciaFallida as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo leer el historial local: {exc}",
        ) from exc


@router.get("/conversations/{conv_id}")
async def get_conversation(
    conv_id: str,
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    chat_service = get_chat_service()
    # MOLCHAT-BE-008: `None` es un 404 legítimo —no existe o no es tuya—; un
    # fallo del historial local es un 503. Antes los dos eran el mismo 404.
    try:
        conv = chat_service.load_conversation_from_db(
            conv_id,
            user_id=str(current_user.id),
            incluir_heredadas=es_invitado(current_user),
        )
    except PersistenciaFallida as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo leer el historial local: {exc}",
        ) from exc
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {
        "id": conv.id,
        "messages": conv.messages,
        "summary": conv.summary,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "molecule_context": conv.molecule_context,
    }


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: str,
    current_user: UserORM = Depends(get_current_user),
):
    _bootstrap_providers()
    chat_service = get_chat_service()
    # MOLCHAT-BE-008: no se contesta «deleted» sin haber borrado. Decir que un
    # historial ya no está cuando sigue estando es la peor de las tres formas
    # de tragarse el error.
    try:
        borrada = chat_service.delete_conversation(
            conv_id,
            user_id=str(current_user.id),
            incluir_heredadas=es_invitado(current_user),
        )
    except PersistenciaFallida as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo borrar del historial local: {exc}",
        ) from exc
    if not borrada:
        raise HTTPException(status_code=404, detail="Conversación no encontrada")
    return {"status": "deleted", "id": conv_id}


@router.get("/status")
async def ai_status(
    current_user: UserORM | None = Depends(get_current_user_optional),
):
    """Sonda de arranque. Ver la nota de identidad opcional en `list_providers`."""
    _bootstrap_providers()
    _bootstrap_tools()
    registry = get_provider_registry()
    vista = _vista_de(current_user)
    try:
        from services.ai.resource_manager import get_resource_manager
        rm = get_resource_manager()
        resource_status = rm.get_status()
    except ImportError:
        resource_status = {}

    tools_list = []
    try:
        from services.ai.tool_registry import get_tool_registry
        tr = get_tool_registry()
        for t in tr.list_all():
            tools_list.append({
                "name": t.name,
                "description": t.description,
                "offline": t.offline,
            })
    except ImportError:
        pass

    # v1.x — info del sidecar `llama-server.exe` (ver docs/33_MIGRATION_LLAMA_SERVER.md).
    # Solo lectura: el puerto se fija por config.py (`llama_server_port=8400`).
    llama_server_info: dict = {
        "available": False,
        "running": False,
        "port": None,
        "pid": None,
    }
    try:
        from services.ai.local_llm import get_local_llm, is_local_llm_available
        from core.config import get_settings
        llama_server_info["available"] = bool(is_local_llm_available())
        llama_server_info["port"] = get_settings().llama_server_port
        llm = get_local_llm()
        if llm is not None and llm.is_loaded and llm._process is not None:
            llama_server_info["running"] = True
            llama_server_info["pid"] = llm._process.pid
    except ImportError:
        pass

    return {
        "providers": registry.list_providers(**vista),
        "active_provider": registry.get_active_info(**vista),
        "resources": resource_status,
        "tools": tools_list,
        "llama_server": llama_server_info,
    }


@router.patch("/settings")
async def update_ai_settings(
    payload: dict,
    current_user: UserORM = Depends(get_current_user),
):
    """Actualizar configuración global de IA (keep_loaded)."""
    try:
        from services.ai.resource_manager import get_resource_manager
        rm = get_resource_manager()
        if "keep_loaded" in payload:
            rm.set_keep_loaded(bool(payload["keep_loaded"]))
    except ImportError:
        pass
    return {"status": "ok"}


@router.post("/models/open-folder")
async def open_models_folder(
    current_user: UserORM = Depends(get_current_user),
):
    """Abre la carpeta de modelos locales en el explorador de archivos del sistema."""
    import os
    import subprocess
    import sys
    from services.ai.local_llm import MODEL_SEARCH_PATHS

    # Usar el home folder (~/MolDesign/models/llm) como default
    target_dir = MODEL_SEARCH_PATHS[1]
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(target_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(target_dir)])
        else:
            subprocess.run(["xdg-open", str(target_dir)])
        return {"status": "ok", "path": str(target_dir)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
