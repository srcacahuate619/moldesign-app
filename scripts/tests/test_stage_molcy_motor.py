"""El motor Molcy que viaja en el instalador es íntegro, GPL y sin rutas de ninguna máquina.

    python -m pytest scripts/tests/test_stage_molcy_motor.py -q

# Qué se midió (2026-10-04) al vendorizarlo

La primera pasada de la guarda sobre el motor del propietario encontró TRES rutas de máquina en código que se ejecuta o viaja:
`C:\\Windows\\Fonts\\seguisb.ttf` y `...\\CascadiaMono.ttf` en el cierre de marca (Cascadia Mono no está en todo Windows 10: una
fuente ausente hacía fallar el cierre de TODOS los vídeos) y `D:\\moldesign-build\\msix\\assets\\...` en una herramienta de una sola vez.
Más `E:\\blender.exe`, `D:\\moldesign-build\\dist\\scenes` y `E:\\proyect3d\\moldesign\\cases` como valores por defecto del motor. Las tres
primeras se corrigieron en el repositorio del motor y la herramienta no se distribuye.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

import stage_molcy_motor as sm

RAIZ = Path(__file__).resolve().parents[2]
VENDORIZADO = RAIZ / "tools" / "molcy"


# --- El detector de rutas tiene que demostrar que ve (AGENTS.md, restricción 2) ------------------------------------------

DEBE_VER = {
    "ruta cruda de Windows": 'BLENDER = Path(r"E:\\blender.exe")',
    "ruta con barras dobles": 'CASOS = "E:\\\\proyect3d\\\\moldesign\\\\cases"',
    "ruta con barras normales": "ESCENAS = 'D:/moldesign-build/dist/scenes'",
    "carpeta del sistema": 'FUENTE = Path(r"C:\\Windows\\Fonts\\seguisb.ttf")',
    "parámetro de PowerShell": "    [string]$Blender = 'E:\\blender.exe',",
    "script de shell": 'BLENDER="E:/blender.exe"',
}
NO_DEBE_VER = {
    "una URL": 'WEB = "https://molecule-design.amezcua-dev.com/x"',
    "otra URL con puerto": 'API = "http://127.0.0.1:8000/health"',
    "una expresión regular": 'PAT = re.compile(r"\\d:\\d")',
    "una hora": 'FMT = "%H:%M:%S"',
    "un diccionario": "d = {'a': 1, 'b:': 2}",
    "una ruta relativa": 'RAIZ = Path(__file__).resolve().parents[2] / "moldesign" / "assets"',
    "una variable de entorno": 'RAIZ = os.environ.get("SystemRoot")',
    "un esquema de fichero": 'U = "file:///x/y"',
}


@pytest.mark.parametrize("nombre", sorted(DEBE_VER))
def test_el_detector_ve_lo_que_debe_ver(nombre):
    assert sm.rutas_de_maquina(DEBE_VER[nombre]), f"no detectó: {nombre}"


@pytest.mark.parametrize("nombre", sorted(NO_DEBE_VER))
def test_el_detector_no_acusa_lo_valido(nombre):
    assert sm.rutas_de_maquina(NO_DEBE_VER[nombre]) == [], f"acusó a algo válido: {nombre}"


def test_el_detector_informa_la_linea():
    assert sm.rutas_de_maquina("a = 1\nb = 2\nBLENDER = r'E:\\x.exe'\n")[0][0] == 3


# --- El motor vendorizado en el repositorio -------------------------------------------------------------------------------

def test_el_motor_vendorizado_es_integro():
    assert sm.verificar(VENDORIZADO) == []


def test_el_manifiesto_dice_lo_que_hay():
    manifiesto = json.loads((VENDORIZADO / sm.NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    assert manifiesto["schema"] == sm.ESQUEMA
    assert manifiesto["licencia_spdx"] == "GPL-3.0-or-later"
    assert manifiesto["requisitos"]["blender_minimo"] == "5.2"
    assert len(manifiesto["fuente"]["commit"]) == 40
    # la GPL pide poder obtener el código fuente: el manifiesto dice dónde está (el repositorio público del motor, sin credenciales)
    assert manifiesto["fuente"]["proyecto"] == "moldesign-molcy"
    assert manifiesto["fuente"]["repositorio"] == "https://github.com/srcacahuate619/moldesign-molcy"
    assert set(sm.INDISPENSABLES) <= set(manifiesto["archivos"])
    # nada del motor que no debe viajar
    for ruta in manifiesto["archivos"]:
        assert not ruta.startswith(("scripts/interfaz/", "scripts/pruebas/", "scripts/herramientas/", "moldesign/cases/",
                                    "moldesign/scripts/", "neuroanatomia/")), ruta
    assert "scripts/marca/preparar_emblema.py" not in manifiesto["archivos"]


def test_el_motor_vendorizado_no_importa_a_moldesign_ni_a_la_inversa():
    """La frontera: el motor sólo habla con MolDesign por ficheros."""
    for ruta in VENDORIZADO.rglob("*.py"):
        texto = ruta.read_text(encoding="utf-8")
        assert "import backend" not in texto and "from backend" not in texto, ruta
        assert "from services" not in texto and "from api." not in texto, ruta


def test_lo_que_viaja_pesa_poco():
    total = sum(p.stat().st_size for p in VENDORIZADO.rglob("*") if p.is_file())
    assert total < 5_000_000, total  # ~2,3 MB: el motor sin casos ni vídeos


# --- verificar(): cada forma de corrupción se ve ---------------------------------------------------------------------------

@pytest.fixture
def copia(tmp_path: Path) -> Path:
    destino = tmp_path / "molcy"
    shutil.copytree(VENDORIZADO, destino)
    assert sm.verificar(destino) == []
    return destino


def test_un_byte_cambiado_se_ve(copia):
    f = copia / "scripts" / "maestro.py"
    f.write_bytes(f.read_bytes() + b"\n# extra\n")
    assert any("scripts/maestro.py difiere" in p for p in sm.verificar(copia))


def test_un_fichero_de_mas_se_ve(copia):
    (copia / "scripts" / "extra.py").write_text("x = 1", encoding="utf-8")
    assert any("sobra scripts/extra.py" in p for p in sm.verificar(copia))


def test_un_fichero_que_falta_se_ve(copia):
    (copia / "scripts" / "salida" / "render.py").unlink()
    assert any("falta scripts/salida/render.py" in p for p in sm.verificar(copia))


def test_una_licencia_distinta_se_ve(copia):
    manifiesto_ruta = copia / sm.NOMBRE_MANIFIESTO
    (copia / "LICENSE").write_text("Licencia propia, todos los derechos reservados.\n", encoding="utf-8")
    manifiesto = json.loads(manifiesto_ruta.read_text(encoding="utf-8"))
    datos = (copia / "LICENSE").read_bytes()
    manifiesto["archivos"]["LICENSE"] = {"bytes": len(datos), "sha256": sm.sha256_bytes(datos)}
    manifiesto["sha256_conjunto"] = sm.sha256_conjunto(manifiesto["archivos"])
    manifiesto_ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
    # el manifiesto cuadra con el disco, pero la licencia ya no es la GPL: lo ve el contenido
    assert any("LICENSE no es el texto de la GPL" in p for p in sm.verificar(copia))


def test_una_ruta_de_maquina_en_el_codigo_se_ve(copia):
    manifiesto_ruta = copia / sm.NOMBRE_MANIFIESTO
    f = copia / "scripts" / "nucleo" / "rutas.py"
    f.write_bytes(f.read_bytes() + b'\nBLENDER = r"E:\\blender.exe"\n')
    manifiesto = json.loads(manifiesto_ruta.read_text(encoding="utf-8"))
    datos = f.read_bytes()
    manifiesto["archivos"]["scripts/nucleo/rutas.py"] = {"bytes": len(datos), "sha256": sm.sha256_bytes(datos)}
    manifiesto["sha256_conjunto"] = sm.sha256_conjunto(manifiesto["archivos"])
    manifiesto_ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
    assert any("ruta de una máquina concreta" in p for p in sm.verificar(copia))


def test_un_manifiesto_adulterado_se_ve(copia):
    manifiesto_ruta = copia / sm.NOMBRE_MANIFIESTO
    manifiesto = json.loads(manifiesto_ruta.read_text(encoding="utf-8"))
    manifiesto["sha256_conjunto"] = "0" * 64
    manifiesto_ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
    assert any("sha256_conjunto" in p for p in sm.verificar(copia))


def test_sin_manifiesto_o_ilegible(copia):
    (copia / sm.NOMBRE_MANIFIESTO).write_text("{no es json", encoding="utf-8")
    assert sm.verificar(copia) == [f"{sm.NOMBRE_MANIFIESTO} ilegible"]
    (copia / sm.NOMBRE_MANIFIESTO).unlink()
    assert sm.verificar(copia) == [f"falta {sm.NOMBRE_MANIFIESTO}"]


# --- Vendorizar lee el COMMIT, no el árbol de trabajo ---------------------------------------------------------------------

def _repo_de_motor(tmp_path: Path) -> Path:
    """Un repositorio git mínimo con los ficheros indispensables y la licencia verdadera."""
    repo = tmp_path / "motor"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    for clave, valor in (("user.email", "t@t"), ("user.name", "t"), ("core.autocrlf", "false")):
        subprocess.run(["git", "-C", str(repo), "config", clave, valor], check=True)
    for ruta in sm.INDISPENSABLES:
        destino = repo / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes((VENDORIZADO / ruta).read_bytes() if ruta == "LICENSE" else b"x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "motor"], check=True)
    return repo


def test_vendorizar_lee_el_commit_y_rechaza_un_arbol_sucio(tmp_path):
    repo = _repo_de_motor(tmp_path)
    contenido, origen = sm.leer_del_commit(repo)
    assert set(sm.INDISPENSABLES) <= set(contenido)
    assert len(origen["commit"]) == 40
    # un cambio sin commitear en lo que se copia: se rechaza en vez de vendorizar otra cosa
    (repo / "scripts" / "maestro.py").write_bytes(b"x = 2\n")
    with pytest.raises(SystemExit, match="sin commitear"):
        sm.leer_del_commit(repo)


def test_vendorizar_usa_los_bytes_del_blob_aunque_el_arbol_tenga_otros_saltos_de_linea(tmp_path):
    repo = _repo_de_motor(tmp_path)
    ruta = repo / "scripts" / "correr_caso.ps1"
    blob = subprocess.run(["git", "-C", str(repo), "show", "HEAD:scripts/correr_caso.ps1"], capture_output=True, check=True).stdout
    ruta.write_bytes(blob.replace(b"\n", b"\r\n"))
    subprocess.run(["git", "-C", str(repo), "update-index", "--assume-unchanged", "scripts/correr_caso.ps1"], check=True)
    contenido, _ = sm.leer_del_commit(repo)
    assert contenido["scripts/correr_caso.ps1"] == blob and b"\r\n" not in contenido["scripts/correr_caso.ps1"]


def test_no_se_vendoriza_lo_que_no_es_del_motor(tmp_path):
    repo = _repo_de_motor(tmp_path)
    for extra in ("scripts/interfaz/app.py", "scripts/pruebas/test_x.py", "moldesign/cases/001/x.mp4", "README.md",
                  "scripts/marca/preparar_emblema.py"):
        destino = repo / extra
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(b"x = 1\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "ruido"], check=True)
    contenido, _ = sm.leer_del_commit(repo)
    assert set(contenido) == set(sm.INDISPENSABLES)


def _con_remoto(repo: Path, url: str) -> None:
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", url], check=True)


@pytest.mark.parametrize("remoto,esperado", [
    ("https://github.com/srcacahuate619/moldesign-molcy.git", "https://github.com/srcacahuate619/moldesign-molcy"),
    ("https://github.com/srcacahuate619/moldesign-molcy", "https://github.com/srcacahuate619/moldesign-molcy"),
    ("https://usuario:ghp_secreto123@github.com/srcacahuate619/moldesign-molcy.git", "https://github.com/srcacahuate619/moldesign-molcy"),
    ("https://token@example.org:8443/x/y.git", "https://example.org:8443/x/y"),
])
def test_la_oferta_de_codigo_fuente_es_publica_y_nunca_lleva_credenciales(tmp_path, remoto, esperado):
    repo = _repo_de_motor(tmp_path)
    _con_remoto(repo, remoto)
    assert sm.repositorio_publico(repo) == esperado
    assert "secreto" not in (sm.repositorio_publico(repo) or "") and "@" not in (sm.repositorio_publico(repo) or "")


@pytest.mark.parametrize("remoto", ["git@github.com:srcacahuate619/moldesign-molcy.git", "ssh://git@github.com/x/y.git",
                                    "C:/repos/moldesign-molcy", "../moldesign-molcy", "file:///x/y"])
def test_un_remoto_que_no_es_publico_no_se_ofrece_como_codigo_fuente(tmp_path, remoto):
    repo = _repo_de_motor(tmp_path)
    _con_remoto(repo, remoto)
    assert sm.repositorio_publico(repo) is None


def test_sin_remoto_no_hay_oferta_que_inventar(tmp_path):
    assert sm.repositorio_publico(_repo_de_motor(tmp_path)) is None


def test_vendorizar_deja_en_el_manifiesto_el_repositorio_del_que_salio(tmp_path):
    repo = _repo_de_motor(tmp_path)
    _con_remoto(repo, "https://usuario:clave@github.com/srcacahuate619/moldesign-molcy.git")
    _, origen = sm.leer_del_commit(repo)
    assert origen["repositorio"] == "https://github.com/srcacahuate619/moldesign-molcy"
    assert "clave" not in json.dumps(origen)


def test_un_commit_sin_lo_indispensable_se_rechaza(tmp_path):
    repo = _repo_de_motor(tmp_path)
    subprocess.run(["git", "-C", str(repo), "rm", "-q", "scripts/salida/render.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "sin render"], check=True)
    with pytest.raises(SystemExit, match="indispensable"):
        sm.leer_del_commit(repo)
