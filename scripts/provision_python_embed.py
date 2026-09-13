#!/usr/bin/env python3
"""Reconstruye `python-embed/` desde los orígenes oficiales, sin Hugging Face.

# El bloqueo que cierra

Un clon limpio no puede construir el instalador. `python-embed/` está en
`.gitignore` y **nueve** de los scripts npm invocan `..\\python-embed\\python.exe`:
sin ese intérprete, `npm run tauri:build` muere en la primera puerta con un
error de ruta que no explica nada.

Hasta hoy sólo había una vía para conseguirlo —`bootstrap_dev_tree.py --fetch`,
que descarga `runtime-base-v1.1.0.zip`— y ese artefacto **no está publicado**:
`RUNTIME_BASE.sha256` es `None` y el bootstrap se niega a descargar sin hash.
El efecto práctico era que nadie que clonara el repositorio podía construirlo,
que es justo lo que la AGPL promete a quien lo recibe.

Este script abre la segunda vía, la que no depende de que publiquemos nada:
CPython embebido de **python.org** y las dependencias de **PyPI**, con el
lockfile del repositorio.

# Lo medido, el 2026-09-06, contra los índices reales

De los 173 paquetes de `backend/requirements-embed.lock.txt`:

| Cuántos | De dónde | Cómo |
|---:|---|---|
| 170 | PyPI | rueda binaria; `--only-binary=:all:` resuelve los 170 |
| 1 | índice propio de llama-cpp-python | PyPI no publica rueda para CPython 3.11/Windows; el proyecto las publica aparte |
| 1 | github.com/openmm/pdbfixer | **no está en PyPI en ninguna versión** |
| 1 | — | `pip`, que se instala antes que nada |

Sin esos dos casos, `pip install -r` falla: el primero cae a compilar desde
fuente con `scikit_build_core` —y por tanto exige CMake y MSVC— y el segundo
muere con «No matching distribution found». Los dos están declarados abajo con
su origen, no escondidos en un mensaje de error.

# Lo que este script NO garantiza

**Bytes idénticos.** Las ruedas se republican y algunas traen extensiones
nativas compiladas contra la máquina que las construyó. Lo que reconstruye es
la **lista exacta de nombres y versiones** del lockfile, que es lo que hace
falta para construir el instalador. El SHA-256 de lo que viaja sigue viviendo
en `docs/api/sbom.json`.

**Que el resultado sea idéntico a `runtime-base-v1.1.0.zip`.** Ese artefacto se
empaqueta desde un árbol ya aprovisionado; esto aprovisiona el árbol. Si algún
día se publica, `bootstrap_dev_tree.py --fetch` es más rápido y más
determinista. Esta vía existe para cuando no lo está.

# Uso

    python scripts/provision_python_embed.py --check      # mide, no escribe
    python scripts/provision_python_embed.py --fetch      # aprovisiona
    python scripts/provision_python_embed.py --fetch --solo-interprete

Corre con el Python del sistema (3.9+): en un clon limpio el embebido es
justamente lo que no hay.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # pragma: no cover - comodidad de presentación, nunca un requisito
    from salida_consola import consola_utf8
except ImportError:
    def consola_utf8() -> None:
        for flujo in (sys.stdout, sys.stderr):
            reconfigurar = getattr(flujo, "reconfigure", None)
            if reconfigurar is not None:
                try:
                    reconfigurar(encoding="utf-8", errors="replace")
                except (ValueError, OSError):
                    pass

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "python-embed"
LOCKFILE = RAIZ / "backend" / "requirements-embed.lock.txt"

#: La versión exacta del intérprete distribuido. Sale de la cabecera del
#: lockfile, que la midió preguntándole al propio `python-embed/python.exe`.
VERSION_PYTHON = "3.11.9"
SERIE_PYTHON = "3.11"


@dataclass(frozen=True)
class Descarga:
    """Algo que se baja de un origen oficial, con su hash fijado."""

    nombre: str
    url: str
    sha256: str
    bytes: int
    procedencia: str

    def verificar(self, ruta: Path) -> None:
        real_bytes = ruta.stat().st_size
        if real_bytes != self.bytes:
            ruta.unlink(missing_ok=True)
            raise SystemExit(
                f"{self.nombre}: la descarga está incompleta.\n"
                f"  esperados {self.bytes} bytes, recibidos {real_bytes}\n"
                "Se descarta. Un archivo a medias que se extrae produce una "
                "instalación que parece válida y no lo es."
            )
        real = sha256(ruta)
        if real != self.sha256:
            ruta.unlink(missing_ok=True)
            raise SystemExit(
                f"{self.nombre}: el archivo descargado NO es el declarado.\n"
                f"  esperado {self.sha256}\n  obtenido {real}\n"
                "Se descarta."
            )


#: CPython embebido oficial. El hash se midió descargando esta misma URL el
#: 2026-09-06; python.org publica además su MD5 y firmas sigstore en la página
#: de la versión, así que un revisor puede contrastarlo sin fiarse de nosotros.
CPYTHON = Descarga(
    nombre=f"CPython {VERSION_PYTHON} embeddable (amd64)",
    url=(
        f"https://www.python.org/ftp/python/{VERSION_PYTHON}/"
        f"python-{VERSION_PYTHON}-embed-amd64.zip"
    ),
    sha256="009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b",
    bytes=11249023,
    procedencia="python.org, distribución oficial de la Python Software Foundation",
)

#: `pip` no viaja en la distribución embebida y ésta no trae `ensurepip`. Se
#: instala desde su propia rueda, con la versión que fija el lockfile. El hash
#: es el que publica PyPI para ese archivo, no uno que hayamos calculado.
PIP = Descarga(
    nombre="pip 26.1.2 (rueda)",
    url=(
        "https://files.pythonhosted.org/packages/5d/95/"
        "6b5cb3461ea5673ba0995989746db58eb18b91b54dbf331e72f569540946/"
        "pip-26.1.2-py3-none-any.whl"
    ),
    sha256="382ff9f685ee3bc25864f820aa50505825f10f5458ffff07e30a6d96e5715cab",
    bytes=1813144,
    procedencia="PyPI; el digest es el que publica el propio índice",
)

#: Los dos paquetes que PyPI no resuelve. Medido, no supuesto: ver la tabla del
#: encabezado. Cada uno dice por qué está aquí, porque un caso especial sin
#: motivo escrito se convierte en folclore a la primera persona que lo hereda.
EXTRA_INDEX_LLAMA = "https://abetlen.github.io/llama-cpp-python/whl/cpu"

CASOS_ESPECIALES: tuple[tuple[str, str, str], ...] = (
    (
        "llama_cpp_python",
        EXTRA_INDEX_LLAMA,
        "PyPI no publica rueda para CPython 3.11 en Windows: pip caería a "
        "compilar el sdist con scikit_build_core, que exige CMake y MSVC. El "
        "proyecto publica sus ruedas en este índice.",
    ),
    (
        "pdbfixer",
        "https://github.com/openmm/pdbfixer/archive/refs/tags/v1.12.tar.gz"
        "#sha256=a5c0b05dfaf2cdcad3b8ffc9ee1e6a955628aade0dda653da04d4a12ba4fe3ec",
        "No está en PyPI en NINGUNA versión (`pip index versions` devuelve "
        "«from versions: none»). Se distribuye por conda-forge y por el "
        "repositorio de openmm. Se instala desde el tag exacto.",
    ),
)


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def descargar(item: Descarga, destino: Path) -> Path:
    print(f"  bajando {item.nombre} ({item.bytes / 1048576:.1f} MiB)…")
    urllib.request.urlretrieve(item.url, destino)  # noqa: S310
    item.verificar(destino)
    print(f"    SHA-256 verificado: {item.sha256[:16]}…")
    return destino


def paquetes_del_lock() -> list[str]:
    """Las líneas reales del lockfile, sin comentarios ni vacías."""
    if not LOCKFILE.is_file():
        raise SystemExit(
            f"Falta {_bonita(LOCKFILE)}. Es la única lista "
            "exacta de lo que hay dentro del runtime distribuido; sin ella no "
            "hay nada que reconstruir."
        )
    return [
        linea.strip()
        for linea in LOCKFILE.read_text(encoding="utf-8").splitlines()
        if linea.strip() and not linea.lstrip().startswith("#")
    ]


def _nombre_de(requisito: str) -> str:
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
        if sep in requisito:
            return requisito.split(sep)[0].strip().lower().replace("-", "_")
    return requisito.strip().lower().replace("-", "_")


def particionar(paquetes: list[str]) -> tuple[list[str], dict[str, str]]:
    """(lo que sale de PyPI, {nombre especial: su línea del lock})."""
    especiales = {n for n, _, _ in CASOS_ESPECIALES}
    normales: list[str] = []
    apartados: dict[str, str] = {}
    for requisito in paquetes:
        nombre = _nombre_de(requisito)
        if nombre in especiales:
            apartados[nombre] = requisito
        elif nombre == "pip":
            continue  # ya instalado antes que nada
        else:
            normales.append(requisito)
    return normales, apartados


# ── Aprovisionamiento ────────────────────────────────────────────────────


def _habilitar_site(raiz_embed: Path) -> None:
    """La distribución embebida trae `import site` comentado.

    Sin `site`, `Lib/site-packages` no entra en `sys.path` y pip no sirve de
    nada: instalaría en un directorio que el intérprete no mira.
    """
    pth = next(raiz_embed.glob("python*._pth"), None)
    if pth is None:
        raise SystemExit(
            f"No hay `python*._pth` en {raiz_embed}: esto no parece una "
            "distribución embebida de CPython."
        )
    texto = pth.read_text(encoding="utf-8")
    if "\nimport site" in texto or texto.startswith("import site"):
        return
    texto = texto.replace("#import site", "import site")
    if "import site" not in texto:
        texto = texto.rstrip() + "\nimport site\n"
    pth.write_text(texto, encoding="utf-8")


def _instalar_pip(raiz_embed: Path, rueda: Path) -> None:
    """Extrae la rueda de pip en `site-packages`.

    No se hace con `python rueda/pip install rueda`: pip se niega a
    modificarse a sí mismo por esa vía («To modify pip, please run…»). Una
    rueda pura ES un zip, y extraerla es exactamente lo que hace instalarla.
    """
    site_packages = raiz_embed / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(rueda) as zf:
        for nombre in zf.namelist():
            destino = (site_packages / nombre).resolve()
            if not destino.is_relative_to(site_packages.resolve()):
                raise SystemExit(f"La rueda de pip intenta salirse: {nombre}")
        zf.extractall(site_packages)


def _ejecutar(exe: Path, *argumentos: str) -> int:
    orden = [str(exe), *argumentos]
    print(f"    $ {' '.join(orden[1:])[:150]}")
    return subprocess.run(orden, check=False).returncode


def aprovisionar(solo_interprete: bool, forzar: bool) -> int:
    if DESTINO.exists() and any(DESTINO.iterdir()) and not forzar:
        raise SystemExit(
            f"`{DESTINO.name}/` ya existe y no está vacío. No se sobrescribe "
            "nada sin permiso explícito: comprueba qué hay y repite con "
            "--force si quieres reemplazarlo."
        )

    with tempfile.TemporaryDirectory(prefix="moldesign-src-") as tmp:
        temporal = Path(tmp)
        print("Orígenes oficiales:")
        zip_cpython = descargar(CPYTHON, temporal / "cpython.zip")
        rueda_pip = descargar(PIP, temporal / "pip-26.1.2-py3-none-any.whl")

        if DESTINO.exists() and forzar:
            apartado = RAIZ / "dist" / "_python-embed-anterior"
            apartado.parent.mkdir(parents=True, exist_ok=True)
            if apartado.exists():
                shutil.rmtree(apartado, ignore_errors=True)
            print(f"  apartando el anterior a {_bonita(apartado)}")
            DESTINO.replace(apartado)

        print(f"Extrayendo el intérprete en {DESTINO.name}/…")
        DESTINO.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_cpython) as zf:
            zf.extractall(DESTINO)
        _habilitar_site(DESTINO)
        _instalar_pip(DESTINO, rueda_pip)

    exe = DESTINO / "python.exe"
    if not exe.is_file():
        raise SystemExit(f"No quedó `{exe}`: la extracción no produjo intérprete.")

    version = subprocess.run(
        [str(exe), "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"  intérprete: CPython {version}")
    if not version.startswith(SERIE_PYTHON):
        raise SystemExit(
            f"Se esperaba la serie {SERIE_PYTHON} y salió {version}. El bytecode "
            "precompilado del bundle lleva el número mágico de otra versión y se "
            "ignoraría en silencio."
        )

    if solo_interprete:
        escribir_recibo(dependencias=False)
        print(
            "\nIntérprete listo, SIN dependencias (--solo-interprete).\n"
            "El árbol todavía no puede construir el instalador."
        )
        return 0

    normales, apartados = particionar(paquetes_del_lock())
    print(f"\nInstalando {len(normales)} paquetes desde PyPI…")
    # Un directorio temporal, no `mkstemp`. Medido el 2026-09-06, después de
    # instalar los 170 paquetes correctamente: `mkstemp` devuelve un descriptor
    # ABIERTO, y en Windows un archivo abierto no se puede borrar. El `finally`
    # reventaba con WinError 32 —«el proceso no tiene acceso al archivo»— y
    # tiraba la corrida entera veinte minutos después de haber hecho el trabajo,
    # justo antes de instalar los dos casos especiales y escribir el recibo.
    with tempfile.TemporaryDirectory(prefix="moldesign-lock-") as carpeta:
        lista = Path(carpeta) / "lock-pypi.txt"
        lista.write_text("\n".join(normales) + "\n", encoding="utf-8")
        codigo = _ejecutar(
            exe, "-m", "pip", "install", "--no-cache-dir",
            "--only-binary=:all:", "-r", str(lista),
        )
    if codigo != 0:
        print(
            "\nLa instalación desde PyPI falló. `--only-binary=:all:` es "
            "deliberado: sin él, pip cae a compilar sdists y un fallo de "
            "compilador aparece 20 minutos después disfrazado de otra cosa.",
            file=sys.stderr,
        )
        return codigo

    for nombre, origen, motivo in CASOS_ESPECIALES:
        requisito = apartados.get(nombre)
        if requisito is None:
            print(f"  {nombre}: no está en el lockfile; se salta.")
            continue
        print(f"\n{nombre} — {motivo}")
        if origen.startswith("https://github.com/"):
            codigo = _ejecutar(exe, "-m", "pip", "install", "--no-cache-dir", origen)
        else:
            codigo = _ejecutar(
                exe, "-m", "pip", "install", "--no-cache-dir",
                "--extra-index-url", origen, requisito,
            )
        if codigo != 0:
            print(f"  {nombre} NO quedó instalado.", file=sys.stderr)
            return codigo

    escribir_recibo(dependencias=True)
    print("\nSe vuelve a medir, en vez de dar la instalación por buena:\n")
    return informe()


#: Recibo propio de esta vía. No lo lleva `runtime-base-v1.1.0.zip` porque este
#: runtime NO salió de ahí, y decir lo contrario sería una procedencia falsa.
#: `bootstrap_dev_tree.py` lo reconoce y por eso deja de llamar AJENO a un árbol
#: aprovisionado legítimamente desde los orígenes oficiales.
NOMBRE_RECIBO_FUENTE = ".runtime-fuente.json"


def escribir_recibo(dependencias: bool) -> Path:
    """Deja constancia de QUÉ se instaló y DESDE DÓNDE. Sin reloj: dos
    aprovisionamientos del mismo lockfile escriben el mismo recibo."""
    import json

    cuerpo = {
        "formato": 1,
        "via": "orígenes oficiales (python.org + PyPI)",
        "python": VERSION_PYTHON,
        "dependencias_instaladas": dependencias,
        "lockfile": LOCKFILE.relative_to(RAIZ).as_posix(),
        "lockfile_sha256": sha256(LOCKFILE),
        "descargas": [
            {"nombre": d.nombre, "url": d.url, "sha256": d.sha256,
             "bytes": d.bytes, "procedencia": d.procedencia}
            for d in (CPYTHON, PIP)
        ],
        "casos_especiales": [
            {"paquete": n, "origen": o, "motivo": m} for n, o, m in CASOS_ESPECIALES
        ],
        "no_garantiza": (
            "bytes idénticos: las ruedas se republican y algunas traen "
            "extensiones nativas. Garantiza la lista exacta del lockfile."
        ),
    }
    ruta = DESTINO / NOMBRE_RECIBO_FUENTE
    ruta.write_text(
        json.dumps(cuerpo, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    print(f"  recibo: {_bonita(ruta)}")
    return ruta


def _bonita(ruta: Path) -> str:
    """Relativa a la raíz cuando se pueda; absoluta cuando no.

    `relative_to` lanza si el destino cae fuera del árbol, y eso pasa cada vez
    que algo apunta `DESTINO` a un temporal. Un informe no puede tumbar al
    programa que informa.
    """
    try:
        return ruta.relative_to(RAIZ).as_posix()
    except ValueError:
        return str(ruta)


# ── Informe ──────────────────────────────────────────────────────────────


def informe() -> int:
    exe = DESTINO / "python.exe"
    if not exe.is_file():
        print(f"`{DESTINO.name}/python.exe` no existe: el árbol NO puede construir.")
        print(f"  origen: {CPYTHON.procedencia}")
        print(f"  arréglalo:  python {Path(__file__).name} --fetch")
        return 1

    version = subprocess.run(
        [str(exe), "-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"Intérprete: CPython {version}  ({DESTINO})")

    esperados = paquetes_del_lock()
    # `pip list --format=json`, no `pip freeze`. Medido el 2026-09-06 sobre un
    # árbol correctamente aprovisionado: `freeze` OMITE pip, setuptools y wheel
    # —los trata como parte del entorno— y a `pdbfixer`, instalado desde una
    # URL, lo escribe como `pdbfixer @ https://…` en vez de `pdbfixer==1.12.0`.
    # El informe anunciaba cuatro paquetes ausentes que estaban instalados. Un
    # comprobador que dice que falta lo que está es tan inútil como el que dice
    # que está lo que falta.
    proceso = subprocess.run(
        [str(exe), "-m", "pip", "list", "--format=json"],
        capture_output=True, text=True,
    )
    if proceso.returncode != 0:
        print("  pip no responde: el intérprete está a medias.")
        return 1
    import json as _json

    instalados = {
        _nombre_de(entrada["name"]): entrada["version"]
        for entrada in _json.loads(proceso.stdout or "[]")
    }
    faltan = [r for r in esperados if _nombre_de(r) not in instalados]
    distintos = [
        f"{_nombre_de(r)}: lock {r.split('==')[-1]}, disco {instalados[_nombre_de(r)]}"
        for r in esperados
        if "==" in r and _nombre_de(r) in instalados
        and instalados[_nombre_de(r)] != r.split("==")[-1]
    ]

    print(f"  lockfile: {len(esperados)} paquetes | instalados: {len(instalados)}")
    if faltan:
        print(f"  FALTAN {len(faltan)}: " + ", ".join(_nombre_de(r) for r in faltan[:8])
              + ("…" if len(faltan) > 8 else ""))
    if distintos:
        print(f"  VERSIÓN DISTINTA en {len(distintos)}:")
        for linea in distintos[:8]:
            print(f"    {linea}")

    if faltan or distintos:
        print(
            "\nEl runtime no coincide con su lockfile. Reconstruirlo:\n"
            f"  python {Path(__file__).name} --fetch --force"
        )
        return 1
    print("\nEl intérprete embebido coincide con `requirements-embed.lock.txt`.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check", action="store_true", help="mide y no escribe nada")
    grupo.add_argument("--fetch", action="store_true",
                       help="descarga de python.org y PyPI y aprovisiona")
    parser.add_argument("--solo-interprete", action="store_true",
                        help="sin las dependencias del lockfile (rápido, para probar)")
    parser.add_argument("--force", action="store_true",
                        help="reemplaza `python-embed/`, apartando el anterior")
    args = parser.parse_args()
    if args.check:
        return informe()
    return aprovisionar(args.solo_interprete, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
