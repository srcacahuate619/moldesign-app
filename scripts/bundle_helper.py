"""Prepara el runtime autocontenido del instalador de escritorio.

Este script no crea el instalador. Construye exclusivamente
frontend/src-tauri/resources con una lista permitida de componentes. Tauri lo
copia después a la raíz de recursos instalada.

Decisiones de producto:
- el flujo crítico incluye Python científico, backend, rescoring, Vina, xTB,
  Open Babel y la colección curada de estructuras;
- los pesos de LLM, CUDA, ESMFold y datasets de entrenamiento se descargan o
  configuran aparte: no son requisito para crear/evaluar un caso;
- nunca se empaquetan .env, bases de usuario, logs ni modelos invalidados.

Frontera con Open Babel (ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`):
Open Babel viaja en el instalador como **programa independiente GPL-2.0-only**,
en `tools/openbabel/`, y **no** dentro del entorno Python importable. Este
script excluye a propósito sus bindings (`openbabel/`, `pybel`,
`_openbabel.pyd`) del `site-packages` del runtime, y excluye también los dos
módulos científicos que los importaban y que nunca fueron runtime.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vc_runtime_source import validated_vc_runtime_dir


IgnoreFunction = Callable[[str, list[str]], set[str]]

COMMON_DIRS = {
    "__pycache__",
    # Basura de pruebas: un mock sin configurar interpolado en una ruta crea un
    # arbol `MagicMock/...`. Estaba ni ignorado por git ni excluido aqui, asi
    # que habria viajado al instalador.
    "MagicMock",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "node_modules",
    # Artefactos de auditoría de diseño: evidencia de una revisión, no producto.
    ".hallmark",
}
# ── La frontera con Open Babel, hecha de exclusiones ─────────────────────
#
# Open Babel es un programa independiente GPL-2.0-only. MolDesign lo invoca por
# subproceso, nunca lo importa. Para que eso no dependa de la disciplina de
# quien escriba el próximo módulo, los bindings SE QUITAN del runtime: aunque
# alguien escribiera `from openbabel import openbabel`, en la aplicación
# instalada no habría nada que importar.
#
# Lo que se retira del `site-packages` empaquetado:
OPENBABEL_BINDINGS_DIRS = {
    "openbabel",                       # el paquete Python del wheel
    "openbabel_wheel.libs",            # sus DLLs privadas
}
OPENBABEL_BINDINGS_FILES = (
    "openbabel_wheel-*.dist-info",     # metadatos de la distribución
    "_openbabel*.pyd",
    "pybel.py",
    "obabel.exe",                      # el lanzador de pip en python/Scripts
    "obabel-script.py",
)

#: Módulos científicos que importaban esos bindings y que NUNCA fueron runtime:
#: `generate_gpu_dataset.py` genera datasets de entrenamiento y
#: `RTMScore/feats/extract_pocket_prody.py` es un ayudante de preparación de
#: bolsillos que ningún módulo del producto importa —`gnn_service` usa
#: `RTMScore.feats.mol2graph_pyg` y `RTMScore.model.*`, y nada más—.
#: Viajaban en el instalador por inercia. Ahora son dependencias de desarrollo.
#
# `RTMScore/data/data.py` también importa `extract_pocket_prody`, pero ya
# quedaba fuera: el filtro por nombre `data` del copiado de rescoring lo excluye
# en cualquier nivel del árbol. Se comprueba, no se supone —lo verifica
# `check_openbabel_boundary.py` sobre el bundle real, no sobre esta lista—.
RESCORING_FUERA_DEL_RUNTIME_FILES = (
    "generate_gpu_dataset.py",
    "extract_pocket_prody.py",
)

COMMON_FILE_PATTERNS = (
    "*.pyc", "*.pyo", "*.log", "*.err", "*.out", "*.tmp",
    # Restos de recuperación y respaldo. En este árbol aparecieron routers
    # `.damaged` de OTRO producto (LegalDesk) y `.bak_*` de bases anteriores;
    # ninguno tiene por qué viajar al instalador, y el coste de excluirlos es
    # cero comparado con el de descubrir que se distribuyeron.
    "*.damaged", "*.bak", "*.bak_*", "*.orig", "*.rej", "trace",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Raíz del repositorio MolDesign.",
    )
    return parser.parse_args()


def matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns)


def ignore_factory(
    *,
    extra_dirs: set[str] | None = None,
    extra_files: tuple[str, ...] = (),
) -> IgnoreFunction:
    blocked_dirs = {item.lower() for item in COMMON_DIRS | (extra_dirs or set())}
    file_patterns = COMMON_FILE_PATTERNS + extra_files

    def ignore(_directory: str, names: list[str]) -> set[str]:
        ignored: set[str] = set()
        for name in names:
            if name.lower() in blocked_dirs or matches_any(name, file_patterns):
                ignored.add(name)
        return ignored

    return ignore


def archivos_bloqueados(raiz: Path, *, limite: int = 4000) -> list[str]:
    """
    Qué archivos no se pueden reemplazar porque otro proceso los tiene abiertos.

    En Windows un `.dll` cargado por un proceso vivo no se puede borrar ni
    renombrar. `shutil.rmtree` lo descubre a mitad del recorrido, cuando ya ha
    borrado media jerarquia: el staging queda destruido y el error no dice como
    repararlo. Se comprueba antes, y se aborta sin tocar nada.

    Se prueba con un rename sobre si mismo, que es la operacion que el sistema
    deniega cuando hay un handle abierto y que no modifica el archivo.
    """
    bloqueados: list[str] = []
    revisados = 0
    for archivo in raiz.rglob("*"):
        if not archivo.is_file():
            continue
        revisados += 1
        if revisados > limite and not bloqueados:
            # Los binarios cargables (.dll/.exe/.pyd) son los unicos que en la
            # practica quedan retenidos; el resto se revisa por muestreo para
            # no recorrer 30.000 archivos en cada build.
            if archivo.suffix.lower() not in {".dll", ".exe", ".pyd", ".so"}:
                continue
        try:
            archivo.rename(archivo)
        except OSError:
            bloqueados.append(str(archivo.relative_to(raiz)))
    return bloqueados


def copy_tree(source: Path, destination: Path, *, ignore: IgnoreFunction) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Directorio requerido ausente: {source}")
    shutil.copytree(source, destination, ignore=ignore)


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Archivo requerido ausente: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def git_tracked_files(root: Path, source: Path) -> list[Path]:
    """Devuelve los archivos de ``source`` que pertenecen al commit.

    Los pesos descargados, checkpoints de entrenamiento y copias de respaldo
    pueden existir en ``rescoring/`` sin estar versionados. Copiar el árbol
    físico haría que el instalador dependiera de la máquina que lo construye.
    Para un componente científico, Git es la lista permitida reproducible.
    """
    try:
        relative_source = source.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RuntimeError(f"Fuente fuera del repositorio: {source}") from exc

    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", relative_source.as_posix()],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            "No se pudo obtener el inventario Git de rescoring; se rechaza "
            f"crear un bundle no reproducible: {detail or 'git ls-files falló'}"
        )

    tracked: list[Path] = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        repository_relative = Path(raw.decode("utf-8", errors="strict"))
        candidate = root / repository_relative
        if candidate.is_file():
            tracked.append(candidate)
    if not tracked:
        raise RuntimeError(f"Git no declara ningún archivo bajo {relative_source.as_posix()}")
    return tracked


def copy_git_tracked_tree(
    root: Path,
    source: Path,
    destination: Path,
    *,
    extra_dirs: set[str] | None = None,
    extra_files: tuple[str, ...] = (),
) -> int:
    """Copia la intersección entre la lista permitida y el árbol versionado."""
    if not source.is_dir():
        raise FileNotFoundError(f"Directorio requerido ausente: {source}")

    blocked_dirs = {item.lower() for item in COMMON_DIRS | (extra_dirs or set())}
    file_patterns = COMMON_FILE_PATTERNS + extra_files
    copied = 0
    for tracked in git_tracked_files(root, source):
        relative = tracked.relative_to(source)
        if any(part.lower() in blocked_dirs for part in relative.parts[:-1]):
            continue
        if matches_any(relative.name, file_patterns):
            continue
        copy_file(tracked, destination / relative)
        copied += 1
    if copied == 0:
        raise RuntimeError(f"La lista permitida dejó vacío el componente {source}")
    return copied


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_stats(path: Path) -> dict[str, int | float]:
    files = [item for item in path.rglob("*") if item.is_file()]
    size = sum(item.stat().st_size for item in files)
    return {"files": len(files), "bytes": size, "mib": round(size / (1024 * 1024), 1)}


def ensure_managed_destination(root: Path, resources: Path) -> None:
    expected = (root / "frontend" / "src-tauri" / "resources").resolve()
    if resources.resolve() != expected:
        raise RuntimeError(f"Destino no administrado; se rechaza limpiar: {resources}")
    if root.resolve() == resources.resolve():
        raise RuntimeError(f"Destino de recursos inseguro: {resources}")


def validate_legal_release(root: Path) -> None:
    """Impide que el instalador distribuya snapshots sin permiso explícito."""
    rtmscore = root / "rescoring" / "RTMScore"
    if rtmscore.is_dir() and not any((rtmscore / name).is_file() for name in ("LICENSE", "LICENSE.txt", "COPYING")):
        raise RuntimeError(
            "BLOQUEO LEGAL: rescoring/RTMScore no declara una licencia de redistribución. "
            "Obtén permiso, incorpora la licencia o elimina esta implementación del producto. "
            "Consulta frontend/public/legal/RELEASE_BLOCKERS.md."
        )

def _programas_externos(root: Path, resources: Path) -> list[dict]:
    """Terceros que se ejecutan como proceso, con su licencia y su procedencia.

    Se lee del manifiesto que `stage_openbabel_tool.py` dejó junto al programa,
    no de una lista escrita aquí: una segunda copia de la versión y la licencia
    es una segunda copia que se puede quedar vieja.
    """
    entradas: list[dict] = []
    manifiesto_ob = resources / "tools" / "openbabel" / "openbabel-manifest.json"
    if manifiesto_ob.is_file():
        datos = json.loads(manifiesto_ob.read_text(encoding="utf-8"))
        entradas.append(
            {
                "nombre": datos["programa"],
                "version": datos["version_paquete"],
                "licencia_spdx": datos["licencia_spdx"],
                "invocacion": "subproceso CLI",
                "ejecutable": f"tools/openbabel/{datos['ejecutable']}",
                "sha256": datos["archivos"][datos["ejecutable"]]["sha256"],
                "texto_de_licencia": f"tools/openbabel/{datos['licencia_texto']}",
                "procedencia": datos["procedencia"],
                "sin_garantia": datos["sin_garantia"],
                "no_se_enlaza": (
                    "MolDesign no importa sus bindings de Python ni carga sus "
                    "bibliotecas; se comunica por archivos y códigos de salida."
                ),
            }
        )
    vina = resources / "tools" / "vina" / "vina.exe"
    if vina.is_file():
        entradas.append(
            {
                "nombre": "AutoDock Vina",
                "version": "1.2.7",
                "licencia_spdx": "Apache-2.0",
                "invocacion": "subproceso CLI",
                "ejecutable": "tools/vina/vina.exe",
                "sha256": sha256(vina),
            }
        )
    return entradas


def build_bundle(root: Path) -> Path:
    root = root.resolve()
    validate_legal_release(root)
    resources = root / "frontend" / "src-tauri" / "resources"
    ensure_managed_destination(root, resources)

    required = [
        root / "python-embed" / "python.exe",
        root / "backend" / "api" / "main.py",
        root / "rescoring" / "artifacts" / "model-manifest.json",
        root / "tools" / "vina" / "vina.exe",
        root / "curated_targets.json",
        root / "curated_targets.csv",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("No se puede preparar el runtime; faltan:\n- " + "\n- ".join(missing))

    if resources.exists():
        bloqueados = archivos_bloqueados(resources)
        if bloqueados:
            raise PermissionError(
                "No se puede reemplazar el runtime staged: hay archivos abiertos por otro "
                "proceso.\n- "
                + "\n- ".join(bloqueados[:10])
                + "\n\nCierra el proceso que los usa (tipicamente `llama-server.exe`, el "
                "servidor LLM local, o un backend en marcha) y repite.\n"
                "Se aborta ANTES de borrar nada: un `rmtree` a medias deja el runtime "
                "destruido y sin forma de repararlo en sitio."
            )
        shutil.rmtree(resources)
    resources.mkdir(parents=True)

    print("[1/7] Python científico (sin los bindings de Open Babel)")
    # El wheel `openbabel-wheel` sigue instalado en `python-embed` porque es la
    # FUENTE de la que `stage_openbabel_tool.py` saca el binario. Lo que no
    # puede es viajar: el runtime de producción no debe poder ejecutar
    # `from openbabel import openbabel`.
    copy_tree(
        root / "python-embed",
        resources / "python",
        ignore=ignore_factory(
            extra_dirs={"test", "tests"} | OPENBABEL_BINDINGS_DIRS,
            extra_files=OPENBABEL_BINDINGS_FILES,
        ),
    )

    print("[2/7] Backend sin secretos ni estado local")
    copy_tree(
        root / "backend",
        resources / "backend",
        ignore=ignore_factory(
            extra_dirs={"tests", "logs", "crash_dumps"},
            extra_files=(
                ".env",
                ".env.*",
                "*.db",
                "*.db-*",
                "*.sqlite",
                "*.sqlite3",
                "provider_config.json",
                "test_*.py",
                "*_test.py",
            ),
        ),
    )

    # `compute_quantum_features.py` vive en <repo>/scripts pero se importa como
    # modulo de PRIMER NIVEL: `from compute_quantum_features import ...` en
    # services/chemistry/molchamb_v2.py y services/docking/queue_handler.py.
    #
    # EL FALLO QUE ARREGLA. El instalador empaqueta `backend/`, no `scripts/`.
    # En el arbol de desarrollo la raiz del repositorio esta en `sys.path` y el
    # import resuelve; en la aplicacion instalada no, y el backend registraba
    #
    #     quantum_features_failed_skipped
    #     error="No module named 'compute_quantum_features'"
    #
    # ...y seguia adelante. Es decir: las features cuanticas se caian en
    # SILENCIO en produccion y en ningun sitio se decia que la corrida instalada
    # no era la misma que la de desarrollo. Copiarlo junto al backend lo pone en
    # el mismo sys.path que el resto.
    copy_file(
        root / "scripts" / "compute_quantum_features.py",
        resources / "backend" / "compute_quantum_features.py",
    )

    print("[3/7] Rescoring y selector de pose (sólo archivos versionados)")
    rescoring_tracked_count = copy_git_tracked_tree(
        root,
        root / "rescoring",
        resources / "rescoring",
        extra_dirs={"tests", "data", "deprecated", "scripts", "feature_cache_v4"},
        extra_files=(
            "*.bak",
            "*.bak*",
            "*.INVALID_DUE_TO_DATA_LEAKAGE",
            "scratch_*",
            "training_progress.*",
            *RESCORING_FUERA_DEL_RUNTIME_FILES,
        ),
    )
    print(f"      {rescoring_tracked_count} archivos reproducibles desde Git")

    print("[4/7] Motores científicos y herramientas externas")
    # `openbabel` es CRÍTICO, no opcional: viaja en el instalador y el respaldo
    # de conversión estructural del docking depende de él. Su ausencia aquí
    # significa que nadie ejecutó `scripts/stage_openbabel_tool.py`, y dejarlo
    # pasar produciría un instalador cuyo respaldo no puede funcionar.
    CRITICOS = {"vina", "openbabel"}
    for tool in ("vina", "xtb", "llama", "openbabel"):
        source = root / "tools" / tool
        if source.is_dir():
            copy_tree(source, resources / "tools" / tool, ignore=ignore_factory())
        elif tool in CRITICOS:
            pista = (
                "\nEjecuta `python scripts/stage_openbabel_tool.py` para "
                "materializarlo desde el wheel `openbabel-wheel`."
                if tool == "openbabel"
                else ""
            )
            raise FileNotFoundError(f"Motor crítico ausente: {source}{pista}")
        else:
            print(f"  opcional ausente: {tool}")

    print("[4b/7] Tokenizer de los motores descargables")
    # Los PESOS se descargan bajo demanda (8.4 GB); los archivos pequenos que
    # `from_pretrained` necesita para poder leerlos —config, vocabulario y
    # tokenizer— pesan kilobytes y viajan en el instalador. Sin ellos, el
    # checkpoint descargado NO se puede cargar: eran 8.4 GB inservibles.
    esmfold_models = root / "esmfold" / "models"
    if esmfold_models.is_dir():
        destino_esmfold = resources / "esmfold" / "models"
        destino_esmfold.mkdir(parents=True, exist_ok=True)
        for nombre in ("config.json", "vocab.txt", "tokenizer_config.json",
                       "special_tokens_map.json"):
            origen = esmfold_models / nombre
            if origen.is_file():
                copy_file(origen, destino_esmfold / nombre)
            else:
                print(f"  AVISO: falta {origen.name}; ESMFold no podra cargar")
    else:
        print("  opcional ausente: esmfold/models")

    print("[5/7] Estructuras y catálogo curado")
    copy_tree(
        root / "data" / "targets",
        resources / "data" / "targets",
        ignore=ignore_factory(),
    )
    seed_database = root / "data" / "molgraph_seed.db"
    if seed_database.is_file():
        copy_file(seed_database, resources / "data" / "molgraph_seed.db")
    copy_file(root / "curated_targets.json", resources / "curated_targets.json")
    copy_file(root / "curated_targets.csv", resources / "curated_targets.csv")

    print("[6/7] Licencias")
    legal_source = root / "frontend" / "public" / "legal"
    if not legal_source.is_dir():
        raise FileNotFoundError(f"Avisos legales ausentes: {legal_source}")
    copy_tree(legal_source, resources / "licenses", ignore=ignore_factory())

    print("[6a/7] Dependencias propias de cada herramienta")
    # El lector de tablas de importacion decide que hace falta y donde, en vez
    # de una lista escrita a mano que se queda vieja.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from pe_imports import imports_de

    # DLLs que YA viajan en el arbol de una herramienta pero no
    # junto al binario que las pide.
    #
    # Caso real: `tools/xtb/xtb.exe` necesita `libiomp5md.dll` y solo estaba en
    # `tools/xtb/xtb-6.7.1/bin/`. El backend prefiere el ejecutable de `bin/`
    # -que si la tiene al lado- pero conserva el de primer nivel como respaldo,
    # y ese respaldo no habria arrancado en una maquina limpia. Un plan B que
    # solo funciona en la maquina de quien lo escribio no es un plan B.
    for herramienta in sorted((resources / "tools").glob("*")):
        if not herramienta.is_dir():
            continue
        disponibles = {f.name.lower(): f for f in herramienta.rglob("*.dll")}
        for binario in herramienta.rglob("*"):
            if not binario.is_file() or binario.suffix.lower() not in (".exe", ".dll"):
                continue
            for dll in set(imports_de(binario)):
                if (binario.parent / dll).exists():
                    continue
                fuente = disponibles.get(dll)
                if fuente is not None:
                    copy_file(fuente, binario.parent / dll)
                    print(f"      {binario.parent.relative_to(resources).as_posix()}: + {dll}")

    print("[6a2/7] Runtime de Visual C++")
    # EL FALLO QUE ARREGLA. En una maquina Windows LIMPIA el backend no
    # arrancaba: `_greenlet.pyd` no cargaba, SQLAlchemy asincrono moria con el
    # y uvicorn se apagaba antes de contestar /health. Las DLLs del runtime de
    # Microsoft Visual C++ no existen en un Windows recien instalado; en la
    # maquina de desarrollo SI, porque Visual Studio las dejo en System32. El
    # fallo era invisible justo donde se construye y se prueba.
    #
    # POR QUE RECORRE TODO Y NO SOLO python/. La primera version copiaba las
    # DLLs a `python/` y daba el problema por cerrado. Pero `tools/llama/` no
    # tenia NINGUNA, y 52 de sus binarios las piden: en una maquina limpia el
    # servidor local de MolChat tampoco habria arrancado. Windows busca una DLL
    # en el directorio del binario que la pide, no en cualquier carpeta del
    # paquete, asi que cada directorio necesita las suyas.
    #
    # Se decide leyendo la tabla de importacion de cada PE, no por una lista
    # escrita a mano: asi sigue funcionando cuando cambien las dependencias.

    DLLS_MSVC = {
        "msvcp140.dll", "msvcp140_1.dll", "msvcp140_2.dll",
        "msvcp140_atomic_wait.dll", "msvcp140_codecvt_ids.dll",
        "concrt140.dll", "vcruntime140.dll", "vcruntime140_1.dll",
        "vcomp140.dll",
    }
    # ── DE QUE REDIST SE COPIAN, Y POR QUE NO VALE ORDENAR LA RUTA ────────
    #
    # Auditoria del 2026-09-04. Esto ordenaba las carpetas por su RUTA con
    # `reverse=True`, suponiendo que la mas nueva quedaria primero. No queda:
    # el nombre del directorio de Visual Studio no es un numero de version, y
    # ordenado como texto
    #
    #     "Microsoft Visual Studio/2019/..."   >   "Microsoft Visual Studio/18/..."
    #
    # porque '2' > '1' en el primer caracter. Medido en esta maquina:
    #
    #     GANABA   2019/BuildTools/.../14.29.30133/x64/Microsoft.VC142.CRT
    #              -> msvcp140.dll 14.29.30157
    #     DISPONIBLE  18/BuildTools/.../14.50.35710/x64/Microsoft.VC145.CRT
    #              -> msvcp140.dll 14.50.35719
    #
    # Y ademas `ProgramFiles(x86)` se recorre antes que `ProgramFiles`, asi que
    # un VS 2019 de 32 bits gana a un VS 2022 aunque el orden interno fuera
    # correcto. Como el primero que TIENE la DLL se la lleva, el paquete salia
    # con un runtime 14.29 al lado de binarios compilados contra 14.38+.
    #
    # CONSECUENCIA. `torch` no carga: `WinError 1114` (fallo de rutina de
    # inicializacion de la DLL) y, detras, ADMET devolviendo None en todo. En
    # esta maquina no se ve porque System32 tiene el runtime del sistema, que
    # es nuevo; en una instalacion limpia manda la DLL del directorio.
    #
    # Se ordena por la VERSION DE MSVC parseada del propio nombre de carpeta
    # (`.../MSVC/14.50.35710/...`), que es lo unico de esa ruta que significa
    # una version. Lo que no se puede parsear va al final, nunca delante.
    def _version_msvc(carpeta: Path) -> tuple[int, ...]:
        """(14, 50, 35710) desde `.../VC/Redist/MSVC/14.50.35710/x64/...`."""
        for parte in carpeta.parts:
            trozos = parte.split(".")
            if len(trozos) >= 2 and all(t.isdigit() for t in trozos):
                return tuple(int(t) for t in trozos)
        return (0,)

    # La fuente versionada gobierna por defecto: un build no cambia sólo porque
    # la máquina conserve otra versión de Visual Studio. Un override explícito
    # sí tiene prioridad y queda reservado para auditorías/reproducciones.
    origenes: list[Path] = []
    override = os.getenv("MOLDESIGN_VC_REDIST")
    if override:
        origenes.append(Path(override))
    origenes.append(validated_vc_runtime_dir(root))

    candidatas: list[Path] = []
    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles")):
        if not base:
            continue
        raiz_vs = Path(base) / "Microsoft Visual Studio"
        if not raiz_vs.is_dir():
            continue
        for carpeta in raiz_vs.glob("*/*/VC/Redist/MSVC/*/x64/*"):
            if carpeta.is_dir() and "debug" not in str(carpeta).lower():
                candidatas.append(carpeta)

    # Las dos bases se juntan ANTES de ordenar: si se ordenan por separado, un
    # redist viejo de ProgramFiles(x86) sigue ganando a uno nuevo de
    # ProgramFiles por el simple hecho de mirarse antes.
    candidatas.sort(key=_version_msvc, reverse=True)
    origenes.extend(candidatas)

    if candidatas:
        print(f"      redist elegido: {candidatas[0]}")

    raiz_python = resources / "python"
    necesita: dict[Path, set[str]] = {}
    for binario in resources.rglob("*"):
        if not binario.is_file() or binario.suffix.lower() not in (".dll", ".pyd", ".exe"):
            continue
        for dll in set(imports_de(binario)):
            if dll not in DLLS_MSVC:
                continue
            if (binario.parent / dll).exists():
                continue
            # Lo que cuelga de python/ tambien encuentra las DLLs junto al
            # interprete, que es el directorio del proceso que las carga.
            dentro_de_python = raiz_python in binario.parents
            if dentro_de_python and (raiz_python / dll).exists():
                continue
            destino = raiz_python if dentro_de_python else binario.parent
            necesita.setdefault(destino, set()).add(dll)

    copiadas = 0
    sin_encontrar: set[str] = set()
    for destino, dlls in sorted(necesita.items()):
        for dll in sorted(dlls):
            for origen in origenes:
                if (origen / dll).is_file():
                    copy_file(origen / dll, destino / dll)
                    copiadas += 1
                    break
            else:
                sin_encontrar.add(dll)
        print(f"      {destino.relative_to(resources).as_posix() or '.'}: {len(dlls)} DLL(s)")

    if not necesita:
        print("      nada que copiar: todas resueltas")
    else:
        print(f"      {copiadas} copiadas de la fuente app-local de Visual C++")
    if sin_encontrar:
        # No se detiene aqui: la comprobacion DURA la hace
        # verify_desktop_bundle.py sobre el resultado.
        print(f"      AVISO: no estaban en el redist: {', '.join(sorted(sin_encontrar))}")

    print("[6b/7] Bytecode precompilado")
    # POR QUE. El runtime viaja con 15.753 modulos .py en site-packages y solo
    # 5.138 .pyc: mas de 10.600 se compilan en la MAQUINA DEL USUARIO, en su
    # primer arranque. Peor: si algun dia el destino de instalacion es de solo
    # lectura (Program Files), Python no puede escribir el __pycache__ y los
    # recompila EN CADA ARRANQUE, para siempre.
    #
    # Se compila con el python EMPAQUETADO y no con el del sistema: el numero
    # magico del bytecode depende de la version del interprete, y un .pyc de
    # otra version se ignora en silencio. Compilar con el equivocado no daria
    # error; simplemente no serviria de nada, que es la peor forma de fallar.
    python_empaquetado = resources / "python" / "python.exe"
    if not python_empaquetado.is_file():
        python_empaquetado = resources / "python" / "bin" / "python"
    # SOLO lo que el arranque importa de verdad, y no site-packages entero.
    #
    # POR QUE NO TODO. Compilar los 15.753 modulos anadia 306 MB al runtime y
    # lo dejaba en 2210 MiB. `makensis` es un compilador de 32 bits y no puede
    # pasar de 2 GiB: el build murio con
    #
    #     Internal compiler error #12345: error mmapping file
    #     (2102254984, 33554432) is out of range
    #
    # ...es decir, precompilarlo todo no hacia el instalador mas grande: lo
    # hacia IMPOSIBLE. El limite no es una preferencia de tamano.
    #
    # DE DONDE SALE LA LISTA. De medir, no de suponer: `python -X importtime`
    # sobre el runtime empaquetado da los 1.221 modulos que se cargan al
    # arrancar. Estos son sus paquetes de terceros. Lo que no este aqui
    # simplemente no se precompila —se compilara en memoria si algun dia se
    # importa— asi que la lista puede quedarse corta sin romper nada.
    #
    # Para regenerarla:
    #   <python empaquetado> -X importtime -c "from api.main import app" 2> t.txt
    PAQUETES_DEL_ARRANQUE = (
        "sqlalchemy", "numpy", "reportlab", "pydantic", "pydantic_core", "rdkit",
        "rich", "fastapi", "starlette", "anyio", "httpx", "httpcore", "h11",
        "cryptography", "pydantic_settings", "structlog", "pygments", "wrapt",
        "attr", "attrs", "click", "jwt", "PIL", "email_validator", "limits",
        "slowapi", "psutil", "colorama", "idna", "certifi", "dotenv", "sniffio",
        "typing_inspection", "typing_extensions", "annotated_types", "packaging",
        "greenlet", "bcrypt", "deprecated", "defusedxml", "python_multipart",
        "multipart", "ujson", "orjson", "brotli", "zstandard", "pyphen",
        "uvicorn", "websockets", "watchfiles", "yaml", "aiosqlite", "passlib",
    )
    site_packages = resources / "python" / "Lib" / "site-packages"
    objetivos = [resources / "backend"]
    for nombre in PAQUETES_DEL_ARRANQUE:
        carpeta = site_packages / nombre
        if carpeta.is_dir():
            objetivos.append(carpeta)
        elif (site_packages / f"{nombre}.py").is_file():
            objetivos.append(site_packages / f"{nombre}.py")

    if python_empaquetado.is_file():
        total_pyc = 0
        for destino in objetivos:
            if not destino.exists():
                continue
            resultado = subprocess.run(
                [str(python_empaquetado), "-m", "compileall", "-q", "-j", "0", str(destino)],
                capture_output=True, text=True,
            )
            # compileall devuelve != 0 si ALGUN archivo no compila. En un arbol
            # con 15.000 modulos de terceros eso pasa —hay codigo py2, plantillas,
            # ejemplos rotos— y no es motivo para detener el empaquetado: esos
            # modulos ya fallaban igual antes y nadie los importa. Se cuenta lo
            # conseguido y se sigue.
            if destino.is_dir():
                total_pyc += len(list(destino.rglob("*.pyc")))
            elif resultado.returncode == 0:
                total_pyc += 1
        print(f"      {total_pyc} .pyc en {len(objetivos)} objetivos del arranque")
    else:
        print("      AVISO: no se encontro el python empaquetado; sin precompilar")

    print("[7/7] Manifiesto del runtime")
    critical_relative = [
        Path("python/python.exe"),
        Path("backend/api/main.py"),
        Path("rescoring/artifacts/model-manifest.json"),
        Path("rescoring/artifacts/model_a_universal.json"),
        Path("rescoring/artifacts/pose_selector_v06.xgb"),
        Path("rescoring/artifacts/gnn_v2_cl_best.pt"),
        Path("rescoring/artifacts/contrastive_v31_pretrained.pt"),
        Path("tools/vina/vina.exe"),
        # Open Babel viaja en el instalador: su ausencia o su alteración es una
        # instalación dañada, y el manifiesto es lo que permite decirlo.
        Path("tools/openbabel/bin/obabel.exe"),
        Path("tools/openbabel/openbabel-manifest.json"),
        Path("curated_targets.json"),
    ]
    critical = {}
    for relative in critical_relative:
        path = resources / relative
        if not path.is_file():
            raise FileNotFoundError(f"Asset crítico no empaquetado: {relative.as_posix()}")
        critical[relative.as_posix()] = {"bytes": path.stat().st_size, "sha256": sha256(path)}

    components = {
        directory.name: directory_stats(directory)
        for directory in sorted((item for item in resources.iterdir() if item.is_dir()), key=lambda item: item.name)
    }
    total = directory_stats(resources)
    manifest = {
        "schema_version": 1,
        "product": "MolDesign",
        "product_version": "1.0.0",
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "profile": "desktop-mvp",
        "rescoring_source": {
            "policy": "git-tracked-only",
            "files": rescoring_tracked_count,
        },
        "critical_assets": critical,
        "components": components,
        # Programas de terceros que viajan en el instalador y se ejecutan como
        # PROCESOS INDEPENDIENTES. La distinción no es decorativa: determina qué
        # obligaciones de licencia arrastran hacia el código de MolDesign, y
        # aquí queda escrita donde el instalador la puede leer.
        "external_programs": _programas_externos(root, resources),
        "total": total,
        "total_excludes_runtime_manifest": True,
    }
    (resources / "runtime-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Runtime preparado: {total['files']} archivos, {total['mib']} MiB")
    return resources


if __name__ == "__main__":
    args = parse_args()
    build_bundle(args.root)
