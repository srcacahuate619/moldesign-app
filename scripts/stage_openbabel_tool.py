#!/usr/bin/env python3
r"""Materializa Open Babel como HERRAMIENTA EXTERNA en `tools/openbabel/`.

# Qué hace y por qué existe

Open Babel es un **programa independiente bajo GPL-2.0-only**. MolDesign lo
distribuye en el mismo instalador, pero no lo enlaza ni lo importa: lo invoca
como `obabel.exe` por subproceso, con archivos de entrada y salida. Para que esa
frontera sea real y no una intención, el programa tiene que vivir fuera del
entorno Python importable, con su propia ruta, versión, hash y licencia.

Este script toma el binario y sus datos del wheel `openbabel-wheel` —que se usa
**sólo durante la construcción**, como fuente— y los deja en `tools/openbabel/`,
junto a `tools/vina/` y `tools/xtb/`, que es donde viven el resto de programas
que se invocan por subproceso.

Los *bindings* de Python del wheel (`openbabel.py`, `pybel.py`,
`_openbabel.pyd`) **no** se copian. `bundle_helper.py` los excluye además del
runtime empaquetado, y `check_openbabel_boundary.py` falla si reaparecen.

# Qué archivos hacen falta, y cómo se supo

No por lista escrita a mano. Se determinó ejecutando el binario empaquetado en
un directorio aislado, con el `PATH` reducido a `C:\Windows\System32` y sin
`BABEL_DATADIR` ni `BABEL_LIBDIR`, y comprobando una conversión PDBQT→SDF real.
El resultado medido (2026-09-05):

    obabel.exe          el ejecutable
    openbabel-3.dll     la biblioteca del programa
    *.obf               los plugins de formatos y de métodos
    data/               las tablas de tipos, campos de fuerza y SMARTS
    msvcp140.dll        runtime de Visual C++ que el wheel ya vendoriza
    vcruntime140*.dll   idem, resueltos del intérprete o del redist

NO hacen falta, y no se copian: `cmake/` (archivos de integración de
compilación), `openbabel-3.lib` (biblioteca de importación para enlazar, que es
justo lo que no queremos), `share/` (un splash PNG) ni los otros veinte
ejecutables `ob*.exe`, que producción no invoca.

El conjunto mínimo produjo un SDF **byte a byte idéntico** al del árbol
completo, así que el recorte no cambia ninguna salida científica.

# Salida

    tools/openbabel/bin/...                     el programa
    tools/openbabel/openbabel-manifest.json     versión, hashes, procedencia
    tools/openbabel/LICENSE-GPL-2.0.txt         el texto íntegro de la licencia
    tools/openbabel/README-PROCEDENCIA.md       cómo obtener y reconstruir la fuente

El manifiesto es la fuente de verdad del adaptador y de las guardas: lo que no
esté ahí, con su hash, no se ejecuta.

# Uso

    python scripts/stage_openbabel_tool.py            # escribe tools/openbabel/
    python scripts/stage_openbabel_tool.py --check    # falla si difiere
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
# (sin `datetime`: el manifiesto no lleva reloj, ver más abajo)
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

from vc_runtime_source import validated_vc_runtime_dir  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

DESTINO = RAIZ / "tools" / "openbabel"
MANIFIESTO = DESTINO / "openbabel-manifest.json"
LICENCIA = DESTINO / "LICENSE-GPL-2.0.txt"
PROCEDENCIA_MD = DESTINO / "README-PROCEDENCIA.md"
SOURCE_OFFER = DESTINO / "SOURCE-OFFER.json"

#: El wheel del que salen los bytes. Es una dependencia **de construcción**.
FUENTE_WHEEL = RAIZ / "python-embed" / "Lib" / "site-packages" / "openbabel"
LIBS_WHEEL = RAIZ / "python-embed" / "Lib" / "site-packages" / "openbabel_wheel.libs"

#: Texto íntegro de la GPLv2 que ya se distribuye con el producto.
GPL2_EN_EL_ARBOL = RAIZ / "frontend" / "public" / "legal" / "licenses" / "OpenBabel-GPL-2.0.txt"

SCHEMA_VERSION = 1

# ── Procedencia verificada ───────────────────────────────────────────────
#
# Estos valores NO se derivan del disco: describen de dónde salió el artefacto
# y son parte de la oferta de fuente correspondiente que exige la GPL. Se
# escriben aquí para que cambiarlos sea un cambio revisable, no un efecto
# secundario de volver a ejecutar el script.
PROCEDENCIA = {
    "paquete": "openbabel-wheel",
    "version_paquete": "3.1.1.23",
    "wheel": "openbabel_wheel-3.1.1.23-cp311-cp311-win_amd64.whl",
    "wheel_sha256": "f0568906e6959fc541518c8e4cea26973e58707bd2434fb7cddfc5f745c32df7",
    "plataforma": "CPython 3.11, Windows x86-64",
    "empaquetador_repo": "https://github.com/njzjz/openbabel-wheel",
    "empaquetador_commit": "c6b2731dbd0a559ee56b8084b6d9997df1beb16f",
    "fuentes_incorporadas_repo": "https://github.com/njzjz/openbabel",
    "fuentes_incorporadas_commit": "77993b9a3b96fb9bd86249098beb97ab0fcbafc6",
    "upstream": "https://github.com/openbabel/openbabel",
    "upstream_version": "3.1.1",
    "licencia_spdx": "GPL-2.0-only",
}

#: Lo que el ejecutable contesta a `-V`. Open Babel 3.1.1 fue una publicación de
#: corrección de empaquetado y **no** actualizó la cadena de versión interna:
#: el binario sigue diciendo 3.1.0. Se declara el valor MEDIDO y no el
#: esperado, porque una guarda que compara contra un número inventado sólo
#: comprueba la imaginación de quien la escribió.
VERSION_REPORTADA = "3.1.0"

#: Runtime de Visual C++ que obabel necesita y que Windows limpio no tiene.
#: `bundle_helper` ya resuelve esto para el instalador; aquí se resuelve
#: también para el árbol de desarrollo, para que dev y bundle ejecuten el mismo
#: conjunto de archivos.
ORIGENES_DLL = (LIBS_WHEEL, RAIZ / "python-embed")


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


def _redist_msvc() -> list[Path]:
    """Carpetas del redistribuible de Visual C++, la más nueva primero.

    Mismo criterio que `bundle_helper.py` [6a2/7]: se ordena por la VERSIÓN
    parseada del nombre de carpeta y no por la ruta como texto, porque
    "2019" > "18" alfabéticamente y eso elegía un runtime viejo.
    """

    def version(carpeta: Path) -> tuple[int, ...]:
        for parte in carpeta.parts:
            trozos = parte.split(".")
            if len(trozos) >= 2 and all(t.isdigit() for t in trozos):
                return tuple(int(t) for t in trozos)
        return (0,)

    preferidas: list[Path] = []
    override = os.getenv("MOLDESIGN_VC_REDIST")
    if override:
        preferidas.append(Path(override))

    candidatas: list[Path] = []
    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles")):
        if not base:
            continue
        raiz = Path(base) / "Microsoft Visual Studio"
        if not raiz.is_dir():
            continue
        for carpeta in raiz.glob("*/*/VC/Redist/MSVC/*/x64/*"):
            if carpeta.is_dir() and "debug" not in str(carpeta).lower():
                candidatas.append(carpeta)
    candidatas.sort(key=version, reverse=True)
    # La copia versionada gobierna el release salvo override explícito. Las
    # instalaciones locales sólo respaldan componentes futuros no declarados.
    return [*preferidas, validated_vc_runtime_dir(RAIZ), *candidatas]


def _cierre_de_dlls(binarios: list[Path]) -> set[str]:
    """DLLs de terceros que piden los binarios staged y no están a su lado."""
    from pe_imports import imports_de

    faltan: set[str] = set()
    presentes = {b.name.lower() for b in binarios}
    for binario in binarios:
        for dll in imports_de(binario):
            minuscula = dll.lower()
            if minuscula in presentes:
                continue
            # Las `api-ms-win-*` y `kernel32` las provee el propio Windows.
            if minuscula.startswith("api-ms-win-") or minuscula in {"kernel32.dll"}:
                continue
            faltan.add(dll)
    return faltan


def recolectar(destino: Path, fuente_wheel: Path = FUENTE_WHEEL) -> dict[str, str]:
    """Copia el conjunto mínimo medido y devuelve `ruta relativa -> origen`."""
    if not fuente_wheel.is_dir():
        raise SystemExit(
            f"No existe {fuente_wheel}.\n"
            "Open Babel se materializa desde el wheel `openbabel-wheel==3.1.1.23` "
            "instalado en `python-embed`. Ese wheel es una dependencia DE "
            "CONSTRUCCIÓN: sin él no hay bytes que empaquetar."
        )
    origen_bin = fuente_wheel / "bin"
    libs_wheel = fuente_wheel.parent / "openbabel_wheel.libs"
    bin_destino = destino / "bin"
    bin_destino.mkdir(parents=True, exist_ok=True)

    origenes: dict[str, str] = {}

    def copiar(src: Path, dst: Path, etiqueta: str) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        origenes[dst.relative_to(destino).as_posix()] = etiqueta

    etiqueta_wheel = "openbabel-wheel 3.1.1.23 (payload del wheel)"
    for nombre in ("obabel.exe", "openbabel-3.dll"):
        origen = origen_bin / nombre
        if not origen.is_file():
            raise SystemExit(f"El wheel no trae {nombre}: {origen}")
        copiar(origen, bin_destino / nombre, etiqueta_wheel)
    for obf in sorted(origen_bin.glob("*.obf")):
        copiar(obf, bin_destino / obf.name, etiqueta_wheel)

    origen_data = origen_bin / "data"
    if not origen_data.is_dir():
        raise SystemExit(f"El wheel no trae los datos de Open Babel: {origen_data}")
    for archivo in sorted(p for p in origen_data.rglob("*") if p.is_file()):
        relativa = archivo.relative_to(origen_data)
        copiar(archivo, bin_destino / "data" / relativa, etiqueta_wheel)

    # ── Runtime de Visual C++ ────────────────────────────────────────────
    # No se supone cuáles hacen falta: se leen las tablas de importación de lo
    # que se acaba de copiar.
    staged = [p for p in bin_destino.rglob("*") if p.suffix.lower() in (".exe", ".dll", ".obf")]
    pendientes = _cierre_de_dlls(staged)
    origenes_dll = [libs_wheel, *ORIGENES_DLL, *_redist_msvc()]
    sin_resolver: list[str] = []
    for dll in sorted(pendientes):
        for carpeta in origenes_dll:
            candidato = carpeta / dll
            if candidato.is_file():
                if carpeta in (libs_wheel, LIBS_WHEEL):
                    etiqueta = "openbabel-wheel (DLL vendorizada)"
                elif carpeta == RAIZ / "python-embed":
                    etiqueta = "runtime de Visual C++ (CPython embebido)"
                else:
                    etiqueta = "runtime de Visual C++ (redistribuible local)"
                copiar(candidato, bin_destino / dll, etiqueta)
                break
        else:
            sin_resolver.append(dll)
    if sin_resolver:
        raise SystemExit(
            "No se encontró el runtime que obabel.exe necesita: "
            + ", ".join(sin_resolver)
            + "\nInstala el redistribuible de Visual C++ x64 o define "
            "MOLDESIGN_VC_REDIST apuntando a su carpeta."
        )

    # ── Licencia y procedencia, junto al programa ────────────────────────
    if not GPL2_EN_EL_ARBOL.is_file():
        raise SystemExit(f"Falta el texto de la GPLv2: {GPL2_EN_EL_ARBOL}")
    shutil.copy2(GPL2_EN_EL_ARBOL, LICENCIA)
    PROCEDENCIA_MD.write_text(_texto_procedencia(), encoding="utf-8")
    return origenes


def _texto_procedencia() -> str:
    p = PROCEDENCIA
    return f"""# Open Babel — programa independiente distribuido con MolDesign AI

