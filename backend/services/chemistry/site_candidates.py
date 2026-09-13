"""Registro completo de candidatos de sitio, antes de truncar.

Implementa la instrumentacion que `docs/53` §6.3 exige para `SiteHypothesis` y que
`docs/49` §21.2 pone como paso 1 de `REC-10`: **persistir la lista completa de candidatos
antes de truncar top-n**, con geometria, residuos, score crudo, version y orden.

Por que hace falta, verificado y no supuesto. Lo que el programa persistia hasta hoy por
target era esto, en `backend/data/molpocket_report_holo.json`::

    {"distancia_a_ligando": 14.381, "score": 0.985, "druggability": 0.9484,
     "pocket_center": [59.67, 4.33, 42.5], "pocket_radius": 6.0,
     "n_spheres": 5764, "n_pockets": 1}

Un centro, un radio, un score y un contador. **No hay lista, ni ranking, ni candidatos
descartados**, asi que la pregunta de `REC-10` -si el pocket correcto ya esta generado y
se pierde al ordenarlo- no se puede contestar sobre ningun dato historico. Este modulo no
cambia el detector ni el ranking de produccion: solo deja de tirar informacion.

Distincion que gobierna todo el modulo, de `docs/49` §21.1:

  - **cobertura**: existe al menos un candidato que coincide con el sitio conocido;
  - **conversion**: ese candidato queda dentro del presupuesto que se presenta o ejecuta.

Sumar las dos dentro de `top-n` es lo que oculta el modo de fallo. Aqui se reportan
siempre por separado y bajo un `candidate_budget` explicito.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from math import sqrt
from typing import Any, Iterable, Sequence

# Origen de una hipotesis de sitio (docs/53 §6.3). No es un ranking de fiabilidad.
ORIGENES = (
    "LIGANDO_COCRISTALIZADO",
    "ANOTACION_EXPERIMENTAL",
    "SELECCION_MANUAL",
    "DETECTOR_ESTATICO",
    "DETECTOR_SOBRE_ENSEMBLE",
    "TEMPLATE_ESTRUCTURAL",
)

ESTADOS = ("CONFIRMADO", "DECLARADO", "INFERIDO", "REVISAR", "ABSTENERSE")


@dataclass
class CandidatoSitio:
    """Un candidato tal como lo produjo el detector, sin interpretar.

    `score` y `druggability` son **metricas crudas del motor y no probabilidades**. El
    §6.3 lo prohibe expresamente: convertirlas en probabilidad es el error que hace que
    un top-1 se lea como «sitio confirmado».
    """
    rank: int
    center: tuple[float, float, float]
    radius: float
    volume: float
    score: float
    druggability: float
    n_spheres: int
    rank_score: float | None
    hotspot_residues: list[str]

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _hotspot_names(hotspots: Iterable[dict]) -> list[str]:
    fuera: list[str] = []
    for h in hotspots or []:
        n = h.get("name") if isinstance(h, dict) else None
        if n:
            fuera.append(str(n))
    return fuera


def candidatos_desde_pockets(pockets: Sequence[Any]) -> list[CandidatoSitio]:
    """Convierte la salida completa de `detect_pockets(..., top_n=None)` en candidatos."""
    fuera: list[CandidatoSitio] = []
    for i, p in enumerate(pockets):
        fuera.append(CandidatoSitio(
            rank=i,
            center=tuple(round(float(c), 3) for c in p.center),  # type: ignore[arg-type]
            radius=round(float(p.radius), 3),
            volume=round(float(p.volume), 3),
            score=round(float(p.score), 6),
            druggability=round(float(p.druggability), 6),
            n_spheres=int(p.n_spheres),
            rank_score=(round(float(getattr(p, "rank_score")), 6)
                        if getattr(p, "rank_score", None) is not None else None),
            hotspot_residues=_hotspot_names(getattr(p, "hotspots", [])),
        ))
    return fuera


def site_candidates_record(
    *,
    structure_id: str,
    structure_text: str,
    candidatos: Sequence[CandidatoSitio],
    detector: str,
    detector_version: str,
    detector_config: dict[str, Any],
    candidate_budget: int,
    origen: str = "DETECTOR_ESTATICO",
    sitio_conocido_center: Sequence[float] | None = None,
    tolerancia_A: float = 4.0,
    seleccionado_rank: int | None = None,
    seleccionado_por: str | None = None,
    justificacion: str | None = None,
) -> dict[str, Any]:
    """Construye el registro persistible de hipotesis de sitio para una estructura.

    Args:
        candidatos: lista COMPLETA, sin truncar. Truncarla antes de llamar aqui destruye
            justo lo que el registro existe para medir.
        candidate_budget: cuantos candidatos se presentan o se ejecutan realmente. Es el
            denominador de `conversion`, y se declara antes de mirar.
        sitio_conocido_center: centro del sitio de referencia, si existe. Solo debe
            pasarse en rutas HOLO o de instrumentacion: usarlo para elegir pocket en una
            ruta presentada como APO esta prohibido por `docs/49` §21.2.
        tolerancia_A: distancia bajo la cual un candidato «coincide» con el sitio conocido.

    Returns:
        Registro serializable con la lista completa, el ranking, y cobertura y conversion
        reportadas por separado.
    """
    if seleccionado_rank is not None and not (0 <= seleccionado_rank < len(candidatos)):
        raise ValueError("seleccionado_rank fuera de la lista de candidatos")
    if origen not in ORIGENES:
        raise ValueError(f"origen desconocido: {origen}; usar uno de {ORIGENES}")

    cobertura: dict[str, Any] = {"evaluable": False}
    if sitio_conocido_center is not None:
        distancias = [_dist(c.center, sitio_conocido_center) for c in candidatos]
        aciertos = [i for i, d in enumerate(distancias) if d <= tolerancia_A]
        primer_acierto = aciertos[0] if aciertos else None
        cobertura = {
            "evaluable": True,
            "tolerancia_A": tolerancia_A,
            "centro_referencia": [round(float(x), 3) for x in sitio_conocido_center],
            # cobertura: ¿existe en CUALQUIER posicion de la lista completa?
            "cubierto": bool(aciertos),
            "rank_del_primer_acierto": primer_acierto,
            # conversion: ¿ese candidato entra en el presupuesto que se ejecuta?
            "convertido": bool(primer_acierto is not None
                               and primer_acierto < candidate_budget),
            "distancia_top1_A": round(distancias[0], 3) if distancias else None,
            "distancia_minima_A": round(min(distancias), 3) if distancias else None,
            "nota": ("cobertura y conversion se reportan por separado a proposito "
                     "(docs/49 §21.1): sumarlas dentro de top-n oculta el modo de fallo"),
        }

    estado = "INFERIDO" if origen == "DETECTOR_ESTATICO" else "DECLARADO"
    if seleccionado_rank is None:
        estado = "REVISAR"

    return {
        "registro": "site_candidates",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "structure_id": structure_id,
        "structure_sha256": hashlib.sha256(
            structure_text.encode("utf-8", "replace")).hexdigest(),
        "origen": origen,
        "estado": estado,
        "detector": {"nombre": detector, "version": detector_version,
                     "config": detector_config},
        "n_candidatos_generados": len(candidatos),
        "candidate_budget": candidate_budget,
        "candidatos": [c.dict() for c in candidatos],
        "seleccion": {
            "rank": seleccionado_rank,
            "por": seleccionado_por,
            "justificacion": justificacion,
        },
        "cobertura_vs_conversion": cobertura,
        "declaracion": (
            "Los campos `score` y `druggability` son metricas crudas del motor, NO "
            "probabilidades. El top-1 no es 'el sitio': mientras `estado` sea INFERIDO o "
            "REVISAR, el target no puede presentarse como estructuralmente cualificado "
            "(docs/53 §6.3). Este registro no cambia el detector ni el ranking de "
            "produccion; solo deja de descartar los candidatos que no entran en top-n."
        ),
    }
