"""
tests/test_rescoring_app.py

Tests unitarios para los endpoints del microservicio de rescoring.
Usa TestClient de FastAPI (síncrono) para verificar health, info y rescore.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app as rescoring_app
from app import app
from fastapi.testclient import TestClient
from model_manager import ModelManager

# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def client(monkeypatch):
    """Aislar el estado global de la app de los artefactos locales reales."""
    isolated_manager = ModelManager()
    monkeypatch.setattr(rescoring_app, "model_manager", isolated_manager)
    monkeypatch.setattr(isolated_manager, "load_models", lambda: None)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ─────────────────────────────────────────────
# Tests — Health Endpoint
# ─────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests del health check."""

    def test_health_returns_200(self, client):
        """Health endpoint siempre devuelve 200."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_without_model_is_degraded(self, client):
        """Sin modelo cargado, status es 'degraded'."""
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["model_loaded"] is False
        assert data["model_version"] is None

    def test_health_has_required_fields(self, client):
        """Response tiene todos los campos requeridos."""
        resp = client.get("/health")
        data = resp.json()
        required = {"status", "model_loaded", "model_version",
                    "prolif_available", "xgboost_available", "gnn_available",
                    "manifest_valid", "manifest_errors"}
        assert required.issubset(set(data.keys()))


# ─────────────────────────────────────────────
# Tests — Info Endpoint
# ─────────────────────────────────────────────


class TestInfoEndpoint:
    """Tests del endpoint de metadata del modelo."""

    def test_info_returns_200(self, client):
        """Info siempre devuelve 200."""
        resp = client.get("/info")
        assert resp.status_code == 200

    def test_info_without_model(self, client):
        """Sin modelo, todos los campos son None/vacíos."""
        resp = client.get("/info")
        data = resp.json()
        assert data["model_version"] is None
        assert data["training_date"] is None
        assert data["families_trained"] == []


# ─────────────────────────────────────────────
# Tests — Rescore Endpoint
# ─────────────────────────────────────────────


def _make_rescore_payload() -> dict:
    """Crear payload válido para /rescore."""
    return {
        "smiles": "c1ccc2[nH]c(-c3ccncc3)cc2c1",
        "target_pdb_path": "/app/targets/7e2y_prepared.pdb",
        "poses": [
            {
                "pdbqt_block": _make_pdbqt_centered(),
                "vina_score": -8.5 + i * 0.2,
                "rmsd_lb": 0.0,
                "rmsd_ub": 0.0,
            }
            for i in range(9)
        ],
        "molecular_weight": 234.27,
        "logp": 2.8,
        "tpsa": 41.57,
        "hbd": 1,
        "hba": 3,
        "rotatable_bonds": 1,
        "qed": 0.82,
    }


def _make_pdbqt_centered() -> str:
    """PDBQT block centrado en el grid de 7E2Y."""
    cx, cy, cz = -22.228, -0.583, -29.375
    coords = [
        (cx, cy, cz),
        (cx + 1, cy, cz),
        (cx, cy + 1, cz),
        (cx, cy, cz + 1),
        (cx - 1, cy - 1, cz),
    ]
    lines = []
    for i, (x, y, z) in enumerate(coords, 1):
        line = f"ATOM  {i:5d}  C{i:<2d} LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     C"
        line = line.ljust(77) + " C"
        lines.append(line)
    lines.append("END")
    return "\n".join(lines)


class TestRescoreEndpoint:
    """Tests del endpoint de rescoring."""

    def test_rescore_without_model_returns_503(self, client):
        """Sin modelo cargado, /rescore debe devolver 503."""
        payload = _make_rescore_payload()
        resp = client.post("/rescore", json=payload)
        assert resp.status_code == 503
        assert "no cargado" in resp.json()["detail"].lower() or "artefactos" in resp.json()["detail"].lower()

    def test_rescore_validates_request_body(self, client):
        """Un body inválido debe devolver 422 (validation error)."""
        resp = client.post("/rescore", json={"smiles": "CCO"})
        assert resp.status_code == 422

    def test_rescore_empty_body_returns_422(self, client):
        """Body vacío → 422."""
        resp = client.post("/rescore", json={})
        assert resp.status_code == 422