Este directorio contiene **Open Babel {p['upstream_version']}**, un programa
independiente cuyo copyright pertenece a sus autores y colaboradores. Se
distribuye bajo **GNU General Public License, versión 2 (GPL-2.0-only)**, cuyo
texto íntegro está en `LICENSE-GPL-2.0.txt`.

Open Babel se entrega **SIN NINGUNA GARANTÍA**, ni siquiera la garantía
implícita de comerciabilidad o idoneidad para un propósito determinado; véanse
las secciones 11 y 12 de la GPLv2.

## Relación con MolDesign AI

MolDesign AI es una obra separada, bajo PolyForm Noncommercial 1.0.0. **No enlaza con Open
Babel ni importa sus bindings de Python.** Lo invoca como herramienta de línea
de órdenes (`bin/obabel.exe`) mediante subproceso, pasando y recibiendo
archivos moleculares. Viajar en el mismo instalador es agregación en un medio
de distribución, no combinación en una sola obra.

## Procedencia exacta de estos bytes

| | |
|---|---|
| Paquete | `{p['paquete']}=={p['version_paquete']}` |
| Wheel | `{p['wheel']}` |
| SHA-256 del wheel | `{p['wheel_sha256']}` |
| Plataforma | {p['plataforma']} |
| Repositorio del empaquetador | {p['empaquetador_repo']} |
| Commit del empaquetador | `{p['empaquetador_commit']}` |
| Fuentes Open Babel incorporadas | {p['fuentes_incorporadas_repo']} |
| Commit de las fuentes | `{p['fuentes_incorporadas_commit']}` |
| Basado en Open Babel oficial | {p['upstream_version']} ({p['upstream']}) |
| Licencia efectiva declarada | `{p['licencia_spdx']}` |

