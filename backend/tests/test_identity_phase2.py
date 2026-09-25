"""Identidad de entrada y migración aditiva de fase 2."""

import sqlite3

import pytest
from rdkit import Chem
from sqlalchemy import select

from chem.identity import identity_hash_v2
from chem.validator import validate_smiles
from core.database import _migrate_sqlite_db
from core.models import MoleculeORM, TargetORM, UserORM
from db.repository import Repository
from tests import test_sqlite_roundtrip as fixtures

engine = fixtures.engine
session_factory = fixtures.session_factory


def test_identidad_v2_incluye_rdkit_y_smiles_de_entrada():
    first = validate_smiles("CC(=O)Oc1ccccc1C(=O)O")
    second = validate_smiles("CC(=O)Oc1ccccc1C(=O)[O-]")
    assert first.motor_canonico == f"RDKit {Chem.rdBase.rdkitVersion}"
    assert first.identity_hash_v2 == identity_hash_v2(first.canonical_smiles)
    assert first.identity_hash_v2 != second.identity_hash_v2


def test_migracion_deja_indeterminadas_las_identidades_historicas(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE molecules (id TEXT, smiles TEXT, smiles_hash TEXT)")
        conn.execute("INSERT INTO molecules VALUES ('m1','CCO','legacy-hash')")
        conn.execute("CREATE TABLE evaluation_results (id TEXT, muegge_pass INTEGER)")
        conn.execute("INSERT INTO evaluation_results VALUES ('r1',1)")
    _migrate_sqlite_db(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT smiles, smiles_hash, identity_hash_v2 FROM molecules").fetchone() == ("CCO", "legacy-hash", None)
        assert conn.execute("SELECT muegge_pass, muegge_violations FROM evaluation_results").fetchone() == (1, None)


@pytest.mark.asyncio
async def test_repetir_entrada_conserva_una_sola_fila_y_su_identidad(session_factory):
    input_smiles = "CC(=O)Oc1ccccc1C(=O)O"
    async with session_factory() as db:
        user = UserORM(email="phase2@example.com", username="phase2")
        target = TargetORM(pdb_id="7E2Y", name="target", chain="A", grid_center_x=0.0, grid_center_y=0.0, grid_center_z=0.0)
        db.add_all([user, target])
        await db.flush()
        repo = Repository(db)
        first = await repo.create_or_get_molecule(input_smiles, "7E2Y", user_id=user.id)
        second = await repo.create_or_get_molecule(input_smiles, "7E2Y", user_id=user.id)
        await db.commit()
        assert first.id == second.id
        assert first.smiles == input_smiles
        assert first.identity_hash_v2 == validate_smiles(input_smiles).identity_hash_v2
        rows = (await db.execute(select(MoleculeORM))).scalars().all()
        assert len(rows) == 1

