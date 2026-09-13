"""
Tests para la matriz de regresión de auditoría (sección 6) — fila
"Carga de target curado y auto-ingestado" (catálogo curado + auto-ingestión).

Dos contratos reales del arranque DESKTOP (backend/api/main.py):

(a) Integridad del catálogo `curated_targets.json` (repo raíz): JSON válido,
    ≥300 entradas y claves requeridas presentes — test sin base de datos.

(b) Auto-ingestión con la función REAL del arranque
    `_auto_seed_curated_targets_if_empty()` contra un SQLite temporal vacío.
    Se usa `core.database.set_engine()` (helper oficial de tests, ver
    test_sqlite_roundtrip.py) para redirigir la sesión del arranque a la DB
    temporal — mismo Repository, mismos serializers JSON del engine de
    producción, misma normalización de hotspots. Después del seed, una query
    independiente debe encontrar ≥300 TargetORM con hotspots como lista cruda
    o None (NUNCA el string literal "null"/"[]" ni doble-serializado).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.database import _json_deserializer, _json_serializer
from core.models import Base, TargetORM

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = REPO_ROOT / "curated_targets.json"

REQUIRED_KEYS = (
    "pdb_id",
    "chain",
    "grid_center_x",
    "grid_center_y",
    "grid_center_z",
)


@pytest_asyncio.fixture
async def seeded_engine(tmp_path):
    """SQLite temporal vacío + auto-seed REAL (función del arranque de main.py)."""
    import core.database as db_mod

    eng = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}",
        json_serializer=_json_serializer,
        json_deserializer=_json_deserializer,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from api.main import _auto_seed_curated_targets_if_empty

    # Redirige el session factory del arranque a la DB temporal (mismo patrón
    # que test_sqlite_roundtrip.py usa para create_all_tables()).
    await db_mod.reset_engine()
    db_mod.set_engine(eng)
    try:
        await _auto_seed_curated_targets_if_empty()
        yield eng
    finally:
        # Cierra el engine inyectado y deja el singleton listo para otra suite.
        await db_mod.reset_engine()


class TestCuratedCatalogIntegrity:
    """(a) El catálogo curado es JSON válido y estructuralmente completo."""

    def test_catalog_is_valid_json_with_required_keys(self):
        assert CATALOG_PATH.is_file(), (
            f"curated_targets.json no existe en {REPO_ROOT} — "
            "el auto-seed del arranque DESKTOP no tiene catálogo"
        )
        rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        assert isinstance(rows, list)
        assert len(rows) >= 300, f"solo {len(rows)} entradas en el catálogo"

        for idx, row in enumerate(rows):
            for key in REQUIRED_KEYS:
                assert row.get(key) not in (None, ""), (
                    f"entrada #{idx} ({row.get('pdb_id')}) sin clave requerida '{key}'"
                )
            assert row.get("structural_family") or row.get("organism"), (
                f"entrada #{idx} ({row.get('pdb_id')}) sin structural_family ni organism"
            )

    def test_catalog_has_unique_pdb_ids(self):
        rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        pdb_ids = [str(r["pdb_id"]).strip().upper() for r in rows]
        assert len(set(pdb_ids)) == len(pdb_ids), "pdb_id duplicados en el catálogo"

    def test_catalog_7e2y_uses_curated_receptor_chain_and_pocket(self):
        """Una instalación nueva no debe reintroducir la firma 7E2Y obsoleta."""
        rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        target = next(row for row in rows if row["pdb_id"].upper() == "7E2Y")

        assert target["chain"] == "R"
        assert (
            target["grid_center_x"],
            target["grid_center_y"],
            target["grid_center_z"],
        ) == (103.03, 114.79, 108.36)
        assert (
            target["grid_size_x"],
            target["grid_size_y"],
            target["grid_size_z"],
        ) == (25.0, 25.0, 25.0)
        assert [hotspot["name"] for hotspot in target["hotspots"]] == [
            "R:MET97", "R:ASP116", "R:VAL117", "R:SER190", "R:PHE361",
        ]

    def test_catalog_hotspots_are_lists_or_null_never_literal_string(self):
        """El catálogo fuente no puede contener el string literal 'null'/'[]'."""
        rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        for idx, row in enumerate(rows):
            hs = row.get("hotspots")
            assert hs is None or isinstance(hs, list), (
                f"entrada #{idx} ({row.get('pdb_id')}) con hotspots tipo "
                f"{type(hs).__name__}: {hs!r}"
            )
            if isinstance(hs, list):
                assert all(isinstance(h, dict) and h.get("name") for h in hs), (
                    f"entrada #{idx} ({row.get('pdb_id')}) con hotspot sin name"
                )


class TestAutoIngestionEmptySQLite:
    """(b) Auto-ingestión real sobre SQLite vacío → ≥300 targets consultables."""

    @pytest.mark.asyncio
    async def test_auto_seed_empty_sqlite_seeds_curated_targets(self, seeded_engine):
        factory = async_sessionmaker(
            seeded_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as s:
            result = await s.execute(select(TargetORM))
            targets = list(result.scalars().all())

        assert len(targets) >= 300, f"auto-seed dejó solo {len(targets)} targets"

        # Regla SC-8 / unificación JSONB: hotspots = lista cruda o None.
        # NUNCA el string literal "null"/"[]" ni doble-serializado (el bug
        # histórico que dejó ~380 targets sin hotspots utilizables).
        with_hotspots = 0
        for t in targets:
            assert t.hotspots is None or isinstance(t.hotspots, list), (
                f"target {t.pdb_id} con hotspots tipo {type(t.hotspots).__name__}: "
                f"{t.hotspots!r}"
            )
            if isinstance(t.hotspots, list) and len(t.hotspots) > 0:
                with_hotspots += 1
                assert all(isinstance(h, dict) and h.get("name") for h in t.hotspots)
        assert with_hotspots >= 300, (
            f"solo {with_hotspots} targets con hotspots válidos tras el seed"
        )

    @pytest.mark.asyncio
    async def test_auto_seeded_targets_carry_scientific_curation(self, seeded_engine):
        """La curación científica (structural_family) sobrevive la ingesta."""
        factory = async_sessionmaker(
            seeded_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as s:
            result = await s.execute(select(TargetORM))
            targets = list(result.scalars().all())

        families = {t.structural_family for t in targets if t.structural_family}
        assert len(families) >= 8, f"pocas familias curadas tras seed: {families}"

        # Catálogo curado = targets PÚBLICOS del catálogo de producción
        # (nunca is_private, a diferencia de los auto-ingestados on-demand).
        assert all(not t.is_private for t in targets), (
            "el catálogo curado debe quedar visible en producción"
        )

        target_7e2y = next(t for t in targets if t.pdb_id == "7E2Y")
        assert target_7e2y.chain == "R"
        assert target_7e2y.grid_center_x == 103.03
        assert target_7e2y.grid_size_x == 25.0

    @pytest.mark.asyncio
    async def test_auto_seed_is_idempotent(self, seeded_engine):
        """Segunda pasada del seed sobre la misma DB no duplica targets."""
        from api.main import _auto_seed_curated_targets_if_empty

        # El fixture registró seeded_engine y centraliza su reset/close al
        # terminar el test; no se toca el singleton privado aquí.
        await _auto_seed_curated_targets_if_empty()

        factory = async_sessionmaker(
            seeded_engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as s:
            count = len(list((await s.execute(select(TargetORM))).scalars().all()))

        catalog_rows = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        assert count == len(catalog_rows), (
            f"idempotencia rota: {count} targets vs {len(catalog_rows)} en catálogo"
        )
def test_preparation_provenance_is_deterministic_and_recipe_sensitive():
    from services.targets.ingestion_manager import _preparation_provenance

    base = _preparation_provenance(
        source_bytes=b"SOURCE",
        prepared_bytes=b"PREPARED",
        recipe={"chain": "A", "cofactors_whitelist": ["ZN"]},
        toolchain={"meeko": "test", "moldesign_preparation_policy": "1"},
    )
    same = _preparation_provenance(
        source_bytes=b"SOURCE",
        prepared_bytes=b"PREPARED",
        recipe={"cofactors_whitelist": ["ZN"], "chain": "A"},
        toolchain={"moldesign_preparation_policy": "1", "meeko": "test"},
    )
    changed = _preparation_provenance(
        source_bytes=b"SOURCE",
        prepared_bytes=b"PREPARED-B",
        recipe={"chain": "A", "cofactors_whitelist": []},
        toolchain={"meeko": "test", "moldesign_preparation_policy": "1"},
    )

    assert base == same
    assert base["receptor_source_sha256"] == changed["receptor_source_sha256"]
    assert base["prepared_receptor_sha256"] != changed["prepared_receptor_sha256"]
    assert base["preparation_fingerprint"] != changed["preparation_fingerprint"]
