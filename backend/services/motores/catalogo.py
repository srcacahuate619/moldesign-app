"""Catálogo de motores descargables — la fuente de verdad de qué se puede ejecutar.

MolDesign empaqueta AutoDock Vina porque cabe. Los motores de plegamiento no
caben: ESMFold son 8.4 GB de pesos. La política del producto es que esos motores
**se descargan bajo demanda** desde el repositorio de modelos y, una vez en disco,
la aplicación los usa sin volver a salir a la red.

Este módulo es el único sitio donde vive la respuesta a cuatro preguntas, y las
cuatro tienen que contestarse por separado porque fallan por separado:

1. **¿Están los archivos?** Un motor descargable sin sus archivos no es un error:
   es un motor que todavía no se instaló, y la interfaz debe poder ofrecer la
   descarga en vez de una tarjeta apagada sin explicación.
2. **¿Están las dependencias?** Los pesos sin `transformers` no cargan. Faltando
   una librería, el motor no está disponible por un motivo DISTINTO —y con una
   solución distinta— que faltando los pesos.
3. **¿Está encendido?** El motor vive en un proceso aparte. Instalado y apagado
   no es lo mismo que instalado y sirviendo.
4. **¿Qué falta exactamente?** Cada estado trae su motivo y su acción. «No
   disponible» a secas es lo que había antes, y no ayuda a nadie.

## Por qué los archivos pequeños importan tanto como los 8.4 GB

`EsmForProteinFolding.from_pretrained` necesita `config.json`, `vocab.txt`,
`tokenizer_config.json` y `special_tokens_map.json` además del tensor. Son unos
pocos KB y sin ellos el checkpoint no se puede leer. El manifiesto descargaba
sólo `pytorch_model.bin`: 8.4 GB que por sí solos no cargan.

Peor: el servicio original hacía `from_pretrained("facebook/esmfold_v1")`, es
decir, resolvía el modelo **contra la red** e ignoraba el directorio local. En un
producto que declara cero red implícita eso no puede quedarse: aquí el checkpoint
se carga del directorio instalado y con `local_files_only`.
"""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass, field
from pathlib import Path

# `backend/services/motores/catalogo.py` → raíz de la instalación.
RAIZ = Path(__file__).resolve().parents[3]


def directorios_de_busqueda() -> list[Path]:
    """Dónde puede haber quedado un módulo descargado, en orden de preferencia.

    El launcher instala bajo el directorio de recursos de la aplicación; en
    desarrollo el árbol del repositorio hace ese papel. `MOLDESIGN_RECURSOS`
    permite apuntar a otro sitio sin recompilar, que es lo que necesita una
    prueba y lo que necesitaría una instalación en otra unidad.
    """
    directorios: list[Path] = []
    override = os.getenv("MOLDESIGN_RECURSOS")
    if override:
        directorios.append(Path(override))
    directorios.append(RAIZ)
    directorios.append(Path.home() / "MolDesign")
    return directorios


@dataclass(frozen=True)
class SidecarSpec:
    """Cómo se enciende el motor. `None` cuando no hay proceso que levantar."""

    #: Carpeta del servicio dentro del árbol de la aplicación.
    paquete: str
    #: Módulo ASGI que sirve `uvicorn`.
    app: str
    #: Puerto fijo. Es parte del contrato con el cliente HTTP del backend.
    puerto: int
    #: Variable de entorno con la que se le dice dónde están los pesos.
    variable_modelo: str = "ESMFOLD_MODEL_DIR"


@dataclass(frozen=True)
class MotorDescargable:
    id: str
    etiqueta: str
    familia: str  # "docking" | "peptido"
    #: `id` del módulo en `launcher-manifest.json`. Une catálogo y descarga.
    modulo_launcher: str | None
    #: Archivos que TIENEN que existir para poder cargar el modelo. El grande y
    #: los pequeños: sin los pequeños el checkpoint no se lee.
    archivos: tuple[str, ...]
    #: Bytes de la descarga completa, para poder decirlo antes de empezar.
    bytes_descarga: int
    #: Librerías Python que el motor necesita además de las del runtime base.
    dependencias_python: tuple[str, ...]
    sidecar: SidecarSpec | None = None
    notas: tuple[str, ...] = field(default_factory=tuple)


ESMFOLD_ARCHIVOS = (
    "esmfold/models/pytorch_model.bin",
    "esmfold/models/config.json",
    "esmfold/models/vocab.txt",
    "esmfold/models/tokenizer_config.json",
    "esmfold/models/special_tokens_map.json",
)


CATALOGO: tuple[MotorDescargable, ...] = (
    MotorDescargable(
        id="esmfold",
        etiqueta="ESMFold",
        familia="peptido",
        modulo_launcher="esmfold-weights",
        archivos=ESMFOLD_ARCHIVOS,
        bytes_descarga=8442062570,
        dependencias_python=("torch", "transformers"),
        sidecar=SidecarSpec(paquete="esmfold", app="app:app", puerto=8100),
        notas=(
            # Condicion de release de `docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md`
            # El plegado y el traspaso quimico estan implementados; mientras no
            # exista un golden positivo y una cohorte de poses/repetibilidad, el
            # producto no puede presentar este camino como docking validado.
            "Pliega el peptido con ESMFold y transfiere sus coordenadas al grafo "
            "quimico del SMILES. Meeko y Vina solo se ejecutan si la identidad, "
            "los terminales y la geometria completada pasan las validaciones; "
            "si no, la corrida conserva la estructura y se abstiene.",
            "Con GPU tarda minutos; en CPU, considerablemente más.",
        ),
    ),
)

