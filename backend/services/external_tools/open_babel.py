r"""Adaptador único de Open Babel. La ÚNICA puerta de producción hacia `obabel`.

# La frontera que este archivo implementa

Open Babel es un **programa independiente bajo GPL-2.0-only**. MolDesign es una
obra separada bajo PolyForm Noncommercial 1.0.0. Viajan en el mismo instalador, pero no forman
una sola obra: MolDesign no enlaza con Open Babel, no importa sus bindings de
Python y no carga `_openbabel.pyd`. Lo ejecuta como una herramienta de línea de
órdenes y se comunica con él por archivos.

```text
MolDesign / Python (PolyForm Noncommercial 1.0.0)
        │  contrato explícito de subprocess
        ▼
    obabel.exe (GPL-2.0-only, programa independiente)
        │  archivos moleculares de entrada y salida
        ▼
    SDF validado antes de aceptarse
```

Que esa frontera sea real y no una intención lo comprueban
`scripts/check_openbabel_boundary.py` (nueve guardas del build) y, en pruebas,
`test_adaptador_open_babel.py`, `test_fallback_open_babel.py` y
`test_guarda_frontera_open_babel.py`. Este módulo es el lado ejecutable de la
misma decisión; el porqué está en `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

# Por qué NO se resuelve por PATH

Porque un binario ajeno encontrado en el `PATH` del usuario produciría un
resultado que el informe atribuiría a la versión declarada en el manifiesto, y
eso es una mentira de procedencia. Ya hubo un caso vivo en este árbol: invocar
`"obabel"` a secas resolvía a `python/Scripts/obabel.exe`, un lanzador generado
por pip con la ruta del intérprete de la máquina de construcción incrustada, que
en el equipo del usuario no existía.

Aquí sólo se ejecuta el ejecutable **empaquetado**, verificado contra su hash.
No hay respaldo a `"obabel"`, no se mira `shutil.which`, y la ausencia no se
degrada a «no disponible»: se declara.

# Estados

`AVAILABLE` · `MISSING` · `HASH_MISMATCH` · `EXECUTION_FAILED` · `INVALID_OUTPUT`

`MISSING` y `HASH_MISMATCH` describen una **instalación dañada**, no una función
opcional: Open Babel viaja en el instalador, así que su ausencia significa que
alguien borró o alteró parte del producto.
"""

from __future__ import annotations

import asyncio
import enum
import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from utils.logger import get_logger
from utils.procesos import BANDERAS_SIN_VENTANA

log = get_logger(__name__)

# ── Dónde vive el programa ───────────────────────────────────────────────
#
# Una sola expresión sirve para el árbol de desarrollo y para el runtime
# instalado, porque las dos jerarquías tienen la misma forma:
#
#   <repo>/backend/services/external_tools/open_babel.py  ->  <repo>/tools/openbabel
#   <res>/backend/services/external_tools/open_babel.py   ->  <res>/tools/openbabel
#
# `parents[3]` es la raíz en ambos casos. Que dev y bundle resuelvan por la
# MISMA regla es lo que permite afirmar que se probó lo que se entrega.
_RAIZ = Path(__file__).resolve().parents[3]

#: Permite apuntar a otra copia sin recompilar. Lo usan el verificador del
#: bundle, el smoke de producción y las pruebas de instalación dañada. No es un
#: respaldo: si apunta a algo que no existe, el estado es `MISSING`.
VARIABLE_DE_ENTORNO = "MOLDESIGN_OPENBABEL_DIR"

NOMBRE_MANIFIESTO = "openbabel-manifest.json"

#: Segundos. Una conversión de una pose tarda decenas de milisegundos; treinta
#: segundos sólo se agotan si el proceso se quedó colgado.
TIMEOUT_CONVERSION_S = 30.0
TIMEOUT_VERSION_S = 15.0

