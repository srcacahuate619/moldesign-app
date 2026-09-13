"""EVAL-BE-003 — el PDB del receptor de una corrida ajena no se entrega.

`GET /evaluation/files/protein/{molecule_id}` era el único archivo de
evaluación sin comprobación de propiedad: aplazada en su día a un corte
posterior. Con el identificador de una molécula ajena devolvía 200 y el PDB del
receptor contra el que corrió. Dos consecuencias, no una:

* **Inferencia.** El gate de Evaluación exige que una segunda cuenta no pueda
  «listar, leer, descargar, cancelar ni inferir» la corrida. Un 200 confirma
  que la molécula existe y revela contra qué proteína se ejecutó.
* **Fuga.** Si el receptor era una estructura privada subida por su dueño
  (`USR_*`), lo que se descargaba eran sus bytes.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api.routers import evaluation_files


class _Database:
    """`db.get` devuelve la fila SIN relaciones cargadas, como en producción.

    Si el endpoint leyera el receptor de esta instancia, en la aplicación real
    dispararía una carga perezosa dentro de una sesión asíncrona. El doble lo
    reproduce a propósito: el receptor sólo puede salir del repositorio.
    """

    def __init__(self, molecule):
        self.molecule = molecule

    async def get(self, _model, _molecule_id):
        return SimpleNamespace(user_id=self.molecule.user_id)


class _Repository:
    def __init__(self, *, molecule, demo_user):
        self.molecule = molecule
        self.demo_user = demo_user

    async def get_molecule(self, _molecule_id):
        return self.molecule

    async def get_or_create_test_user(self):
        return self.demo_user


def _target(pdb_id="7E2Y", *, private=False, creator_id=None):
    return SimpleNamespace(
        pdb_id=pdb_id,
        is_private=private,
        is_community=False,
        creator_id=creator_id,
    )


def _entorno(monkeypatch, *, owner_id, target):
    molecule = SimpleNamespace(user_id=owner_id, target=target)
    repository = _Repository(molecule=molecule, demo_user=SimpleNamespace(id=uuid.uuid4()))
    monkeypatch.setattr(evaluation_files, "Repository", lambda _db: repository)
    return _Database(molecule)


@pytest.mark.asyncio
async def test_otra_cuenta_no_descarga_el_receptor_de_una_corrida_ajena(monkeypatch):
    alice = uuid.uuid4()
    bob = SimpleNamespace(id=uuid.uuid4())
    db = _entorno(monkeypatch, owner_id=alice, target=_target())

    import utils.local_storage as local_storage

    async def _no_leer(_object_name):
        raise AssertionError("No debe tocarse el disco sin autorizar la molécula")

    monkeypatch.setattr(local_storage, "exists", _no_leer)
    monkeypatch.setattr(local_storage, "read_text", _no_leer)

    with pytest.raises(HTTPException) as error:
        await evaluation_files.get_protein_file(uuid.uuid4(), bob, db)

    assert error.value.status_code in (403, 404)


@pytest.mark.asyncio
async def test_el_receptor_privado_de_otra_cuenta_no_se_entrega_ni_a_su_corrida_demo(
    monkeypatch,
):
    """Receptor privado ajeno ⇒ sigue sin entregarse, y ahora se corta antes.

    La prueba nació cuando el espacio anónimo era compartido: Bob **podía**
    llegar a una molécula de ese espacio, y lo que se comprobaba es que aun así
    no se le entregaba el receptor privado de Alice. Al retirar el espacio
    compartido, Bob ya no pasa de la primera puerta: la molécula no es suya.

    Lo que la prueba vigila —que el PDB privado de otra cuenta no se lea nunca—
    no cambia; cambia en qué puerta se detiene, y eso es lo que se afirma.
    """
    alice = SimpleNamespace(id=uuid.uuid4())
    bob = SimpleNamespace(id=uuid.uuid4())
    demo_id = uuid.uuid4()
    molecule = SimpleNamespace(
        user_id=demo_id,
        target=_target("USR_ALICE", private=True, creator_id=alice.id),
    )
    repository = _Repository(molecule=molecule, demo_user=SimpleNamespace(id=demo_id))
    monkeypatch.setattr(evaluation_files, "Repository", lambda _db: repository)

    import utils.local_storage as local_storage

    async def _no_leer(_object_name):
        raise AssertionError("No debe leerse el PDB de un receptor privado ajeno")

    monkeypatch.setattr(local_storage, "exists", _no_leer)
    monkeypatch.setattr(local_storage, "read_text", _no_leer)

    with pytest.raises(HTTPException) as error:
        await evaluation_files.get_protein_file(uuid.uuid4(), bob, _Database(molecule))

    assert error.value.status_code == 403, (
        "una cuenta registrada ya no alcanza una molécula del espacio anónimo"
    )


@pytest.mark.asyncio
async def test_el_propietario_sigue_descargando_su_receptor(monkeypatch):
    alice = SimpleNamespace(id=uuid.uuid4())
    db = _entorno(monkeypatch, owner_id=alice.id, target=_target())

    import utils.local_storage as local_storage

    async def exists(object_name):
        return object_name == "targets/7E2Y/raw.pdb"

    async def read_text(object_name):
        assert object_name == "targets/7E2Y/raw.pdb"
        return "ATOM      1  N   ALA A   1\nEND\n"

    monkeypatch.setattr(local_storage, "exists", exists)
    monkeypatch.setattr(local_storage, "read_text", read_text)

    response = await evaluation_files.get_protein_file(uuid.uuid4(), alice, db)

    assert response.status_code == 200
    assert response.media_type == "chemical/x-pdb"
    assert response.body.startswith(b"ATOM")


@pytest.mark.asyncio
async def test_sin_receptor_resoluble_no_se_sale_a_la_red(monkeypatch):
    """Una corrida sin target asociado responde 404, no descarga nada."""
    alice = SimpleNamespace(id=uuid.uuid4())
    db = _entorno(monkeypatch, owner_id=alice.id, target=None)

    import utils.file_handlers as file_handlers

    async def _no_red(_pdb_id):
        raise AssertionError("No debe descargarse nada de RCSB")

    monkeypatch.setattr(file_handlers, "download_pdb_from_rcsb", _no_red, raising=False)

    with pytest.raises(HTTPException) as error:
        await evaluation_files.get_protein_file(uuid.uuid4(), alice, db)

    assert error.value.status_code == 404
