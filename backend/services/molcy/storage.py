"""Archivos del render dentro del caso; el registro de Rust autoriza la ruta.

El índice local conserva sólo case_id y un nombre relativo. Así, mover un caso
y volver a registrarlo no deja un camino absoluto obsoleto en Molcy.
"""
from __future__ import annotations

import json
import os
import re
import stat
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from utils.local_storage import data_dir


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"El archivo {path.name} no contiene un objeto JSON.")
    return value


def _redireccion(path: Path) -> bool:
    """También rechaza junctions de Windows, que is_symlink no detecta."""
    return path.is_symlink() or bool(
        path.exists() and getattr(path.lstat(), "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def casos(user_id: str) -> list[dict[str, Any]]:
    uuid.UUID(user_id)
    registry = os.environ.get("MOLDESIGN_CASE_REGISTRY")
    if not registry:
        return []  # API sin contenedor de escritorio: no autoriza rutas externas.
    path = Path(registry)
    if not path.exists():
        return []
    try:
        index = _json(path)
        if index.get("version") != 1 or not isinstance(index.get("cases"), dict):
            raise ValueError("Formato desconocido.")
    except (OSError, ValueError) as exc:
        raise ValueError("No se pudo leer el registro de casos. Reabre MolDesign y revisa sus casos.") from exc
    result = []
    for case_id, raw_path in index["cases"].items():
        try:
            uuid.UUID(case_id)
            folder = Path(raw_path)
            if not folder.is_absolute():
                continue
            folder = folder.resolve(strict=True)
            manifest_path = folder / "case.json"
            if _redireccion(manifest_path):
                continue
            manifest = _json(manifest_path)
            if (manifest.get("id") != case_id or manifest.get("ownerUserId") != user_id
                    or manifest.get("schemaVersion") not in range(1, 8)):
                continue
            result.append({"id": case_id, "nombre": manifest.get("name") or folder.name,
                           "ruta": folder, "manifest": manifest})
        except (OSError, TypeError, ValueError):
            continue
    return result


def caso_de_corrida(user_id: str, task_id: str, *, registrados=None) -> dict[str, Any] | None:
    matches = []
    for case in casos(user_id) if registrados is None else registrados:
        manifest = case["manifest"]
        runs = manifest.get("runs") or [manifest.get("activeRun")]
        if any(isinstance(run, dict) and run.get("taskId") == task_id for run in runs):
            matches.append(case)
    if len(matches) > 1:
        raise ValueError("Esta corrida aparece en varios casos. Resuelve esa asociación antes de generar el vídeo.")
    return matches[0] if matches else None


def indice_trabajo(user_id: str, job_id: str) -> Path:
    uuid.UUID(user_id)
    uuid.UUID(job_id)
    return data_dir() / "molcy" / user_id / job_id


def _carpeta_del_caso(case: dict[str, Any], name: str) -> Path:
    if not isinstance(name, str) or not re.fullmatch(r"[0-9]{3,}_[A-Za-z0-9_-]+", name):
        raise ValueError("El trabajo no conserva un nombre de carpeta válido.")
    base = case["ruta"] / "molcy"
    root = base / name
    if (_redireccion(base) or _redireccion(root)
            or base.resolve().parent != case["ruta"] or root.resolve().parent != base.resolve()):
        raise ValueError("La carpeta Molcy fue redirigida fuera de su caso.")
    return root


def _carpeta_de_salida(salida: dict[str, Any], name: str) -> Path:
    from .salidas import SUBCARPETA

    if not isinstance(name, str) or not re.fullmatch(r"[0-9]{3,}_[A-Za-z0-9_-]+", name):
        raise ValueError("El trabajo no conserva un nombre de carpeta válido.")
    base = salida["ruta"] / SUBCARPETA
    root = base / name
    if (_redireccion(base) or _redireccion(root)
            or (base.exists() and base.resolve().parent != salida["ruta"])
            or (root.exists() and root.resolve().parent != base.resolve())):
        raise ValueError("La carpeta de salida de Molcy fue redirigida.")
    return root


def raiz_trabajo(user_id: str, job_id: str) -> Path:
    index = indice_trabajo(user_id, job_id)
    if _redireccion(index) or index.resolve().parent != index.parent.resolve():
        raise ValueError("El índice del trabajo fue redirigido.")
    pointer = index / "ubicacion.json"
    if not pointer.exists():
        return index  # Trabajos anteriores conservan su ubicación original.
    if _redireccion(pointer):
        raise ValueError("El índice del trabajo fue redirigido.")
    try:
        link = _json(pointer)
        if link.get("salida_id"):
            from .salidas import carpeta

            return _carpeta_de_salida(carpeta(link["salida_id"]), link.get("carpeta"))
        case = next((c for c in casos(user_id) if c["id"] == link.get("case_id")), None)
        if case is None:
            raise ValueError("El caso de este vídeo no está disponible. Abre su carpeta desde Casos.")
        return _carpeta_del_caso(case, link.get("carpeta"))
    except OSError as exc:
        raise ValueError("No se pudo leer la ubicación del trabajo.") from exc


def crear_raiz(user_id: str, job_id: str, case: dict[str, Any] | None,
               receptor: str, pdb_id: str, task_id: str | None,
               salida: dict[str, Any] | None = None) -> Path:
    index = indice_trabajo(user_id, job_id)
    if salida is not None:
        return _crear_en_salida(index, user_id, job_id, salida, receptor, pdb_id)
    if case is None:
        index.mkdir(parents=True, exist_ok=False)
        return index
    # Releer la autorización: el caso pudo cambiar durante el sondeo de Blender.
    case = next((c for c in casos(user_id) if c["id"] == case["id"]), None)
    if case is None:
        raise ValueError("El caso ya no está disponible para guardar el vídeo.")
    if caso_de_corrida(user_id, task_id, registrados=[case]) is None:
        raise ValueError("La corrida ya no pertenece al caso seleccionado.")
    base = case["ruta"] / "molcy"
    _carpeta_del_caso(case, "001_validacion")
    base.mkdir(exist_ok=True)
    numbers = [int(match[1]) for p in base.iterdir()
               if (match := re.match(r"^(\d+)_", p.name))]
    ascii_name = unicodedata.normalize("NFKD", receptor).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")[:40] or "receptor"
    pdb = re.sub(r"[^A-Za-z0-9]+", "_", pdb_id).strip("_") or "pdb"
    run_id = str(uuid.UUID(task_id))
    name = f"{max(numbers, default=0) + 1:03d}_{slug}_{pdb}_{run_id}"
    root = _carpeta_del_caso(case, name)
    root.mkdir(exist_ok=False)
    created_index = False
    try:
        index.mkdir(parents=True, exist_ok=False)
        created_index = True
        pointer = index / "ubicacion.json"
        pointer.write_text(json.dumps({"case_id": case["id"], "carpeta": name}), encoding="utf-8")
    except (OSError, ValueError):
        if created_index:
            (index / "ubicacion.json").unlink(missing_ok=True)
            index.rmdir()
        root.rmdir()  # Aún vacía: no se elimina ningún archivo del investigador.
        raise
    return root


def _crear_en_salida(index: Path, user_id: str, job_id: str, salida: dict[str, Any],
                     receptor: str, pdb_id: str) -> Path:
    from .salidas import SUBCARPETA, carpeta

    salida = carpeta(salida["id"])  # releer: el disco pudo desaparecer durante el sondeo de Blender
    base = salida["ruta"] / SUBCARPETA
    base.mkdir(exist_ok=True)
    numbers = [int(match[1]) for p in base.iterdir() if (match := re.match(r"^(\d+)_", p.name))]
    ascii_name = unicodedata.normalize("NFKD", receptor).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.lower()).strip("_")[:40] or "receptor"
    pdb = re.sub(r"[^A-Za-z0-9]+", "_", pdb_id).strip("_") or "pdb"
    name = f"{max(numbers, default=0) + 1:03d}_{slug}_{pdb}_{job_id}"
    root = _carpeta_de_salida(salida, name)
    root.mkdir(exist_ok=False)
    created_index = False
    try:
        index.mkdir(parents=True, exist_ok=False)
        created_index = True
        (index / "ubicacion.json").write_text(json.dumps({"salida_id": salida["id"], "carpeta": name}),
                                              encoding="utf-8")
    except (OSError, ValueError):
        if created_index:
            (index / "ubicacion.json").unlink(missing_ok=True)
            index.rmdir()
        root.rmdir()  # aún vacía: no se elimina ningún archivo de la persona
        raise
    return root


def validar_raiz(user_id: str, job_id: str, root: Path) -> None:
    if (_redireccion(root) or not root.is_dir()
            or root.resolve() != raiz_trabajo(user_id, job_id).resolve()):
        raise ValueError("La ruta del trabajo no pertenece al usuario.")


def retirar_indice(user_id: str, job_id: str) -> None:
    index = indice_trabajo(user_id, job_id)
    pointer = index / "ubicacion.json"
    if pointer.is_file():
        pointer.unlink()
        index.rmdir()