#: Título que llevará cada molécula del SDF convertido. Ver el comentario del
#: argumento `--title` en `convertir_pdbqt_a_sdf`: sin fijarlo, el título es la
#: ruta absoluta del temporal de entrada y viaja dentro del archivo entregado.
TITULO_DE_LA_POSE = "vina_pose"


class EstadoOpenBabel(str, enum.Enum):
    """Resultado tipado y auditable de mirar o ejecutar Open Babel."""

    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    HASH_MISMATCH = "HASH_MISMATCH"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    INVALID_OUTPUT = "INVALID_OUTPUT"


class OpenBabelNoDisponible(RuntimeError):
    """Open Babel no se puede usar, y se dice por qué en vez de continuar."""

    def __init__(self, estado: EstadoOpenBabel, detalle: str) -> None:
        self.estado = estado
        self.detalle = detalle
        super().__init__(f"{estado.value}: {detalle}")


@dataclass(frozen=True)
class DisponibilidadOpenBabel:
    """Lo que se puede afirmar del programa sin ejecutar una conversión."""

    estado: EstadoOpenBabel
    detalle: str
    #: Ruta RELATIVA a la raíz del bundle o del repositorio. La absoluta es un
    #: detalle del disco de quien corre, no evidencia; ya hubo un manifiesto en
    #: este árbol que describía el disco de quien lo generó.
    ruta_relativa: str | None = None
    sha256: str | None = None
    version_declarada: str | None = None
    version_reportada: str | None = None
    licencia_spdx: str | None = None
    procedencia: dict = field(default_factory=dict)

    @property
    def disponible(self) -> bool:
        return self.estado is EstadoOpenBabel.AVAILABLE

    def como_dict(self) -> dict:
        return {
            "estado": self.estado.value,
            "detalle": self.detalle,
            "ruta_relativa": self.ruta_relativa,
            "sha256": self.sha256,
            "version_declarada": self.version_declarada,
            "version_reportada": self.version_reportada,
            "licencia_spdx": self.licencia_spdx,
            "procedencia": self.procedencia,
        }


@dataclass(frozen=True)
class ConversionOpenBabel:
    """Lo que produjo una conversión, con todo lo necesario para auditarla."""

    contenido: str
    #: Los mismos campos que `DisponibilidadOpenBabel`, congelados en el momento
    #: de ejecutar: un informe posterior no debe volver a preguntarle al disco.
    ruta_relativa: str
    sha256: str
    version_declarada: str
    licencia_spdx: str
    argumentos: list[str]
    returncode: int
    stdout: str
    stderr: str


def directorio_de_la_herramienta() -> Path:
    """Dónde debe estar Open Babel. No comprueba que esté."""
    desde_entorno = os.environ.get(VARIABLE_DE_ENTORNO, "").strip()
    if desde_entorno:
        return Path(desde_entorno)
    return _RAIZ / "tools" / "openbabel"


def _sha256(ruta: Path) -> str:
    digest = hashlib.sha256()
    with ruta.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)
    return digest.hexdigest()


#: Prefijo con el que se publica cualquier ruta de esta herramienta. Es la
#: ubicación canónica dentro del bundle y del repositorio.
UBICACION_CANONICA = "tools/openbabel"


def _ruta_relativa(ruta: Path) -> str:
    """Ruta publicable: relativa al directorio de la herramienta, con su prefijo.

    Nunca sale una ruta absoluta. Aunque `MOLDESIGN_OPENBABEL_DIR` apunte a un
    directorio temporal de una prueba, lo que se publica sigue siendo
    `tools/openbabel/bin/obabel.exe`: la ubicación en el disco de quien corre no
    es evidencia, y ya hubo en este árbol un manifiesto que describía el disco
    de quien lo generó.
    """
    base = directorio_de_la_herramienta()
    try:
        cola = ruta.resolve().relative_to(base.resolve()).as_posix()
    except (ValueError, OSError):
        return f"{UBICACION_CANONICA}/{ruta.name}"
    return f"{UBICACION_CANONICA}/{cola}" if cola != "." else UBICACION_CANONICA


