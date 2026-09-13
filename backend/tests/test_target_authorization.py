"""Contrato multiusuario de receptores privados."""

from __future__ import annotations

import io
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

from api.dependencies import get_current_user, get_current_user_optional
from api.routers import batch, evaluation, evaluation_cohorts, pro_features, targets
from services.targets.access import get_target_for_user_id, target_is_accessible
from db.repository import Repository
from core.database import get_db
from core.models import Base, TargetORM, UserORM


def _request(path: str = "/evaluation/submit") -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
    )


class _Environment:
    def __init__(self, db_path: Path):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)

    async def start(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        await self.engine.dispose()

    async def user(self, name: str) -> UserORM:
        async with self.factory() as session:
            user = UserORM(
                id=uuid.uuid4(),
                email=f"{name}@moldesign.local",
                username=name,
                hashed_password="x",
                is_active=True,
            )
            session.add(user)
            await session.commit()
            return user

    async def target(
        self,
        pdb_id: str,
        *,
        owner: UserORM | None = None,
        private: bool = False,
        anti: bool = False,
    ) -> TargetORM:
        async with self.factory() as session:
            target = TargetORM(
                id=uuid.uuid4(),
                pdb_id=pdb_id,
                name=f"Target {pdb_id}",
                chain="A",
                description="fixture",
                grid_center_x=1.0,
                grid_center_y=2.0,
                grid_center_z=3.0,
                grid_size_x=20.0,
                grid_size_y=20.0,
                grid_size_z=20.0,
                requires_cns=False,
                structural_family=None if private else "GPCR",
                organism="Homo sapiens",
                resolution=2.0,
                is_prepared=True,
                is_private=private,
                is_community=False,
                is_anti_target=anti,
                creator_id=owner.id if owner else None,
                creator_username=owner.username if owner else None,
            )
            session.add(target)
            await session.commit()
            return target

    def client(self, user: UserORM | None) -> TestClient:
        app = FastAPI()
        app.include_router(targets.router)

        async def database():
            async with self.factory() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_user_optional] = lambda: user
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)


@pytest_asyncio.fixture
async def environment(tmp_path):
    env = _Environment(tmp_path / "targets.db")
    await env.start()
    try:
        yield env
    finally:
        await env.close()


@pytest.mark.asyncio
async def test_catalog_is_derived_from_authenticated_owner_not_client_ids(environment):
    alice = await environment.user("alice")
    bob = await environment.user("bob")
    public = await environment.target("7E2Y")
    alice_private = await environment.target("USR_ALICE", owner=alice, private=True)
    bob_private = await environment.target("USR_BOB", owner=bob, private=True)

    alice_ids = {item["pdb_id"] for item in environment.client(alice).get("/targets/").json()}
    bob_ids = {item["pdb_id"] for item in environment.client(bob).get("/targets/").json()}
    anonymous_ids = {item["pdb_id"] for item in environment.client(None).get("/targets/").json()}

    assert alice_ids == {public.pdb_id, alice_private.pdb_id}
    assert bob_ids == {public.pdb_id, bob_private.pdb_id}
    assert anonymous_ids == {public.pdb_id}

    # El parámetro legado se ignora: conocer el UUID ajeno no concede visibilidad.
    spoofed = environment.client(alice).get(
        f"/targets/?private_ids={bob_private.id}"
    )
    assert spoofed.status_code == 200
    assert bob_private.pdb_id not in {item["pdb_id"] for item in spoofed.json()}


@pytest.mark.asyncio
async def test_private_pdb_and_share_are_owner_only_without_enumeration(
    environment, tmp_path, monkeypatch
):
    alice = await environment.user("alice")
    bob = await environment.user("bob")
    private = await environment.target("USR_ALICE", owner=alice, private=True)
    pdb_file = tmp_path / "alice.pdb"
    pdb_file.write_text("HEADER ALICE PRIVATE\nATOM\n", encoding="utf-8")
    monkeypatch.setattr(
        "services.docking.preparer.get_target_pdb_path", lambda _pdb_id: str(pdb_file)
    )

    alice_client = environment.client(alice)
    bob_client = environment.client(bob)
    assert alice_client.get(f"/targets/{private.id}/pdb").status_code == 200
    assert alice_client.get(f"/targets/{private.pdb_id}/pdb").status_code == 200
    assert bob_client.get(f"/targets/{private.id}/pdb").status_code == 404
    assert bob_client.get(f"/targets/{private.pdb_id}/pdb").status_code == 404
    assert environment.client(None).get(f"/targets/{private.pdb_id}/pdb").status_code == 404

    foreign_share = bob_client.post(f"/targets/{private.id}/share")
    assert foreign_share.status_code == 404
    assert "permiso" not in foreign_share.text.lower()

    own_share = alice_client.post(f"/targets/{private.id}/share")
    assert own_share.status_code == 200
    assert private.pdb_id in {
        item["pdb_id"] for item in environment.client(bob).get("/targets/").json()
    }


