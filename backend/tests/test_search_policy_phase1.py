"""DOCK-014: política de esfuerzo observable y coherente."""

from services.docking.search_policy import (
    BOX_VOLUME_WARNING_A3,
    box_volume,
    effective_exhaustiveness,
)


def test_solo_el_default_vina_sube_en_caja_grande():
    small = (30.0, 30.0, 30.0)
    large = (31.0, 31.0, 31.0)
    assert box_volume(small) == BOX_VOLUME_WARNING_A3
    assert effective_exhaustiveness(requested=None, default=8, size=small, engine="vina") == 8
    assert effective_exhaustiveness(requested=None, default=8, size=large, engine="vina") == 32
    assert effective_exhaustiveness(requested=8, default=8, size=large, engine="vina") == 8
    assert effective_exhaustiveness(requested=None, default=4, size=large, engine="qvina2") == 4


def test_preflight_declara_exhaustividad_efectiva_en_caja_grande():
    from services.docking.preflight import _effective_configuration

    effective, controls = _effective_configuration(
        grid_center=(1.0, 2.0, 3.0), grid_size=(31.0, 31.0, 31.0),
        catalog_grid_center=None, catalog_grid_size=None,
        custom_hotspots=None, catalog_hotspots=None,
        cofactors_whitelist=None, filtered_text=None, prepared_chains=["A"],
        docking_engine="vina", exhaustiveness=None, num_poses=None,
    )
    assert effective["exhaustiveness"] == 32
    assert any(c.code == "GRID_VOLUMEN_AMPLIO" and c.state == "advertencia" for c in controls)


def test_caja_dinamica_sin_senal_de_sitio_bloquea_preflight(monkeypatch):
    from services.docking import preflight

    monkeypatch.setattr(preflight, "_derive_dynamic_box", lambda _: {
        "center": (10.0, 11.0, 12.0), "size": 20.0,
        "source": "pdb_fallback:PROTEIN_ATOM_FALLBACK",
    })
    _, controls = preflight._effective_configuration(
        grid_center=(0, 0, 0), grid_size=(20, 20, 20),
        catalog_grid_center=None, catalog_grid_size=None,
        custom_hotspots=None, catalog_hotspots=None,
        cofactors_whitelist=None, filtered_text="ATOM", prepared_chains=["A"],
        docking_engine="vina", exhaustiveness=None, num_poses=None,
    )
    assert any(c.code == "GRID_EFECTIVO" and c.state == "bloquea" for c in controls)


def test_caja_dinamica_sin_senal_de_sitio_bloquea_ejecucion(monkeypatch):
    import gzip
    from pathlib import Path
    import pytest
    from services.docking import preparer
    from core.exceptions import ProteinPreparationError

    source = Path(__file__).resolve().parents[2] / "data/targets/1CBS.pdb.gz"
    monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda _: source)
    monkeypatch.setattr(preparer, "derive_dynamic_box", lambda _: {
        "center": (10.0, 11.0, 12.0), "size": 20.0,
        "source": "pdb_fallback:PROTEIN_ATOM_FALLBACK",
    })
    # El preparador lee texto plano; se usa una copia de la estructura en tmp.
    # El archivo gzip original permanece intacto.
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        plain = Path(directory) / "1CBS.pdb"
        plain.write_bytes(gzip.decompress(source.read_bytes()))
        monkeypatch.setattr(preparer, "receptor_source_path_no_network", lambda _: plain)
        with pytest.raises(ProteinPreparationError) as exc:
            preparer.resolve_effective_docking_box(
                pdb_id="1CBS", chain_id="A", center=(0, 0, 0), size=(20, 20, 20),
            )
    assert exc.value.step == "dynamic_box_without_site_ligand"
