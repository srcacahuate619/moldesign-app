"""Qué respaldo científico tiene realmente un receptor. Un solo sitio.

SC-9 (`docs/36_POR_ARREGLAR_Y_VALIDAR.md`). El catálogo tiene 387 receptores
curados **estructuralmente** —familia, caja, preparación y, en 384 de ellos,
hotspots minados—. Eso está bien hecho. Lo que no se puede hacer es el salto de
ahí a «validado»:

* `spearman_rho` —la medida de que el ranking del motor correlaciona con
  afinidad real **para ese receptor**— existe en 2 de 387, y los dos valen
  exactamente `0.0`. Ése es el valor por defecto; y si fuera una medida real,
  diría que no hay correlación. En ninguna de las dos lecturas hay calibración.
* El contrato M4 alpha no declara hoy ninguna familia con stacking ML calibrado.
  Todas usan pesos conservadores comunes; CL-GNN se ejecuta como señal
  experimental con peso cero hasta validar externamente su checkpoint exacto.

El riesgo no es de código, es de producto: la interfaz presenta scores y
rankings con el mismo aspecto profesional tenga el receptor respaldo o no. Este
módulo existe para que ese respaldo sea **un dato del contrato** —calculado una
vez, transportado a todas las superficies— y no algo que cada pantalla deduzca
por su cuenta y una de ellas olvide.

Lo que este módulo **no** hace: calibrar. El holdout de los 327 restantes, los
benchmarks externos y el ρ real de cada receptor son trabajo científico que hay
que ejecutar; ninguna cantidad de código lo sustituye. Aquí sólo se dice la
verdad sobre lo que hay.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# No hay familias con stacking ML liberable en el contrato M4 alpha.
#: Mantener este conjunto explícito conserva el contrato y permite promover una
#: familia sólo mediante una futura validación sellada del artefacto exacto.
FAMILIAS_CON_PIPELINE_CALIBRADO: frozenset[str] = frozenset()


class NivelDeCalibracion(str, Enum):
    """Los cuatro estados reales. El orden es de más a menos respaldo."""

    #: ρ medido y utilizable para ESTE receptor. Hoy: ninguno del catálogo.
    CALIBRADO = "calibrado"
    #: Sin ρ propio, pero su familia estructural tiene stacking ML calibrado.
    PIPELINE_DE_FAMILIA = "pipeline_de_familia"
    #: Familia, caja y preparación curadas; ni ρ ni pipeline de familia.
    CURADO_ESTRUCTURAL = "curado_estructural"
    #: Ingerido sin curación: sin familia conocida o sin preparación.
    SIN_CURAR = "sin_curar"


#: Texto de una línea para la insignia. No dice «validado» en ningún caso.
RESUMEN: dict[NivelDeCalibracion, str] = {
    NivelDeCalibracion.CALIBRADO: "Calibrado para este receptor (Spearman ρ medido)",
    NivelDeCalibracion.PIPELINE_DE_FAMILIA: (
        "Pipeline calibrado por familia; este receptor no está calibrado individualmente"
    ),
    NivelDeCalibracion.CURADO_ESTRUCTURAL: (
        "Curado estructuralmente; sin calibrar y sin pipeline de familia"
    ),
    NivelDeCalibracion.SIN_CURAR: "Sin curar: sin familia estructural conocida",
}

#: Lo que hay que leer ANTES de ejecutar y JUNTO al resultado.
ADVERTENCIA: dict[NivelDeCalibracion, str] = {
    NivelDeCalibracion.CALIBRADO: "",
    NivelDeCalibracion.PIPELINE_DE_FAMILIA: (
        "Este receptor no tiene Spearman ρ medido: no se ha comprobado que el "
        "ranking del motor correlacione con afinidad real para él. El stacking "
        "sí está calibrado para su familia estructural, lo que respalda el "
        "método pero no este receptor en concreto. Usa el score para ordenar "
        "candidatos, no como una predicción de afinidad."
    ),
    NivelDeCalibracion.CURADO_ESTRUCTURAL: (
        "Este receptor no tiene Spearman ρ medido y su familia estructural no "
        "tiene stacking calibrado: se ejecuta con el contrato alpha conservador común. No hay "
        "evidencia de que el ranking correlacione con afinidad real aquí. Trata "
        "el resultado como una hipótesis a comprobar, no como una medida."
    ),
    NivelDeCalibracion.SIN_CURAR: (
        "Este receptor no está curado: no se le conoce familia estructural ni "
        "preparación verificada, y no tiene Spearman ρ. El pipeline corre con "
        "el contrato alpha conservador común y sin family-gating. Cualquier score de esta corrida es "
        "orientativo; no lo cites como evidencia de afinidad."
    ),
}

#: Qué falta exactamente, para que la advertencia sea accionable.
MOTIVO: dict[NivelDeCalibracion, str] = {
    NivelDeCalibracion.CALIBRADO: "",
    NivelDeCalibracion.PIPELINE_DE_FAMILIA: (
        "falta calibrar Spearman ρ contra afinidades medidas de este receptor"
    ),
    NivelDeCalibracion.CURADO_ESTRUCTURAL: (
        "faltan Spearman ρ del receptor y stacking calibrado para su familia"
    ),
    NivelDeCalibracion.SIN_CURAR: (
        "falta curar el receptor: familia estructural, preparación y Spearman ρ"
    ),
}


def rho_es_utilizable(rho: float | None) -> bool:
    """¿Ese `spearman_rho` respalda algo?

    `0.0` se rechaza deliberadamente. Es el valor por defecto con el que se
    escribieron los dos únicos registros del catálogo, y aunque fuera una medida
    real significaría «no correlaciona»: en ninguna de las dos lecturas se puede
    llamar calibrado a un receptor con ρ = 0.
    """
    if rho is None:
        return False
    try:
        valor = float(rho)
    except (TypeError, ValueError):
        return False
    if valor == 0.0:
        return False
    return -1.0 <= valor <= 1.0


@dataclass(frozen=True)
class EstadoDeCalibracion:
    """El respaldo de un receptor, listo para viajar por el contrato."""

    nivel: NivelDeCalibracion
    spearman_rho: float | None
    structural_family: str | None
    tiene_pipeline_de_familia: bool
    resumen: str
    advertencia: str
    motivo: str

    @property
    def requiere_advertencia(self) -> bool:
        return self.nivel is not NivelDeCalibracion.CALIBRADO

    def to_dict(self) -> dict[str, Any]:
        return {
            "nivel": self.nivel.value,
            "spearman_rho": self.spearman_rho,
            "structural_family": self.structural_family,
            "tiene_pipeline_de_familia": self.tiene_pipeline_de_familia,
            "resumen": self.resumen,
            "advertencia": self.advertencia,
            "motivo": self.motivo,
            "requiere_advertencia": self.requiere_advertencia,
        }


def _curado_estructuralmente(target: Any) -> bool:
    """Curado = tiene familia conocida y está preparado."""
    familia = getattr(target, "structural_family", None)
    preparado = bool(getattr(target, "is_prepared", False))
    return bool(familia) and preparado


def estado_de_calibracion(target: Any | None) -> EstadoDeCalibracion:
    """Nivel de respaldo de un receptor. Es LA función; no hay una segunda.

    Acepta cualquier objeto con los atributos del receptor —ORM, esquema de
    lectura o el snapshot congelado de una corrida— para que la corrida pueda
    declarar el respaldo que tenía **cuando se ejecutó**, no el de hoy.

    Un receptor ausente no se trata como bueno: `None` es `SIN_CURAR`.
    """
    if target is None:
        nivel = NivelDeCalibracion.SIN_CURAR
        return EstadoDeCalibracion(
            nivel=nivel,
            spearman_rho=None,
            structural_family=None,
            tiene_pipeline_de_familia=False,
            resumen=RESUMEN[nivel],
            advertencia=ADVERTENCIA[nivel],
            motivo=MOTIVO[nivel],
        )

    rho = getattr(target, "spearman_rho", None)
    familia = getattr(target, "structural_family", None)
    familia_normalizada = (familia or "").strip().lower() or None
    con_pipeline = familia_normalizada in FAMILIAS_CON_PIPELINE_CALIBRADO

    if rho_es_utilizable(rho):
        nivel = NivelDeCalibracion.CALIBRADO
        rho_publicado: float | None = float(rho)
    else:
        rho_publicado = None
        if not _curado_estructuralmente(target):
            nivel = NivelDeCalibracion.SIN_CURAR
        elif con_pipeline:
            nivel = NivelDeCalibracion.PIPELINE_DE_FAMILIA
        else:
            nivel = NivelDeCalibracion.CURADO_ESTRUCTURAL

    return EstadoDeCalibracion(
        nivel=nivel,
        spearman_rho=rho_publicado,
        structural_family=familia_normalizada,
        tiene_pipeline_de_familia=con_pipeline,
        resumen=RESUMEN[nivel],
        advertencia=ADVERTENCIA[nivel],
        motivo=MOTIVO[nivel],
    )
