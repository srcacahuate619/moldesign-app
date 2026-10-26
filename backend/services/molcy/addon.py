"""User-requested installation through Blender's official extension manager.

MolDesign never downloads or imports the GPL extension itself.  Blender owns
the repository metadata, package verification, installation and preferences.

Before asking Blender, the helper Python that its extension manager launches is
started with the exact environment it will receive (VM-MOLCY-01): on a Windows
without the Visual C++ x64 runtime it died with 0xC0000135 and Blender only said
«No installable packages marked». Every attempt leaves its full record under
`<data>/molcy/registros/`, and a failure says which step failed.
"""
from __future__ import annotations

import subprocess
import threading
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.local_storage import data_dir
from utils.procesos import BANDERAS_SIN_VENTANA

from . import disk, renderer, installation, runtime_vc
from .process import carpeta_de_proceso


OFFICIAL_REPOSITORY = 'url: "https://extensions.blender.org/api/v1/extensions/"'
PACKAGE = "blender_org.molecularnodes"
#: Lo que imprime Blender cuando no llegó a descargar el catálogo: «Done...» no lo acredita (ver el informe VM-MOLCY-01).
SIN_CATALOGO = ("sync required", "No installable packages marked")
MENSAJE_PYTHON_SIN_VC = ("El Python auxiliar de Blender no arranca: le falta una biblioteca de Microsoft Visual C++ x64 "
                         "(0xC0000135, STATUS_DLL_NOT_FOUND), así que Blender no puede descargar el catálogo de extensiones.")
MENSAJE_VC_DANADO = "El runtime de Visual C++ que trae MolDesign está incompleto o alterado: reinstala MolDesign."
MENSAJE_VC_SIN_COPIAR = ("MolDesign no pudo colocar su runtime junto a ese Python; comprueba que ningún antivirus bloquee la "
                         "carpeta de datos de MolDesign y vuelve a intentarlo.")
MENSAJE_VC_BLENDER_PROPIO = ("MolDesign no modifica tu Blender: usa el Blender de MolDesign (recomendado), que lo resuelve sin "
                             "permisos de administrador.")
MENSAJE_PYTHON_SIN_RESPUESTA = "El Python auxiliar de Blender no respondió en 60 s; Blender no puede instalar extensiones."
MENSAJE_SIN_CATALOGO = ("Blender no pudo descargar el catálogo oficial de extensiones (extensions.blender.org), así que no "
                        "encontró Molecular Nodes.")
MENSAJE_REVISA_LA_CONEXION = "Comprueba la conexión a Internet y vuelve a intentarlo."
MENSAJE_SIN_INSTALAR = "Blender no pudo instalar Molecular Nodes."
_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="molcy-addon")
_lock = threading.Lock()
_state: dict[str, Any] = {"estado": "inactivo"}


def estado() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def iniciar() -> dict[str, Any]:
    capability = renderer.detectar()
    if capability.get("motivo_codigo") != "falta_addon":
        raise ValueError("La instalación sólo está disponible si falta Molecular Nodes.")
    blender = Path(capability["blender"])
    if not blender.is_absolute() or not blender.is_file():
        raise ValueError("No se encontró Blender en una ruta absoluta.")
    with _lock:
        if _state["estado"] == "instalando":
            return dict(_state)
        _state.clear()
        _state.update({"estado": "instalando", "fase": "comprobando", "motivo": None})
        _pool.submit(_instalar, blender)
        return dict(_state)


class _Registro:
    """Todo lo que pasó en un intento, entero, en un archivo: el mensaje de la pantalla es corto y este no."""

    def __init__(self, blender: Path) -> None:
        self.inicio = datetime.now(timezone.utc)
        self.lineas = [f"MolDesign · instalación de Molecular Nodes · {self.inicio.isoformat(timespec='seconds')}",
                       f"Blender: {blender}"]
        self.ruta: Path | None = None

    def paso(self, titulo: str, **datos: Any) -> None:
        self.lineas.append(f"\n== {titulo}")
        for clave, valor in datos.items():
            texto = valor if isinstance(valor, str) else repr(valor)
            self.lineas.append(f"-- {clave}:\n{texto}" if "\n" in texto else f"-- {clave}: {texto}")

    def guardar(self) -> Path | None:
        try:
            carpeta = data_dir() / "molcy" / "registros"
            carpeta.mkdir(parents=True, exist_ok=True)
            ruta = carpeta / f"molecular-nodes-{self.inicio.strftime('%Y%m%dT%H%M%SZ')}.log"
            ruta.write_text("\n".join(self.lineas) + "\n", encoding="utf-8")
            self.ruta = ruta
        except OSError:
            self.ruta = None
        return self.ruta


def _ultima_linea(*salidas: str) -> str:
    lineas = [l.strip() for salida in salidas for l in (salida or "").splitlines() if l.strip()]
    return lineas[-1][-200:] if lineas else ""


