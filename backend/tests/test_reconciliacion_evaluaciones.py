"""EVAL-BE-004 — ninguna corrida muerta queda fingiendo que sigue en marcha.

El arranque reconciliaba sólo las moléculas `pending`. Una evaluación que
moría durante el cálculo —cierre de la aplicación, apagón, crash del
proceso— ya había pasado a `validated` (propiedades hechas) o `docking`
(acoplamiento en curso), y ahí se quedaba para siempre:

* el historial lista `evaluated` y `failed`, así que la corrida desaparecía
  sin dejar rastro consultable;
* `get_desktop_job_status` no encontraba estado terminal en SQLite y devolvía
  «la tarea ya no existe», contradiciendo a la fila de la base de datos.

La reconciliación cierra ahora todos los estados no terminales y escribe POR
QUÉ, que es lo único que se sabe con certeza: se interrumpió.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.models import (
    Base,
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)
from services.docking.recovery import reconcile_interrupted_evaluations


@pytest_asyncio.fixture
async def factory(tmp_path: Path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'recovery.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield sessions
    finally:
        await engine.dispose()


async def _semilla(factory) -> dict[str, uuid.UUID]:
    async with factory() as session:
        user = UserORM(
            id=uuid.uuid4(),
            email="alice@moldesign.local",
            username="alice",
            hashed_password="x",
            is_active=True,
        )
        target = TargetORM(
            id=uuid.uuid4(),
            pdb_id="7E2Y",
            name="Receptor base",
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
        session.add_all([user, target])
        ids: dict[str, uuid.UUID] = {}
        for nombre, estado in (
            ("pendiente", MoleculeStatus.PENDING),
            ("validada", MoleculeStatus.VALIDATED),
            ("acoplando", MoleculeStatus.DOCKING),
            ("evaluada", MoleculeStatus.EVALUATED),
            ("fallida", MoleculeStatus.FAILED),
        ):
            molecula = MoleculeORM(
                id=uuid.uuid4(),
                smiles="CCO",
                name=nombre,
                smiles_hash=f"hash-{nombre}",
                status=estado,
                user_id=user.id,
                target_id=target.id,
            )
            session.add(molecula)
            ids[nombre] = molecula.id
        await session.commit()
        return ids


@pytest.mark.asyncio
async def test_las_corridas_a_medias_se_cierran_como_interrumpidas(factory):
    ids = await _semilla(factory)

    async with factory() as session:
        cerradas = await reconcile_interrupted_evaluations(session)
        await session.commit()

    assert cerradas == 3  # pending + validated + docking

    async with factory() as session:
        estados = {
            nombre: (await session.get(MoleculeORM, mol_id)).status
            for nombre, mol_id in ids.items()
        }

    assert estados["pendiente"] == MoleculeStatus.FAILED
    assert estados["validada"] == MoleculeStatus.FAILED
    assert estados["acoplando"] == MoleculeStatus.FAILED
    # Lo terminal no se reescribe: una evaluación buena de ayer sigue siéndolo.
    assert estados["evaluada"] == MoleculeStatus.EVALUATED
    assert estados["fallida"] == MoleculeStatus.FAILED


@pytest.mark.asyncio
async def test_la_interrupcion_se_explica_y_no_se_confunde_con_un_fallo_cientifico(
    factory,
):
    ids = await _semilla(factory)

    async with factory() as session:
        await reconcile_interrupted_evaluations(session)
        await session.commit()

    async with factory() as session:
        filas = (
            await session.execute(
                select(EvaluationResultORM).where(
                    EvaluationResultORM.molecule_id == ids["acoplando"]
                )
            )
        ).scalars().all()

    assert len(filas) == 1
    mensaje = filas[0].error_message or ""
    assert "interrump" in mensaje.lower()
    # No se inventa un resultado: la corrida no produjo afinidad ninguna.
    assert filas[0].affinity_kcal is None
    assert filas[0].total_score is None


@pytest.mark.asyncio
async def test_reconciliar_dos_veces_no_cambia_nada_mas(factory):
    await _semilla(factory)

    async with factory() as session:
        primera = await reconcile_interrupted_evaluations(session)
        await session.commit()
    async with factory() as session:
        segunda = await reconcile_interrupted_evaluations(session)
        await session.commit()

    assert primera == 3
    assert segunda == 0


def test_el_arranque_usa_la_reconciliacion_completa():
    """`main.py` ya no puede quedarse sólo con `pending`."""
    fuente = (
        Path(__file__).resolve().parents[1] / "api/main.py"
    ).read_text(encoding="utf-8")

    assert "reconcile_interrupted_evaluations" in fuente
    assert "list_molecules_by_status(MoleculeStatus.PENDING)" not in fuente
