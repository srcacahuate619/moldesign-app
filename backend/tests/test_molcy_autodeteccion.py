"""La autodetección de Blender encuentra las instalaciones que un investigador real tiene, sin ejecutarlas.

# Qué se midió (2026-10-04, la máquina del propietario)

El detector anterior sólo miraba `%ProgramFiles%\\Blender Foundation\\Blender *`. En esta máquina esa carpeta no existe: Blender 5.2.2
se instaló con el MSI oficial eligiendo la raíz del disco (`InstallLocation = E:\\`, `E:\\blender.exe`), de modo que la aplicación decía
«No se encontró Blender» con uno instalado y apto. Las pistas que Windows deja y que ahora se leen, tal como se vieron aquí:

* `HKLM\\...\\Uninstall\\{GUID}`: `DisplayName = Blender`, `Publisher = Blender Foundation`, `DisplayVersion = 5.2.2`, `InstallLocation = E:\\`.
* `.blend` → `blender.5.2` → `"E:\\blender-launcher.exe" "%1"` (el LANZADOR, no `blender.exe`: se toma su hermano).
* Steam: `HKCU\\Software\\Valve\\Steam\\SteamPath = c:/program files (x86)/steam` y tres bibliotecas en `libraryfolders.vdf` (con las barras
  invertidas duplicadas), dos de ellas en otros discos.
* Tienda: `HKCU\\...\\AppModel\\Repository\\Packages\\<paquete>` con `PackageRootFolder` (244 paquetes legibles sin ser administrador);
  `WindowsApps` NO se puede listar (`PermissionError`), pero dentro de la carpeta de un paquete conocido sí se lee `AppxManifest.xml`.

Estas pruebas dan un registro y unos discos de mentira (cualquiera las ejecuta en cualquier máquina) y tienen controles negativos:
quitada la pista, el candidato desaparece. Al final hay unas pocas que miran la máquina real, sólo para lo que no admite mentira.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.molcy import autodeteccion as ad
from services.molcy import renderer
from services.molcy.autodeteccion import Candidato, Entorno

MINIMA = (5, 2)


# --- Un registro y unos discos de mentira ---------------------------------------------------------------------------------------

class RegistroFalso:
    """`{(raiz, clave): {nombre: valor}}`. Las claves no distinguen mayúsculas (como en Windows) y los nombres de subclave conservan las suyas."""

    def __init__(self, arbol=None):
        self.arbol: dict[tuple[str, str], dict] = {}
        self.nombres: dict[tuple[str, str], str] = {}
        for (raiz, clave), valores in (arbol or {}).items():
            self.poner(raiz, clave, valores)

    @staticmethod
    def _k(raiz, clave):
        return raiz.upper(), clave.lower().strip("\\")

    def poner(self, raiz, clave, valores=None):
        partes = clave.strip("\\").split("\\")
        for i in range(1, len(partes) + 1):  # las claves intermedias existen
            sub = "\\".join(partes[:i])
            self.arbol.setdefault(self._k(raiz, sub), {})
            self.nombres[self._k(raiz, sub)] = partes[i - 1]
        self.arbol[self._k(raiz, clave)].update(valores or {})

    def valores(self, raiz, clave, *, vista=""):
        return dict(self.arbol.get(self._k(raiz, clave), {}))

    def subclaves(self, raiz, clave, *, vista=""):
        base = self._k(raiz, clave)[1] + "\\"
        vistas = []
        for (r, c), original in self.nombres.items():
            if r == raiz.upper() and c.startswith(base) and "\\" not in c[len(base):]:
                vistas.append(original)
        return vistas


class RegistroRoto(RegistroFalso):
    """Un registro cuya lectura de ciertas claves revienta (permiso, corrupción…)."""

    def __init__(self, arbol=None, *, rompe=("uninstall",)):
        super().__init__(arbol)
        self.rompe = rompe

    def _comprobar(self, clave):
        if any(r in clave.lower() for r in self.rompe):
            raise PermissionError("acceso denegado")

    def valores(self, raiz, clave, *, vista=""):
        self._comprobar(clave)
        return super().valores(raiz, clave, vista=vista)

    def subclaves(self, raiz, clave, *, vista=""):
        self._comprobar(clave)
        return super().subclaves(raiz, clave, vista=vista)


def blender(carpeta: Path, version: str | None = "5.2") -> Path:
    """Un `blender.exe` de mentira con la carpeta de versión que Blender trae junto a su ejecutable."""
    carpeta.mkdir(parents=True, exist_ok=True)
    exe = carpeta / "blender.exe"
    exe.write_bytes(b"MZ")
    if version:
        (carpeta / version).mkdir(exist_ok=True)
    return exe


def entorno(tmp_path: Path, registro=None, unidades=(), **env) -> Entorno:
    base = {"USERPROFILE": str(tmp_path / "usuario"), "LOCALAPPDATA": str(tmp_path / "usuario" / "AppData" / "Local"),
            "ProgramFiles": str(tmp_path / "PF"), "ProgramData": str(tmp_path / "PD")}
    base.update(env)
    return Entorno(env=base, registro=registro or RegistroFalso(), unidades=list(unidades))


def claves(candidatos):
    return [os.path.normcase(str(c.ruta)) for c in candidatos]


def uno(candidatos) -> Candidato:
    assert len(candidatos) == 1, candidatos
    return candidatos[0]


# --- Instalador oficial: Program Files, otros discos, la carpeta que eligió el usuario ---------------------------------------------

def test_program_files_con_dos_versiones_elige_la_mas_nueva_primero(tmp_path):
    viejo = blender(tmp_path / "PF" / "Blender Foundation" / "Blender 4.5", "4.5")
    nuevo = blender(tmp_path / "PF" / "Blender Foundation" / "Blender 5.2", "5.2")
    encontrados = ad.buscar(entorno(tmp_path))
    assert claves(encontrados) == claves([Candidato(nuevo, ""), Candidato(viejo, "")])
    assert [c.version for c in encontrados] == [(5, 2), (4, 5)]


def test_la_version_se_compara_como_numero_no_como_texto(tmp_path):
    una = blender(tmp_path / "PF" / "Blender Foundation" / "Blender 9.0", "9.0")
    otra = blender(tmp_path / "PF" / "Blender Foundation" / "Blender 10.0", "10.0")
    assert claves(ad.buscar(entorno(tmp_path))) == claves([Candidato(otra, ""), Candidato(una, "")])


def test_instalacion_por_usuario_en_localappdata(tmp_path):
    exe = blender(tmp_path / "usuario" / "AppData" / "Local" / "Programs" / "Blender Foundation" / "Blender 5.2")
    assert claves(ad.buscar(entorno(tmp_path))) == claves([Candidato(exe, "")])


def test_program_files_de_otro_disco(tmp_path):
    disco = tmp_path / "D"
    exe = blender(disco / "Program Files" / "Blender Foundation" / "Blender 5.2")
    assert claves(ad.buscar(entorno(tmp_path, unidades=[disco]))) == claves([Candidato(exe, "")])
    assert ad.buscar(entorno(tmp_path)) == []  # control: sin ese disco en la lista no se mira


def test_el_instalador_oficial_en_una_carpeta_elegida_se_encuentra_por_el_registro(tmp_path):
    """El caso de esta máquina: el MSI instalado con InstallLocation en la raíz de un disco (`E:\\`)."""
    elegida = tmp_path / "E"
    exe = blender(elegida, "5.2")
    registro = RegistroFalso({("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{4B0BC91B-29A6}"): {
        "DisplayName": "Blender", "Publisher": "Blender Foundation", "DisplayVersion": "5.2.2",
        "InstallLocation": str(elegida) + "\\"}})
    encontrado = uno(ad.buscar(entorno(tmp_path, registro)))
    assert os.path.normcase(str(encontrado.ruta)) == os.path.normcase(str(exe))
    assert encontrado.origen == ad.PROGRAMA
    assert encontrado.version == (5, 2, 2)  # el registro es más preciso que la carpeta `5.2`
    # Control negativo: sin la pista del registro, y sin recorrer ese disco, no hay forma de saber que existe.
    assert ad.buscar(entorno(tmp_path)) == []


@pytest.mark.parametrize("datos", [
    {"DisplayName": "Blender", "Publisher": "Acme Corp", "InstallLocation": "{carpeta}"},          # otro «Blender»
    {"DisplayName": "Blender Launcher", "Publisher": "Otro", "InstallLocation": "{carpeta}"},      # programa de terceros
    {"DisplayName": "Blender", "Publisher": "Blender Foundation", "InstallLocation": ""},          # sin ubicación
    {"DisplayName": "Blender", "Publisher": "Blender Foundation", "InstallLocation": "{vacia}"},   # ubicación sin blender.exe
    {"DisplayName": "Otra cosa", "Publisher": "Blender Foundation", "InstallLocation": "{carpeta}"},
])
def test_el_registro_no_da_por_blender_lo_que_no_lo_es(tmp_path, datos):
    carpeta = tmp_path / "X"
    blender(carpeta)
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    datos = {k: v.format(carpeta=carpeta, vacia=vacia) for k, v in datos.items()}
    registro = RegistroFalso({("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{G}"): datos})
    assert ad.buscar(entorno(tmp_path, registro)) == []


def test_app_paths(tmp_path):
    exe = blender(tmp_path / "Z")
    registro = RegistroFalso({("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe"): {"": f'"{exe}"'}})
    assert uno(ad.buscar(entorno(tmp_path, registro))).origen == ad.PROGRAMA


# --- Asociación del .blend ---------------------------------------------------------------------------------------------------------

def _asociacion(progid: str, orden: str, *, raiz="HKLM") -> RegistroFalso:
    return RegistroFalso({
        (raiz, r"SOFTWARE\Classes\.blend"): {"": progid},
        (raiz, rf"SOFTWARE\Classes\{progid}\shell\open\command"): {"": orden}})


def test_la_asociacion_con_el_lanzador_lleva_al_blender_hermano(tmp_path):
    exe = blender(tmp_path / "Portatil")
    (tmp_path / "Portatil" / "blender-launcher.exe").write_bytes(b"MZ")
    registro = _asociacion("blender.5.2", f'"{tmp_path / "Portatil" / "blender-launcher.exe"}" "%1"')
    encontrado = uno(ad.buscar(entorno(tmp_path, registro)))
    assert os.path.normcase(str(encontrado.ruta)) == os.path.normcase(str(exe))
    assert encontrado.origen == ad.ASOCIACION


def test_la_asociacion_sin_comillas_y_con_espacios(tmp_path):
    exe = blender(tmp_path / "Mi Blender")
    registro = _asociacion("blendfile", f'{exe} "%1"', raiz="HKCU")
    assert uno(ad.buscar(entorno(tmp_path, registro))).origen == ad.ASOCIACION


def test_la_eleccion_del_usuario_y_los_progids_alternativos(tmp_path):
    uno_ = blender(tmp_path / "A", "4.5")
    otro = blender(tmp_path / "B", "5.2")
    registro = RegistroFalso({
        ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.blend\UserChoice"): {"ProgId": "blender.elegido"},
        ("HKCU", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.blend\OpenWithProgids"): {"blender.viejo": None},
        ("HKLM", r"SOFTWARE\Classes\blender.elegido\shell\open\command"): {"": f'"{otro}" "%1"'},
        ("HKLM", r"SOFTWARE\Classes\blender.viejo\shell\open\command"): {"": f'"{uno_}" "%1"'}})
    assert [c.version for c in ad.buscar(entorno(tmp_path, registro))] == [(5, 2), (4, 5)]


def test_una_asociacion_con_otro_programa_no_cuenta(tmp_path):
    otro = tmp_path / "bloc" / "notepad.exe"
    otro.parent.mkdir()
    otro.write_bytes(b"MZ")
    (tmp_path / "bloc" / "blender.exe").write_bytes(b"MZ")  # un blender.exe junto a OTRO programa asociado: no es una pista
    assert ad.buscar(entorno(tmp_path, _asociacion("txt.blend", f'"{otro}" "%1"'))) == []


# --- Steam -------------------------------------------------------------------------------------------------------------------------

#: `libraryfolders.vdf` de esta máquina (2026-10-04), recortado: Valve duplica las barras invertidas.
VDF_REAL = r'''"libraryfolders"
{
	"0"
	{
		"path"		"C:\\Program Files (x86)\\Steam"
		"label"		""
		"apps"
		{
			"228980"		"250207205"
		}
	}
	"1"
	{
		"path"		"D:\\SteamLibrary"
		"label"		""
		"apps"
		{
			"275850"		"33471518875"
		}
	}
	"2"
	{
		"path"		"E:\\SteamLibrary"
		"label"		""
	}
}
'''


def test_las_bibliotecas_de_steam_se_leen_del_vdf_real_con_las_barras_deshechas():
    assert ad._rutas_de_bibliotecas_steam(VDF_REAL) == [
        r"C:\Program Files (x86)\Steam", r"D:\SteamLibrary", r"E:\SteamLibrary"]
    assert ad._rutas_de_bibliotecas_steam("") == []
    assert ad._rutas_de_bibliotecas_steam("basura {{ no es vdf") == []


def _steam(tmp_path: Path, *, blender_en: str | None, installdir: str | None = None):
    """Un Steam con dos bibliotecas (la de Steam y otra en «otro disco»); Blender, si se pide, en la segunda."""
    raiz = tmp_path / "Steam"
    otra = tmp_path / "Disco2" / "SteamLibrary"
    (raiz / "steamapps").mkdir(parents=True)
    vdf = VDF_REAL.replace(r"C:\\Program Files (x86)\\Steam", str(raiz).replace("\\", "\\\\")) \
                  .replace(r"D:\\SteamLibrary", str(otra).replace("\\", "\\\\"))
    (raiz / "steamapps" / "libraryfolders.vdf").write_text(vdf, encoding="utf-8")
    # Steam anota `SteamPath` con barras normales y en minúsculas (`c:/program files (x86)/steam`).
    registro = RegistroFalso({("HKCU", r"SOFTWARE\Valve\Steam"): {"SteamPath": str(raiz).replace("\\", "/")}})
    exe = None
    if blender_en:
        biblioteca = {"principal": raiz, "otra": otra}[blender_en]
        nombre = installdir or "Blender"
        if installdir:
            (biblioteca / "steamapps").mkdir(parents=True, exist_ok=True)
            (biblioteca / "steamapps" / f"appmanifest_{ad.APP_ID_STEAM}.acf").write_text(
                f'"AppState"\n{{\n\t"appid"\t\t"{ad.APP_ID_STEAM}"\n\t"installdir"\t\t"{nombre}"\n}}\n', encoding="utf-8")
        exe = blender(biblioteca / "steamapps" / "common" / nombre)
    return registro, exe


def test_blender_de_steam_en_una_biblioteca_de_otro_disco(tmp_path):
    registro, exe = _steam(tmp_path, blender_en="otra")
    encontrado = uno(ad.buscar(entorno(tmp_path, registro)))
    assert os.path.normcase(str(encontrado.ruta)) == os.path.normcase(str(exe))
    assert encontrado.origen == ad.STEAM and encontrado.version == (5, 2)


def test_blender_de_steam_en_la_biblioteca_principal(tmp_path):
    registro, exe = _steam(tmp_path, blender_en="principal")
    assert claves(ad.buscar(entorno(tmp_path, registro))) == claves([Candidato(exe, "")])


def test_steam_usa_el_installdir_del_manifiesto_de_la_app(tmp_path):
    registro, exe = _steam(tmp_path, blender_en="otra", installdir="Blender 5.2 LTS")
    assert uno(ad.buscar(entorno(tmp_path, registro))).ruta == exe


def test_steam_sin_blender_instalado_no_inventa_nada(tmp_path):
    registro, _ = _steam(tmp_path, blender_en=None)
    assert ad.buscar(entorno(tmp_path, registro)) == []


def test_sin_la_pista_de_steam_no_se_encuentra_la_biblioteca_de_otro_disco(tmp_path):
    """Control: el Blender de Steam en un disco secundario sólo se halla porque el registro dice dónde está Steam."""
    _, exe = _steam(tmp_path, blender_en="otra")
    assert exe.is_file()
    assert ad.buscar(entorno(tmp_path)) == []


def test_steam_con_registro_pero_sin_vdf_no_revienta(tmp_path):
    registro = RegistroFalso({("HKCU", r"SOFTWARE\Valve\Steam"): {"SteamPath": str(tmp_path / "no-existe")}})
    assert ad.buscar(entorno(tmp_path, registro)) == []


def test_una_biblioteca_de_steam_en_un_disco_sin_steam_registrado(tmp_path):
    disco = tmp_path / "F"
    exe = blender(disco / "SteamLibrary" / "steamapps" / "common" / "Blender")
    assert uno(ad.buscar(entorno(tmp_path, unidades=[disco]))).origen == ad.STEAM
    assert uno(ad.buscar(entorno(tmp_path, unidades=[disco]))).ruta == exe


# --- Microsoft Store ---------------------------------------------------------------------------------------------------------------

_PAQUETES = r"SOFTWARE\Classes\Local Settings\Software\Microsoft\Windows\CurrentVersion\AppModel\Repository\Packages"

#: Estructura real de un `AppxManifest.xml` de la Tienda (el del Bloc de notas de esta máquina, recortado): espacios de nombres, `Identity`
#: y `Application Executable="<carpeta>\\<programa>.exe"` con atributos de otro espacio de nombres.
MANIFIESTO_REAL = '''<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<Package IgnorableNamespaces="uap uap11" xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:uap11="http://schemas.microsoft.com/appx/manifest/uap/windows10/11">
  <Identity Name="{nombre}" Publisher="CN=Test" Version="{version}" ProcessorArchitecture="x64"/>
  <Applications>
    <Application Id="App" Executable="{ejecutable}" EntryPoint="Windows.FullTrustApplication" uap11:CurrentDirectoryPath="$(env:USERPROFILE)">
      <uap:VisualElements DisplayName="x"/>
    </Application>
  </Applications>
</Package>
'''


def _paquete(tmp_path: Path, *, nombre="BlenderFoundation.Blender", version="5.2.2.0", ejecutable=r"Blender\blender.exe",
             con_manifiesto=True, con_exe=True, donde="WindowsApps", carpeta_version="5.2"):
    """Un paquete de la Tienda: su carpeta (en `WindowsApps`, aquí de mentira) y su entrada en el registro."""
    completo = f"{nombre}_{version}_x64__ppwjx74xxxxxx"
    raiz = tmp_path / donde / completo
    raiz.mkdir(parents=True)
    exe = None
    if con_exe:
        exe = blender(raiz.joinpath(*ejecutable.split("\\")).parent, carpeta_version)
    if con_manifiesto:
        (raiz / "AppxManifest.xml").write_text(
            MANIFIESTO_REAL.format(nombre=nombre, version=version, ejecutable=ejecutable), encoding="utf-8")
    registro = RegistroFalso({("HKCU", f"{_PAQUETES}\\{completo}"): {"PackageRootFolder": str(raiz)}})
    return registro, exe, raiz


def test_blender_de_la_tienda_por_el_manifiesto_del_paquete(tmp_path):
    registro, exe, _ = _paquete(tmp_path)
    encontrado = uno(ad.buscar(entorno(tmp_path, registro)))
    assert encontrado.ruta == exe
    assert encontrado.origen == ad.TIENDA
    assert encontrado.version == (5, 2, 2)  # del nombre del paquete: 5.2.2.0 → 5.2.2


def test_blender_de_la_tienda_en_otra_unidad_se_halla_por_la_ruta_del_registro(tmp_path):
    """La Tienda puede instalar en otra unidad (en esta máquina existe `E:\\WindowsApps`): la ruta real sale del registro, no de `%ProgramFiles%`."""
    registro, exe, _ = _paquete(tmp_path, donde="otra-unidad/WindowsApps")
    assert uno(ad.buscar(entorno(tmp_path, registro))).ruta == exe


def test_la_tienda_sin_manifiesto_cae_a_las_disposiciones_conocidas(tmp_path):
    registro, exe, _ = _paquete(tmp_path, con_manifiesto=False)
    assert uno(ad.buscar(entorno(tmp_path, registro))).ruta == exe


def test_un_manifiesto_ilegible_no_rompe_la_busqueda(tmp_path):
    registro, exe, raiz = _paquete(tmp_path)
    (raiz / "AppxManifest.xml").write_text("<Package><esto no es xml", encoding="utf-8")
    assert uno(ad.buscar(entorno(tmp_path, registro))).ruta == exe  # la disposición conocida lo salva


def test_la_tienda_con_paquete_registrado_pero_sin_programa_no_da_candidato(tmp_path):
    registro, _, _ = _paquete(tmp_path, con_exe=False)
    assert ad.buscar(entorno(tmp_path, registro)) == []


def test_otros_paquetes_de_la_tienda_no_cuentan(tmp_path):
    registro, _, _ = _paquete(tmp_path, nombre="Microsoft.WindowsNotepad", version="11.2607.14.0", ejecutable=r"Notepad\Notepad.exe",
                              con_exe=False)
    assert ad.buscar(entorno(tmp_path, registro)) == []


def test_paquete_con_nombre_parecido_pero_de_otro_editor_no_cuenta(tmp_path):
    registro, _, _ = _paquete(tmp_path, nombre="BlenderFoundationFake.Blender")
    assert ad.buscar(entorno(tmp_path, registro)) == []


def test_sin_la_entrada_del_registro_la_tienda_es_invisible(tmp_path):
    """Control: `WindowsApps` no se puede listar, así que sin el registro no hay manera de hallar el paquete."""
    _, exe, _ = _paquete(tmp_path)
    assert exe.is_file()
    assert ad.buscar(entorno(tmp_path)) == []


def test_el_ejecutable_de_la_tienda_se_lee_del_manifiesto_real_de_esta_maquina():
    """Con un paquete REAL instalado (el Bloc de notas), el mismo lector da su `.exe`: el formato del manifiesto es el de verdad."""
    if sys.platform != "win32":
        pytest.skip("sólo Windows")
    real = ad.RegistroWindows()
    paquetes = [p for p in real.subclaves("HKCU", _PAQUETES) if p.lower().startswith("microsoft.windowsnotepad_")]
    if not paquetes:
        pytest.skip("esta máquina no tiene el Bloc de notas de la Tienda")
    carpeta = real.valores("HKCU", f"{_PAQUETES}\\{paquetes[0]}").get("PackageRootFolder")
    ejecutable = ad._ejecutable_de_paquete(Path(str(carpeta)))
    assert ejecutable is not None and ejecutable.name.lower() == "notepad.exe" and ejecutable.is_file()


# --- Scoop, Chocolatey, winget, PATH, ZIP descomprimido, raíz de un disco -----------------------------------------------------------------

def test_scoop(tmp_path):
    exe = blender(tmp_path / "usuario" / "scoop" / "apps" / "blender" / "current")
    assert uno(ad.buscar(entorno(tmp_path))).origen == ad.GESTOR
    assert uno(ad.buscar(entorno(tmp_path))).ruta == exe


def test_scoop_con_variable_y_versiones(tmp_path):
    blender(tmp_path / "scoopdir" / "apps" / "blender" / "4.5.0", "4.5")
    nuevo = blender(tmp_path / "scoopdir" / "apps" / "blender" / "5.2.2", "5.2")
    encontrados = ad.buscar(entorno(tmp_path, SCOOP=str(tmp_path / "scoopdir")))
    assert encontrados[0].ruta == nuevo and len(encontrados) == 2


def test_chocolatey_portable(tmp_path):
    exe = blender(tmp_path / "choco" / "lib" / "blender.portable" / "tools" / "blender-5.2.2-windows-x64")
    assert uno(ad.buscar(entorno(tmp_path, ChocolateyInstall=str(tmp_path / "choco")))).ruta == exe


def test_enlace_de_winget(tmp_path):
    exe = blender(tmp_path / "usuario" / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links")
    assert uno(ad.buscar(entorno(tmp_path))).ruta == exe


def test_path_con_entradas_absolutas_y_entre_comillas(tmp_path):
    exe = blender(tmp_path / "herramientas" / "blender")
    ruta = os.pathsep.join([str(tmp_path / "nada"), f'"{exe.parent}"'])
    assert uno(ad.buscar(entorno(tmp_path, PATH=ruta))).origen == ad.RUTA


def test_path_ignora_las_entradas_relativas_y_la_carpeta_actual(tmp_path, monkeypatch):
    """`shutil.which` en Windows mira primero la carpeta actual: un `blender.exe` suelto ahí NO debe contar. Aquí tampoco las entradas relativas."""
    blender(tmp_path / "trampa")
    monkeypatch.chdir(tmp_path / "trampa")
    assert ad.buscar(entorno(tmp_path, PATH=os.pathsep.join([".", "", "trampa", "bin"]))) == []


def test_zip_descomprimido_en_descargas(tmp_path):
    exe = blender(tmp_path / "usuario" / "Downloads" / "blender-5.2.2-windows-x64")
    encontrado = uno(ad.buscar(entorno(tmp_path)))
    assert encontrado.ruta == exe and encontrado.origen == ad.PORTATIL and encontrado.version == (5, 2)


def test_raiz_de_un_disco_y_carpeta_blender_en_un_disco(tmp_path):
    disco_e, disco_f = tmp_path / "E", tmp_path / "F"
    en_raiz = blender(disco_e, "5.2")
    en_carpeta = blender(disco_f / "Blender 4.5 portable", "4.5")
    encontrados = ad.buscar(entorno(tmp_path, unidades=[disco_e, disco_f]))
    assert claves(encontrados) == claves([Candidato(en_raiz, ""), Candidato(en_carpeta, "")])


def test_una_carpeta_que_no_es_de_blender_no_da_candidato(tmp_path):
    (tmp_path / "usuario" / "Downloads" / "blender_notas").mkdir(parents=True)
    (tmp_path / "usuario" / "Downloads" / "blender_notas" / "apuntes.txt").write_text("x")
    assert ad.buscar(entorno(tmp_path)) == []


# --- Duplicados, orden y versión ------------------------------------------------------------------------------------------------------

def test_el_mismo_blender_por_tres_pistas_sale_una_sola_vez_con_las_demas_anotadas(tmp_path):
    disco = tmp_path / "E"
    exe = blender(disco, "5.2")
    (disco / "blender-launcher.exe").write_bytes(b"MZ")
    registro = RegistroFalso({
        ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{G}"): {
            "DisplayName": "Blender", "Publisher": "Blender Foundation", "DisplayVersion": "5.2.2", "InstallLocation": str(disco)},
        ("HKLM", r"SOFTWARE\Classes\.blend"): {"": "blender.5.2"},
        ("HKLM", r"SOFTWARE\Classes\blender.5.2\shell\open\command"): {"": f'"{disco / "blender-launcher.exe"}" "%1"'}})
    encontrado = uno(ad.buscar(entorno(tmp_path, registro, unidades=[disco])))
    assert encontrado.ruta == exe
    assert encontrado.origen == ad.PROGRAMA                      # la pista más fiable gana
    assert set(encontrado.tambien) == {ad.ASOCIACION, ad.PORTATIL}


def test_la_misma_ruta_con_otra_capitalizacion_es_el_mismo_blender(tmp_path):
    exe = blender(tmp_path / "Mi Blender")
    registro = RegistroFalso({("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\blender.exe"): {"": str(exe).upper()}})
    assert len(ad.buscar(entorno(tmp_path, registro, PATH=str(exe.parent)))) == 1


def test_orden_version_mas_alta_primero_y_las_desconocidas_al_final(tmp_path):
    registro, steam_exe = _steam(tmp_path, blender_en="otra")                       # 5.2
    viejo = blender(tmp_path / "PF" / "Blender Foundation" / "Blender 4.5", "4.5")   # 4.5
    sin_version = blender(tmp_path / "usuario" / "Downloads" / "blender-x", None)    # ?
    orden = ad.buscar(entorno(tmp_path, registro))
    assert [c.ruta for c in orden] == [steam_exe, viejo, sin_version]
    assert [c.version for c in orden] == [(5, 2), (4, 5), None]


def test_ordenar_para_usar_pone_los_viejos_detras_de_los_que_sirven_y_de_los_desconocidos():
    a = Candidato(Path("a/blender.exe"), ad.PROGRAMA, (4, 5))
    b = Candidato(Path("b/blender.exe"), ad.PROGRAMA, (5, 2, 2))
    c = Candidato(Path("c/blender.exe"), ad.PORTATIL, None)
    assert ad.ordenar_para_usar([a, b, c], MINIMA) == [b, c, a]
    assert ad.ordenar_para_usar([a], MINIMA) == [a]     # si sólo hay viejos, el sondeo dirá por qué no
    assert ad.ordenar_para_usar([], MINIMA) == []


@pytest.mark.parametrize("version,esperado", [((5, 2), True), ((5, 2, 2), True), ((6, 0), True), ((5, 1), False), ((4, 5), False),
                                              ((4, 2, 23), False), (None, None)])
def test_apto_segun_la_version_minima(version, esperado):
    assert ad.apto(Candidato(Path("x/blender.exe"), ad.PROGRAMA, version), MINIMA) is esperado


def test_para_la_pantalla_lleva_ruta_origen_version_y_si_es_apto():
    lista = ad.para_la_pantalla([Candidato(Path("x/blender.exe"), ad.STEAM, (5, 2, 2), (ad.PORTATIL,)),
                                 Candidato(Path("y/blender.exe"), ad.TIENDA, None)], MINIMA)
    assert lista[0] == {"ruta": str(Path("x/blender.exe")), "origen": "steam", "version": "5.2.2", "apto": True, "tambien": ["portatil"]}
    assert lista[1]["version"] is None and lista[1]["apto"] is None


def test_version_de_carpeta_toma_la_mayor_e_ignora_lo_que_no_es_version(tmp_path):
    exe = blender(tmp_path / "B", "4.5")
    for nombre in ("5.2", "5.2.2", "datafiles", "x.y"):
        (tmp_path / "B" / nombre).mkdir()
    (tmp_path / "B" / "6.0").write_text("un fichero llamado como una versión")  # no es carpeta
    assert ad.version_de_carpeta(exe) == (5, 2)
    assert ad.version_de_carpeta(tmp_path / "no-existe" / "blender.exe") is None


@pytest.mark.parametrize("texto,esperado", [("5.2.2", (5, 2, 2)), ("5.2", (5, 2)), (" 4.5.14 ", (4, 5, 14)), ("Blender 5.2", None),
                                            ("", None), (None, None), (5.2, (5, 2))])
def test_version_de_texto(texto, esperado):
    assert ad.version_de_texto(texto) == esperado


def test_solo_cuenta_un_archivo_llamado_blender_exe(tmp_path):
    carpeta = tmp_path / "C"
    carpeta.mkdir()
    (carpeta / "blender-launcher.exe").write_bytes(b"MZ")
    (carpeta / "BLENDER.EXE").write_bytes(b"MZ")
    assert ad._es_blender(carpeta / "BLENDER.EXE") is True            # Windows no distingue mayúsculas
    assert ad._es_blender(carpeta / "blender-launcher.exe") is False
    (tmp_path / "D" / "blender.exe").mkdir(parents=True)
    assert ad._es_blender(tmp_path / "D" / "blender.exe") is False    # una carpeta llamada así
    assert ad._es_blender(tmp_path / "no-existe.exe") is False


# --- Resistencia -----------------------------------------------------------------------------------------------------------------------

def test_una_pista_que_revienta_no_impide_usar_las_demas(tmp_path):
    exe = blender(tmp_path / "Portatil")
    (tmp_path / "Portatil" / "blender-launcher.exe").write_bytes(b"MZ")
    registro = RegistroRoto({
        ("HKLM", r"SOFTWARE\Classes\.blend"): {"": "blender.5.2"},
        ("HKLM", r"SOFTWARE\Classes\blender.5.2\shell\open\command"): {"": f'"{tmp_path / "Portatil" / "blender-launcher.exe"}" "%1"'},
        ("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{G}"): {"DisplayName": "Blender"}})
    with pytest.raises(PermissionError):
        registro.subclaves("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")  # control: de verdad revienta
    assert uno(ad.buscar(entorno(tmp_path, registro))).ruta == exe


def test_un_registro_vacio_y_sin_discos_no_encuentra_nada_ni_falla(tmp_path):
    assert ad.buscar(entorno(tmp_path)) == []


def test_las_variables_de_entorno_no_distinguen_mayusculas(tmp_path):
    exe = blender(tmp_path / "PF2" / "Blender Foundation" / "Blender 5.2")
    e = Entorno(env={"PROGRAMFILES": str(tmp_path / "PF2")}, registro=RegistroFalso(), unidades=[])
    assert uno(ad.buscar(e)).ruta == exe


# --- Caché -------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def buscar_contado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(ad, "buscar", lambda entorno=None: llamadas.append(entorno) or [Candidato(Path("x/blender.exe"), ad.PROGRAMA, (5, 2))])
    ad.invalidar()
    yield llamadas
    ad.invalidar()


def test_la_busqueda_se_reutiliza_y_forzar_la_repite(buscar_contado):
    primero = ad.listar()
    assert ad.listar() == primero and len(buscar_contado) == 1
    ad.listar(forzar=True)
    assert len(buscar_contado) == 2
    ad.invalidar()
    ad.listar()
    assert len(buscar_contado) == 3


def test_la_busqueda_caduca(buscar_contado, monkeypatch):
    ad.listar()
    ahora = time.monotonic()
    monkeypatch.setattr(ad, "time", SimpleNamespace(monotonic=lambda: ahora + ad.VIGENCIA_S + 1))
    ad.listar()
    assert len(buscar_contado) == 2


def test_un_entorno_inyectado_nunca_lee_ni_escribe_la_cache(buscar_contado, tmp_path):
    guardado = ad.listar()
    ajeno = entorno(tmp_path)
    assert ad.listar(entorno=ajeno) == guardado          # el sustituto devuelve lo mismo, pero...
    assert len(buscar_contado) == 2 and buscar_contado[-1] is ajeno   # ...se llamó con SU entorno, sin usar la caché
    assert ad.listar() == guardado and len(buscar_contado) == 2       # y la caché de verdad sigue vigente


# --- Integración con el sondeo del renderizador ---------------------------------------------------------------------------------------------

@pytest.fixture
def renderizador(monkeypatch, tmp_path):
    monkeypatch.setattr(renderer.installation, "settings", lambda: {})
    monkeypatch.setattr(renderer.installation, "blender_path", lambda: None)
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_blender_path=None, molcy_engine_dir=None))
    monkeypatch.setattr(renderer.motor, "directorio_incluido", lambda: None)
    monkeypatch.setattr(renderer.subprocess, "run", lambda *a, **k: pytest.fail("No se debe lanzar Blender"))
    renderer.invalidar()
    return tmp_path


def test_el_renderizador_prueba_primero_el_blender_que_sirve(monkeypatch, renderizador):
    viejo = Candidato(renderizador / "viejo" / "blender.exe", ad.PROGRAMA, (4, 5))
    nuevo = Candidato(renderizador / "nuevo" / "blender.exe", ad.STEAM, (5, 2, 2))
    monkeypatch.setattr(ad, "listar", lambda forzar=False, entorno=None: [viejo, nuevo])
    assert renderer._blender_candidatos() == [nuevo.ruta, viejo.ruta]


def test_el_blender_administrado_y_el_configurado_mandan_sobre_lo_detectado(monkeypatch, renderizador):
    detectado = Candidato(renderizador / "det" / "blender.exe", ad.PROGRAMA, (5, 2))
    monkeypatch.setattr(ad, "listar", lambda forzar=False, entorno=None: [detectado])
    administrado = blender(renderizador / "adm")
    monkeypatch.setattr(renderer.installation, "blender_path", lambda: administrado)
    assert renderer._blender_candidatos() == [administrado]
    monkeypatch.setattr(renderer.installation, "blender_path", lambda: None)
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_blender_path=str(renderizador / "cfg.exe"), molcy_engine_dir=None))
    assert renderer._blender_candidatos() == [renderizador / "cfg.exe"]
    monkeypatch.setattr(renderer, "get_settings", lambda: SimpleNamespace(molcy_blender_path=None, molcy_engine_dir=None))
    monkeypatch.setattr(renderer.installation, "settings", lambda: {"modo": "existente", "blender": str(renderizador / "elegido.exe")})
    assert renderer._blender_candidatos() == [renderizador / "elegido.exe"]


def test_el_estado_del_renderizador_lista_los_blender_encontrados(monkeypatch, renderizador):
    monkeypatch.setattr(renderer, "_detectar", lambda: {"disponible": False, "motivo": "x"})
    monkeypatch.setattr(ad, "listar", lambda forzar=False, entorno=None: [
        Candidato(Path("E:/blender.exe"), ad.PROGRAMA, (5, 2, 2), (ad.ASOCIACION,)), Candidato(Path("C:/v/blender.exe"), ad.STEAM, (4, 5))])
    encontrados = renderer.detectar()["blenders_encontrados"]
    assert [(e["origen"], e["version"], e["apto"]) for e in encontrados] == [("programa", "5.2.2", True), ("steam", "4.5", False)]


def test_comprobar_vuelve_a_mirar_el_disco_y_una_comprobacion_normal_no(monkeypatch, renderizador):
    monkeypatch.setattr(renderer, "_detectar", lambda: {"disponible": False})
    invalidaciones = []
    monkeypatch.setattr(ad, "invalidar", lambda: invalidaciones.append(1))
    monkeypatch.setattr(ad, "listar", lambda forzar=False, entorno=None: [])
    renderer.detectar()
    assert invalidaciones == []
    renderer.detectar(forzar=True)
    assert invalidaciones == [1]


def test_sin_ningun_blender_el_sondeo_se_abstiene_sin_lanzar_nada(monkeypatch, renderizador):
    monkeypatch.setattr(ad, "listar", lambda forzar=False, entorno=None: [])
    resultado = renderer.detectar(forzar=True)
    assert resultado["disponible"] is False
    assert "No se encontró Blender" in resultado["motivo"] and resultado["blenders_encontrados"] == []
    # El menú de Descargas ofrece «Descargar e instalar» por este código; sin él no sabía que faltaba Blender.
    assert resultado["motivo_codigo"] == "falta_blender"


# --- Lo que no admite mentira: la máquina real --------------------------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="sólo Windows")
def test_el_registro_real_se_lee_y_lo_que_no_existe_es_sin_pista():
    real = ad.RegistroWindows()
    version = real.valores("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion")
    assert os.path.normcase(str(version.get("ProgramFilesDir"))) == os.path.normcase(os.environ["ProgramFiles"])
    assert real.valores("HKLM", r"SOFTWARE\ClaveQueNoExiste\Seguro") == {}
    assert real.subclaves("HKCU", r"SOFTWARE\ClaveQueNoExiste\Seguro") == []
    assert len(real.subclaves("HKLM", r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", vista="64")) > 0


@pytest.mark.skipif(sys.platform != "win32", reason="sólo Windows")
def test_los_discos_fijos_reales_existen_y_incluyen_el_del_sistema():
    discos = ad._unidades_fijas()
    assert discos and all(d.exists() for d in discos)
    sistema = Path(os.environ["SystemDrive"] + "\\")
    assert os.path.normcase(str(sistema)) in [os.path.normcase(str(d)) for d in discos]


@pytest.mark.skipif(sys.platform != "win32", reason="sólo Windows")
def test_solo_se_recorren_los_discos_fijos(monkeypatch):
    """Un disco de red o una unidad óptica puede tardar segundos en contestar: sólo `DRIVE_FIXED` (3) entra."""
    tipos = {"C:\\": 3, "D:\\": 5, "E:\\": 4, "F:\\": 2, "G:\\": 3}
    nucleo = SimpleNamespace(GetLogicalDrives=lambda: sum(1 << (ord(l[0]) - ord("A")) for l in tipos),
                             GetDriveTypeW=lambda letra: tipos[letra])
    monkeypatch.setattr(ad.ctypes, "windll", SimpleNamespace(kernel32=nucleo), raising=False)
    assert ad._unidades_fijas() == [Path("C:\\"), Path("G:\\")]


@pytest.mark.skipif(sys.platform != "win32", reason="sólo Windows")
def test_la_busqueda_real_no_ejecuta_nada_y_es_rapida(monkeypatch):
    """Sin lanzar ni un proceso (ni Blender ni PowerShell) y en una fracción de segundo."""
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("la autodetección no puede lanzar procesos"))
    inicio = time.perf_counter()
    encontrados = ad.buscar(Entorno())
    assert time.perf_counter() - inicio < 5.0
    assert all(c.ruta.name.lower() == "blender.exe" and c.ruta.is_file() for c in encontrados)
    claves_ = claves(encontrados)
    assert len(claves_) == len(set(claves_))
