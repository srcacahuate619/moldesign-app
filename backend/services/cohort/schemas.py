"""
Contrato de la comprobación previa de cohortes, v1.

# Qué es una cohorte v1

**Un receptor. Una configuración. Muchas moléculas.** Esa es toda la definición,
y es lo que hace comparables entre sí a las filas. El Batch histórico acepta
`ALL` y mezcla receptores en una misma tabla; dos filas de esa tabla no son
comparables y presentarlas juntas sugiere que sí lo son.

Por eso el contrato NO admite:

    · `pdb_id = ALL`
    · varios receptores (estructuralmente imposible: hay un solo objeto)
    · configuración por fila
    · campos desconocidos (`extra="forbid"`)
    · valores no finitos (NaN, ±Infinity)
    · parámetros fuera de los límites que el producto ya maneja

# Por qué la configuración es OBLIGATORIA

`docking_engine`, `exhaustiveness` y `num_poses` no tienen valor por defecto en
este contrato, aunque el producto tenga los suyos. Una cohorte identificada por
un fingerprint que incluye un valor que nadie declaró es una cohorte cuya
identidad cambia el día que cambie el ajuste por defecto. Aquí se declara o no
se ejecuta.

# Workers no entra

El número de trabajadores es una propiedad OPERACIONAL: cambia cuánto tarda,
no qué se calcula. Ponerlo en la identidad científica haría que la misma
cohorte, ejecutada en un portátil y en una estación, pareciera dos cohortes
distintas.
"""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from services.cohort.taxonomy import ControlRole, Decision, Eligibility

#: Versión del CONTRATO de la comprobación previa de cohortes.
COHORT_PREFLIGHT_SCHEMA_VERSION = 1

#: Motores admitidos en cohorte v1. Es una lista blanca a propósito: aceptar un
#: motor arbitrario aquí sólo aplaza el fallo hasta la ejecución de 5B, cuando
#: ya haya 300 moléculas en marcha.
COHORT_DOCKING_ENGINES = ("vina", "qvina2")

#: Límite de filas. Es el mismo que ya aplica el Batch histórico: no se inventa
#: una capacidad que el producto no ha demostrado.
MAX_COHORT_ROWS = 500

#: Techo del archivo. Un archivo mayor no llega a parsearse.
MAX_COHORT_FILE_BYTES = 8 * 1024 * 1024

#: Límites declarados de la caja. No son física: son el rango dentro del cual
#: este contrato acepta una caja declarada a mano.
MAX_GRID_COORDINATE = 1000.0
MAX_GRID_SIDE = 100.0

_PDB_ID = re.compile(r"^[A-Z0-9_-]{4,10}$")

#: Flotante que no puede ser NaN ni ±Infinity. `json.loads` acepta esos
#: literales por defecto y `1e400` se convierte en `inf` sin ningún literal, así
#: que el rechazo tiene que estar también en el tipo, no sólo en el parser.
Finite = Annotated[float, Field(allow_inf_nan=False)]
Triple = tuple[Finite, Finite, Finite]


class _Base(BaseModel):
    """Base común: nada desconocido entra ni sale."""

    model_config = ConfigDict(extra="forbid")


# ── Entrada ──────────────────────────────────────────────────────────


class CohortReceptor(_Base):
    """
    El receptor único de la cohorte.

    Que sea un objeto y no una lista es la restricción, no un detalle de
    serialización: no hay forma de expresar dos receptores en una cohorte v1.
    """

    #: `min_length` es 1, no 4, A PROPÓSITO. Con 4, `ALL` se rechazaba por
    #: «cadena demasiado corta» y quien viniera del Batch histórico —donde
    #: `target_pdb_id=ALL` es una opción legítima— leería un error de longitud
    #: en vez de la razón real: que `ALL` no define una cohorte comparable.
    pdb_id: str = Field(min_length=1, max_length=10)
    chain: str | None = Field(default=None, max_length=4)

    @field_validator("pdb_id")
    @classmethod
    def _receptor_unico_y_valido(cls, value: str) -> str:
        limpio = value.strip().upper()
        if limpio == "ALL":
            raise ValueError(
                "`ALL` no es un receptor. Una cohorte compara moléculas entre sí bajo un "
                "mismo receptor; ejecutarla contra todos produce filas que no son "
                "comparables aunque compartan tabla."
            )
        if not _PDB_ID.match(limpio):
            raise ValueError(
                "`pdb_id` debe ser un identificador único de 4 a 10 caracteres "
                "([A-Z0-9_-]). Una lista de receptores no define una cohorte v1."
            )
        return limpio

    @field_validator("chain")
    @classmethod
    def _cadena_normalizada(cls, value: str | None) -> str | None:
        if value is None:
            return None
        limpio = value.strip().upper()
        return limpio or None


