"""EVAL-SCI-001 — el receptor de una corrida nunca se sustituye en silencio.

Una evaluación que no puede resolver el receptor pedido tiene DOS salidas
honestas: incorporarlo o fallar diciéndolo. La tercera —acoplar contra el
receptor base y devolver `SUCCESS`— produce un resultado que parece completo,
se persiste, se exporta al dossier y describe una proteína que el investigador
nunca eligió. Estas pruebas fijan que esa tercera salida no existe.
"""

from __future__ import annotations

import inspect
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.models import Base, TargetORM, UserORM
from db.repository import Repository
from services.targets.resolution import (
    TargetUnavailableError,
    resolve_execution_target,
)


class _RepositorioFalso:
    """Repositorio mínimo: sólo lo que la resolución del receptor necesita."""

    def __init__(self, conocidos: dict[str, object] | None = None):
        self.conocidos = conocidos or {}
        self.default_pedido = False

    async def get_target_by_pdb_id(self, pdb_id: str):
        return self.conocidos.get(pdb_id.strip().upper())

    async def ensure_default_target(self):
        self.default_pedido = True
        return object()


class _TargetFalso:
    def __init__(self, pdb_id: str):
        self.pdb_id = pdb_id


@pytest.mark.asyncio
async def test_un_receptor_ausente_e_iningestable_detiene_la_corrida(monkeypatch):
    """Sin receptor no hay corrida: nunca se acopla contra otra proteína."""

    async def _ingesta_fallida(pdb_id, db):
        return {"success": False, "error": "sin conexión"}

    monkeypatch.setattr(
        "services.targets.ingestion_manager.ingest_new_target", _ingesta_fallida
    )
    repositorio = _RepositorioFalso()

    with pytest.raises(TargetUnavailableError) as error:
        await resolve_execution_target(repositorio, None, "5TUN")

    assert "5TUN" in str(error.value)
    assert repositorio.default_pedido is False


@pytest.mark.asyncio
async def test_una_excepcion_de_ingesta_tampoco_sustituye_el_receptor(monkeypatch):
    """Un fallo inesperado de la ingesta es un fallo, no un cambio de proteína."""

    async def _ingesta_rota(pdb_id, db):
        raise RuntimeError("RCSB inalcanzable")

    monkeypatch.setattr(
        "services.targets.ingestion_manager.ingest_new_target", _ingesta_rota
    )
    repositorio = _RepositorioFalso()

    with pytest.raises(TargetUnavailableError):
        await resolve_execution_target(repositorio, None, "5TUN")

    assert repositorio.default_pedido is False


@pytest.mark.asyncio
async def test_el_receptor_base_si_puede_sembrarse_en_una_base_vacia(monkeypatch):
    """Sembrar 7E2Y cuando 7E2Y es lo pedido no es sustituir nada."""

    async def _ingesta_fallida(pdb_id, db):
        return {"success": False}

    monkeypatch.setattr(
        "services.targets.ingestion_manager.ingest_new_target", _ingesta_fallida
    )
    repositorio = _RepositorioFalso()

    resuelto = await resolve_execution_target(repositorio, None, "7e2y")

    assert repositorio.default_pedido is True
    assert resuelto is not None


@pytest.mark.asyncio
async def test_un_receptor_conocido_se_devuelve_tal_cual():
    repositorio = _RepositorioFalso({"5TUN": _TargetFalso("5TUN")})

    resuelto = await resolve_execution_target(repositorio, None, "5tun")

    assert resuelto.pdb_id == "5TUN"
    assert repositorio.default_pedido is False


@pytest.mark.asyncio
async def test_la_ingesta_exitosa_devuelve_el_receptor_incorporado(monkeypatch):
    async def _ingesta_ok(pdb_id, db):
        return {"success": True, "target": _TargetFalso("5TUN")}

    monkeypatch.setattr(
        "services.targets.ingestion_manager.ingest_new_target", _ingesta_ok
    )
    repositorio = _RepositorioFalso()

    resuelto = await resolve_execution_target(repositorio, None, "5TUN")

    assert resuelto.pdb_id == "5TUN"
    assert repositorio.default_pedido is False


# ── Persistencia: la molécula se registra contra el receptor pedido ──────


