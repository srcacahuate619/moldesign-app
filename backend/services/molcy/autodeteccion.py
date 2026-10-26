"""Dónde puede tener el usuario su Blender, sin lanzarlo.

Un investigador instala Blender de muchas maneras y ninguna es «la» manera: el instalador oficial (a `Program Files` o a la carpeta que
elija —en esta máquina a la raíz de `E:\\`, y entonces ninguna búsqueda en `Program Files` lo ve—), Steam (con bibliotecas en otros
discos), la Microsoft Store (en `WindowsApps`, que no se puede listar), Scoop, un ZIP descomprimido en Descargas… Esta pieza junta las
pistas que Windows deja y devuelve rutas a `blender.exe` con su origen y, si se puede saber sin ejecutarlo, su versión.

Reglas:

* **No ejecuta nada.** La versión sale de la carpeta `X.Y` que Blender trae junto a su `.exe`, del nombre del paquete de la Tienda o del
  registro. Lanzar cada candidato costaría segundos por cada uno y abriría procesos de programas que no son nuestros.
* **Sin PowerShell ni `Get-AppxPackage`**: el registro (`winreg`) y el sistema de archivos bastan y no abren consolas.
* **Sólo discos fijos.** Un disco de red o una unidad extraíble puede tardar segundos en contestar; no se recorren.
* **Todo es inyectable** (`Entorno`): las pruebas dan un registro y unos discos de mentira, así que se prueban en cualquier máquina.
* Ninguna pista es obligatoria: una clave ausente, ilegible o un permiso denegado sólo quitan ese candidato.
"""
from __future__ import annotations

import ctypes
import os
import re
import sys
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Protocol

#: Origen de cada candidato; el orden es la preferencia en un empate de versión (el instalador oficial, antes que lo demás).
PROGRAMA, STEAM, TIENDA, GESTOR, ASOCIACION, RUTA, PORTATIL = (
    "programa", "steam", "tienda", "gestor", "asociacion", "ruta", "portatil")
ORIGENES = (PROGRAMA, STEAM, TIENDA, GESTOR, ASOCIACION, RUTA, PORTATIL)

APP_ID_STEAM = "365670"
EJECUTABLE = "blender.exe"
#: Cuánto vale un resultado antes de volver a mirar el disco: la pantalla pide el estado al cargar y al pulsar «Comprobar».
VIGENCIA_S = 30.0
_VERSION_CARPETA = re.compile(r"^(\d+)\.(\d+)$")
_VERSION_PAQUETE = re.compile(r"_(\d+)\.(\d+)(?:\.(\d+))?(?:\.\d+)?_")
_VERSION_TEXTO = re.compile(r"^\s*(\d+)\.(\d+)(?:\.(\d+))?")

Version = tuple[int, ...]


@dataclass(frozen=True)
class Candidato:
    ruta: Path
    origen: str
    version: Version | None = None
    #: Otras pistas que llevaron al mismo ejecutable (p. ej. el instalador oficial y la asociación del `.blend`).
    tambien: tuple[str, ...] = ()

    @property
    def version_texto(self) -> str | None:
        return ".".join(str(n) for n in self.version) if self.version else None


class Registro(Protocol):
    """Lo mínimo que se lee del registro de Windows. Las claves no distinguen mayúsculas, como en Windows."""

    def valores(self, raiz: str, clave: str, *, vista: str = "") -> dict[str, object]: ...
    def subclaves(self, raiz: str, clave: str, *, vista: str = "") -> list[str]: ...


