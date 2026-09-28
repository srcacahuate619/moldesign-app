"""¿El sello describe la corrida que se está mostrando?

`evaluation_results` es la proyección mutable de la última evaluación. Al
reevaluar una molécula se reescriben score, afinidad, receptor y semilla, pero
el sello de la corrida anterior se conserva (fase 4 de la auditoría `ae4db6a`):
`blockchain_tx_id` sigue ahí y `certified_task_id` dice qué corrida cubrió.

Moldex ya hacía esta comparación (MOLDEX-SCI-001). La pestaña Evaluación no
tenía el dato: tras reevaluar decía «Certificado» y deshabilitaba el registro
con la firma de otra corrida. La regla vive aquí para que las dos pantallas no
puedan divergir.
"""

from __future__ import annotations


def sello_describe_la_corrida(
    *,
    tx_id: str | None,
    certified_task_id: str | None,
    certified_total_score: float | None,
    task_id: str | None,
    total_score: float | None,
) -> bool | None:
    """Tres valores, y cada uno significa algo distinto.

    - ``True``: el sello describe la corrida vigente.
    - ``False``: la molécula se reevaluó después de certificarla, así que lo
      sellado y lo mostrado son corridas distintas.
    - ``None``: indeterminado. O no hay sello, o es anterior a v14 y no
      registra qué corrida cubrió. Suponer que coincide sería reintroducir el
      defecto, así que no se supone.
    """
    if not tx_id or certified_task_id is None:
        return None
    # El cero medido es un valor válido, no un faltante: se compara el valor,
    # nunca su veracidad (MOLDEX-SCI-002).
    return certified_task_id == task_id and certified_total_score == total_score
