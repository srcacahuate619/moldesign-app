"""Contrato único entre preparación, Vina y el caché de docking."""
from __future__ import annotations

from services.docking import preparer
from services.docking.vina_service import _docking_cache_fingerprint
from utils.cache import CacheKey


PDB_CHAIN_A = (
    "ATOM      1  N   ALA A   1      11.104  13.207  10.000  1.00 20.00           N\n"
    "ATOM      2  CA  ALA A   1      12.560  13.207  10.000  1.00 20.00           C\n"
    "END\n"
)


def test_prepared_receptor_must_declare_exactly_the_requested_chain():
    chain_a = "ATOM      1  N   ALA A   1       0.0   0.0   0.0  1.00  0.00     0.000 N\n"
    chain_b = "ATOM      2  N   ALA B   1       0.0   0.0   0.0  1.00  0.00     0.000 N\n"

    assert preparer.prepared_receptor_matches_chain(chain_a, "A") is True
    assert preparer.prepared_receptor_matches_chain(chain_a, "B") is False
    assert preparer.prepared_receptor_matches_chain(chain_a + chain_b, "A") is False
    assert preparer.prepared_receptor_matches_chain("ATOM\n", "A") is False


def test_dynamic_box_resolver_returns_the_box_shared_with_preflight(monkeypatch, tmp_path):
    source = tmp_path / "1ABC.pdb"
    source.write_text(PDB_CHAIN_A, encoding="utf-8")
    monkeypatch.setattr(preparer, "get_target_pdb_path", lambda pdb_id: source)
    monkeypatch.setattr(
        preparer,
        "derive_dynamic_box",
        lambda filtered: {"center": (4.0, 5.0, 6.0), "size": 24.0, "source": "test"},
    )

    center, size = preparer.resolve_effective_docking_box(
        pdb_id="1ABC",
        chain_id="A",
        center=(0.0, 0.0, 0.0),
        size=(20.0, 20.0, 20.0),
    )

    assert center == (4.0, 5.0, 6.0)
    assert size == (24.0, 24.0, 24.0)


def _fingerprint(**overrides) -> str:
    values = {
        "receptor_sha256": "a" * 64,
        "target_chain": "A",
        "center": (1.0, 2.0, 3.0),
        "size": (20.0, 20.0, 20.0),
        "hotspots": [{"name": "A:ASP1"}],
        "docking_engine": "vina",
        "exhaustiveness": 8,
        "num_poses": 9,
        "seed": 42,
    }
    values.update(overrides)
    return _docking_cache_fingerprint(**values)


def test_docking_cache_fingerprint_separates_distinct_hypotheses():
    base = _fingerprint()
    for change in (
        {"receptor_sha256": "b" * 64},
        {"target_chain": "B"},
        {"center": (9.0, 9.0, 9.0)},
        {"size": (30.0, 30.0, 30.0)},
        {"hotspots": [{"name": "A:TYR2"}]},
        {"docking_engine": "qvina2"},
        {"exhaustiveness": 16},
        {"num_poses": 5},
        {"seed": 7},
    ):
        assert _fingerprint(**change) != base, change


def test_cache_key_never_reuses_the_legacy_pair_only_entry():
    legacy = CacheKey.docking("ligand", "7E2Y")
    first = CacheKey.docking("ligand", "7E2Y", "config-a")
    second = CacheKey.docking("ligand", "7E2Y", "config-b")

    assert legacy.endswith(":legacy")
    assert len({legacy, first, second}) == 3