class CohortConfig(_Base):
    """
    La configuración científica COMÚN. Se aplica idéntica a todas las filas.

    `grid_center` y `grid_size` son opcionales porque el producto sabe derivar
    la caja del receptor. Omitirlos declara «derívala»; enviarlos declara «ésta
    y no otra». Lo que NO se admite es el centinela `(0,0,0)`: un lado de cero
    no es una caja, y aceptarlo dejaría el fingerprint identificando una caja
    inexistente.
    """

    grid_center: Triple | None = None
    grid_size: Triple | None = None
    docking_engine: Literal["vina", "qvina2"]
    exhaustiveness: int = Field(ge=1, le=128)
    num_poses: int = Field(ge=1, le=20)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)

    @field_validator("grid_center")
    @classmethod
    def _centro_en_rango(cls, value: Triple | None) -> Triple | None:
        if value is None:
            return None
        for coordenada in value:
            if abs(coordenada) > MAX_GRID_COORDINATE:
                raise ValueError(
                    f"`grid_center` fuera de rango: |{coordenada}| > {MAX_GRID_COORDINATE} Å."
                )
        return tuple(round(float(v), 3) for v in value)  # type: ignore[return-value]

    @field_validator("grid_size")
    @classmethod
    def _lado_utilizable(cls, value: Triple | None) -> Triple | None:
        if value is None:
            return None
        for lado in value:
            if lado <= 0:
                raise ValueError(
                    "`grid_size` debe tener los tres lados positivos. Para que la caja se "
                    "derive del receptor, OMITE `grid_size`; no envíes (0,0,0)."
                )
            if lado > MAX_GRID_SIDE:
                raise ValueError(f"`grid_size` fuera de rango: {lado} > {MAX_GRID_SIDE} Å.")
        return tuple(round(float(v), 3) for v in value)  # type: ignore[return-value]


class CohortStudy(_Base):
    """
    Definición científica compartida de la cohorte.

    Es lo ÚNICO que el cliente declara además del archivo. No lleva rutas, ni
    usuario, ni número de trabajadores, ni nada que dependa de la máquina.
    """

    schema_version: Literal[1] = COHORT_PREFLIGHT_SCHEMA_VERSION
    name: str = Field(min_length=1, max_length=300)
    receptor: CohortReceptor
    config: CohortConfig

    @model_validator(mode="after")
    def _nombre_normalizado(self) -> "CohortStudy":
        limpio = self.name.strip()
        if not limpio:
            raise ValueError("`name` no puede quedar vacío tras recortar espacios.")
        object.__setattr__(self, "name", limpio)
        return self


# ── Salida ───────────────────────────────────────────────────────────


class CohortRow(_Base):
    """
    Una fila del archivo, conservada pase lo que pase.

    NADA se descarta. Un SMILES vacío, uno ilegible, un duplicado o una
    etiqueta inválida siguen siendo una fila con su `row_index`: si
    desaparecieran, el total dejaría de corresponder al archivo que la persona
    subió y la cobertura mediría sobre un denominador falso.
    """

    #: Índice de fila de DATOS, base 0, en el orden del archivo. No es el número
    #: de línea del fichero: la cabecera no cuenta y un SDF no tiene líneas.
    row_index: int = Field(ge=0)
    source_name: str | None = None
    #: Lo que traía la celda, tal cual (recortado). Cadena vacía si no traía nada.
    input_smiles: str
    #: Canónico de RDKit. Presente en cuanto la estructura se puede LEER, aunque
    #: después el validador la rechace: es lo que permite ver de qué molécula se
    #: está hablando y detectar duplicados.
    canonical_smiles: str | None = None
    eligibility: Eligibility
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    active_label: bool | None = None
    control_role: ControlRole = "none"
    #: Primera fila con el mismo canónico. `None` si esta es la primera.
    duplicate_of_row: int | None = Field(default=None, ge=0)


class CohortSummary(_Base):
    """
    Recuentos de la cohorte. Todos con denominador explícito o derivables de él.

    `unique_canonical_ligands` cuenta canónicos DISTINTOS entre filas elegibles:
    es cuántas moléculas distintas entrarían de verdad en la corrida.

    `duplicate_rows` cuenta filas que repiten un canónico ya visto, sobre todas
    las filas que tienen canónico (una fila inadmisible sigue siendo la misma
    molécula que otra).

    Los recuentos de control cuentan roles declarados **en filas elegibles**:
    un control que no puede ejecutarse no es un control disponible, y contarlo
    haría creer que la cohorte tiene una referencia que nunca va a correr.
    """

    total_rows: int = Field(ge=0)
    eligible_rows: int = Field(ge=0)
    invalid_rows: int = Field(ge=0)
    unique_canonical_ligands: int = Field(ge=0)
    duplicate_rows: int = Field(ge=0)
    explicit_reference_controls: int = Field(ge=0)
    explicit_positive_controls: int = Field(ge=0)
    explicit_negative_controls: int = Field(ge=0)
    #: `eligible_rows / total_rows`. **`null` cuando no hay denominador**: sin
    #: filas no hay cobertura que medir, y `0.0` afirmaría un 0 % medido sobre
    #: nada. Nunca es NaN ni ±Infinity — no serían JSON válido.
    input_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    #: El denominador, dicho en voz alta. Una cobertura sin denominador es un
    #: porcentaje sin población.
    input_coverage_denominator: int = Field(ge=0)


