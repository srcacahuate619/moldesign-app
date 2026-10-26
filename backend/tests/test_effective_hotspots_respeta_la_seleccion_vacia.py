"""
`PipelineParams.effective_hotspots` respeta la selección vacía (QA1-007, SOL-08).

El preflight (`test_seleccion_vacia_de_hotspots.py`) y el runner ya distinguen
`None` («nunca se abrió Opciones»: hereda el catálogo) de `[]` («no quiero residuos
de referencia»). La propiedad `effective_hotspots` seguía preguntando
`if self.custom_hotspots:`, y `[]` es falso: devolvía los del catálogo. Hoy nadie la
llama, pero el preflight la cita como procedencia de «HOTSPOTS_EFECTIVOS» y la
próxima persona que la use heredaría la decisión equivocada.
"""

from __future__ import annotations

import uuid

from core.pipeline_params import PipelineParams

CATALOGO = [
    {"name": "A:ASP32", "importance": 0.94},
    {"name": "A:ASP228", "importance": 0.72},
]


def _params(**overrides) -> PipelineParams:
    kwargs = dict(
        target_pdb_id="4AZY",
        target_name="BACE1",
        target_chain="A",
        target_site_chains=["A"],
        target_structural_family="protease",
        target_is_hot=False,
        target_grid_center_x=5.427,
        target_grid_center_y=1.673,
        target_grid_center_z=-21.014,
        target_grid_size_x=30.0,
        target_grid_size_y=30.0,
        target_grid_size_z=30.0,
        target_hotspots_base=list(CATALOGO),
        target_hotspots_source="auto_pocket_top15",
        target_cofactors_whitelist=[],
        molecule_id=uuid.uuid4(),
        molecule_smiles="CC(=O)Oc1ccccc1C(=O)O",
        molecule_smiles_hash="x",
    )
    kwargs.update(overrides)
    return PipelineParams(**kwargs)


def _nombres(hotspots: list[dict]) -> list[str]:
    return [h["name"] for h in hotspots]


def test_sin_decision_hereda_el_catalogo():
    assert _nombres(_params(custom_hotspots=None).effective_hotspots) == ["A:ASP32", "A:ASP228"]


def test_la_seleccion_vacia_es_ninguno_no_el_catalogo():
    assert _params(custom_hotspots=[]).effective_hotspots == []


def test_una_seleccion_conserva_sus_residuos_y_la_importancia_del_catalogo():
    efectivos = _params(custom_hotspots=["A:ASP228", "A:XYZ1"]).effective_hotspots
    assert efectivos == [
        {"name": "A:ASP228", "importance": 0.72},
        {"name": "A:XYZ1", "importance": 1.0},
    ]
