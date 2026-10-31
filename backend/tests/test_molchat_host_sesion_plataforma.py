"""La plataforma acepta la sesión mh1 como identidad (Fase 6, diseño A).

El sidecar reenvía el Bearer que recibe; estos tests demuestran que la
plataforma lo honra contra un usuario real semilla, que rechaza lo forjado
o caducado, y que el camino JWT ni se entera (puerta por prefijo).
"""

import time
import uuid

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.dependencies import get_current_user
from core.database import _json_deserializer, _json_serializer
from core.database import get_db
from core.models import Base, UserORM
from services.molchat_host import sesion


@pytest_asyncio.fixture
async def engine(tmp_path):
    eng = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'sesion.db'}",
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def cuenta(session_factory):
    async with session_factory() as db:
        user = UserORM(email="molchat@example.com", username="molchat")
        db.add(user)
        await db.commit()
        return str(user.id)


@pytest.fixture
def app(session_factory):
    async def _db():
        async with session_factory() as db:
            yield db

    app = FastAPI()
    app.dependency_overrides[get_db] = _db

    @app.get("/quien-soy")
    async def quien_soy(user: UserORM = Depends(get_current_user)):
        return {"sub": str(user.id)}

    sesion.fijar_secreto_host(b"test-secret-32-bytes-0123456789ab")
    return app


@pytest.mark.asyncio
async def test_sesion_mh1_autentica_al_usuario(app, cuenta):
    token = sesion.acunar(cuenta, {"read", "chat"}, 600)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        respuesta = await c.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 200
    assert respuesta.json() == {"sub": cuenta}


@pytest.mark.asyncio
async def test_sesion_mala_cuenta_desconocida_o_caducada_401(app):
    bueno = sesion.acunar(str(uuid.uuid4()), {"read"}, 600)
    caducado = sesion.acunar(str(uuid.uuid4()), {"read"}, 60, ahora=time.time() - 3600)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        assert (await c.get("/quien-soy",
                            headers={"Authorization": f"Bearer {bueno[:-2]}xx"})).status_code == 401
        assert (await c.get("/quien-soy",
                            headers={"Authorization": f"Bearer {caducado}"})).status_code == 401
        assert (await c.get("/quien-soy",
                            headers={"Authorization": f"Bearer {bueno}"})).status_code == 401


@pytest.mark.asyncio
async def test_jwt_raro_no_pisa_el_codigo_mh1(app, monkeypatch):
    def _explotar(*args, **kwargs):
        raise AssertionError("el camino JWT no debe tocar mh1")

    monkeypatch.setattr(sesion, "verificar_para_plataforma", _explotar)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        respuesta = await c.get("/quien-soy",
                                headers={"Authorization": "Bearer jwt-basura"})
    assert respuesta.status_code == 401


@pytest.mark.asyncio
async def test_sin_secreto_instalado_no_hay_mh1(app, cuenta, monkeypatch):
    token = sesion.acunar(cuenta, {"read"}, 600)
    monkeypatch.setattr(sesion, "_SECRETO_HOST", None)
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as c:
        respuesta = await c.get("/quien-soy", headers={"Authorization": f"Bearer {token}"})
    assert respuesta.status_code == 401