class CohortPreflightResult(_Base):
    """
    Resultado de la comprobación previa. No ejecuta nada y no guarda nada.

    Superar esta comprobación **no predice unión, actividad ni calidad
    farmacológica**. Dice una cosa mucho más pequeña y mucho más comprobable:
    que estas entradas se pueden leer y que esta configuración se puede
    aplicar a todas por igual.
    """

    schema_version: Literal[1] = COHORT_PREFLIGHT_SCHEMA_VERSION
    #: ISO 8601 UTC. **No entra en el fingerprint**: si entrara, la misma
    #: cohorte tendría una identidad distinta cada vez que se comprueba.
    generated_at: str
    cohort_fingerprint: str
    normalized_study: CohortStudy
    decision: Decision
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: CohortSummary
    rows: list[CohortRow] = Field(default_factory=list)


# ── Cohorte persistida ───────────────────────────────────────────────
#
# La diferencia con lo de arriba es toda la diferencia de este sprint:
#
#   `CohortPreflightResult`  es un DICTAMEN. Se calcula, se enseña y se tira.
#   `CohortRecord`           es un REGISTRO. Se congela y sobrevive al reinicio.
#
# Un dictamen se puede repetir cuando quieras y siempre da lo mismo mientras el
# archivo, el estudio y la versión del validador no cambien. Un registro tiene
# que seguir diciendo lo mismo aunque las tres cosas cambien, porque es lo que
# alguien aceptó.

#: Único estado posible en 5B. La ejecución de 5C añadirá los suyos; el
#: vocabulario vive aquí y no en un Enum de la DB, que no ganaría nada con un
#: solo valor y obligaría a una migración para añadir el segundo.
COHORT_STATUS_READY = "ready"
COHORT_STATUSES = (COHORT_STATUS_READY,)

#: Forma exigida a `expected_fingerprint`. Se comprueba ANTES de leer el
#: archivo: una huella con otra forma no puede coincidir con ninguna que este
#: producto emita, y descubrirlo después de canonicalizar 500 moléculas es
#: trabajo tirado.
FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class CohortProvenance(_Base):
    """
    Con qué se congeló esta cohorte.

    **Lo ausente se omite, no se inventa.** Si no se puede leer la versión de
    RDKit, el campo no viaja: un `"desconocida"` escrito a mano se leería
    después como un dato, y la procedencia existe justamente para poder
    distinguir «esto es lo que había» de «esto es lo que supusimos».
    """

    #: Versión del contrato de comprobación previa (`CohortPreflightResult`).
    preflight_contract_version: int
    #: Etiqueta del contrato de canonicalización del fingerprint.
    fingerprint_contract: str
    moldesign_version: str | None = None
    rdkit_version: str | None = None
    #: ISO 8601 UTC del instante en que se congeló.
    created_at: str


class CohortSourceFile(_Base):
    """El archivo que definió la cohorte, descrito sin entregarlo."""

    #: Nombre BASE y saneado. Nunca una ruta: ni la del equipo de quien subió el
    #: archivo, ni la del disco donde vive la base de datos.
    filename: str
    content_type: str | None = None
    sha256: str
    size_bytes: int = Field(ge=0)


class CohortListItem(_Base):
    """
    Una cohorte en el listado. **Sin filas y sin archivo.**

    No es una decisión de tamaño de respuesta: es que el listado responde a
    «¿qué cohortes tengo?», y contestarlo con 500 filas por cohorte convierte
    una pregunta de orientación en una descarga.
    """

    id: uuid.UUID
    name: str
    status: str
    cohort_fingerprint: str
    #: Para orientarse en el listado sin abrir cada cohorte.
    receptor_pdb_id: str
    docking_engine: str
    created_at: str
    source: CohortSourceFile
    #: Los recuentos, que sí son un resumen. Las filas no.
    summary: CohortSummary


class CohortRecord(_Base):
    """
    La cohorte completa: definición, snapshot, resumen y filas.

    Los cuatro están, y **una sola vez**: `preflight` es el dictamen congelado
    entero, así que la definición es `preflight.normalized_study`, el resumen es
    `preflight.summary` y las filas son `preflight.rows`. Repetirlos en el nivel
    superior daría tres copias del mismo dato que podrían divergir el día que
    alguien edite una.

    Lo que NO lleva son los bytes del archivo. Se guardan —y su SHA-256 se
    publica aquí para que se puedan cotejar—, pero entregarlos es otra
    operación, no un efecto secundario de mirar una cohorte.
    """

    id: uuid.UUID
    schema_version: int
    name: str
    status: str
    cohort_fingerprint: str
    created_at: str
    source: CohortSourceFile
    provenance: CohortProvenance
    #: El veredicto tal como se le enseñó a quien aceptó la cohorte: filas
    #: inválidas y duplicadas incluidas, cobertura incluida, avisos incluidos.
    preflight: CohortPreflightResult
