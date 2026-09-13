"""MOLDEX-SCI-001 — un sello debe decir qué corrida certificó.

`blockchain_tx_id` vive en `evaluation_results`, la proyección **mutable** que
`upsert_evaluation_result` reescribe entera cada vez que la molécula se reevalúa.
El sello sobrevive a esa reescritura sin enterarse: la cadena queda atestiguando
un score y la ficha mostrando otro, con la misma insignia CERTIFIED.

El contrato que fija esta prueba:

1. al certificar se registra **qué corrida** se certificó y **qué score** se
   selló, no sólo la firma;
2. Moldex compara ese registro con la corrida vigente y declara si coinciden;
3. un sello anterior a este registro (`certified_task_id` nulo) se declara
   **indeterminado**, nunca coincidente. No sabemos qué corrida cubrió, y
   afirmar que coincide sería exactamente el defecto que se está corrigiendo.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from api import moldex
from api.routers import blockchain


def _resultado(**overrides):
    molecula = SimpleNamespace(
        id=uuid.uuid4(),
        name="Ligando",
        smiles="CCO",
        smiles_hash="b" * 64,
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        target=SimpleNamespace(
            pdb_id="7E2Y",
            name="5-HT1A",
            structural_family="GPCR",
            hotspots=[],
            spearman_rho=0.61,
        ),
    )
    base = dict(
        molecule=molecula,
        affinity_kcal=-8.2,
        log_p=2.1,
        molecular_weight=310.4,
        tpsa=64.2,
        total_score=91.0,
        gnn_score=71.0,
        lipinski_pass=True,
        veber_pass=True,
        scientific_warnings=[],
        hotspots_hit=[],
        blockchain_tx_id=None,
        certified_task_id=None,
        certified_total_score=None,
        task_id="corrida-1",
        receptor_sha256="c" * 64,
        receptor_path=None,
        vina_version="1.2.5",
        vina_random_seed=73,
        docking_protocol={"engine": "vina"},
        evaluated_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _RepoFalso:
    def __init__(self, resultados):
        self._resultados = resultados

    def __call__(self, _db):
        return self

    async def get_moldex_molecules(self, **_kwargs):
        return self._resultados, len(self._resultados)


async def _ficha(monkeypatch, resultado):
    monkeypatch.setattr(moldex, "Repository", _RepoFalso([resultado]))
    respuesta = await moldex.get_moldex(
        target_pdb_id=None,
        limit=None,
        offset=0,
        current_user=SimpleNamespace(id=uuid.uuid4()),
        db=object(),
    )
    return respuesta["results"][0]


# ── Lo que se registra al certificar ─────────────────────────────────────────


def test_certificar_registra_la_corrida_y_el_score_sellado():
    """La firma sola no basta: hay que poder saber qué se selló."""
    valores = blockchain._valores_del_sello(
        signature="firma-xyz",
        task_id="corrida-1",
        sealed_score=91.0,
    )

    assert valores["blockchain_tx_id"] == "firma-xyz"
    assert valores["certified_task_id"] == "corrida-1"
    assert valores["certified_total_score"] == 91.0


def test_la_unica_ruta_de_enlace_registra_el_sello():
    """Sólo /certify/link persiste sellos; /certify es una negativa explícita."""
    import inspect

    fuente = inspect.getsource(blockchain)

    # Ninguna ruta puede volver a escribir sólo la firma.
    assert fuente.count("_valores_del_sello(") == 2  # definición + /certify/link
    assert "status_code=409" in fuente
    assert ".values(blockchain_tx_id=signature)" not in fuente
    assert ".values(blockchain_tx_id=request.signature)" not in fuente


# ── Lo que Moldex declara ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_sello_intacto_se_declara_coincidente(monkeypatch):
    ficha = await _ficha(
        monkeypatch,
        _resultado(
            blockchain_tx_id="firma-xyz",
            certified_task_id="corrida-1",
            certified_total_score=91.0,
            task_id="corrida-1",
            total_score=91.0,
        ),
    )

    assert ficha["blockchain"]["certified"] is True
    assert ficha["blockchain"]["matches_current_run"] is True


@pytest.mark.asyncio
async def test_una_reevaluacion_posterior_rompe_la_coincidencia(monkeypatch):
    """El caso que motiva el hallazgo: se selló 91 y la fila ya muestra 63."""
    ficha = await _ficha(
        monkeypatch,
        _resultado(
            blockchain_tx_id="firma-xyz",
            certified_task_id="corrida-1",
            certified_total_score=91.0,
            task_id="corrida-2",
            total_score=63.0,
        ),
    )

    assert ficha["blockchain"]["certified"] is True
    assert ficha["blockchain"]["matches_current_run"] is False
    # La ficha debe poder mostrar ambas cifras sin que el lector adivine.
    assert ficha["blockchain"]["certified_total_score"] == 91.0
    assert ficha["metrics"]["score"] == 63.0


@pytest.mark.asyncio
async def test_un_sello_heredado_es_indeterminado_nunca_coincidente(monkeypatch):
    """Anterior al registro: no sabemos qué corrida cubrió, y no lo inventamos."""
    ficha = await _ficha(
        monkeypatch,
        _resultado(
            blockchain_tx_id="firma-antigua",
            certified_task_id=None,
            certified_total_score=None,
            task_id="corrida-1",
            total_score=91.0,
        ),
    )

    assert ficha["blockchain"]["certified"] is True
    assert ficha["blockchain"]["matches_current_run"] is None


@pytest.mark.asyncio
async def test_sin_sello_no_se_declara_coincidencia(monkeypatch):
    ficha = await _ficha(monkeypatch, _resultado())

    assert ficha["blockchain"]["certified"] is False
    assert ficha["blockchain"]["matches_current_run"] is None


@pytest.mark.asyncio
async def test_un_score_sellado_de_cero_real_sigue_siendo_comparable(monkeypatch):
    """MOLDEX-SCI-002: el cero medido es un valor, no un faltante."""
    ficha = await _ficha(
        monkeypatch,
        _resultado(
            blockchain_tx_id="firma-xyz",
            certified_task_id="corrida-1",
            certified_total_score=0.0,
            task_id="corrida-1",
            total_score=0.0,
        ),
    )

    assert ficha["blockchain"]["matches_current_run"] is True
    assert ficha["blockchain"]["certified_total_score"] == 0.0


# ── El esquema ───────────────────────────────────────────────────────────────


def test_las_columnas_del_sello_existen_y_son_aditivas():
    from core.models import EvaluationResultORM

    columnas = EvaluationResultORM.__table__.columns

    assert columnas["certified_task_id"].nullable is True
    assert columnas["certified_total_score"].nullable is True


def test_el_sello_de_esquema_subio():
    from core.database import SCHEMA_VERSION

    assert SCHEMA_VERSION >= 14


def test_una_base_v13_recibe_las_columnas_sin_perder_datos(tmp_path):
    """Migración v13→v14 sobre SQLite real: aditiva y no destructiva.

    Se construye a mano una `evaluation_results` como la de v13 —con un sello
    ya emitido— y se comprueba que tras migrar aparecen las dos columnas, que
    la fila anterior sigue ahí, y que su sello queda **indeterminado** en vez de
    rellenarse: no se puede saber qué corrida cubrió.
    """
    import sqlite3
    from pathlib import Path

    from core.database import _migrate_sqlite_db

    db_path = Path(tmp_path) / "v13.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE evaluation_results (
            id TEXT PRIMARY KEY,
            molecule_id TEXT,
            total_score REAL,
            task_id TEXT,
            blockchain_tx_id TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO evaluation_results VALUES (?,?,?,?,?)",
        ("row-1", "mol-1", 91.0, "corrida-1", "firma-antigua"),
    )
    conn.commit()
    conn.close()

    _migrate_sqlite_db(db_path)

    conn = sqlite3.connect(str(db_path))
    columnas = {r[1] for r in conn.execute("PRAGMA table_info(evaluation_results)")}
    assert "certified_task_id" in columnas
    assert "certified_total_score" in columnas

    fila = conn.execute(
        "SELECT total_score, blockchain_tx_id, certified_task_id, certified_total_score"
        " FROM evaluation_results WHERE id='row-1'"
    ).fetchone()
    conn.close()

    # El dato anterior sobrevive intacto.
    assert fila[0] == 91.0
    assert fila[1] == "firma-antigua"
    # Y el sello heredado queda indeterminado, no rellenado.
    assert fila[2] is None
    assert fila[3] is None
