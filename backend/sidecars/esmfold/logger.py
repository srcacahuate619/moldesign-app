"""
logger.py — Logging estructurado con rotación diaria.

Salida a stdout + archivo `logs/esmfold-YYYYMMDD.log`.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


_INITIALIZED = False


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Inicializa logging global. Idempotente."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    log_dir.mkdir(parents=True, exist_ok=True)

    log_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)

    # Limpiar handlers previos (evita duplicación si uvicorn reimporta)
    for h in list(root.handlers):
        root.removeHandler(h)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Consola
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # Archivo rotado por día
    today = datetime.now().strftime("%Y%m%d")
    fh = TimedRotatingFileHandler(
        filename=log_dir / f"esmfold-{today}.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Silenciar librerías ruidosas
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _INITIALIZED = True


class _LoggerConCampos:
    """Acepta el estilo `log.info("evento", clave=valor)` sobre logging estándar.

    El servicio se escribió con la sintaxis de structlog —así se loguea en todo
    el backend— pero `logger.py` devolvía un `logging.Logger` pelado, que
    interpreta el segundo argumento posicional como parte del formato y explota
    con `Logger.info() got multiple values for argument 'msg'` en cuanto recibe
    un kwarg.

    Reventaba en el arranque, en la línea que anuncia el predictor creado: el
    servicio no podía llegar a servir ni una petición. Que nadie lo hubiera visto
    dice lo que había que decir sobre si este motor estaba realmente conectado.

    Se resuelve aquí y no reescribiendo 37 llamadas: los campos se aplanan a
    `clave=valor` detrás del mensaje, que es lo que se quería leer.
    """

    __slots__ = ("_log",)

    def __init__(self, log: logging.Logger):
        self._log = log

    @staticmethod
    def _componer(mensaje: object, campos: dict) -> str:
        if not campos:
            return str(mensaje)
        extras = " ".join(f"{k}={v!r}" for k, v in campos.items())
        return f"{mensaje} {extras}"

    def debug(self, mensaje: object = "", **campos) -> None:
        self._log.debug(self._componer(mensaje, campos))

    def info(self, mensaje: object = "", **campos) -> None:
        self._log.info(self._componer(mensaje, campos))

    def warning(self, mensaje: object = "", **campos) -> None:
        self._log.warning(self._componer(mensaje, campos))

    def error(self, mensaje: object = "", **campos) -> None:
        self._log.error(self._componer(mensaje, campos))

    def exception(self, mensaje: object = "", **campos) -> None:
        self._log.exception(self._componer(mensaje, campos))

    def critical(self, mensaje: object = "", **campos) -> None:
        self._log.critical(self._componer(mensaje, campos))


def get_logger(name: str) -> _LoggerConCampos:
    return _LoggerConCampos(logging.getLogger(name))