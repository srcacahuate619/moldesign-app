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

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from utils.logger import bind_context, clear_context, get_logger

settings = get_settings()
log = get_logger(__name__)


def register_middleware(app: FastAPI) -> None:
    """Registra middleware HTTP base para el MVP."""
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
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        started = time.perf_counter()

        bind_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.url.query),
        )

        log.info("request iniciada")
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request falló con excepción no controlada")
            raise
        finally:
            clear_context()

        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = str(elapsed_ms)

        bind_context(elapsed_ms=elapsed_ms)
        log.info(
            "request completada",
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        clear_context()

        return response
