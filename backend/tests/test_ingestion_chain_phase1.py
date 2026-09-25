"""DOCK-010: reingesta conserva la cadena detectada y su caja efectiva."""

from types import SimpleNamespace

import pytest

from services.targets import ingestion_manager as manager


@pytest.mark.asyncio
async def test_reingesta_actualiza_cadena_y_los_tres_lados(monkeypatch):
    old = SimpleNamespace(
        pdb_id="5ML3", is_prepared=True, chain="A",
        grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
    )

    class Repository:
        def __init__(self, db):
            pass

        async def get_target_by_pdb_id(self, pdb_id):
            assert pdb_id == "5ML3"
            return old

    class Session:
        committed = False

        async def commit(self):
            self.committed = True

    async def yes(*args, **kwargs):
        return True

    async def pdb(*args, **kwargs):
        return "PDB fuente"

    async def prepare(**kwargs):
        assert kwargs["chain_id"] == "B"
        assert kwargs["size"] == (26.0, 28.0, 30.0)
        return "targets/5ML3/prepared-hash.pdbqt"

    monkeypatch.setattr(manager, "Repository", Repository)
    monkeypatch.setattr(manager, "exists", yes)
    monkeypatch.setattr(manager, "read_text", pdb)
    monkeypatch.setattr(manager, "discover_pocket_from_pdb", lambda *args: {
        "success": True, "detected_chain": "B", "grid_center": (1.0, 2.0, 3.0),
        "grid_size": (26.0, 28.0, 30.0), "suggested_hotspots": [],
    })
    monkeypatch.setattr(manager, "anotar_sitio", lambda *args: {
        "site_chains": ["B"], "site_chain_atoms": {"B": 100},
        "site_evidence": "cocrystal_ligand", "site_ligand": "LIG",
    })
    monkeypatch.setattr(manager, "prepare_target", prepare)
    db = Session()
    result = await manager.ingest_new_target(
        "5ML3", db, chain_id="A", cofactors_whitelist=[], force_reingest=True,
    )
    assert db.committed and result["target"] is old
    assert old.chain == "B"
    assert (old.grid_center_x, old.grid_center_y, old.grid_center_z) == (1.0, 2.0, 3.0)
    assert (old.grid_size_x, old.grid_size_y, old.grid_size_z) == (26.0, 28.0, 30.0)
