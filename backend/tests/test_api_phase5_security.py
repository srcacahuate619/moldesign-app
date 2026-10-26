"""Regresiones de seguridad de fase 5 sobre rutas HTTP reales."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from api.auth import create_access_token, create_refresh_token
from api.dependencies import get_current_user
from api.middleware import register_middleware
from api.routers.auth import router as auth_router
from core.config import get_settings
from core.database import get_db
from core.models import Base, UserORM
from services.targets.access import is_safe_local_target_id
from services.targets.box_validation import validar_caja
from utils.file_handlers import download_pdb_from_rcsb
from services.docking.preparer import get_target_pdb_path


@pytest.mark.asyncio
async def test_tokens_tipo_exp_y_revocacion_en_api(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def db_override():
        async with factory() as session:
            yield session

    app = FastAPI()
    register_middleware(app)
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = db_override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://localhost") as client:
        registered = await client.post("/auth/register", json={
            "email": "phase5@example.com", "username": "phase5user",
            "password": "strong-password-123",
        })
        assert registered.status_code == 201, registered.text
        body = registered.json()
        access = body["access_token"]
        refresh = body["refresh_token"]
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})).status_code == 200
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {refresh}"})).status_code == 401
        no_exp = jwt.encode(
            {"sub": body["user_id"], "iat": int(datetime.now(UTC).timestamp()),
             "type": "access", "jti": str(uuid.uuid4())},
            get_settings().secret_key, algorithm="HS256",
        )
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {no_exp}"})).status_code == 401
        renewed = await client.post("/auth/refresh", json={"refresh_token": refresh})
        assert renewed.status_code == 200, renewed.text
        assert (await client.post("/auth/refresh", json={"refresh_token": refresh})).status_code == 401
        logout = await client.post("/auth/logout", headers={"Authorization": f"Bearer {access}"},
                                   json={"refresh_token": renewed.json()["refresh_token"]})
        assert logout.status_code == 204, logout.text
        assert (await client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})).status_code == 401
        assert (await client.post("/auth/refresh", json={
            "refresh_token": renewed.json()["refresh_token"]
        })).status_code == 401
        assert (await client.post("/auth/register", json={
            "email": "another@example.com", "username": "demo",
            "password": "strong-password-123",
        })).status_code == 409
        assert (await client.post("/auth/register", json={
            "email": "another@example.com", "username": "anotheruser",
            "password": "ñ" * 40,
        })).status_code == 422
        assert (await client.post("/auth/login", json={
            "email": "phase5@example.com", "password": "wrong",
        }, headers={"Origin": "https://malicioso.example"})).status_code == 403
        assert (await client.get("/auth/me", headers={"Host": "malicioso.example"})).status_code == 400
    await engine.dispose()


@pytest.mark.asyncio
async def test_login_escritorio_exige_secreto_y_vincula_tokens(tmp_path, monkeypatch):
    monkeypatch.setenv("MOLDESIGN_LAUNCH_TOKEN", "a" * 64)
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'desktop.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def db_override():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = db_override
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                 base_url="http://localhost") as client:
        assert (await client.get("/auth/desktop-login")).status_code == 403
        good = await client.get("/auth/desktop-login",
                                headers={"X-MolDesign-Launch": "a" * 64})
        assert good.status_code == 200, good.text
        token = good.json()["access_token"]
        assert jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])["launch"]
        monkeypatch.setenv("MOLDESIGN_LAUNCH_TOKEN", "b" * 64)
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        from api.auth import valid_guest_token
        assert not valid_guest_token(payload)
    await engine.dispose()


@pytest.mark.asyncio
async def test_identificadores_pdb_y_caja_se_rechazan_antes_de_io(monkeypatch):
    for invalid in ("..\\..\\x", "C:\\privado", "1ABC?X=1", "a/b"):
        assert not is_safe_local_target_id(invalid)
        with pytest.raises(ValueError):
            get_target_pdb_path(invalid)
        with pytest.raises(ValueError):
            await download_pdb_from_rcsb(invalid)
    from utils.file_handlers import _fetch_rcsb_entry_detail, fetch_target_cofactors_from_rcsb
    with pytest.raises(ValueError):
        await _fetch_rcsb_entry_detail("../1ABC")
    with pytest.raises(ValueError):
        await fetch_target_cofactors_from_rcsb("1ABC?query=1")
    for size in ((-5, 20, 20), (0, 20, 20), (200, 20, 20),
                 (float("nan"), 20, 20)):
        with pytest.raises(ValueError):
            validar_caja((0, 0, 0), size)



def test_limites_de_pipeline_y_geometria_rechazan_costos_anomalos():
    from pydantic import ValidationError
    from api.routers.evaluation import EvaluationSubmitRequest, PipelineConfigRequest

    for params in (
        {"docking": {"exhaustiveness": 100000}},
        {"docking": {"num_poses": 10000}},
        {"docking": {"engine": "vina"}},
        {"conformer": {"conformers": 10000}},
        {"unknown": {}},
    ):
        with pytest.raises(ValidationError):
            PipelineConfigRequest(stage_params=params)
    # `target_id` no es un campo del modelo (es `target_pdb_id`): estas pruebas lo
    # pasaban creyendo ejercitar la geometría, el modelo lo ignoraba en silencio y
    # seguían verdes. Con el modelo cerrado (LUNA-04) habrían seguido en verde por
    # la razón equivocada: el 422 de «campo desconocido», no el de la caja.
    for size in ((4, 20, 20), (81, 20, 20), (float("inf"), 20, 20)):
        with pytest.raises(ValidationError) as salida:
            EvaluationSubmitRequest(smiles="CCO", target_pdb_id="7E2Y", grid_size=size)
        assert "grid_size" in {str(e["loc"][-1]) for e in salida.value.errors()}
    with pytest.raises(ValidationError) as salida:
        EvaluationSubmitRequest(smiles="CCO", target_pdb_id="7E2Y",
                                custom_hotspots=["A" * 33])
    assert "custom_hotspots" in {str(e["loc"][-1]) for e in salida.value.errors()}


@pytest.mark.asyncio
async def test_estadisticas_no_revelan_moleculas_de_otra_cuenta(tmp_path):
    from core.models import MoleculeORM, TargetORM, EvaluationResultORM
    from api.routers.stats import get_global_stats, get_leaderboard

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'stats.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        alice = UserORM(email="alice@phase5.test", username="alice")
        bob = UserORM(email="bob@phase5.test", username="bob")
        target = TargetORM(pdb_id="1ABC", name="Test", chain="A",
                           grid_center_x=0, grid_center_y=0, grid_center_z=0)
        db.add_all([alice, bob, target])
        await db.flush()
        secret = MoleculeORM(smiles="CCO", name="Bob secret", smiles_hash="b"*64,
                             user_id=bob.id, target_id=target.id)
        db.add(secret)
        await db.flush()
        db.add(EvaluationResultORM(molecule_id=secret.id, affinity_kcal=-9.9,
                                   total_score=99))
        await db.commit()
        anon = await get_global_stats(db=db, current_user=None)
        assert anon["total_molecules"] == 0 and anon["best_affinity"] is None
        own = await get_global_stats(db=db, current_user=alice)
        assert own["total_molecules"] == 0 and own["best_affinity"] is None
        assert await get_leaderboard(db=db, current_user=alice, limit=10) == []
        theirs = await get_global_stats(db=db, current_user=bob)
        assert theirs["total_molecules"] == 1 and theirs["best_affinity"] == -9.9
    await engine.dispose()