@pytest.mark.asyncio
async def test_scientific_preflights_reject_a_foreign_private_receptor(environment):
    alice = await environment.user("alice")
    bob = await environment.user("bob")
    private = await environment.target("USR_ALICE", owner=alice, private=True, anti=True)
    valid_smiles = "CC(=O)OC1=CC=CC=C1C(=O)O"

    async with environment.factory() as session:
        with pytest.raises(HTTPException) as evaluation_error:
            await evaluation.evaluation_preflight(
                data=evaluation.PreflightRequest(
                    smiles=valid_smiles, target_pdb_id=private.pdb_id
                ),
                db=session,
                current_user=bob,
            )
        assert evaluation_error.value.status_code == 404

        with pytest.raises(HTTPException) as submit_error:
            await evaluation.submit_evaluation(
                data=evaluation.EvaluationSubmitRequest(
                    smiles=valid_smiles, target_pdb_id=private.pdb_id
                ),
                request=_request(),
                current_user=bob,
                db=session,
            )
        assert submit_error.value.status_code == 404

        study = {
            "schema_version": 1,
            "name": "Privada ajena",
            "receptor": {"pdb_id": private.pdb_id, "chain": "A"},
            "config": {"docking_engine": "vina", "exhaustiveness": 8, "num_poses": 5},
        }
        upload = UploadFile(filename="cohort.csv", file=io.BytesIO(b"name,smiles\na,CCO\n"))
        with pytest.raises(HTTPException) as cohort_error:
            await evaluation_cohorts.cohort_preflight(
                file=upload,
                study=json.dumps(study),
                current_user=bob,
                db=session,
            )
        assert cohort_error.value.status_code == 404

        legacy_upload = UploadFile(
            filename="batch.csv", file=io.BytesIO(b"name,smiles\na,CCO\n")
        )
        with pytest.raises(HTTPException) as legacy_batch_error:
            await batch.submit_batch(
                file=legacy_upload,
                target_pdb_id=private.pdb_id,
                num_workers=1,
                early_exit=False,
                current_user=bob,
                db=session,
            )
        assert legacy_batch_error.value.status_code == 404

        alice_panel = await pro_features.list_anti_targets(current_user=alice, db=session)
        bob_panel = await pro_features.list_anti_targets(current_user=bob, db=session)
        assert private.pdb_id in {item["pdb_id"] for item in alice_panel["anti_targets"]}
        assert private.pdb_id not in {item["pdb_id"] for item in bob_panel["anti_targets"]}

        with pytest.raises(HTTPException) as docking_error:
            await pro_features.dock_single_anti_target(
                molecule_id=str(uuid.uuid4()),
                target_pdb_id=private.pdb_id,
                current_user=bob,
                db=session,
            )
        assert docking_error.value.status_code == 404


@pytest.mark.asyncio
async def test_create_variant_is_private_owned_and_keeps_parent_recipe(
    environment, monkeypatch
):
    from api.routers import targets
    from services.targets import ingestion_manager

    alice = await environment.user("variant-alice")
    public = await environment.target("8VAR")
    created = await environment.target("USR_VAR01", owner=alice, private=True)

    captured = {}

    async def fake_ingest_custom_target(**kwargs):
        captured.update(kwargs)
        return {"target": created}

    monkeypatch.setattr(targets, "_read_variant_source_bytes", AsyncMock(return_value=b"PDB"))
    monkeypatch.setattr(ingestion_manager, "ingest_custom_target", fake_ingest_custom_target)

    async with environment.factory() as session:
        result = await targets.create_target_variant(
            pdb_id=public.pdb_id,
            request=targets.TargetVariantRequest(
                name="8VAR · Zn",
                chain_id="b",
                grid_center=(1.0, 2.0, 3.0),
                grid_size=(20.0, 21.0, 22.0),
                cofactors_whitelist=["zn", "ZN", "hem"],
            ),
            current_user=alice,
            db=session,
        )

    assert result is created
    assert captured["creator_id"] == alice.id
    assert captured["is_community"] is False
    assert captured["preparation_parent_id"] == public.id
    assert captured["chain_id"] == "B"
    assert captured["cofactors_whitelist"] == ["HEM", "ZN"]
    assert captured["preparation_recipe"]["parent_pdb_id"] == public.pdb_id


