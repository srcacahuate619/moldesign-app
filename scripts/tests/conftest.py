"""Deja `scripts/` importable y da los ladrillos que usan las pruebas.

Estas pruebas NO tocan el árbol de trabajo. Cada una construye su propio árbol
en un temporal de pytest, lo empaqueta y lo aprovisiona ahí. La razón es la
regla que este mismo trabajo existe para sostener: un aprovisionador que
escribe donde no le han dicho ya destruyó 102 resultados en este proyecto, y
una prueba que reutiliza el árbol real es la misma clase de error con otro
sombrero.

Corolario práctico: **ninguna prueba de aquí demuestra nada sobre las piezas ya
aprovisionadas en la máquina de quien la ejecuta.** Los árboles son sintéticos
y sus entradas están controladas una por una.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))


@pytest.fixture(scope="session")
def raiz_del_repositorio() -> Path:
    return RAIZ


@pytest.fixture
def arbol(tmp_path: Path) -> Path:
    """Un árbol de origen sintético, mínimo y completo.

    Trae los tres componentes obligatorios y algo de ruido que NO debe viajar:
    un `__pycache__`, un directorio `test/` y código del repositorio.
    """
    raiz = tmp_path / "origen"

    def escribir(relativa: str, cuerpo: bytes) -> None:
        destino = raiz / relativa
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(cuerpo)

    escribir("python-embed/python.exe", b"MZ" + b"\x00" * 64)
    escribir("python-embed/Lib/site-packages/rdkit/__init__.py", b"# rdkit\n")
    escribir("python-embed/Lib/site-packages/numpy/_core.pyd", b"\x00" * 32)
    escribir("tools/vina/vina.exe", b"vina-de-mentira")
    escribir("tools/openbabel/bin/obabel.exe", b"obabel-de-mentira")
    escribir("tools/openbabel/bin/data/atomtyp.txt", b"tabla de tipos\n")
    escribir("data/molgraph_seed.db", b"SQLite format 3\x00")

    # Ruido que el empaquetador tiene que dejar fuera.
    escribir("python-embed/Lib/site-packages/x/__pycache__/a.pyc", b"basura")
    escribir("python-embed/Lib/test/test_x.py", b"basura")
    escribir("backend/api/main.py", b"# codigo del producto\n")
    escribir("scripts/bundle_helper.py", b"# codigo del producto\n")
    escribir("rescoring/artifacts/gnn_v2_cl_best.pt", b"pesos propios")
    return raiz


def _git(destino: Path, *orden: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(destino), *orden],
        capture_output=True, text=True, timeout=300,
    )


@pytest.fixture
def clon(tmp_path: Path) -> Path:
    """Un repositorio de destino sintético, con índice de git de verdad.

    Tiene que ser un repositorio y no una carpeta: la segunda muralla del
    bootstrap pregunta a `git ls-files`, y sobre una carpeta suelta esa
    comprobación no existiría — la prueba estaría comprobando menos de lo que
    dice.

    Es sintético y no un clon del repositorio real por velocidad (clonar 3.896
    archivos por prueba costaba dos minutos de suite) y por control: aquí se
    sabe exactamente qué archivos hay versionados. El clon de verdad se usa
    donde hace falta, en `clon_real`.
    """
    if shutil.which("git") is None:
        pytest.skip("no hay git: la segunda muralla no se puede comprobar")
    destino = tmp_path / "destino"
    destino.mkdir()

    versionados = {
        # Código del producto: lo que un artefacto no puede tocar jamás.
        "backend/api/main.py": b"# el backend de verdad\n",
        "scripts/bundle_helper.py": b"# el empaquetador de verdad\n",
        # Un archivo versionado DENTRO de un destino permitido: es la única
        # forma de probar la segunda muralla por separado de la primera.
        "tools/llama/README.md": b"llama.cpp: el binario no viaja en el repo\n",
        "tools/openbabel/openbabel-manifest.json": b"{}\n",
        ".gitignore": b"python-embed/\ndist/\ntools/**/*.exe\ndata/*.db\n",
    }
    for relativa, cuerpo in versionados.items():
        ruta = destino / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(cuerpo)

    _git(destino, "init", "--quiet")
    _git(destino, "config", "user.email", "pruebas@moldesign.local")
    _git(destino, "config", "user.name", "pruebas")
    _git(destino, "add", "-A")
    resultado = _git(destino, "commit", "--quiet", "--no-verify", "-m", "base")
    if resultado.returncode != 0:
        pytest.skip(f"no se pudo preparar el repositorio: {resultado.stderr[:200]}")
    return destino


@pytest.fixture
def clon_real(tmp_path: Path) -> Path:
    """Un `git clone` de esta rama, en un directorio temporal cualquiera.

    Lento —clona el árbol entero— así que lo usa sólo la prueba del clon
    limpio, que es donde el realismo es el punto: demuestra que aprovisionar no
    depende de `D:\\moldesign-build` ni de nada ya provisionado en esta máquina.
    """
    if shutil.which("git") is None:
        pytest.skip("no hay git: la prueba del clon no se puede montar")
    destino = tmp_path / "clon"
    proceso = subprocess.run(
        ["git", "clone", "--quiet", "--no-hardlinks", str(RAIZ), str(destino)],
        capture_output=True, text=True, timeout=900,
    )
    if proceso.returncode != 0:
        pytest.skip(f"git clone falló: {proceso.stderr.strip()[:200]}")
    return destino
