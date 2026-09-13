"""
Tests de regresión para la consolidación desktop-only (C-08).

Una instalación puede conservar ``APP_MODE=CLOUD`` de un entorno antiguo. El
runtime debe normalizarlo a DESKTOP, no activar rutas o límites de un SaaS.

Nota: los módulos bajo test capturan settings = get_settings() al importarse;
por eso cada test los recarga (importlib.reload) tras limpiar la caché de
get_settings(), para probar la resolución real y no un estado congelado
de tests previos.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import pytest

from core.config import get_settings


@pytest.fixture(autouse=True)
def _app_mode_absent(monkeypatch):
    """Garantiza que APP_MODE no está definido y limpia la caché de Settings."""
    monkeypatch.delenv("APP_MODE", raising=False)
    get_settings.cache_clear()


class TestDesktopModeIsEnforced:
    """El runtime siempre conserva las rutas y límites de escritorio."""

    def test_default_mode_is_desktop_without_env(self):
        """Sin APP_MODE en el entorno, el modo por defecto es DESKTOP."""
        settings = get_settings()
        assert settings.app_mode == "DESKTOP"
        assert settings.is_desktop is True
        assert not hasattr(settings, "is_cloud")

    def test_legacy_cloud_env_is_normalized_to_desktop(self, monkeypatch):
        """Una variable heredada nunca desvía el pipeline fuera de desktop."""
        monkeypatch.setenv("APP_MODE", "CLOUD")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.app_mode == "DESKTOP"
        assert settings.is_desktop is True

    def test_dynamic_limiter_desktop_by_default(self):
        """Sin APP_MODE, el limiter resuelve el límite desktop (3000/minute)."""
        import api.dynamic_limiter as dl

        dl = importlib.reload(dl)
        assert dl.get_dynamic_limit(None) == "3000/minute"
        # Llamada de introspección de SlowAPI (sin argumentos)
        assert dl.get_dynamic_limit() == "3000/minute"

    def test_dynamic_limiter_ignores_legacy_cloud_env(self, monkeypatch):
        """El limiter conserva el contrato desktop aunque exista APP_MODE viejo."""
        monkeypatch.setenv("APP_MODE", "CLOUD")
        get_settings.cache_clear()
        import api.dynamic_limiter as dl

        dl = importlib.reload(dl)
        assert dl.get_dynamic_limit(None) == "3000/minute"

    def test_file_handlers_expose_stable_local_paths(self):
        """Las rutas lógicas se conservan al retirar el bootstrap remoto."""
        import utils.file_handlers as fh

        fh = importlib.reload(fh)
        assert fh.StoragePath.target_raw("7e2y") == "targets/7E2Y/raw.pdb"
        assert fh.StoragePath.docking_poses("abc", "7e2y") == "poses/abc/7E2Y/poses.sdf"

    def test_preparer_resolves_local_path_in_desktop(self):
        """get_target_pdb_path resuelve a local_data_dir/targets en desktop."""
        import services.docking.preparer as prep

        prep = importlib.reload(prep)
        assert prep.settings.is_desktop is True

        path = prep.get_target_pdb_path("ZZZ_FAKE_PDB_ID")
        expected = str(Path(prep.settings.local_data_dir) / "targets" / "ZZZ_FAKE_PDB_ID.pdb")
        assert path == expected
        assert path.startswith(prep.settings.local_data_dir)
