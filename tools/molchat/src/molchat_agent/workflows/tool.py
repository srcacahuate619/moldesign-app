"""The tool the model uses to propose an iteration. It proposes; it never runs.

The tool validates the spec with the same code that will run it, adds the person's literal request (the model does
not get to rewrite what was asked) and leaves a card. Nothing is evaluated until the person approves that card.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ..conversation.tool_loop import Tool
from .iteration import ENSEMBLE_VARIANTS, FORMATS, MAX_MOLECULES, RECEPTOR_VIEWS, SCENES, IterationSpec, SpecError

ITERATION_GUIDANCE = (
    "Cuando el usuario pida, en una sola petición, evaluar UNA LISTA de moléculas una por una, en un mismo caso, contra un "
    "umbral de energía de Vina y, según cumpla, encadenar pasos (guardar en Moldex, vídeo de Molcy, auditar en Preparación, "
    "juntarlo todo en un único archivo), usa propose_iteration una sola vez: no encadenes tú las herramientas sueltas. "
    "Necesitas del usuario: nombre del caso, receptor (PDB), las moléculas con su SMILES y el umbral en kcal/mol; si falta "
    "alguno, pregúntalo y no inventes SMILES ni receptor. Pasa save=true si pidió guardar, video si pidió vídeo (scene: "
    "'vídeo de búsqueda' es busqueda). Formato: «de prueba», «vista previa», «rápido» o «corto» es previsualizacion; «vertical», "
    "«para redes», «shorts», «reels» o «TikTok» es vertical; si no dijo nada, horizontal. Personalización del vídeo, sólo "
    "lo que la persona pidió: title (título en pantalla), receptor (visible u oculto), receptor_color, residue_color (los "
    "«hotspots», residuos clave o destacados del sitio), polar_color y apolar_color (las líneas de las interacciones), "
    "labels, contacts y previous_sample (falso si pide quitarlos) y ensemble_variant. Los colores van como #RRGGBB: "
    "traduce el nombre (verde #22C55E, morado #8B5CF6, rojo #EF4444, azul #3B82F6, amarillo #EAB308, naranja #F97316, "
    "rosa #EC4899, cian #06B6D4, blanco #FFFFFF, gris #9CA3AF, negro #111827) o usa el código que dé. "
    "preparation=true si pidió la auditoría en "
    "Preparación y package=true si pidió juntar o entregar todo en un único archivo/ZIP; no actives lo que no pidió. "
    "stop=first (por defecto) detiene la iteración en la primera molécula que cumple; usa all solo si pidió evaluarlas todas. "
    "La herramienta no ejecuta nada: deja una tarjeta que la persona aprueba una vez; después el plan corre sin más "
    "intervención. Nunca digas que se evaluó, guardó o generó algo: di qué quedó pendiente de su aprobación. "
    "No llames «cribado» a esto: en MolDesign el cribado es el módulo de lotes y esto es otra cosa; di «iteración» o "
    "«evaluar la lista». ")

_COLOR = {"type": "string", "pattern": "^#[0-9A-Fa-f]{6}$", "maxLength": 7}
_MOLECULE = {"type": "object", "properties": {"name": {"type": "string", "maxLength": 80},
                                              "smiles": {"type": "string", "maxLength": 500}},
             "required": ["smiles"], "additionalProperties": False}


def propose_iteration_tool(user_text: str, propose: Callable[[IterationSpec], dict[str, Any] | None]) -> Tool:
    async def run(args: dict[str, Any]) -> dict[str, Any]:
        data = dict(args)
        video = data.get("video")
        if isinstance(video, dict):
            data["video"] = {"format": "horizontal", **video}  # the card shows the format before anyone approves
        data["original_request"] = user_text[:4000]
        try:
            spec = IterationSpec.from_dict(data)
        except SpecError as exc:
            return {"status": "invalid", "message": str(exc)}
        card = propose(spec)
        if card is None:
            return {"status": "busy", "message": "Ya hay una propuesta de iteración en este turno o demasiadas pendientes."}
        return {"status": "awaiting_approval", "workflow_id": card["id"], "digest": spec.digest, "card": card["lines"],
                "message": "Quedó una tarjeta. NO se evaluó nada: la persona debe aprobarla con el botón."}

    schema = {"type": "object", "properties": {
        "case_name": {"type": "string", "maxLength": 100},
        "pdb_id": {"type": "string", "maxLength": 64},
        "molecules": {"type": "array", "minItems": 1, "maxItems": MAX_MOLECULES, "items": _MOLECULE},
        "threshold_kcal": {"type": "number", "minimum": -30, "maximum": 0},
        "stop": {"type": "string", "enum": ["first", "all"]},
        "require_physical": {"type": "boolean"}, "save": {"type": "boolean"},
        "video": {"type": "object", "properties": {
            "scene": {"type": "string", "enum": list(SCENES)}, "format": {"type": "string", "enum": list(FORMATS)},
            "title": {"type": "string", "maxLength": 80},
            "receptor": {"type": "string", "enum": list(RECEPTOR_VIEWS)},
            "receptor_color": _COLOR, "residue_color": _COLOR, "polar_color": _COLOR, "apolar_color": _COLOR,
            "labels": {"type": "boolean"}, "contacts": {"type": "boolean"}, "previous_sample": {"type": "boolean"},
            "ensemble_variant": {"type": "string", "enum": list(ENSEMBLE_VARIANTS)}},
            "required": ["scene"], "additionalProperties": False},
        "preparation": {"type": "boolean"}, "package": {"type": "boolean"}},
        "required": ["case_name", "pdb_id", "molecules", "threshold_kcal"], "additionalProperties": False}
    return Tool("propose_iteration",
                "Prepara una iteración automática: evalúa una lista de moléculas una por una en un caso, se detiene según un umbral "
                "de energía de Vina (kcal/mol, negativo) y, si una cumple, puede guardarla en Moldex, pedir un vídeo a Molcy, "
                "auditarla en Preparación y juntar todo en un único ZIP. No ejecuta nada: deja una tarjeta que la persona aprueba "
                "una sola vez. Úsala cuando la petición encadene varios pasos sobre una lista de moléculas.", schema, run)
