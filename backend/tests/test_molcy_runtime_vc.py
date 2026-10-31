"""VM-MOLCY-01: el Python auxiliar de Blender recibe el runtime de Visual C++ x64 que trae MolDesign.

En un Windows sin el redistribuible, `<versión>/python/bin/python.exe` (el que el gestor de extensiones de Blender lanza por
subproceso) moría con 0xC0000135 y Molecular Nodes no se instalaba nunca. Estas pruebas fijan el contrato: sólo se usa un runtime
que coincide byte a byte con su manifiesto; en el Blender administrado las DLL se copian junto a su Python sin pisar lo que
traiga Blender; un Blender del usuario no se toca y sólo su subproceso ve la carpeta; y un fallo de arranque se dice como tal,
con su registro completo, antes de pedirle nada a Blender.

Lo que NO demuestran: que las DLL basten en un Windows limpio. En esta máquina System32 ya tiene el runtime, así que la
aceptación es la del informe (una imagen limpia, sin el redistribuible).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from services.molcy import addon, installation, renderer, runtime_vc

RAIZ = Path(__file__).resolve().parents[2]
DLLS = {"vcruntime140.dll": b"runtime de prueba 140", "vcruntime140_1.dll": b"runtime de prueba 140_1",
        "msvcp140.dll": b"biblioteca de prueba"}


def _runtime_falso(carpeta: Path) -> Path:
    (carpeta / "x64").mkdir(parents=True)
    archivos = {}
    for nombre, datos in DLLS.items():
        (carpeta / "x64" / nombre).write_bytes(datos)
        archivos[nombre] = {"bytes": len(datos), "file_version": "14.50.35719.0", "sha256": hashlib.sha256(datos).hexdigest()}
    (carpeta / runtime_vc.NOMBRE_MANIFIESTO).write_text(json.dumps({
        "component": "Microsoft Visual C++ Redistributable runtime", "version": "14.50.35719",
        "architecture": "x64", "deployment": "app-local", "files": archivos}), encoding="utf-8")
    return carpeta


@pytest.fixture
def aislado(monkeypatch, tmp_path):
    datos = tmp_path / "data"
    datos.mkdir()
    monkeypatch.setattr(installation, "data_dir", lambda: datos)
    monkeypatch.setattr(addon, "data_dir", lambda: datos)
    monkeypatch.setattr(renderer, "data_dir", lambda: datos)
    runtime = _runtime_falso(tmp_path / "vc-runtime")
    monkeypatch.setenv("MOLDESIGN_VC_RUNTIME_DIR", str(runtime))
    runtime_vc._cache.clear()
    yield tmp_path
    runtime_vc._cache.clear()


def _blender(raiz: Path) -> tuple[Path, Path]:
    """Un Blender con la forma del ZIP oficial: `blender.exe` y `5.2/python/bin/python.exe` (sin ninguna DLL de Visual C++)."""
    blender = raiz / "blender.exe"
    python = raiz / "5.2" / "python" / "bin" / "python.exe"
    python.parent.mkdir(parents=True)
    blender.write_bytes(b"blender")
    python.write_bytes(b"python")
    (python.parent / "python313.dll").write_bytes(b"python313")
    return blender, python


def _administrado() -> tuple[Path, Path]:
    return _blender(installation.blender_path().parent)


def _arbol(raiz: Path) -> dict[str, bytes]:
    return {p.relative_to(raiz).as_posix(): p.read_bytes() for p in sorted(raiz.rglob("*")) if p.is_file()}


# --- El runtime que viaja ------------------------------------------------------------------------------------------------

def test_el_runtime_del_repositorio_se_verifica(monkeypatch):
    """El que se versiona en `tools/vc-runtime` y viaja en el instalador: el backend lo encuentra con la resolución por defecto."""
    monkeypatch.delenv("MOLDESIGN_VC_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("MOLDESIGN_OPENBABEL_DIR", raising=False)
    runtime_vc._cache.clear()
    carpeta, manifiesto, problemas = runtime_vc.runtime_verificado()
    runtime_vc._cache.clear()
    assert problemas == []
    assert carpeta == (RAIZ / "tools" / "vc-runtime" / "x64").resolve()
    assert manifiesto["version"] == "14.50.35719" and manifiesto["architecture"] == "x64"
    # Las tres que pide el Python de Blender 5.2 (medido en python.exe, python313.dll y sus .pyd).
    assert {"vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"} <= set(manifiesto["files"])


def test_un_byte_alterado_y_el_runtime_no_se_usa(aislado):
    (aislado / "vc-runtime" / "x64" / "msvcp140.dll").write_bytes(b"biblioteca de prueba alterada")
    carpeta, _, problemas = runtime_vc.runtime_verificado()
    assert carpeta is None
    assert problemas == ["msvcp140.dll: no coincide con su manifiesto"]
    entorno = {"PATH": r"C:\Windows\System32"}
    assert runtime_vc.con_runtime_en_path(entorno) == entorno
    _, python = _administrado()
    assert runtime_vc.desplegar_junto_a_python(python) == []
    assert not (python.parent / "vcruntime140.dll").exists()


def test_un_manifiesto_que_no_declara_x64_no_se_usa(aislado):
    manifiesto_path = aislado / "vc-runtime" / runtime_vc.NOMBRE_MANIFIESTO
    manifiesto = json.loads(manifiesto_path.read_text(encoding="utf-8"))
    manifiesto["architecture"] = "x86"
    manifiesto_path.write_text(json.dumps(manifiesto), encoding="utf-8")
    carpeta, _, problemas = runtime_vc.runtime_verificado()
    assert carpeta is None and "el manifiesto no declara x64/app-local" in problemas


# --- El Blender administrado ---------------------------------------------------------------------------------------------

def test_el_blender_administrado_recibe_el_runtime_junto_a_su_python(aislado):
    blender, python = _administrado()
    entorno = installation.environment(blender)
    for nombre, datos in DLLS.items():
        assert (python.parent / nombre).read_bytes() == datos
    registro = json.loads((python.parent / runtime_vc.NOMBRE_REGISTRO).read_text(encoding="utf-8"))
    assert registro["version"] == "14.50.35719" and set(registro["archivos"]) == set(DLLS)
    # El PATH del subproceso también la lleva delante; el perfil propio sigue ahí.
    assert entorno["PATH"].split(os.pathsep)[0] == str((aislado / "vc-runtime" / "x64").resolve())
    assert "perfil_blender" in entorno["BLENDER_USER_CONFIG"]
    # El PATH de este proceso no cambia: sólo el del subproceso.
    assert str(aislado / "vc-runtime") not in os.environ.get("PATH", "")


def test_no_pisa_una_dll_que_trae_el_propio_blender(aislado):
    blender, python = _administrado()
    (python.parent / "vcruntime140.dll").write_bytes(b"la de Blender")
    installation.environment(blender)
    assert (python.parent / "vcruntime140.dll").read_bytes() == b"la de Blender"
    assert (python.parent / "msvcp140.dll").read_bytes() == DLLS["msvcp140.dll"]
    registro = json.loads((python.parent / runtime_vc.NOMBRE_REGISTRO).read_text(encoding="utf-8"))
    assert "vcruntime140.dll" not in registro["archivos"]


def test_repone_una_copia_propia_danada_y_no_reescribe_las_buenas(aislado):
    blender, python = _administrado()
    installation.environment(blender)
    (python.parent / "msvcp140.dll").write_bytes(b"danada")
    assert runtime_vc.desplegar_junto_a_python(python) == ["msvcp140.dll"]
    assert (python.parent / "msvcp140.dll").read_bytes() == DLLS["msvcp140.dll"]
    assert runtime_vc.desplegar_junto_a_python(python) == []


def test_un_blender_del_usuario_no_se_modifica_pero_su_subproceso_ve_el_runtime(aislado):
    blender, _ = _blender(aislado / "personal")
    antes = _arbol(aislado / "personal")
    entorno = installation.environment(blender)
    assert _arbol(aislado / "personal") == antes
    assert entorno["PATH"].split(os.pathsep)[0] == str((aislado / "vc-runtime" / "x64").resolve())
    assert entorno.get("BLENDER_USER_CONFIG") is None


def test_el_python_auxiliar_es_el_de_la_version_mas_alta(tmp_path):
    blender, _ = _blender(tmp_path)
    otro = tmp_path / "5.10" / "python" / "bin" / "python.exe"
    otro.parent.mkdir(parents=True)
    otro.write_bytes(b"python")
    (tmp_path / "scripts" / "python" / "bin").mkdir(parents=True)
    (tmp_path / "scripts" / "python" / "bin" / "python.exe").write_bytes(b"no es una version")
    assert runtime_vc.python_de_blender(blender) == otro
    assert runtime_vc.python_de_blender(tmp_path / "vacio" / "blender.exe") is None


def test_un_blender_en_la_raiz_de_una_unidad_no_rompe_la_busqueda(tmp_path, monkeypatch):
    """Medido en esta máquina: un Blender en `E:\\` y `glob('*/python/bin/python.exe')` lanzaba WinError 1337 en `E:\\WpSystem`.
    Eso habría tumbado `environment()` y con él la detección de Molcy. Sólo se miran las carpetas con nombre de versión."""
    blender, python = _blender(tmp_path)
    (tmp_path / "WpSystem" / "python" / "bin").mkdir(parents=True)
    is_dir, stat = Path.is_dir, Path.stat

    def protegida(ruta: Path) -> bool:
        return "WpSystem" in ruta.parts

    def is_dir_protegida(self, *a, **k):
        if protegida(self):
            raise OSError(1337, "La estructura del identificador de seguridad no es válida")
        return is_dir(self, *a, **k)

    def stat_protegida(self, *a, **k):
        if protegida(self):
            raise OSError(1337, "La estructura del identificador de seguridad no es válida")
        return stat(self, *a, **k)

    monkeypatch.setattr(Path, "is_dir", is_dir_protegida)
    monkeypatch.setattr(Path, "stat", stat_protegida)
    assert runtime_vc.python_de_blender(blender) == python


def test_una_carpeta_que_no_se_puede_listar_no_rompe_el_entorno(aislado, monkeypatch):
    blender, _ = _blender(aislado / "personal")
    iterdir = Path.iterdir

    def iterdir_denegado(self):
        if self == blender.parent:
            raise PermissionError(5, "Acceso denegado")
        return iterdir(self)

    monkeypatch.setattr(Path, "iterdir", iterdir_denegado)
    assert runtime_vc.python_de_blender(blender) is None
    assert installation.environment(blender)["PATH"].split(os.pathsep)[0].endswith("x64")


# --- La instalación de Molecular Nodes -----------------------------------------------------------------------------------

def _sin_blender(*args, **kwargs):
    raise AssertionError("no se le pide nada a Blender si su Python auxiliar no arranca")


@pytest.mark.parametrize("returncode", [0xC0000135, -1073741515])
def test_un_python_auxiliar_sin_visual_cpp_se_explica_y_no_se_intenta_instalar(aislado, monkeypatch, returncode):
    blender, python = _administrado()
    monkeypatch.setattr(runtime_vc, "probar_python", lambda b, env, **_: {
        "ok": False, "python": str(python), "returncode": returncode,
        "codigo": f"0x{runtime_vc.codigo_windows(returncode):08X}", "stdout": "", "stderr": ""})
    monkeypatch.setattr(addon.subprocess, "run", _sin_blender)
    addon._instalar(blender)
    estado = addon.estado()
    assert estado["estado"] == "fallido"
    assert estado["motivo"].startswith(addon.MENSAJE_PYTHON_SIN_VC + " " + addon.MENSAJE_VC_SIN_COPIAR)
    registro = Path(estado["registro"])
    assert estado["motivo"].endswith(f"Registro completo: {registro}")
    texto = registro.read_text(encoding="utf-8")
    assert "0xC0000135" in texto and "14.50.35719" in texto and str(python) in texto


def test_con_el_blender_del_usuario_se_recomienda_el_de_moldesign(aislado, monkeypatch):
    blender, python = _blender(aislado / "personal")
    monkeypatch.setattr(runtime_vc, "probar_python", lambda b, env, **_: {
        "ok": False, "python": str(python), "returncode": 0xC0000135, "codigo": "0xC0000135", "stdout": "", "stderr": ""})
    monkeypatch.setattr(addon.subprocess, "run", _sin_blender)
    addon._instalar(blender)
    assert addon.MENSAJE_VC_BLENDER_PROPIO in addon.estado()["motivo"]


def test_con_el_runtime_alterado_se_pide_reinstalar(aislado, monkeypatch):
    (aislado / "vc-runtime" / "x64" / "vcruntime140.dll").write_bytes(b"otra cosa")
    blender, python = _administrado()
    monkeypatch.setattr(runtime_vc, "probar_python", lambda b, env, **_: {
        "ok": False, "python": str(python), "returncode": 0xC0000135, "codigo": "0xC0000135", "stdout": "", "stderr": ""})
    monkeypatch.setattr(addon.subprocess, "run", _sin_blender)
    addon._instalar(blender)
    assert addon.MENSAJE_VC_DANADO in addon.estado()["motivo"]
    assert not (python.parent / "vcruntime140.dll").exists()


def test_un_catalogo_sin_sincronizar_se_dice_como_tal(aislado, monkeypatch):
    blender, python = _administrado()
    monkeypatch.setattr(runtime_vc, "probar_python", lambda b, env, **_: {
        "ok": True, "python": str(python), "returncode": 0, "codigo": "0x00000000", "stdout": "MOLCY_PY_OK 3.13.13", "stderr": ""})
    monkeypatch.setattr(addon.disk, "free_bytes", lambda _: 10 * addon.disk.GIB)
    repos = ("blender_org:\n    name: \"extensions.blender.org\"\n    directory: \"" + str(aislado).replace("\\", "/")
             + "\"\n    " + addon.OFFICIAL_REPOSITORY + "\n")
    llamadas = []

    def run(cmd, **kwargs):
        llamadas.append(cmd)
        if "repo-list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, repos, "")
        return subprocess.CompletedProcess(cmd, 1, "Done...\nRepository data: x\\extensions\\blender_org not found, sync required!\n"
                                           "Error: No installable packages marked\n", "")

    monkeypatch.setattr(addon.subprocess, "run", run)
    addon._instalar(blender)
    estado = addon.estado()
    assert len(llamadas) == 2
    assert estado["motivo"].startswith(f"{addon.MENSAJE_SIN_CATALOGO} {addon.MENSAJE_REVISA_LA_CONEXION} Registro completo: ")
    assert "No installable packages marked" in Path(estado["registro"]).read_text(encoding="utf-8")


def test_los_mensajes_nuevos_tienen_ingles_tambien_con_el_registro_detras():
    from core import i18n
    token = i18n.set_request_locale("en-US")
    try:
        compuesto = (f"{addon.MENSAJE_PYTHON_SIN_VC} {addon.MENSAJE_VC_SIN_COPIAR} "
                     r"Registro completo: C:\Users\Ana Ruiz\MolDesign\data\molcy\registros\molecular-nodes-20261012T101500Z.log")
        ingles = i18n.translate_text(compuesto)
        assert ingles.startswith("Blender's helper Python cannot start")
        assert ingles.endswith(r"Full record: C:\Users\Ana Ruiz\MolDesign\data\molcy\registros\molecular-nodes-20261012T101500Z.log")
        catalogo = i18n.translate_text(f"{addon.MENSAJE_SIN_CATALOGO} {addon.MENSAJE_REVISA_LA_CONEXION} "
                                       r"Registro completo: D:\datos\x.log")
        assert catalogo == ("Blender could not download the official extensions catalog (extensions.blender.org), so it did not "
                            r"find Molecular Nodes. Check the Internet connection and try again. Full record: D:\datos\x.log")
        codigo = i18n.translate_text("El Python auxiliar de Blender terminó con 0xC0000005 antes de poder instalar extensiones.")
        assert codigo == "Blender's helper Python exited with 0xC0000005 before it could install extensions."
    finally:
        i18n.reset_request_locale(token)


# --- Con el cargador real de Windows -------------------------------------------------------------------------------------

@pytest.mark.skipif(sys.platform != "win32", reason="el código 0xC0000135 es del cargador de Windows")
def test_el_cargador_real_da_0xC0000135_y_se_reconoce(tmp_path):
    """Un `python.exe` real sin la DLL que importa (aquí `python3xx.dll`) muere en el cargador con el mismo código que el de
    Blender sin Visual C++. Se comprueba que `probar_python` lo lee y que el mensaje es el de una DLL que falta."""
    # En un venv, `sys.executable` es un lanzador que no importa `python3xx.dll` y arranca sin ella.
    fuente = Path(getattr(sys, "_base_executable", None) or sys.executable)
    if not fuente.is_file():
        pytest.skip("sin intérprete en disco")
    blender, python = _blender(tmp_path / "blender")
    shutil.copyfile(fuente, python)
    (python.parent / "python313.dll").unlink()
    raiz = os.environ.get("SystemRoot", r"C:\Windows")
    entorno = {"SystemRoot": raiz, "PATH": str(Path(raiz) / "System32")}
    prueba = runtime_vc.probar_python(blender, entorno)
    assert prueba["ok"] is False
    assert prueba["codigo"] == "0xC0000135", prueba
    assert addon._motivo_python(prueba, blender).startswith(addon.MENSAJE_PYTHON_SIN_VC)
