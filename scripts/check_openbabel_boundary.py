#!/usr/bin/env python3
r"""Guarda de la frontera con Open Babel. Bloquea el build si se rompe.

# Qué vigila

Open Babel es un **programa independiente GPL-2.0-only** que MolDesign
distribuye en el mismo instalador y ejecuta como herramienta de línea de
órdenes. Esa frontera no se sostiene sola: basta un `from openbabel import
openbabel` en el módulo equivocado, o un `shutil.which("obabel")` bien
intencionado, para que deje de ser cierta sin que nada lo diga.

Las nueve comprobaciones, en el orden en que aparecen:

    G1  ningún `.py` de `backend/` ni `rescoring/` importa `openbabel`, `pybel` ni
        `_openbabel` (AST sobre TODO el árbol; sólo las excepciones declaradas)
    G2  esos bindings no están en el `site-packages` del backend empaquetado
    G3  producción no resuelve `obabel` por PATH
    G4  el ejecutable empaquetado está donde dice el manifiesto
    G5  su hash coincide con el manifiesto
    G6  `obabel -V` devuelve la versión declarada
    G7  una conversión PDBQT→SDF real funciona sobre el árbol comprobado
    G8  el docking se abstiene si Meeko no exporta un SDF utilizable
    G9  el SBOM y la pantalla de licencias NO lo llaman `GPL-2.0-or-later`

# Por qué cada guarda lleva su propia muestra rota

Porque ya pasó lo contrario. Un detector de este árbol quedó con un carácter
`0x08` dentro de su expresión regular, recorrió 167 archivos y anunció «limpio»
sobre un export sucio. Aquí cada comprobación se ejecuta primero contra una
muestra que **debe** marcar y otra que **no** debe marcar, y el script aborta si
alguna de las dos falla. Un guardián que no demuestra que ve no sirve.

# Alcance

    python scripts/check_openbabel_boundary.py            # árbol de desarrollo
    python scripts/check_openbabel_boundary.py --bundle   # además, el bundle staged

Sin `--bundle` se comprueba el repositorio. Con `--bundle` se comprueba también
`frontend/src-tauri/resources`, que es lo que de verdad se entrega: las pruebas
del *código* estaban verdes mientras la aplicación instalada fallaba, y ese
error no se repite aquí.

Sobre un clon limpio, `tools/openbabel/bin/` no existe —los binarios no se
versionan, igual que Vina y xTB— así que G4-G7 no pueden comprobar nada. En ese
caso lo DICEN y devuelven un código distinto de «verificado»; no se anuncian en
verde. Con `--exigir-binario` (lo que hace el build) la ausencia es un fallo.

# El alcance de G1 y la lista de excepciones

G1 mira **todos** los `.py` de `backend/` y `rescoring/` —`tests/`, `scripts/`,
`data/`, `artifacts/` y `deprecated/` incluidos— y detecta `import`, `from ... import`
e imports dinámicos con nombre constante (`__import__("openbabel")`,
`importlib.import_module("pybel")`). Un nombre calculado en tiempo de ejecución no
se ve: es el límite del análisis estático, y se declara en vez de callarse. Un archivo
que no se puede analizar es un fallo, no un «limpio».

La única excepción es `EXCEPCIONES_DEV_ONLY`: scripts de desarrollo, nombrados uno a
uno y con su motivo escrito, que no viajan en el instalador. Esa lista no se amplía
para que la guarda pase: añadir una es una decisión del propietario (AGENTS.md,
`docs/79_ADR_FRONTERA_OPEN_BABEL.md` §5.1, `docs/86`, LUNA-01). `g1b` comprueba que
cada una existe y que `bundle_helper` la excluye del empaquetado; G2 y G1 sobre el
bundle comprueban, sin ninguna exención, que no viaja.

Exit code: 0 = frontera intacta, 1 = rota.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# La consola de Windows usa cp1252: un carácter fuera de esa tabla convierte un
# informe en un traceback DESPUÉS de haber hecho el trabajo. Ver salida_consola.
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # noqa: E402
    from salida_consola import consola_utf8
except ImportError:  # pragma: no cover - un clon puede no traer el ayudante
    # Se degrada en vez de morir: esto es presentación, no resultado. Un script
    # de aprovisionamiento que no arranca porque falta una comodidad de consola
    # deja al que clona sin la única herramienta que tenía para desbloquearse.
    def consola_utf8() -> None:
        import sys as _sys
        for _flujo in (_sys.stdout, _sys.stderr):
            _reconfigurar = getattr(_flujo, "reconfigure", None)
            if _reconfigurar is not None:
                try:
                    _reconfigurar(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]
RESOURCES = RAIZ / "frontend" / "src-tauri" / "resources"

# ── Qué recorre cada comprobación ────────────────────────────────────────
#
# G1 mira TODO `.py` de estos dos árboles. Antes filtraba por nombre de directorio
# (`NO_ES_PRODUCCION`: `tests`, `scripts`, `data`...) y por una lista de módulos «de
# desarrollo» leída de `bundle_helper`: «limpio» era cierto sólo del subconjunto
# que miraba, y un recorrido AST completo encontró siete imports que el filtro no
# veía (auditoría LUNA-01). La regla de AGENTS.md no distingue directorios.
ARBOLES_DE_PRODUCCION = ("backend", "rescoring")

#: Módulos que sí pueden nombrar Open Babel (cadenas, nombre del ejecutable): el
#: adaptador y su paquete. Sólo exime de G3; NUNCA de G1 —el adaptador invoca el
#: programa, no importa los bindings—.
EXENTOS = (
    "backend/services/external_tools/open_babel.py",
    "backend/services/external_tools/__init__.py",
)

#: Ruido de máquina, no código del proyecto: nada de esto se versiona ni viaja.
DIRECTORIOS_IGNORADOS = frozenset(
    {"__pycache__", "node_modules", ".venv", "venv", "site-packages", ".git"}
)

#: LO ÚNICO QUE G1 DEJA PASAR. Scripts de desarrollo que importan los bindings y
#: que no viajan en el instalador (decisión del propietario, 2026-10-03; ver
#: `docs/86_CORRECCIONES_AUDITORIA_LUNA_20261002.md`, LUNA-01).
#:
#: Cada uno lleva su motivo, porque una excepción sin motivo es una puerta sin
#: dueño. La lista NO se amplía para que la guarda pase: una violación nueva se
#: arregla o se lleva al propietario. Tampoco se confía en ella a ciegas:
#: `g1b_excepciones_coherentes` exige que cada entrada exista y que
#: `bundle_helper` la excluya del empaquetado, y G2 / G1-sobre-el-bundle lo
#: comprueban en el artefacto.
EXCEPCIONES_DEV_ONLY: dict[str, str] = {
    "rescoring/generate_gpu_dataset.py": (
        "Genera los datasets de entrenamiento (docking y features 3D de PDBbind); "
        "nunca fue runtime. `bundle_helper` lo excluye por nombre "
        "(RESCORING_FUERA_DEL_RUNTIME_FILES) y su cabecera ya lo declara "
        "dependencia de desarrollo."
    ),
    "rescoring/RTMScore/feats/extract_pocket_prody.py": (
        "Ayudante de preparación de bolsillos del código de terceros RTMScore (MIT); "
        "ningún módulo del producto lo importa (`gnn_service` usa mol2graph_pyg y "
        "RTMScore.model.*). `bundle_helper` lo excluye por nombre."
    ),
    "rescoring/scripts/redock_pdbbind.py": (
        "Preparación del redocking de PDBbind con los bindings de Open Babel (receptor "
        "PDB→PDBQT rígido). 1414 registros de procedencia de cinco artefactos sellados "
        "declaran el receptor «openbabel_pdb2pdbqt_rigido» y en FND-06 470 citan este "
        "archivo como el código de preparación; además lo importan scripts/molflex*.py, "
        "calibrate_redock.py y otros por ruta. Reescribirlo cambiaría lo medido. "
        "`rescoring/scripts` no viaja (RESCORING_DIRS_FUERA_DEL_RUNTIME)."
    ),
    "rescoring/scripts/test_crystal_vs_docked.py": (
        "Experimento de desarrollo (degradación de features cristal vs acoplado) que "
        "prepara el receptor con los bindings; no es una prueba del producto y nadie lo "
        "importa. `rescoring/scripts` no viaja (RESCORING_DIRS_FUERA_DEL_RUNTIME)."
    ),
}

#: Alcance de G3 (resolución por PATH): sigue siendo CÓDIGO DE PRODUCCIÓN. Es una
#: búsqueda por expresión regular sobre el texto, y en `tests/` abundan las
#: muestras que contienen justo lo que se busca; aquí el filtro por directorio sí
#: tiene sentido, y por eso G1 y G3 ya no comparten recorrido.
NO_ES_PRODUCCION = {
    "tests", "test", "__pycache__", "deprecated", "scripts", "data",
    "node_modules", ".venv", "artifacts", "trained_models",
}

MODULOS_PROHIBIDOS = {"openbabel", "pybel", "_openbabel"}

#: Nombres cuya presencia en `site-packages` significa que los bindings viajan.
HUELLAS_DE_BINDINGS = (
    "openbabel",
    "pybel.py",
    "_openbabel.pyd",
    "_openbabel.so",
    "openbabel_wheel.libs",
)

#: Formas de resolver el ejecutable por entorno. Todas prohibidas en producción.
RESOLUCION_POR_PATH = (
    re.compile(r"shutil\.which\(\s*[\"']obabel"),
    re.compile(r"which\(\s*[\"']obabel"),
    # `"obabel"` o `'obabel'` como argumento suelto de un subprocess.
    re.compile(r"(?:create_subprocess_exec|Popen|run|call|check_output)\s*\(\s*[\"']obabel[\"']"),
    re.compile(r"\[\s*[\"']obabel[\"']\s*,"),
    re.compile(r"os\.environ\[[\"']PATH[\"']\].{0,80}obabel", re.DOTALL),
)

LICENCIA_INCORRECTA = re.compile(r"GPL-2\.0-or-later", re.IGNORECASE)


@dataclass
class Resultado:
    ok: bool = True
    verificado: list[str] = field(default_factory=list)
    fallos: list[str] = field(default_factory=list)
    saltado: list[str] = field(default_factory=list)

    def bien(self, mensaje: str) -> None:
        self.verificado.append(mensaje)

    def mal(self, mensaje: str) -> None:
        self.ok = False
        self.fallos.append(mensaje)

    def salta(self, mensaje: str) -> None:
        self.saltado.append(mensaje)


# ── Detectores (cada uno con su autotest más abajo) ──────────────────────


def _nombre_importado_dinamicamente(llamada: ast.Call) -> str | None:
    """`__import__("x")` / `importlib.import_module("x")` con nombre CONSTANTE."""
    funcion = llamada.func
    if isinstance(funcion, ast.Name):
        nombre = funcion.id
    elif isinstance(funcion, ast.Attribute):
        nombre = funcion.attr
    else:
        return None
    if nombre not in ("__import__", "import_module") or not llamada.args:
        return None
    primero = llamada.args[0]
    if isinstance(primero, ast.Constant) and isinstance(primero.value, str):
        return primero.value
    return None


def analizar_imports(fuente: str | bytes) -> tuple[list[tuple[str, int]], str | None]:
    """(hallazgos, error): imports prohibidos con su línea, y por qué no se pudo leer.

    Se analiza el AST y no el texto: un comentario que explique la prohibición
    no es una violación, y una guarda que no sepa distinguirlos convertiría
    cada explicación en un falso positivo — y acabaría desactivada.

    Lo que NO ve, declarado: un nombre de módulo calculado en tiempo de ejecución
    (`importlib.import_module(nombre)`). Y lo que NO hace: devolver «limpio» ante un
    archivo que no pudo leer —el detector anterior contestaba `[]` ante un
    `SyntaxError`, y la auditoría LUNA que originó este cambio escaneó con
    `except: continue`—. El error se devuelve aparte para que quien llama lo trate
    como lo que es: un archivo sin mirar.
    """
    try:
        arbol = ast.parse(fuente)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        return [], f"{type(exc).__name__}: {str(exc)[:120]}"
    hallazgos: set[tuple[str, int]] = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name.split(".")[0] in MODULOS_PROHIBIDOS:
                    hallazgos.add((alias.name, nodo.lineno))
        elif isinstance(nodo, ast.ImportFrom):
            # `level > 0` es un import RELATIVO: `from .openbabel import x` nombra un
            # módulo local, no los bindings. `from x import openbabel` sólo importa un
            # nombre de `x`, no el paquete.
            if nodo.level == 0 and (nodo.module or "").split(".")[0] in MODULOS_PROHIBIDOS:
                hallazgos.add((nodo.module or "", nodo.lineno))
        elif isinstance(nodo, ast.Call):
            dinamico = _nombre_importado_dinamicamente(nodo)
            if dinamico and dinamico.split(".")[0] in MODULOS_PROHIBIDOS:
                hallazgos.add((dinamico, nodo.lineno))
    return sorted(hallazgos, key=lambda h: (h[1], h[0])), None


def importa_prohibido(fuente: str | bytes) -> list[str]:
    """Módulos prohibidos que este archivo IMPORTA de verdad (ver `analizar_imports`)."""
    hallazgos, _ = analizar_imports(fuente)
    return sorted({modulo for modulo, _linea in hallazgos})


def _sin_comentarios(fuente: str) -> str:
    """Borra los comentarios `#` conservando las posiciones del resto.

    `vina_service.py` explica en sus comentarios justo lo que tiene prohibido;
    buscar sobre el texto crudo daría positivos que no son código.
    """
    import io
    import tokenize

    lineas = fuente.splitlines(keepends=True)
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(fuente).readline))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return fuente
    for token in tokens:
        if token.type is not tokenize.COMMENT:
            continue
        fila = token.start[0] - 1
        ini, fin = token.start[1], token.end[1]
        linea = lineas[fila]
        lineas[fila] = linea[:ini] + " " * (fin - ini) + linea[fin:]
    return "".join(lineas)


def resuelve_por_path(fuente: str) -> list[str]:
    """Formas de encontrar `obabel` fuera del bundle."""
    codigo = _sin_comentarios(fuente)
    hallazgos: list[str] = []
    for patron in RESOLUCION_POR_PATH:
        for m in patron.finditer(codigo):
            hallazgos.append(m.group(0)[:80])
    return hallazgos


# ── AUTOTEST: cada detector, contra lo que debe y no debe ver ────────────

_DEBE_VER_IMPORT = (
    "from openbabel import openbabel\n",
    "import openbabel\n",
    "from openbabel import pybel\n",
    "import pybel\n",
    "import openbabel.openbabel as ob\n",
    '__import__("openbabel")\n',
    'import importlib\nimportlib.import_module("openbabel.openbabel")\n',
    "def f():\n    try:\n        import pybel\n    except ImportError:\n        pass\n",
)
_NO_DEBE_VER_IMPORT = (
    "# from openbabel import openbabel  <- prohibido, ver el ADR\n",
    '"""Se prohíbe `import pybel` en producción."""\n',
    "from services.external_tools import open_babel\n",
    "texto = 'openbabel'\n",
    "from rdkit import Chem\n",
    "from .openbabel import algo\n",                         # módulo local
    "import importlib\nimportlib.import_module(nombre)\n",   # nombre no constante
    '__import__("rdkit")\n',
)
_DEBE_VER_PATH = (
    'shutil.which("obabel")\n',
    "proc = await create_subprocess_exec('obabel', '-ipdbqt', x)\n",
    'subprocess.run(["obabel", "-V"])\n',
)
_NO_DEBE_VER_PATH = (
    '# nunca se hace shutil.which("obabel"): resolvería un binario ajeno\n',
    'shutil.which("vina")\n',
    "exe = base / manifiesto['ejecutable']\n",
    'subprocess.run([str(exe), "-V"])\n',
)


def autotest() -> None:
    """Un guardián que no demuestra que ve no sirve. Aborta si no ve."""
    for muestra in _DEBE_VER_IMPORT:
        if not importa_prohibido(muestra):
            raise SystemExit(
                f"[check-openbabel] AUTOTEST FALLIDO: el detector de imports no "
                f"ve `{muestra.strip()}`. La guarda anunciaría verde sobre un "
                "árbol contaminado."
            )
    for muestra in _NO_DEBE_VER_IMPORT:
        if importa_prohibido(muestra):
            raise SystemExit(
                f"[check-openbabel] AUTOTEST FALLIDO: el detector de imports marca "
                f"de más en `{muestra.strip()[:60]}`."
            )
    for muestra in _DEBE_VER_PATH:
        if not resuelve_por_path(muestra):
            raise SystemExit(
                f"[check-openbabel] AUTOTEST FALLIDO: el detector de PATH no ve "
                f"`{muestra.strip()}`."
            )
    for muestra in _NO_DEBE_VER_PATH:
        if resuelve_por_path(muestra):
            raise SystemExit(
                f"[check-openbabel] AUTOTEST FALLIDO: el detector de PATH marca de "
                f"más en `{muestra.strip()[:60]}`."
            )
    hallazgos, error = analizar_imports("def roto(:\n")
    if hallazgos or not error:
        raise SystemExit(
            "[check-openbabel] AUTOTEST FALLIDO: un archivo que no parsea tiene que "
            "devolver un error, no «limpio»."
        )
    autotest_recorrido()


def autotest_recorrido() -> None:
    """El recorrido de árbol, ejecutado sobre un árbol fabricado.

    Los detectores de arriba prueban que se ve un `import`; esto prueba que el
    RECORRIDO llega a donde debe: `tests/`, `scripts/` y `data/` (los directorios
    que el filtro anterior se saltaba), que un archivo ilegible no se da por
    limpio, que una excepción declarada se admite y se lista, y que el ruido de
    máquina (`__pycache__`) no cuenta. Aborta si algo de eso falla.
    """
    importa = "from openbabel import openbabel\n"
    muestras = {
        "backend/services/sano.py": "import os\n",
        "backend/tests/test_roto.py": importa,
        "rescoring/scripts/roto.py": importa,
        "rescoring/data/roto.py": importa,
        "rescoring/artifacts/roto.py": importa,
        "backend/services/ilegible.py": "def roto(:\n",
        "rescoring/scripts/declarado.py": importa,
        "backend/__pycache__/ruido.py": importa,
    }
    esperados = {
        "backend/tests/test_roto.py", "rescoring/scripts/roto.py",
        "rescoring/data/roto.py", "rescoring/artifacts/roto.py",
        "rescoring/scripts/declarado.py",
    }

    def fallo(mensaje: str) -> None:
        raise SystemExit(f"[check-openbabel] AUTOTEST FALLIDO (recorrido): {mensaje}")

    with tempfile.TemporaryDirectory(prefix="ob-recorrido-") as tmp:
        base = Path(tmp)
        for relativa, fuente in muestras.items():
            destino = base / relativa
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(fuente, encoding="utf-8")

        encontrados, ilegibles = imports_prohibidos_en(base)
        if set(encontrados) != esperados:
            fallo(
                f"el recorrido vio {sorted(encontrados)} y debía ver {sorted(esperados)}: "
                "un directorio se está saltando o el ruido cuenta como código"
            )
        if [ruta for ruta, _ in ilegibles] != ["backend/services/ilegible.py"]:
            fallo(f"un archivo ilegible no quedó declarado: {ilegibles}")

        resultado = Resultado()
        g1_g3_codigo(
            base, "autotest", resultado,
            excepciones={"rescoring/scripts/declarado.py": "excepción de muestra"},
        )
        mensaje = "\n".join(resultado.fallos)
        if resultado.ok:
            fallo("G1 aprobó un árbol con imports prohibidos")
        for ruta in esperados - {"rescoring/scripts/declarado.py"}:
            if ruta not in mensaje:
                fallo(f"G1 no nombró {ruta}")
        if "ilegible.py" not in mensaje:
            fallo("G1 no declaró el archivo que no pudo analizar")
        if "declarado.py" in mensaje:
            fallo("G1 marcó una excepción declarada")
        if not any("declarado.py" in v for v in resultado.verificado):
            fallo("G1 no listó la excepción declarada: una excepción callada es una puerta oculta")

        for relativa in muestras:
            if relativa != "backend/services/sano.py":
                (base / relativa).unlink()
        sano = Resultado()
        g1_g3_codigo(base, "autotest", sano, excepciones={})
        if not sano.ok:
            fallo(f"G1 marcó un árbol limpio: {sano.fallos}")


# ── Recorrido ────────────────────────────────────────────────────────────


def _archivos_python(base: Path) -> list[Path]:
    """TODO `.py` de los dos árboles, sin más filtro que el ruido de máquina."""
    salida: list[Path] = []
    for arbol in ARBOLES_DE_PRODUCCION:
        raiz = base / arbol
        if not raiz.is_dir():
            continue
        for archivo in raiz.rglob("*.py"):
            if DIRECTORIOS_IGNORADOS & set(archivo.relative_to(base).parts):
                continue
            salida.append(archivo)
    return sorted(salida)


def _archivos_de_produccion(base: Path, arboles: tuple[str, ...]) -> list[Path]:
    """Alcance de G3: código de producción (ver `NO_ES_PRODUCCION`)."""
    salida: list[Path] = []
    for arbol in arboles:
        raiz = base / arbol
        if not raiz.is_dir():
            continue
        for archivo in raiz.rglob("*.py"):
            if NO_ES_PRODUCCION & {p.lower() for p in archivo.relative_to(base).parts}:
                continue
            salida.append(archivo)
    return sorted(salida)


def _relativa(archivo: Path, base: Path) -> str:
    return archivo.relative_to(base).as_posix()


def imports_prohibidos_en(
    base: Path,
) -> tuple[dict[str, list[tuple[str, int]]], list[tuple[str, str]]]:
    """(imports por archivo, archivos ilegibles) sobre TODO el árbol, sin exenciones.

    Es la verdad de fondo: lo que el AST encuentra cuando nadie queda fuera. G1
    decide después qué admite; esta función no admite nada.
    """
    encontrados: dict[str, list[tuple[str, int]]] = {}
    ilegibles: list[tuple[str, str]] = []
    for archivo in _archivos_python(base):
        relativa = _relativa(archivo, base)
        try:
            fuente = archivo.read_bytes()
        except OSError as exc:
            ilegibles.append((relativa, f"OSError: {exc}"))
            continue
        hallazgos, error = analizar_imports(fuente)
        if error:
            ilegibles.append((relativa, error))
        elif hallazgos:
            encontrados[relativa] = hallazgos
    return encontrados, ilegibles


def g1_g3_codigo(
    base: Path,
    etiqueta: str,
    resultado: Resultado,
    *,
    excepciones: dict[str, str] | None = None,
) -> None:
    """G1 imports prohibidos (todo el árbol) · G3 resolución por PATH (producción).

    Sobre el repositorio rige `EXCEPCIONES_DEV_ONLY`. Sobre el BUNDLE no hay
    ninguna: lo que no debe distribuirse, no está, y eso incluye los scripts
    declarados de desarrollo.
    """
    archivos = _archivos_python(base)
    if not archivos:
        resultado.salta(f"[{etiqueta}] no hay árboles de producción que revisar")
        return
    if excepciones is None:
        excepciones = EXCEPCIONES_DEV_ONLY if base == RAIZ else {}

    encontrados, ilegibles = imports_prohibidos_en(base)
    violaciones: list[str] = []
    admitidas: list[str] = []
    for relativa, hallazgos in sorted(encontrados.items()):
        destino = admitidas if relativa in excepciones else violaciones
        for modulo, linea in hallazgos:
            destino.append(f"{relativa}:{linea}: import {modulo}")

    if admitidas:
        rutas = sorted({a.split(":")[0] for a in admitidas})
        resultado.bien(
            f"G1 [{etiqueta}] {len(rutas)} excepción(es) declarada(s) de desarrollo, que "
            f"no viajan (G2 y G1 sobre el bundle lo comprueban): {', '.join(rutas)}"
        )
    if ilegibles:
        resultado.mal(
            f"G1 [{etiqueta}] no se pudo analizar {len(ilegibles)} archivo(s): no se "
            "afirma que estén limpios. Un detector que calla ante lo que no entiende "
            "anuncia «limpio» sobre algo que no miró.\n  - "
            + "\n  - ".join(f"{ruta}: {error}" for ruta, error in ilegibles[:20])
        )
    if violaciones:
        resultado.mal(
            f"G1 [{etiqueta}] hay código que importa los bindings de Open Babel. Eso "
            "convertiría a MolDesign y a Open Babel en una sola obra: los bindings "
            "GPL-2.0-only no pueden redistribuirse como una sola obra con código "
            "PolyForm Noncommercial. La regla vale para TODO `backend/` y `rescoring/` "
            "(también tests, scripts y data). No se añade una excepción para que la "
            "guarda pase: es una decisión del propietario (AGENTS.md, docs/86 LUNA-01)."
            "\n  - " + "\n  - ".join(violaciones[:20])
        )
    if not (violaciones or ilegibles):
        resultado.bien(f"G1 [{etiqueta}] {len(archivos)} módulos: ningún import prohibido")

    con_path: list[str] = []
    for archivo in _archivos_de_produccion(base, ARBOLES_DE_PRODUCCION):
        relativa = _relativa(archivo, base)
        if relativa in EXENTOS or relativa in excepciones:
            continue
        try:
            fuente = archivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for hallazgo in resuelve_por_path(fuente):
            con_path.append(f"{relativa}: {hallazgo}")

    if con_path:
        resultado.mal(
            f"G3 [{etiqueta}] producción resuelve `obabel` por PATH o por nombre "
            "suelto. Un binario ajeno del equipo del usuario produciría un "
            "resultado que el informe atribuiría a la versión del manifiesto.\n  - "
            + "\n  - ".join(con_path[:20])
        )
    else:
        resultado.bien(f"G3 [{etiqueta}] ninguna resolución de `obabel` por entorno")


def _excluido_del_empaquetado(relativa: str) -> str | None:
    """Por qué `bundle_helper` NO copia este archivo, o None si viajaría."""
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        from bundle_helper import (
            RESCORING_DIRS_FUERA_DEL_RUNTIME,
            RESCORING_FUERA_DEL_RUNTIME_FILES,
        )
    except ImportError:  # pragma: no cover - sólo si se mueve el empaquetador
        return None
    partes = PurePosixPath(relativa).parts
    if not partes or partes[0] != "rescoring":
        return None  # no hay regla de exclusión conocida fuera de rescoring/
    if partes[-1] in RESCORING_FUERA_DEL_RUNTIME_FILES:
        return f"excluido por nombre ({partes[-1]})"
    directorios = {d.lower() for d in partes[1:-1]} & {
        d.lower() for d in RESCORING_DIRS_FUERA_DEL_RUNTIME
    }
    if directorios:
        return f"excluido por directorio ({sorted(directorios)[0]}/)"
    return None


def g1b_excepciones_coherentes(resultado: Resultado) -> None:
    """Cada excepción existe, lleva su motivo y `bundle_helper` la excluye.

    Una excepción que ya no existe autorizaría el próximo import que alguien
    ponga en ese camino; una que el empaquetado SÍ copia sería una puerta abierta
    al instalador; una sin motivo no tiene dueño.
    """
    problemas: list[str] = []
    for relativa, motivo in sorted(EXCEPCIONES_DEV_ONLY.items()):
        if not (RAIZ / relativa).is_file():
            problemas.append(f"{relativa}: excepción huérfana, el archivo ya no existe")
            continue
        if len(motivo.strip()) < 60:
            problemas.append(f"{relativa}: el motivo no está escrito")
        if _excluido_del_empaquetado(relativa) is None:
            problemas.append(
                f"{relativa}: `bundle_helper` NO lo excluye del instalador; una "
                "excepción de desarrollo que viaja deja de ser de desarrollo"
            )
    if problemas:
        resultado.mal(
            "G1b la lista de excepciones de desarrollo no es coherente:\n  - "
            + "\n  - ".join(problemas)
        )
    else:
        resultado.bien(
            f"G1b {len(EXCEPCIONES_DEV_ONLY)} excepciones: existen, con motivo, y "
            "`bundle_helper` las excluye del empaquetado"
        )


def g2_bindings_en_el_bundle(resultado: Resultado) -> None:
    """G2 los bindings no viajan en el `site-packages` empaquetado."""
    site = RESOURCES / "python" / "Lib" / "site-packages"
    if not site.is_dir():
        site = RESOURCES / "python" / "lib" / "site-packages"
    if not site.is_dir():
        resultado.salta("G2 no hay bundle staged: `site-packages` sin comprobar")
        return
    encontrados = [
        entrada.name
        for entrada in site.iterdir()
        if any(entrada.name.lower().startswith(h) for h in HUELLAS_DE_BINDINGS)
    ]
    # Y los módulos científicos que los importaban y viajaban por inercia.
    #
    # La lista se lee de `bundle_helper`, la MISMA que autoriza esos módulos en
    # G1 y la misma que los excluye del instalador. Con una copia escrita aquí,
    # autorizar uno nuevo sin excluirlo pasaría desapercibido en el artefacto,
    # que es justo lo que esta comprobación existe para impedir.
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        from bundle_helper import RESCORING_FUERA_DEL_RUNTIME_FILES as _fuera
    except ImportError:  # pragma: no cover - sólo si se mueve el empaquetador
        _fuera = ()
    colados = [
        _relativa(p, RESOURCES)
        for p in (RESOURCES / "rescoring").rglob("*.py")
        if p.name in _fuera
    ]
    # Y TODA excepción declarada de G1, no sólo las dos que el empaquetado excluye
    # por nombre: las otras dos cuelgan de `rescoring/scripts`, que se excluye por
    # directorio. Si alguna aparece aquí, la declaración «no viaja» era falsa.
    colados += [r for r in sorted(EXCEPCIONES_DEV_ONLY) if (RESOURCES / r).exists()]
    colados = sorted(set(colados))
    lanzadores = [
        _relativa(p, RESOURCES)
        for p in (RESOURCES / "python").rglob("obabel*")
        if (RESOURCES / "python").is_dir() and p.is_file()
    ]
    problemas = (
        [f"python/Lib/site-packages/{n}" for n in encontrados] + colados + lanzadores
    )
    if problemas:
        resultado.mal(
            "G2 los bindings de Open Babel viajan dentro del entorno Python del "
            "runtime. En esa instalación `from openbabel import openbabel` "
            "funcionaría, y la frontera dejaría de ser cierta:\n  - "
            + "\n  - ".join(sorted(problemas)[:20])
        )
    else:
        resultado.bien(
            "G2 el `site-packages` empaquetado no contiene los bindings de Open Babel"
        )


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def g4_g7_herramienta(
    base: Path, etiqueta: str, resultado: Resultado, *, exigir: bool
) -> None:
    """G4 presente · G5 hash · G6 versión · G7 conversión real."""
    herramienta = base / "tools" / "openbabel"
    manifiesto_path = herramienta / "openbabel-manifest.json"
    if not manifiesto_path.is_file():
        mensaje = (
            f"G4 [{etiqueta}] falta `tools/openbabel/openbabel-manifest.json`. "
            "Open Babel viaja en el instalador: su ausencia es una instalación "
            "incompleta. Ejecuta `python scripts/stage_openbabel_tool.py`."
        )
        (resultado.mal if exigir else resultado.salta)(mensaje)
        return
    manifiesto = json.loads(manifiesto_path.read_text(encoding="utf-8"))

    relativa_exe = manifiesto.get("ejecutable", "bin/obabel.exe")
    exe = herramienta / relativa_exe
    if not exe.is_file():
        (resultado.mal if exigir else resultado.salta)(
            f"G4 [{etiqueta}] falta el ejecutable empaquetado: tools/openbabel/{relativa_exe}"
        )
        return
    resultado.bien(f"G4 [{etiqueta}] ejecutable presente en tools/openbabel/{relativa_exe}")

    if relativa_exe not in manifiesto.get("archivos", {}):
        resultado.mal(f"G5 [{etiqueta}] el ejecutable no tiene hash en el manifiesto")
        return

    # G5: TODOS los archivos declarados, no sólo el ejecutable. Un plugin
    # alterado cambia lo que el programa hace sin tocar el .exe.
    desviados: list[str] = []
    for relativa, esperado in manifiesto.get("archivos", {}).items():
        ruta = herramienta / relativa
        if not ruta.is_file():
            desviados.append(f"ausente: {relativa}")
        elif _sha256(ruta) != esperado["sha256"]:
            desviados.append(f"hash distinto: {relativa}")
    if desviados:
        resultado.mal(
            f"G5 [{etiqueta}] el árbol de Open Babel no coincide con su manifiesto:\n  - "
            + "\n  - ".join(desviados[:20])
        )
        return
    resultado.bien(
        f"G5 [{etiqueta}] {len(manifiesto['archivos'])} archivos coinciden con el manifiesto"
    )

    # G6: la versión que contesta el binario.
    esperada = manifiesto.get("version_reportada_por_el_binario")
    try:
        proceso = subprocess.run(
            [str(exe), "-V"], capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        resultado.mal(f"G6 [{etiqueta}] el ejecutable no arranca: {exc}")
        return
    reportada = ((proceso.stdout or "") + (proceso.stderr or "")).strip()
    if proceso.returncode != 0 or (esperada and esperada not in reportada):
        resultado.mal(
            f"G6 [{etiqueta}] `obabel -V` contestó {reportada!r} (código "
            f"{proceso.returncode}), y el manifiesto declara {esperada!r}."
        )
        return
    resultado.bien(f"G6 [{etiqueta}] `obabel -V` → {reportada}")

    # G7: una conversión de verdad. Copiar archivos no es empaquetar.
    muestra = "\n".join(
        [
            "ROOT",
            "ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00     0.000 C ",
            "ATOM      2  C   UNL     1       1.520   0.000   0.000  1.00  0.00     0.000 C ",
            "ATOM      3  O   UNL     1       2.100   1.080   0.000  1.00  0.00    -0.270 OA",
            "ENDROOT",
            "TORSDOF 0",
            "",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="ob-gate-") as tmp:
        entrada = Path(tmp) / "in.pdbqt"
        salida = Path(tmp) / "out.sdf"
        entrada.write_text(muestra, encoding="utf-8")
        conv = subprocess.run(
            [str(exe), "-ipdbqt", str(entrada), "-osdf", "-O", str(salida)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60,
        )
        texto = salida.read_text(encoding="utf-8", errors="replace") if salida.is_file() else ""
    if conv.returncode != 0 or "$$$$" not in texto or "V2000" not in texto:
        resultado.mal(
            f"G7 [{etiqueta}] la conversión PDBQT→SDF no produjo un SDF utilizable "
            f"(código {conv.returncode}). stderr: {conv.stderr[-300:]}"
        )
        return
    atomos = next((int(l[:3]) for l in texto.splitlines() if "V2000" in l), 0)
    if atomos != 3:
        resultado.mal(
            f"G7 [{etiqueta}] la conversión devolvió {atomos} átomos y entraron 3."
        )
        return
    resultado.bien(f"G7 [{etiqueta}] conversión PDBQT→SDF real: 3 átomos, SDF válido")


def g8_contrato_de_persistencia(resultado: Resultado) -> None:
    """G8 el docking no reconstruye química desde PDBQT."""
    fuente_path = RAIZ / "backend" / "services" / "docking" / "vina_service.py"
    if not fuente_path.is_file():
        resultado.salta("G8 no está `vina_service.py`")
        return
    codigo = _sin_comentarios(fuente_path.read_text(encoding="utf-8"))
    faltan: list[str] = []
    if "convertir_pdbqt_a_sdf(" in codigo or 'parsing_source = "sdf_openbabel_cli"' in codigo:
        faltan.append("la conversión PDBQT→SDF sigue en la ruta de producción")
    if not re.search(
        r"if not poses:\s*raise DockingFailed\(",
        codigo,
    ):
        faltan.append("falta la abstención cuando Meeko no exporta poses SDF")
    if "No se reconstruye la molécula desde el PDBQT de Vina." not in codigo:
        faltan.append("la abstención no declara el motivo químico")
    if not re.search(r"await write_file\(output_sdf, poses_path\)", codigo):
        faltan.append("no se entrega el SDF verificado de Meeko")
    if faltan:
        resultado.mal("G8 contrato de abstención roto:\n  - " + "\n  - ".join(faltan))
    else:
        resultado.bien("G8 sin conversión PDBQT→SDF en docking; SDF de Meeko o abstención")


def g9_licencia_declarada(resultado: Resultado) -> None:
    """G9 nadie vuelve a llamarlo `GPL-2.0-or-later`."""
    objetivos = [
        RAIZ / "frontend" / "lib" / "softwareCatalog.ts",
        RAIZ / "frontend" / "public" / "legal" / "THIRD_PARTY_NOTICES.md",
        RAIZ / "docs" / "api" / "sbom.json",
        RESOURCES / "licenses" / "THIRD_PARTY_NOTICES.md",
        RESOURCES / "runtime-manifest.json",
    ]
    culpables: list[str] = []
    revisados = 0
    for objetivo in objetivos:
        if not objetivo.is_file():
            continue
        revisados += 1
        try:
            nombre = objetivo.relative_to(RAIZ).as_posix()
        except ValueError:
            nombre = objetivo.name
        texto = objetivo.read_text(encoding="utf-8", errors="replace")
        # Se mira LÍNEA A LÍNEA y se exige que la mención de Open Babel y la
        # licencia equivocada estén en la misma: hay otros componentes
        # legítimamente `-or-later` (Meeko LGPL-2.1, xTB LGPL-3.0) y marcarlos
        # convertiría esta guarda en ruido que alguien acabaría desactivando.
        #
        # En TypeScript se ignoran los comentarios `//`: el propio catálogo
        # EXPLICA por qué la forma `-or-later` era falsa, y una guarda que lee
        # la explicación como si fuera la declaración castiga documentar.
        es_ts = objetivo.suffix in (".ts", ".tsx", ".js", ".mjs")
        for linea_num, linea in enumerate(texto.splitlines(), 1):
            efectiva = re.sub(r"//.*$", "", linea) if es_ts else linea
            if not LICENCIA_INCORRECTA.search(efectiva):
                continue
            if "babel" not in efectiva.lower():
                continue
            culpables.append(f"{nombre}:{linea_num}: {linea.strip()[:110]}")

    # Y la afirmación positiva: donde se nombra, debe decir GPL-2.0-only.
    # Que nadie escriba lo incorrecto no basta —borrar la línea también lo
    # cumpliría—; tiene que estar escrito lo correcto.
    catalogo = RAIZ / "frontend" / "lib" / "softwareCatalog.ts"
    if catalogo.is_file() and 'license: "GPL-2.0-only"' not in catalogo.read_text(
        encoding="utf-8"
    ):
        culpables.append(
            "frontend/lib/softwareCatalog.ts: Open Babel ya no se declara GPL-2.0-only"
        )
    avisos = RAIZ / "frontend" / "public" / "legal" / "THIRD_PARTY_NOTICES.md"
    if avisos.is_file() and "GPL-2.0-only" not in avisos.read_text(encoding="utf-8"):
        culpables.append(
            "frontend/public/legal/THIRD_PARTY_NOTICES.md: falta la declaración "
            "GPL-2.0-only de Open Babel"
        )
    if culpables:
        resultado.mal(
            "G9 Open Babel vuelve a declararse como `GPL-2.0-or-later`. Open Babel "
            "dice «GNU General Public License, versión 2», sin «o posterior»: ese "
            "«or-later» concede un permiso que sus autores no dieron y borra del "
            "informe la incompatibilidad con la familia GPL-3.\n  - "
            + "\n  - ".join(culpables[:20])
        )
    else:
        resultado.bien(
            f"G9 {revisados} documentos de licencia: Open Babel declarado GPL-2.0-only"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        action="store_true",
        help="comprueba también `frontend/src-tauri/resources`, que es lo que se entrega",
    )
    parser.add_argument(
        "--exigir-binario",
        action="store_true",
        help=(
            "la ausencia de `tools/openbabel/bin/` es un fallo, no un salto. Lo "
            "usa el build; un clon limpio no trae binarios."
        ),
    )
    args = parser.parse_args()

    autotest()
    resultado = Resultado()

    g1_g3_codigo(RAIZ, "repositorio", resultado)
    g1b_excepciones_coherentes(resultado)
    g4_g7_herramienta(RAIZ, "repositorio", resultado, exigir=args.exigir_binario)
    g8_contrato_de_persistencia(resultado)
    g9_licencia_declarada(resultado)

    if args.bundle:
        if not RESOURCES.is_dir():
            resultado.mal(
                "Se pidió --bundle y no existe `frontend/src-tauri/resources`. "
                "Ejecuta `npm run stage:desktop` primero."
            )
        else:
            g1_g3_codigo(RESOURCES, "bundle", resultado)
            g2_bindings_en_el_bundle(resultado)
            g4_g7_herramienta(RESOURCES, "bundle", resultado, exigir=True)
    else:
        g2_bindings_en_el_bundle(resultado)

    for linea in resultado.verificado:
        print(f"[check-openbabel] OK   {linea}")
    for linea in resultado.saltado:
        print(f"[check-openbabel] SALTA {linea}")
    for linea in resultado.fallos:
        print(f"[check-openbabel] ERROR {linea}", file=sys.stderr)

    if not resultado.ok:
        print(
            "\nLa frontera con Open Babel está rota. Contexto y reglas en "
            "`docs/79_ADR_FRONTERA_OPEN_BABEL.md`.",
            file=sys.stderr,
        )
        return 1
    if resultado.saltado:
        print(
            f"\n[check-openbabel] {len(resultado.verificado)} comprobaciones pasadas, "
            f"{len(resultado.saltado)} SIN comprobar. Saltar no es aprobar."
        )
    else:
        print(
            f"\n[check-openbabel] frontera intacta: "
            f"{len(resultado.verificado)} comprobaciones."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
