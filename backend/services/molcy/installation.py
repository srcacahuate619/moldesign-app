"""Blender portable bajo demanda; sólo fuentes oficiales y promoción verificada.

Se instala en la carpeta de DATOS del usuario (`LOCAL_DATA_DIR/molcy/blender/`), nunca junto al ejecutable de MolDesign:
la carpeta del programa es de sólo lectura en la build de la Microsoft Store (`WindowsApps`, ni el administrador escribe
allí) y en una instalación por máquina exige elevación. Escribir donde el usuario ya escribe sus datos no pide permisos, no
lanza PowerShell y no deja un proceso elevado. El ZIP se valida (rutas, enlaces, tamaño, SHA-256 fijado) antes de extraerlo.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import urllib.request
import urllib.parse
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from typing import Any

from utils.local_storage import data_dir
from . import disk, motor, runtime_vc

VERSION = "5.2.2"
ARCHIVE_ROOT = f"blender-{VERSION}-windows-x64"
URL = f"https://download.blender.org/release/Blender5.2/{ARCHIVE_ROOT}.zip"
# Blender Foundation, blender-5.2.2.sha256, consultado 2026-09-29.
SHA256 = "3849d17a682cba006075aaa3f3597ecb5c9c30ec31035b2e092c53e40679b535"
DOWNLOAD_BYTES = 404453484
MAX_UNPACKED = 3 * disk.GIB
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="molcy-blender")
_lock = threading.RLock()
_cancel = threading.Event()
_state: dict[str, Any] = {"estado": "inactivo"}


def blender_path() -> Path:
    """Dónde vive el Blender administrado: siempre en la carpeta de datos del usuario, que siempre es escribible."""
    return data_dir() / "molcy" / "blender" / ARCHIVE_ROOT / "blender.exe"


def settings_path() -> Path:
    return data_dir() / "molcy" / "configuracion.json"


def settings() -> dict[str, Any]:
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def configure(mode: str, blender: str | None, engine: str | None) -> None:
    if mode not in {"administrado", "existente"}:
        raise ValueError("Modo de Blender inválido")
    if mode == "existente":
        path = Path(blender or "")
        if not path.is_absolute() or not path.is_file() or path.name.lower() != "blender.exe":
            raise ValueError("Elige el blender.exe existente con su ruta absoluta.")
        blender = str(path.resolve())
    if engine:
        if not motor.motor_propio_permitido():
            # El cierre de MolDesign lo pone el motor incluido: no se elige otro desde la aplicación.
            raise ValueError("MolDesign usa el motor Molcy incluido; elegir otro motor no está disponible.")
        path = Path(engine)
        if not path.is_absolute() or not (path / "scripts" / "maestro.py").is_file():
            raise ValueError("Elige la carpeta del motor Molcy, que contiene scripts/maestro.py.")
        engine = str(path.resolve())
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"modo": mode, "blender": blender, "motor": engine}), encoding="utf-8")
    os.replace(temp, path)


def environment(blender: Path) -> dict[str, str]:
    """Entorno de TODO subproceso de Blender. Con el Blender administrado, además, deja su Python auxiliar listo para arrancar.

    El Python que Blender lanza para el gestor de extensiones necesita el runtime de Visual C++ x64, que un Windows limpio no
    trae (VM-MOLCY-01): en el administrado se copian a su lado las DLL verificadas de MolDesign, y en cualquier Blender la
    carpeta verificada va delante del PATH del subproceso. Ver `runtime_vc`.
    """
    managed = blender_path()
    env = dict(os.environ)
    if blender.resolve() == managed.resolve():
        profile = data_dir() / "molcy" / "perfil_blender" / VERSION
        # Perfiles independientes: no modifica preferencias del Blender personal.
        env.update({"BLENDER_USER_RESOURCES": str(profile),
                    "BLENDER_USER_CONFIG": str(profile / "config"),
                    "BLENDER_USER_EXTENSIONS": str(profile / "extensions")})
        python = runtime_vc.python_de_blender(blender)
        if python is not None:
            runtime_vc.desplegar_junto_a_python(python)
    return runtime_vc.con_runtime_en_path(env)


def status() -> dict[str, Any]:
    with _lock:
        value = dict(_state)
    path = blender_path()
    return {**value, "version": VERSION, "descarga_bytes": DOWNLOAD_BYTES,
            "reserva_bytes": MAX_UNPACKED + DOWNLOAD_BYTES + disk.RESERVE_BYTES,
            "ruta": str(path), "instalado": path.is_file(), "configuracion": settings()}


def _update(**fields: Any) -> None:
    with _lock:
        _state.update(fields)


def start() -> dict[str, Any]:
    path = blender_path()
    with _lock:
        if _state.get("estado") == "instalando":
            return status()
        if path.is_file():
            raise ValueError("La instalación administrada ya existe; selecciona ese Blender o configura uno existente.")
        # Descarga (ZIP) y extracción conviven en la misma carpeta de datos: una sola comprobación, con la reserva.
        if disk.free_bytes(path.parent) < MAX_UNPACKED + DOWNLOAD_BYTES + disk.RESERVE_BYTES:
            raise ValueError("Espacio insuficiente en la unidad de datos de MolDesign: se reservan 4,4 GiB.")
        _cancel.clear()
        _state.clear()
        _update(estado="instalando", fase="descargando", recibidos_bytes=0, motivo=None)
        _pool.submit(_install, path)
        return status()


def cancel() -> dict[str, Any]:
    with _lock:
        if _state.get("estado") == "instalando":
            if _state.get("fase") == "instalando":
                raise ValueError("La instalación ya está aplicándose; espera a que termine.")
            _cancel.set()
    return status()


def _check_cancel() -> None:
    if _cancel.is_set():
        raise InterruptedError("Descarga de Blender cancelada.")


def _download(archive: Path) -> None:
    request = urllib.request.Request(URL + "?molcy=1", headers={"User-Agent": "Mozilla/5.0 MolDesign-Molcy/1.0.2"})
    digest = hashlib.sha256()
    received = 0
    with urllib.request.urlopen(request, timeout=45) as response, archive.open("wb") as stream:
        if urllib.parse.urlparse(response.url).hostname != "download.blender.org":
            raise ValueError("La descarga se redirigió fuera del servidor oficial de Blender.")
        while chunk := response.read(1024 * 1024):
            _check_cancel()
            received += len(chunk)
            if received > DOWNLOAD_BYTES:
                raise ValueError("El ZIP de Blender excede el tamaño oficial.")
            if disk.free_bytes(archive.parent) < disk.RESERVE_BYTES + len(chunk):
                raise OSError("Espacio insuficiente durante la descarga de Blender.")
            stream.write(chunk)
            digest.update(chunk)
            _update(recibidos_bytes=received)
    if received != DOWNLOAD_BYTES or digest.hexdigest() != SHA256:
        raise ValueError("Blender no coincide con el tamaño y SHA-256 oficiales; no se instalará.")


def _validate_zip(archive: Path) -> None:
    with zipfile.ZipFile(archive) as package:
        total = 0
        for item in package.infolist():
            path = PurePosixPath(item.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != ARCHIVE_ROOT:
                raise ValueError("El ZIP contiene una ruta fuera de la instalación de Blender.")
            if (item.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("El ZIP contiene un enlace simbólico.")
            total += item.file_size
        if total > MAX_UNPACKED or f"{ARCHIVE_ROOT}/blender.exe" not in package.namelist():
            raise ValueError("El ZIP no tiene la estructura o tamaño esperado de Blender.")


def _sha256_archivo(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _promote(archive: Path, target: Path) -> None:
    """Extrae el ZIP oficial a una carpeta temporal hermana y lo promueve con un renombrado.

    El SHA-256 fijado se repite aquí aunque `_download` ya lo comprobó: esta función sólo extrae el ZIP oficial, llegue
    por el camino que llegue. `_validate_zip` ya rechazó rutas absolutas, `..` y enlaces simbólicos.
    """
    if target.resolve() != blender_path().parent.resolve():
        raise ValueError("El destino no pertenece a la instalación administrada de MolDesign.")
    if _sha256_archivo(archive) != SHA256:
        raise ValueError("Blender no coincide con el SHA-256 oficial; no se instalará.")
    if target.exists():
        raise RuntimeError("La instalación administrada ya existe.")
    stage = target.parent / (".blender-" + uuid.uuid4().hex)
    try:
        stage.mkdir(parents=True)
        _update(fase="instalando")
        with zipfile.ZipFile(archive) as package:
            package.extractall(stage)
        source = stage / ARCHIVE_ROOT
        if not (source / "blender.exe").is_file():
            raise RuntimeError("El ZIP no contiene blender.exe.")
        os.replace(source, target)
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise RuntimeError(
            "Blender no se instaló. Comprueba el espacio libre y que ningún antivirus bloquee la carpeta de datos de MolDesign."
        ) from exc
    finally:
        # `stage` es una carpeta UUID creada aquí, dentro de la carpeta de datos de Blender; nunca la raíz.
        shutil.rmtree(stage, ignore_errors=True)


def _install(blender: Path) -> None:
    cache = data_dir() / "molcy" / "descargas" / uuid.uuid4().hex
    try:
        cache.mkdir(parents=True)
        archive = cache / "blender.zip"
        _download(archive)
        _update(fase="verificando")
        _validate_zip(archive)
        _check_cancel()
        if disk.free_bytes(blender.parent) < MAX_UNPACKED + disk.RESERVE_BYTES:
            raise OSError("Espacio insuficiente antes de instalar Blender.")
        _promote(archive, blender.parent)
        # Instalado quiere decir que su Python auxiliar puede arrancar, también en un Windows sin Visual C++ (VM-MOLCY-01).
        python = runtime_vc.python_de_blender(blender)
        if python is not None:
            runtime_vc.desplegar_junto_a_python(python)
        configure("administrado", None, settings().get("motor"))
        _update(estado="completo", fase="completo", motivo=None)
    except InterruptedError as exc:
        _update(estado="cancelado", motivo=str(exc))
    except Exception as exc:
        _update(estado="fallido", motivo=str(exc)[:600])
    finally:
        # Sólo la carpeta UUID que creó este trabajo, nunca archivos del usuario.
        if cache.is_dir():
            shutil.rmtree(cache, ignore_errors=True)
