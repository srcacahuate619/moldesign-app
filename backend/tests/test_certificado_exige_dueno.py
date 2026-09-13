"""MOLDEX-BE-005 y MOLDEX-BE-015 — el certificado en PDF exige dueño.

`_generate_certificate_data` autorizaba con:

    if mol.user_id != current_user_id and mol.user_id != demo_user.id: 403

con `current_user_id = current_user.id if current_user else demo_user.id`. Dos
agujeros en una línea:

1. la segunda cláusula abría **toda** molécula del espacio demo a cualquier
   cuenta y también a un llamador **sin autenticar**;
2. el 403 confirma que el recurso existe. BATCH-BE-002 ya había elegido 404
   deliberadamente para no revelar la existencia de un cribado ajeno.

El PDF no es un dato menor: lleva SMILES, poses, receptor y metodología.

MOLDEX-BE-015 es el agravante: el usuario `demo` se creaba con la contraseña
`demo123` escrita en el código y `is_active=True`, y `/auth/login` acepta
username o email. Cualquiera que alcanzara la API entraba como demo.

El invitado real del escritorio es otra cuenta —`Desktop User`, creada por
`/auth/desktop-login` con contraseña aleatoria—, así que el demo no tiene
ningún uso legítimo como identidad con la que iniciar sesión.
"""

from __future__ import annotations

import inspect
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import blockchain
from db import repository as repository_module
from tests._fuente import codigo_con_literales


def _molecula(owner_id):
    return SimpleNamespace(id=uuid.uuid4(), user_id=owner_id, smiles_hash="a" * 64)


# ── MOLDEX-BE-005 ────────────────────────────────────────────────────────────


def test_un_llamador_sin_sesion_no_recibe_el_certificado():
    """Sin token no se resuelve a demo: se responde como si no existiera."""
    with pytest.raises(HTTPException) as error:
        blockchain._require_certificate_owner(_molecula(uuid.uuid4()), None)

    assert error.value.status_code == 404


def test_otra_cuenta_recibe_404_y_no_403():
    """El 403 confirmaba la existencia del certificado ajeno."""
    alice = SimpleNamespace(id=uuid.uuid4())
    de_bob = _molecula(uuid.uuid4())

    with pytest.raises(HTTPException) as error:
        blockchain._require_certificate_owner(de_bob, alice)

    assert error.value.status_code == 404
    assert error.value.status_code != 403


def test_una_molecula_del_espacio_demo_no_es_de_todos():
    """Conocer el id de una molécula demo ya no basta para leer su dossier."""
    alice = SimpleNamespace(id=uuid.uuid4())
    demo_id = uuid.uuid4()

    with pytest.raises(HTTPException) as error:
        blockchain._require_certificate_owner(_molecula(demo_id), alice)

    assert error.value.status_code == 404


def test_el_dueno_si_puede_leer_su_certificado():
    alice = SimpleNamespace(id=uuid.uuid4())
    suya = _molecula(alice.id)

    assert blockchain._require_certificate_owner(suya, alice) is suya


def test_el_router_no_conserva_el_atajo_al_espacio_demo():
    fuente = inspect.getsource(blockchain)

    assert "get_or_create_test_user" not in fuente
    assert "current_user.id if current_user else" not in fuente


# ── MOLDEX-BE-015 ────────────────────────────────────────────────────────────


def test_el_usuario_demo_no_lleva_una_contrasena_escrita_en_el_codigo():
    """Una credencial conocida embarcada en el producto es una puerta abierta.

    Se escanea el código **conservando los literales** —la contraseña sería
    uno— pero sin comentarios ni docstrings, para que la explicación histórica
    de por qué se retiró no cuente como reincidencia.
    """
    fuente = codigo_con_literales(repository_module)

    assert "demo123" not in fuente
    # La identidad de servicio no debe poder autenticarse por contraseña.
    assert "secrets.token_hex" in fuente