#: Caché de `obabel -V`, indexada por (ruta, hash). Un proceso por instalación.
#:
#: POR QUÉ. `/health` se consulta repetidamente —el supervisor de Tauri lo sondea
#: durante el arranque— y lanzar un proceso en cada consulta es coste y parpadeo
#: de consola por un dato que no puede cambiar.
#:
#: POR QUÉ LA CLAVE LLEVA EL HASH. Porque el hash SÍ se recalcula en cada
#: llamada. Si alguien reemplaza el binario, la clave cambia y la versión se
#: vuelve a preguntar: la caché acelera el caso normal sin poder afirmar nada
#: sobre un archivo que ya no es el mismo.
_VERSION_CACHEADA: dict[tuple[str, str], tuple[int | None, str, str]] = {}


def _version_del_binario(exe: Path, sha256_actual: str) -> tuple[int | None, str, str]:
    """(código de salida, versión reportada, error). Código `None` = no arrancó."""
    clave = (str(exe), sha256_actual)
    if clave in _VERSION_CACHEADA:
        return _VERSION_CACHEADA[clave]
    try:
        proceso = subprocess.run(
            [str(exe), "-V"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_VERSION_S,
            creationflags=BANDERAS_SIN_VENTANA,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        resultado = (None, "", f"{type(exc).__name__}: {exc}")
    else:
        reportada = ((proceso.stdout or "") + (proceso.stderr or "")).strip()
        resultado = (
            proceso.returncode,
            reportada,
            (proceso.stderr or proceso.stdout or "").strip(),
        )
    # Se registra el lanzamiento, no el resultado cacheado: así el log dice
    # cuántas VECES se gastó un proceso, que es el dato que hace falta si algún
    # día esto aparece en un perfil de arranque.
    log.debug(
        "open_babel_version_consultada",
        codigo=resultado[0],
        reportada=resultado[1][:60],
    )
    _VERSION_CACHEADA[clave] = resultado
    return resultado


def estado_actual(*, verificar_version: bool = False) -> DisponibilidadOpenBabel:
    """Mira el disco y contesta qué se puede afirmar de Open Babel.

    Con `verificar_version=True` ejecuta además `obabel -V`, que es la única
    forma de comprobar que el binario no sólo está sino que arranca. Cuesta un
    proceso, así que el preflight lo pide y la pantalla de estado también, pero
    el camino caliente de una conversión no.
    """
    base = directorio_de_la_herramienta()
    manifiesto_path = base / NOMBRE_MANIFIESTO
    if not manifiesto_path.is_file():
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.MISSING,
            detalle=(
                f"No existe el manifiesto de Open Babel en {_ruta_relativa(manifiesto_path)}. "
                "Open Babel viaja en el instalador: su ausencia indica una instalación "
                "dañada o incompleta, no una función opcional."
            ),
            ruta_relativa=_ruta_relativa(manifiesto_path),
        )
    try:
        manifiesto = json.loads(manifiesto_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.MISSING,
            detalle=f"El manifiesto de Open Babel no se puede leer: {exc}",
            ruta_relativa=_ruta_relativa(manifiesto_path),
        )

    licencia = manifiesto.get("licencia_spdx")
    version_declarada = manifiesto.get("version_paquete")
    version_esperada_binario = manifiesto.get("version_reportada_por_el_binario")
    procedencia = manifiesto.get("procedencia", {})
    relativa_exe = manifiesto.get("ejecutable", "bin/obabel.exe")
    exe = base / relativa_exe
    comun = {
        "version_declarada": version_declarada,
        "licencia_spdx": licencia,
        "procedencia": procedencia,
        "ruta_relativa": _ruta_relativa(exe),
    }

    if not exe.is_file():
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.MISSING,
            detalle=(
                f"Falta el ejecutable empaquetado de Open Babel ({_ruta_relativa(exe)}). "
                "No se busca en el PATH a propósito: un binario ajeno produciría un "
                "resultado que el informe atribuiría a la versión declarada."
            ),
            **comun,
        )

    esperado = (manifiesto.get("archivos") or {}).get(relativa_exe, {}).get("sha256")
    real = _sha256(exe)
    if esperado and real != esperado:
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.HASH_MISMATCH,
            detalle=(
                f"El ejecutable de Open Babel no coincide con su manifiesto "
                f"(esperado {esperado[:12]}…, encontrado {real[:12]}…). "
                "No se ejecuta: el programa que correría no es el declarado."
            ),
            sha256=real,
            **comun,
        )

    if not verificar_version:
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.AVAILABLE,
            detalle="Open Babel empaquetado presente y con el hash declarado.",
            sha256=real,
            **comun,
        )

    codigo, reportada, error = _version_del_binario(exe, real)
    if codigo is None:
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.EXECUTION_FAILED,
            detalle=f"El ejecutable de Open Babel está pero no arranca: {error}",
            sha256=real,
            **comun,
        )
    if codigo != 0:
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.EXECUTION_FAILED,
            detalle=f"`obabel -V` terminó con código {codigo}: {error[-400:]}",
            sha256=real,
            version_reportada=reportada or None,
            **comun,
        )
    if version_esperada_binario and version_esperada_binario not in reportada:
        return DisponibilidadOpenBabel(
            estado=EstadoOpenBabel.EXECUTION_FAILED,
            detalle=(
                f"El binario contesta {reportada!r}, que no contiene la versión "
                f"declarada {version_esperada_binario!r}. El manifiesto describe "
                "un programa distinto del que hay en disco."
            ),
            sha256=real,
            version_reportada=reportada or None,
            **comun,
        )

    return DisponibilidadOpenBabel(
        estado=EstadoOpenBabel.AVAILABLE,
        detalle=f"Open Babel empaquetado disponible y verificado ({reportada}).",
        sha256=real,
        version_reportada=reportada or None,
        **comun,
    )