class RegistroWindows:
    """`winreg`, tragándose cualquier error: una clave que no existe o no se puede leer es «sin pista»."""

    def _abrir(self, raiz: str, clave: str, vista: str):
        import winreg
        base = {"HKLM": winreg.HKEY_LOCAL_MACHINE, "HKCU": winreg.HKEY_CURRENT_USER}[raiz]
        extra = {"64": winreg.KEY_WOW64_64KEY, "32": winreg.KEY_WOW64_32KEY}.get(vista, 0)
        return winreg.OpenKey(base, clave, 0, winreg.KEY_READ | extra)

    def valores(self, raiz: str, clave: str, *, vista: str = "") -> dict[str, object]:
        if sys.platform != "win32":
            return {}
        import winreg
        encontrados: dict[str, object] = {}
        try:
            with self._abrir(raiz, clave, vista) as abierta:
                indice = 0
                while True:
                    try:
                        nombre, valor, _tipo = winreg.EnumValue(abierta, indice)
                    except OSError:
                        break
                    encontrados[nombre] = valor
                    indice += 1
        except OSError:
            return {}
        return encontrados

    def subclaves(self, raiz: str, clave: str, *, vista: str = "") -> list[str]:
        if sys.platform != "win32":
            return []
        import winreg
        nombres: list[str] = []
        try:
            with self._abrir(raiz, clave, vista) as abierta:
                indice = 0
                while True:
                    try:
                        nombres.append(winreg.EnumKey(abierta, indice))
                    except OSError:
                        break
                    indice += 1
        except OSError:
            return []
        return nombres


def _unidades_fijas() -> list[Path]:
    """Raíces de los discos fijos (`DRIVE_FIXED`). Los de red y los extraíbles no se tocan: pueden tardar segundos en contestar."""
    if sys.platform != "win32":
        return []
    try:
        mascara = ctypes.windll.kernel32.GetLogicalDrives()  # type: ignore[attr-defined]
        raices = []
        for indice in range(26):
            if mascara & (1 << indice):
                letra = chr(ord("A") + indice) + ":\\"
                if ctypes.windll.kernel32.GetDriveTypeW(letra) == 3:  # type: ignore[attr-defined]
                    raices.append(Path(letra))
        return raices
    except (OSError, AttributeError):
        return []


@dataclass
class Entorno:
    """Todo lo que la búsqueda lee de la máquina. Por defecto, la máquina real."""
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    registro: Registro = field(default_factory=RegistroWindows)
    unidades: list[Path] | None = None

    def discos(self) -> list[Path]:
        return _unidades_fijas() if self.unidades is None else list(self.unidades)

    def variable(self, nombre: str) -> str | None:
        for clave, valor in self.env.items():  # Windows no distingue mayúsculas en el entorno
            if clave.lower() == nombre.lower() and valor:
                return valor
        return None

    def carpeta(self, nombre: str, *resto: str) -> Path | None:
        base = self.variable(nombre)
        return Path(base, *resto) if base else None


# --- Versión sin ejecutar -----------------------------------------------------------------------------------------------------

def version_de_carpeta(exe: Path) -> Version | None:
    """La carpeta `X.Y` que Blender trae junto a su ejecutable (`5.2/`, `4.5/`): la mayor, o None si no hay o no se puede listar."""
    mejor: Version | None = None
    try:
        for hijo in exe.parent.iterdir():
            m = _VERSION_CARPETA.match(hijo.name)
            if m and hijo.is_dir():
                version = (int(m.group(1)), int(m.group(2)))
                if mejor is None or version > mejor:
                    mejor = version
    except OSError:
        return None
    return mejor


def version_de_texto(texto: object) -> Version | None:
    """`5.2.2` o `5.2` (como `DisplayVersion` del registro); lo que no empieza por dos números no es una versión."""
    m = _VERSION_TEXTO.match(str(texto or ""))
    if not m:
        return None
    return tuple(int(g) for g in m.groups() if g is not None)


def _mas_precisa(a: Version | None, b: Version | None) -> Version | None:
    """La que tenga más componentes si coinciden en `X.Y`; si no, la primera que exista."""
    if a and b and a[:2] == b[:2]:
        return a if len(a) >= len(b) else b
    return a or b


def _es_blender(ruta: Path) -> bool:
    try:
        return ruta.name.lower() == EJECUTABLE and ruta.is_file()
    except OSError:  # permiso denegado, ruta demasiado larga…: no es un candidato
        return False


# --- Orígenes -----------------------------------------------------------------------------------------------------------------

