#!/usr/bin/env python3
r"""Guarda de la frontera con Open Babel. Bloquea el build si se rompe.

# Qué vigila

Open Babel es un **programa independiente GPL-2.0-only** que MolDesign
distribuye en el mismo instalador y ejecuta como herramienta de línea de
órdenes. Esa frontera no se sostiene sola: basta un `from openbabel import
openbabel` en el módulo equivocado, o un `shutil.which("obabel")` bien
intencionado, para que deje de ser cierta sin que nada lo diga.

Las nueve comprobaciones, en el orden en que aparecen:

    G1  el código de producción no importa `openbabel`, `pybel` ni `_openbabel`
    G2  esos bindings no están en el `site-packages` del backend empaquetado
    G3  producción no resuelve `obabel` por PATH
    G4  el ejecutable empaquetado está donde dice el manifiesto
    G5  su hash coincide con el manifiesto
    G6  `obabel -V` devuelve la versión declarada
    G7  una conversión PDBQT→SDF real funciona sobre el árbol comprobado
    G8  el SDF convertido es el que se persiste (contrato de `vina_service`)
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
from pathlib import Path

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

# ── Qué cuenta como «código de producción» ───────────────────────────────
#
# Lo que viaja en el instalador y se ejecuta en el equipo del investigador. Los
# scripts científicos y los generadores de datasets NO están aquí: pueden usar
# los bindings legítimamente porque son dependencias de desarrollo y no se
# distribuyen. Lo que la guarda exige es que no se distribuyan (G2).
ARBOLES_DE_PRODUCCION = ("backend", "rescoring")

#: Módulos que sí pueden nombrar Open Babel: el adaptador y su paquete.
EXENTOS = (
    "backend/services/external_tools/open_babel.py",
    "backend/services/external_tools/__init__.py",
)


def _dev_only_declarados() -> set[str]:
    r"""Módulos científicos que usan los bindings y NO se distribuyen.

    La lista no se escribe aquí: se lee de `bundle_helper.py`, que es quien de
    verdad los excluye del instalador. Dos copias de la misma decisión se
    separan, y la que se quedara vieja sería justo ésta —la que autoriza—.

    Y la autorización no se cree a ciegas: G2 comprueba sobre el bundle REAL
    que ninguno de estos archivos viaja. Si alguien añade uno aquí sin
    excluirlo allí, la guarda lo caza en el artefacto.
    """
    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        from bundle_helper import RESCORING_FUERA_DEL_RUNTIME_FILES
    except ImportError:  # pragma: no cover - sólo si se mueve el empaquetador
        return set()
    permitidos: set[str] = set()
    for arbol in ARBOLES_DE_PRODUCCION:
        raiz = RAIZ / arbol
        if not raiz.is_dir():
            continue
        for nombre in RESCORING_FUERA_DEL_RUNTIME_FILES:
            for encontrado in raiz.rglob(nombre):
                permitidos.add(encontrado.relative_to(RAIZ).as_posix())
    return permitidos

#: Directorios que no son producción aunque cuelguen de un árbol que sí lo es.
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


def importa_prohibido(fuente: str) -> list[str]:
    """Módulos prohibidos que este archivo IMPORTA de verdad.

    Se analiza el AST y no el texto: un comentario que explique la prohibición
    no es una violación, y una guarda que no sepa distinguirlos convertiría
    cada explicación en un falso positivo — y acabaría desactivada.
    """
    try:
        arbol = ast.parse(fuente)
    except SyntaxError:
        return []
    encontrados: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                raiz = alias.name.split(".")[0]
                if raiz in MODULOS_PROHIBIDOS:
                    encontrados.append(alias.name)
        elif isinstance(nodo, ast.ImportFrom):
            raiz = (nodo.module or "").split(".")[0]
            if raiz in MODULOS_PROHIBIDOS:
                encontrados.append(nodo.module or "")
            elif nodo.module is None:
                continue
            # `from openbabel import openbabel` cae en la rama anterior;
            # `from x import openbabel` sólo importa un nombre, no el paquete.
    return sorted(set(encontrados))


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
)
_NO_DEBE_VER_IMPORT = (
    "# from openbabel import openbabel  <- prohibido, ver el ADR\n",
    '"""Se prohíbe `import pybel` en producción."""\n',
    "from services.external_tools import open_babel\n",
    "texto = 'openbabel'\n",
    "from rdkit import Chem\n",
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


# ── Recorrido ────────────────────────────────────────────────────────────


def _archivos_de_produccion(base: Path, arboles: tuple[str, ...]) -> list[Path]:
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


def g1_g3_codigo(base: Path, etiqueta: str, resultado: Resultado) -> None:
    """G1 imports prohibidos · G3 resolución por PATH."""
    archivos = _archivos_de_produccion(base, ARBOLES_DE_PRODUCCION)
    if not archivos:
        resultado.salta(f"[{etiqueta}] no hay árboles de producción que revisar")
        return
    # En el BUNDLE no hay excepciones: lo que no debe distribuirse, no está.
    # En el repositorio se permiten los módulos declarados como dependencia de
    # desarrollo, porque el árbol de trabajo no es lo que se entrega.
    dev_only = _dev_only_declarados() if base == RAIZ else set()
    con_import: list[str] = []
    con_path: list[str] = []
    for archivo in archivos:
        relativa = _relativa(archivo, base)
        if relativa in EXENTOS or relativa in dev_only:
            continue
        try:
            fuente = archivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for modulo in importa_prohibido(fuente):
            con_import.append(f"{relativa}: import {modulo}")
        for hallazgo in resuelve_por_path(fuente):
            con_path.append(f"{relativa}: {hallazgo}")

    if dev_only:
        resultado.bien(
            f"G1 [{etiqueta}] {len(dev_only)} módulo(s) declarados dependencia de "
            "desarrollo (y G2 comprueba que no viajan): "
            + ", ".join(sorted(dev_only))
        )
    if con_import:
        resultado.mal(
            f"G1 [{etiqueta}] el código de producción importa los bindings de Open "
            "Babel. Eso convierte a MolDesign y a Open Babel en una sola obra y "
            "mezclaría bindings GPL-2.0-only con código PolyForm Noncommercial, que no puede redistribuirse como una sola obra, y "
            "incompatibles.\n  - " + "\n  - ".join(con_import[:20])
        )
    else:
        resultado.bien(f"G1 [{etiqueta}] {len(archivos)} módulos: ningún import prohibido")

    if con_path:
        resultado.mal(
            f"G3 [{etiqueta}] producción resuelve `obabel` por PATH o por nombre "
            "suelto. Un binario ajeno del equipo del usuario produciría un "
            "resultado que el informe atribuiría a la versión del manifiesto.\n  - "
            + "\n  - ".join(con_path[:20])
        )
    else:
        resultado.bien(f"G3 [{etiqueta}] ninguna resolución de `obabel` por entorno")


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
    """G8 el SDF convertido es el que se persiste."""
    fuente_path = RAIZ / "backend" / "services" / "docking" / "vina_service.py"
    if not fuente_path.is_file():
        resultado.salta("G8 no está `vina_service.py`")
        return
    codigo = _sin_comentarios(fuente_path.read_text(encoding="utf-8"))
    faltan: list[str] = []
    if not re.search(
        r"if sdf_a_persistir is not None:\s*await write_text\(poses_path, sdf_a_persistir\)"
        r"\s*else:\s*await write_file\(output_sdf, poses_path\)",
        codigo,
    ):
        faltan.append(
            "la persistencia del SDF de poses no está condicionada a de dónde "
            "salieron las poses"
        )
    if 'parsing_source == "sdf_openbabel_cli") != (sdf_a_persistir is not None)' not in codigo:
        faltan.append(
            "falta la comprobación de coherencia entre la procedencia declarada "
            "y el archivo que se entrega"
        )
    if 'parsing_source = "openbabel"' in codigo:
        faltan.append(
            'vuelve la procedencia inválida `"openbabel"`, que revienta '
            "DockingResult justo cuando el respaldo funciona"
        )
    modelos = (RAIZ / "backend" / "core" / "models.py").read_text(encoding="utf-8")
    if "sdf_openbabel_cli" not in modelos:
        faltan.append("`DockingResult.parsing_source` ya no admite `sdf_openbabel_cli`")
    if faltan:
        resultado.mal(
            "G8 el contrato de persistencia del respaldo está roto:\n  - "
            + "\n  - ".join(faltan)
        )
    else:
        resultado.bien("G8 el SDF entregado es aquel del que salieron las poses")


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
