"""Qué resultado puede alimentar una decisión, y cuál no. Cerrado por defecto.

═══════════════════════════════════════════════════════════════════════════
LA REGLA
═══════════════════════════════════════════════════════════════════════════

    Sólo un resultado con estado explícito VALIDATED puede alimentar una
    decisión derivada. Cualquier otro estado queda excluido.

Es una lista BLANCA de un solo elemento, y esa es toda la idea. La alternativa
—enumerar los estados que hay que excluir— tiene un modo de fallo garantizado:
el día que aparezca un estado nuevo, el filtro lo dejará pasar por omisión.

Este producto ya conoce esa forma de error. `REVIEW_INVALID_BENCHMARK_SITE` y
`REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING` nacieron el 2026-09-04, después
de que M5-Zn se conectara al pipeline; una lista negra escrita el día anterior
no los habría contenido, y dos perfiles con el benchmark cuestionado habrían
entrado en el ranking sin que nada fallara.

═══════════════════════════════════════════════════════════════════════════
QUÉ SIGNIFICA «DECISIÓN DERIVADA»
═══════════════════════════════════════════════════════════════════════════

Todo lo que ordena, recomienda, concluye o certifica:

    total_score · ordenación y ranking · recomendación final ·
    explicabilidad y SHAP · veredicto clínico · resumen de evidencia como
    conclusión · certificado y dossier como conclusión

Lo que NO es una decisión derivada: el **bloque de auditoría**. Ahí el número
sí aparece —ocultarlo impediría auditarlo justo cuando hace falta— pero nunca
solo: viaja con su estado, su motivo y
`eligible_for_scientific_interpretation: false`.
"""

from __future__ import annotations

from typing import Any

#: El ÚNICO estado que habilita una decisión derivada. No se amplía sin
#: revisar el ADR correspondiente y sus pruebas.
ESTADO_HABILITANTE = "VALIDATED"


def es_interpretable(estado: Any) -> bool:
    """¿Este resultado puede alimentar una decisión? Sólo si está VALIDATED.

    `None`, cadena vacía, un estado desconocido o cualquier `REVIEW_*`
    devuelven `False`. La ausencia de estado NO habilita: un resultado que no
    dice en qué situación está no está en una situación buena.
    """
    return isinstance(estado, str) and estado.strip().upper() == ESTADO_HABILITANTE


def score_para_decision(score: Any, estado: Any) -> float | None:
    """El score si puede decidir, `None` si no.

    Se usa en el borde de cada consumidor. Devuelve `None` en vez de 0.0
    porque un cero es una predicción y la exclusión no lo es — el §5 del ADR 75
    aplicado a la frontera del ranking.
    """
    if score is None or not es_interpretable(estado):
        return None
    return float(score)


def bloque_de_auditoria(score: Any, estado: Any, motivo: str | None = None) -> dict:
    """La forma en que un score no interpretable SÍ puede viajar.

    Nunca el número solo. Quien lo lea recibe a la vez qué es, por qué está en
    ese estado, y que no habilita ninguna conclusión.
    """
    return {
        "score": None if score is None else float(score),
        "scientific_status": estado,
        "reason": motivo,
        "eligible_for_scientific_interpretation": es_interpretable(estado),
    }