@pytest_asyncio.fixture
async def sesion(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'moleculas.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_create_or_get_molecule_rechaza_un_receptor_explicito_inexistente(sesion):
    """La molécula no puede quedar registrada contra otro receptor.

    `create_or_get_molecule` es el punto donde la molécula adquiere su
    procedencia estructural. Si acepta un `target_pdb_id` desconocido y guarda
    el receptor base, el resultado miente sobre contra qué se acopló aunque el
    motor haya hecho lo correcto.
    """
    repositorio = Repository(sesion)

    with pytest.raises(TargetUnavailableError):
        await repositorio.create_or_get_molecule(
            smiles="CCO", target_pdb_id="5TUN", name="etanol"
        )


@pytest.mark.asyncio
async def test_create_or_get_molecule_usa_el_receptor_pedido_cuando_existe(sesion):
    usuario = UserORM(
        id=uuid.uuid4(),
        email="alice@moldesign.local",
        username="alice",
        hashed_password="x",
        is_active=True,
    )
    receptor = TargetORM(
        id=uuid.uuid4(),
        pdb_id="5TUN",
        name="Receptor de prueba",
        chain="A",
        description="fixture",
        grid_center_x=1.0,
        grid_center_y=2.0,
        grid_center_z=3.0,
        grid_size_x=20.0,
        grid_size_y=20.0,
        grid_size_z=20.0,
        requires_cns=False,
        is_prepared=True,
    )
    sesion.add_all([usuario, receptor])
    await sesion.commit()

    repositorio = Repository(sesion)
    molecula = await repositorio.create_or_get_molecule(
        smiles="CCO", target_pdb_id="5TUN", user_id=usuario.id
    )

    assert molecula.target_id == receptor.id


@pytest.mark.asyncio
async def test_mismo_ligando_y_receptor_quedan_separados_por_usuario(sesion):
    alice = UserORM(
        id=uuid.uuid4(), email="alice2@moldesign.local", username="alice2",
        hashed_password="x", is_active=True,
    )
    bob = UserORM(
        id=uuid.uuid4(), email="bob@moldesign.local", username="bob",
        hashed_password="x", is_active=True,
    )
    receptor = TargetORM(
        id=uuid.uuid4(), pdb_id="6ABC", name="Receptor compartido", chain="A",
        description="fixture", grid_center_x=1.0, grid_center_y=2.0,
        grid_center_z=3.0, grid_size_x=20.0, grid_size_y=20.0,
        grid_size_z=20.0, requires_cns=False, is_prepared=True,
    )
    sesion.add_all([alice, bob, receptor])
    await sesion.commit()
    repositorio = Repository(sesion)

    de_alice = await repositorio.create_or_get_molecule(
        smiles="CCO", target_pdb_id="6ABC", user_id=alice.id
    )
    de_bob = await repositorio.create_or_get_molecule(
        smiles="CCO", target_pdb_id="6ABC", user_id=bob.id
    )
    repetida_de_alice = await repositorio.create_or_get_molecule(
        smiles="CCO", target_pdb_id="6ABC", user_id=alice.id
    )

    assert de_alice.id != de_bob.id
    assert de_alice.user_id == alice.id
    assert de_bob.user_id == bob.id
    assert repetida_de_alice.id == de_alice.id


# ── Guardas de código: ningún camino de ejecución vuelve a caer al base ──


@pytest.mark.parametrize(
    "modulo",
    [
        "services/pipeline/runner.py",
        "services/docking/queue_handler.py",
        "services/docking/peptide_docking.py",
    ],
)
def test_ningun_pipeline_llama_a_ensure_default_target(modulo: str):
    """El fallback vive en UNA función que falla; no se reintroduce por copia."""
    ruta = Path(__file__).resolve().parents[1] / modulo
    fuente = ruta.read_text(encoding="utf-8")

    assert "ensure_default_target" not in fuente


def test_el_docking_peptidico_registra_la_molecula_con_su_receptor():
    """El peptídico registraba la molécula sin receptor: iba al base por defecto."""
    from services.docking import peptide_docking

    fuente = inspect.getsource(peptide_docking)

    assert "create_or_get_molecule(smiles=smiles)" not in fuente
