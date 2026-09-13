"""MOLDEX-SCI-002 — un sello es irreversible: nunca puede llevar un cero fabricado.

Las dos rutas de certificación colapsaban un `total_score` ausente a `0.0`
(`evaluation.total_score or 0.0`). Ese cero no es una medida débil: es una medida
inexistente, y a diferencia de BATCH-SCI-001 y EVAL-SCI-012 aquí se escribe en
una cadena pública y no se puede corregir.

El contrato que fijan estas pruebas tiene dos mitades, y las dos importan:

1. un score ausente **bloquea** la certificación;
2. un score realmente medido de `0.0` **sigue siendo certificable** — el cero
   real es un valor válido del extremo inferior de la escala 0-100, y la
   corrección no puede confundirlo con el faltante.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import blockchain
from tests._fuente import codigo_ejecutable

WALLET = "11111111111111111111111111111111"


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _Database:
    """Stub mínimo: `execute` devuelve la molécula, `scalar` la evaluación."""

    def __init__(self, molecule, evaluation):
        self.molecule = molecule
        self.evaluation = evaluation

    async def execute(self, _statement):
        return _Result(self.molecule)

    async def scalar(self, _statement):
        return self.evaluation


def _molecula(owner_id: uuid.UUID):
    return SimpleNamespace(
        id=uuid.uuid4(),
        user_id=owner_id,
        smiles_hash="a" * 64,
        target=SimpleNamespace(pdb_id="7E2Y"),
        is_saved=False,
    )


def _evaluacion(total_score):
    return SimpleNamespace(
        total_score=total_score,
        blockchain_tx_id=None,
        affinity_kcal=-7.4,
    )


async def _preparar(total_score):
    owner = SimpleNamespace(id=uuid.uuid4(), email="quien@example.org")
    mol = _molecula(owner.id)
    db = _Database(mol, _evaluacion(total_score))
    return await blockchain.prepare_certification(
        molecule_id=mol.id,
        user_wallet=WALLET,
        current_user=owner,
        db=db,
    )


# ── Ruta wallet: GET /blockchain/certify/{id}/prepare ────────────────────────


@pytest.mark.asyncio
async def test_prepare_rechaza_un_score_ausente_en_vez_de_sellar_cero():
    """Un score ausente no puede convertirse en `|0.00|` dentro del memo."""
    with pytest.raises(HTTPException) as excinfo:
        await _preparar(None)

    assert excinfo.value.status_code == 400
    assert "0.00" not in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_prepare_conserva_el_cero_realmente_medido():
    """El cero real es una medida válida de la escala 0-100 y sigue sellándose."""
    respuesta = await _preparar(0.0)

    assert respuesta["already_certified"] is False
    assert "|0.00|" in respuesta["memo"]


@pytest.mark.asyncio
async def test_prepare_sella_un_score_normal_sin_alterarlo():
    respuesta = await _preparar(91.5)

    assert "|91.50|" in respuesta["memo"]


# ── Ruta institucional: POST /blockchain/certify ─────────────────────────────


def test_el_score_sellable_bloquea_el_faltante_y_deja_pasar_el_cero_real():
    """El helper que ambas rutas comparten distingue faltante de cero medido."""
    sellable = blockchain._score_sellable

    with pytest.raises(HTTPException) as excinfo:
        sellable(_evaluacion(None))
    assert excinfo.value.status_code == 400

    assert sellable(_evaluacion(0.0)) == 0.0
    assert sellable(_evaluacion(91.5)) == 91.5


def test_ninguna_ruta_construye_el_registro_con_or_cero():
    """El laundering `or 0.0` derrotaba la validación del propio esquema.

    `BlockchainRecord.total_score` es `float = Field(..., ge=0, le=100)`: un
    `None` habría sido rechazado por Pydantic. El idiom prohibido lo convertía
    en un cero válido antes de que el esquema pudiera verlo. Si vuelve al
    router, esta prueba lo detecta.
    """
    codigo = codigo_ejecutable(blockchain)

    assert "total_score or 0.0" not in codigo


def test_el_registro_rechaza_un_score_nulo_cuando_no_se_lava():
    """Sin el `or 0.0`, el esquema es la segunda línea de defensa."""
    from core.models import BlockchainRecord

    with pytest.raises(Exception):
        BlockchainRecord(
            smiles_hash="a" * 64,
            total_score=None,
            target_pdb_id="7E2Y",
            user_wallet=WALLET,
            timestamp=datetime.utcnow(),
        )
