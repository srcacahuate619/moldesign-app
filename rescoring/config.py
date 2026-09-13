"""
rescoring/config.py

Configuración del microservicio de rescoring.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class RescoringSettings(BaseSettings):
    """Configuración del microservicio de rescoring."""

    # ── Paths a artefactos del modelo ──────────────────────────────
    # En DESKTOP, se usa el directorio artifacts/ relativo al proyecto.
    # En DOCKER, se usa /app/artifacts/ (paths del contenedor).
    _default_artifacts_dir: str = "artifacts"

    model_a_path: str = "artifacts/model_a_universal.json"
    model_null_path: str = "artifacts/model_null.json"
    delta_distribution_path: str = "artifacts/delta_distribution.json"
    applicability_domain_path: str = "artifacts/applicability_domain.json"
    training_report_path: str = "artifacts/training_report.json"

    # Pose selector (Ruta C v0.6, Fase 4) — opcional: si los artefactos no
    # existen o pose_selector_enabled=False, el pipeline de rescoring
    # funciona exactamente igual que antes (degradacion elegante).
    pose_selector_model_path: str = "artifacts/pose_selector_v06.xgb"
    pose_selector_meta_path: str = "artifacts/pose_selector_v06_meta.json"
    pose_selector_enabled: bool = True
    pose_selector_abstention_threshold: float = 0.097663

    # Umbrales de semáforo de Delta (percentiles, se cargan del artefacto)
    delta_green_threshold: float = 0.5  # por encima → verde (específico)
    delta_red_threshold: float = -0.3  # por debajo → rojo (choque)

    # Pose filter
    pose_filter_max_distance: float = 12.0  # Å — distancia máxima centroide-ligando al grid center
    pose_filter_min_atoms_in_box: float = 0.7  # 70% de átomos pesados dentro del grid box
    pose_filter_max_clashes: int = 5  # máximo de clashes estéricos con la proteína

    # Pose variance — umbrales de estabilidad
    pose_variance_low: float = 0.3  # < 0.3 kcal/mol → ALTA estabilidad
    pose_variance_high: float = 1.0  # > 1.0 kcal/mol → BAJA estabilidad

    # Shared API Key. Sin valor por defecto: una clave compartida escrita en el
    # repositorio no es una clave. El backend ya envia "" por defecto
    # (backend/core/config.py::rescoring_api_key) y hoy nada en este sidecar
    # valida la cabecera X-API-Key; el campo existe para inyectarla por entorno
    # (RESCORING_API_KEY) cuando se despliegue fuera de localhost.
    api_key: str = ""

    model_config = SettingsConfigDict(
        env_prefix="RESCORING_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_rescoring_settings() -> RescoringSettings:
    return RescoringSettings()
