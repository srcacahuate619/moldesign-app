"""
Tests de round-trip SQLite para el hallazgo de auditoría F-04.

F-04: models.py importaba tipos de PostgreSQL (JSONB/UUID de
sqlalchemy.dialects.postgresql) y database.py compensaba con un @compiles
JSONB→TEXT. Tras F-04:

- UUID: sqlalchemy.Uuid (genérico) — escribe los MISMOS bytes que antes
  en SQLite (hex de 32 chars sin guiones) y lee de vuelta uuid.UUID.
- JSON: core.models.SQLiteJSON (subclase de sqlalchemy.JSON) que compila
  a TEXT en SQLite; el engine usa _json_serializer/_json_deserializer.
- schema_meta: sello de versión del esquema (SCHEMA_VERSION en
  core/database.py), upsert en create_all_tables().

Cada test usa una DB temporal por test (tmp_path) con los MISMOS
json_serializer/json_deserializer del engine de producción — nunca toca la
DB real del desktop (~/MolDesign/data/moldesign_local.db).
"""
from __future__ import annotations

import sqlite3
import uuid
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.database import SCHEMA_VERSION, _json_deserializer, _json_serializer
from core.models import (
    Base,
    EvaluationResultORM,
    MoleculeORM,
    MoleculeStatus,
    TargetORM,
    UserORM,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def engine(tmp_path):
    """Engine async SQLite en archivo temporal, con los serializers reales."""
    eng = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'roundtrip.db'}",
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "roundtrip.db"


@pytest.fixture
def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _seed_user_target_molecule(session) -> tuple[UserORM, TargetORM, MoleculeORM]:
    """Inserta user + target + molecule (con hotspots) y retorna los ORM."""
    user = UserORM(email="u@example.com", username="user1")
    target = TargetORM(
        pdb_id="7E2Y",
        name="Target Test",
        chain="A",
        grid_center_x=1.0,
        grid_center_y=2.0,
        grid_center_z=3.0,
        hotspots=[{"name": "MET97", "importance": 0.8}, {"name": "ASP116", "importance": 1.0}],
        cofactors_whitelist=["ZN", "MG"],
    )
    session.add_all([user, target])
    await session.flush()
    molecule = MoleculeORM(
        smiles="CCO",
        user_id=user.id,
        target_id=target.id,
        smiles_hash="a" * 64,
        status=MoleculeStatus.PENDING,
    )
    session.add(molecule)
    await session.flush()
    return user, target, molecule


# ── UUID round-trip ───────────────────────────────────────────────────────────


class TestUuidRoundtrip:
    @pytest.mark.asyncio
    async def test_uuid_roundtrip_user_molecule_evaluation(
        self, engine, db_path, session_factory
    ):
        """User + Molecule + Evaluation: ids vuelven como uuid.UUID y coinciden."""
        async with session_factory() as s:
            user, target, molecule = await _seed_user_target_molecule(s)
            evaluation = EvaluationResultORM(molecule_id=molecule.id)
            s.add(evaluation)
            await s.commit()
            expected = {
                "user_id": user.id,
                "target_id": target.id,
                "molecule_id": molecule.id,
                "evaluation_id": evaluation.id,
            }

        async with session_factory() as s:
            mol = await s.get(MoleculeORM, expected["molecule_id"])
            ev = await s.get(EvaluationResultORM, expected["evaluation_id"])
            usr = await s.get(UserORM, expected["user_id"])
            tgt = await s.get(TargetORM, expected["target_id"])

        for val in (mol.id, mol.user_id, mol.target_id, ev.id, ev.molecule_id, usr.id, tgt.id):
            assert isinstance(val, uuid.UUID)
        assert mol.id == expected["molecule_id"]
        assert ev.molecule_id == expected["molecule_id"]
        assert mol.user_id == expected["user_id"]
        assert mol.target_id == expected["target_id"]

        # Bytes almacenados idénticos a los de las DB legacy (uuid.hex, TEXT).
        raw = sqlite3.connect(str(db_path))
        try:
            cur = raw.cursor()
            cur.execute("SELECT id, typeof(id) FROM users")
            stored_id, stored_type = cur.fetchone()
            assert stored_type == "text"
            assert stored_id == str(expected["user_id"].hex)
        finally:
            raw.close()

    @pytest.mark.asyncio
    async def test_uuid_ddl_declared_type_matches_legacy(self, engine, db_path):
        """Columnas UUID: CHAR(32) declarado; hotspots JSON: TEXT declarado."""
        raw = sqlite3.connect(str(db_path))
        try:
            cur = raw.cursor()
            cur.execute("PRAGMA table_info(users)")
            cols = {name: typ for (_cid, name, typ, *_rest) in cur.fetchall()}
            assert cols["id"] == "CHAR(32)"
            cur.execute("PRAGMA table_info(targets)")
            cols = {name: typ for (_cid, name, typ, *_rest) in cur.fetchall()}
            assert cols["hotspots"] == "TEXT"
            assert cols["cofactors_whitelist"] == "TEXT"
        finally:
            raw.close()