def _con_version_numerica(carpetas: Iterable[Path]) -> list[Path]:
    """Ordena de más nueva a más vieja las carpetas `Blender 5.2`, `Blender 4.5`… (comparación numérica, no de texto: 10 > 9)."""
    def clave(carpeta: Path):
        m = re.search(r"(\d+)(?:\.(\d+))?", carpeta.name)
        return (int(m.group(1)), int(m.group(2) or 0)) if m else (-1, -1)
    return sorted(carpetas, key=clave, reverse=True)


def _hijos(carpeta: Path, patron: str) -> list[Path]:
    try:
        return [p for p in carpeta.glob(patron)]
    except OSError:
        return []


def _carpetas_de_programas(entorno: Entorno) -> list[Path]:
    """`Program Files`, su versión de 32 bits, la de otros discos y la instalación por usuario del instalador oficial."""
    bases: list[Path] = []
    for nombre in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        carpeta = entorno.carpeta(nombre)
        if carpeta:
            bases.append(carpeta)
    local = entorno.carpeta("LOCALAPPDATA", "Programs")
    if local:
        bases.append(local)
    for disco in entorno.discos():
        bases += [disco / "Program Files", disco / "Program Files (x86)", disco]
    return bases


def _desde_programas(entorno: Entorno) -> Iterable[Candidato]:
    for base in _carpetas_de_programas(entorno):
        for carpeta in _con_version_numerica(_hijos(base / "Blender Foundation", "Blender *")):
            yield Candidato(carpeta / EJECUTABLE, PROGRAMA)


def _desde_uninstall(entorno: Entorno) -> Iterable[Candidato]:
    """El instalador oficial (MSI, también el de winget y Chocolatey) anota `InstallLocation`, que el usuario pudo cambiar a cualquier carpeta."""
    clave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for raiz, vista in (("HKLM", "64"), ("HKLM", "32"), ("HKCU", "")):
        for sub in entorno.registro.subclaves(raiz, clave, vista=vista):
            datos = entorno.registro.valores(raiz, f"{clave}\\{sub}", vista=vista)
            nombre = str(datos.get("DisplayName") or "")
            editor = str(datos.get("Publisher") or "")
            if nombre.strip().lower() != "blender" and not nombre.lower().startswith("blender "):
                continue
            if "blender foundation" not in editor.lower():
                continue  # «Blender» a secas lo usan otros programas; el del instalador oficial firma la Fundación
            ubicacion = str(datos.get("InstallLocation") or "").strip().strip('"')
            if ubicacion:
                yield Candidato(Path(ubicacion) / EJECUTABLE, PROGRAMA, version_de_texto(datos.get("DisplayVersion")))


def _desde_app_paths(entorno: Entorno) -> Iterable[Candidato]:
    clave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe"
    for raiz, vista in (("HKLM", "64"), ("HKLM", "32"), ("HKCU", "")):
        valor = entorno.registro.valores(raiz, clave, vista=vista).get("")
        if valor:
            yield Candidato(Path(str(valor).strip('"')), PROGRAMA)


def _primer_argumento(orden: str) -> str:
    """El programa de una orden de shell: `"E:\\x y\\blender-launcher.exe" "%1"` → `E:\\x y\\blender-launcher.exe`."""
    orden = orden.strip()
    if orden.startswith('"'):
        fin = orden.find('"', 1)
        return orden[1:fin] if fin > 0 else orden[1:]
    m = re.match(r"^(.*?\.exe)\b", orden, re.IGNORECASE)
    return m.group(1) if m else orden.split(" ", 1)[0]


def _desde_asociacion(entorno: Entorno) -> Iterable[Candidato]:
    """El programa que Windows abre con un `.blend`: delata también una instalación portátil que el usuario asoció.

    Blender asocia su LANZADOR (`blender-launcher.exe`), que vive junto a `blender.exe`: se toma el hermano.
    """
    progids: list[str] = []
    for raiz in ("HKCU", "HKLM"):
        base = r"SOFTWARE\Classes\.blend"
        predeterminado = entorno.registro.valores(raiz, base).get("")
        if predeterminado:
            progids.append(str(predeterminado))
        progids += list(entorno.registro.valores(raiz, base + r"\OpenWithProgids"))
    progids += list(entorno.registro.valores(
        "HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.blend\OpenWithProgids"))
    elegido = entorno.registro.valores(
        "HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.blend\UserChoice").get("ProgId")
    if elegido:
        progids.append(str(elegido))
    vistos: set[str] = set()
    for progid in progids:
        if progid.lower() in vistos:
            continue
        vistos.add(progid.lower())
        for raiz in ("HKCU", "HKLM"):
            orden = entorno.registro.valores(raiz, rf"SOFTWARE\Classes\{progid}\shell\open\command").get("")
            if not orden:
                continue
            programa = Path(_primer_argumento(str(orden)))
            if programa.name.lower() in {"blender.exe", "blender-launcher.exe"}:
                yield Candidato(programa.with_name(EJECUTABLE), ASOCIACION)


