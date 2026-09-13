"""
api/routers/steam.py — Steamworks integration.

Verificacion de compra y licencia via Steam Web API.
Solo se activa en modo DESKTOP con STEAM_WEB_API_KEY configurada.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/steam", tags=["Steamworks"])
settings = get_settings()


@router.get("/verify")
async def verify_steam_purchase(
    steam_id: str = Query(..., min_length=17, max_length=17, description="SteamID64 del usuario"),
) -> dict[str, Any]:
    """
    Verifica que el usuario compro la app en Steam.

    En modo dev (sin STEAM_WEB_API_KEY), siempre retorna verified=true.
    En produccion, consulta la Steam Web API.
    """
    steam_api_key = os.getenv("STEAM_WEB_API_KEY", "")
    steam_app_id = os.getenv("STEAM_APP_ID", "")

    if not steam_api_key or not steam_app_id:
        # Modo dev: siempre verificado
        return {
            "verified": True,
            "tier": "base",
            "mode": "development",
            "message": "Steam API no configurada — verificacion omitida",
        }

    try:
        import httpx
        url = "https://api.steampowered.com/ISteamUser/CheckAppOwnership/v2/"
        params = {
            "key": steam_api_key,
            "steamid": steam_id,
            "appid": steam_app_id,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        owns = data.get("appownership", {}).get("ownsapp", False)
        if not owns:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No se encontro la licencia de Steam para esta aplicacion.",
            )

        # Verificar DLCs
        dlcs = []
        for dlc_id in os.getenv("STEAM_DLC_IDS", "").split(","):
            dlc_id = dlc_id.strip()
            if dlc_id:
                dlc_params = {"key": steam_api_key, "steamid": steam_id, "appid": dlc_id}
                dlc_resp = await client.get(url, params=dlc_params)
                dlc_data = dlc_resp.json()
                if dlc_data.get("appownership", {}).get("ownsapp"):
                    dlcs.append(dlc_id)

        tier = "pro" if dlcs else "base"
        log.info("steam_verified", steam_id=steam_id[:8], tier=tier)

        return {
            "verified": True,
            "tier": tier,
            "dlc": dlcs,
            "mode": "production",
        }

    except HTTPException:
        raise
    except Exception as e:
        log.warning("steam_verify_failed", error=str(e))
        # Degradacion gracil: si la API de Steam no responde, permitir uso
        return {
            "verified": True,
            "tier": "base",
            "mode": "degraded",
            "message": "Steam API no disponible — verificacion omitida temporalmente",
        }


@router.get("/health")
async def steam_health() -> dict[str, Any]:
    """Health check para integracion Steam."""
    steam_api_key = os.getenv("STEAM_WEB_API_KEY", "")
    steam_app_id = os.getenv("STEAM_APP_ID", "")

    return {
        "status": "ok",
        "configured": bool(steam_api_key and steam_app_id),
        "has_api_key": bool(steam_api_key),
        "has_app_id": bool(steam_app_id),
    }
