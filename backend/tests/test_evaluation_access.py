"""Contratos de propiedad compartidos por endpoints de evaluación."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers.evaluation_access import require_owned_molecule


class _Database:
    def __init__(self, molecule):
        self.molecule = molecule

    async def get(self, _model, _molecule_id):
        return self.molecule


class _Repository:
    def __init__(self, demo_user):
        self.demo_user = demo_user

    async def get_or_create_test_user(self):
        return self.demo_user


@pytest.mark.asyncio
async def test_el_dueno_accede_a_lo_suyo():
    owner_id = uuid.uuid4()
    demo_user = SimpleNamespace(id=uuid.uuid4())
    repository = _Repository(demo_user)
    molecule = SimpleNamespace(user_id=owner_id)

    own = await require_owned_molecule(
        repository=repository,
        db=_Database(molecule),
        molecule_id=uuid.uuid4(),
        current_user=SimpleNamespace(id=owner_id),
        forbidden_detail="forbidden",
    )

    assert own is molecule


@pytest.mark.asyncio
async def test_una_cuenta_registrada_ya_no_accede_a_lo_anonimo():
    """Esta prueba estaba invertida, y por eso el agujero pasó desapercibido.

    Se llamaba `test_owner_and_demo_molecule_are_accessible` y exigía que una
    cuenta cualquiera pudiera leer una molécula del espacio anónimo. Eso era el
    «espacio demo público» que la docstring del módulo prometía: cualquier
    registrado leyendo el trabajo anónimo de cualquiera.

    TRANS-ANON-002 conserva la evaluación sin cuenta; lo que se retira es que su
    resultado sea de todos. Una molécula tiene un dueño y sólo uno.
    """
    demo_user = SimpleNamespace(id=uuid.uuid4())
    repository = _Repository(demo_user)

    with pytest.raises(HTTPException) as error:
        await require_owned_molecule(
            repository=repository,
            db=_Database(SimpleNamespace(user_id=demo_user.id)),
            molecule_id=uuid.uuid4(),
            current_user=SimpleNamespace(id=uuid.uuid4()),
            forbidden_detail="forbidden",
        )

    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_sin_sesion_se_accede_a_lo_anonimo():
    """Lo anónimo sigue siendo alcanzable por quien lo produjo, sin cuenta."""
    demo_user = SimpleNamespace(id=uuid.uuid4())
    repository = _Repository(demo_user)
    molecule = SimpleNamespace(user_id=demo_user.id)

    obtenida = await require_owned_molecule(
        repository=repository,
        db=_Database(molecule),
        molecule_id=uuid.uuid4(),
        current_user=None,
        forbidden_detail="forbidden",
    )

    assert obtenida is molecule


@pytest.mark.asyncio
async def test_private_or_missing_molecule_is_rejected_with_existing_contract():
    repository = _Repository(SimpleNamespace(id=uuid.uuid4()))

    with pytest.raises(HTTPException) as private_error:
        await require_owned_molecule(
            repository=repository,
            db=_Database(SimpleNamespace(user_id=uuid.uuid4())),
            molecule_id=uuid.uuid4(),
            current_user=SimpleNamespace(id=uuid.uuid4()),
            forbidden_detail="Sin permiso",
        )
    assert private_error.value.status_code == 403
    assert private_error.value.detail == "Sin permiso"

    with pytest.raises(HTTPException) as missing_error:
        await require_owned_molecule(
            repository=repository,
            db=_Database(None),
            molecule_id=uuid.uuid4(),
            current_user=None,
            forbidden_detail="Sin permiso",
            missing_detail="No existe molécula",
        )
    assert missing_error.value.status_code == 404
    assert missing_error.value.detail == "No existe molécula"


def test_protein_file_route_remains_under_evaluation_prefix():
    from api.routers.evaluation import router

    paths = {route.path for route in router.routes}
    assert "/evaluation/files/protein/{molecule_id}" in paths
