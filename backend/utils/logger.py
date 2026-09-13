"""
utils/logger.py

Logging estructurado para todo el sistema.

Por qué structlog y no el logging estándar de Python:
- Logs en JSON: parseable por Grafana, Datadog, cualquier agregador
- Context binding: puedes adjuntar molecule_id o task_id a todos los
  logs de una request sin pasarlo manualmente a cada función
- Async-safe: no bloquea el event loop de FastAPI

Uso básico:
    from utils.logger import get_logger
    log = get_logger(__name__)
    log.info("molécula validada", smiles="CCO", mw=46.07)

Con contexto ligado (útil en endpoints):
    from utils.logger import get_logger, bind_context
    log = get_logger(__name__)
    bind_context(molecule_id="abc123", user_id="u456")
    log.info("iniciando docking")   # incluye molecule_id y user_id automáticamente
"""

import logging
import sys
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from core.config import get_settings


# ── Procesadores custom ───────────────────────────────────────────────────────

def _add_service_name(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Añade el nombre del servicio a cada log entry.
    Útil cuando los logs de múltiples microservicios van al mismo agregador.
    """
    event_dict["service"] = "moldesign-api"
    return event_dict


def _drop_color_message_key(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Elimina el campo 'color_message' que uvicorn añade a sus logs.
    Sin esto, los logs de uvicorn incluyen códigos ANSI en JSON, que rompen
    el parsing en Grafana/Datadog.
    """
    event_dict.pop("color_message", None)
    return event_dict


def _sanitize_sensitive_fields(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Reemplaza valores de campos sensibles antes de que lleguen al output.
    Evita que API keys o passwords aparezcan en los logs por accidente.
    """
    sensitive_keys = {"password", "secret_key", "api_key", "token", "authorization"}
    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***REDACTED***"
    return event_dict


# ── Configuración principal ───────────────────────────────────────────────────

def setup_logging() -> None:
    """
    Configura structlog y el logging estándar de Python.

    Debe llamarse UNA SOLA VEZ al arrancar la aplicación, en el lifespan
    de FastAPI (api/main.py). Si se llama múltiples veces, los handlers
    se duplican y los logs aparecen repetidos.

    En desarrollo: output legible en consola con colores.
    En producción: output JSON por línea, listo para ingestión.
    """
    settings = get_settings()

    # Nivel de log global
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Procesadores compartidos entre desarrollo y producción
    shared_processors: list[Any] = [
        # Añade timestamp ISO 8601
        structlog.stdlib.add_log_level,
        # Nota: no usamos structlog.stdlib.add_logger_name porque
        # PrintLoggerFactory produce loggers sin atributo .name.
        # El nombre del logger se inyecta vía get_logger() → bind(logger=name).
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,   # Fusiona contexto ligado con bind_context()
        _add_service_name,
        _drop_color_message_key,
        _sanitize_sensitive_fields,
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development:
        # Desarrollo: output con colores y formato legible
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Producción: JSON por línea — una entrada de log = un objeto JSON
        # Esto es lo que Grafana/Datadog/CloudWatch esperan
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # v1.7: Rotating file logger (DESKTOP/service mode — stdout no es visible)
    try:
        from logging.handlers import RotatingFileHandler
        log_dir = Path(settings.local_data_dir).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "moldesign.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        logging.getLogger().addHandler(file_handler)
    except Exception:
        pass  # non-critical — continue without file logging

    # Redirige el logging estándar de Python (usado por SQLAlchemy, uvicorn,
    # etc.) a structlog para que todo salga en el mismo formato
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Silencia loggers muy verbosos en producción
    if settings.is_production:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Confirma que el logger quedó configurado
    log = structlog.get_logger("utils.logger")
    log.info(
        "sistema de logging inicializado",
        environment=settings.environment,
        log_level=settings.log_level,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Retorna un logger con el nombre del módulo que lo solicita.

    Uso estándar al inicio de cada módulo:
        log = get_logger(__name__)

    Pasar __name__ (no un string hardcodeado) permite filtrar logs
    por módulo en Grafana sin configuración adicional.
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Liga variables de contexto al logger de la request actual.

    Todo lo que se loguee después de esta llamada — en cualquier función
    llamada dentro de la misma coroutine — incluirá estos valores
    automáticamente.

    Uso típico en un middleware de FastAPI:
        async def logging_middleware(request: Request, call_next):
            bind_context(
                request_id=str(uuid4()),
                path=request.url.path,
                method=request.method,
            )
            response = await call_next(request)
            return response

    Uso en un job del dispatcher local:
        async def run_docking(molecule_id: str):
            bind_context(molecule_id=molecule_id, task="docking")
            log.info("iniciando docking")   # incluye molecule_id automáticamente
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """
    Limpia el contexto ligado al finalizar una request.

    Debe llamarse en el middleware después de que la response fue enviada,
    para que el contexto de una request no contamine la siguiente que
    reutilice el mismo worker.
    """
    structlog.contextvars.clear_contextvars()


# ── Logger de módulo ─────────────────────────────────────────────────────────
# Para uso interno de este módulo, antes de que setup_logging() sea llamado.
# No usar este patrón en otros módulos — usa get_logger(__name__) allí.
log = get_logger(__name__)
