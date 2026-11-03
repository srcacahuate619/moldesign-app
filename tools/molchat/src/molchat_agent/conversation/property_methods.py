"""Explain a difference between PubChem and MolDesign only when a real calculation reproduces it.

Two sources can publish different TPSA or acceptor counts for the same molecule because they define the
descriptor differently, not because either is wrong. The tempting answer is to say so. This module says so
only when MolDesign's own variant (the same RDKit under the other definition, with its method declared)
lands on PubChem's figure at the precision PubChem prints. When no variant reproduces it, the note says the
difference is not explained and warns against blaming a side.

The text is written here, never by the model, from the numbers and the method strings MolDesign declared.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping

#: MolDesign key -> (PubChem key, label, unit, decimals PubChem prints). A figure agrees with PubChem's when it
#: rounds (half up) to what PubChem prints; counts must be equal.
_PAIRS = {
    "tpsa": ("TPSA", "TPSA", " Å²", 1),
    "hba": ("HBondAcceptorCount", "Aceptores de enlace de hidrógeno", "", 0),
}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _shown(value: float) -> str:
    return format(value, "g")


def _same(published: float, value: float, decimals: int) -> bool:
    """Whether ``value`` rounds (half up, on its decimal form) to the ``published`` figure."""
    step = Decimal(1).scaleb(-decimals)
    return Decimal(repr(value)).quantize(step, rounding=ROUND_HALF_UP) == Decimal(repr(published)).quantize(step, rounding=ROUND_HALF_UP)


def property_difference_notes(reference: Mapping[str, Any] | None, props: Mapping[str, Any],
                              methods: Mapping[str, str], variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One note per descriptor whose PubChem and MolDesign figures differ and for which MolDesign has a variant."""
    if not isinstance(reference, Mapping):
        return []
    notes: list[dict[str, Any]] = []
    for key, (pubchem_key, label, unit, decimals) in _PAIRS.items():
        published, computed = _number(reference.get(pubchem_key)), _number(props.get(key))
        if published is None or computed is None or _same(published, computed, decimals):
            continue
        variant = next((item for item in variants if item.get("applies_to") == key and _number(item.get("value")) is not None), None)
        if variant is None:
            continue
        value = float(variant["value"])
        reproduces = _same(published, value, decimals)
        own_method = methods.get(key) or "su definición del producto"
        head = f"{label}: PubChem da {_shown(published)}{unit} y MolDesign {_shown(computed)}{unit}."
        if reproduces:
            text = (f"{head} No son cifras contradictorias: MolDesign usa {own_method}. Con la definición alternativa "
                    f"({variant['method']}), el mismo RDKit da {_shown(value)}{unit}, que coincide con PubChem. Para esta "
                    "molécula la diferencia es la definición del descriptor, no un error de cálculo.")
        else:
            text = (f"{head} La variante calculada ({variant['method']}) da {_shown(value)}{unit} y tampoco coincide con PubChem, "
                    "así que la diferencia no queda explicada; no la atribuyas a un error de un lado.")
        notes.append({"property": key, "pubchem": published, "moldesign": computed, "variant": variant["name"],
                      "variant_value": value, "reproduces_pubchem": reproduces, "text": text})
    return notes