POR_ID = {m.id: m for m in CATALOGO}


def ruta_instalada(relativa: str) -> Path | None:
    """Primer directorio de búsqueda donde exista ese archivo."""
    for base in directorios_de_busqueda():
        candidato = base / relativa
        if candidato.exists() and candidato.is_file():
            return candidato
    return None


def archivos_que_faltan(motor: MotorDescargable) -> list[str]:
    return [rel for rel in motor.archivos if ruta_instalada(rel) is None]


def dependencias_que_faltan(motor: MotorDescargable) -> list[str]:
    faltan: list[str] = []
    for nombre in motor.dependencias_python:
        try:
            if importlib.util.find_spec(nombre) is None:
                faltan.append(nombre)
        except (ImportError, ValueError):
            faltan.append(nombre)
    return faltan


def directorio_del_modelo(motor: MotorDescargable) -> Path | None:
    """Carpeta que contiene el checkpoint, deducida del archivo grande.

    Es lo que se le pasa al sidecar para que cargue de disco y no de la red.
    """
    if not motor.archivos:
        return None
    grande = ruta_instalada(motor.archivos[0])
    return grande.parent if grande else None


@dataclass(frozen=True)
class EstadoMotor:
    """Lo que se puede decir hoy de un motor, con su siguiente paso."""

    id: str
    etiqueta: str
    familia: str
    #: `no_instalado` | `dependencias_faltantes` | `instalado_apagado`
    #: | `encendiendo` | `listo` | `error`
    estado: str
    disponible: bool
    motivo: str | None
    accion: str | None
    bytes_descarga: int = 0
    archivos_faltantes: tuple[str, ...] = ()
    dependencias_faltantes: tuple[str, ...] = ()
    modulo_launcher: str | None = None

    def como_dict(self) -> dict:
        return {
            "id": self.id,
            "etiqueta": self.etiqueta,
            "familia": self.familia,
            "estado": self.estado,
            "disponible": self.disponible,
            "motivo": self.motivo,
            "accion": self.accion,
            "bytes_descarga": self.bytes_descarga,
            "archivos_faltantes": list(self.archivos_faltantes),
            "dependencias_faltantes": list(self.dependencias_faltantes),
            "modulo_launcher": self.modulo_launcher,
        }


def _humano(bytes_: int) -> str:
    gb = bytes_ / 1_000_000_000
    return f"{gb:.1f} GB" if gb >= 1 else f"{bytes_ / 1_000_000:.0f} MB"


def estado_de(motor: MotorDescargable, *, encendido: bool = False,
              error: str | None = None) -> EstadoMotor:
    """El estado de un motor descargable, con su motivo y su acción.

    El orden de las comprobaciones es deliberado: primero lo que el investigador
    puede resolver descargando, después lo que exige una aplicación distinta, y
    sólo al final el encendido. Decir «no responde» a quien no ha descargado los
    pesos manda a mirar al sitio equivocado.
    """
    faltan_archivos = archivos_que_faltan(motor)
    if faltan_archivos:
        # Que falte SÓLO el archivo grande y estén los pequeños —o al revés— es
        # información: una descarga a medias no es lo mismo que no haber
        # empezado, y el aviso lo dice para que se pueda reanudar.
        parcial = len(faltan_archivos) < len(motor.archivos)
        return EstadoMotor(
            id=motor.id,
            etiqueta=motor.etiqueta,
            familia=motor.familia,
            estado="no_instalado",
            disponible=False,
            motivo=(
                f"{motor.etiqueta} no está instalado en este equipo. Son "
                f"{_humano(motor.bytes_descarga)} que se descargan una vez desde el "
                "gestor de modelos y quedan en disco."
                + (" La descarga anterior quedó incompleta." if parcial else "")
            ),
            accion="descargar",
            bytes_descarga=motor.bytes_descarga,
            archivos_faltantes=tuple(faltan_archivos),
            modulo_launcher=motor.modulo_launcher,
        )

    faltan_deps = dependencias_que_faltan(motor)
    if faltan_deps:
        return EstadoMotor(
            id=motor.id,
            etiqueta=motor.etiqueta,
            familia=motor.familia,
            estado="dependencias_faltantes",
            disponible=False,
            motivo=(
                f"Los pesos de {motor.etiqueta} están descargados, pero este runtime "
                f"no trae {', '.join(faltan_deps)}. Sin esas librerías el checkpoint "
                "no se puede cargar; hace falta una versión de la aplicación que las "
                "incluya."
            ),
            accion=None,
            dependencias_faltantes=tuple(faltan_deps),
            modulo_launcher=motor.modulo_launcher,
        )

    if error:
        return EstadoMotor(
            id=motor.id,
            etiqueta=motor.etiqueta,
            familia=motor.familia,
            estado="error",
            disponible=False,
            motivo=f"{motor.etiqueta} está instalado pero no arrancó: {error}",
            accion="reintentar",
            modulo_launcher=motor.modulo_launcher,
        )

    if encendido:
        return EstadoMotor(
            id=motor.id,
            etiqueta=motor.etiqueta,
            familia=motor.familia,
            estado="listo",
            disponible=True,
            motivo=None,
            accion=None,
            modulo_launcher=motor.modulo_launcher,
        )

    return EstadoMotor(
        id=motor.id,
        etiqueta=motor.etiqueta,
        familia=motor.familia,
        estado="instalado_apagado",
        disponible=False,
        motivo=(
            f"{motor.etiqueta} está instalado y apagado. Se enciende cuando lo pidas "
            "y ocupa memoria sólo mientras esté encendido."
        ),
        accion="encender",
        modulo_launcher=motor.modulo_launcher,
    )
