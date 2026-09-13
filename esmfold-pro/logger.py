"""
logger.py — Logging estructurado para ESMFold-Pro (RFdiffusion).

Salida dual: stdout (desarrollo) + archivo rotativo diario.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from config import get_config

_logger_cache: dict[str, logging.Logger] = {}


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Configura el logging raíz."""
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Consola
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root_logger.addHandler(console)

    # Archivo
    file_handler = logging.FileHandler(
        log_dir / f"esmfold-pro-{today}.log", encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger cacheado por nombre."""
    if name not in _logger_cache:
        _logger_cache[name] = logging.getLogger(name)
    return _logger_cache[name]
