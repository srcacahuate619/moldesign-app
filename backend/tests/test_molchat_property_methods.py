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


CLOPIDOGREL = 'COC(=O)[C@H](c1ccccc1Cl)N1CCc2sccc2C1'


def _propiedades(smiles):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=uuid4())
    with TestClient(app) as client:
        response = client.post('/molchat-host/properties', json={'smiles': smiles})
    assert response.status_code == 200, response.text
    return response.json()


def test_tpsa_declara_que_no_cuenta_azufre_ni_fosforo_y_ofrece_la_variante_que_si():
    """PubChem publica 57,8 Å² para el clopidogrel y el producto 29,54: la diferencia es la definición, no un error.

    Lo que se protege: el producto conserva su TPSA (los umbrales de Lipinski y Veber se calibraron con ella),
    declara con exactitud qué cuenta, y ofrece la otra definición como un cálculo real para que quien compare
    pueda comprobar la explicación en lugar de suponerla.
    """
    from rdkit.Chem import rdMolDescriptors
    data = _propiedades(CLOPIDOGREL)
    mol = Chem.MolFromSmiles(data['canonical_smiles'])
    assert data['properties']['tpsa'] == round(rdMolDescriptors.CalcTPSA(mol), 2) == 29.54
    assert 'includeSandP=False' in data['methods']['tpsa'] and 'sólo N y O' in data['methods']['tpsa']
    variants = {item['name']: item for item in data['variants']}
    tpsa = variants['tpsa_incl_s_p']
    assert tpsa['applies_to'] == 'tpsa' and tpsa['unit'] == 'Å²'
    assert tpsa['value'] == round(rdMolDescriptors.CalcTPSA(mol, includeSandP=True), 2) == 57.78
    assert 'includeSandP=True' in tpsa['method']


def test_hba_del_producto_cuenta_n_y_o_y_la_variante_cuenta_aceptores_de_rdkit():
    from rdkit.Chem import rdMolDescriptors
    data = _propiedades(CLOPIDOGREL)
    mol = Chem.MolFromSmiles(data['canonical_smiles'])
    assert data['properties']['hba'] == Lipinski.NOCount(mol) == 3
    hba = {item['name']: item for item in data['variants']}['hba_rdkit_num_h_acceptors']
    assert hba['applies_to'] == 'hba' and hba['value'] == rdMolDescriptors.CalcNumHBA(mol) == 4
    assert 'no es el recuento de todos los N y O' in hba['method']


def test_las_variantes_no_sustituyen_a_las_propiedades_del_producto():
    data = _propiedades(CLOPIDOGREL)
    assert set(data['properties']) == {'mw', 'logp', 'tpsa', 'hbd', 'hba', 'rot_bonds', 'heavy_atoms', 'rings'}
    assert all(set(item) == {'name', 'applies_to', 'unit', 'value', 'method'} for item in data['variants'])


def test_sin_azufre_ni_fosforo_la_tpsa_no_cambia_con_la_variante():
    from rdkit.Chem import rdMolDescriptors
    data = _propiedades('CN1C=NC2=C1C(=O)N(C(=O)N2C)C')  # cafeína: sin S ni P
    tpsa = {item['name']: item for item in data['variants']}['tpsa_incl_s_p']
    assert tpsa['value'] == data['properties']['tpsa']
