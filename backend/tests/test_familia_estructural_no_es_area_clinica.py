"""Un área terapéutica no elige los pesos del stacking.

Auditoría de backend del 2026-09-04, §2.6. `scoring/engine.py` traducía el área
clínica a una clase estructural antes de elegir pesos:

    "cardiovascular" -> "metaloenzyme"   vina 0.0 · xgb 0.1 · gnn 0.9
    "oncologia"      -> "kinase"
    "antivirals"     -> "protease"

`vina: 0.0` significa descartar el score de acoplamiento entero. Aplicado a un
receptor adrenérgico —un GPCR, y el catálogo tiene 30— por el solo hecho de que
el proyecto se clasificara como cardiovascular.

El mapa no llegaba a dispararse: las 380 entradas curadas traen familias
estructurales de verdad en `structural_family`, y el área clínica vive en
`therapeutic_family`, otra columna. Estas pruebas fijan las dos cosas que hacían
falta para poder quitarlo sin miedo: que el catálogo sigue siendo estructural, y
que si algún día llega un área clínica el resultado es un aviso y los pesos por
defecto, no una familia inventada.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scoring.engine import AREAS_CLINICAS_CONOCIDAS, STACKING_WEIGHTS, _get_stacking_weights

ROOT = Path(__file__).resolve().parents[2]
CATALOGO = ROOT / "curated_targets.json"


def test_un_area_clinica_no_inventa_una_familia_estructural():
    """A therapeutic area falls back to the explicit unknown-target contract."""
    clinical = _get_stacking_weights("cardiovascular")
    assert clinical == _get_stacking_weights(None)
    assert clinical.get("vina", 0.0) > 0.0


@pytest.mark.parametrize("area", sorted(AREAS_CLINICAS_CONOCIDAS))
def test_toda_area_clinica_cae_a_los_pesos_por_defecto(area: str):
    """Sin familia estructural no se adivina: se usan los pesos genéricos."""
    assert _get_stacking_weights(area) == _get_stacking_weights(None), (
        f"«{area}» produce pesos distintos a los de una familia desconocida. "
        "Si se conoce su clase estructural, pásala; si no, el default es la "
        "lectura honesta."
    )


def test_gpcr_does_not_claim_calibration_from_a_different_checkpoint():
    """Alpha is conservative until the exact CL-GNN SHA is validated."""
    gpcr = _get_stacking_weights("gpcr")
    generic = _get_stacking_weights(None)
    assert gpcr == generic
    assert gpcr["gnn"] == 0.0
    assert gpcr["clgnn"] == 0.0


def test_el_catalogo_curado_no_guarda_areas_clinicas_en_structural_family():
    """La columna que alimenta el scoring tiene que seguir siendo estructural.

    Es la premisa de todo lo anterior. Si un día alguien escribe «oncologia» en
    `structural_family` de una entrada curada, el pipeline empieza a pedir pesos
    con un área clínica y esta prueba lo dice antes que el aviso en tiempo de
    ejecución.
    """
    entradas = json.loads(CATALOGO.read_text(encoding="utf-8"))
    if isinstance(entradas, dict):
        entradas = entradas.get("targets", [])

    intrusas = sorted({
        (t.get("pdb_id"), familia)
        for t in entradas
        if (familia := (t.get("structural_family") or "").lower().strip())
        in AREAS_CLINICAS_CONOCIDAS
    })
    assert not intrusas, (
        f"Entradas del catálogo con un área clínica en structural_family: {intrusas}. "
        "El área terapéutica va en therapeutic_family."
    )
