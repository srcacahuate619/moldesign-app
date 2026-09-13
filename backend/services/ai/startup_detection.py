"""Qué modo de arranque le toca a MolChat, sin salir a preguntárselo a nadie.

MOLCHAT-NET-006. Esta sonda era la salida a la red **más temprana** del
producto y la única sin puerta: el `health_check` de un proveedor cloud no
inspecciona configuración, manda un turno real —`"hi"`, `max_tokens=1`— a
`api.anthropic.com`, `generativelanguage.googleapis.com` o el `base_url` de
OpenAI. Corría al montarse `ChatPanel`, sin identidad de cuenta, sin consultar
`consent.py` y sin mirar `MOLDESIGN_OFFLINE`.

No viajaba trabajo del investigador —el prompt es «hi»—, pero sí la clave de
API, la dirección IP del equipo y el hecho de que el producto acaba de
arrancar, hacia tres empresas, antes de que nadie autorizara nada. Eso basta
para que «no se envía nada sin tu permiso» fuera falso, que es lo que tiene que
poder afirmarse en la ficha de privacidad.

Ahora el destino sin autorizar **no se consulta**, y eso se dice: `working` es
lo que responde, `failed` lo que falló, y `sin_consentimiento` lo que no se
preguntó. Un proveedor que no se sondeó no es un proveedor caído.
"""

from __future__ import annotations

import asyncio
from typing import Any

from services.ai.providers.base import HealthStatus, StartupMode
from services.ai.providers.registry import get_provider_registry
from utils.logger import get_logger

log = get_logger(__name__)

_CLOUD_PROVIDER_IDS = {"claude", "gemini", "openai"}

#: Los dos estados que se alcanzan **sin** tocar la red. Ninguno de los dos
#: dice nada sobre si el proveedor funciona, así que ninguno puede contarse
#: como «la clave no tiene saldo».
_SIN_LLAMADA = {HealthStatus.NO_API_KEY.value, HealthStatus.SIN_CONSENTIMIENTO.value}


def _bloqueo(provider: Any, user_id: str | None) -> str:
    """Qué impide sondear a ese proveedor, o `""` si se puede."""
    from services.ai.consent import destino_de, motivo_de_bloqueo

    return motivo_de_bloqueo(destino_de(provider), user_id)


