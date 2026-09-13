"""D-09 — el proveedor y sus claves son por cuenta.

Decisión del propietario (2026-08-31): «proveedor por cuenta». Hasta aquí la
configuración era **global a la máquina**: un único `~/.moldesign/
provider_config.json` con un mapa plano `provider_id → entrada`, y
`POST /ai/providers/configure` mutando el objeto proveedor del singleton. Con
BE-002 esa escritura ya exige sesión, pero seguía siendo la misma configuración
para todas las cuentas: **la clave de una persona se gastaba en el chat de
otra**, y cambiar el modelo o el `base_url` se lo cambiaba a todo el mundo.

El registro arrastraba además la misma enfermedad que `ChatService` antes de
MOLCHAT-BE-006: `_providers` y `_active_provider_id` como atributos de **clase**
sobre un singleton de proceso.

Las entradas anteriores a esta columna no tienen dueño conocido. **No se les
asigna uno por suposición** —mismo criterio que D-07 con las conversaciones y
que MOLDEX-SCI-001 con los sellos—: se preservan como heredadas y sólo las lee
la cuenta invitada.
"""

from __future__ import annotations

import json
import uuid

import pytest

from services.ai import provider_config_store as store
from services.ai.providers.base import ProviderConfig
from services.ai.providers.registry import ProviderRegistry

ALICE = str(uuid.uuid4())
BOB = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def almacen_aislado(tmp_path, monkeypatch):
    """Cada prueba usa su propio almacén y su propia clave de cifrado."""
    secreto = tmp_path / "secret_key"
    secreto.write_text("a" * 64, encoding="utf-8")
    monkeypatch.setattr(store, "_STORE_DIR", tmp_path)
    monkeypatch.setattr(store, "_STORE_FILE", tmp_path / "provider_config.json")
    monkeypatch.setattr(store, "_SECRET_KEY_FILE", secreto)
    yield


def _registro_con_catalogo():
    """Un registro con dos proveedores de catálogo, como los del arranque."""
    from services.ai.providers.claude_provider import ClaudeProvider
    from services.ai.providers.ollama_provider import OllamaProvider

    registro = ProviderRegistry()
    registro.register(ClaudeProvider(config=ProviderConfig()))
    registro.register(OllamaProvider(config=ProviderConfig(base_url="http://localhost:11434")))
    return registro


# ── El almacén ───────────────────────────────────────────────────────────────


def test_la_clave_de_una_cuenta_no_la_lee_otra():
    """El daño concreto de D-09: la clave de Alice pagada por el chat de Bob."""
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-de-alice")

    assert store.load_provider_config("claude", user_id=ALICE)["api_key"] == "sk-de-alice"
    assert store.load_provider_config("claude", user_id=BOB) == {}


def test_el_base_url_de_una_cuenta_no_redirige_a_otra():
    """MOLCHAT-BE-003: el `base_url` es el destino de los datos, no un ajuste."""
    store.save_provider_config("ollama", user_id=ALICE, base_url="http://otro-servidor:1234")

    assert store.load_provider_config("ollama", user_id=BOB).get("base_url") is None


def test_el_proveedor_activo_es_por_cuenta():
    store.save_active_provider("claude", user_id=ALICE)
    store.save_active_provider("ollama", user_id=BOB)

    assert store.load_active_provider(user_id=ALICE) == "claude"
    assert store.load_active_provider(user_id=BOB) == "ollama"


def test_borrar_la_configuracion_de_una_cuenta_no_toca_la_de_la_otra():
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-de-alice")
    store.save_provider_config("claude", user_id=BOB, api_key="sk-de-bob")

    assert store.delete_provider_config("claude", user_id=ALICE) is True

    assert store.load_provider_config("claude", user_id=ALICE) == {}
    assert store.load_provider_config("claude", user_id=BOB)["api_key"] == "sk-de-bob"


def test_la_clave_sigue_cifrada_en_reposo():
    """Lo que ya estaba bien (§4 del expediente) y no debe romperse."""
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-secreta-en-claro")

    crudo = store._STORE_FILE.read_text(encoding="utf-8")
    assert "sk-secreta-en-claro" not in crudo


# ── Lo heredado, que no tiene dueño ──────────────────────────────────────────


