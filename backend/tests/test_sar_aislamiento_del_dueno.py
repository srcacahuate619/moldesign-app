"""La tabla SAR automática sólo reúne moléculas del dueño de la petición (auditoría científica 1.0.4, S1-3.3).

`GET /sar/{molecule_id}` comprueba que la molécula base es de quien pregunta, pero los análogos salían de
`Repository.get_sar_analogs` (hoy `get_sar_candidatas`), que sólo filtraba por dueño `if user_id:`. Sin sesión la ruta pasaba `None`, y una
petición anónima recibía, además de lo anónimo, los SMILES y las afinidades de **cualquier** cuenta contra el mismo
receptor. La regla del producto (`dueno_de_la_peticion`, TRANS-ANON-002) es otra: una cuenta ve lo suyo y nada más, y
una petición sin sesión ve lo anónimo y nada más.

Tres dueños sobre el mismo receptor: dos cuentas y el espacio anónimo. La prueba se corre contra los tres, y el
repositorio, que ya no admite un dueño ausente, falla cerrado.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import core.database as db_mod
from api.dependencies import get_current_user_optional
from api.routers.sar import router as sar_router
from core.database import get_db
from core.models import Base, EvaluationResultORM, MoleculeORM, TargetORM, UserORM
from db.repository import Repository

# (nombre, SMILES, afinidad): cada dueño tiene dos moléculas contra el mismo receptor.
ANONIMAS = [("anon-0", "CCO", -5.0), ("anon-1", "CCN", -5.5)]
DE_ANA = [("ana-0", "CCC", -6.0), ("ana-1", "CCCl", -6.5)]
DE_OTRO = [("otro-0", "CCBr", -7.0), ("otro-1", "CCCC", -7.5)]


class _Entorno:
    def __init__(self, ruta):
        self.ruta = ruta
        self.engine = None
        self.factory = None
        self.ana: UserORM | None = None
        self.otro: UserORM | None = None
        self.ids: dict[str, uuid.UUID] = {}

    async def arrancar(self):
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self.ruta}")
        self.factory = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def apagar(self):
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None

    async def sembrar(self):
        async with self.factory() as s:
            anonimo = await Repository(s).get_or_create_test_user()
            self.ana = UserORM(id=uuid.uuid4(), email="a@b.c", username="ana", hashed_password="x", is_active=True)
            self.otro = UserORM(id=uuid.uuid4(), email="o@b.c", username="otro", hashed_password="x", is_active=True)
            receptor = TargetORM(
                id=uuid.uuid4(), pdb_id="3F75", name="COX-2", chain="A",
                grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
                grid_size_x=20.0, grid_size_y=20.0, grid_size_z=20.0,
            )
            s.add_all([self.ana, self.otro, receptor])
            await s.flush()
            for duenyo, filas in ((anonimo, ANONIMAS), (self.ana, DE_ANA), (self.otro, DE_OTRO)):
                for nombre, smiles, afinidad in filas:
                    molecula = MoleculeORM(
                        id=uuid.uuid4(), smiles=smiles, name=nombre,
                        smiles_hash=f"{abs(hash(nombre)):x}".ljust(64, "0")[:64],
                        user_id=duenyo.id, target_id=receptor.id,
                    )
                    s.add(molecula)
                    await s.flush()
                    s.add(EvaluationResultORM(
                        molecule_id=molecula.id, affinity_kcal=afinidad, total_score=60.0 + afinidad,
                    ))
                    self.ids[nombre] = molecula.id
            await s.commit()

    def cliente(self, usuario: UserORM | None) -> httpx.AsyncClient:
        async def db_override():
            async with self.factory() as session:
                yield session

        async def usuario_override():
            return usuario

        app = FastAPI()
        app.include_router(sar_router)
        app.dependency_overrides[get_db] = db_override
        app.dependency_overrides[get_current_user_optional] = usuario_override
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost")


@pytest_asyncio.fixture
async def entorno(tmp_path):
    await db_mod.reset_engine()
    env = _Entorno(tmp_path / "sar_dueno.db")
    await env.arrancar()
    await env.sembrar()
    try:
        yield env
    finally:
        await env.apagar()
        await db_mod.reset_engine()


def _smiles_de_la_tabla(respuesta) -> set[str]:
    assert respuesta.status_code == 200, respuesta.text
    return {fila["smiles"] for fila in respuesta.json()["results"]}


def _smiles(filas) -> set[str]:
    return {smiles for _nombre, smiles, _afinidad in filas}


@pytest.mark.asyncio
async def test_una_peticion_sin_sesion_solo_ve_lo_anonimo(entorno):
    """El defecto: sin sesión llegaban también las dos moléculas de ana y las dos de otro."""
    async with entorno.cliente(None) as c:
        r = await c.get(f"/sar/{entorno.ids['anon-0']}")

    assert _smiles_de_la_tabla(r) == _smiles(ANONIMAS)


@pytest.mark.asyncio
async def test_una_cuenta_solo_ve_lo_suyo(entorno):
    async with entorno.cliente(entorno.ana) as c:
        r = await c.get(f"/sar/{entorno.ids['ana-0']}")

    assert _smiles_de_la_tabla(r) == _smiles(DE_ANA)


@pytest.mark.asyncio
async def test_la_otra_cuenta_ve_lo_suyo_aunque_el_receptor_sea_el_mismo(entorno):
    async with entorno.cliente(entorno.otro) as c:
        r = await c.get(f"/sar/{entorno.ids['otro-0']}")

    assert _smiles_de_la_tabla(r) == _smiles(DE_OTRO)


@pytest.mark.asyncio
async def test_la_molecula_base_ajena_sigue_siendo_403(entorno):
    """La comprobación de la base no cambia: ni sin sesión se lee lo de una cuenta, ni al revés."""
    async with entorno.cliente(None) as c:
        sin_sesion = await c.get(f"/sar/{entorno.ids['ana-0']}")
    async with entorno.cliente(entorno.ana) as c:
        con_sesion = await c.get(f"/sar/{entorno.ids['anon-0']}")

    assert sin_sesion.status_code == 403
    assert con_sesion.status_code == 403


@pytest.mark.asyncio
async def test_el_repositorio_falla_cerrado_sin_dueno(entorno):
    """Un dueño ausente ya no significa «todos»: devuelve lo que no tiene dueño, que aquí es nada."""
    async with entorno.factory() as s:
        sin_dueno = await Repository(s).get_sar_candidatas("3F75", None)  # type: ignore[arg-type]
        de_ana = await Repository(s).get_sar_candidatas("3F75", entorno.ana.id)
        # La segunda consulta, la de las elegidas, repite el filtro: pedir las moléculas de otro con el dueño de
        # ana no devuelve nada, aunque los identificadores existan.
        ajenas = await Repository(s).get_sar_evaluaciones(
            "3F75", entorno.ana.id, [entorno.ids["otro-0"], entorno.ids["anon-0"]],
        )

    assert sin_dueno == []
    assert {fila[1] for fila in de_ana} == _smiles(DE_ANA)
    assert ajenas == []
