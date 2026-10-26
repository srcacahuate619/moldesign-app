"""La comprobación de Solana devnet distingue «falta el permiso» de «devnet caída».

Hasta 1.0.2 `health()` convertía la negativa de `red.exigir_permiso` en «No se pudo conectar con Solana
devnet», y no existe ninguna pantalla que conceda ese permiso: el botón de la prueba devnet quedaba
deshabilitado para siempre. Ahora la respuesta trae `reason_code` y el destino, para que la interfaz pida el
permiso (por cuenta y por destino) en lugar de culpar a la red.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from services.ai import red
from services.blockchain.certifier import SolanaCertifier

ALICE = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def almacen_aislado(tmp_path, monkeypatch):
    from services.ai import provider_config_store as store

    secreto = tmp_path / "secret_key"
    secreto.write_text("f" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    monkeypatch.delenv("MOLDESIGN_OFFLINE", raising=False)
    red.fijar_identidad_peticion(ALICE)
    yield
    red.fijar_identidad_peticion(None)


def _health():
    return asyncio.run(SolanaCertifier("https://api.devnet.solana.com").health())


def test_sin_permiso_pide_permiso_y_nombra_el_destino():
    estado = _health()
    assert estado["available"] is False
    assert estado["reason_code"] == "consent_required"
    assert estado["destino"]["servicio"] == "solana-devnet"
    assert estado["destino"]["host"] == "api.devnet.solana.com"


def test_modo_offline_no_se_presenta_como_falta_de_permiso(monkeypatch):
    monkeypatch.setenv("MOLDESIGN_OFFLINE", "1")
    assert _health()["reason_code"] == "offline"


def test_con_permiso_la_comprobacion_llega_al_rpc(monkeypatch):
    red.otorgar("solana-devnet", ALICE)
    llamadas = []

    async def rpc_falso(self, method, params=None):
        llamadas.append(method)
        return "ok"

    monkeypatch.setattr(SolanaCertifier, "_rpc", rpc_falso)
    estado = _health()
    assert estado["available"] is True and llamadas == ["getHealth"]
    assert "reason_code" not in estado
