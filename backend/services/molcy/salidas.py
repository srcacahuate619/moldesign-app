"""Carpeta de salida OPCIONAL de los vídeos de Molcy (otra carpeta u otro disco).

Por defecto un vídeo se guarda donde ya se guardaba: dentro del caso de su corrida o, sin caso, en la carpeta
de datos de MolDesign. Esto añade una elección explícita de la persona: «para todos los vídeos» (una
preferencia por cuenta) o «para este vídeo» (un solo render).

La AUTORIDAD sobre qué carpetas existen es de Rust, igual que con los casos: sólo `molcy_pick_output_dir`
(selector nativo) escribe `molcy-salidas.json`, y este módulo sólo lo LEE. Una ruta que llegue por la API sin
haber pasado por el selector no se escribe. Dentro de la carpeta elegida los vídeos van a una subcarpeta propia
(`MolDesign-Molcy`) y cada trabajo a una carpeta nueva: nunca se sobrescribe ni se mezcla con archivos ajenos.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from utils.local_storage import data_dir

SUBCARPETA = "MolDesign-Molcy"
PREDETERMINADA = "predeterminada"


def _registro() -> dict[str, Path]:
    ruta = os.environ.get("MOLDESIGN_MOLCY_OUTPUTS")
    if not ruta or not Path(ruta).is_file():
        return {}
    try:
        datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
        if datos.get("version") != 1 or not isinstance(datos.get("folders"), dict):
            raise ValueError("El registro de carpetas de salida tiene un formato desconocido.")
    except (OSError, ValueError) as exc:
        raise ValueError("No se pudo leer el registro de carpetas de salida. Elígela de nuevo.") from exc
    return {key: Path(valor) for key, valor in datos["folders"].items() if isinstance(valor, str)}


def disponible() -> bool:
    """Sólo la aplicación de escritorio (con selector nativo) puede autorizar carpetas."""
    return bool(os.environ.get("MOLDESIGN_MOLCY_OUTPUTS"))


def carpeta(salida_id: str) -> dict[str, Any]:
    """La carpeta autorizada con ese id, o `ValueError` con la causa."""
    from .storage import _redireccion

    try:
        uuid.UUID(salida_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("La carpeta de salida elegida no es válida.") from exc
    ruta = _registro().get(salida_id)
    if ruta is None or not ruta.is_absolute():
        raise ValueError("La carpeta de salida ya no está autorizada. Elígela de nuevo en Molcy.")
    try:
        real = ruta.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"La carpeta de salida no está disponible ({ruta}). ¿Falta el disco? Elige otra.") from exc
    if not real.is_dir() or _redireccion(real):
        raise ValueError("La carpeta de salida no es una carpeta ordinaria. Elige otra.")
    return {"id": salida_id, "ruta": real}


def _archivo_preferencia(user_id: str) -> Path:
    uuid.UUID(user_id)
    return data_dir() / "molcy_preferencias" / f"{user_id}.json"


def preferencia(user_id: str) -> str | None:
    try:
        valor = json.loads(_archivo_preferencia(user_id).read_text(encoding="utf-8")).get("salida_id")
    except (OSError, ValueError, AttributeError):
        return None
    return valor if isinstance(valor, str) else None


def fijar_preferencia(user_id: str, salida_id: str | None) -> None:
    archivo = _archivo_preferencia(user_id)
    if salida_id is None:
        archivo.unlink(missing_ok=True)
        return
    carpeta(salida_id)  # sólo se recuerda una carpeta autorizada y utilizable
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({"salida_id": salida_id}), encoding="utf-8")


def elegir(user_id: str, solicitada: str | None) -> dict[str, Any] | None:
    """Qué carpeta usar: este vídeo > todos los vídeos > nada (caso o datos de MolDesign).

    `solicitada == PREDETERMINADA` ignora la preferencia global sólo para este vídeo.
    """
    if solicitada == PREDETERMINADA:
        return None
    if solicitada:
        return carpeta(solicitada)
    global_ = preferencia(user_id)
    return carpeta(global_) if global_ else None
