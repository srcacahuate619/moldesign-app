"""Proveedores de IA por cuenta: catálogo verificado, claves cifradas y autorización por destino.

Reparto de responsabilidades (la cerradura y la llave):

- El CATÁLOGO (nombre, familia, URL base, modelos) lo escribe MolChat en
  `src/molchat_agent/providers/catalogo.json`. Viaja en la llave, así que su
  hash está en el manifiesto y MolDesign lo lee sólo de la copia verificada.
- Las CLAVES y las AUTORIZACIONES viven en MolDesign, por cuenta
  (`provider_config_store`, cifrado en reposo). La interfaz de MolDesign las
  introduce; ninguna respuesta de la API devuelve una clave completa.
- El sidecar pide la clave en el momento de llamar. MolDesign sólo la entrega si
  la cuenta tiene la clave, autorizó la huella `proveedor@host` y el host que
  el sidecar va a usar es el del catálogo verificado. Así, cambiar la URL de un
  proveedor en una copia alterada no saca la clave de la cuenta.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from services import provider_config_store as pcs
from services.molchat_host import launcher

ESQUEMA_CATALOGO = "moldesign.molchat-catalogo/1"
#: Ruta del catálogo dentro de la copia de MolChat vendorizada.
CATALOGO_RELATIVO = Path("src") / "molchat_agent" / "providers" / "catalogo.json"
#: Familias de protocolo que el sidecar sabe hablar. Un catálogo con otra familia no se usa.
FAMILIAS = frozenset({"openai_chat", "anthropic", "gemini", "meta", "llama_server", "ollama"})
_ID = re.compile(r"[a-z0-9][a-z0-9-]{1,31}")
_CLAVE = re.compile(r"\S{8,512}")
_LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})


class ProveedorError(Exception):
    """Una operación de proveedor no se puede hacer. `estado` es el código HTTP."""

    def __init__(self, estado: int, detalle: Any) -> None:
        super().__init__(str(detalle))
        self.estado = estado
        self.detalle = detalle


def _host(base_url: str) -> str:
    return (urlsplit(base_url).hostname or "").lower()


def leer_catalogo(carpeta: Path) -> list[dict[str, Any]]:
    """Entradas del catálogo de la copia `carpeta`. Lanza ValueError si el catálogo no es válido."""
    try:
        datos = json.loads((carpeta / CATALOGO_RELATIVO).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("el catálogo de proveedores no se puede leer") from exc
    if not isinstance(datos, dict) or datos.get("schema") != ESQUEMA_CATALOGO:
        raise ValueError("catálogo de proveedores con esquema desconocido")
    entradas = datos.get("proveedores")
    if not isinstance(entradas, list) or not entradas:
        raise ValueError("el catálogo no trae proveedores")
    vistos: set[str] = set()
    limpias: list[dict[str, Any]] = []
    for e in entradas:
        if not isinstance(e, dict):
            raise ValueError("entrada de catálogo no es un objeto")
        pid = str(e.get("id", ""))
        if not _ID.fullmatch(pid) or pid in vistos:
            raise ValueError(f"id de proveedor no válido o repetido: {pid!r}")
        vistos.add(pid)
        familia = e.get("familia")
        if familia not in FAMILIAS:
            raise ValueError(f"{pid}: familia desconocida {familia!r}")
        base = str(e.get("base_url", ""))
        host = _host(base)
        scheme = urlsplit(base).scheme
        remoto = bool(e.get("remoto"))
        if not host:
            raise ValueError(f"{pid}: base_url sin host")
        if remoto and (scheme != "https" or host in _LOOPBACK):
            raise ValueError(f"{pid}: un proveedor remoto debe usar https fuera de la máquina")
        if not remoto and host not in _LOOPBACK:
            raise ValueError(f"{pid}: un proveedor local debe apuntar a la máquina")
        if remoto and not e.get("requiere_clave", True):
            raise ValueError(f"{pid}: un proveedor remoto necesita clave")
        limpias.append({
            "id": pid,
            "nombre": str(e.get("nombre", pid))[:80],
            "familia": familia,
            "base_url": base,
            "host": host,
            "remoto": remoto,
            "requiere_clave": bool(e.get("requiere_clave", True)),
            "modelo_por_defecto": str(e.get("modelo_por_defecto", "")),
            "modelos_ejemplo": [str(m) for m in e.get("modelos_ejemplo", [])][:20],
            "prefijo_clave": str(e.get("prefijo_clave", "")),
            "documentacion": str(e.get("documentacion", "")),
            "que_sale": str(e.get("que_sale", "")),
        })
    return limpias


def catalogo_verificado() -> tuple[list[dict[str, Any]] | None, str]:
    """(entradas, motivo): el catálogo de la copia incluida ya verificada, o None con el motivo."""
    carpeta, motivo = launcher.localizar()
    if carpeta is None:
        return None, motivo
    try:
        return leer_catalogo(carpeta), "ok"
    except ValueError as exc:
        return None, str(exc)


def _entrada(entradas: list[dict[str, Any]], proveedor: str) -> dict[str, Any]:
    for e in entradas:
        if e["id"] == proveedor:
            return e
    raise ProveedorError(404, f"proveedor desconocido: {proveedor}")


def _entradas_o_error() -> list[dict[str, Any]]:
    entradas, motivo = catalogo_verificado()
    if entradas is None:
        raise ProveedorError(503, f"MolChat no disponible: {motivo}")
    return entradas


def _pista(clave: str) -> str:
    """Lo único de la clave que se muestra: los cuatro últimos caracteres."""
    return f"••••{clave[-4:]}" if len(clave) >= 8 else "••••"


def _vista(e: dict[str, Any], cfg: dict[str, Any], autorizados: dict[str, Any],
           activo: str | None) -> dict[str, Any]:
    clave = cfg.get("api_key") or ""
    if e["requiere_clave"]:
        autorizado = f"{e['id']}@{e['host']}" in autorizados
    else:
        autorizado = None  # un proveedor local no sale de la máquina: no hay nada que autorizar
    return {
        "id": e["id"],
        "nombre": e["nombre"],
        "familia": e["familia"],
        "host": e["host"],
        "remoto": e["remoto"],
        "requiere_clave": e["requiere_clave"],
        "documentacion": e["documentacion"],
        "que_sale": e["que_sale"],
        "modelo": cfg.get("model") or e["modelo_por_defecto"],
        "modelos_ejemplo": e["modelos_ejemplo"],
        "clave": {"configurada": bool(clave), "pista": _pista(clave)} if e["requiere_clave"] else None,
        "autorizado": autorizado,
        "activo": activo == e["id"],
    }


def estado(user_id: str) -> dict[str, Any]:
    """Catálogo verificado + lo que esta cuenta tiene. Nunca incluye una clave."""
    entradas, motivo = catalogo_verificado()
    if entradas is None:
        return {"disponible": False, "motivo": motivo, "activo": None, "proveedores": []}
    activo = pcs.load_active_provider(user_id)
    autorizados = pcs.cargar_consentimientos(user_id)
    filas = [_vista(e, pcs.load_provider_config(e["id"], user_id), autorizados, activo)
             for e in entradas]
    return {"disponible": True, "motivo": "ok", "activo": activo, "proveedores": filas}


def _uno(entradas: list[dict[str, Any]], proveedor: str, user_id: str) -> dict[str, Any]:
    e = _entrada(entradas, proveedor)
    return _vista(e, pcs.load_provider_config(proveedor, user_id),
                  pcs.cargar_consentimientos(user_id), pcs.load_active_provider(user_id))


def _validar_modelo(e: dict[str, Any], modelo: str | None) -> str | None:
    if modelo is None or modelo == "":
        return None
    if len(modelo) > 120 or not re.fullmatch(r"[\w./:+-]+", modelo):
        raise ProveedorError(422, "nombre de modelo no válido")
    return modelo


def guardar_y_autorizar(user_id: str, proveedor: str, api_key: str, host_visto: str,
                        modelo: str | None = None) -> dict[str, Any]:
    """«Guardar y autorizar envío a <host>» en un solo paso.

    `host_visto` es el host que la interfaz mostró antes de pedir la clave. Si el
    catálogo ahora dice otro, no se guarda nada: el usuario debe volver a mirar.
    """
    entradas = _entradas_o_error()
    e = _entrada(entradas, proveedor)
    if not e["requiere_clave"]:
        raise ProveedorError(400, f"{e['nombre']} no usa clave: es local")
    if not _CLAVE.fullmatch(api_key or ""):
        raise ProveedorError(422, "la clave no tiene un formato válido")
    if host_visto != e["host"]:
        raise ProveedorError(409, {"motivo": "destino_cambiado", "destino_actual": e["host"]})
    elegido = _validar_modelo(e, modelo)
    pcs.borrar_consentimientos_de(user_id, proveedor)
    pcs.guardar_consentimiento(user_id, f"{proveedor}@{e['host']}", {
        "proveedor": proveedor,
        "host": e["host"],
        "url": e["base_url"],
        "otorgado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    pcs.save_provider_config(proveedor, user_id=user_id, api_key=api_key, model=elegido)
    return _uno(entradas, proveedor, user_id)


def retirar_clave(user_id: str, proveedor: str) -> dict[str, Any]:
    """Borra la clave de la cuenta y retira todas sus autorizaciones de ese proveedor."""
    entradas = _entradas_o_error()
    _entrada(entradas, proveedor)
    pcs.delete_provider_config(proveedor, user_id)
    pcs.borrar_consentimientos_de(user_id, proveedor)
    if pcs.load_active_provider(user_id) == proveedor:
        pcs.save_active_provider(None, user_id)  # type: ignore[arg-type]
    return _uno(entradas, proveedor, user_id)


def elegir_activo(user_id: str, proveedor: str | None, modelo: str | None = None) -> dict[str, Any]:
    """Proveedor activo de la cuenta (o ninguno). Un remoto exige clave y autorización."""
    entradas = _entradas_o_error()
    if proveedor is None:
        pcs.save_active_provider(None, user_id)  # type: ignore[arg-type]
        return estado(user_id)
    e = _entrada(entradas, proveedor)
    if e["requiere_clave"]:
        cfg = pcs.load_provider_config(proveedor, user_id)
        if not cfg.get("api_key"):
            raise ProveedorError(409, {"motivo": "sin_clave"})
        if f"{proveedor}@{e['host']}" not in pcs.cargar_consentimientos(user_id):
            raise ProveedorError(409, {"motivo": "sin_autorizacion"})
    elegido = _validar_modelo(e, modelo)
    if elegido is not None:
        pcs.save_provider_config(proveedor, user_id=user_id, model=elegido)
    pcs.save_active_provider(proveedor, user_id)
    return estado(user_id)


def credencial(user_id: str, proveedor: str | None, host: str) -> dict[str, Any]:
    """Lo que el sidecar necesita para llamar: modelo y, si el proveedor lo pide, la clave.

    Sólo se entrega si el host pedido es el del catálogo verificado y la cuenta
    autorizó esa huella. Quien llama no decide a dónde van los datos: MolDesign sí.
    """
    entradas = _entradas_o_error()
    elegido = proveedor or pcs.load_active_provider(user_id)
    if not elegido:
        raise ProveedorError(409, {"motivo": "sin_proveedor_activo"})
    e = _entrada(entradas, elegido)
    if host.lower() != e["host"]:
        raise ProveedorError(403, {"motivo": "destino_distinto"})
    cfg = pcs.load_provider_config(elegido, user_id)
    modelo = cfg.get("model") or e["modelo_por_defecto"]
    if not e["requiere_clave"]:
        return {"proveedor": elegido, "modelo": modelo, "api_key": None}
    clave = cfg.get("api_key") or ""
    if not clave:
        raise ProveedorError(403, {"motivo": "sin_clave"})
    if f"{elegido}@{e['host']}" not in pcs.cargar_consentimientos(user_id):
        raise ProveedorError(403, {"motivo": "sin_autorizacion"})
    return {"proveedor": elegido, "modelo": modelo, "api_key": clave}
