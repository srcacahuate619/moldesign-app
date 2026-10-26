"""
La selección vacía de hotspots es una decisión, no una ausencia (SOL-08).

La auditoría lo midió en vivo: en Opciones, «Desmarcar todos» + Aplicar +
comprobar preparación enviaba `custom_hotspots: []` y la API respondía con
los 15 hotspots del catálogo. El preflight usaba la lista del usuario sólo
si era *truthy*, el runner hacía lo mismo, y el documento canónico firmaba
`[]` igual que la ausencia — dos decisiones estructurales distintas
compartiendo una huella.

El criterio de cierre de la auditoría: «preservar por separado ausencia de
override y selección vacía, en UI, fingerprint, ejecución y dossier». La UI
ya los distingue (`null` vs `[]`); este archivo fija el resto de la cadena:

    ausencia (None)  → el catálogo manda
    selección vacía  → CERO hotspots efectivos, origen declarado, huella
                       propia y ejecución sin lista de referencias
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import rdkit_available

from services.docking.preflight import build_preflight, canonical_input_document

RAIZ = Path(__file__).resolve().parents[1]

ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
CATALOGO = ["A:TYR123", "A:ASP456"]


def _build(**overrides):
    kwargs = dict(
        smiles=ASPIRIN,
        target_pdb_id="1ABC",
        chain="A",
        target_origin="curado",
        target_reference="ref-1",
        grid_center=(1.0, 2.0, 3.0),
        grid_size=(20.0, 20.0, 20.0),
        custom_hotspots=None,
        catalog_grid_center=None,
        catalog_grid_size=None,
        catalog_hotspots=CATALOGO,
        cofactors_whitelist=None,
        docking_engine="vina",
    )
    kwargs.update(overrides)
    return build_preflight(**kwargs)


def _control(report: dict, code: str) -> dict:
    for control in report["controls"]:
        if control["code"] == code:
            return control
    raise AssertionError(f"El informe no incluye el control {code}")


# ── 1. La selección vacía no se convierte en el catálogo ─────────────


@rdkit_available
def test_la_seleccion_vacia_se_conserva_en_el_preflight():
    """`[]` es «no quiero residuos de referencia», no «usa los del catálogo».

    La reproducción de la auditoría: desmarcar todos devolvía los 15 del
    catálogo como efectivos y su origen. Hoy tiene que declarar CERO y que
    la decisión fue del investigador.
    """
    report = _build(custom_hotspots=[])

    assert report["effective_config"]["hotspots"] == []
    assert report["effective_config"]["hotspots_origin"] == "seleccion_vacia"

    control = _control(report, "HOTSPOTS_EFECTIVOS")
    # Una decisión consciente no es «no evaluado»: se tomó, se registra.
    assert control["state"] == "pasa"
    assert "decisión" in control["observation"]


@rdkit_available
def test_la_ausencia_de_override_sigue_siendo_el_catalogo():
    """`None` —nunca se abrió Opciones— SÍ hereda los hotspots del catálogo.

    La distinción funciona en los dos sentidos o no funciona.
    """
    report = _build(custom_hotspots=None)

    assert report["effective_config"]["hotspots"] == sorted(CATALOGO)
    assert report["effective_config"]["hotspots_origin"] == "catalogo_target"


@rdkit_available
def test_la_seleccion_con_residuos_sigue_igual():
    """El caso normal —una lista con elementos— no cambia en nada."""
    report = _build(custom_hotspots=["A:TYR123"])

    assert report["effective_config"]["hotspots"] == ["A:TYR123"]
    assert report["effective_config"]["hotspots_origin"] == "seleccion_usuario"


# ── 2. La huella distingue las dos decisiones ────────────────────────


@rdkit_available
def test_la_huella_distingue_seleccion_vacia_de_ausencia():
    """`[]` y `None` son corridas distintas: la huella tiene que notarlo.

    Antes el documento canónico convertía `[]` en clave ausente: elegir
    ninguno y no elegir nada firmaban igual. El fingerprint es la prueba de
    que la corrida es la que se inspeccionó; colapsar decisiones ahí es
    exactamente el defecto.
    """
    base = dict(
        smiles_for_hash=ASPIRIN,
        target_pdb_id="1ABC",
        chain="A",
        grid_center=(1.0, 2.0, 3.0),
        grid_size=(20.0, 20.0, 20.0),
        docking_engine="vina",
        exhaustiveness=8,
        num_poses=9,
        seed=42,
        source_sha256=None,
        prepared_sha256=None,
    )
    vacia = json.loads(canonical_input_document(custom_hotspots=[], **base))
    ausente = json.loads(canonical_input_document(custom_hotspots=None, **base))

    assert vacia["custom_hotspots"] == []
    # El estilo del documento conserva la clave con None para lo ausente
    # (igual que grid_center); lo que distingue las decisiones es el VALOR:
    # [] firmado ≠ None sin override.
    assert ausente["custom_hotspots"] is None
    assert (
        canonical_input_document(custom_hotspots=[], **base)
        != canonical_input_document(custom_hotspots=None, **base)
    )


# ── 3. La ejecución también respeta la decisión ──────────────────────


def test_el_runner_respeta_la_seleccion_vacia():
    """El runner debe distinguir `[]` de `None` con `is not None`.

    Con el chequeo truthy, la selección vacía restauraba los hotspots base
    para el análisis de contactos. Source-text, el mismo enfoque que
    `test_los_dos_caminos_sellan_el_protocolo`.
    """
    fuente = (RAIZ / "services" / "pipeline" / "runner.py").read_text(encoding="utf-8")
    assert "if pipeline_params.custom_hotspots is not None:" in fuente
    assert "if pipeline_params.custom_hotspots:" not in fuente
