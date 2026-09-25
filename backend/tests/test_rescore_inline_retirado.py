"""La API de escritorio no publica el endpoint inline que fabricaba scores."""
from fastapi.testclient import TestClient
from api.main import app


def test_rescore_inline_retirado_del_contrato():
    assert "/rescore" not in app.openapi()["paths"]
    client = TestClient(app)
    response = client.post("/rescore", json={"poses": [{"pdbqt_block": "ATOM"}], "target_pdb_path": "C:/arbitrario.pdb", "smiles": "CCO"})
    assert response.status_code == 404
    assert "score_a" not in response.json()
