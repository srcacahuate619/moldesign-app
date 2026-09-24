#!/usr/bin/env python3
"""Construye y comprueba `runtime-base-v1.1.0.zip`, el runtime redistribuible.

# El hueco que cierra, y el que abrió el archivo anterior

`launcher-manifest.json` fija un archivo base por URL, revisión inmutable y
SHA-256; la aplicación lo descarga y lo extrae para poder arrancar. Pero
**ningún script del repositorio lo generaba**: `base-v1.0.0.zip` se subió a
mano. Un repositorio público del que no se puede reconstruir el binario
distribuido incumple la promesa que la AGPL hace a quien lo recibe.

La primera versión de este script cerraba ese hueco y abría otro. Auditado el
2026-09-06, `base-v1.0.0.zip` resultó ser un archivo que **no se puede extraer
sobre un clon** sin daño:

| Lo que contiene | Por qué no puede extraerse sobre el árbol |
|---|---|
| `python/` | el bootstrap y el empaquetador esperan `python-embed/` |
| `backend/`, `rescoring/`, `scripts/` | copias de julio del código **versionado**: extraerlo pisa el trabajo actual |
| `rescoring/artifacts/*.pt` | pesos propios, licencia distinta, no redistribuibles con el resto |
| `site-packages/openbabel/` | bindings GPL importables desde el entorno AGPL |

Y `--check` —que anunciaba «empaqueta en un temporal»— escribía sobre
`dist/base-v1.0.0.zip`. Durante esa misma auditoría dejó corrupto el archivo
local. Un verificador que destruye lo que verifica es peor que no tenerlo.

`runtime-base-v1.1.0.zip` es un formato distinto con un nombre distinto. No
sustituye al publicado ni se parece a él: cambia el contrato, así que cambia el
nombre. El archivo v1.0.0 sigue donde está y este script no lo toca nunca.

# El contrato

1. Sólo dependencias y runtime **redistribuibles**. Nada del producto.
2. Ningún archivo rastreado por git. Se comprueba contra `git ls-files`, no
   contra una lista escrita a mano que puede quedarse vieja.
3. Ningún peso propio de MolDesign. Van aparte, con su licencia — ver §PESOS.
4. Ningún binding importable de Open Babel: ni `openbabel`, ni `pybel`, ni
   `_openbabel`. Ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.
5. Open Babel viaja **sólo** como programa externo, en `tools/openbabel/bin/`,
   con su versión, su SHA-256, su licencia y su procedencia declaradas en
   `RUNTIME-MANIFEST.json` y verificables contra el manifiesto versionado del
   repositorio.
6. El intérprete se materializa exactamente en `python-embed/`.
7. Cada archivo lleva su SHA-256 dentro del propio artefacto, de modo que una
   extracción incompleta se pueda distinguir de una completa.

# Los destinos permitidos

Un archivo no puede escribir donde le apetezca. Siete rutas son las únicas que
se empaquetan y las únicas que el bootstrap acepta extraer, y **ninguna de las
siete contiene código del producto**. Ésa es la garantía estructural.

Que además estén en `.gitignore` es deseable —evita que aprovisionar ensucie el
`git status` de quien clona— pero **no se da por supuesto**: se mide con
`git check-ignore` y `--check` lo informa. Medido el 2026-09-06 sobre esta
rama, `tools/openbabel/bin/` NO está ignorado: `.gitignore` cubre sus `.exe` y
sus `.dll` por extensión, pero no las tablas de datos, así que el directorio
aparece como no rastreado. La línea que falta está en
`docs/81_HANDOFF_RUNTIME_ALPHA.md`; no se añade desde aquí porque `.gitignore`
es de otro equipo.

Lo que esa ausencia NO compromete: nada de eso permite sobrescribir un archivo
versionado. Estar sin ignorar es ruido cosmético; la comprobación dinámica
contra `git ls-files` es la que impide el daño, y corre siempre.

# PESOS: lo que este archivo NO trae

Los pesos entrenados de MolDesign (`rescoring/artifacts/*.pt`) estaban dentro
de `base-v1.0.0.zip`. No vuelven. Su licencia no es la de las dependencias que
los rodean, y mezclarlos obliga a poner una sola etiqueta sobre dos cosas
distintas. **Los que usa el producto están versionados en el repositorio** bajo
LICENSE-MODELS (decisión del titular, 2026-09-23: se distribuyen gratuitamente).
`PESOS_PROPIOS` describe sólo un módulo opcional de checkpoints antiguos que no
está publicado; su definición entra en el manifiesto interno del zip, así que
no se cambia sin reconstruir el archivo. Ver `docs/78`.

# Determinismo

Entradas ordenadas y marca de tiempo fija: dos ejecuciones sobre el mismo árbol
dan el mismo SHA-256. Lo que NO garantiza es que dos árboles distintos den el
mismo archivo; eso depende de cómo se reconstruyó `python-embed/`, y lo
gobierna `backend/requirements-embed.lock.txt`.

# Uso

    python scripts/build_base_archive.py                # escribe dist/
    python scripts/build_base_archive.py --check        # NO escribe dist/
    python scripts/build_base_archive.py --inspeccionar ARCHIVO.zip
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json

import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:  # pragma: no cover - comodidad de presentación, nunca un requisito
    from salida_consola import consola_utf8
except ImportError:  # el ayudante puede no estar; el trabajo no depende de él
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

#: Nombre del inventario que viaja DENTRO del zip. No se extrae al árbol: el
#: bootstrap lo guarda como recibo de aprovisionamiento.
NOMBRE_MANIFIESTO = "RUNTIME-MANIFEST.json"

#: Versión del formato del artefacto. Sube cuando cambie la ESTRUCTURA, no
#: cuando cambie el contenido: un bootstrap viejo tiene que poder decir «este
#: archivo es de un formato que no sé leer» en vez de intentarlo a medias.
FORMATO = 1

PYTHON_EMBEBIDO = "3.11"


@dataclass(frozen=True)
class Modulo:
    """Un artefacto descargable, declarado antes de existir.

    `sha256` y `size_bytes` en `None` significan **no publicado todavía**. Es un
    estado legítimo y distinto de «publicado y no coincide»: el bootstrap se
    niega a descargar sin hash, en vez de descargar y confiar.
    """

    id: str
    filename: str
    version: str
    licencia: str
    urls: tuple[str, ...] = ()
    sha256: str | None = None
    size_bytes: int | None = None
    #: `True` si el repositorio de origen exige autenticación aceptada.
    gated: bool = False
    nota: str = ""

    @property
    def publicado(self) -> bool:
        return bool(self.urls) and bool(self.sha256) and bool(self.size_bytes)


#: El runtime redistribuible. Sin gating a propósito: es obligatorio para
#: arrancar, y poner una puerta delante de lo que todo el mundo necesita sólo
#: produce usuarios bloqueados. Ver `docs/78`.
#:
#: `sha256`/`size_bytes` se rellenan al publicar, con los que imprime este
#: script. Mientras estén en `None`, `--check` verifica el CONTENIDO y dice qué
#: habría que publicar; no finge una comparación que no puede hacer.
RUNTIME_BASE = Modulo(
    id="runtime-base",
    filename="runtime-base-v1.1.0.zip",
    version="1.1.0",
    licencia=(
        "cada componente conserva la suya; el inventario del artefacto las "
        "declara una por una (ver RUNTIME-MANIFEST.json)"
    ),
    urls=(
        "https://huggingface.co/srcacahuate/moldesign-models/resolve/"
        "<REVISION-INMUTABLE>/v1.1.0/runtime-base-v1.1.0.zip",
    ),
    sha256=None,
    size_bytes=None,
    gated=False,
    nota=(
        "La URL lleva `<REVISION-INMUTABLE>` a propósito: una rama no fija "
        "bytes. Se sustituye por el commit de Hugging Face al publicar."
    ),
)

#: Los pesos propios. Contrato declarado, NO implementado: este script no los
#: descarga, no los empaqueta y no crea el repositorio.
#:
#: Que `urls` esté vacío no es un descuido — es el estado real. El repositorio
#: `moldesign-rescoring` no existe todavía, y un contrato que apunta a una URL
#: inventada es peor que uno que dice «falta esto».
PESOS_PROPIOS = Modulo(
    id="rescoring-weights",
    filename="rescoring-weights-v1.1.0.zip",
    version="1.1.0",
    licencia="LICENSE-MODELS v1.1 (MolDesign Model License)",
    urls=(),
    sha256=None,
    size_bytes=None,
    gated=True,
    nota=(
        "Origen previsto: hf.co/srcacahuate/moldesign-rescoring, con acceso "
        "controlado y aceptación de LICENSE-MODELS. Requiere credencial. "
        "Su AUSENCIA es legítima: sin estos pesos CL-GNN y el preentrenado "
        "contrastivo no están disponibles y la corrida lo declara; lo que no "
        "es legítimo es un archivo presente que no coincida con su hash."
    ),
)


@dataclass(frozen=True)
class Componente:
    """Un trozo del artefacto, con su licencia y su razón de estar."""

    prefijo: str
    licencia: str
    obligatorio: bool
    descripcion: str
    #: Si el prefijo nombra un archivo suelto y no un directorio.
    es_archivo: bool = False
    #: Archivos que prueban que el componente ESTÁ, relativos al prefijo. Basta
    #: uno.
    #:
    #: «El directorio existe y no está vacío» no sirve como prueba: `tools/llama/`
    #: trae `README.md` y `SHA256SUM.txt` versionados, así que un clon recién
    #: hecho lo daba por presente y el informe decía OK sobre un directorio sin
    #: un solo binario. Se comprueba el ejecutable, que es lo que hace falta.
    sondas: tuple[str, ...] = ()


#: LOS ÚNICOS DESTINOS. El orden es el del informe: primero lo que bloquea.
#:
#: Las siete rutas están en `.gitignore` (medido, no supuesto: lo comprueba
#: `_verificar_destinos_ignorados`). Ninguna contiene código del producto, así
#: que ni el empaquetador ni el bootstrap pueden pisar el repositorio aunque
#: alguien se equivoque escribiendo una lista.
COMPONENTES: tuple[Componente, ...] = (
    Componente(
        "python-embed/",
        "PSF-2.0 (CPython) + las de cada dependencia; ver "
        "backend/requirements-embed.lock.txt y docs/api/sbom.json",
        True,
        f"CPython {PYTHON_EMBEBIDO} embeddable con el entorno científico. "
        "SIN los bindings de Open Babel.",
        sondas=("python.exe", "bin/python3"),
    ),
    Componente(
        "tools/vina/",
        "Apache-2.0",
        True,
        "AutoDock Vina 1.2.7: el motor de docking. Se invoca por subproceso.",
        sondas=("vina.exe", "vina"),
    ),
    Componente(
        "tools/openbabel/bin/",
        "GPL-2.0-only",
        True,
        "Open Babel 3.1.1.23 como PROGRAMA INDEPENDIENTE. Sólo el binario y "
        "sus datos: el manifiesto, la licencia y la procedencia están "
        "versionados en `tools/openbabel/` y no viajan aquí para que el "
        "archivo no pueda contradecirlos.",
        sondas=("obabel.exe", "obabel"),
    ),
    Componente(
        "tools/xtb/",
        "LGPL-3.0-or-later",
        False,
        "xTB 6.7.1: descriptores cuánticos. Sin él, esa capa se declara ausente.",
        sondas=("xtb.exe", "bin/xtb"),
    ),
    Componente(
        "tools/llama/",
        "MIT",
        False,
        "llama.cpp: servidor local de MolChat. Sin él, MolChat no tiene motor.",
        sondas=("llama-server.exe", "llama-server"),
    ),
    Componente(
        "esmfold/models/",
        "MIT (facebook/esmfold_v1); los PESOS son otra descarga",
        False,
        "Sólo el tokenizer: unos kilobytes sin los cuales el checkpoint de "
        "8,4 GB no se puede leer.",
        sondas=("config.json",),
    ),
    Componente(
        "data/molgraph_seed.db",
        "CC0-1.0 (datos derivados de fuentes públicas)",
        False,
        "Base sembrada del grafo molecular. Si falta se siembra sola en el "
        "primer arranque, más despacio.",
        es_archivo=True,
    ),
)

#: Basura que nunca debe viajar dentro del runtime.
EXCLUIR_DIRS = {"__pycache__", ".git", "test", "tests", ".pytest_cache", ".mypy_cache"}
EXCLUIR_SUFIJOS = (".pyc", ".pyo", ".log", ".err", ".out", ".tmp")

#: Huellas de los bindings de Open Babel. Se comparan en minúsculas contra el
#: NOMBRE de cada entrada, no contra la ruta completa: `openbabel-3.dll` —que sí
#: viaja, dentro del programa externo— no empieza por ninguna de éstas seguida
#: de un límite de módulo, y el chequeo lo distingue. Ver `_es_binding`.
MODULOS_PROHIBIDOS = ("openbabel", "pybel", "_openbabel")

#: Extensiones de peso entrenado. La primera defensa contra los pesos PROPIOS
#: es estructural —`rescoring/`, `models/` y `scripts/artifacts_science/` no
#: están entre los destinos permitidos—; ésta es la segunda, por si alguien
#: mete un `.pt` dentro de un destino que sí lo está.
#:
#: NO se aplica dentro de `site-packages`. Medido el 2026-09-06 sobre el árbol
#: real: `admet_ai` vendoriza sus propios checkpoints
#: (`resources/models/admet_classification/model_0.pt` y compañía). Son pesos de
#: una DEPENDENCIA, con la licencia de esa dependencia, y sin ellos la capa
#: ADMET no funciona. Llamarlos «pesos propios de MolDesign» sería falso y
#: bloquearía el empaquetado por una regla mal apuntada.
#:
#: A cambio no se ocultan: el manifiesto los cuenta y dice de qué paquete sale
#: cada uno, para que una revisión de licencias los vea sin tener que abrir el
#: zip.
SUFIJOS_DE_PESO = (".pt", ".pth.tar", ".joblib", ".xgb", ".npz", ".safetensors", ".ckpt")

#: Marca de tiempo fija del zip. 1980-01-01 es el mínimo del formato. Cualquier
#: valor sirve mientras sea constante: si fuera el reloj, el SHA-256 cambiaría
#: en cada empaquetado y no significaría nada.
FECHA_FIJA = (1980, 1, 1, 0, 0, 0)

#: Nombres que Windows no puede crear. Un zip que los traiga no es un zip
#: portable, y en esta plataforma dejaría la extracción a medias.
RESERVADOS_WINDOWS = {
    "con", "prn", "aux", "nul",
    *(f"com{n}" for n in range(1, 10)),
    *(f"lpt{n}" for n in range(1, 10)),
}


class ArchivoRechazado(Exception):
    """El artefacto no cumple el contrato. `codigo` es lo que prueban las pruebas."""

    def __init__(self, codigo: str, detalle: str) -> None:
        super().__init__(f"[{codigo}] {detalle}")
        self.codigo = codigo
        self.detalle = detalle


# ── Validación de nombres ────────────────────────────────────────────────
#
# Todo esto se comprueba ANTES de escribir un solo byte. `extractall` de la
# biblioteca estándar sanea rutas desde 3.12, pero este código corre también
# con el Python del sistema de quien clona, que puede ser 3.9.

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_UNIDAD = re.compile(r"^[A-Za-z]:")


def _binding_de_open_babel(nombre: str) -> str | None:
    """¿Hay aquí algo que `import` pueda alcanzar? Devuelve la parte ofensiva.

    La pregunta no es «¿se llama openbabel?» sino «¿está dentro del entorno
    Python?». `tools/openbabel/bin/openbabel-3.dll` se llama así y **debe**
    viajar: es la biblioteca del programa externo, y ningún `import` la ve.
    `python-embed/Lib/site-packages/openbabel/__init__.py` sí la ve, y ésa es
    exactamente la frontera que docs/79 existe para sostener.

    Por eso la comprobación se limita a `python-embed/`. Fuera de ahí no hay
    ruta de importación, y aplicar la regla por el nombre convertiría la única
    forma correcta de distribuir Open Babel en un error.
    """
    if not nombre.startswith("python-embed/"):
        return None
    for parte in PurePosixPath(nombre).parts[1:]:
        tallo = parte.lower()
        for extension in (".py", ".pyd", ".so", ".pyi"):
            if tallo.endswith(extension):
                tallo = tallo[: -len(extension)]
                break
        # `openbabel_wheel-3.1.1.dist-info` y `openbabel_wheel.libs` son la
        # distribución y sus DLL privadas: rastro del wheel que no debe quedar.
        raiz = re.split(r"[-.]", tallo, maxsplit=1)[0]
        if tallo in MODULOS_PROHIBIDOS or raiz in MODULOS_PROHIBIDOS:
            return parte
        if raiz in ("openbabel_wheel", "obabel"):
            # `obabel.exe`/`obabel-script.py`: el lanzador que pip deja en
            # `Scripts/`, que resolvería el binario dentro del paquete Python.
            return parte
    return None


def validar_nombre(nombre: str) -> None:
    """Rechaza cualquier nombre que no pueda extraerse con seguridad.

    Cada `raise` de aquí corresponde a una muestra deliberadamente defectuosa
    del autotest. Un detector que no se ha visto fallar no está comprobado.
    """
    if not nombre or nombre.endswith("/"):
        raise ArchivoRechazado("ENTRADA_VACIA", f"entrada sin archivo: {nombre!r}")
    if _CONTROL.search(nombre):
        raise ArchivoRechazado("CARACTER_DE_CONTROL", f"nombre con control: {nombre!r}")
    if "\\" in nombre:
        raise ArchivoRechazado(
            "SEPARADOR_NO_PORTABLE",
            f"el zip usa `\\` como separador: {nombre!r}. El formato exige `/`; "
            "en Linux ese nombre sería un archivo con una barra invertida dentro.",
        )
    if nombre.startswith("/") or _UNIDAD.match(nombre):
        raise ArchivoRechazado("RUTA_ABSOLUTA", f"ruta absoluta: {nombre!r}")
    partes = PurePosixPath(nombre).parts
    if any(p in ("..", ".") for p in partes):
        raise ArchivoRechazado("TRAVERSAL", f"la ruta se sale del destino: {nombre!r}")
    for parte in partes:
        if parte != parte.strip() or parte.endswith("."):
            raise ArchivoRechazado(
                "NOMBRE_NO_PORTABLE",
                f"`{parte}` acaba en punto o espacio: Windows lo trunca en silencio",
            )
        if parte.split(".")[0].lower() in RESERVADOS_WINDOWS:
            raise ArchivoRechazado(
                "NOMBRE_RESERVADO", f"`{parte}` es un nombre reservado en Windows"
            )


#: Dentro de esto vive lo que instaló `pip`, y lo que instaló `pip` es de quien
#: publicó el paquete.
PREFIJOS_DE_DEPENDENCIAS = (
    "python-embed/Lib/site-packages/",
    "python-embed/lib/site-packages/",
)


def _es_de_una_dependencia(nombre: str) -> bool:
    return nombre.startswith(PREFIJOS_DE_DEPENDENCIAS)


def _paquete_de(nombre: str) -> str:
    for prefijo in PREFIJOS_DE_DEPENDENCIAS:
        if nombre.startswith(prefijo):
            return nombre[len(prefijo):].split("/", 1)[0]
    return "?"


def validar_destino(nombre: str) -> Componente:
    """El nombre tiene que caer dentro de un componente declarado."""
    for componente in COMPONENTES:
        if componente.es_archivo:
            if nombre == componente.prefijo:
                return componente
        elif nombre.startswith(componente.prefijo):
            return componente
    raise ArchivoRechazado(
        "DESTINO_NO_PERMITIDO",
        f"`{nombre}` no cae en ninguno de los destinos declarados: "
        + ", ".join(c.prefijo for c in COMPONENTES),
    )


def validar_contenido(nombre: str) -> None:
    """Las prohibiciones de contenido, aparte de las de ruta."""
    hoja = PurePosixPath(nombre).name
    ofensiva = _binding_de_open_babel(nombre)
    if ofensiva is not None:
        raise ArchivoRechazado(
            "BINDING_DE_OPEN_BABEL",
            f"`{nombre}` deja `{ofensiva}` dentro del entorno Python del "
            "runtime. GPL-2.0-only y AGPL-3.0 son incompatibles: un import "
            "convertiría las dos obras en una sola. Ver docs/79.",
        )
    if hoja.lower().endswith(SUFIJOS_DE_PESO) and not _es_de_una_dependencia(nombre):
        raise ArchivoRechazado(
            "PESO_PROPIO",
            f"`{nombre}` parece un peso entrenado de MolDesign. Los pesos "
            "propios tienen otra licencia y otro origen: ver PESOS_PROPIOS y "
            "docs/78.",
        )


def _entrada_es_enlace(info: zipfile.ZipInfo) -> bool:
    """Enlaces simbólicos y demás archivos que no son archivos.

    Un zip creado en Unix guarda el modo en los 16 bits altos de
    `external_attr`. `extractall` los ignora y crea un archivo de texto con la
    ruta dentro, que es un fallo silencioso: el bootstrap lo rechaza en vez de
    producir un runtime con un «binario» de 30 bytes.
    """
    if info.create_system != 3:  # 3 = Unix; en Windows no hay modo que leer
        return False
    modo = (info.external_attr >> 16) & 0xF000
    return modo in (0xA000, 0x6000, 0x2000, 0x1000, 0xC000)  # link, blk, chr, fifo, sock


# ── git: qué está rastreado ──────────────────────────────────────────────


def rutas_rastreadas(raiz: Path) -> frozenset[str]:
    """Lo que git versiona, en rutas POSIX relativas a la raíz.

    Devuelve el conjunto vacío si no hay git o el árbol no es un repositorio.
    Eso NO relaja la comprobación: la defensa principal es la lista de destinos
    permitidos, y esto es la segunda. Un conjunto vacío se declara en el informe
    para que nadie lea «0 conflictos» como «comprobado».
    """
    try:
        proceso = subprocess.run(
            ["git", "-C", str(raiz), "ls-files", "-z"],
            capture_output=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    if proceso.returncode != 0:
        return frozenset()
    salida = proceso.stdout.decode("utf-8", errors="replace")
    return frozenset(p for p in salida.split("\0") if p)


def _verificar_destinos_ignorados(raiz: Path) -> list[str]:
    """Destinos que `.gitignore` NO cubre por completo.

    Qué mide exactamente, porque la diferencia importa: se sonda cada destino
    con un nombre inventado y sin extensión (`tools/llama/__sonda__`). Así, un
    destino sale en esta lista cuando la regla que lo cubre es por EXTENSIÓN
    —`tools/**/*.exe`, `*.dll`— y no por directorio. Sus binarios sí están
    ignorados; una tabla de datos `.txt` que caiga ahí, no.

    No es una comprobación de seguridad. Lo que impide pisar código versionado
    son los destinos permitidos y `git ls-files`, y los dos corren siempre.
    Esto es higiene: dice si aprovisionar va a dejar ruido en `git status`.

    Si no hay git, devuelve la lista vacía porque no se pudo medir — no porque
    esté todo bien. Quien la consuma tiene que distinguirlo.
    """
    try:
        muestras = [
            c.prefijo if c.es_archivo else f"{c.prefijo}__sonda__"
            for c in COMPONENTES
        ]
        proceso = subprocess.run(
            ["git", "-C", str(raiz), "check-ignore", "--no-index", *muestras],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    ignorados = {linea.strip().replace("\\", "/") for linea in proceso.stdout.splitlines()}
    sin_ignorar = []
    for componente, muestra in zip(COMPONENTES, muestras):
        if muestra.replace("\\", "/") not in ignorados:
            sin_ignorar.append(componente.prefijo)
    return sin_ignorar


# ── Empaquetado ──────────────────────────────────────────────────────────


def _incluir(ruta: Path) -> bool:
    if any(parte in EXCLUIR_DIRS for parte in ruta.parts):
        return False
    return not ruta.name.lower().endswith(EXCLUIR_SUFIJOS)


def sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


@dataclass
class Recuento:
    archivos: int = 0
    bytes: int = 0


def _exclusiones_de_bindings() -> tuple[set[str], tuple[str, ...]]:
    """La lista de nombres que `bundle_helper` ya usa para quitar el wheel.

    Se lee de allí en vez de copiarla: es la misma decisión y una segunda copia
    se queda vieja. Que la lista y el VALIDADOR sean mecanismos distintos es
    deliberado —la lista excluye por nombre exacto, `_binding_de_open_babel`
    reconoce por forma— porque si el guardián comprobara justo lo mismo que la
    exclusión, no podría fallar nunca y no comprobaría nada.
    """
    try:
        from bundle_helper import (  # noqa: PLC0415
            OPENBABEL_BINDINGS_DIRS,
            OPENBABEL_BINDINGS_FILES,
        )
    except ImportError:  # pragma: no cover - sólo si se mueve el empaquetador
        return set(), ()
    return set(OPENBABEL_BINDINGS_DIRS), tuple(OPENBABEL_BINDINGS_FILES)


def _es_rastro_del_wheel(
    relativa: Path, dirs_binding: set[str], patrones: tuple[str, ...]
) -> bool:
    """¿Cae este archivo dentro de lo que el empaquetador ya quita del runtime?"""
    if any(parte in dirs_binding for parte in relativa.parts):
        return True
    return any(
        fnmatch.fnmatch(parte, patron)
        for parte in relativa.parts
        for patron in patrones
    )


def reunir(raiz: Path) -> tuple[list[tuple[str, Path]], list[str], list[str]]:
    """(entradas ordenadas, obligatorios que faltan, versionados omitidos).

    Dos exclusiones, las dos por definición y no por defensa:

    **El wheel de Open Babel.** Sigue instalado en el `python-embed` de
    desarrollo —es la FUENTE de la que `stage_openbabel_tool.py` saca el
    binario— así que se excluye al copiar, igual que hace `bundle_helper` con
    el bundle. Fallar por encontrarlo obligaría a desinstalarlo del árbol de
    trabajo para poder empaquetar, y entonces no habría de dónde sacar el
    programa externo.

    **Lo que git ya versiona.** El artefacto es, por definición, «lo que el
    árbol necesita y el repositorio no trae»; si el repositorio lo trae, el
    artefacto no tiene nada que aportar y sí algo que romper. Medido el
    2026-09-06 sobre el árbol real: `tools/llama/` contiene `.gitkeep`,
    `README.md` y `SHA256SUM.txt` versionados junto a binarios que no lo están.
    Se omiten, y se DEVUELVEN para que el manifiesto los declare: una exclusión
    silenciosa es indistinguible de un olvido.
    """
    entradas: dict[str, Path] = {}
    faltan: list[str] = []
    omitidos: list[str] = []
    dirs_binding, patrones_binding = _exclusiones_de_bindings()
    rastreadas = rutas_rastreadas(raiz)

    for componente in COMPONENTES:
        origen = raiz / componente.prefijo.rstrip("/")
        if componente.es_archivo:
            if origen.is_file():
                entradas[componente.prefijo] = origen
            elif componente.obligatorio:
                faltan.append(componente.prefijo)
            continue
        if not origen.is_dir() or not any(origen.iterdir()):
            if componente.obligatorio:
                faltan.append(componente.prefijo)
            continue
        es_python = componente.prefijo == "python-embed/"
        for archivo in origen.rglob("*"):
            if not archivo.is_file() or not _incluir(archivo):
                continue
            relativa_al_componente = archivo.relative_to(origen)
            if es_python and relativa_al_componente.as_posix() in {
                ".runtime-base.json",
                ".runtime-fuente.json",
            }:
                continue
            # `is_symlink` antes que nada: seguir un enlace metería en el
            # artefacto bytes de fuera del árbol sin que se note.
            if archivo.is_symlink():
                continue
            if es_python and _es_rastro_del_wheel(
                relativa_al_componente, dirs_binding, patrones_binding
            ):
                continue
            nombre = archivo.relative_to(raiz).as_posix()
            if nombre in rastreadas:
                omitidos.append(nombre)
                continue
            entradas[nombre] = archivo

    ordenadas = sorted(entradas.items(), key=lambda par: par[0])
    return ordenadas, faltan, sorted(omitidos)


def _manifiesto_openbabel(raiz: Path) -> dict:
    """La procedencia de Open Babel, leída de su manifiesto versionado.

    No se copia aquí la versión ni el hash a mano: una segunda copia es una
    segunda copia que se queda vieja. Si el manifiesto no está, se dice.
    """
    ruta = raiz / "tools" / "openbabel" / "openbabel-manifest.json"
    if not ruta.is_file():
        return {"declarado": False, "por_que": f"falta {ruta.name} en el árbol"}
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    ejecutable = datos.get("ejecutable", "")
    return {
        "declarado": True,
        "programa": datos.get("programa"),
        "version": datos.get("version_paquete"),
        "licencia_spdx": datos.get("licencia_spdx"),
        "ejecutable": f"tools/openbabel/{ejecutable}" if ejecutable else None,
        "sha256": (datos.get("archivos", {}).get(ejecutable) or {}).get("sha256"),
        "procedencia": datos.get("procedencia"),
        "oferta_de_fuente": (
            "GPLv2 §3. Los artefactos de fuente correspondiente se adjuntan a "
            "cada publicación y los comprueba "
            "`scripts/verify_release_source_offer.py --check`. La licencia "
            "íntegra y las instrucciones de reconstrucción están versionadas "
            "en `tools/openbabel/`."
        ),
        "invocacion": "subproceso CLI; nunca import de Python; nunca por PATH",
    }


def construir_manifiesto(
    raiz: Path, entradas: list[tuple[str, Path]], omitidos: list[str] | None = None
) -> dict:
    """El inventario que viaja dentro del zip.

    Lleva el SHA-256 de cada archivo. Son unos megabytes de JSON dentro de un
    archivo de cientos, y es lo que permite decir «faltan 12 archivos» en vez
    de «parece que está». Sin esto, una extracción interrumpida es
    indistinguible de una completa, que es el fallo 10 del contrato.
    """
    por_componente: dict[str, Recuento] = {c.prefijo: Recuento() for c in COMPONENTES}
    archivos: dict[str, dict] = {}
    pesos_de_terceros: dict[str, Recuento] = {}
    for nombre, ruta in entradas:
        componente = validar_destino(nombre)
        tam = ruta.stat().st_size
        archivos[nombre] = {"sha256": sha256(ruta), "bytes": tam}
        recuento = por_componente[componente.prefijo]
        recuento.archivos += 1
        recuento.bytes += tam
        if nombre.lower().endswith(SUFIJOS_DE_PESO) and _es_de_una_dependencia(nombre):
            ajeno = pesos_de_terceros.setdefault(_paquete_de(nombre), Recuento())
            ajeno.archivos += 1
            ajeno.bytes += tam

    return {
        "formato": FORMATO,
        "artefacto": RUNTIME_BASE.filename,
        "version": RUNTIME_BASE.version,
        "generado_por": "scripts/build_base_archive.py",
        "python_embebido": PYTHON_EMBEBIDO,
        "componentes": [
            {
                "prefijo": c.prefijo,
                "licencia": c.licencia,
                "obligatorio": c.obligatorio,
                "descripcion": c.descripcion,
                "archivos": por_componente[c.prefijo].archivos,
                "bytes": por_componente[c.prefijo].bytes,
            }
            for c in COMPONENTES
        ],
        "open_babel": _manifiesto_openbabel(raiz),
        "no_contiene": {
            "codigo_del_repositorio": (
                "backend/, frontend/, rescoring/, scripts/ y cualquier archivo "
                "rastreado por git. Extraer este archivo no puede pisar el "
                "trabajo de nadie."
            ),
            "archivos_versionados_omitidos": sorted(omitidos or ()),
            "por_que_se_omiten": (
                "caen dentro de un destino permitido pero el repositorio ya los "
                "trae. El artefacto sólo aporta lo que el clon no tiene; "
                "incluirlos no añadiría nada y sí podría sobrescribir trabajo."
            ),
            "pesos_propios": PESOS_PROPIOS.nota,
            "bindings_de_open_babel": (
                "ni `openbabel`, ni `pybel`, ni `_openbabel`. El programa viaja "
                "en tools/openbabel/bin/ y se invoca por subproceso."
            ),
            "pesos_de_llm_y_esmfold": (
                "descargas propias, bajo demanda, con su hash en "
                "`launcher-manifest.json`."
            ),
        },
        "pesos_de_terceros_dentro_de_dependencias": {
            "por_que_estan": (
                "los publica el propio paquete de PyPI y su licencia es la de "
                "ese paquete; sin ellos la dependencia no funciona. NO son "
                "pesos de MolDesign. Se declaran aquí para que una revisión de "
                "licencias los vea sin abrir el zip."
            ),
            "por_paquete": {
                paquete: {"archivos": r.archivos, "bytes": r.bytes}
                for paquete, r in sorted(pesos_de_terceros.items())
            },
        },
        "pesos_propios": {
            "modulo": PESOS_PROPIOS.id,
            "licencia": PESOS_PROPIOS.licencia,
            "gated": PESOS_PROPIOS.gated,
            "urls": list(PESOS_PROPIOS.urls),
            "sha256": PESOS_PROPIOS.sha256,
            "nota": PESOS_PROPIOS.nota,
        },
        "archivos": archivos,
    }


def empaquetar(raiz: Path, destino: Path) -> dict:
    """Escribe el zip. Devuelve el manifiesto interno."""
    entradas, faltan, omitidos = reunir(raiz)
    if faltan:
        raise SystemExit(
            "No se puede empaquetar el runtime: faltan componentes OBLIGATORIOS.\n- "
            + "\n- ".join(faltan)
            + "\n\nAprovisiona primero:  python scripts/bootstrap_dev_tree.py --check"
        )
    if omitidos:
        print(
            f"  {len(omitidos)} archivos versionados omitidos (el repositorio ya "
            f"los trae): {', '.join(omitidos[:6])}"
            + ("…" if len(omitidos) > 6 else "")
        )

    # Poscondición, no guardia: `reunir` ya los quitó. Está aquí para que
    # quitar aquella exclusión no pase desapercibido. La guardia de verdad —la
    # que puede fallar con datos ajenos— es la del bootstrap al extraer, que
    # pregunta al índice del clon de DESTINO y no al del que empaquetó.
    rastreadas = rutas_rastreadas(raiz)
    conflictos = [n for n, _ in entradas if n in rastreadas]
    if conflictos:
        raise ArchivoRechazado(
            "ARCHIVO_RASTREADO",
            "estos archivos están versionados en git y el artefacto los "
            "sobrescribiría al extraerse:\n  - " + "\n  - ".join(conflictos[:20]),
        )

    for nombre, _ in entradas:
        validar_nombre(nombre)
        validar_destino(nombre)
        validar_contenido(nombre)

    manifiesto = construir_manifiesto(raiz, entradas, omitidos)
    cuerpo = json.dumps(manifiesto, ensure_ascii=False, indent=1, sort_keys=True)

    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        info = zipfile.ZipInfo(NOMBRE_MANIFIESTO, date_time=FECHA_FIJA)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        zf.writestr(info, cuerpo.encode("utf-8"))
        for nombre, ruta in entradas:
            info = zipfile.ZipInfo(nombre, date_time=FECHA_FIJA)
            info.compress_type = zipfile.ZIP_DEFLATED
            # Permisos fijos: los del disco varían entre máquinas y meterían
            # ruido en el hash sin describir nada del contenido.
            info.external_attr = (0o755 if nombre.endswith(".exe") else 0o644) << 16
            zf.writestr(info, ruta.read_bytes())
    return manifiesto


# ── Inspección: el verificador que el bootstrap reutiliza ────────────────


@dataclass
class Inspeccion:
    """Lo que se sabe de un artefacto tras mirarlo sin extraer nada."""

    manifiesto: dict
    nombres: list[str] = field(default_factory=list)
    bytes_declarados: int = 0

    @property
    def componentes_presentes(self) -> list[str]:
        return [c["prefijo"] for c in self.manifiesto["componentes"] if c["archivos"]]


def inspeccionar(archivo: Path) -> Inspeccion:
    """Comprueba el artefacto ENTERO antes de que se escriba un solo byte.

    Levanta `ArchivoRechazado` con un `codigo` estable. Los códigos son el
    contrato con las pruebas: si mañana cambia el mensaje, la prueba sigue
    valiendo; si cambia el código, es que cambió la regla.
    """
    if not archivo.is_file():
        raise ArchivoRechazado("AUSENTE", f"no existe {archivo}")
    if archivo.stat().st_size == 0:
        raise ArchivoRechazado("VACIO", f"{archivo.name} tiene 0 bytes")
    try:
        zf = zipfile.ZipFile(archivo)
    except zipfile.BadZipFile as error:
        raise ArchivoRechazado(
            "ZIP_ILEGIBLE",
            f"{archivo.name} no es un zip legible ({error}). Una descarga "
            "truncada llega aquí: se descarta entera, no se extrae a medias.",
        ) from error

    with zf:
        infos = zf.infolist()
        nombres = [i.filename for i in infos]
        if NOMBRE_MANIFIESTO not in nombres:
            raise ArchivoRechazado(
                "SIN_MANIFIESTO",
                f"el artefacto no trae `{NOMBRE_MANIFIESTO}`. Sin inventario no "
                "se puede distinguir una extracción completa de una a medias, "
                "así que no se extrae. `base-v1.0.0.zip` llega aquí: es de otro "
                "formato y este bootstrap no lo acepta.",
            )
        try:
            manifiesto = json.loads(zf.read(NOMBRE_MANIFIESTO).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ArchivoRechazado(
                "MANIFIESTO_ILEGIBLE", f"`{NOMBRE_MANIFIESTO}` no es JSON: {error}"
            ) from error

        if manifiesto.get("formato") != FORMATO:
            raise ArchivoRechazado(
                "FORMATO_DESCONOCIDO",
                f"el artefacto declara formato {manifiesto.get('formato')!r} y "
                f"este código sabe leer el {FORMATO}. No se intenta a medias.",
            )
        declarados = manifiesto.get("archivos")
        if not isinstance(declarados, dict) or not declarados:
            raise ArchivoRechazado(
                "MANIFIESTO_SIN_ARCHIVOS", "el inventario no declara ningún archivo"
            )

        # El inventario PRIMERO. Medido el 2026-09-06: el lector de `zipfile`
        # normaliza `\` a `/` al leer, de modo que un nombre con separador
        # invertido llega aquí ya saneado y la regla nunca se dispararía sobre
        # las entradas —`..\..\x` llega como `../../x`, que TRAVERSAL sí ve—.
        # Donde un separador de Windows SÍ sobrevive es dentro del JSON, y un
        # inventario que no es portable describe mal el archivo en Linux.
        for declarado in declarados:
            validar_nombre(declarado)
            validar_destino(declarado)
            validar_contenido(declarado)

        for info in infos:
            if info.filename == NOMBRE_MANIFIESTO:
                continue
            if _entrada_es_enlace(info):
                raise ArchivoRechazado(
                    "ENLACE",
                    f"`{info.filename}` es un enlace o un archivo especial, no un "
                    "archivo regular. Extraerlo produciría un binario falso.",
                )
            validar_nombre(info.filename)
            validar_destino(info.filename)
            validar_contenido(info.filename)

        reales = {n for n in nombres if n != NOMBRE_MANIFIESTO}
        sobran = sorted(reales - set(declarados))
        faltan = sorted(set(declarados) - reales)
        if sobran:
            raise ArchivoRechazado(
                "ENTRADA_NO_DECLARADA",
                "el zip trae archivos que su propio inventario no menciona:\n  - "
                + "\n  - ".join(sobran[:20]),
            )
        if faltan:
            raise ArchivoRechazado(
                "ARCHIVO_QUE_FALTA",
                "el inventario declara archivos que el zip no trae:\n  - "
                + "\n  - ".join(faltan[:20]),
            )
        for nombre, esperado in declarados.items():
            info = zf.getinfo(nombre)
            if info.file_size != esperado["bytes"]:
                raise ArchivoRechazado(
                    "TAMANO_DISTINTO",
                    f"`{nombre}`: el inventario dice {esperado['bytes']} bytes y "
                    f"el zip trae {info.file_size}",
                )

    total = sum(v["bytes"] for v in declarados.values())
    return Inspeccion(manifiesto=manifiesto, nombres=sorted(reales), bytes_declarados=total)


# ── AUTOTEST: buenas y deliberadamente defectuosas ───────────────────────
#
# Restricción 2 de AGENTS.md: un guardián tiene que demostrar que ve. Un
# detector nuestro quedó con un `0x08` dentro de su expresión regular, recorrió
# 167 archivos y anunció «limpio» sobre un export sucio. Esto no puede pasar en
# silencio: si una muestra defectuosa NO se rechaza, `--check` falla.


def _zip_de_prueba(destino: Path, entradas: dict[str, bytes], manifiesto: dict | None,
                   modos: dict[str, int] | None = None) -> Path:
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
        if manifiesto is not None:
            zf.writestr(NOMBRE_MANIFIESTO, json.dumps(manifiesto, ensure_ascii=False))
        for nombre, cuerpo in entradas.items():
            info = zipfile.ZipInfo(nombre, date_time=FECHA_FIJA)
            # `ZipInfo.__init__` cambia `\` por `/` en Windows, así que en esta
            # plataforma no se puede construir la muestra del separador
            # invertido por la vía normal. Se fuerza: la muestra tiene que ser
            # el archivo defectuoso de verdad, no una versión saneada de él.
            info.filename = nombre
            info.compress_type = zipfile.ZIP_DEFLATED
            if modos and nombre in modos:
                info.create_system = 3
                info.external_attr = modos[nombre] << 16
            zf.writestr(info, cuerpo)
    return destino


def _manifiesto_de_prueba(entradas: dict[str, bytes]) -> dict:
    return {
        "formato": FORMATO,
        "artefacto": RUNTIME_BASE.filename,
        "version": RUNTIME_BASE.version,
        "componentes": [
            {"prefijo": c.prefijo, "licencia": c.licencia, "obligatorio": c.obligatorio,
             "descripcion": c.descripcion, "archivos": 0, "bytes": 0}
            for c in COMPONENTES
        ],
        "archivos": {
            n: {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
            for n, b in entradas.items()
        },
    }


#: (nombre del caso, entradas, código que DEBE salir). `None` = debe pasar.
def _casos() -> list[tuple[str, dict[str, bytes], str | None, dict | None]]:
    bueno = {"python-embed/python.exe": b"MZ-de-mentira", "tools/vina/vina.exe": b"vina"}
    return [
        ("un artefacto bien formado", bueno, None, None),
        ("traversal con ../", {"../fuera.txt": b"x"}, "TRAVERSAL", None),
        ("traversal enterrado", {"python-embed/../../fuera.txt": b"x"}, "TRAVERSAL", None),
        ("ruta absoluta posix", {"/etc/passwd": b"x"}, "RUTA_ABSOLUTA", None),
        ("ruta absoluta windows", {"C:/Windows/x.dll": b"x"}, "RUTA_ABSOLUTA", None),
        ("separador invertido", {"python-embed\\x.pyd": b"x"}, "SEPARADOR_NO_PORTABLE", None),
        ("sobrescribir el backend", {"backend/api/main.py": b"x"}, "DESTINO_NO_PERMITIDO", None),
        ("sobrescribir un script", {"scripts/bundle_helper.py": b"x"}, "DESTINO_NO_PERMITIDO", None),
        ("sobrescribir el frontend", {"frontend/package.json": b"x"}, "DESTINO_NO_PERMITIDO", None),
        ("codigo de rescoring", {"rescoring/gnn_service.py": b"x"}, "DESTINO_NO_PERMITIDO", None),
        ("un peso propio", {"python-embed/gnn_v2_cl_best.pt": b"x"}, "PESO_PROPIO", None),
        ("un joblib escondido", {"tools/vina/model_a.joblib": b"x"}, "PESO_PROPIO", None),
        ("bindings de open babel",
         {"python-embed/Lib/site-packages/openbabel/__init__.py": b"x"},
         "BINDING_DE_OPEN_BABEL", None),
        ("pybel suelto",
         {"python-embed/Lib/site-packages/pybel.py": b"x"}, "BINDING_DE_OPEN_BABEL", None),
        ("la extension nativa",
         {"python-embed/Lib/site-packages/_openbabel.pyd": b"x"},
         "BINDING_DE_OPEN_BABEL", None),
        ("nombre reservado de windows", {"python-embed/nul.txt": b"x"}, "NOMBRE_RESERVADO", None),
        ("nombre con espacio final", {"python-embed/x /y.dll": b"x"}, "NOMBRE_NO_PORTABLE", None),
    ]


def autotest() -> list[str]:
    """Corre las muestras. Devuelve los fallos; lista vacía = el detector ve."""
    fallos: list[str] = []
    with tempfile.TemporaryDirectory(prefix="moldesign-autotest-") as tmp:
        carpeta = Path(tmp)
        for i, (etiqueta, entradas, esperado, _extra) in enumerate(_casos()):
            archivo = carpeta / f"caso{i}.zip"
            _zip_de_prueba(archivo, entradas, _manifiesto_de_prueba(entradas))
            try:
                inspeccionar(archivo)
                obtenido: str | None = None
            except ArchivoRechazado as error:
                obtenido = error.codigo
            if obtenido != esperado:
                fallos.append(
                    f"«{etiqueta}»: se esperaba {esperado or 'que pasara'} y "
                    f"salió {obtenido or 'que pasara'}"
                )

        # Casos que no se expresan con la tabla porque tocan la ESTRUCTURA.
        bueno = {"python-embed/python.exe": b"MZ"}
        estructurales: list[tuple[str, Path, str]] = []

        sin_manifiesto = _zip_de_prueba(carpeta / "sinman.zip", bueno, None)
        estructurales.append(("sin inventario", sin_manifiesto, "SIN_MANIFIESTO"))

        # El zip de v1.0.0 llega aquí: sin manifiesto y con `python/`.
        viejo = _zip_de_prueba(carpeta / "viejo.zip", {"python/python.exe": b"MZ"}, None)
        estructurales.append(("el formato v1.0.0", viejo, "SIN_MANIFIESTO"))

        # Un archivo que el inventario no menciona: extracción a medias al revés.
        man = _manifiesto_de_prueba(bueno)
        colado = _zip_de_prueba(
            carpeta / "colado.zip", {**bueno, "tools/vina/vina.exe": b"v"}, man
        )
        estructurales.append(("un archivo no declarado", colado, "ENTRADA_NO_DECLARADA"))

        # El inventario promete algo que no está: descarga incompleta.
        man2 = _manifiesto_de_prueba({**bueno, "tools/vina/vina.exe": b"v"})
        incompleto = _zip_de_prueba(carpeta / "incompleto.zip", bueno, man2)
        estructurales.append(("un archivo que falta", incompleto, "ARCHIVO_QUE_FALTA"))

        # Tamaño mentido: el byte cambió pero el inventario no.
        man3 = _manifiesto_de_prueba(bueno)
        man3["archivos"]["python-embed/python.exe"]["bytes"] = 999
        mentira = _zip_de_prueba(carpeta / "mentira.zip", bueno, man3)
        estructurales.append(("un tamaño mentido", mentira, "TAMANO_DISTINTO"))

        # Formato futuro: mejor negarse que adivinar.
        man4 = _manifiesto_de_prueba(bueno)
        man4["formato"] = FORMATO + 99
        futuro = _zip_de_prueba(carpeta / "futuro.zip", bueno, man4)
        estructurales.append(("un formato futuro", futuro, "FORMATO_DESCONOCIDO"))

        # Enlace simbólico disfrazado de binario.
        enlace = _zip_de_prueba(
            carpeta / "enlace.zip", {"tools/vina/vina.exe": b"/etc/passwd"},
            _manifiesto_de_prueba({"tools/vina/vina.exe": b"/etc/passwd"}),
            modos={"tools/vina/vina.exe": 0o120777},
        )
        estructurales.append(("un enlace simbólico", enlace, "ENLACE"))

        # Zip truncado: los últimos 200 bytes se pierden en la red.
        entero = carpeta / "entero.zip"
        _zip_de_prueba(entero, bueno, _manifiesto_de_prueba(bueno))
        truncado = carpeta / "truncado.zip"
        truncado.write_bytes(entero.read_bytes()[:-200])
        estructurales.append(("una descarga truncada", truncado, "ZIP_ILEGIBLE"))

        vacio = carpeta / "vacio.zip"
        vacio.write_bytes(b"")
        estructurales.append(("un archivo de 0 bytes", vacio, "VACIO"))

        estructurales.append(("un archivo que no está", carpeta / "no-existe.zip", "AUSENTE"))

        for etiqueta, archivo, esperado in estructurales:
            try:
                inspeccionar(archivo)
                obtenido = None
            except ArchivoRechazado as error:
                obtenido = error.codigo
            if obtenido != esperado:
                fallos.append(
                    f"«{etiqueta}»: se esperaba {esperado} y salió "
                    f"{obtenido or 'que pasara'}"
                )
    return fallos


# ── Informe ──────────────────────────────────────────────────────────────


def _humano(n: float) -> str:
    for unidad in ("B", "KiB", "MiB", "GiB"):
        if n < 1024 or unidad == "GiB":
            return f"{n:.2f} {unidad}" if unidad != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.2f} GiB"


def _informe_de_contenido(inspeccion: Inspeccion) -> None:
    print("\nContenido declarado:")
    for componente in inspeccion.manifiesto["componentes"]:
        marca = " " if componente["archivos"] else "!"
        print(
            f"  {marca} {componente['prefijo']:<26} "
            f"{componente['archivos']:>7} archivos  "
            f"{_humano(componente['bytes']):>10}   {componente['licencia'][:44]}"
        )
    ob = inspeccion.manifiesto.get("open_babel") or {}
    if ob.get("declarado"):
        print(
            f"\nOpen Babel: {ob.get('programa')} {ob.get('version')} "
            f"[{ob.get('licencia_spdx')}]\n"
            f"  ejecutable  {ob.get('ejecutable')}\n"
            f"  sha256      {str(ob.get('sha256'))[:32]}…\n"
            f"  invocación  {ob.get('invocacion')}"
        )
    else:
        print(f"\nOpen Babel: NO declarado — {ob.get('por_que', 'sin manifiesto')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help=("empaqueta en un TEMPORAL, comprueba el contenido, corre los "
              "autotests y borra sólo sus temporales. No toca dist/."),
    )
    parser.add_argument(
        "--inspeccionar", type=Path, default=None, metavar="ZIP",
        help="sólo mira un artefacto ya construido; no empaqueta nada",
    )
    parser.add_argument("--raiz", type=Path, default=RAIZ, help="árbol de origen")
    parser.add_argument("--salida", type=Path, default=None)
    args = parser.parse_args()

    raiz = args.raiz.resolve()
    destino_canonico = raiz / "dist" / RUNTIME_BASE.filename

    if args.inspeccionar is not None:
        try:
            inspeccion = inspeccionar(args.inspeccionar.resolve())
        except ArchivoRechazado as error:
            print(f"RECHAZADO {error}", file=sys.stderr)
            return 1
        print(f"{args.inspeccionar} — aceptado")
        print(f"  {len(inspeccion.nombres)} archivos, "
              f"{_humano(inspeccion.bytes_declarados)} sin comprimir")
        _informe_de_contenido(inspeccion)
        return 0

    if args.check:
        fallos = autotest()
        if fallos:
            print(
                "El verificador NO detecta muestras defectuosas. Hasta que esto "
                "pase, ninguna aprobación suya significa nada:\n  - "
                + "\n  - ".join(fallos),
                file=sys.stderr,
            )
            return 1
        print(f"[autotest] {len(_casos()) + 10} muestras: el verificador ve.")

        # Temporal PROPIO. Ni `dist/` ni el nombre canónico aparecen aquí: ésta
        # es exactamente la línea cuyo defecto dejó corrupto `base-v1.0.0.zip`.
        temporal = Path(tempfile.mkdtemp(prefix="moldesign-check-"))
        try:
            provisional = temporal / RUNTIME_BASE.filename
            print(f"Empaquetando en un temporal: {provisional}")
            empaquetar(raiz, provisional)
            inspeccion = inspeccionar(provisional)
            huella = sha256(provisional)
            tam = provisional.stat().st_size
            print(f"  {len(inspeccion.nombres)} archivos, "
                  f"{_humano(inspeccion.bytes_declarados)} sin comprimir")
            print(f"  bytes:  {tam}")
            print(f"  sha256: {huella}")
            _informe_de_contenido(inspeccion)

            sin_ignorar = _verificar_destinos_ignorados(raiz)
            if sin_ignorar:
                print(
                    "\nHIGIENE: `.gitignore` no cubre estos destinos por "
                    "directorio, sólo por extensión. Lo que caiga ahí sin una "
                    "extensión ignorada aparecerá como no rastreado en el "
                    "`git status` de quien clone. No afecta a la seguridad —esa "
                    "la dan los destinos permitidos y `git ls-files`—:\n  - "
                    + "\n  - ".join(sin_ignorar)
                )

            if RUNTIME_BASE.publicado:
                problemas = []
                if huella != RUNTIME_BASE.sha256:
                    problemas.append(
                        f"SHA-256 distinto:\n      declarado    {RUNTIME_BASE.sha256}"
                        f"\n      reconstruido {huella}"
                    )
                if tam != RUNTIME_BASE.size_bytes:
                    problemas.append(
                        f"tamaño: declarado {RUNTIME_BASE.size_bytes}, "
                        f"reconstruido {tam}"
                    )
                if problemas:
                    print("\nEl runtime reconstruido NO coincide con el publicado:\n  - "
                          + "\n  - ".join(problemas), file=sys.stderr)
                    return 1
                print("\nEl runtime reconstruido coincide con el publicado.")
            else:
                print(
                    f"\n`{RUNTIME_BASE.filename}` todavía no está publicado: no hay "
                    "SHA-256 declarado contra el que comparar. Eso es un estado "
                    "conocido, no un fallo — pero mientras dure, NINGÚN clon puede "
                    "aprovisionarse con `--fetch`. Los valores de arriba son los "
                    "que hay que publicar."
                )
            if destino_canonico.exists():
                print(f"\n`{destino_canonico}` sigue intacto: --check no lo toca.")
            return 0
        finally:
            # Sólo lo suyo. Nada de `dist/`.
            shutil.rmtree(temporal, ignore_errors=True)

    destino = args.salida or destino_canonico
    print(f"Empaquetando {RUNTIME_BASE.filename}…")
    empaquetar(raiz, destino)
    inspeccion = inspeccionar(destino)
    huella = sha256(destino)
    print(f"  {len(inspeccion.nombres)} archivos, "
          f"{_humano(inspeccion.bytes_declarados)} sin comprimir")
    print(f"  archivo: {destino}")
    print(f"  bytes:   {destino.stat().st_size}")
    print(f"  sha256:  {huella}")
    _informe_de_contenido(inspeccion)
    print(
        "\nPara publicarlo: sube el archivo a "
        "`hf.co/srcacahuate/moldesign-models` y añade el módulo "
        f"`{RUNTIME_BASE.id}` a `launcher-manifest.json` con estos `size_bytes` "
        "y `sha256` y la revisión inmutable resultante. El bloque exacto está "
        "en `docs/81_HANDOFF_RUNTIME_ALPHA.md`."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArchivoRechazado as error:  # noqa: B904 - mensaje, no traza
        print(f"RECHAZADO {error}", file=sys.stderr)
        raise SystemExit(1) from None