El binario contesta `Open Babel {VERSION_REPORTADA}` a `obabel -V`. Open Babel
3.1.1 fue una publicación de corrección de empaquetado que no actualizó la
cadena de versión interna; la discrepancia es de origen y está declarada, no es
un error de este paquete.

## Cómo obtener el código fuente correspondiente

La GPLv2 §3 obliga a acompañar el binario del código fuente correspondiente, o
de una oferta escrita válida para obtenerlo. Cada publicación de MolDesign
adjunta el archivo de fuentes de **esta versión exacta**; además puede
reconstruirse así:

```bash
# 1. Las fuentes que se compilaron, por commit exacto
git clone {p['fuentes_incorporadas_repo']} openbabel-src
cd openbabel-src && git checkout {p['fuentes_incorporadas_commit']}

# 2. Las recetas de compilación que produjeron este wheel
git clone {p['empaquetador_repo']} openbabel-wheel-src
cd openbabel-wheel-src && git checkout {p['empaquetador_commit']}

# 3. El wheel publicado, cuyo SHA-256 debe ser el declarado arriba
pip download {p['paquete']}=={p['version_paquete']} \\
    --no-deps --only-binary :all: \\
    --python-version 3.11 --platform win_amd64
```

Un enlace a una web no basta por sí solo: la publicación debe ofrecer acceso al
código fuente correspondiente **de la versión exacta distribuida**. Ver
`frontend/public/legal/SOURCE_CODE_AND_RELINKING.md`.

