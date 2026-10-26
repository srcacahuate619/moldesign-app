"""
El preflight del receptor privado: el propietario pasa, el resto ni lo ve (SOL-01).

La auditoría DevOps SOL (2026-09-30) lo midió en vivo: el backend protege
correctamente el target privado — la misma petición con el token del
propietario devuelve 200 con origen «privado», sin token devuelve 404 — pero
los clientes del frontend salían sin credenciales, así que el dueño recibía
un 404 de SU propio receptor desde la interfaz y el flujo quedaba
bloqueado pese a que la API lo autorizaba.

Esta suite fija el lado del BACKEND: la regla de acceso real
(`services/targets/access`) cableada al endpoint, y el origen «privado» en
el informe. El lado del cliente — que `requestPreflight` y `getTargetPdb`
envíen la sesión — lo fija
`frontend/lib/__tests__/authDeTargetsPrivados.test.ts`.

El ocultamiento es deliberado: para el ajeno y el anónimo el privado no
existe (404 idéntico al de un PDB desconocido), porque distinguir «existe
pero no es tuyo» revelaría qué receptores privados hay.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from tests.conftest import rdkit_available

OWNER_ID = uuid.uuid4()
AJENO_ID = uuid.uuid4()
PDB_ID = "USR_TEST"


def _target_privado() -> SimpleNamespace:
    """Fila de target privado con la forma que el endpoint lee del ORM.

    Sólo los atributos que `evaluation_preflight` y `estado_de_calibracion`
    consultan; el resto del preflight no depende del target (el receptor no
    está en disco y eso genera bloqueantes honestos, no errores).
    """
    return SimpleNamespace(
        id=uuid.uuid4(),
        pdb_id=PDB_ID,
        chain="A",
        is_private=True,
        is_community=False,
        creator_id=OWNER_ID,
        grid_center_x=None,
        grid_center_y=None,
        grid_center_z=None,
        grid_size_x=None,
        grid_size_y=None,
        grid_size_z=None,
        hotspots=None,
        cofactors_whitelist=None,
        site_chains=None,
        site_ligand=None,
        # SC-9: la calibración se lee del target vivo (todo por getattr).
        spearman_rho=None,
        structural_family=None,
        is_prepared=False,
    )


class _Repositorio:
    """El catálogo del test: sólo existe USR_TEST, creado por OWNER_ID."""

    def __init__(self, _db) -> None:
        pass

    async def get_target_by_pdb_id(self, pdb_id: str) -> SimpleNamespace | None:
        if str(pdb_id).strip().upper() == PDB_ID:
            return _target_privado()
        return None


def _usuario(user_id: uuid.UUID) -> SimpleNamespace:
    return SimpleNamespace(id=user_id)


async def _comprobar(current_user: SimpleNamespace | None) -> dict:
    from api.routers import evaluation

    return await evaluation.evaluation_preflight(
        data=evaluation.PreflightRequest(
            smiles="CC(=O)Oc1ccccc1C(=O)O", target_pdb_id=PDB_ID
        ),
        db=object(),
        current_user=current_user,
    )


# ── El propietario pasa ──────────────────────────────────────────────


@pytest.mark.asyncio
@rdkit_available
async def test_el_propietario_comprueba_su_receptor_privado(monkeypatch):
    """Con la sesión del creador, el informe existe y declara origen privado."""
    from api.routers import evaluation

    monkeypatch.setattr(evaluation, "Repository", _Repositorio)

    report = await _comprobar(_usuario(OWNER_ID))

    assert report["receptor"]["origin"] == "privado"
    assert report["receptor"]["pdb_id"] == PDB_ID
    # El informe se genera completo: es una comprobación, no un 404 del flujo.
    assert report["effective_config"]["docking_engine"] == "vina"
    assert "LIGANDO_SMILES_VALIDO" not in report["technical_blockers"]


# ── El resto no ve que existe ────────────────────────────────────────


@pytest.mark.asyncio
@rdkit_available
async def test_sin_sesion_el_receptor_privado_no_existe(monkeypatch):
    """Anónimo: 404, igual que un PDB desconocido. La API no revela la fila."""
    from api.routers import evaluation

    monkeypatch.setattr(evaluation, "Repository", _Repositorio)

    with pytest.raises(HTTPException) as error:
        await _comprobar(None)

    assert error.value.status_code == 404


@pytest.mark.asyncio
@rdkit_available
async def test_un_usuario_ajeno_ve_lo_mismo_que_un_desconocido(monkeypatch):
    """Ajeno autenticado: el MISMO 404 que el anónimo.

    Distinguir «existe pero no es tuyo» entregaría el inventario de
    receptores privados de otras cuentas; el 404 uniforme es el
    ocultamiento que `require_target_object_access` promete.
    """
    from api.routers import evaluation

    monkeypatch.setattr(evaluation, "Repository", _Repositorio)

    with pytest.raises(HTTPException) as error:
        await _comprobar(_usuario(AJENO_ID))

    assert error.value.status_code == 404
