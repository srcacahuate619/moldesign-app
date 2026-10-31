"""Exercise the real MolDesign receiver and its declared calculation methods."""
from types import SimpleNamespace
from uuid import uuid4
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.dependencies import get_current_user
from api.routers.molchat_host import router
from chem.validator import validate_smiles
from rdkit import Chem
from rdkit.Chem import Lipinski


def test_caffeine_methods_and_smiles():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    original = 'CN1C=NC2=C1C(=O)N(C(=O)N2C)C'
    with TestClient(app) as client:
        response = client.post('/molchat-host/properties', json={'smiles': original})
    assert response.status_code == 200, response.text
    data = response.json()
    assert 'Lipinski.NOCount' in data['methods']['hba']
    assert 'Crippen.MolLogP' in data['methods']['logp']
    assert data['properties']['hba'] == Lipinski.NOCount(Chem.MolFromSmiles(original)) == 6
    assert data['canonical_smiles'] == Chem.MolToSmiles(Chem.MolFromSmiles(original))


def test_salt_processing_is_visible():
    original = 'O=C([O-])c1ccccc1.[Na+]'
    result = validate_smiles(original)
    assert result.is_valid and result.warnings
    assert Chem.MolToSmiles(Chem.MolFromSmiles(original)) != result.canonical_smiles