## Reemplazo

No hay medida técnica que impida sustituir este programa. Otra compilación de
Open Babel con el mismo contrato de línea de órdenes funciona igual, siempre que
se actualice `openbabel-manifest.json` con sus hashes: MolDesign verifica el
hash antes de ejecutar y se abstiene si no coincide.

> Este documento describe la ingeniería y la procedencia. No es asesoría
> jurídica.
"""


def construir_manifiesto(destino: Path, origenes: dict[str, str]) -> dict:
    archivos: dict[str, dict] = {}
    for ruta in sorted(p for p in destino.rglob("*") if p.is_file()):
        relativa = ruta.relative_to(destino).as_posix()
        if relativa == MANIFIESTO.name:
            continue
        archivos[relativa] = {
            "bytes": ruta.stat().st_size,
            "sha256": sha256(ruta),
            "origen": origenes.get(relativa, "árbol de MolDesign"),
        }
    ejecutable = "bin/obabel.exe"
    if ejecutable not in archivos:
        raise SystemExit("El staging no dejó bin/obabel.exe")
    return {
        "schema_version": SCHEMA_VERSION,
        "programa": "Open Babel",
        "papel": (
            "Programa independiente invocado por MolDesign como herramienta de "
            "línea de órdenes mediante subproceso. NO se enlaza ni se importa."
        ),
        "licencia_spdx": PROCEDENCIA["licencia_spdx"],
        "licencia_texto": LICENCIA.name,
        "sin_garantia": (
            "Open Babel se distribuye SIN NINGUNA GARANTÍA; véanse las secciones "
            "11 y 12 de la GPLv2."
        ),
        "ejecutable": ejecutable,
        "version_paquete": PROCEDENCIA["version_paquete"],
        "version_reportada_por_el_binario": VERSION_REPORTADA,
        "procedencia": PROCEDENCIA,
        "archivos": archivos,
    }


def serializar(manifiesto: dict) -> str:
    return json.dumps(manifiesto, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _conversion_real(destino: Path) -> str:
    """Ejecuta una conversión PDBQT→SDF con el binario recién staged.

    No se da por buena una copia de archivos: si el programa no convierte una
    molécula, no está empaquetado, está depositado.
    """
    exe = destino / "bin" / "obabel.exe"
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
    with tempfile.TemporaryDirectory(prefix="ob-stage-") as tmp:
        entrada = Path(tmp) / "in.pdbqt"
        salida = Path(tmp) / "out.sdf"
        entrada.write_text(muestra, encoding="utf-8")
        proceso = subprocess.run(
            [str(exe), "-ipdbqt", str(entrada), "-osdf", "-O", str(salida)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if proceso.returncode != 0 or not salida.is_file():
            raise SystemExit(
                "El Open Babel staged no convierte PDBQT→SDF:\n"
                f"  exit={proceso.returncode}\n  stderr={proceso.stderr[-800:]}"
            )
        texto = salida.read_text(encoding="utf-8", errors="replace")
    if "$$$$" not in texto or "V2000" not in texto:
        raise SystemExit("El SDF producido por el Open Babel staged no es válido.")
    version = subprocess.run(
        [str(exe), "-V"], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=30,
    )
    reportada = (version.stdout or version.stderr).strip()
    if VERSION_REPORTADA not in reportada:
        raise SystemExit(
            f"El binario staged contesta {reportada!r}, no la versión declarada "
            f"{VERSION_REPORTADA!r}. Actualiza VERSION_REPORTADA sólo si de verdad "
            "cambió el programa."
        )
    return reportada


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--check", action="store_true", help="no escribe; falla si difiere")
    parser.add_argument(
        "--fuente-wheel", type=Path, default=FUENTE_WHEEL,
        help="directorio openbabel/ del wheel usado solo durante la construcci?n",
    )
    args = parser.parse_args()

    if args.check:
        if not MANIFIESTO.is_file():
            print(
                "No hay `tools/openbabel/openbabel-manifest.json`. Ejecuta "
                "`python scripts/stage_openbabel_tool.py`.",
                file=sys.stderr,
            )
            return 1
        manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
        problemas: list[str] = []
        for relativa, esperado in manifiesto.get("archivos", {}).items():
            ruta = DESTINO / relativa
            if not ruta.is_file():
                problemas.append(f"ausente: {relativa}")
                continue
            if ruta.stat().st_size != esperado["bytes"]:
                problemas.append(f"tamaño distinto: {relativa}")
            elif sha256(ruta) != esperado["sha256"]:
                problemas.append(f"hash distinto: {relativa}")
        sobrantes = sorted(
            p.relative_to(DESTINO).as_posix()
            for p in DESTINO.rglob("*")
            if p.is_file() and p.name != MANIFIESTO.name
            and p.relative_to(DESTINO).as_posix() not in manifiesto.get("archivos", {})
        )
        problemas += [f"no declarado en el manifiesto: {s}" for s in sobrantes]
        if problemas:
            print("tools/openbabel/ no coincide con su manifiesto:", file=sys.stderr)
            for p in problemas[:40]:
                print(f"  - {p}", file=sys.stderr)
            return 1
        reportada = _conversion_real(DESTINO)
        print(
            f"Open Babel verificado: {len(manifiesto['archivos'])} archivos, "
            f"{reportada}, conversión PDBQT→SDF correcta."
        )
        return 0

    fuente_wheel = args.fuente_wheel.resolve()
    if not fuente_wheel.is_dir():
        raise SystemExit(
            f"No existe {fuente_wheel}. La fuente de construcci?n se valida "
            "antes de tocar tools/openbabel/."
        )
    if not SOURCE_OFFER.is_file():
        raise SystemExit(
            "Falta tools/openbabel/SOURCE-OFFER.json: no se materializa un "
            "binario GPL sin su oferta de fuente versionada."
        )
    oferta_fuente = SOURCE_OFFER.read_bytes()
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    DESTINO.mkdir(parents=True)
    origenes = recolectar(DESTINO, fuente_wheel)
    SOURCE_OFFER.write_bytes(oferta_fuente)
    origenes[SOURCE_OFFER.name] = "declaracion versionada de la oferta GPLv2"
    reportada = _conversion_real(DESTINO)
    manifiesto = construir_manifiesto(DESTINO, origenes)
    # Sin marca de tiempo a propósito: el manifiesto se versiona y un reloj
    # dentro lo haría cambiar en cada staging aunque los bytes fueran los
    # mismos, convirtiendo el diff en ruido.
    manifiesto["verificacion"] = (
        f"Staging verificado ejecutando el binario: contesta {reportada!r} y "
        "convierte PDBQT→SDF a un SDF válido."
    )
    MANIFIESTO.write_text(serializar(manifiesto), encoding="utf-8")

    total = sum(a["bytes"] for a in manifiesto["archivos"].values())
    print(f"Open Babel staged en {DESTINO.relative_to(RAIZ).as_posix()}")
    print(f"  {len(manifiesto['archivos'])} archivos, {total / (1024 * 1024):.1f} MiB")
    print(f"  {reportada}")
    print(f"  licencia declarada: {manifiesto['licencia_spdx']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
