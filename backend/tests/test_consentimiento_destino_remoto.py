"""MOLCHAT-NET-005 — no se envía nada fuera de la máquina sin consentimiento.

Búsqueda de `consent`, `autoriz` y `allow_remote` en el router, el servicio de
chat y los proveedores: cero coincidencias. No había puerta alguna — si había un
proveedor remoto configurado, el turno salía, y con él el contexto de caso y
molécula, que es el trabajo del investigador y no sólo el texto del chat.

Y la mitad que MOLCHAT-BE-003 dejó abierta vive aquí: autenticar
`providers/configure` impidió que un anónimo redirigiera el tráfico, pero
cambiar el `base_url` seguía siendo un cambio de **destino de los datos**
invisible. El consentimiento se otorga a la huella `proveedor@host`, así que el
destino nuevo no hereda la autorización del anterior.

El destino se calcula, no se supone: `ollama` apuntado al servidor de otra
persona sale de la máquina, y un `openai` apuntado a `localhost` no.

(Fase 6.6) Los turnos de chat y las rutas `/ai/providers/*` murieron con el
asistente interno; lo que queda es la puerta (`services/consent.py` +
`services/red.py`), que usan los informes IA y las salidas de plataforma. Los
proveedores aquí son dobles mínimos: la puerta sólo lee `id` y
`config.base_url`.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from services import consent
from services import provider_config_store as store

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def almacen_aislado(tmp_path, monkeypatch):
    secreto = tmp_path / "secret_key"
    secreto.write_text("b" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    yield


# ── El destino se calcula ────────────────────────────────────────────────


def _proveedor(pid: str, base_url: str = ""):
    return SimpleNamespace(id=pid, config=SimpleNamespace(base_url=base_url))


def _ollama(base_url: str):
    return _proveedor("ollama", base_url)


def _local():
    return _proveedor("local")


def test_el_motor_local_no_sale_de_la_maquina():
    destino = consent.destino_de(_local())
    assert destino.es_remoto is False


def test_ollama_en_esta_maquina_no_es_remoto():
    assert consent.destino_de(_ollama("http://localhost:11434")).es_remoto is False
    assert consent.destino_de(_ollama("http://127.0.0.1:11434")).es_remoto is False


def test_ollama_apuntado_a_otra_maquina_si_es_remoto():
    """El nombre del proveedor no decide; el host del destino sí."""
    destino = consent.destino_de(_ollama("http://servidor-ajeno.example:11434"))
    assert destino.es_remoto is True
    assert destino.host == "servidor-ajeno.example"


def test_una_ip_de_la_red_local_es_otra_computadora():
    assert consent.destino_de(_ollama("http://192.168.1.50:11434")).es_remoto is True


def test_un_destino_sin_declarar_se_trata_como_remoto():
    """La duda no se resuelve a favor de enviar."""

    class SinDestino:
        id = "openai"
        config = SimpleNamespace(base_url="")

    assert consent.destino_de(SinDestino()).es_remoto is True


def test_los_proveedores_de_api_fija_son_remotos():
    destino = consent.destino_de(_proveedor("claude"))
    assert destino.es_remoto is True
    assert destino.host == "api.anthropic.com"


# ── El destino cambia, el permiso no viaja con él ────────────────────────


def test_cambiar_el_base_url_deja_el_destino_sin_autorizar():
    """La mitad abierta de MOLCHAT-BE-003, comprobada donde se decide."""
    antes = consent.destino_de(_ollama("http://servidor-a.example:11434"))
    consent.otorgar(antes, ALICE)
    assert consent.hay_consentimiento(antes, ALICE) is True

    despues = consent.destino_de(_ollama("http://servidor-b.example:11434"))
    assert consent.hay_consentimiento(despues, ALICE) is False, (
        "el consentimiento del destino anterior autorizó a uno nuevo"
    )


def test_revocar_retira_todos_los_destinos_del_proveedor():
    consent.otorgar(consent.destino_de(_ollama("http://servidor-a.example:11434")), ALICE)
    consent.otorgar(consent.destino_de(_ollama("http://servidor-b.example:11434")), ALICE)

    assert consent.revocar("ollama", ALICE) is True
    assert store.cargar_consentimientos(ALICE) == {}


def test_el_invitado_no_hereda_consentimientos():
    """Heredarlo sería afirmar que alguien aceptó algo que nadie comprobó."""
    destino = consent.destino_de(_ollama("http://servidor-a.example:11434"))
    consent.otorgar(destino, ALICE)

    # La herencia de D-07 llega a la configuración, no al permiso.
    assert consent.hay_consentimiento(destino, BOB) is False
