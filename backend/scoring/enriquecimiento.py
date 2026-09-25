"""Métricas de cribado con empates fraccionales y política de faltantes explícita."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence


def ef_fraccional(
    scores: Sequence[float], labels: Sequence[bool], fraction: float,
) -> tuple[float | None, float, int]:
    """EF@fraction; el bloque empatado que cruza el corte contribuye a prorrata.

    Un score -inf representa una evaluación fallida y cuenta en el denominador.
    Devuelve (EF, activos esperados en el top, tamaño del top).
    """
    if len(scores) != len(labels):
        raise ValueError("scores y labels tienen distinta longitud")
    if not 0 < fraction <= 1:
        raise ValueError("fraction debe estar en (0, 1]")
    if len(scores) == 0:
        return None, 0.0, 0
    if any(math.isnan(float(score)) for score in scores):
        raise ValueError("NaN no es un score; use -inf y declare la exclusión")
    n = len(scores)
    n_act = sum(bool(label) for label in labels)
    k = min(n, max(1, math.ceil(fraction * n)))
    if not n_act:
        return None, 0.0, k
    groups: dict[float, list[bool]] = defaultdict(list)
    for score, label in zip(scores, labels):
        groups[float(score)].append(bool(label))
    selected = 0
    found = 0.0
    for score in sorted(groups, reverse=True):
        group = groups[score]
        take = min(len(group), k - selected)
        found += sum(group) * take / len(group)
        selected += take
        if selected == k:
            break
    return found / (n_act * k / n), found, k


def roc_auc_midrank(scores: Sequence[float], labels: Sequence[bool]) -> float | None:
    """Probabilidad de que un activo supere a un inactivo; empate = 0.5."""
    if len(scores) != len(labels):
        raise ValueError("scores y labels tienen distinta longitud")
    n_pos = sum(bool(label) for label in labels)
    n_neg = len(labels) - n_pos
    if not n_pos or not n_neg:
        return None
    groups: dict[float, list[bool]] = defaultdict(list)
    for score, label in zip(scores, labels):
        if math.isnan(float(score)):
            raise ValueError("NaN no es un score")
        groups[float(score)].append(bool(label))
    neg_below = 0
    concordant = 0.0
    for score in sorted(groups):
        group = groups[score]
        pos = sum(group)
        neg = len(group) - pos
        concordant += pos * neg_below + 0.5 * pos * neg
        neg_below += neg
    return concordant / (n_pos * n_neg)