# Steam ---------------------------------------------------------------------------------------------------------------------

def _rutas_de_bibliotecas_steam(texto: str) -> list[str]:
    """Las `"path"` de un `libraryfolders.vdf` (formato de Valve: las barras invertidas van duplicadas)."""
    return [m.group(1).replace("\\\\", "\\") for m in re.finditer(r'"path"\s+"((?:[^"\\]|\\.)*)"', texto)]


def _instalacion_en_biblioteca(biblioteca: Path) -> Path:
    """`<biblioteca>\\steamapps\\common\\<installdir>\\blender.exe`; `installdir` sale del manifiesto de la app si existe."""
    pasos = biblioteca / "steamapps"
    nombre = "Blender"
    try:
        manifiesto = (pasos / f"appmanifest_{APP_ID_STEAM}.acf").read_text(encoding="utf-8", errors="replace")
        m = re.search(r'"installdir"\s+"((?:[^"\\]|\\.)*)"', manifiesto)
        if m:
            nombre = m.group(1).replace("\\\\", "\\")
    except OSError:
        pass
    return pasos / "common" / nombre / EJECUTABLE


def _desde_steam(entorno: Entorno) -> Iterable[Candidato]:
    raices: list[Path] = []
    for raiz, clave, valor in (("HKCU", r"SOFTWARE\Valve\Steam", "SteamPath"),
                               ("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
                               ("HKLM", r"SOFTWARE\Valve\Steam", "InstallPath")):
        ruta = entorno.registro.valores(raiz, clave).get(valor)
        if ruta:
            raices.append(Path(str(ruta)))
    pf86 = entorno.carpeta("ProgramFiles(x86)")
    if pf86:
        raices.append(pf86 / "Steam")
    bibliotecas: list[Path] = list(raices)
    for raiz in raices:
        try:
            texto = (raiz / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        bibliotecas += [Path(p) for p in _rutas_de_bibliotecas_steam(texto)]
    # Una biblioteca también puede estar en un disco sin que Steam esté registrado aquí (un disco movido de máquina).
    for disco in entorno.discos():
        bibliotecas += [disco / "SteamLibrary", disco / "Steam"]
    for biblioteca in bibliotecas:
        yield Candidato(_instalacion_en_biblioteca(biblioteca), STEAM)


# Microsoft Store -----------------------------------------------------------------------------------------------------------

#: Dónde el sistema anota los paquetes instalados para el usuario, con su carpeta REAL (puede estar en otro disco: `E:\\WindowsApps`).
_PAQUETES = r"SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"
PAQUETE_BLENDER = "blenderfoundation.blender"


def _ejecutable_de_paquete(raiz: Path) -> Path | None:
    """El `.exe` que declara el `AppxManifest.xml` del paquete (legible aunque `WindowsApps` no se pueda listar)."""
    try:
        arbol = ET.parse(raiz / "AppxManifest.xml")
    except (OSError, ET.ParseError):
        arbol = None
    if arbol is not None:
        for elemento in arbol.iter():
            if elemento.tag.rsplit("}", 1)[-1] == "Application":
                ejecutable = (elemento.get("Executable") or "").replace("\\", "/")
                if ejecutable.lower().endswith(".exe"):
                    return raiz.joinpath(*ejecutable.split("/"))
    # Sin manifiesto legible: las dos disposiciones conocidas.
    for relativa in (("Blender", EJECUTABLE), (EJECUTABLE,)):
        if (raiz.joinpath(*relativa)).is_file():
            return raiz.joinpath(*relativa)
    return None


def _desde_tienda(entorno: Entorno, *, paquete: str = PAQUETE_BLENDER) -> Iterable[Candidato]:
    """Los paquetes de la Microsoft Store cuyo nombre es `BlenderFoundation.Blender`; sin `Get-AppxPackage` (PowerShell abriría una consola)."""
    for sub in entorno.registro.subclaves("HKCU", _PAQUETES):
        if not sub.lower().startswith(paquete + "_"):
            continue
        carpeta = entorno.registro.valores("HKCU", f"{_PAQUETES}\\{sub}").get("PackageRootFolder")
        if not carpeta:
            continue
        ejecutable = _ejecutable_de_paquete(Path(str(carpeta)))
        if ejecutable is not None:
            m = _VERSION_PAQUETE.search(sub)
            version = tuple(int(g) for g in m.groups() if g is not None) if m else None
            yield Candidato(ejecutable, TIENDA, version)


# Gestores de paquetes, PATH y carpetas habituales --------------------------------------------------------------------------

def _desde_scoop(entorno: Entorno) -> Iterable[Candidato]:
    bases = [entorno.carpeta("SCOOP"), entorno.carpeta("USERPROFILE", "scoop"),
             entorno.carpeta("SCOOP_GLOBAL"), entorno.carpeta("ProgramData", "scoop")]
    for base in filter(None, bases):
        yield Candidato(base / "apps" / "blender" / "current" / EJECUTABLE, GESTOR)
        for carpeta in _con_version_numerica(_hijos(base / "apps" / "blender", "[0-9]*")):
            yield Candidato(carpeta / EJECUTABLE, GESTOR)
    choco = entorno.carpeta("ChocolateyInstall") or entorno.carpeta("ProgramData", "chocolatey")
    if choco:
        for carpeta in _hijos(choco / "lib", "blender*"):
            for exe in _hijos(carpeta, "tools/**/blender.exe") + _hijos(carpeta, "tools/blender.exe"):
                yield Candidato(exe, GESTOR)
    enlaces = entorno.carpeta("LOCALAPPDATA", "Microsoft", "WinGet", "Links", EJECUTABLE)
    if enlaces:
        yield Candidato(enlaces, GESTOR)


def _desde_path(entorno: Entorno) -> Iterable[Candidato]:
    """Las carpetas del `PATH`, SIN la carpeta actual (que `shutil.which` consulta primero en Windows) ni entradas relativas."""
    for entrada in (entorno.variable("PATH") or "").split(os.pathsep):
        carpeta = Path(entrada.strip().strip('"'))
        if entrada.strip() and carpeta.is_absolute():
            yield Candidato(carpeta / EJECUTABLE, RUTA)


def _desde_carpetas_habituales(entorno: Entorno) -> Iterable[Candidato]:
    """El ZIP descomprimido (`blender-5.2.2-windows-x64\\`) donde la gente lo deja, y la raíz de cada disco fijo."""
    usuario = entorno.carpeta("USERPROFILE")
    bases: list[Path] = []
    if usuario:
        bases += [usuario, usuario / "Downloads", usuario / "Desktop", usuario / "Documents", usuario / "Descargas",
                  usuario / "Escritorio"]
    for nombre in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        nube = entorno.carpeta(nombre)
        if nube:
            bases += [nube / "Desktop", nube / "Documents", nube / "Escritorio", nube / "Documentos"]
    bases += entorno.discos()
    for base in bases:
        yield Candidato(base / EJECUTABLE, PORTATIL)
        for carpeta in _con_version_numerica(_hijos(base, "[Bb]lender*")):
            yield Candidato(carpeta / EJECUTABLE, PORTATIL)


_ORIGENES = (_desde_uninstall, _desde_app_paths, _desde_programas, _desde_steam, _desde_tienda, _desde_scoop,
             _desde_asociacion, _desde_path, _desde_carpetas_habituales)


# --- Resultado ------------------------------------------------------------------------------------------------------------------

def _clave(ruta: Path) -> str:
    try:
        return os.path.normcase(os.path.realpath(ruta))
    except OSError:
        return os.path.normcase(str(ruta))


def buscar(entorno: Entorno | None = None) -> list[Candidato]:
    """Todas las instalaciones de Blender que hay rastro de que existen, SIN duplicados, de mejor a peor.

    «Mejor»: la versión más alta primero (las de versión desconocida, después de las conocidas); a igual versión, el origen más fiable
    (`ORIGENES`). El mismo `blender.exe` hallado por varias pistas aparece una vez, con las demás en `tambien`.
    """
    entorno = entorno or Entorno()
    halladas: dict[str, Candidato] = {}
    for origen in _ORIGENES:
        try:
            candidatos = list(origen(entorno))
        except Exception:  # una pista que revienta (registro corrupto, permiso…) no impide usar las demás
            continue
        for candidato in candidatos:
            if not _es_blender(candidato.ruta):
                continue
            version = _mas_precisa(candidato.version, version_de_carpeta(candidato.ruta))
            llave = _clave(candidato.ruta)
            previo = halladas.get(llave)
            if previo is None:
                halladas[llave] = Candidato(candidato.ruta, candidato.origen, version)
            else:
                otras = previo.tambien
                if candidato.origen != previo.origen and candidato.origen not in otras:
                    otras = (*otras, candidato.origen)
                halladas[llave] = Candidato(previo.ruta, previo.origen, _mas_precisa(previo.version, version), otras)

    def preferencia(c: Candidato):
        # Versión mayor primero, comparando hasta el parche (5.2 y 5.2.0 empatan); sin versión conocida, al final.
        numeros = ((c.version or ()) + (0, 0, 0))[:3]
        return (c.version is None, tuple(-n for n in numeros), ORIGENES.index(c.origen), str(c.ruta).lower())

    return sorted(halladas.values(), key=preferencia)


def apto(candidato: Candidato, minima: tuple[int, int]) -> bool | None:
    """True/False si la versión se conoce; None si no (se sabrá al sondear: el sondeo es quien decide)."""
    if candidato.version is None:
        return None
    return candidato.version[:2] >= minima


def para_la_pantalla(candidatos: list[Candidato], minima: tuple[int, int]) -> list[dict]:
    return [{"ruta": str(c.ruta), "origen": c.origen, "version": c.version_texto, "apto": apto(c, minima),
             "tambien": list(c.tambien)} for c in candidatos]


def ordenar_para_usar(candidatos: list[Candidato], minima: tuple[int, int]) -> list[Candidato]:
    """Los que sirven primero (versión suficiente o desconocida) y detrás los demasiado viejos, de más nuevo a más viejo.

    Si sólo hay viejos, el primero de la lista es el más nuevo de ellos y el sondeo dirá por qué no sirve. La ordenación es estable:
    dentro de cada grupo se conserva el orden de `buscar`.
    """
    return sorted(candidatos, key=lambda c: apto(c, minima) is False)


# --- Caché ----------------------------------------------------------------------------------------------------------------------

_lock = threading.Lock()
_guardado: dict[str, object] = {}


def listar(*, forzar: bool = False, entorno: Entorno | None = None) -> list[Candidato]:
    """`buscar` con una vigencia corta: la pantalla pregunta al cargar, al cambiar de idioma y al pulsar «Comprobar»."""
    if entorno is not None:  # un entorno inyectado es de una prueba: nunca toca la caché
        return buscar(entorno)
    with _lock:
        if not forzar and _guardado and time.monotonic() - float(_guardado["t"]) < VIGENCIA_S:  # type: ignore[arg-type]
            return list(_guardado["candidatos"])  # type: ignore[arg-type]
        candidatos = buscar()
        _guardado.update(t=time.monotonic(), candidatos=list(candidatos))
        return candidatos


def preferidos(minima: tuple[int, int]) -> list[Candidato]:
    """`listar()` ordenado para usarlo: el primero es el que Molcy probará."""
    return ordenar_para_usar(listar(), minima)


def invalidar() -> None:
    with _lock:
        _guardado.clear()