def _motivo_python(prueba: dict[str, Any], blender: Path) -> str:
    """Por qué no arrancó el Python auxiliar, dicho como un fallo de arranque y con lo que se puede hacer."""
    administrado = blender.resolve() == installation.blender_path().resolve()
    falta_dll = (isinstance(prueba.get("returncode"), int)
                 and runtime_vc.codigo_windows(prueba["returncode"]) == runtime_vc.STATUS_DLL_NOT_FOUND)
    if falta_dll:
        _, _, problemas = runtime_vc.runtime_verificado()
        # Qué DLL o qué byte falló queda en el registro; la pantalla dice qué hacer.
        siguiente = MENSAJE_VC_DANADO if problemas else MENSAJE_VC_SIN_COPIAR if administrado else MENSAJE_VC_BLENDER_PROPIO
        return f"{MENSAJE_PYTHON_SIN_VC} {siguiente}"
    if prueba.get("codigo") == "timeout":
        return MENSAJE_PYTHON_SIN_RESPUESTA
    detalle = _ultima_linea(prueba.get("stderr", ""), prueba.get("stdout", ""))
    return (f"El Python auxiliar de Blender terminó con {prueba.get('codigo')} antes de poder instalar extensiones."
            + (f" Último mensaje: {detalle}" if detalle else ""))


def _instalar(blender: Path) -> None:
    registro = _Registro(blender)
    try:
        env = installation.environment(blender)
        carpeta, manifiesto, problemas = runtime_vc.runtime_verificado()
        registro.paso("runtime de Visual C++ de MolDesign", carpeta=str(carpeta), version=manifiesto.get("version"),
                      problemas=problemas)
        prueba = runtime_vc.probar_python(blender, env)
        registro.paso("python auxiliar de Blender", **prueba)
        if not prueba["ok"]:
            raise RuntimeError(_motivo_python(prueba, blender))
        repos = subprocess.run([str(blender), "--command", "extension", "repo-list"],
                               capture_output=True, text=True, timeout=90, check=False, env=env,
                               creationflags=BANDERAS_SIN_VENTANA, cwd=carpeta_de_proceso())
        registro.paso("repo-list", returncode=repos.returncode, stdout=repos.stdout, stderr=repos.stderr)
        sections = re.split(r"(?m)^(?=[a-zA-Z_][\w-]*:\s*$)", repos.stdout)
        official = next((part for part in sections if part.startswith("blender_org:")), "")
        if repos.returncode != 0 or OFFICIAL_REPOSITORY not in official:
            raise RuntimeError("Blender no tiene configurado el repositorio oficial de extensiones.")
        directory = re.search(r'(?m)^\s+directory: "([^"]+)"', official)
        if directory is None:
            raise RuntimeError("Blender no informó dónde instala sus extensiones.")
        if disk.free_bytes(Path(directory.group(1))) < disk.GIB:
            raise RuntimeError("Espacio insuficiente para descargar e instalar Molecular Nodes: se requiere 1 GiB libre en el perfil de Blender.")
        with _lock:
            _state["fase"] = "descargando"
        result = subprocess.run([str(blender), "--online-mode", "--command", "extension",
                                 "install", "-s", "-e", PACKAGE],
                                capture_output=True, text=True, timeout=1800, check=False, env=env,
                                creationflags=BANDERAS_SIN_VENTANA, cwd=carpeta_de_proceso())
        registro.paso("install", returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode != 0:
            salida = f"{result.stdout}\n{result.stderr}"
            if any(marca in salida for marca in SIN_CATALOGO):
                raise RuntimeError(f"{MENSAJE_SIN_CATALOGO} {MENSAJE_REVISA_LA_CONEXION}")
            detalle = _ultima_linea(result.stderr, result.stdout)
            raise RuntimeError(MENSAJE_SIN_INSTALAR + (f" Último mensaje: {detalle}" if detalle else ""))
        with _lock:
            _state["fase"] = "verificando"
        capability = renderer.detectar(forzar=True)
        registro.paso("comprobación de Molcy", disponible=capability.get("disponible"), motivo=capability.get("motivo"),
                      molecular_nodes=capability.get("molecular_nodes"))
        if not capability["disponible"]:
            raise RuntimeError(capability["motivo"] or "Molecular Nodes no pasó la comprobación.")
        update = {"estado": "completo", "motivo": None,
                  "version": capability["molecular_nodes"]}
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        registro.paso("resultado", error=f"{type(exc).__name__}: {exc}")
        update = {"estado": "fallido", "motivo": str(exc)[:600]}
    ruta = registro.guardar()
    if ruta is not None:
        update["registro"] = str(ruta)
        if update["estado"] == "fallido":
            update["motivo"] = f"{update['motivo']} Registro completo: {ruta}"
    with _lock:
        _state.clear()
        _state.update(update)
