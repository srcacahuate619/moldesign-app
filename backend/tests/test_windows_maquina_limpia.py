"""Lo que rompe en un Windows limpio y no se ve desde la maquina de desarrollo.

Este barrido salio de un hallazgo concreto: el generador de PDF buscaba su fuente
en `/usr/share/fonts/truetype/dejavu/…`, una ruta de LINUX. En Windows nunca
existe, caia a Courier, y de ahi salia el defecto D2 del doc 71 -las vinetas
extraidas como U+007F-. Esa es la firma de toda una familia: **codigo escrito o
probado en otro sistema que en Windows degrada en silencio.**

Las pruebas de aqui son en su mayoria ESTATICAS, y conviene decir por que: el
fallo se manifiesta en una maquina que no es esta. No se puede reproducir un
«Windows recien instalado» desde dentro de el, asi que se vigila la causa -una
ruta absoluta, una variable de entorno ausente- en vez del sintoma.

Lo que SI se midio de verdad, sobre el interprete que se instala
(`python-embed`, 3.11.9), esta anotado en cada prueba.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
BACKEND = RAIZ / "backend"


def _fuentes_de_produccion() -> list[pathlib.Path]:
    """El backend sin pruebas ni cache. Los `scripts/` de experimento quedan
    fuera a proposito: no se instalan, y sus rutas absolutas describen la
    maquina donde se corrio un experimento sellado."""
    return [
        p for p in BACKEND.rglob("*.py")
        if "tests" not in p.parts and "__pycache__" not in p.parts
    ]


# ── Rutas de otra maquina ────────────────────────────────────────────────────

#: Una ruta absoluta a un disco concreto no puede estar en codigo que se
#: instala: en otra maquina apunta a la nada o, peor, a lo que esa persona
#: tenga ahi.
RUTA_DE_OTRA_MAQUINA = re.compile(
    r"""["'r]{1,2}[A-Za-z]:[\\/](?:moldesign|Users)[\\/]""",
    re.IGNORECASE,
)


def test_ningun_modulo_instalado_apunta_a_un_disco_concreto():
    """`mmgbsa_subprocess.py` insertaba `D:\\moldesign-build\\backend` en
    `sys.path`. En cualquier instalacion real ese directorio no existe, el
    import fallaba, y el `except` lo devolvia como
    `{"error": "No module named 'services'"}`: MM-GBSA no podia funcionar en
    NINGUNA maquina que no fuera la de construccion, y el mensaje no apuntaba a
    la causa.
    """
    culpables = []
    for p in _fuentes_de_produccion():
        for i, linea in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if linea.lstrip().startswith("#"):
                continue  # los comentarios explican por que ya no estan
            if RUTA_DE_OTRA_MAQUINA.search(linea):
                culpables.append(f"{p.relative_to(RAIZ)}:{i}  {linea.strip()[:90]}")
    assert not culpables, "rutas absolutas a otra maquina:\n" + "\n".join(culpables)


RUTA_POSIX = re.compile(r"^/(usr|opt|etc|var|home|bin|sbin)/")


def test_ninguna_ruta_de_linux_es_la_unica_candidata():
    """El `font_path` del PDF era exactamente esto, y produjo el defecto D2.

    La comprobacion es POR AST y no por texto: una ruta de Linux DENTRO de una
    lista de candidatas es correcta -varios modulos prueban Linux, Unix y
    Windows en orden y se quedan con la que exista-. Lo que no puede estar es
    una ruta de Linux SOLA, como valor unico.

    La primera version de esta prueba miraba el archivo entero buscando pistas
    de que hubiera alternativa, y marco `chem/properties.py`, que tiene tres
    candidatas incluida la de Windows. Una prueba que obliga a ensuciar codigo
    sano para callarla es peor que no tenerla.
    """
    culpables = []
    for p in _fuentes_de_produccion():
        try:
            arbol = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        # Constantes de texto que estan dentro de una lista/tupla de dos o mas:
        # esas son candidatas y quedan exentas.
        exentas = set()
        for n in ast.walk(arbol):
            if isinstance(n, (ast.List, ast.Tuple)) and len(n.elts) >= 2:
                for e in n.elts:
                    exentas.add(id(e))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Constant) or not isinstance(n.value, str):
                continue
            if not RUTA_POSIX.match(n.value) or id(n) in exentas:
                continue
            culpables.append(f"{p.relative_to(RAIZ)}:{n.lineno}  {n.value[:70]}")
    assert not culpables, (
        "rutas de Linux usadas como valor unico, sin alternativa en Windows: "
        + "; ".join(culpables)
    )


