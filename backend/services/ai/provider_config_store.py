"""
Persistent, encrypted store for AI provider configuration.

Follows the same pattern as the secret_key persistence (~/.moldesign/):
- API keys are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256).
- The encryption key is derived from the machine-local secret_key.
- Config lives in ~/.moldesign/provider_config.json.

Design principles:
- Local first: no cloud dependency for configuration storage.
- Zero-config default: works out of the box with local LLM.
- Environment variables act as overrides, not the primary mechanism.
- Single source of truth: the persist file is authoritative after user saves.

D-09 (decisión del propietario, 2026-08-31): **el proveedor y sus claves son por
cuenta**. Hasta el esquema v1 este archivo era un mapa plano
``provider_id -> entrada``, global a la máquina: la clave de una persona se
gastaba en el chat de otra y cambiar el ``base_url`` cambiaba el destino de los
datos de todo el mundo.

El esquema v2 mete la cuenta en el medio. Las entradas de v1 no tienen dueño
conocido y **no se les asigna uno por suposición** —mismo criterio que D-07 con
las conversaciones—: se preservan bajo ``__heredado__`` y sólo las lee quien
pide ``incluir_heredadas``, que es la cuenta invitada.
"""

from __future__ import annotations

import base64
import json
import threading
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from utils.logger import get_logger

log = get_logger(__name__)

_STORE_DIR = Path.home() / ".moldesign"
_STORE_FILE = _STORE_DIR / "provider_config.json"
_SECRET_KEY_FILE = _STORE_DIR / "secret_key"

_SALT = b"moldesign_provider_store_v1"

#: Esquema del archivo. v1 = mapa plano por proveedor; v2 = con dimensión de cuenta.
_SCHEMA = 2

_lock = threading.Lock()


def _derive_fernet_key() -> bytes:
    """Derive a Fernet-compatible key from the machine-local secret_key.

    Uses PBKDF2 with a fixed salt. The secret_key is already
    a random 32-byte hex string persisted on first launch.
    """
    if not _SECRET_KEY_FILE.exists():
        raise FileNotFoundError(
            f"Secret key not found at {_SECRET_KEY_FILE}. "
            "The application must be started at least once to generate it."
        )

    raw = _SECRET_KEY_FILE.read_text(encoding="utf-8").strip()
    key_bytes = bytes.fromhex(raw)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=480_000,
    )
    derived = kdf.derive(key_bytes)
    return base64.urlsafe_b64encode(derived)


def _get_fernet() -> Fernet:
    """Lazily initialise Fernet with a cached instance."""
    return Fernet(_derive_fernet_key())


def _vacio() -> dict[str, Any]:
    """Un almacén v2 recién nacido."""
    return {
        "__schema__": _SCHEMA,
        "cuentas": {},
        "__heredado__": {"providers": {}, "active_provider": None},
    }


def _cuenta_vacia() -> dict[str, Any]:
    """La forma de una cuenta. Los consentimientos viven con su configuración.

    No hay `__heredado__` para consentimientos, y es deliberado: heredarlos
    sería afirmar que alguien autorizó un destino, y eso nadie lo comprobó
    (MOLCHAT-NET-005).
    """
    return {"providers": {}, "active_provider": None, "consentimientos": {}}


def _migrar_v1(plano: dict[str, Any]) -> dict[str, Any]:
    """Sube el mapa plano de v1 a v2 **sin asignarle dueño**.

    Las entradas de v1 se escribieron cuando no había cuentas: pertenecen a
    quien usara el escritorio, y eso nadie lo comprobó. Se preservan aparte, y
    las lee sólo quien pide `incluir_heredadas` —la cuenta invitada—. Es el
    mismo criterio que D-07 con las conversaciones y que MOLDEX-SCI-001 con los
    sellos heredados.
    """
    migrado = _vacio()
    meta = plano.get("__meta__", {})
    migrado["__heredado__"]["providers"] = {
        pid: entry
        for pid, entry in plano.items()
        if pid != "__meta__" and isinstance(entry, dict)
    }
    migrado["__heredado__"]["active_provider"] = meta.get("active_provider")
    if migrado["__heredado__"]["providers"] or migrado["__heredado__"]["active_provider"]:
        log.info(
            "provider_config_migrado_v1_a_v2",
            heredados=sorted(migrado["__heredado__"]["providers"]),
        )
    return migrado


