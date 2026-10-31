"""Contrato público del host: versión y descriptores calculados por MolDesign."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.dependencies import get_current_user
from api.routers.molchat_host import router


@pytest.fixture
def cliente():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    with TestClient(app) as client:
        yield client


def test_contrato_declara_version_y_capacidad_real(cliente):
    r = cliente.get('/molchat-host/contract')
    assert r.status_code == 200
    assert r.json()['contract'] == 'moldesign.molchat/1'
    assert 'properties/1' in r.json()['capabilities']
    assert 'platform-actions/1' in r.json()['capabilities']


def test_propiedades_reales_fuera_de_las_fixtures(cliente):
    from chem.properties import calculate_properties
    smiles = 'CCOC(=O)c1ccccc1'
    r = cliente.post('/molchat-host/properties', json={'smiles': smiles})
    assert r.status_code == 200, r.text
    body = r.json()
    referencia = calculate_properties(smiles, run_admet_ai=False)
    assert body['contract'] == 'properties/1'
    assert body['properties']['mw'] == referencia.molecular_weight
    assert body['properties']['logp'] == referencia.log_p
    assert body['canonical_smiles']
    assert 'RDKit' in body['source']


def test_invalidos_no_producen_numeros(cliente):
    r = cliente.post('/molchat-host/properties', json={'smiles': 'not a smiles'})
    assert r.status_code == 422
    assert 'properties' not in r.json()


def test_contrato_y_propiedades_exigen_identidad():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        assert c.get('/molchat-host/contract').status_code in (401, 403)
        assert c.post('/molchat-host/properties', json={'smiles': 'CCO'}).status_code in (401, 403)