def _exigir_disponible() -> tuple[Path, DisponibilidadOpenBabel]:
    disponibilidad = estado_actual()
    if not disponibilidad.disponible:
        raise OpenBabelNoDisponible(disponibilidad.estado, disponibilidad.detalle)
    base = directorio_de_la_herramienta()
    manifiesto = json.loads((base / NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    return base / manifiesto.get("ejecutable", "bin/obabel.exe"), disponibilidad


def sdf_es_valido(texto: str) -> bool:
    """Un SDF utilizable: bloque de conexión V2000/V3000 y terminador.

    Es deliberadamente estructural y no químico. Rechazar aquí un SDF por
    razones químicas escondería el fallo real —Open Babel produjo algo que no es
    un SDF— detrás de un diagnóstico equivocado.
    """
    if not texto or "$$$$" not in texto:
        return False
    if "V2000" not in texto and "V3000" not in texto:
        return False
    # El bloque de conteo declara al menos un átomo.
    for linea in texto.splitlines():
        if "V2000" in linea or "V3000" in linea:
            try:
                return int(linea[:3]) > 0 if "V2000" in linea else True
            except ValueError:
                return "V3000" in linea
    return False


async def convertir_pdbqt_a_sdf(
    pdbqt: str,
    *,
    timeout_s: float = TIMEOUT_CONVERSION_S,
) -> ConversionOpenBabel:
    """PDBQT → SDF con el Open Babel empaquetado. Valida antes de devolver.

    Lanza `OpenBabelNoDisponible` con el estado tipado si el programa falta,
    su hash no coincide, la ejecución falla o el archivo producido no es un SDF
    utilizable. **No devuelve nada aproximado**: quien llama decide qué hacer
    con la ausencia, y en producción esa decisión no es continuar en silencio.
    """
    exe, disponibilidad = _exigir_disponible()

    # `ignore_cleanup_errors`: en Windows el antivirus puede tener abierto lo
    # recién escrito y un PermissionError al limpiar tiraría una conversión que
    # ya terminó bien. Dejar un temporal suelto es mejor que perder el trabajo.
    with tempfile.TemporaryDirectory(
        prefix="moldesign-obabel-", ignore_cleanup_errors=True
    ) as tmp:
        entrada = Path(tmp) / "pose.pdbqt"
        salida = Path(tmp) / "pose.sdf"
        entrada.write_text(pdbqt, encoding="utf-8")

        argumentos = [
            str(exe),
            "-ipdbqt",
            str(entrada),
            "-osdf",
            "-O",
            str(salida),
            # ── POR QUÉ SE FIJA EL TÍTULO ────────────────────────────────
            #
            # Sin esto, Open Babel usa el nombre del archivo de entrada como
            # título de la molécula, y el archivo de entrada es un temporal:
            # el SDF salía con
            #
            #     C:\Users\<usuario>\AppData\Local\Temp\moldesign-obabel-1m9e_hvu\pose.pdbqt
            #
            # como primera línea de CADA pose. Ese archivo se entrega. Es decir,
            # el artefacto llevaría la ruta absoluta del disco de quien corrió
            # —y su nombre de usuario— dentro de la evidencia estructural, y
            # además cambiaría en cada ejecución, rompiendo la comparación byte
            # a byte de dos corridas equivalentes.
            "--title",
            TITULO_DE_LA_POSE,
        ]
        try:
            proceso = await asyncio.create_subprocess_exec(
                *argumentos,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=BANDERAS_SIN_VENTANA,
            )
        except OSError as exc:
            raise OpenBabelNoDisponible(
                EstadoOpenBabel.EXECUTION_FAILED,
                f"No se pudo lanzar Open Babel ({_ruta_relativa(exe)}): {exc}",
            ) from exc

        try:
            salida_b, error_b = await asyncio.wait_for(
                proceso.communicate(), timeout=timeout_s
            )
        except asyncio.TimeoutError as exc:
            proceso.kill()
            await proceso.wait()
            raise OpenBabelNoDisponible(
                EstadoOpenBabel.EXECUTION_FAILED,
                f"Open Babel excedió el timeout de {timeout_s:g} s convirtiendo PDBQT→SDF.",
            ) from exc

        stdout = salida_b.decode("utf-8", errors="replace")
        stderr = error_b.decode("utf-8", errors="replace")

        if proceso.returncode != 0:
            raise OpenBabelNoDisponible(
                EstadoOpenBabel.EXECUTION_FAILED,
                f"Open Babel terminó con código {proceso.returncode}: "
                f"{(stderr or stdout)[-600:]}",
            )
        if not salida.is_file():
            raise OpenBabelNoDisponible(
                EstadoOpenBabel.INVALID_OUTPUT,
                "Open Babel terminó con éxito pero no escribió el SDF de salida.",
            )
        contenido = salida.read_text(encoding="utf-8", errors="replace")

    if not sdf_es_valido(contenido):
        raise OpenBabelNoDisponible(
            EstadoOpenBabel.INVALID_OUTPUT,
            "El archivo que produjo Open Babel no es un SDF utilizable "
            "(sin bloque V2000/V3000 con átomos o sin terminador `$$$$`).",
        )

    return ConversionOpenBabel(
        contenido=contenido,
        ruta_relativa=disponibilidad.ruta_relativa or _ruta_relativa(exe),
        sha256=disponibilidad.sha256 or "",
        version_declarada=disponibilidad.version_declarada or "",
        licencia_spdx=disponibilidad.licencia_spdx or "",
        argumentos=[Path(argumentos[0]).name, *argumentos[1:]],
        returncode=int(proceso.returncode or 0),
        stdout=stdout,
        stderr=stderr,
    )
