"""
Tests de integración del backend FastAPI.

Usa TestClient de FastAPI (httpx) para ejercitar endpoints reales sin
necesitar un servidor corriendo. Mockeamos dependencias pesadas
(RDKit, Vina, ModelManager) que no necesitamos para tests de
integración de la capa API.

Validez científica: estos tests verifican que los contratos HTTP del
backend se mantienen — endpoints, códigos de estado, shape de respuesta.
Un cambio en un router que rompa un contrato puede invalidar
resultados científicos downstream.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def test_db_path(tmp_path_factory) -> Path:
    """Crea un directorio temporal para la DB SQLite de tests."""
    return tmp_path_factory.mktemp("db") / "test_moldesign.db"


@pytest.fixture(scope="module")
def client(test_db_path: Path):
    """TestClient de FastAPI con ModelManager mockeado y DB temporal.

    El lifespan de la app:
    1. Carga settings (mockeadas)
    2. Carga ModelManager (mockeado para no descargar modelos reales)
    3. Abre DB SQLite en archivo temporal

    El heartbeat anti-zombie se desactiva porque settings.environment = "testing".
    """
    # Configurar env vars ANTES de importar la app y restaurarlas al salir.
    env_values = {
        "APP_MODE": "DESKTOP",
        "ENVIRONMENT": "testing",
        "LOCAL_DATA_DIR": str(test_db_path.parent),
    }
    missing_env = object()
    previous_env = {key: os.environ.get(key, missing_env) for key in env_values}
    os.environ.update(env_values)

    # Mockear sys.modules para que el import lazy de "rescoring" en api/main.py
    # no falle cuando RDKit/modelos pesados no están instalados
    mock_rescoring = MagicMock()
    mock_model_manager = MagicMock()
    mock_model_manager.return_value.load_models = MagicMock()
    mock_model_manager.return_value.models = {}
    mock_rescoring.model_manager = MagicMock()
    mock_rescoring.model_manager.ModelManager = mock_model_manager

    settings = MagicMock()
    settings.environment = "testing"
    settings.app_mode = "DESKTOP"
    settings.strict_science_mode = True
    settings.database_url = f"sqlite:///{test_db_path}"
    settings.local_data_dir = str(test_db_path.parent)
    settings.solana_rpc_url = ""
    settings.log_level = "INFO"
    settings.db_echo_sql = False  # Para SQLAlchemy

    # No usar patch.dict(sys.modules): al salir restaura TODO el diccionario y
    # puede desregistrar extensiones nativas cargadas por TestClient (PyO3).
    missing = object()
    previous_rescoring = sys.modules.get("rescoring", missing)
    previous_model_manager = sys.modules.get("rescoring.model_manager", missing)
    sys.modules["rescoring"] = mock_rescoring
    sys.modules["rescoring.model_manager"] = mock_rescoring.model_manager
    try:
        with patch("core.config.get_settings", return_value=settings), \
             patch("api.main.get_settings", return_value=settings):
            # Importar la app DENTRO del patch.
            from api.main import app

            with TestClient(app) as c:
                yield c
    finally:
        if previous_rescoring is missing:
            sys.modules.pop("rescoring", None)
        else:
            sys.modules["rescoring"] = previous_rescoring
        if previous_model_manager is missing:
            sys.modules.pop("rescoring.model_manager", None)
        else:
            sys.modules["rescoring.model_manager"] = previous_model_manager
        for key, previous in previous_env.items():
            if previous is missing_env:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


# ── Tests de /health ─────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """Tests del endpoint /health — gating del frontend (LauncherScreen).

    El frontend llama a /health durante bootstrap. Si falla,
    el modelo base se marca como missing y se muestra el launcher.
    """

    def test_health_returns_200_when_all_components_ok(self, client: TestClient):
        """Todos los componentes healthy → 200 + status='healthy'."""
        # Los componentes se simulan sanos a proposito: lo que esta bajo
        # prueba es la AGREGACION del endpoint, no el entorno. El manifiesto
        # se daba por sano por omision, y solo porque en la maquina del
        # mantenedor estaban todos los pesos. En un clon limpio faltan los
        # `.pt`, el verificador reporta `degraded` con razon y esta prueba
        # caia. Que la aplicacion se degrade sin sus pesos es el
        # comportamiento correcto; quien lo comprueba es
        # test_health_returns_503_*, no esta.
        verificacion_sana = {
            "valid": True,
            "manifest_version": 4,
            "models": [],
            "errors": [],
        }
        with patch("api.main._check_rdkit_health", new_callable=AsyncMock) as mock_rdkit, \
             patch("api.main._check_vina_health", new_callable=AsyncMock) as mock_vina, \
             patch("services.rescoring_bridge.get_model_manifest_verification",
                   return_value=verificacion_sana):
            mock_rdkit.return_value = {"status": "healthy"}
            mock_vina.return_value = {"status": "healthy"}

            response = client.get("/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["app_mode"] == "DESKTOP"
            assert "components" in data
            assert data["components"]["rdkit"]["status"] == "healthy"
            assert data["components"]["vina"]["status"] == "healthy"
            assert data["components"]["database"]["status"] == "healthy"
            assert data["components"]["model_manifest"]["status"] == "healthy"
            assert data["components"]["model_manifest"]["manifest_version"] == 4

    def test_health_returns_503_when_rdkit_unhealthy(self, client: TestClient):
        """RDKit unhealthy → 503 + status='degraded' (frontend marca base como missing)."""
        with patch("api.main._check_rdkit_health", new_callable=AsyncMock) as mock_rdkit, \
             patch("api.main._check_vina_health", new_callable=AsyncMock) as mock_vina:
            mock_rdkit.return_value = {"status": "unhealthy", "error": "rdkit not installed"}
            mock_vina.return_value = {"status": "healthy"}

            response = client.get("/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "degraded"
            assert data["components"]["rdkit"]["status"] == "unhealthy"

    def test_health_response_shape(self, client: TestClient):
        """La respuesta siempre tiene la estructura esperada (contrato con frontend)."""
        with patch("api.main._check_rdkit_health", new_callable=AsyncMock) as mock_rdkit, \
             patch("api.main._check_vina_health", new_callable=AsyncMock) as mock_vina:
            mock_rdkit.return_value = {"status": "healthy"}
            mock_vina.return_value = {"status": "healthy"}

            response = client.get("/health")
            data = response.json()

            # Contrato: siempre estos campos
            assert "status" in data
            assert "app_mode" in data
            assert "components" in data
            assert set(data["components"].keys()) >= {
                "mode", "rdkit", "vina", "database", "storage", "model_manifest"
            }


# ── Tests de /hardware ──────────────────────────────────────────────────────


class TestHardwareEndpoint:
    """Tests de /hardware — el frontend usa esto para mostrar capabilities."""

    def test_hardware_returns_200(self, client: TestClient):
        """Endpoint de hardware siempre responde 200 (es info, no gating)."""
        response = client.get("/hardware")
        assert response.status_code == 200
        data = response.json()
        # Debe tener al menos alguna info de hardware (CPU/RAM)
        assert isinstance(data, dict)
