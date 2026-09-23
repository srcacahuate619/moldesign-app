"""MOLDEX-INT-007 — el catálogo debe decir de qué corrida salió cada número.

El gate de Moldex exige que «cada valor mostrado y exportado conserve origen,
unidad y corrida» (§7 del plan 61). `GET /moldex` emitía métricas desnudas: sin
`task_id`, sin `receptor_sha256`, sin versión de motor, sin semilla y sin
protocolo. Por eso ni MOLDEX-SCI-001 (sello anclado a una fila que se sobrescribe)
ni MOLDEX-SCI-004 (comparar cosas incompatibles) eran detectables en el cliente:
la información no llegaba.

Todos estos campos ya viven en `EvaluationResultORM`, la fila que el catálogo ya
carga. No hace falta join, migración ni consulta adicional.

`receptor_path` se omite deliberadamente: es una ruta local del usuario y
EVAL-INT-008 ya fijó que no se renderiza. Lo que Moldex necesita para decidir
compatibilidad es el hash, no la ruta.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from api import moldex

PROTOCOLO = {
    "engine": "vina",
    "exhaustiveness": 8,
    "num_poses": 9,
    "conformers_requested": 1,
    "conformers_generated": 1,
}


def _resultado(**overrides):
    """Una fila de evaluación con procedencia completa."""
    molecula = SimpleNamespace(
        id=uuid.uuid4(),
        name="Ligando de prueba",
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
        total_score=88.0,
        gnn_score=71.0,
        clgnn_score=0.74,
        lipinski_pass=True,
        veber_pass=True,
        scientific_warnings=[],
        hotspots_hit=[],
        blockchain_tx_id=None,
        task_id="task-abc-123",
        receptor_sha256="c" * 64,
        receptor_path=r"C:\Users\privado\receptores\7E2Y.pdbqt",
        vina_version="1.2.5",
        vina_random_seed=73,
        docking_protocol=dict(PROTOCOLO),
        evaluated_at=datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc),
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


async def _catalogo(monkeypatch, resultados):
    monkeypatch.setattr(moldex, "Repository", _RepoFalso(resultados))
    usuario = SimpleNamespace(id=uuid.uuid4())
    respuesta = await moldex.get_moldex(
        target_pdb_id=None,
        limit=None,
        offset=0,
        current_user=usuario,
        db=object(),
    )
    return respuesta["results"]


@pytest.mark.asyncio
async def test_la_ficha_declara_la_corrida_que_la_produjo(monkeypatch):
    (ficha,) = await _catalogo(monkeypatch, [_resultado()])

    procedencia = ficha["provenance"]

    assert procedencia["task_id"] == "task-abc-123"
    assert procedencia["receptor_sha256"] == "c" * 64
    assert procedencia["engine_version"] == "1.2.5"
    assert procedencia["random_seed"] == 73
    assert procedencia["docking_protocol"] == PROTOCOLO


@pytest.mark.asyncio
async def test_avisos_mixtos_cumplen_el_contrato_http(monkeypatch):
    """El endpoint solo publica mensajes, incluso con corridas heredadas."""
    fichas = await _catalogo(
        monkeypatch,
        [
            _resultado(
                scientific_warnings=[
                    {
                        "codigo": "SITIO_DESOLVATADO",
                        "severidad": "info",
                        "mensaje": "Se retiraron aguas cristalográficas.",
                    },
                    "Aviso heredado de una corrida anterior.",
                ]
            )
        ],
    )

    respuesta = moldex.MoldexCatalogRead.model_validate(
        {
            "count": len(fichas),
            "total": len(fichas),
            "limit": None,
            "offset": 0,
            "has_next": False,
            "results": fichas,
        }
    )

    assert respuesta.results[0].scientific_warnings == [
        "Se retiraron aguas cristalográficas.",
        "Aviso heredado de una corrida anterior.",
    ]


@pytest.mark.asyncio
async def test_la_ficha_declara_cuando_fue_evaluada(monkeypatch):
    """El orden «RECIENTES» del cliente leía `evaluated_at` y nunca llegaba."""
    (ficha,) = await _catalogo(monkeypatch, [_resultado()])

    assert ficha["evaluated_at"] == "2026-08-30T12:00:00+00:00"
    # `created_at` es la fecha de la molécula y no debe confundirse con ella.
    assert ficha["created_at"] == "2026-08-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_una_corrida_heredada_declara_procedencia_ausente_sin_inventarla(
    monkeypatch,
):
    """Lo anterior al registro de procedencia viaja como `null`, nunca como 0 ni ''."""
    heredada = _resultado(
        task_id=None,
        receptor_sha256=None,
        vina_version=None,
        vina_random_seed=None,
        docking_protocol=None,
        evaluated_at=None,
    )

    (ficha,) = await _catalogo(monkeypatch, [heredada])

    procedencia = ficha["provenance"]

    assert procedencia["task_id"] is None
    assert procedencia["receptor_sha256"] is None
    assert procedencia["engine_version"] is None
    assert procedencia["random_seed"] is None
    assert procedencia["docking_protocol"] is None
    assert ficha["evaluated_at"] is None


@pytest.mark.asyncio
async def test_el_catalogo_nunca_publica_la_ruta_local_del_receptor(monkeypatch):
    """EVAL-INT-008: el hash se publica, la ruta privada del usuario no."""
    import json

    fichas = await _catalogo(monkeypatch, [_resultado()])

    serializado = json.dumps(fichas)

    assert "privado" not in serializado
    assert "receptor_path" not in serializado
    assert r"C:\\Users" not in serializado
