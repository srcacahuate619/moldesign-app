"""Regla única para las cajas que reciben Vina y el catálogo."""
from __future__ import annotations

import math


def validar_caja(
    center: tuple[float, float, float] | None,
    size: tuple[float, float, float] | None,
) -> None:
    if center is not None and (len(center) != 3 or not all(math.isfinite(v) and abs(v) <= 10000 for v in center)):
        raise ValueError("El centro de la caja debe tener tres números finitos entre -10000 y 10000 Å.")
    if size is not None and (len(size) != 3 or not all(
        math.isfinite(v) and 5.0 <= v <= 80.0 for v in size
    )):
        raise ValueError("Cada dimensión de la caja debe estar entre 5 y 80 Å y ser finita.")