# ── Codificacion ─────────────────────────────────────────────────────────────

def test_el_lanzador_arranca_el_backend_en_modo_utf8():
    """LA MAS IMPORTANTE DE ESTE ARCHIVO, y la unica medida de verdad.

    Medido sobre `python-embed/python.exe` (3.11.9), que es el interprete que se
    instala:

        sin PYTHONUTF8   leer un archivo UTF-8 sin `encoding=` devuelve
                         CONTENIDO CORROMPIDO, sin excepcion;
                         escribir una cadena con «→» -> UnicodeEncodeError;
                         sys.stdout.encoding = cp1252.
        con PYTHONUTF8   las tres cosas correctas.

    El backend tiene 87 llamadas de texto sin `encoding=` explicito. Se arregla
    en el unico sitio donde se define el entorno del proceso, y los subprocesos
    -Vina, los sidecars, MM-GBSA- lo heredan.

    La lectura silenciosa es la peor de las tres: un PDB o un JSON con un acento
    vuelve mal y nadie se entera.
    """
    backend_rs = RAIZ / "frontend" / "src-tauri" / "src" / "backend.rs"
    if not backend_rs.is_file():
        pytest.skip("el lanzador Tauri no esta en este arbol")
    fuente = backend_rs.read_text(encoding="utf-8")
    assert '.env("PYTHONUTF8", "1")' in fuente, (
        "el backend arrancaria con la pagina de codigos del sistema; en un "
        "Windows en espanol eso es cp1252 y las 87 llamadas de texto sin "
        "`encoding=` explicito leen mal y escriben peor"
    )


# ── Limpieza de temporales ───────────────────────────────────────────────────

def test_los_temporales_del_camino_de_docking_se_limpian_sin_reventar():
    """En Windows no se puede borrar un archivo que alguien tenga abierto.

    Dentro de estos directorios corren procesos hijos -Meeko, Vina, Open Babel-
    y el antivirus escanea lo recien escrito. Sin `ignore_cleanup_errors`, la
    limpieza levanta PermissionError DESPUES de que el trabajo haya terminado
    bien: se pierde una corrida completa por no poder borrar un temporal.
    """
    criticos = [
        BACKEND / "services" / "docking" / "preparer.py",
        BACKEND / "services" / "docking" / "vina_service.py",
        BACKEND / "services" / "chemistry" / "structural_evidence.py",
        BACKEND / "services" / "docking" / "quantum_ad4_service.py",
    ]
    fallos = []
    for p in criticos:
        arbol = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(arbol):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            nombre = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if nombre != "TemporaryDirectory":
                continue
            if not any(k.arg == "ignore_cleanup_errors" for k in n.keywords):
                fallos.append(f"{p.relative_to(RAIZ)}:{n.lineno}")
    assert not fallos, (
        "temporales que pueden tirar una corrida ya terminada: " + ", ".join(fallos)
    )


# ── Herramientas que Windows ya no trae ──────────────────────────────────────

def test_no_se_depende_de_wmic():
    """`wmic` ESTA ELIMINADO de Windows 11 moderno.

    Comprobado en la maquina de desarrollo (build 26200): `where wmic` no lo
    encuentra y `subprocess.run` levanta FileNotFoundError. Como la llamada
    vivia dentro de un `except Exception`, el fallo no se veia: el modelo de CPU
    caia al respaldo «6C/12T CPU» y eso acababa en la seccion de entorno del
    dossier.
    """
    culpables = [
        str(p.relative_to(RAIZ))
        for p in _fuentes_de_produccion()
        if '"wmic"' in p.read_text(encoding="utf-8", errors="replace")
        or "'wmic'" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert not culpables, f"dependen de wmic, que ya no existe: {culpables}"


def test_el_modelo_de_cpu_se_obtiene_de_verdad():
    """Comprobacion de comportamiento, no de fuente: aqui SI se puede."""
    import os

    if os.name != "nt":
        pytest.skip("solo aplica en Windows")

    from core.hardware import detect_hardware

    modelo = detect_hardware().cpu_model
    assert modelo, "no se obtuvo ningun modelo de CPU"
    # El respaldo «6C/12T CPU» significa que las dos vias fallaron.
    assert not re.fullmatch(r"\d+C/\d+T CPU", modelo), (
        f"el modelo de CPU cayo al respaldo generico: {modelo!r}"
    )
