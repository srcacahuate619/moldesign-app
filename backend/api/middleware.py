"""
api/middleware.py

Middleware base del MVP.

Responsabilidades en esta fase:
- CORS consistente con config.py
- request_id por request
- logging estructurado de entrada/salida
- limpieza de contexto al finalizar

No añadimos aún rate limiting ni autenticación global obligatoria porque
el roadmap marca eso como posterior al cierre del núcleo científico.
"""

from __future__ import annotations

import time
from uuid import uuid4
from core.i18n import (
    localize_json_response,
    parse_accept_language,
    reset_request_locale,
    set_request_locale,
)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse

from core.config import get_settings
from utils.logger import bind_context, clear_context, get_logger

settings = get_settings()
log = get_logger(__name__)


def register_middleware(app: FastAPI) -> None:
    """Registra middleware HTTP base para el MVP."""
    from api.body_limit import BodyLimitMiddleware
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time", "Content-Disposition", "content-disposition"],
    )

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        from services.ai.red import fijar_identidad_peticion
        fijar_identidad_peticion(None)
        origin = request.headers.get("origin")
        if (request.method.upper() not in {"GET", "HEAD", "OPTIONS"}
                and origin and origin not in settings.cors_origins):
            return JSONResponse(status_code=403, content={"detail": "Origen no autorizado"})
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        started = time.perf_counter()
        locale = parse_accept_language(request.headers.get("accept-language"))
        locale_token = set_request_locale(locale)

        bind_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
        )

        log.info("request iniciada")
        try:
            response = await call_next(request)
            response = await localize_json_response(response)
        except Exception:
            log.exception("request falló con excepción no controlada")
            raise
        finally:
            reset_request_locale(locale_token)
            fijar_identidad_peticion(None)
            clear_context()

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(elapsed_ms)
        response.headers.setdefault(
            "Content-Language",
            locale,
        )

        bind_context(elapsed_ms=elapsed_ms)
        log.info(
            "request completada",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        clear_context()

        return response

    # En producción sólo se aceptan nombres locales. `testserver` pertenece
    # exclusivamente a TestClient en desarrollo; nunca al ejecutable instalado.
    allowed_hosts = ["127.0.0.1", "localhost", "tauri.localhost"]
    if settings.environment != "production":
        allowed_hosts.append("testserver")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
