"""Contrato del lifecycle SQLite para que las suites no hereden la DB desktop."""
from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

import core.database as db_mod


@pytest.mark.asyncio
async def test_reset_engine_disposes_injected_engine_and_clears_singletons(tmp_path):
    await db_mod.reset_engine()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'isolated.db'}")
    db_mod.set_engine(engine)

    assert db_mod.get_engine() is engine
    assert db_mod.get_session_factory().kw["bind"] is engine

    await db_mod.reset_engine()

    assert db_mod._engine is None
    assert db_mod._session_factory is None


def test_test_mode_rejects_persistent_desktop_database(monkeypatch):
    monkeypatch.setenv("MOLDESIGN_TESTING", "1")
    monkeypatch.setattr(
        db_mod,
        "get_settings",
        lambda: SimpleNamespace(
            local_data_dir=str(Path.home() / "MolDesign" / "data"),
            db_echo_sql=False,
        ),
    )

    with pytest.raises(RuntimeError, match="persistent desktop database"):
        db_mod._create_engine()


def test_schema_v3_backfills_legacy_dispatcher_task_id(tmp_path):
    """Una DB v2 conserva los jobs al migrar al nombre local ``task_id``."""
    db_path = tmp_path / "legacy-v2.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE evaluation_results (id TEXT, celery_task_id TEXT)"
        )
        conn.execute(
            "INSERT INTO evaluation_results (id, celery_task_id) VALUES (?, ?)",
            ("result-1", "desktop-job-1"),
        )

    db_mod._migrate_sqlite_db(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT task_id, celery_task_id FROM evaluation_results WHERE id = ?",
            ("result-1",),
        ).fetchone()

    assert row == ("desktop-job-1", "desktop-job-1")


def test_schema_v12_adds_terminal_state_and_backfills_old_run_snapshots(tmp_path):
    """Los snapshots v11 eran éxitos; v12 los conserva sin estado ambiguo."""
    db_path = tmp_path / "legacy-v11.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE evaluation_runs ("
            "id TEXT, task_id TEXT, molecule_id TEXT, "
            "projected_result_id TEXT, snapshot_json TEXT, created_at TEXT)"
        )
        conn.execute(
            "INSERT INTO evaluation_runs "
            "(id, task_id, molecule_id, projected_result_id, snapshot_json) "
            "VALUES (?, ?, ?, ?, ?)",
            ("run-1", "task-1", "mol-1", "result-1", "{}"),
        )

    db_mod._migrate_sqlite_db(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(evaluation_runs)")
        }
        terminal = conn.execute(
            "SELECT status, error_message FROM evaluation_runs WHERE id = ?",
            ("run-1",),
        ).fetchone()

    assert {"status", "error_message"}.issubset(columns)
    assert terminal == ("SUCCESS", None)


def test_schema_v13_adds_versioned_preparation_metadata_to_targets(tmp_path):
    db_path = tmp_path / "legacy-v12-targets.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE targets (id TEXT, pdb_id TEXT)")

    db_mod._migrate_sqlite_db(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(targets)")}

    assert {
        "preparation_parent_id",
        "receptor_source_sha256",
        "prepared_receptor_sha256",
        "preparation_fingerprint",
        "preparation_recipe",
        "preparation_toolchain",
    }.issubset(columns)


def _create_legacy_target_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE targets ("
        "id TEXT, pdb_id TEXT, chain TEXT, "
        "grid_center_x REAL, grid_center_y REAL, grid_center_z REAL, "
        "grid_size_x REAL, grid_size_y REAL, grid_size_z REAL, hotspots TEXT)"
    )


def test_known_7e2y_legacy_signature_is_repaired(tmp_path):
    db_path = tmp_path / "legacy-7e2y.db"
    with sqlite3.connect(db_path) as conn:
        _create_legacy_target_table(conn)
        conn.execute(
            "INSERT INTO targets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("t1", "7E2Y", "A", 84.25, 106.49, 89.97, 45.0, 45.0, 45.0, "[]"),
        )

    db_mod._migrate_sqlite_db(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT chain, grid_center_x, grid_center_y, grid_center_z, "
            "grid_size_x, hotspots FROM targets WHERE pdb_id = '7E2Y'"
        ).fetchone()

    assert row[:5] == ("R", 103.03, 114.79, 108.36, 25.0)
    assert [item["name"] for item in json.loads(row[5])] == [
        "R:MET97", "R:ASP116", "R:VAL117", "R:SER190", "R:PHE361",
    ]


def test_7e2y_user_configuration_is_not_overwritten(tmp_path):
    db_path = tmp_path / "custom-7e2y.db"
    with sqlite3.connect(db_path) as conn:
        _create_legacy_target_table(conn)
        conn.execute(
            "INSERT INTO targets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("t1", "7E2Y", "A", 1.0, 2.0, 3.0, 20.0, 20.0, 20.0, "[]"),
        )

    db_mod._migrate_sqlite_db(db_path)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT chain, grid_center_x, grid_center_y, grid_center_z FROM targets"
        ).fetchone()

    assert row == ("A", 1.0, 2.0, 3.0)


def test_corrupt_sqlite_migration_fails_closed_without_replacing_the_file(tmp_path):
    db_path = tmp_path / "corrupt.db"
    original = b"this is not sqlite"
    db_path.write_bytes(original)

    with pytest.raises(RuntimeError, match="no se actualizará"):
        db_mod._migrate_sqlite_db(db_path)

    assert db_path.read_bytes() == original


@pytest.mark.asyncio
async def test_startup_never_stamps_schema_after_a_failed_migration(tmp_path, monkeypatch):
    db_path = tmp_path / "moldesign_local.db"
    db_path.touch()
    monkeypatch.setattr(
        db_mod,
        "get_settings",
        lambda: SimpleNamespace(local_data_dir=str(tmp_path), db_echo_sql=False),
    )
    monkeypatch.setattr(
        db_mod,
        "_migrate_sqlite_db",
        lambda _path: (_ for _ in ()).throw(RuntimeError("migration failed")),
    )
    engine_requested = False

    def _unexpected_engine():
        nonlocal engine_requested
        engine_requested = True
        raise AssertionError("no debe abrir el engine después de fallar la migración")

    monkeypatch.setattr(db_mod, "get_engine", _unexpected_engine)

    with pytest.raises(RuntimeError, match="migration failed"):
        await db_mod.create_all_tables()

    assert engine_requested is False