async def detect_startup_mode(
    user_id: str | None = None, incluir_heredadas: bool = False
) -> dict:
    """
    Escanea todos los providers y determina el modo de inicio de MolChat.

    `user_id` es la cuenta que pregunta. Sin ella no hay consentimiento posible
    —el permiso es de alguien, no del proceso—, así que ningún proveedor cloud
    se sondea: se informa de su existencia y se arranca en local.

    `incluir_heredadas` es la vista de D-07 y llega hasta aquí porque la
    configuración heredada incluye el `base_url`, que es el destino. El
    consentimiento, en cambio, **nunca** se hereda: lo que se hereda es a dónde
    iría, no el permiso para ir.

    Returns:
        dict con:
        - mode: StartupMode.value ("auto_start" | "notify_fallback" | "manual_only")
        - reason: string explicativo para mostrar al usuario
        - working_providers: lista de providers que funcionan
        - failed_providers: lista de {id, name, status, reason}; `status` distingue
          los que fallaron de los que no se consultaron (`sin_consentimiento`)
        - auto_start_local: bool (true si MolChat debe iniciarse con Local LLM)
    """
    registry = get_provider_registry()

    cloud_providers = []
    local_available = False

    for pid in _CLOUD_PROVIDER_IDS:
        # `resolve_for_user` y no `get`: la clave y sobre todo el `base_url`
        # —que es el destino— son datos de cuenta desde D-09. Sondear el
        # catálogo desnudo probaría un destino distinto del que usaría el turno.
        p = registry.resolve_for_user(pid, user_id, incluir_heredadas)
        if p:
            cloud_providers.append(p)

    local = registry.get("local")
    if local:
        ok, _ = local.validate_config()
        local_available = ok

    working: list[dict] = []
    failed: list[dict] = []

    async def check_provider(p: Any) -> None:
        try:
            # Sin configuración no hay nada que sondear y nada saldría: es el
            # caso más común y merece su propio mensaje, no el de consentimiento.
            ok, msg = p.validate_config()
            if not ok:
                failed.append({
                    "id": p.id,
                    "name": p.name,
                    "status": HealthStatus.NO_API_KEY.value,
                    "reason": msg,
                })
                return

            falta = _bloqueo(p, user_id)
            if falta:
                log.info("sonda_de_arranque_no_enviada", provider_id=p.id)
                failed.append({
                    "id": p.id,
                    "name": p.name,
                    "status": HealthStatus.SIN_CONSENTIMIENTO.value,
                    "reason": falta,
                })
                return

            result = await p.health_check()
            if result.status == HealthStatus.OK:
                working.append({
                    "id": p.id,
                    "name": p.name,
                    "latency_ms": result.latency_ms,
                })
            else:
                failed.append({
                    "id": p.id,
                    "name": p.name,
                    "status": result.status.value,
                    "reason": result.message,
                })
        except Exception as e:
            failed.append({
                "id": p.id,
                "name": p.name if hasattr(p, "name") else p.id,
                "status": "error",
                "reason": str(e)[:120],
            })

    await asyncio.gather(*[check_provider(p) for p in cloud_providers], return_exceptions=True)

    if working:
        names = [w["name"] for w in working]
        return _result(StartupMode.MANUAL_ONLY, local_available, working, failed,
                       f"Tiene {len(names)} proveedor(es) en funcionamiento: {', '.join(names)}. "
                       "MolChat no se inicia automáticamente. Actívelo desde Configuración > Intérprete de IA.")

    # Nadie responde, y las tres razones posibles piden mensajes distintos.
    # Antes se juntaban todas bajo «las claves de API no tienen saldo», que de
    # un destino no consultado es una afirmación inventada.
    caidos = [f for f in failed if f["status"] not in _SIN_LLAMADA]
    if caidos:
        reasons = [f"{f['name']}: {f['reason'][:60]}" for f in caidos]
        return _result(StartupMode.NOTIFY_FALLBACK, local_available, working, failed,
                       f"Las claves de API no tienen saldo disponible: {' | '.join(reasons)}. "
                       "MolChat usará el modo local.")

    sin_permiso = [f for f in failed if f["status"] == HealthStatus.SIN_CONSENTIMIENTO.value]
    if sin_permiso:
        nombres = ", ".join(f["name"] for f in sin_permiso)
        return _result(StartupMode.AUTO_START, local_available, working, failed,
                       f"No consulté los proveedores cloud configurados ({nombres}): su destino no "
                       "está autorizado para esta cuenta, o el equipo está en modo offline. MolChat "
                       "se inicia con el modo local (Qwen 1.5B), que no sale de tu máquina. Para "
                       "usarlos, autorizá el destino en Opciones > Intérprete IA.")

    any_configured = any(
        p.id in _CLOUD_PROVIDER_IDS and bool(p.config.api_key)
        for p in cloud_providers
    )
    if not any_configured:
        return _result(StartupMode.AUTO_START, local_available, working, failed,
                       "No se configuró ninguna clave de API. MolChat se inicia con el modo local "
                       "(Qwen 1.5B). Para usar un proveedor cloud, abre 'Intérprete IA Online' "
                       "en el menú de Opciones. Tus claves se almacenarán de forma encriptada y segura.")

    return _result(StartupMode.MANUAL_ONLY, local_available, working, failed,
                   "No se detectaron proveedores. MolChat se puede activar manualmente.")


def _result(
    mode: StartupMode,
    local_available: bool,
    working: list,
    failed: list,
    reason: str,
) -> dict:
    return {
        "mode": mode.value,
        "reason": reason,
        "working_providers": working,
        "failed_providers": failed,
        "local_available": local_available,
        "auto_start_local": mode == StartupMode.AUTO_START,
    }