def _normalizar(data: dict[str, Any]) -> dict[str, Any]:
    """Devuelve siempre la forma v2, venga de donde venga el archivo."""
    if data.get("__schema__") == _SCHEMA:
        data.setdefault("cuentas", {})
        heredado = data.setdefault("__heredado__", {"providers": {}, "active_provider": None})
        heredado.setdefault("providers", {})
        heredado.setdefault("active_provider", None)
        return data
    return _migrar_v1(data)


def _read_store() -> dict[str, Any]:
    """Read the full provider config store from disk, always in v2 shape.

    Returns an empty store if the file does not exist or is corrupt.
    """
    if not _STORE_FILE.exists():
        return _vacio()
    try:
        raw = _STORE_FILE.read_text(encoding="utf-8")
        if not raw.strip():
            return _vacio()
        return _normalizar(json.loads(raw))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("provider_config_store_corrupt", path=str(_STORE_FILE), error=str(exc))
        return _vacio()


def _descifrar_entrada(entry: dict[str, Any], provider_id: str) -> dict[str, Any]:
    """Copia de la entrada con la clave en claro; el resto tal cual."""
    result: dict[str, Any] = {}
    for key, value in entry.items():
        if key == "api_key":
            try:
                result[key] = _decrypt(value)
            except Exception:
                log.warning(
                    "provider_config_decrypt_failed",
                    provider_id=provider_id,
                    field=key,
                )
                result[key] = ""
        else:
            result[key] = value
    return result


def _write_store(data: dict[str, Any]) -> None:
    """Atomically write the full provider config store to disk."""
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_STORE_FILE)


def _encrypt(value: str) -> str:
    """Encrypt a plaintext value. Returns base64-encoded ciphertext."""
    if not value:
        return ""
    f = _get_fernet()
    return f.encrypt(value.encode("utf-8")).decode("utf-8")


def _decrypt(token: str) -> str:
    """Decrypt a Fernet token. Returns the original plaintext."""
    if not token:
        return ""
    f = _get_fernet()
    return f.decrypt(token.encode("utf-8")).decode("utf-8")


# ── Public API ──────────────────────────────────────────────────────────

