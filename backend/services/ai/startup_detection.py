from __future__ import annotations

import asyncio
from typing import Any

from services.ai.providers.base import HealthStatus, StartupMode
from services.ai.providers.registry import get_provider_registry
from utils.logger import get_logger

log = get_logger(__name__)

_CLOUD_PROVIDER_IDS = {"claude", "gemini", "openai"}


async def detect_startup_mode() -> dict:
    """
    Escanea todos los providers y determina el modo de inicio de MolChat.

    Returns:
        dict con:
        - mode: StartupMode.value ("auto_start" | "notify_fallback" | "manual_only")
        - reason: string explicativo para mostrar al usuario
        - working_providers: lista de providers que funcionan
        - failed_providers: lista de {id, name, reason} de los que fallaron
        - auto_start_local: bool (true si MolChat debe iniciarse con Local LLM)
    """
    registry = get_provider_registry()

    cloud_providers = []
    local_available = False

    for pid in _CLOUD_PROVIDER_IDS:
        p = registry.get(pid)
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

    if not cloud_providers or all(
        f["status"] in ("no_api_key",) for f in failed if f["id"] in _CLOUD_PROVIDER_IDS
    ):
        for f in failed:
            if f["status"] == "no_api_key":
                pass
            else:
                break
        any_configured = any(
            p.id in _CLOUD_PROVIDER_IDS and bool(p.config.api_key)
            for p in cloud_providers
        )

        if not any_configured:
            return _result(StartupMode.AUTO_START, local_available, working, failed,
                           "No se configuró ninguna clave de API. MolChat se inicia con el modo local "
                           "(Qwen 1.5B). Para usar un proveedor cloud, abre 'Intérprete IA Online' "
                           "en el menú de Opciones. Tus claves se almacenarán de forma encriptada y segura.")

    if working:
        names = [w["name"] for w in working]
        return _result(StartupMode.MANUAL_ONLY, local_available, working, failed,
                       f"Tiene {len(names)} proveedor(es) en funcionamiento: {', '.join(names)}. "
                       "MolChat no se inicia automáticamente. Actívelo desde Configuración > Intérprete de IA.")

    names = [f["name"] for f in failed if f["status"] != "no_api_key"]
    if names:
        reasons = [f"{f['name']}: {f['reason'][:60]}" for f in failed if f["status"] != "no_api_key"]
        return _result(StartupMode.NOTIFY_FALLBACK, local_available, working, failed,
                       f"Las claves de API no tienen saldo disponible: {' | '.join(reasons)}. "
                       "MolChat usará el modo local.")

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
