"""
config.py — Configuración del servicio local ESMFold.

Edita los valores o usa variables de entorno (tienen prioridad).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Raíz del servicio
SERVICE_ROOT = Path(__file__).resolve().parent


@dataclass
class ServiceConfig:
    # ── Red ──────────────────────────────────────────────────────────────
    host: str = field(default_factory=lambda: os.getenv("ESMFOLD_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("ESMFOLD_PORT", "8100")))

    # ── Auto-shutdown ────────────────────────────────────────────────────
    # Si no llega ningún request en `shutdown_idle_minutes`, el servicio se apaga.
    # Poner en 0 para desactivar (no recomendado — desperdicia GPU/RAM).
    shutdown_idle_minutes: float = field(
        default_factory=lambda: float(os.getenv("ESMFOLD_IDLE_MIN", "10"))
    )

    # Cada cuántos segundos el watchdog revisa la inactividad.
    watchdog_interval_seconds: float = 10.0

    # ── Predictor ────────────────────────────────────────────────────────
    # Modo del predictor:
    #   - "stub"  : poses dummy (tests E2E)
    #   - "fast"  : ESMFold pliega → Vina dockea → OpenMM refina (~1-2 min)
    #   - "pro"   : plegamiento completo + refinamiento exhaustivo (~5-15 min)
    predictor_mode: str = field(
        default_factory=lambda: os.getenv("ESMFOLD_MODE", "fast")
    )

    # Directorio donde está el checkpoint de ESMFold (modos "fast" y "pro").
    model_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("ESMFOLD_MODEL_DIR", str(SERVICE_ROOT / "models"))
        )
    )

    # Dispositivo PyTorch (auto/cuda/cpu). Solo aplica en modo "real".
    torch_device: str = field(
        default_factory=lambda: os.getenv("ESMFOLD_DEVICE", "auto")
    )

    # ── Límites ─────────────────────────────────────────────────────────
    # Tamaño máximo del PDB del receptor (MB) — para no aceptar payloads absurdos.
    max_protein_pdb_mb: float = 10.0
    # Timeout duro por predicción (s). Si ESMFold tarda más, se cancela.
    #
    # Eran 300 y no bastaban. Medido en CPU con el runtime embebido, receptor
    # 1HSG y la caja del catálogo: un hexapéptido tarda ~120 s de punta a punta
    # y los de 8-9 residuos agotaban los 300. El plegado es la parte rápida
    # —5-10 s—; lo que tarda es Vina con un ligando de 70-80 átomos pesados.
    #
    # 1200 s es lo que el sidecar «pro» ya usa para la misma clase de trabajo, y
    # el cliente del backend espera 1320 para que quien decide abortar sea el
    # servidor, que es el que sabe por qué.
    predict_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("ESMFOLD_PREDICT_TIMEOUT", "1200"))
    )
    # Número máximo de poses que devolverá el servicio.
    max_poses: int = field(default_factory=lambda: int(os.getenv("ESMFOLD_MAX_POSES", "10")))

    # ── Logging ─────────────────────────────────────────────────────────
    log_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("ESMFOLD_LOG_DIR", str(SERVICE_ROOT / "logs"))
        )
    )
    log_level: str = field(default_factory=lambda: os.getenv("ESMFOLD_LOG_LEVEL", "INFO"))


def get_config() -> ServiceConfig:
    cfg = ServiceConfig()
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    cfg.model_dir.mkdir(parents=True, exist_ok=True)
    return cfg