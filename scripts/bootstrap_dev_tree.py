#!/usr/bin/env python3
"""De un clon limpio a un árbol que se puede construir, sin pisar el clon.

# El bloqueo que resuelve

`git clone` no basta. El árbol necesita ~2,2 GB que **no viajan en el
repositorio** —el intérprete embebido, los motores nativos y la base sembrada—
y hasta hoy no había forma documentada de conseguirlos. Un repositorio público
del que nadie puede reconstruir el binario distribuido no se puede auditar (la
promesa se formuló cuando el proyecto era AGPL; hoy es PolyForm Noncommercial y
sigue valiendo como regla de reproducibilidad).

# El bloqueo que abrió la primera versión

Extraía el archivo base **encima del árbol**, con una sola comprobación de
traversal. Y el archivo publicado contiene copias de julio de `backend/`,
`rescoring/` y `scripts/`. Es decir: aprovisionar un clon con trabajo sin
commitear lo habría **sobrescrito en silencio**, y el aviso de daño habría
llegado por un `git status` posterior, no por este script.

Ya hay un precedente medido en este proyecto —reusar un directorio de salida
destruyó 102 resultados de RS-03-PARAM-B—, así que la regla no se discute:

> **Un aprovisionador no escribe donde no le han dicho que escriba.**

Ahora hay tres murallas, en este orden:

1. **Destinos permitidos.** Sólo las siete rutas que declara
   `build_base_archive.COMPONENTES`, ninguna de las cuales contiene código del
   producto. Cualquier otra entrada aborta el archivo entero. No se extrae «lo
   que sí vale»: un artefacto que trae algo que no debería no es un artefacto
   del que se pueda salvar la parte buena.
2. **Nada rastreado.** Se pregunta a `git ls-files` y se rechaza cualquier
   destino que git conozca, aunque estuviera en la lista de arriba.
3. **Fuera del árbol.** Se extrae a `dist/_runtime-base-staging/`, se verifica
   allí archivo a archivo contra el inventario, y sólo entonces se mueve cada
   componente a su sitio. Una interrupción deja el árbol como estaba.

# Ausente, incompleto, corrupto, completo

Seis estados distintos, porque confundirlos ya costó una tarde:

| Estado | Qué significa | Qué hacer |
|---|---|---|
| `AUSENTE` | no hay nada aprovisionado | `--fetch` |
| `AJENO` | hay piezas que no puso ningún archivo | comprobar a mano, o `--force` |
| `INCOMPLETO` | una ejecución se interrumpió | `--fetch --force` |
| `CORRUPTO` | el recibo no cuadra con lo que hay en disco | `--fetch --force` |
| `COMPLETO` | el recibo y el disco coinciden | nada |
| `DESDE_FUENTE` | reconstruido de python.org y PyPI, no de un artefacto | nada; es una vía válida |

El recibo (`python-embed/.runtime-base.json`) se escribe **al final**, cuando
todo lo demás ya está en su sitio. Mientras no exista, la instalación no está
atestiguada por nadie — que es justo la diferencia entre «terminó» y «parecía
que había terminado».

# Uso

    python scripts/bootstrap_dev_tree.py --check
    python scripts/bootstrap_dev_tree.py --check --hashes    # lento y exhaustivo
    python scripts/bootstrap_dev_tree.py --fetch
    python scripts/bootstrap_dev_tree.py --desde ARCHIVO.zip --sha256 HEX

Nada de esto necesita el intérprete embebido: corre con el Python del sistema,
porque en un clon limpio el embebido es justamente lo que no hay. Después del
aprovisionamiento, `--check` no toca la red.
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
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_base_archive import (  # noqa: E402
    COMPONENTES,
    PESOS_PROPIOS,
    PYTHON_EMBEBIDO,
    RUNTIME_BASE,
    ArchivoRechazado,
    Componente,
    consola_utf8,
    inspeccionar,
    rutas_rastreadas,
    sha256,
)

consola_utf8()


RAIZ = Path(__file__).resolve().parents[1]

#: El recibo. Vive dentro de `python-embed/`, que `.gitignore` ignora entero:
#: así el aprovisionamiento no ensucia `git status` de quien clona. Se escribe
#: EL ÚLTIMO y es la única prueba de que una instalación terminó.
NOMBRE_RECIBO = ".runtime-base.json"

#: Donde se extrae antes de mover nada. `dist/` está ignorado y está en el mismo
#: volumen que el árbol, que es lo que hace que mover sea instantáneo y atómico
#: por componente. Si este directorio existe al empezar, la ejecución anterior
#: se interrumpió: es la señal de INCOMPLETO.
STAGING = "dist/_runtime-base-staging"
APARTADO = "dist/_runtime-base-anterior"

AUSENTE, AJENO, INCOMPLETO, CORRUPTO, COMPLETO, DESDE_FUENTE = (
    "AUSENTE", "AJENO", "INCOMPLETO", "CORRUPTO", "COMPLETO", "DESDE_FUENTE"
)

#: Recibo que deja `provision_python_embed.py`. Vive junto al de los
#: artefactos porque describe lo mismo —de dónde salió este runtime— por
#: otra vía. Ver `docs/82_CLON_LIMPIO_CONSTRUIBLE.md`.
NOMBRE_RECIBO_FUENTE = ".runtime-fuente.json"


@dataclass
class Estado:
    """Lo que hay en el árbol, medido. Nunca supuesto."""

    codigo: str
    detalle: str = ""
    recibo: dict | None = None
    componentes_presentes: list[str] = field(default_factory=list)
    componentes_ausentes: list[str] = field(default_factory=list)
    faltan_obligatorios: list[str] = field(default_factory=list)
    discrepancias: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def utilizable(self) -> bool:
        return self.codigo == COMPLETO and not self.faltan_obligatorios


def _ruta(raiz: Path, componente: Componente) -> Path:
    return raiz / componente.prefijo.rstrip("/")


def _presente(raiz: Path, componente: Componente) -> bool:
    """Presente = su sonda está. NO «el directorio existe y tiene algo dentro».

    Medido en un clon limpio: `tools/llama/` trae `README.md` y `SHA256SUM.txt`
    versionados, así que la comprobación por directorio no vacío daba OK sobre
    un directorio sin un solo binario. Un informe que dice que está lo que no
    está es peor que no tener informe.
    """
    destino = _ruta(raiz, componente)
    if componente.es_archivo:
        return destino.is_file()
    if not destino.is_dir():
        return False
    if not componente.sondas:
        return any(destino.iterdir())
    return any((destino / sonda).is_file() for sonda in componente.sondas)


def leer_recibo(raiz: Path) -> dict | None:
    ruta = raiz / "python-embed" / NOMBRE_RECIBO
    if not ruta.is_file():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _recibo_de_fuente(raiz: Path) -> dict | None:
    """El recibo de `provision_python_embed.py`, si esa fue la vía."""
    ruta = raiz / "python-embed" / NOMBRE_RECIBO_FUENTE
    if not ruta.is_file():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def medir(raiz: Path, con_hashes: bool = False) -> Estado:
    """El estado del árbol. Esta función no escribe nada y no toca la red."""
    presentes = [c.prefijo for c in COMPONENTES if _presente(raiz, c)]
    ausentes = [c.prefijo for c in COMPONENTES if c.prefijo not in presentes]
    faltan_obligatorios = [
        c.prefijo for c in COMPONENTES if c.obligatorio and c.prefijo not in presentes
    ]
    avisos: list[str] = []

    version = _version_del_interprete(raiz)
    if version and not version.startswith(PYTHON_EMBEBIDO):
        avisos.append(
            f"`python-embed` es CPython {version} y el runtime distribuido es "
            f"{PYTHON_EMBEBIDO}. El bytecode precompilado del bundle lleva el "
            "número mágico de otra versión y se ignora en silencio: el arranque "
            "en la máquina del investigador se recompilaría entero."
        )
    if not (raiz / "backend" / "requirements-embed.lock.txt").is_file():
        avisos.append(
            "Falta `backend/requirements-embed.lock.txt`, la única lista exacta "
            "de lo que hay dentro del runtime distribuido. "
            "`python scripts/lock_embedded_runtime.py` la escribe."
        )

    interrumpido = (raiz / STAGING).is_dir()
    recibo = leer_recibo(raiz)

    if interrumpido:
        return Estado(
            INCOMPLETO,
            f"quedó `{STAGING}` de una ejecución anterior: se interrumpió a "
            "medias. Nada de lo que hay ahí se ha movido al árbol.",
            recibo, presentes, ausentes, faltan_obligatorios, [], avisos,
        )

    if recibo is None:
        if not presentes:
            return Estado(
                AUSENTE, "no hay ninguna pieza del runtime en el árbol.",
                None, presentes, ausentes, faltan_obligatorios, [], avisos,
            )
        # La otra procedencia legítima: `provision_python_embed.py`, que
        # reconstruye el intérprete desde python.org y PyPI cuando el artefacto
        # no está publicado. Deja su propio recibo, y llamar AJENO a eso sería
        # tratar la única vía documentada como si fuera un accidente.
        fuente = _recibo_de_fuente(raiz)
        if fuente is not None:
            return Estado(
                DESDE_FUENTE,
                "el intérprete se reconstruyó desde "
                f"{fuente.get('via', 'python.org + PyPI')}, no desde un "
                "artefacto empaquetado. Es una procedencia válida y distinta: "
                "reproduce la lista exacta del lockfile, no los bytes.",
                fuente, presentes, ausentes, faltan_obligatorios, [], avisos,
            )
        return Estado(
            AJENO,
            "hay piezas del runtime que no puso ningún artefacto: no existe "
            f"`python-embed/{NOMBRE_RECIBO}`. Puede ser un aprovisionamiento "
            "manual legítimo, o una ejecución interrumpida. No se puede "
            "distinguir desde aquí, así que no se afirma que esté bien.",
            None, presentes, ausentes, faltan_obligatorios, [], avisos,
        )

    declarados = (recibo.get("manifiesto") or {}).get("archivos") or {}
    discrepancias: list[str] = []
    retirados = 0
    for nombre, esperado in declarados.items():
        if _esta_retirado(nombre):
            retirados += 1
            continue
        destino = raiz / nombre
        if not destino.is_file():
            discrepancias.append(f"falta   {nombre}")
            continue
        real = destino.stat().st_size
        if real != esperado["bytes"]:
            discrepancias.append(
                f"tamaño  {nombre}: recibo {esperado['bytes']}, disco {real}"
            )
        elif con_hashes and sha256(destino) != esperado["sha256"]:
            discrepancias.append(f"sha256  {nombre}")
        if len(discrepancias) >= 40:
            discrepancias.append("… (se corta a 40; hay más)")
            break

    if discrepancias:
        return Estado(
            CORRUPTO,
            f"el recibo describe {len(declarados)} archivos y el disco no "
            "coincide. Esto NO es «falta algo»: es que lo que hay no es lo que "
            "el artefacto dice haber puesto.",
            recibo, presentes, ausentes, faltan_obligatorios, discrepancias, avisos,
        )

    return Estado(
        COMPLETO,
        f"{len(declarados)} archivos, verificados por "
        + ("SHA-256" if con_hashes else "tamaño"),
        recibo, presentes, ausentes, faltan_obligatorios, [], avisos,
    )


def _version_del_interprete(raiz: Path) -> str | None:
    """Pregunta al intérprete embebido, por RUTA ABSOLUTA.

    Nunca `python` a secas: en una máquina con otro intérprete en el `PATH`, la
    respuesta describiría a un desconocido. Es la misma regla que la frontera de
    Open Babel aplica a `obabel` (doc 79), por la misma razón.
    """
    exe = raiz / "python-embed" / "python.exe"
    if not exe.is_file():
        exe = raiz / "python-embed" / "bin" / "python3"
    if not exe.is_file():
        return None
    try:
        proceso = subprocess.run(
            [str(exe), "-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proceso.stdout.strip() if proceso.returncode == 0 else None


# ── Descarga ─────────────────────────────────────────────────────────────


def descargar(url: str, destino: Path, esperado: str, bytes_esperados: int) -> None:
    """Descarga y verifica. Un archivo que no coincide se borra, no se guarda.

    Guardar una descarga que no cuadra invita a «reintentar reanudando», y una
    reanudación sobre bytes de otro archivo produce un zip que se abre, se
    extrae y está mal. Se descarta entero.
    """
    print(f"Descargando {destino.name} ({bytes_esperados / (1024 ** 3):.2f} GiB)…")
    ultimo = -1

    def progreso(bloques: int, tam: int, total: int) -> None:
        nonlocal ultimo
        if total <= 0:
            return
        pct = min(100, int(bloques * tam * 100 / total))
        if pct >= ultimo + 5:
            ultimo = pct
            print(f"  {pct:3d}%", flush=True)

    urllib.request.urlretrieve(url, destino, reporthook=progreso)  # noqa: S310

    real_bytes = destino.stat().st_size
    if real_bytes != bytes_esperados:
        destino.unlink(missing_ok=True)
        raise SystemExit(
            "La descarga está INCOMPLETA (o el servidor entregó otra cosa).\n"
            f"  esperados  {bytes_esperados} bytes\n"
            f"  recibidos  {real_bytes}\n"
            "Se descarta. Un archivo a medias que se extrae produce una "
            "instalación que parece válida y no lo es."
        )
    real = sha256(destino)
    if real != esperado:
        destino.unlink(missing_ok=True)
        raise SystemExit(
            "El archivo descargado NO es el declarado.\n"
            f"  esperado  {esperado}\n  obtenido  {real}\n"
            "Se descarta. Un runtime que el manifiesto describe mal es peor que "
            "ningún runtime: todo lo que se construya con él llevará una "
            "procedencia falsa."
        )
    print(f"  SHA-256 verificado: {real[:16]}…")


# ── Extracción ───────────────────────────────────────────────────────────


# ── Retiradas deliberadas del runtime base ─────────────────────────────────
#
# El recibo describe lo que el artefacto `runtime-base-v1.1.0.zip` PUSO, y eso
# no se edita: mentiria sobre el archivo. Pero el arbol puede apartarse de el a
# proposito, y entonces "falta" es una respuesta equivocada.
#
# Unico caso hasta ahora: `padelpy` venia en el runtime base con
# `PaDEL-Descriptor.jar` bajo AGPL-3.0, declarado MIT por el metadata del
# wrapper y sin que ningun modulo lo importara. Se retiro el 2026-09-12 en vez de
# asumir la obligacion. Ver `scripts/check_copyleft_en_runtime.py` y
# `frontend/public/legal/THIRD_PARTY_NOTICES.md`.
#
# Cuando se republique el runtime base sin estos ficheros, esta lista se vacia y
# el recibo nuevo vuelve a describir el arbol entero.
RETIRADOS_A_PROPOSITO: tuple[str, ...] = (
    # AGPL-3.0 sin declarar y sin usar. Ver check_copyleft_en_runtime.py.
    "python-embed/Lib/site-packages/padelpy/",
    "python-embed/Lib/site-packages/padelpy-",
    # Lanzadores de script de otra arquitectura dentro de un paquete x64: seis
    # de x86 y cuatro de ARM64. `distlib` compone el nombre en ejecucion como
    # '%s%s%s.exe' % (kind, bits, sufijo), y con este interprete -calcsize('P')
    # == 8, get_platform() == 'win-amd64'- eso solo puede dar t64/w64. Los de
    # setuptools no los referencia ningun fichero del runtime: easy_install, que
    # era quien los usaba, ya no existe en esta version. Se conservan cli-64,
    # gui-64, t64 y w64, que son los alcanzables.
    "python-embed/Lib/site-packages/setuptools/cli-32.exe",
    "python-embed/Lib/site-packages/setuptools/cli-arm64.exe",
    "python-embed/Lib/site-packages/setuptools/cli.exe",
    "python-embed/Lib/site-packages/setuptools/gui-32.exe",
    "python-embed/Lib/site-packages/setuptools/gui-arm64.exe",
    "python-embed/Lib/site-packages/setuptools/gui.exe",
    "python-embed/Lib/site-packages/pip/_vendor/distlib/t32.exe",
    "python-embed/Lib/site-packages/pip/_vendor/distlib/t64-arm.exe",
    "python-embed/Lib/site-packages/pip/_vendor/distlib/w32.exe",
    "python-embed/Lib/site-packages/pip/_vendor/distlib/w64-arm.exe",
)


def _esta_retirado(nombre: str) -> bool:
    ruta = nombre.replace(chr(92), "/")
    return any(ruta.startswith(p) for p in RETIRADOS_A_PROPOSITO)


def _comprobar_destinos(raiz: Path, nombres: list[str]) -> None:
    """La segunda muralla: nada rastreado por git, aunque esté permitido."""
    rastreadas = rutas_rastreadas(raiz)
    if not rastreadas:
        print(
            "  AVISO: no se pudo consultar `git ls-files` (¿no es un clon, o no "
            "hay git?). La comprobación contra archivos versionados NO se hizo; "
            "queda sólo la lista de destinos permitidos."
        )
        return
    conflictos = sorted(n for n in nombres if n in rastreadas)
    if conflictos:
        raise ArchivoRechazado(
            "SOBRESCRIBIRIA_RASTREADO",
            "el artefacto sobrescribiría archivos que git versiona. Se aborta "
            "sin escribir nada:\n  - " + "\n  - ".join(conflictos[:20]),
        )
    print(f"  ninguno de los {len(nombres)} destinos está versionado en git")


def extraer(raiz: Path, archivo: Path, forzar: bool) -> dict:
    """Extrae a un staging, verifica allí, y sólo entonces mueve. Devuelve el
    manifiesto interno del artefacto."""
    inspeccion = inspeccionar(archivo)          # primera muralla
    nombres = inspeccion.nombres
    _comprobar_destinos(raiz, nombres)          # segunda muralla

    staging = raiz / STAGING
    if staging.exists():
        if not forzar:
            raise SystemExit(
                f"Existe `{STAGING}`: una ejecución anterior se interrumpió. "
                "Revísalo y bórralo, o repite con --force."
            )
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    declarados = inspeccion.manifiesto["archivos"]
    print(f"Extrayendo {len(nombres)} archivos a `{STAGING}`…")
    with zipfile.ZipFile(archivo) as zf:
        for nombre in nombres:
            destino = staging / nombre
            # Ya validado por `inspeccionar`, pero la comprobación es barata y
            # es la última línea antes de escribir: se repite a propósito.
            if not destino.resolve().is_relative_to(staging.resolve()):
                raise ArchivoRechazado("TRAVERSAL", f"fuera del staging: {nombre}")
            destino.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(nombre) as origen, destino.open("wb") as salida:
                shutil.copyfileobj(origen, salida, 1024 * 1024)

    print("Verificando lo extraído contra el inventario, archivo a archivo…")
    malos: list[str] = []
    for nombre, esperado in declarados.items():
        ruta = staging / nombre
        if not ruta.is_file():
            malos.append(f"falta {nombre}")
        elif ruta.stat().st_size != esperado["bytes"]:
            malos.append(f"tamaño {nombre}")
        elif sha256(ruta) != esperado["sha256"]:
            malos.append(f"sha256 {nombre}")
    if malos:
        shutil.rmtree(staging, ignore_errors=True)
        raise ArchivoRechazado(
            "EXTRACCION_INCOMPLETA",
            "lo extraído no coincide con el inventario del propio archivo:\n  - "
            + "\n  - ".join(malos[:20])
            + "\nSe borra el staging. El árbol no se ha tocado.",
        )
    print(f"  {len(declarados)} archivos verificados por SHA-256")

    _mover_componentes(raiz, staging, forzar)
    shutil.rmtree(staging, ignore_errors=True)
    return inspeccion.manifiesto


def _incorporar_rastreados(raiz: Path, staging: Path, componente: Componente) -> None:
    """Conserva los archivos que el clon ya trae dentro de un componente.

    El artefacto los omite para no sobrescribir codigo o documentacion de Git,
    pero el intercambio se hace por directorio completo. Sin esta copia al
    staging, reemplazar `tools/llama/` borraria su README, suma y `.gitkeep`.
    """
    prefijo = componente.prefijo.rstrip("/")
    for relativa in sorted(rutas_rastreadas(raiz)):
        if relativa != prefijo and not relativa.startswith(prefijo + "/"):
            continue
        actual = raiz / relativa
        if not actual.is_file():
            continue
        provisional = staging / relativa
        if provisional.exists():
            raise ArchivoRechazado(
                "DESTINO_VERSIONADO",
                f"el artefacto intenta reemplazar `{relativa}`",
            )
        provisional.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(actual, provisional)


def _solo_rastreados(raiz: Path, destino: Path) -> bool:
    """`True` si `destino` no contiene nada que git no conozca (o está vacío)."""
    if destino.is_file():
        return destino.relative_to(raiz).as_posix() in rutas_rastreadas(raiz)
    rastreadas = rutas_rastreadas(raiz)
    return all(p.relative_to(raiz).as_posix() in rastreadas
               for p in destino.rglob("*") if p.is_file())


def _mover_componentes(raiz: Path, staging: Path, forzar: bool) -> None:
    """Mueve cada componente entero. Nada se borra: lo anterior se aparta."""
    ejecutable = Path(sys.executable).resolve()
    zonas_gestionadas = [raiz / APARTADO, raiz / STAGING]
    zonas_gestionadas += [
        _ruta(raiz, componente)
        for componente in COMPONENTES
        if not componente.es_archivo
    ]
    if any(ejecutable.is_relative_to(zona.resolve()) for zona in zonas_gestionadas):
        raise SystemExit(
            "El intérprete que ejecuta el bootstrap está dentro de una ruta que "
            "se va a reemplazar. Usa Python del sistema u otro intérprete externo."
        )
    apartado = raiz / APARTADO
    for componente in COMPONENTES:
        origen = _ruta(staging, componente)
        if not origen.exists():
            continue
        destino = _ruta(raiz, componente)
        _incorporar_rastreados(raiz, staging, componente)
        if destino.exists():
            # Un clon recién hecho ya trae `tools/llama/` con tres ficheros
            # VERSIONADOS (.gitkeep, README.md, SHA256SUM.txt). Se acaban de copiar
            # al staging, así que sustituir la carpeta no pierde nada. Hasta el
            # 2026-09-24 esto exigía --force y un fork no podía aprovisionarse:
            # --fetch se quedaba a medias (INCOMPLETO). Sólo se exige permiso si
            # hay algo que git no conoce.
            if not forzar and not _solo_rastreados(raiz, destino):
                raise SystemExit(
                    f"`{componente.prefijo}` ya existe en el árbol y este "
                    "artefacto no lo puso. No se sobrescribe nada sin permiso "
                    "explícito: comprueba qué hay ahí, y repite con --force si "
                    "quieres reemplazarlo."
                )
            apartado.mkdir(parents=True, exist_ok=True)
            reserva = apartado / componente.prefijo.rstrip("/").replace("/", "__")
            if reserva.exists():
                shutil.rmtree(reserva, ignore_errors=True)
                reserva.unlink(missing_ok=True)
            print(f"  apartando  {componente.prefijo} → {APARTADO}/{reserva.name}")
            os.replace(destino, reserva)
        destino.parent.mkdir(parents=True, exist_ok=True)
        os.replace(origen, destino)
        print(f"  colocado   {componente.prefijo}")


def escribir_recibo(raiz: Path, manifiesto: dict, huella: str | None) -> Path:
    """El recibo, lo último. Determinista: dos ejecuciones lo escriben igual.

    No lleva reloj a propósito. Una marca de tiempo haría que dos
    aprovisionamientos del mismo archivo produjeran inventarios distintos, y
    entonces «el mismo inventario» dejaría de poder comprobarse.
    """
    ruta = raiz / "python-embed" / NOMBRE_RECIBO
    ruta.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = {
        "formato": manifiesto["formato"],
        "artefacto": manifiesto["artefacto"],
        "version": manifiesto["version"],
        "sha256_del_archivo": huella,
        "manifiesto": manifiesto,
    }
    ruta.write_text(
        json.dumps(cuerpo, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    return ruta


# ── Open Babel: se comprueba, no se supone ───────────────────────────────


def verificar_open_babel(raiz: Path) -> tuple[bool, str]:
    """El binario extraído contra el manifiesto VERSIONADO del repositorio.

    El manifiesto no viaja en el zip a propósito: si viajara, un artefacto
    manipulado traería su propio hash y coincidiría consigo mismo. La referencia
    tiene que venir de fuera del archivo que se está comprobando.
    """
    manifiesto = raiz / "tools" / "openbabel" / "openbabel-manifest.json"
    if not manifiesto.is_file():
        return False, "falta `tools/openbabel/openbabel-manifest.json` en el clon"
    datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    relativa = datos.get("ejecutable")
    esperado = (datos.get("archivos", {}).get(relativa) or {}).get("sha256")
    if not relativa or not esperado:
        return False, "el manifiesto de Open Babel no declara ejecutable y hash"
    binario = raiz / "tools" / "openbabel" / relativa
    if not binario.is_file():
        return False, f"falta el binario `tools/openbabel/{relativa}`"
    real = sha256(binario)
    if real != esperado:
        return False, (
            f"`{relativa}` no es el declarado:\n      manifiesto {esperado}\n"
            f"      disco      {real}"
        )
    return True, f"{relativa} coincide con su manifiesto ({real[:16]}…)"


# ── Informe ──────────────────────────────────────────────────────────────


def imprimir(estado: Estado, raiz: Path) -> int:
    print(f"Árbol: {raiz}")
    print(f"Estado del runtime: {estado.codigo}")
    print(f"  {estado.detalle}\n")

    for componente in COMPONENTES:
        marca = "OK   " if componente.prefijo in estado.componentes_presentes else (
            "FALTA" if componente.obligatorio else "falta"
        )
        print(f"  {marca}  {componente.prefijo:<26} {componente.descripcion[:60]}")
    print()

    if estado.discrepancias:
        print("El recibo y el disco no coinciden:")
        for linea in estado.discrepancias:
            print(f"  {linea}")
        print()

    ok_ob, detalle_ob = verificar_open_babel(raiz)
    print(f"Open Babel: {'OK' if ok_ob else 'NO'} — {detalle_ob}")

    # Hasta el 2026-09-23 este aviso decía que los pesos propios «no vienen» y
    # que su origen estaba «SIN PUBLICAR». Los que usa el producto (clasificador
    # XGBoost, model_a_*, CL-GNN gnn_v2_cl_best.pt) están VERSIONADOS en
    # rescoring/artifacts/ bajo LICENSE-MODELS y los trae el propio clon; lo que
    # no está publicado es el módulo opcional de checkpoints antiguos.
    print(
        "\nPesos propios: los que usa el producto vienen con el clon, en rescoring/artifacts/\n"
        f"  licencia: {PESOS_PROPIOS.licencia}; se verifican con\n"
        "  python rescoring/scripts/generate_model_manifest.py --check\n"
        f"  El módulo opcional «{PESOS_PROPIOS.id}» (checkpoints antiguos) no está publicado y no hace falta."
    )

    for aviso in estado.avisos:
        print(f"\nAVISO: {aviso}")

    if estado.faltan_obligatorios:
        print("\nBLOQUEA la construcción del instalador: faltan " +
              ", ".join(estado.faltan_obligatorios))
    if estado.codigo != COMPLETO:
        if RUNTIME_BASE.publicado:
            print(f"\nPara aprovisionar:  python {Path(__file__).name} --fetch")
        else:
            print(
                f"\n`{RUNTIME_BASE.filename}` NO está publicado todavía: no hay "
                "SHA-256 declarado, así que `--fetch` se niega a descargar. "
                "Un clon limpio no puede aprovisionarse hasta que se publique. "
                "Ver docs/81_HANDOFF_RUNTIME_ALPHA.md."
            )
        return 1

    print("\nEl árbol está completo y atestiguado por su recibo.")
    return 0


# ── Órdenes ──────────────────────────────────────────────────────────────


def aprovisionar(raiz: Path, desde: Path | None, sha_declarado: str | None,
                 forzar: bool) -> int:
    estado = medir(raiz)
    if estado.codigo == COMPLETO and not forzar:
        recibo = estado.recibo or {}
        print(
            f"Ya aprovisionado con `{recibo.get('artefacto')}` "
            f"v{recibo.get('version')}. No se hace nada.\n"
            "Repetir esto es idempotente por diseño: si quieres rehacerlo, "
            "--force."
        )
        return imprimir(medir(raiz), raiz)
    if estado.codigo in (AJENO, INCOMPLETO, CORRUPTO, DESDE_FUENTE) and not forzar:
        print(f"Estado {estado.codigo}: {estado.detalle}", file=sys.stderr)
        print(
            "No se sobrescribe nada sin permiso explícito. Revisa lo que hay y "
            "repite con --force si quieres reemplazarlo.",
            file=sys.stderr,
        )
        return 1

    # Un --sha256 explícito manda: quien reconstruye su propio runtime con
    # build_base_archive.py y lo pasa con --desde declara él mismo qué espera.
    # Sin él, se verifica contra el publicado. Nunca se extrae sin un hash.
    esperado = sha_declarado or RUNTIME_BASE.sha256

    if desde is not None:
        archivo = desde.resolve()
        if not archivo.is_file():
            raise SystemExit(f"No existe {archivo}")
        if not esperado:
            raise SystemExit(
                "Un archivo local también se verifica antes de extraerse. "
                f"`{RUNTIME_BASE.filename}` no tiene SHA-256 declarado todavía, "
                "así que pasa el suyo con --sha256 HEX. Sin eso no hay nada "
                "contra lo que comprobar, y «se veía bien» no es una verificación."
            )
        real = sha256(archivo)
        if real != esperado:
            raise SystemExit(
                f"El archivo local NO coincide.\n  esperado  {esperado}\n"
                f"  obtenido  {real}\nNo se extrae."
            )
        print(f"Archivo local verificado: {real[:16]}…")
        manifiesto = extraer(raiz, archivo, forzar)
        escribir_recibo(raiz, manifiesto, real)
    else:
        if not RUNTIME_BASE.publicado:
            print(
                f"`{RUNTIME_BASE.filename}` no está publicado: "
                f"urls={'sí' if RUNTIME_BASE.urls else 'no'}, "
                f"sha256={'sí' if RUNTIME_BASE.sha256 else 'NO'}.\n"
                "Descargar sin hash declarado sería confiar en la red, que es "
                "exactamente lo que este script existe para no hacer.\n"
                "Mientras tanto: --desde ARCHIVO.zip --sha256 HEX.",
                file=sys.stderr,
            )
            return 1
        with tempfile.TemporaryDirectory(prefix="moldesign-runtime-") as tmp:
            archivo = Path(tmp) / RUNTIME_BASE.filename
            descargar(
                RUNTIME_BASE.urls[0], archivo,
                RUNTIME_BASE.sha256, int(RUNTIME_BASE.size_bytes or 0),
            )
            manifiesto = extraer(raiz, archivo, forzar)
            escribir_recibo(raiz, manifiesto, RUNTIME_BASE.sha256)

    print("\nSe vuelve a medir el árbol, en vez de dar el archivo por bueno:\n")
    return imprimir(medir(raiz), raiz)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--check", action="store_true", help="mide y no escribe nada")
    grupo.add_argument("--fetch", action="store_true", help="descarga y aprovisiona")
    parser.add_argument("--desde", type=Path, default=None, metavar="ZIP",
                        help="aprovisiona desde un archivo local ya descargado")
    parser.add_argument("--sha256", default=None,
                        help="SHA-256 esperado del archivo local")
    parser.add_argument("--hashes", action="store_true",
                        help="con --check: verifica cada archivo por SHA-256 (lento)")
    parser.add_argument("--force", action="store_true",
                        help="reemplaza lo que ya haya, apartándolo antes")
    parser.add_argument("--raiz", type=Path, default=RAIZ)
    args = parser.parse_args()

    raiz = args.raiz.resolve()
    if args.check:
        if args.desde is not None:
            print("`--desde` sólo tiene sentido con --fetch.", file=sys.stderr)
            return 2
        return imprimir(medir(raiz, con_hashes=args.hashes), raiz)
    return aprovisionar(raiz, args.desde, args.sha256, args.force)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArchivoRechazado as error:
        print(f"RECHAZADO {error}", file=sys.stderr)
        print("\nEl árbol NO se ha modificado.", file=sys.stderr)
        raise SystemExit(1) from None
