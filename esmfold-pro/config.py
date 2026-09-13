"""
config.py — Configuración del sidecar ESMFold-Pro (RFdiffusion).

Modo experimental: RFdiffusion RFpeptides (Baker Lab)
requiere GPU NVIDIA >= 8GB VRAM.

Edita los valores o usa variables de entorno (tienen prioridad).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parent


@dataclass
class ServiceConfig:
    # ── Red ──────────────────────────────────────────────────────────
    host: str = field(default_factory=lambda: os.getenv("ESMFOLD_PRO_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("ESMFOLD_PRO_PORT", "8300")))

    # ── Auto-shutdown ────────────────────────────────────────────────
    shutdown_idle_minutes: float = field(
        default_factory=lambda: float(os.getenv("ESMFOLD_PRO_IDLE_MIN", "0"))
    )
    watchdog_interval_seconds: float = 10.0

    # ── Modelo ───────────────────────────────────────────────────────
    # Directorio con checkpoints RFdiffusion (~4 GB total):
    #   Base_ckpt.pt, Complex_base_ckpt.pt
    model_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("ESMFOLD_PRO_MODEL_DIR", str(SERVICE_ROOT / "models"))
        )
    )

    # Path al repo RFdiffusion clonado
    rfdiffusion_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("RFDIFFUSION_PATH", str(SERVICE_ROOT.parent / "rfdiffusion"))
        )
    )

    # Dispositivo: auto/cuda/cpu (RFdiffusion requiere CUDA)
    device: str = field(
        default_factory=lambda: os.getenv("ESMFOLD_PRO_DEVICE", "auto")
    )

    # ── Límites ──────────────────────────────────────────────────────
    max_protein_pdb_mb: float = 10.0
    predict_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("ESMFOLD_PRO_TIMEOUT", "1200"))
    )
    max_poses: int = field(
        default_factory=lambda: int(os.getenv("ESMFOLD_PRO_MAX_POSES", "5"))
    )

    # ── RFdiffusion inference params ─────────────────────────────────
    diffuser_T: int = 50  # diffusion steps (default)
    noise_scale_ca: float = 0.5  # reduce noise for better quality
    noise_scale_frame: float = 0.5

    # ── Logging ──────────────────────────────────────────────────────
    log_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("ESMFOLD_PRO_LOG_DIR", str(SERVICE_ROOT / "logs"))
        )
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("ESMFOLD_PRO_LOG_LEVEL", "INFO")
    )


def get_config() -> ServiceConfig:
    cfg = ServiceConfig()
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    cfg.model_dir.mkdir(parents=True, exist_ok=True)
    return cfg
