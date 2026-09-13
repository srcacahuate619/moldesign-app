"""
Contrato de entrada del dossier: la proyección del caso.

# Qué entra y qué no

El caso vive en el cliente (`case.json`). El backend no lo lee ni lo quiere
entero: recibe una **proyección** con lo justo para redactar el dossier, y
recupera por su cuenta todo lo científico —molécula, resultado, target, poses—
desde sus propias fuentes.

Esa separación no es ceremonia. Si el resultado científico llegara desde el
cliente, cualquiera podría dictar el contenido del dossier con una petición
HTTP, y el documento dejaría de ser evidencia de lo que se ejecutó para pasar a
ser evidencia de lo que alguien escribió.

# Lo que se rechaza por construcción

    · rutas absolutas del equipo (`C:\\Users\\…`, `/home/…`, UNC)
    · `storage.path` y cualquier ubicación local del caso
    · campos desconocidos (`extra="forbid"`)
    · secretos: claves, tokens, configuración de proveedores
    · resultados científicos suministrados por el cliente

Las rutas se rechazan en un validador compartido en vez de filtrarse al
imprimir: un filtro de salida hay que acordarse de aplicarlo en cada sitio, y
basta olvidarlo una vez para publicar el nombre de usuario de alguien dentro de
un PDF que va a circular.

# Versionado

`projection_version` es del CONTRATO, no del caso. `case_schema_version` viaja
aparte porque son cosas distintas: un caso v3 puede proyectarse con la v1 de
este contrato, y este contrato tiene que poder cambiar sin migrar `case.json`.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Versión del contrato de proyección. Subir sólo con nota de compatibilidad.
PROJECTION_VERSION = 1

#: Formas de ruta local que no pueden aparecer en NINGÚN texto de la proyección.
#: Se mira la forma, no la existencia: un `D:\Users\…` es igual de identificable
#: exista o no en esta máquina.
_PATRONES_RUTA = (
    re.compile(r"^[A-Za-z]:[\\/]"),        # C:\... o C:/...
    re.compile(r"^\\\\"),                   # UNC \\servidor\recurso
    re.compile(r"^/(?:home|Users|root|var|tmp|mnt|media)/"),
    re.compile(r"(?:^|[\s\"'])\.\.[\\/]"),  # traversal
)

#: Nombres que delatan un secreto. Se rechazan como CLAVE de cualquier objeto
#: libre que aceptemos, no por su valor: un token no se reconoce mirándolo.
_CLAVES_PROHIBIDAS = {
    "api_key", "apikey", "token", "access_token", "refresh_token", "secret",
    "password", "passwd", "authorization", "bearer", "private_key",
    "openai_api_key", "anthropic_api_key", "provider_config",
}


def _sin_ruta_local(valor: str | None, campo: str) -> str | None:
    """Rechaza cualquier texto con forma de ruta local. Devuelve el valor tal cual."""
    if valor is None:
        return None
    for patron in _PATRONES_RUTA:
        if patron.search(valor):
            raise ValueError(
                f"`{campo}` contiene una ruta local. El dossier no acepta rutas del "
                "equipo del usuario: acabarían impresas en un documento que circula."
            )
    return valor


class _Base(BaseModel):
    """Base común: prohíbe campos desconocidos en todo el contrato."""

    model_config = ConfigDict(extra="forbid")


class ContextoCientifico(_Base):
    """
    Las preguntas del caso. TODAS opcionales a propósito.

    Un hueco es información: el dossier lo imprime como `NO DEFINIDO` en vez de
    omitir el apartado. Omitirlo dejaría al lector sin saber si nadie preguntó o
    si nadie contestó.
    """

    study_kind: str | None = Field(default=None, max_length=64)
    question: str | None = Field(default=None, max_length=4000)
    decision: str | None = Field(default=None, max_length=4000)
    system_rationale: str | None = Field(default=None, max_length=4000)
    controls: str | None = Field(default=None, max_length=4000)
    assumptions: str | None = Field(default=None, max_length=4000)
    uncertainties: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)

    @field_validator("*")
    @classmethod
    def _prohibir_rutas(cls, v: str | None, info) -> str | None:
        return _sin_ruta_local(v, f"context.{info.field_name}")


class ReceptorDeclarado(_Base):
    """Receptor tal como lo declaró el caso. La verdad la tiene el backend."""

    pdb_id: str = Field(min_length=1, max_length=16)
    chain: str | None = Field(default=None, max_length=8)
    origin: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=200)
    target_id: str | None = Field(default=None, max_length=64)

    @field_validator("name", "origin")
    @classmethod
    def _prohibir_rutas(cls, v: str | None, info) -> str | None:
        return _sin_ruta_local(v, f"inputs.receptor.{info.field_name}")


class LigandoDeclarado(_Base):
    """
    Lo que la persona escribió y el canónico que devolvió el validador.

    Se conservan los dos. El dossier tiene que poder decir «escribiste esto, se
    acopló esto otro»: sustituir uno por otro borra una transformación real.
    """

    input_smiles: str = Field(min_length=1, max_length=4000)
    canonical_smiles: str | None = Field(default=None, max_length=4000)
    name: str | None = Field(default=None, max_length=200)


class ConfiguracionDeclarada(_Base):
    """Caja, motor y parámetros que el preflight inspeccionó."""

    grid_center: tuple[float, float, float] | None = None
    grid_size: tuple[float, float, float] | None = None
    custom_hotspots: list[Annotated[str, Field(max_length=64)]] = Field(default_factory=list, max_length=200)
    docking_engine: str | None = Field(default=None, max_length=32)
    exhaustiveness: int | None = Field(default=None, ge=1, le=1024)
    num_poses: int | None = Field(default=None, ge=1, le=100)
    seed: int | None = None
    pipeline_config: dict[str, object] | None = None


class PreflightDeclarado(_Base):
    """
    Resumen del preflight que autorizó la corrida.

    Es lo que el caso guardó, no un informe nuevo: el dossier no vuelve a
    inspeccionar nada. Si el resumen y la corrida no encajan, se declara — no se
    recalcula para tapar la discrepancia.
    """

    fingerprint: str = Field(min_length=8, max_length=200)
    generated_at: str | None = Field(default=None, max_length=64)
    schema_version: int | None = None
    execution_route: str | None = Field(default=None, max_length=64)
    blockers: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=100)
    warnings: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=100)
    not_evaluated: list[Annotated[str, Field(max_length=80)]] = Field(default_factory=list, max_length=100)
    receptor_label: str | None = Field(default=None, max_length=200)
    ligand_label: str | None = Field(default=None, max_length=4000)
    grid_label: str | None = Field(default=None, max_length=200)


class CorridaDeclarada(_Base):
    """Identidad de la corrida según el caso. El backend la contrasta."""

    task_id: str = Field(min_length=1, max_length=128)
    input_fingerprint: str | None = Field(default=None, max_length=200)
    execution_state: str | None = Field(default=None, max_length=32)
    started_at: str | None = Field(default=None, max_length=64)
    last_error: str | None = Field(default=None, max_length=2000)

    @field_validator("last_error")
    @classmethod
    def _prohibir_rutas(cls, v: str | None) -> str | None:
        return _sin_ruta_local(v, "run.last_error")


class DecisionHumana(_Base):
    """
    Una persona vio una advertencia y siguió adelante.

    Atada a su fingerprint: reconocer algo sobre unos inputs no dice nada sobre
    otros. El dossier imprime la huella junto a la decisión para que se vea a
    qué hipótesis aplicaba.
    """

    control_code: str = Field(min_length=1, max_length=80)
    fingerprint: str = Field(min_length=1, max_length=200)
    decision: Literal["reconocida"] = "reconocida"
    at: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=2000)

    @field_validator("note")
    @classmethod
    def _prohibir_rutas(cls, v: str | None) -> str | None:
        return _sin_ruta_local(v, "decisions[].note")


class DisposicionDeclarada(_Base):
    """Cierre científico del caso, separado de acuses de controles."""

    kind: Literal["accept", "limit", "abstain"]
    rationale: str = Field(min_length=3, max_length=4000)
    fingerprint: str = Field(min_length=1, max_length=200)
    at: str | None = Field(default=None, max_length=64)

    @field_validator("rationale")
    @classmethod
    def _prohibir_rutas(cls, v: str) -> str:
        return _sin_ruta_local(v, "disposition.rationale") or v


class InputsDeclarados(_Base):
    receptor: ReceptorDeclarado | None = None
    ligand: LigandoDeclarado | None = None
    config: ConfiguracionDeclarada | None = None


class CaseProjection(_Base):
    """
    Proyección del caso: TODO lo que el backend acepta del cliente.

    Nótese lo que NO está: `storage`, rutas, poses, afinidades, scores. Lo
    científico lo recupera el backend de sus propias fuentes, y por eso el
    dossier puede afirmar que describe lo que se ejecutó.
    """

    projection_version: int = Field(default=PROJECTION_VERSION, ge=1, le=PROJECTION_VERSION)
    case_id: str = Field(min_length=1, max_length=128)
    case_schema_version: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=300)
    created_at: str | None = Field(default=None, max_length=64)
    context: ContextoCientifico = Field(default_factory=ContextoCientifico)
    inputs: InputsDeclarados = Field(default_factory=InputsDeclarados)
    preflight: PreflightDeclarado | None = None
    run: CorridaDeclarada | None = None
    decisions: list[DecisionHumana] = Field(default_factory=list, max_length=500)
    disposition: DisposicionDeclarada | None = None
    #: Relación entre la corrida guardada y los inputs actuales, tal como la
    #: calculó el cliente. El backend la contrasta con el fingerprint; si
    #: discrepan, manda lo que el backend puede comprobar.
    run_inputs_relation: Literal["corresponde", "corrida_anterior", "desconocida"] = "desconocida"

    @field_validator("name", "case_id")
    @classmethod
    def _prohibir_rutas(cls, v: str, info) -> str:
        return _sin_ruta_local(v, info.field_name)  # type: ignore[return-value]

    @field_validator("case_id")
    @classmethod
    def _identificador_utilizable(cls, v: str) -> str:
        """
        El `case_id` acaba en el nombre de una carpeta dentro del ZIP.

        Se exige que tenga al menos un carácter sanitizable; el saneado real lo
        hace `package.py`, pero un identificador que se quede en cadena vacía
        produciría una raíz sin nombre y hay que rechazarlo aquí.
        """
        if not re.search(r"[A-Za-z0-9]", v):
            raise ValueError("`case_id` no contiene ningún carácter utilizable.")
        return v


def claves_prohibidas_en(payload: object, prefijo: str = "") -> list[str]:
    """
    Busca nombres de secreto en un objeto libre. Utilidad para las pruebas.

    No se usa en el camino normal —`extra="forbid"` ya rechaza lo desconocido—
    pero deja escrito qué se considera un secreto, y permite comprobarlo sobre
    payloads construidos a mano.
    """
    encontradas: list[str] = []
    if isinstance(payload, dict):
        for clave, valor in payload.items():
            ruta = f"{prefijo}.{clave}" if prefijo else str(clave)
            if str(clave).lower() in _CLAVES_PROHIBIDAS:
                encontradas.append(ruta)
            encontradas.extend(claves_prohibidas_en(valor, ruta))
    elif isinstance(payload, (list, tuple)):
        for indice, valor in enumerate(payload):
            encontradas.extend(claves_prohibidas_en(valor, f"{prefijo}[{indice}]"))
    return encontradas
