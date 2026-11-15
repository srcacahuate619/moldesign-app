"""Qué comparaciones entran en la tabla SAR automática (auditoría científica 1.0.4, S1-3.3).

La consulta anterior exigía `total_score`, ordenaba por estado del stacking e índice heredado y cortaba a 50 ANTES de
medir ninguna similitud. Un análogo antiguo, con índice bajo o sin índice, podía quedar fuera aunque fuera el más
parecido a la referencia, y la vista, que sí ordena por similitud, sólo recibía lo que esa consulta había dejado pasar.

Decisión del propietario: la tabla relaciona la similitud estructural con evidencia de docking, así que

* son candidatas las últimas evaluaciones de cada molécula del mismo dueño y receptor que la referencia, SIN error
  registrado y con `affinity_kcal` finita; el índice (`total_score`) no interviene en la admisión;
* se mide el Tanimoto de TODAS las candidatas frente a la referencia, se ordena antes de redondear, se desempata y
  después se corta a 50;
* la referencia no gasta plaza.

Este módulo es puro: recibe filas ligeras, no toca la base de datos ni el bucle de eventos, y la huella se le inyecta
para que su radio y sus bits sigan teniendo un solo dueño (`api/routers/sar.py::_huella_morgan`).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

#: Plazas de comparación de la selección automática. La referencia va aparte.
LIMITE_COMPARACIONES = 50

MOTIVO_BASE_SIN_HUELLA = (
    "La molécula base no tiene una estructura legible: sin su huella no se puede medir la similitud, "
    "así que no se eligen comparaciones automáticas."
)


@dataclass(frozen=True)
class Candidata:
    """Lo mínimo de una proyección para decidir si entra: nada de poses, resultados ni ORM."""

    molecule_id: Any
    smiles: str | None
    evaluated_at: datetime | None
    affinity_kcal: float | None


@dataclass(frozen=True)
class SeleccionSar:
    #: (candidata, Tanimoto SIN redondear), en el orden de selección.
    elegidas: tuple[tuple[Candidata, float], ...]
    #: Candidatas con afinidad finita, antes de medir similitud.
    admitidas: int
    #: Admitidas que no entran porque su SMILES no se pudo leer. Un fallo no es similitud cero.
    sin_huella: int
    #: Por qué no hay comparaciones, cuando no las hay por una causa que no es «no había candidatas».
    motivo: str | None


def _afinidad_finita(valor: Any) -> bool:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return False
    return math.isfinite(numero)


def _a_utc(fecha: datetime | None) -> datetime | None:
    if fecha is None:
        return None
    return fecha.replace(tzinfo=UTC) if fecha.tzinfo is None else fecha.astimezone(UTC)


def clave_de_orden(tanimoto: float, candidata: Candidata) -> tuple:
    """Más parecida primero; después la evaluación más reciente (la ausente, al final); por último el ID.

    El Tanimoto entra tal cual lo da RDKit: ordenar por el valor redondeado a 3 decimales convertiría en empate lo
    que no lo es. El ID de molécula cierra el orden para que la misma consulta devuelva siempre lo mismo.
    """
    fecha = _a_utc(candidata.evaluated_at)
    return (
        -tanimoto,
        fecha is None,
        0.0 if fecha is None else -fecha.timestamp(),
        str(candidata.molecule_id),
    )


def seleccionar(
    candidatas: Iterable[Candidata],
    base_smiles: str | None,
    huella_de: Callable[[Any], Any],
    *,
    limite: int = LIMITE_COMPARACIONES,
) -> SeleccionSar:
    """Elige hasta `limite` comparaciones por similitud estructural con la referencia."""
    from rdkit import Chem, DataStructs

    con_afinidad = [c for c in candidatas if _afinidad_finita(c.affinity_kcal)]

    base_fp = None
    molecula_base = Chem.MolFromSmiles(base_smiles) if base_smiles else None
    if molecula_base is not None:
        base_fp = huella_de(molecula_base)
    if base_fp is None:
        return SeleccionSar(elegidas=(), admitidas=len(con_afinidad), sin_huella=0, motivo=MOTIVO_BASE_SIN_HUELLA)

    puntuadas: list[tuple[float, Candidata]] = []
    sin_huella = 0
    for candidata in con_afinidad:
        molecula = Chem.MolFromSmiles(candidata.smiles) if candidata.smiles else None
        if molecula is None:
            sin_huella += 1
            continue
        puntuadas.append((float(DataStructs.TanimotoSimilarity(base_fp, huella_de(molecula))), candidata))

    puntuadas.sort(key=lambda par: clave_de_orden(par[0], par[1]))
    return SeleccionSar(
        elegidas=tuple((c, t) for t, c in puntuadas[:limite]),
        admitidas=len(con_afinidad),
        sin_huella=sin_huella,
        motivo=None,
    )
