"""
La procedencia por pose tiene que cruzar la persistencia, o no existe.

EL FALLO QUE PRUEBAN (ENS-07, encontrado el 2026-09-17)
═══════════════════════════════════════════════════════════════════════════

`DockingPose.source_provenance` se añadió para que una pose de una piscina de
ensemble conserve de qué corrida y de qué rank salió. El campo existe en el
modelo, el agrupador lo rellena y la revisión del ensemble lo declaró resuelto:

    «cada pose conserva `source_provenance` con rank original, ruta SDF de su
    corrida, parsing_source y metadata del conversor […] el backend expone los
    nuevos datos para su futura presentación.»

No los exponía. `Repository.cast_pose` enumeraba los campos a persistir uno a
uno —rank, affinity, rmsd_lb, rmsd_ub, pdbqt_block, conformer_index— y
`source_provenance` no estaba en la lista. El dato vivía en memoria durante la
corrida y se perdía al guardar: la API devolvía `None`, el snapshot congelado
también, y recuperar la pose exacta de una piscina era imposible a los cinco
minutos de haberla calculado.

Es el mismo patrón que ENS-02 —preservar un campo tras agruparlo y perderlo en
el siguiente salto— y sólo se ve probando el salto completo: agrupar, guardar,
volver a leer. Las pruebas del agrupador estaban verdes.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.database import _json_deserializer, _json_serializer
from core.models import (
    Base,
    DockingPose,
    DockingResult,
    EvaluationResultRead,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)
from db.repository import Repository

PROCEDENCIA = {
    "rank": 4,
    "poses_file_path": "runs/docking/abc__c07/7E2Y/huella/poses.sdf",
    "poses_file_sha256": "b" * 64,
    "parsing_source": "sdf",
    "conversor_estructural": None,
    "ligand_input": {
        "conformer_path": "ligands/abc__c07/conformer.sdf",
        "conformer_sha256": "c" * 64,
        "semilla_conformacional": 1001,
    },
}


@pytest_asyncio.fixture
async def sesiones(tmp_path):
    motor = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'procedencia.db'}",
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )
    async with motor.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    await motor.dispose()


async def _molecula(sesion) -> MoleculeORM:
    usuario = UserORM(
        email=f"{uuid.uuid4().hex}@local",
        username=uuid.uuid4().hex[:12],
        hashed_password="x",
    )
    diana = TargetORM(
        pdb_id=uuid.uuid4().hex[:4].upper(), name="prueba", chain="A",
        grid_center_x=1.0, grid_center_y=2.0, grid_center_z=3.0,
    )
    sesion.add_all([usuario, diana])
    await sesion.flush()
    molecula = MoleculeORM(
        smiles="CCO", smiles_hash=uuid.uuid4().hex, user_id=usuario.id,
        target_id=diana.id, status=MoleculeStatus.PENDING,
    )
    sesion.add(molecula)
    await sesion.flush()
    return molecula


def _resultado() -> DockingResult:
    return DockingResult(
        best_affinity=-9.3,
        poses=[
            DockingPose(
                rank=1, affinity=-9.3, rmsd_lb=0.0, rmsd_ub=0.0,
                pdbqt_block="ROOT\nENDROOT\n", conformer_index=7,
                source_provenance=PROCEDENCIA,
            ),
            DockingPose(rank=2, affinity=-8.1, rmsd_lb=1.0, rmsd_ub=2.0),
        ],
        poses_file_path=None,
        parsing_source="mixed",
    )


@pytest.mark.asyncio
async def test_la_procedencia_por_pose_sobrevive_al_guardado(sesiones):
    """Guardar y volver a leer: el dato tiene que seguir ahí."""
    async with sesiones() as sesion:
        molecula = await _molecula(sesion)
        repositorio = Repository(sesion)
        await repositorio.upsert_evaluation_result(
            molecule_id=molecula.id, docking=_resultado()
        )
        await sesion.commit()
        molecula_id = molecula.id

    async with sesiones() as sesion:
        leido = await Repository(sesion).get_evaluation_result(molecula_id)

    assert leido is not None
    primera = leido.docking_poses[0]
    assert primera["source_provenance"] == PROCEDENCIA, (
        "la procedencia por pose no llegó a la base de datos: el agrupador la "
        "conserva y el guardado la tira, así que el contrato no existe fuera "
        "de la memoria del proceso"
    )
    assert primera["conformer_index"] == 7
    # Una pose sin procedencia se guarda como ausente, no como un dict vacío.
    assert leido.docking_poses[1]["source_provenance"] is None


@pytest.mark.asyncio
async def test_el_contrato_de_lectura_devuelve_la_procedencia(sesiones):
    """
    El salto que de verdad importa: lo que ve un cliente de la API.

    `EvaluationResultRead` valida `docking_poses` contra `DockingPose`. Si la
    clave no está en el JSON guardado, Pydantic la rellena con `None` sin
    protestar: el cliente lee «esta pose no tiene procedencia» cuando la tenía.
    """
    async with sesiones() as sesion:
        molecula = await _molecula(sesion)
        await Repository(sesion).upsert_evaluation_result(
            molecule_id=molecula.id, docking=_resultado()
        )
        await sesion.commit()
        molecula_id = molecula.id

    async with sesiones() as sesion:
        leido = await Repository(sesion).get_evaluation_result(molecula_id)
        contrato = EvaluationResultRead.model_validate(leido, from_attributes=True)

    assert contrato.docking_poses[0].source_provenance == PROCEDENCIA
    assert contrato.docking_poses[0].conformer_index == 7
    assert contrato.docking_poses[1].source_provenance is None


@pytest.mark.asyncio
async def test_la_pose_persistida_se_puede_recuperar_y_verificar(sesiones, monkeypatch,
                                                                tmp_path):
    """
    De punta a punta: guardar una pose de piscina y recuperar su registro exacto.

    Es la prueba de que las dos correcciones se sostienen JUNTAS. Con la
    procedencia perdida al guardar, la recuperación verificada de ENS-04 sería
    código muerto: no habría de dónde leer el rank ni el hash.
    """
    import hashlib

    import utils.local_storage as ls
    from services.docking.pose_recovery import recuperar_pose_agrupada

    monkeypatch.setattr(ls.settings, "local_data_dir", str(tmp_path / "data"))

    def sdf(z: float, nombre: str) -> str:
        return (
            f"{nombre}\n     RDKit          3D\n\n"
            "  1  0  0  0  0  0  0  0  0  0999 V2000\n"
            f"    1.0000    2.0000{z:10.4f} C   0  0  0  0  0  0  0  0  0  0  0  0\n"
            "M  END\n$$$$\n"
        )

    archivo = "runs/docking/abc__c07/7E2Y/h/poses.sdf"
    conformero = "ligands/abc__c07/conformer.sdf"
    contenido = sdf(1.0, "otra") + sdf(3.5, "la_nuestra")
    entrada = sdf(9.0, "conformero")
    await ls.write_text(archivo, contenido)
    await ls.write_text(conformero, entrada)

    pose = DockingPose(
        rank=1, affinity=-9.3, rmsd_lb=0.0, rmsd_ub=0.0, conformer_index=7,
        pdbqt_block=(
            "ROOT\n"
            "ATOM      1  C   UNL     1       1.000   2.000   3.500  "
            "0.00  0.00    +0.000 C \n"
            "ENDROOT\n"
        ),
        source_provenance={
            "rank": 2,
            "poses_file_path": archivo,
            "poses_file_sha256": hashlib.sha256(contenido.encode("utf-8")).hexdigest(),
            "parsing_source": "sdf",
            "conversor_estructural": None,
            "ligand_input": {
                "conformer_path": conformero,
                "conformer_sha256": hashlib.sha256(entrada.encode("utf-8")).hexdigest(),
                "semilla_conformacional": 1001,
            },
        },
    )

    async with sesiones() as sesion:
        molecula = await _molecula(sesion)
        await Repository(sesion).upsert_evaluation_result(
            molecule_id=molecula.id,
            docking=DockingResult(
                best_affinity=-9.3, poses=[pose],
                poses_file_path=None, parsing_source="mixed",
            ),
        )
        await sesion.commit()
        molecula_id = molecula.id

    async with sesiones() as sesion:
        leido = await Repository(sesion).get_evaluation_result(molecula_id)
        contrato = EvaluationResultRead.model_validate(leido, from_attributes=True)

    recuperada = await recuperar_pose_agrupada(contrato.docking_poses[0])
    assert recuperada.rank_original == 2
    assert "la_nuestra" in recuperada.sdf_record
    assert "otra" not in recuperada.sdf_record
