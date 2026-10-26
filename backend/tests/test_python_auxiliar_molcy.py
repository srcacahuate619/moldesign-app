"""El Python del paquete no arranca desde PowerShell: el motor usa una copia que sí (vídeo 9, HOT FIX 1.0.3).

Las pruebas con ficheros falsos cubren la lógica de copia. La prueba con `python-embed` real comprueba lo que de verdad
importa: que la copia arranca como proceso hijo, importa Pillow y ejecuta los dos scripts del sellado.
"""
import subprocess
from pathlib import Path

import pytest

from services.molcy import python_auxiliar as pa

RAIZ = Path(__file__).resolve().parents[2]
PYTHON_EMBED = RAIZ / "python-embed"
SCRIPTS_SALIDA = RAIZ / "tools" / "molcy" / "scripts" / "salida"


def _origen_falso(tmp_path: Path) -> Path:
    origen = tmp_path / "python"
    origen.mkdir()
    (origen / "python.exe").write_bytes(b"MZ-exe")
    (origen / "python311.dll").write_bytes(b"dll-del-interprete")
    (origen / "python311.zip").write_bytes(b"biblioteca-estandar")
    (origen / "python311._pth").write_text("python311.zip\n.\n", encoding="utf-8")
    (origen / "vcruntime140.dll").write_bytes(b"dll-msvc")
    (origen / "LICENSE.txt").write_text("no se copia", encoding="utf-8")
    (origen / "Lib" / "site-packages" / "PIL").mkdir(parents=True)
    (origen / "Lib" / "site-packages" / "PIL" / "Image.py").write_text("x = 1\n", encoding="utf-8")
    return origen


def test_copia_lo_necesario_y_no_lo_demas(tmp_path):
    ejecutable = pa.python_auxiliar(_origen_falso(tmp_path), tmp_path / "destino")
    nombres = {p.name for p in ejecutable.parent.iterdir()}
    assert {"python.exe", "python311.dll", "python311.zip", "python311._pth", "vcruntime140.dll", "Lib", pa.NOMBRE_MANIFIESTO} <= nombres
    assert "LICENSE.txt" not in nombres
    assert (ejecutable.parent / "Lib" / "site-packages" / "PIL" / "Image.py").read_text(encoding="utf-8") == "x = 1\n"


def test_una_copia_completa_no_se_vuelve_a_copiar(tmp_path):
    origen = _origen_falso(tmp_path)
    ejecutable = pa.python_auxiliar(origen, tmp_path / "destino")
    marca = ejecutable.parent / "marca.txt"
    marca.write_text("sigue aqui", encoding="utf-8")
    assert pa.python_auxiliar(origen, tmp_path / "destino") == ejecutable
    assert marca.read_text(encoding="utf-8") == "sigue aqui"  # si se hubiera rehecho, la marca habría desaparecido


def test_cambiar_el_origen_crea_otra_copia(tmp_path):
    origen = _origen_falso(tmp_path)
    primera = pa.python_auxiliar(origen, tmp_path / "destino")
    (origen / "python311.dll").write_bytes(b"otra-version-del-interprete")
    segunda = pa.python_auxiliar(origen, tmp_path / "destino")
    assert segunda.parent != primera.parent
    assert (segunda.parent / "python311.dll").read_bytes() == b"otra-version-del-interprete"


def test_una_copia_a_medias_se_rehace(tmp_path):
    origen = _origen_falso(tmp_path)
    ejecutable = pa.python_auxiliar(origen, tmp_path / "destino")
    (ejecutable.parent / pa.NOMBRE_MANIFIESTO).unlink()  # como si el corte llegara antes de terminar
    (ejecutable.parent / "basura.tmp").write_text("de una copia cortada", encoding="utf-8")
    rehecho = pa.python_auxiliar(origen, tmp_path / "destino")
    assert rehecho == ejecutable
    assert (rehecho.parent / pa.NOMBRE_MANIFIESTO).is_file()
    assert not (rehecho.parent / "basura.tmp").exists()


def test_sin_pillow_el_motivo_se_dice(tmp_path):
    origen = _origen_falso(tmp_path)
    (origen / "Lib" / "site-packages" / "PIL" / "Image.py").unlink()
    (origen / "Lib" / "site-packages" / "PIL").rmdir()
    with pytest.raises(RuntimeError, match="PIL"):
        pa.python_auxiliar(origen, tmp_path / "destino")


@pytest.mark.skipif(not (PYTHON_EMBED / "python311.zip").is_file(), reason="sin python-embed (runtime de desarrollo)")
def test_la_copia_real_arranca_importa_pillow_y_ejecuta_el_sellado(tmp_path):
    ejecutable = pa.python_auxiliar(PYTHON_EMBED, tmp_path / "destino")
    importa = subprocess.run([str(ejecutable), "-I", "-c", "from PIL import Image; print('PILOK', Image.__name__)"],
                             capture_output=True, text=True, timeout=120, check=False)
    assert importa.returncode == 0 and "PILOK" in importa.stdout, importa.stderr
    # Los scripts sin argumentos terminan con «uso:» (código 2): prueba de que arrancan y pasan sus importaciones.
    for script in ("sellar_mp4.py", "contraste.py"):
        ejecuta = subprocess.run([str(ejecutable), str(SCRIPTS_SALIDA / script)], capture_output=True, text=True,
                                 timeout=120, check=False)
        assert ejecuta.returncode == 2 and "uso:" in ejecuta.stdout + ejecuta.stderr, (script, ejecuta.stderr)


@pytest.mark.skipif(not (PYTHON_EMBED / "python311.zip").is_file(), reason="sin python-embed (runtime de desarrollo)")
def test_la_copia_ignora_el_pythonpath_que_exporta_el_backend(tmp_path):
    # backend.rs exporta PYTHONPATH=<backend> al proceso del backend, y el hijo lo hereda. Con python311._pth, Python lo ignora:
    # un módulo que sólo existe en esa ruta no debe importarse, o la copia cargaría código ajeno.
    intruso = tmp_path / "intruso"
    intruso.mkdir()
    (intruso / "modulo_ajeno_molcy.py").write_text("ESTADO = 'ajeno'\n", encoding="utf-8")
    ejecutable = pa.python_auxiliar(PYTHON_EMBED, tmp_path / "destino")
    entorno = {"PYTHONPATH": str(intruso), "SYSTEMROOT": "C:\Windows", "PATH": "C:\Windows\System32"}
    ajeno = subprocess.run([str(ejecutable), "-c", "import modulo_ajeno_molcy"], capture_output=True, text=True,
                           timeout=120, check=False, env=entorno)
    assert ajeno.returncode != 0, "la copia importó un módulo de PYTHONPATH"
    util = subprocess.run([str(ejecutable), "-c", "from PIL import Image; print('PILOK')"], capture_output=True, text=True,
                          timeout=120, check=False, env=entorno)
    assert util.returncode == 0 and "PILOK" in util.stdout, util.stderr


def test_dos_llamadas_a_la_vez_dejan_una_sola_copia_completa(tmp_path):
    import threading
    origen = _origen_falso(tmp_path)
    resultados, errores = [], []

    def preparar():
        try:
            resultados.append(pa.python_auxiliar(origen, tmp_path / "destino"))
        except Exception as exc:  # noqa: BLE001 - la prueba quiere ver cualquier fallo
            errores.append(exc)

    hilos = [threading.Thread(target=preparar) for _ in range(6)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert not errores, errores
    assert len(set(resultados)) == 1
    assert (resultados[0].parent / pa.NOMBRE_MANIFIESTO).is_file()
