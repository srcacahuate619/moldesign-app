"""
Identidad reproducible de una cohorte.

# Qué identifica el fingerprint

Responde a UNA pregunta: *¿es ésta la misma cohorte científica que aquélla?*
Dos cohortes con el mismo fingerprint producirían la misma corrida; dos con
fingerprints distintos no son comparables aunque su tabla se parezca.

# Canonicalización EXACTA (v1)

Se construye este documento y se serializa con
`json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False,
allow_nan=False)`; el fingerprint es `"sha256:" + sha256(utf8(documento))`.

    {
      "contract":   "cohort_preflight/v1",
      "receptor":   {"pdb_id": <MAYÚSCULAS>, "chain": <MAYÚSCULAS|null>},
      "config":     {"grid_center":  [x,y,z] redondeado a 3 decimales | null,
                     "grid_size":    [x,y,z] redondeado a 3 decimales | null,
                     "docking_engine": <minúsculas>,
                     "exhaustiveness": <int>,
                     "num_poses":      <int>,
                     "seed":           <int|null>},
      "rows":       [ [<molecula>, <active|null>, <control_role>], ... ]
    }

donde `<molecula>` es el **SMILES canónico** cuando la estructura se pudo leer,
y el texto de entrada recortado cuando no. Un input ilegible sigue formando
parte de la cohorte declarada: dos cohortes que difieren en una fila ilegible
son cohortes distintas, y omitirla las haría parecer la misma.

Las filas van **en el orden del archivo**. Reordenar el archivo cambia el
fingerprint: en v1 la cohorte es el conjunto tal como se declaró. Ordenar por
canónico haría indistinguible «reordené» de «cambié una molécula», y la
deduplicación todavía no está decidida (5B).

# Qué NO entra, y por qué

    generated_at      cambiaría en cada comprobación de la misma cohorte
    name              es descriptivo; renombrar un estudio no cambia la ciencia
    source_name       ídem, por fila
    nombre del archivo y cualquier ruta local
    número de workers  operacional: cambia cuánto tarda, no qué se calcula
    usuario o sesión   la misma cohorte es la misma la ejecute quien la ejecute
    elegibilidad, razones y avisos  son el VEREDICTO sobre la entrada, no la
                      entrada; incluirlos ataría la identidad a la versión del
                      validador y la cohorte «cambiaría» al actualizar RDKit

Los flotantes se redondean a 3 decimales antes de serializar, igual que en
`services/docking/preflight.py`: sin eso, `22.5` y `22.500000000000004` —que
producen la misma caja— darían identidades distintas.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from services.cohort.schemas import CohortStudy

#: Etiqueta del contrato dentro del documento canónico. Cambiarla invalida
#: deliberadamente todos los fingerprints anteriores: es lo que debe pasar
#: cuando la canonicalización deja de significar lo mismo.
COHORT_FINGERPRINT_CONTRACT = "cohort_preflight/v1"


@dataclass(frozen=True)
class FingerprintRow:
    """La parte de una fila que pertenece a la IDENTIDAD de la cohorte."""

    #: Canónico si se pudo leer; si no, el texto de entrada recortado.
    molecule: str
    active_label: bool | None
    control_role: str


def _triple(value: tuple[float, float, float] | None) -> list[float] | None:
    if value is None:
        return None
    return [round(float(component), 3) for component in value]


def canonical_cohort_document(study: CohortStudy, rows: list[FingerprintRow]) -> str:
    """
    Documento canónico del que sale el fingerprint. Determinista y sin entorno.

    Se expone como función propia —en vez de esconderla dentro del hash— para
    que una prueba pueda comparar DOCUMENTOS cuando dos fingerprints difieren.
    Un hash que no cuadra sin el documento al lado es indepurable.
    """
    documento = {
        "contract": COHORT_FINGERPRINT_CONTRACT,
        "receptor": {
            "pdb_id": study.receptor.pdb_id,
            "chain": study.receptor.chain,
        },
        "config": {
            "grid_center": _triple(study.config.grid_center),
            "grid_size": _triple(study.config.grid_size),
            "docking_engine": study.config.docking_engine,
            "exhaustiveness": int(study.config.exhaustiveness),
            "num_poses": int(study.config.num_poses),
            "seed": None if study.config.seed is None else int(study.config.seed),
        },
        "rows": [[row.molecule, row.active_label, row.control_role] for row in rows],
    }
    return json.dumps(
        documento,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def cohort_fingerprint(study: CohortStudy, rows: list[FingerprintRow]) -> str:
    """SHA-256 del documento canónico, con el prefijo que usa el resto del producto."""
    documento = canonical_cohort_document(study, rows)
    return "sha256:" + hashlib.sha256(documento.encode("utf-8")).hexdigest()
