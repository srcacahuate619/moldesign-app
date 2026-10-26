"""El contexto de ensayo frente a lo que la corrida preparó (C-GAP-02).

La auditoría científica (Fase C) encontró que las condiciones de ensayo y el
constructo sólo viajaban como texto libre: nada contrastaba el pH, las cadenas o
los cofactores del ensayo con los de la preparación, y una discrepancia no dejaba
rastro. Esto **no** valida ninguna afinidad ni detecta nada nuevo: compara lo que
el investigador declara del ensayo con lo que la corrida registró, y separa tres
estados que no se mezclan:

* ``coincide``     el ensayo y la corrida dicen lo mismo (con la tolerancia declarada);
* ``discrepancia`` dicen cosas distintas: pide una decisión registrada;
* ``desconocido``  falta uno de los dos lados. **Un campo omitido nunca se rotula
                   coincidente ni discrepante.**

Lo que no tiene contraparte en la corrida (temperatura, magnitud medida,
constructo, fuente) se transmite como declarado y no se compara.

La función de clasificación es pura y se aplica igual al reconstruir el paquete:
quien reciba el ZIP puede recalcular cada estado desde los valores que lleva.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

#: Identidad del contrato que viaja con cada comparación.
CONTRATO = "moldesign.contexto_ensayo/1"

#: Tolerancia del pH. dimorphite enumera con precisión 1.0 alrededor del pH pedido
#: (`chem/conformer.py`); por debajo de media unidad, la especie no cambia de forma
#: que esta comparación pueda afirmar.
TOLERANCIA_PH = 0.5

EstadoComparacion = Literal["coincide", "discrepancia", "desconocido"]

#: Campo → (etiqueta, de dónde sale el valor de la corrida).
CAMPOS_CONTRASTABLES: dict[str, tuple[str, str]] = {
    "ph": ("pH del ensayo frente al de protonación", "ligand_state.protonacion.ph"),
    "cadenas": ("Cadenas del constructo frente a las del receptor",
                "execution_provenance.receptor_prep.prepared_chains"),
    "cofactores": ("Cofactores del ensayo frente a los conservados",
                   "execution_provenance.receptor_prep.cofactors_whitelist"),
}

#: Lo que se declara y no tiene contraparte en la corrida.
CAMPOS_DECLARADOS = ("temperature_c", "endpoint", "protein_construct", "source")


@dataclass(frozen=True)
class Comparacion:
    campo: str
    ensayo: Any
    corrida: Any
    estado: EstadoComparacion
    fuente_ensayo: str
    fuente_corrida: str
    contrato: str = CONTRATO

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _v(obj: Any, campo: str, defecto: Any = None) -> Any:
    if obj is None:
        return defecto
    if isinstance(obj, dict):
        return obj.get(campo, defecto)
    return getattr(obj, campo, defecto)


def _codigos(valores: Any) -> list[str] | None:
    """Lista de códigos en mayúsculas, ordenada y sin repetir; ``None`` si no es lista."""
    if not isinstance(valores, (list, tuple)):
        return None
    return sorted({str(v).strip().upper() for v in valores if str(v).strip()})


def clasificar(campo: str, ensayo: Any, corrida: Any) -> EstadoComparacion:
    """El estado de una comparación. Pura: se usa al construir y al reconstruir."""
    if ensayo is None or corrida is None:
        return "desconocido"
    if campo == "ph":
        try:
            return "coincide" if abs(float(ensayo) - float(corrida)) <= TOLERANCIA_PH else "discrepancia"
        except (TypeError, ValueError):
            return "desconocido"
    a, b = _codigos(ensayo), _codigos(corrida)
    if a is None or b is None:
        return "desconocido"
    return "coincide" if a == b else "discrepancia"


def valores_de_la_corrida(eval_result: Any) -> dict[str, Any]:
    """pH de protonación, cadenas preparadas y cofactores conservados, o ``None`` si no constan."""
    ligand_state = _v(eval_result, "ligand_state") or {}
    protonacion = _v(ligand_state, "protonacion") or {}
    ph = _v(protonacion, "ph") if _v(protonacion, "aplicada") else None
    protocolo = _v(eval_result, "docking_protocol") or {}
    prep = _v(_v(protocolo, "execution_provenance") or {}, "receptor_prep") or {}
    cadenas = _v(prep, "prepared_chains")
    # Una lista vacía registrada es «no se conservó ninguno»; la clave ausente,
    # «no se registró» (SCI-A-068): no se confunden.
    cofactores = prep.get("cofactors_whitelist") if isinstance(prep, dict) and "cofactors_whitelist" in prep else None
    return {
        "ph": float(ph) if isinstance(ph, (int, float)) and not isinstance(ph, bool) else None,
        "cadenas": _codigos(cadenas),
        "cofactores": _codigos(cofactores),
    }


def comparar(assay: Any, eval_result: Any) -> list[Comparacion]:
    """Una comparación por campo contrastable del ensayo declarado; vacía si no se declaró."""
    if assay is None:
        return []
    corrida = valores_de_la_corrida(eval_result)
    declarados = {
        "ph": _v(assay, "ph"),
        "cadenas": _codigos(_v(assay, "chains")),
        "cofactores": _codigos(_v(assay, "cofactors")),
    }
    fuentes = {"ph": "case.context.assay.ph", "cadenas": "case.context.assay.chains",
               "cofactores": "case.context.assay.cofactors"}
    return [
        Comparacion(campo, declarados[campo], corrida[campo],
                    clasificar(campo, declarados[campo], corrida[campo]),
                    fuentes[campo], CAMPOS_CONTRASTABLES[campo][1])
        for campo in CAMPOS_CONTRASTABLES
    ]


def declarados_sin_contraparte(assay: Any) -> dict[str, Any]:
    """Temperatura, magnitud, constructo y fuente tal como los declaró el caso."""
    if assay is None:
        return {}
    return {campo: _v(assay, campo) for campo in CAMPOS_DECLARADOS if _v(assay, campo) not in (None, "")}