def save_provider_config(
    provider_id: str,
    *,
    user_id: str,
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist configuration for a single provider **of one account**.

    Only the fields explicitly provided are updated; existing fields
    are preserved.  The ``api_key`` is encrypted before storage.

    Guardar es siempre en el espacio propio de la cuenta: lo heredado se lee,
    nunca se reescribe.
    """
    if not user_id:
        raise ValueError("save_provider_config requiere user_id (D-09)")

    with _lock:
        store = _read_store()
        cuenta = store["cuentas"].setdefault(user_id, _cuenta_vacia())
        entry = cuenta["providers"].get(provider_id, {})

        if api_key is not None:
            entry["api_key"] = _encrypt(api_key)
        if base_url is not None:
            entry["base_url"] = base_url
        if model is not None:
            entry["model"] = model
        if temperature is not None:
            entry["temperature"] = temperature
        if max_tokens is not None:
            entry["max_tokens"] = max_tokens
        if extra is not None:
            entry["extra"] = extra

        cuenta["providers"][provider_id] = entry
        _write_store(store)

    log.info("provider_config_saved", provider_id=provider_id)


def load_provider_config(
    provider_id: str,
    user_id: str,
    incluir_heredadas: bool = False,
) -> dict[str, Any]:
    """Load the persisted configuration for a single provider of an account.

    Returns a dict with decrypted values, or an empty dict if
    nothing has been saved for this provider.

    ``incluir_heredadas`` sólo lo pide la cuenta invitada (ver D-07/D-09): cae a
    la configuración anterior a las cuentas cuando la cuenta no tiene la suya.
    """
    store = _read_store()
    entry = store["cuentas"].get(user_id, {}).get("providers", {}).get(provider_id, {})
    if not entry and incluir_heredadas:
        entry = store["__heredado__"]["providers"].get(provider_id, {})
    if not entry:
        return {}
    return _descifrar_entrada(entry, provider_id)


def load_all_provider_configs(
    user_id: str,
    incluir_heredadas: bool = False,
) -> dict[str, dict[str, Any]]:
    """Load all persisted provider configurations of an account."""
    store = _read_store()
    propias = store["cuentas"].get(user_id, {}).get("providers", {})

    fuente: dict[str, dict[str, Any]] = {}
    if incluir_heredadas:
        fuente.update(store["__heredado__"]["providers"])
    fuente.update(propias)

    return {pid: _descifrar_entrada(entry, pid) for pid, entry in fuente.items()}


def delete_provider_config(provider_id: str, user_id: str) -> bool:
    """Remove persisted configuration for a provider of an account.

    Returns True if the entry existed, False otherwise. Lo heredado no se borra
    por esta vía: no es de nadie, así que nadie puede retirarlo.
    """
    with _lock:
        store = _read_store()
        providers = store["cuentas"].get(user_id, {}).get("providers", {})
        if provider_id not in providers:
            return False
        del providers[provider_id]
        _write_store(store)
    log.info("provider_config_deleted", provider_id=provider_id)
    return True


def save_active_provider(provider_id: str, user_id: str) -> None:
    """Persist the account's choice of active provider."""
    if not user_id:
        raise ValueError("save_active_provider requiere user_id (D-09)")

    with _lock:
        store = _read_store()
        cuenta = store["cuentas"].setdefault(user_id, _cuenta_vacia())
        cuenta["active_provider"] = provider_id
        _write_store(store)
    log.info("active_provider_saved", provider_id=provider_id)


def load_active_provider(user_id: str, incluir_heredadas: bool = False) -> str | None:
    """Load the account's persisted active provider choice."""
    store = _read_store()
    activo = store["cuentas"].get(user_id, {}).get("active_provider")
    if activo:
        return activo
    if incluir_heredadas:
        return store["__heredado__"]["active_provider"]
    return None


# ── Consentimiento de destino (MOLCHAT-NET-005) ─────────────────────────


def cargar_consentimientos(user_id: str) -> dict[str, dict[str, Any]]:
    """Destinos que esta cuenta autorizó, por huella `proveedor@host`.

    Nunca cae a lo heredado: un consentimiento sin dueño conocido no es un
    consentimiento.
    """
    store = _read_store()
    return store["cuentas"].get(user_id, {}).get("consentimientos", {})


def guardar_consentimiento(user_id: str, huella: str, registro: dict[str, Any]) -> None:
    if not user_id:
        raise ValueError("guardar_consentimiento requiere user_id")

    with _lock:
        store = _read_store()
        cuenta = store["cuentas"].setdefault(user_id, _cuenta_vacia())
        cuenta.setdefault("consentimientos", {})[huella] = registro
        _write_store(store)


def borrar_consentimientos_de(user_id: str, provider_id: str) -> list[str]:
    """Retira todos los destinos autorizados de un proveedor. Devuelve las huellas.

    Es por proveedor y no por huella porque también se usa al cambiar el
    `base_url`: el destino anterior deja de estar autorizado sin que nadie tenga
    que acordarse de revocarlo.
    """
    with _lock:
        store = _read_store()
        cuenta = store["cuentas"].get(user_id, {})
        consentimientos = cuenta.get("consentimientos", {})
        retiradas = [h for h in consentimientos if h.split("@", 1)[0] == provider_id]
        for huella in retiradas:
            del consentimientos[huella]
        if retiradas:
            _write_store(store)
    return retiradas