# ── JSON round-trip ───────────────────────────────────────────────────────────


class TestJsonRoundtrip:
    @pytest.mark.asyncio
    async def test_json_roundtrip_hotspots_and_lists(self, session_factory):
        """Hotspots, docking_poses y warnings vuelven como listas, NO strings."""
        hotspots = [{"name": "MET97", "importance": 0.8}, {"name": "ASP116", "importance": 1.0}]
        poses = [
            {"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -8.7, "rmsd_lb": 1.2, "rmsd_ub": 1.9},
        ]
        warnings = ["grid no validado", "seed aleatorio"]

        async with session_factory() as s:
            user, target, molecule = await _seed_user_target_molecule(s)
            target.hotspots = hotspots
            evaluation = EvaluationResultORM(
                molecule_id=molecule.id,
                docking_poses=poses,
                scientific_warnings=warnings,
                hotspots_hit=["MET97"],
            )
            s.add(evaluation)
            await s.commit()
            molecule_id = molecule.id
            target_id = target.id
            evaluation_id = evaluation.id

        async with session_factory() as s:
            mol = await s.get(MoleculeORM, molecule_id)
            tgt = await s.get(TargetORM, target_id)
            ev = await s.get(EvaluationResultORM, evaluation_id)

        # hotspots: list[dict] con floats intactos
        assert isinstance(tgt.hotspots, list)
        assert tgt.hotspots == hotspots
        assert isinstance(tgt.hotspots[0]["importance"], float)

        # docking_poses: list[dict] con floats intactos
        assert isinstance(ev.docking_poses, list)
        assert ev.docking_poses == poses

        # warnings y hotspots_hit: list[str]
        assert isinstance(ev.scientific_warnings, list)
        assert ev.scientific_warnings == warnings
        assert isinstance(ev.hotspots_hit, list)
        assert ev.hotspots_hit == ["MET97"]

        # Listas vacías: [] — nunca la string "null" ni pre-serializada
        assert isinstance(tgt.cofactors_whitelist, list)
        assert tgt.cofactors_whitelist == ["ZN", "MG"]

    @pytest.mark.asyncio
    async def test_json_null_and_empty_roundtrip_no_string_corruption(
        self, session_factory
    ):
        """None → None y [] → [] al releer (sin corrupción a string 'null')."""
        async with session_factory() as s:
            user, target, molecule = await _seed_user_target_molecule(s)
            evaluation = EvaluationResultORM(
                molecule_id=molecule.id,
                docking_poses=None,
                scientific_warnings=[],
                sa_reasons=[],
            )
            s.add(evaluation)
            await s.commit()
            evaluation_id = evaluation.id

        async with session_factory() as s:
            ev = await s.get(EvaluationResultORM, evaluation_id)

        assert ev.docking_poses is None
        assert ev.scientific_warnings == [] and isinstance(ev.scientific_warnings, list)
        assert ev.sa_reasons == [] and isinstance(ev.sa_reasons, list)

    @pytest.mark.asyncio
    async def test_evaluation_result_full_roundtrip(self, session_factory):
        """Fila completa de EvaluationResultORM (scores, XAI, ML) sobrevive."""
        shap_values = {"LogP": -0.2, "MW": 0.5}
        gnn_attention = [0.1, 0.8, 0.2]
        anti_target_results = [{"pdb_id": "3ERT", "affinity": -6.0}]

        async with session_factory() as s:
            user, target, molecule = await _seed_user_target_molecule(s)
            evaluation = EvaluationResultORM(
                molecule_id=molecule.id,
                affinity_kcal=-9.5,
                affinity_score=87.3,
                docking_poses=[{"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
                poses_file_path="docking-poses/abc.sdf",
                parsing_source="sdf",
                vina_version="1.2.5",
                vina_random_seed=42,
                scientific_warnings=["w1"],
                task_id="task-123",
                molecular_weight=180.16,
                log_p=1.4,
                tpsa=63.6,
                hbd=1,
                hba=4,
                rotatable_bonds=3,
                heavy_atom_count=13,
                ring_count=2,
                sa_score=1.9,
                sa_reasons=["tensión de anillo"],
                lipinski_pass=True,
                veber_pass=True,
                qed=0.93,
                adme_score=82.0,
                druglikeness_score=79.0,
                total_score=81.5,
                gnn_score=56.2,
                specificity_score=74.0,
                affinity_multiplier=0.9,
                specificity_multiplier=0.8,
                xgb_score=0.61,
                clgnn_score=0.44,
                quantum_score=0.3,
                ums_score=0.2,
                mmgbsa_score=-22.1,
                stacking_vina_weight=0.5,
                stacking_xgb_weight=0.3,
                stacking_gnn_weight=0.2,
                stacking_clgnn_weight=0.0,
                stacking_effective_weights={"vina": 0.71428571, "xgb": 0.0, "gnn": 0.28571429, "clgnn": 0.0},
                stacking_degraded=True,
                stacking_missing_components=["xgb"],
                target_family="gpcr",
                shap_values=shap_values,
                gnn_attention=gnn_attention,
                gnn_attention_svg="<svg/>",
                gnn_pharmacophores={"Aromaticos / Pi-Stacking": 45.0},
                ai_report="reporte",
                blockchain_tx_id="tx-1",
                blockchain_hash="b" * 64,
                selectivity_ratio=1.8,
                selectivity_verdict="selectivo",
                selectivity_ran=True,
                anti_target_results=anti_target_results,
                is_control=False,
                error_message=None,
            )
            s.add(evaluation)
            await s.commit()
            evaluation_id = evaluation.id

        async with session_factory() as s:
            ev = await s.get(EvaluationResultORM, evaluation_id)

        assert ev.affinity_kcal == -9.5
        assert ev.total_score == 81.5
        assert ev.molecular_weight == 180.16
        assert ev.hbd == 1
        assert ev.vina_random_seed == 42
        assert ev.stacking_effective_weights == {"vina": 0.71428571, "xgb": 0.0, "gnn": 0.28571429, "clgnn": 0.0}
        assert ev.stacking_degraded is True
        assert ev.stacking_missing_components == ["xgb"]
        assert ev.sa_reasons == ["tensión de anillo"] and isinstance(ev.sa_reasons, list)
        assert ev.shap_values == shap_values and isinstance(ev.shap_values, dict)
        assert ev.gnn_attention == gnn_attention and isinstance(ev.gnn_attention, list)
        assert ev.gnn_pharmacophores == {"Aromaticos / Pi-Stacking": 45.0}
        assert isinstance(ev.gnn_pharmacophores, dict)
        assert ev.anti_target_results == anti_target_results
        assert isinstance(ev.anti_target_results, list)
        assert ev.selectivity_ran is True
        assert ev.error_message is None
        assert ev.poses_file_path == "docking-poses/abc.sdf"


class TestPosePersistence:
    @pytest.mark.asyncio
    async def test_pose_persistence_roundtrip(self, session_factory):
        """Persistencia de poses (docking_poses + poses_file_path) sobrevive."""
        poses = [
            {"rank": 1, "affinity": -9.5, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -8.7, "rmsd_lb": 1.2, "rmsd_ub": 1.9},
            {"rank": 3, "affinity": -8.1, "rmsd_lb": 2.0, "rmsd_ub": 3.1},
        ]
        async with session_factory() as s:
            user, target, molecule = await _seed_user_target_molecule(s)
            evaluation = EvaluationResultORM(
                molecule_id=molecule.id,
                docking_poses=poses,
                poses_file_path="docking-poses/molecule.sdf",
                parsing_source="sdf",
                vina_version="1.2.5",
                vina_random_seed=7,
            )
            s.add(evaluation)
            await s.commit()
            evaluation_id = evaluation.id

        async with session_factory() as s:
            ev = await s.get(EvaluationResultORM, evaluation_id)

        assert isinstance(ev.docking_poses, list)
        assert ev.docking_poses == poses
        assert all(isinstance(p, dict) for p in ev.docking_poses)
        assert ev.docking_poses[0]["affinity"] == -9.5
        assert ev.poses_file_path == "docking-poses/molecule.sdf"
        assert ev.parsing_source == "sdf"
        assert ev.vina_version == "1.2.5"
        assert ev.vina_random_seed == 7


# ── DB nueva vs existente (create_all idempotente) ────────────────────────────


class TestIdempotentCreateAll:
    @pytest.mark.asyncio
    async def test_create_all_twice_no_error_and_data_survives(
        self, session_factory, engine
    ):
        """create_all sobre un archivo con datos previos no rompe nada."""
        async with session_factory() as s:
            user, target, molecule = await _seed_user_target_molecule(s)
            await s.commit()
            molecule_id = molecule.id

        # Segunda pasada de create_all sobre el MISMO archivo (arranque real).
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as s:
            mol = await s.get(MoleculeORM, molecule_id)
        assert mol is not None
        assert mol.smiles == "CCO"
        assert mol.id == molecule_id


# ── Sello de versión del esquema ──────────────────────────────────────────────


class TestSchemaVersionStamp:
    @pytest.fixture
    def startup_engine(self, tmp_path):
        import core.database as db_mod

        class _FakeSettings:
            local_data_dir = str(tmp_path)

        eng = create_async_engine(
            f"sqlite+aiosqlite:///{tmp_path / 'startup.db'}",
            json_serializer=_json_serializer,
            json_deserializer=_json_deserializer,
        )
        return eng, db_mod, _FakeSettings()

    @pytest.mark.asyncio
    async def test_schema_version_stamped_on_startup(
        self, startup_engine, monkeypatch
    ):
        """create_all_tables() (flujo de arranque) sella SCHEMA_VERSION."""
        eng, db_mod, fake_settings = startup_engine
        monkeypatch.setattr(db_mod, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(db_mod, "get_engine", lambda: eng)
        try:
            await db_mod.create_all_tables()

            async with eng.connect() as conn:
                result = await conn.execute(
                    text("SELECT schema_version, applied_at FROM schema_meta LIMIT 1")
                )
                row = result.fetchone()

            assert row is not None
            assert row[0] == SCHEMA_VERSION
            assert row[1] is not None  # applied_at sellado
        finally:
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_existing_db_gets_stamped_only_once(self, startup_engine, monkeypatch):
        """Segunda pasada con el mismo sello: no duplica filas ni pisa datos."""
        eng, db_mod, fake_settings = startup_engine
        monkeypatch.setattr(db_mod, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(db_mod, "get_engine", lambda: eng)
        try:
            await db_mod.create_all_tables()
            await db_mod.create_all_tables()

            async with eng.connect() as conn:
                result = await conn.execute(
                    text("SELECT COUNT(*), MAX(schema_version) FROM schema_meta")
                )
                count, max_version = result.fetchone()

            assert count == 1
            assert max_version == SCHEMA_VERSION
        finally:
            await eng.dispose()

    @pytest.mark.asyncio
    async def test_older_stamp_logs_warning_and_updates(
        self, startup_engine, monkeypatch
    ):
        """DB con sello anterior: warning con delta y sello actualizado."""
        eng, db_mod, fake_settings = startup_engine
        monkeypatch.setattr(db_mod, "get_settings", lambda: fake_settings)
        monkeypatch.setattr(db_mod, "get_engine", lambda: eng)
        fake_log = MagicMock()
        monkeypatch.setattr(db_mod, "log", fake_log)
        try:
            await db_mod.create_all_tables()
            async with eng.begin() as conn:
                await conn.execute(
                    text("UPDATE schema_meta SET schema_version = schema_version - 1")
                )

            await db_mod.create_all_tables()

            assert fake_log.warning.called
            warn_args, warn_kwargs = fake_log.warning.call_args
            assert warn_kwargs.get("delta") == 1

            async with eng.connect() as conn:
                version = (
                    await conn.execute(text("SELECT schema_version FROM schema_meta LIMIT 1"))
                ).scalar()
            assert version == SCHEMA_VERSION
        finally:
            await eng.dispose()
