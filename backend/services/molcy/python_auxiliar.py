"""Un Python con Pillow que sí puede arrancar `correr_caso.ps1` como proceso hijo.

EL FALLO (prueba de la app instalada 1.0.3, 2026-10-13; vídeo 9 del caso Imatinib 1IEP redocking). El Python del
paquete vive en `WindowsApps`, y desde fuera del paquete Windows no lo deja arrancar: «Acceso denegado». El script del
motor lo lanza para dos cosas: añadir el halo a los títulos (contraste.py, necesita Pillow) y sellar el MP4
(sellar_mp4.py, sólo biblioteca estándar). Ninguna de las dos arrancó: el sellado falló (SELLO_FALLO) y el vídeo
quedó sin sello aunque el MP4 existía. El script no detecta el fallo de arranque y sigue.

QUÉ HACE. Copia a la carpeta de datos de Molcy, una sola vez, lo mínimo de ese Python para que corran los dos
scripts: el ejecutable, sus DLL, la biblioteca estándar comprimida, `python311._pth` y la carpeta `PIL`. Pesa unos
35 MiB; el runtime completo pesa 1,4 GiB. La copia vive en una carpeta cuyo nombre es la firma del origen, así que
una copia incompleta o de otra versión nunca se reutiliza.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import threading
from pathlib import Path

from utils.local_storage import data_dir

#: Ficheros de primer nivel del intérprete que hacen falta para arrancarlo.
SUFIJOS_DE_FICHERO = (".exe", ".dll", ".pyd", ".zip")
#: La biblioteca de imagen que usa contraste.py. Pillow vive en `Lib\site-packages` del intérprete (su `._pth`
#: activa `import site`), y la copia conserva esa misma ruta relativa.
CARPETAS = ("Lib/site-packages/PIL",)
NOMBRE_MANIFIESTO = "python-auxiliar.json"
EJECUTABLE = "python.exe"
_cerrojo = threading.Lock()


def _ficheros_del_origen(origen: Path) -> list[Path]:
    """Lo que se copia: los binarios de primer nivel, el `._pth` y la carpeta PIL."""
    if not origen.is_dir():
        raise RuntimeError(f"No está la carpeta del Python de MolDesign: {origen}")
    ficheros = [f for f in origen.iterdir() if f.is_file() and (f.suffix.lower() in SUFIJOS_DE_FICHERO or f.name.endswith("._pth"))]
    for nombre in ("python311.zip", "python311._pth", EJECUTABLE):
        if not any(f.name == nombre for f in ficheros):
            raise RuntimeError(f"Falta {nombre} en el Python de MolDesign ({origen}); no se puede preparar el sellado de Molcy.")
    for carpeta in CARPETAS:
        if not (origen / Path(carpeta)).is_dir():
            raise RuntimeError(f"Falta la carpeta {carpeta} en el Python de MolDesign ({origen}); no se puede añadir el halo de Molcy.")
    return sorted(ficheros)


def _firma(origen: Path) -> dict[str, list[int]]:
    """Tamaño y fecha de cada fichero copiado: si cambian, cambia la carpeta de la copia."""
    firma: dict[str, list[int]] = {}
    for fichero in _ficheros_del_origen(origen):
        info = fichero.stat()
        firma[fichero.name] = [info.st_size, info.st_mtime_ns]
    for carpeta in CARPETAS:
        raiz = origen / Path(carpeta)
        for fichero in sorted(raiz.rglob("*")):
            if fichero.is_file():
                info = fichero.stat()
                firma[f"{carpeta}/{fichero.relative_to(raiz).as_posix()}"] = [info.st_size, info.st_mtime_ns]
    return firma


def _nombre_de_carpeta(firma: dict[str, list[int]]) -> str:
    return hashlib.sha256(json.dumps(firma, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def python_auxiliar(origen: Path | None = None, destino: Path | None = None) -> Path:
    """Devuelve la ruta de un `python.exe` fuera de `WindowsApps` que puede usar el script del motor.

    `origen`: la carpeta del Python de MolDesign (por defecto, la del backend en marcha).
    `destino`: la carpeta de copias (por defecto, `<datos>/molcy/python-auxiliar`).
    """
    origen = Path(origen) if origen is not None else Path(sys.executable).parent
    destino = Path(destino) if destino is not None else data_dir() / "molcy" / "python-auxiliar"
    # Dos renders a la vez no pueden copiar a la vez ni uno borrar la copia que usa el otro.
    with _cerrojo:
        firma = _firma(origen)
        carpeta = destino / _nombre_de_carpeta(firma)
        manifiesto = carpeta / NOMBRE_MANIFIESTO
        if manifiesto.is_file() and (carpeta / EJECUTABLE).is_file():
            return carpeta / EJECUTABLE
        # Una copia sin manifiesto quedó a medias (corte, disco lleno): se rehace desde cero.
        if carpeta.exists():
            shutil.rmtree(carpeta)
        carpeta.mkdir(parents=True)
        for fichero in _ficheros_del_origen(origen):
            shutil.copy2(fichero, carpeta / fichero.name)
        for relativa in CARPETAS:
            destino_carpeta = carpeta / Path(relativa)
            destino_carpeta.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(origen / Path(relativa), destino_carpeta)
        manifiesto.write_text(json.dumps({"origen": str(origen), "firma": firma}, indent=2, sort_keys=True), encoding="utf-8")
        return carpeta / EJECUTABLE
