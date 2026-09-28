"""Política explícita de esfuerzo de búsqueda para Vina.

El umbral de volumen es una decisión conservadora de ingeniería, no una
relación publicada y validada entre volumen y exhaustividad.
"""

from __future__ import annotations

BOX_VOLUME_WARNING_A3 = 27_000.0
LARGE_BOX_DEFAULT_EXHAUSTIVENESS = 32

#: Procesos Vina simultáneos por directorio de datos (fase 7, PROV-018): un
#: semáforo y un `FileLock` en `vina_service` los serializan, y cada uno usa
#: todos los núcleos. Vive aquí, y no en `vina_service`, para que la estimación
#: de duración (`/evaluation/estimate`) lea el mismo número sin cargar el
#: servicio de docking.
VINA_PROCESS_LIMIT = 1


def box_volume(size: tuple[float, float, float]) -> float:
    return float(size[0]) * float(size[1]) * float(size[2])


def effective_exhaustiveness(
    *,
    requested: int | None,
    default: int,
    size: tuple[float, float, float],
    engine: str,
) -> int:
    """Respeta el valor explícito; eleva sólo el default de Vina en caja grande."""
    if requested is not None:
        return int(requested)
    if engine.lower() == "vina" and box_volume(size) > BOX_VOLUME_WARNING_A3:
        return max(int(default), LARGE_BOX_DEFAULT_EXHAUSTIVENESS)
    return int(default)