def _escribir_almacen_v1(api_key_cifrada: str) -> None:
    """El formato plano anterior a las cuentas, tal cual lo escribía v1."""
    store._STORE_FILE.write_text(
        json.dumps(
            {
                "claude": {"api_key": api_key_cifrada, "model": "claude-haiku-4-5-20251001"},
                "__meta__": {"active_provider": "claude"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_la_configuracion_anterior_a_las_cuentas_no_se_le_asigna_a_nadie():
    _escribir_almacen_v1(store._encrypt("sk-de-antes-de-las-cuentas"))

    assert store.load_provider_config("claude", user_id=ALICE) == {}
    assert store.load_active_provider(user_id=ALICE) is None


def test_la_cuenta_invitada_hereda_lo_anterior():
    """D-07 aplicado a la configuración: la hereda quien hizo ese trabajo."""
    _escribir_almacen_v1(store._encrypt("sk-de-antes-de-las-cuentas"))

    heredada = store.load_provider_config("claude", user_id=ALICE, incluir_heredadas=True)
    assert heredada["api_key"] == "sk-de-antes-de-las-cuentas"
    assert store.load_active_provider(user_id=ALICE, incluir_heredadas=True) == "claude"


def test_lo_propio_gana_a_lo_heredado():
    _escribir_almacen_v1(store._encrypt("sk-de-antes-de-las-cuentas"))
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-propia")

    cfg = store.load_provider_config("claude", user_id=ALICE, incluir_heredadas=True)
    assert cfg["api_key"] == "sk-propia"


def test_la_migracion_no_pierde_lo_que_habia():
    """Migrar no puede ser una forma elegante de borrar la clave del usuario."""
    _escribir_almacen_v1(store._encrypt("sk-de-antes-de-las-cuentas"))

    store.save_provider_config("ollama", user_id=BOB, base_url="http://localhost:11434")

    assert (
        store.load_provider_config("claude", user_id=ALICE, incluir_heredadas=True)["api_key"]
        == "sk-de-antes-de-las-cuentas"
    )


# ── El registro ──────────────────────────────────────────────────────────────


def test_el_registro_no_guarda_su_estado_en_atributos_de_clase():
    """La misma enfermedad que BE-006 curó en `ChatService`."""
    uno = _registro_con_catalogo()
    otro = ProviderRegistry()

    assert otro.get("claude") is None, (
        "el catálogo vive en un atributo de clase: un registro nuevo ya trae "
        "los proveedores de otro"
    )
    assert uno.get("claude") is not None


def test_configurar_una_cuenta_no_muta_el_proveedor_del_catalogo():
    registro = _registro_con_catalogo()
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-de-alice")

    del_catalogo = registro.get("claude")
    assert del_catalogo.config.api_key == "", (
        "la configuración de una cuenta se aplicó al objeto compartido del "
        "catálogo: es la mutación global que D-09 retira"
    )

    de_alice = registro.resolve_for_user("claude", user_id=ALICE)
    de_bob = registro.resolve_for_user("claude", user_id=BOB)
    assert de_alice.config.api_key == "sk-de-alice"
    assert de_bob.config.api_key == ""


def test_el_activo_del_registro_es_por_cuenta():
    registro = _registro_con_catalogo()

    assert registro.set_active("claude", user_id=ALICE) is True
    assert registro.set_active("ollama", user_id=BOB) is True

    assert registro.resolve_for_user(None, user_id=ALICE).id == "claude"
    assert registro.resolve_for_user(None, user_id=BOB).id == "ollama"


def test_la_sonda_abierta_no_dice_de_quien_es_la_clave():
    """`GET /ai/providers` y `GET /ai/status` responden sin sesión.

    Con la configuración por cuenta, `configured` pasa a ser un dato de cuenta:
    sin identidad no puede afirmarse.
    """
    registro = _registro_con_catalogo()
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-de-alice")

    sin_sesion = {p["id"]: p for p in registro.list_providers(user_id=None)}
    assert sin_sesion["claude"]["configured"] is False

    con_sesion = {p["id"]: p for p in registro.list_providers(user_id=ALICE)}
    assert con_sesion["claude"]["configured"] is True
    # `requires_api_key` sí viaja —es una propiedad del proveedor, no un secreto—;
    # lo que no puede viajar es el valor, y eso lo comprueba la prueba siguiente.
    assert "api_key" not in con_sesion["claude"]


def test_el_catalogo_nunca_publica_la_clave():
    registro = _registro_con_catalogo()
    store.save_provider_config("claude", user_id=ALICE, api_key="sk-de-alice")

    assert "sk-de-alice" not in json.dumps(registro.list_providers(user_id=ALICE))