@pytest.mark.asyncio
async def test_create_variant_cannot_clone_a_foreign_private_receptor(
    environment, monkeypatch
):
    from api.routers import targets

    alice = await environment.user("variant-owner")
    bob = await environment.user("variant-foreign")
    private = await environment.target("USR_VBASE", owner=alice, private=True)
    source_reader = AsyncMock(return_value=b"PDB")
    monkeypatch.setattr(targets, "_read_variant_source_bytes", source_reader)

    async with environment.factory() as session:
        with pytest.raises(HTTPException) as denied:
            await targets.create_target_variant(
                pdb_id=private.pdb_id,
                request=targets.TargetVariantRequest(name="No autorizada"),
                current_user=bob,
                db=session,
            )

    assert denied.value.status_code == 404
    source_reader.assert_not_awaited()


def test_private_target_without_owner_is_not_claimable():
    orphan = type(
        "Target",
        (),
        {"pdb_id": "USR_ORPHAN", "is_private": True, "creator_id": None},
    )()
    legacy_rcsb = type(
        "Target",
        (),
        {"pdb_id": "9ZZZ", "is_private": True, "creator_id": None},
    )()
    user = type("User", (), {"id": uuid.uuid4()})()
    assert target_is_accessible(orphan, user) is False
    assert target_is_accessible(legacy_rcsb, user) is True


@pytest.mark.asyncio
async def test_internal_service_contract_is_owner_only_and_usr_ids_fail_closed(environment):
    alice = await environment.user("alice")
    bob = await environment.user("bob")
    private = await environment.target("USR_ALICE", owner=alice, private=True)

    async with environment.factory() as session:
        repository = Repository(session)
        owned = await get_target_for_user_id(
            repository, private.pdb_id, str(alice.id), allow_missing=True
        )
        assert owned.id == private.id

        for actor_id in (str(bob.id), None):
            with pytest.raises(HTTPException) as foreign_error:
                await get_target_for_user_id(
                    repository, private.pdb_id, actor_id, allow_missing=True
                )
            assert foreign_error.value.status_code == 404

        for orphan_id in ("USR_ORPHAN", "SECRET"):
            with pytest.raises(HTTPException) as orphan_file_error:
                await get_target_for_user_id(
                    repository, orphan_id, str(alice.id), allow_missing=True
                )
            assert orphan_file_error.value.status_code == 404

        assert (
            await get_target_for_user_id(
                repository, "9ZZZ", None, allow_missing=True
            )
            is None
        )


@pytest.mark.asyncio
async def test_rcsb_auto_ingestion_is_public_data_but_not_a_private_orphan(
    environment, monkeypatch
):
    from services.targets import ingestion_manager

    alice = await environment.user("alice")
    bob = await environment.user("bob")
    monkeypatch.setattr(ingestion_manager, "exists", AsyncMock(return_value=False))
    monkeypatch.setattr(
        ingestion_manager,
        "download_pdb_from_rcsb",
        AsyncMock(return_value="HEADER    PUBLIC TEST\nTITLE     PUBLIC RECEPTOR\n"),
    )
    monkeypatch.setattr(ingestion_manager, "write_text", AsyncMock())
    monkeypatch.setattr(
        ingestion_manager,
        "discover_pocket_from_pdb",
        lambda *_args, **_kwargs: {
            "success": True,
            "detected_chain": "A",
            "grid_center": (1.0, 2.0, 3.0),
            "grid_size": (20.0, 20.0, 20.0),
            "suggested_hotspots": [],
            "warnings": [],
            "all_ligands_found": [],
            "ligand_name": "",
            "ligand_id": None,
        },
    )
    monkeypatch.setattr(
        ingestion_manager,
        "fetch_target_cofactors_from_rcsb",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        ingestion_manager, "prepare_target", AsyncMock(return_value="prepared/9ZZZ.pdbqt")
    )

    async with environment.factory() as session:
        result = await ingestion_manager.ingest_new_target("9zzz", session)
        target = result["target"]
        assert target.is_private is False
        assert target.creator_id is None
        assert target_is_accessible(target, alice) is True
        assert target_is_accessible(target, bob) is True
