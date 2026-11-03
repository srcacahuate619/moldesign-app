"""Product actions that wait for a person's click: save a run in Moldex, ask Molcy for a video.

The model never executes these. A tool checks everything that can be checked without side effects
(the run finished, whether it is already saved, the scene exists, the machine can render) and leaves a
*proposal*. The person confirms it from a card in the chat; only then does the sidecar call MolDesign with
that person's session. MolDesign accepts the chat session as the full identity of the account, so the
confirmation cannot live on the lock's side: it has to be a click the model cannot make.

Nothing here renders or stores science. The video is MolDesign's (``POST /molcy/trabajos``) and so is its
mandatory closing; there is no field to remove it, and the personalization is the small recipe Molcy already
validates (``PresentacionMolcy``): title, colors, receptor visibility, labels and contacts.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import time
import unicodedata
import uuid
from collections.abc import Callable
from typing import Any

import httpx

from ..bridge import MolDesignBridge
from ..lang import tr
from .harness_tools import fetch_job
from .tool_loop import Tool

SAVE, VIDEO = "save_moldex", "molcy_video"
PROPOSAL_TTL_S = 900
MAX_PENDING = 20

SCENES = ("resultado", "receptor", "busqueda", "ensamble")
FORMATS = ("horizontal", "vertical", "previsualizacion")
RECEPTOR_MODES = ("automatico", "visible", "oculto")
_FORMAT_LABEL = {"horizontal": "horizontal (biblioteca)", "vertical": "vertical (redes)",
                 "previsualizacion": "previsualización (rápida)"}
_SCENE_LABEL = {"resultado": "resultado", "receptor": "receptor", "busqueda": "búsqueda", "ensamble": "ensamble"}

_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
_UUID = re.compile(r"[0-9a-fA-F-]{36}")

#: Appended to the hosted system prompt. Static: no user data is formatted in.
ACTIONS_GUIDANCE = (
    "Guardar una corrida en Moldex y generar un vídeo con Molcy tienen efecto: usa save_to_moldex o "
    "request_molcy_video solo si el usuario lo pidió. Esas herramientas no ejecutan nada: dejan una propuesta que la "
    "persona confirma con un botón. Nunca digas que se guardó ni que el vídeo empezó; di qué quedó pendiente de su "
    "confirmación. Un vídeo solo puede salir de una corrida guardada en Moldex: si no lo está, la propuesta del vídeo la "
    "guarda primero. Si el usuario no dijo la escena (resultado, receptor, búsqueda o ensamble) o el formato (horizontal, "
    "vertical o previsualización), pregúntalo antes de proponer. Personaliza solo lo que el usuario pidió (título, "
    "colores en #RRGGBB, receptor visible u oculto, etiquetas, contactos); el cierre de MolDesign es obligatorio y no se "
    "puede quitar. Si no hay GPU o Blender, dilo: no se instala nada desde el chat. Para saber cómo va un vídeo ya "
    "pedido usa get_molcy_video_status con su job_id. ")


@dataclass
class Proposal:
    id: str
    owner: str
    conv_id: str | None
    kind: str
    spec: dict[str, Any]
    summary: dict[str, Any]
    expires: float
    state: str = "pending"  # pending | running | done | cancelled
    outcome: dict[str, Any] | None = None


def new_proposal(proposals: dict[str, Proposal], owner: str, conv_id: str | None, kind: str,
                 spec: dict[str, Any], summary: dict[str, Any]) -> Proposal | None:
    """Register a proposal, dropping the stale ones first; ``None`` when too many are waiting."""
    now = time.monotonic()
    for key in [key for key, item in proposals.items() if item.expires < now]:
        del proposals[key]
    if sum(1 for item in proposals.values() if item.owner == owner and item.state == "pending") >= MAX_PENDING:
        return None
    proposal = Proposal(uuid.uuid4().hex, owner, conv_id, kind, spec, summary, now + PROPOSAL_TTL_S)
    proposals[proposal.id] = proposal
    return proposal


def view(proposal: Proposal) -> dict[str, Any]:
    """What the interface may show of a proposal: never the platform session, never a local path."""
    return {"id": proposal.id, "kind": proposal.kind, **proposal.summary}


# ── Talking to MolDesign ──────────────────────────────────────────────────────────────────────────


async def _http(bridge: MolDesignBridge, method: str, path: str, *, params: dict[str, str] | None = None,
                body: dict[str, Any] | None = None, timeout: float = 30) -> tuple[int, Any]:
    """``(status, json)``; ``(0, None)`` when the platform cannot be reached. Never follows redirects."""
    if not getattr(bridge, "token", None):
        return 0, None
    try:
        response = await bridge.client.request(method, path, params=params, json=body, timeout=timeout,
                                               follow_redirects=False, headers={"Authorization": f"Bearer {bridge.token}"})
    except httpx.RequestError:
        return 0, None
    if len(response.content) > 5_000_000:
        return response.status_code, None
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def _detail(data: Any) -> str | None:
    if isinstance(data, dict):
        data = data.get("detail")
    if isinstance(data, str):
        return data.strip()[:300] or None
    if isinstance(data, list):
        parts = []
        for item in data[:3]:
            if isinstance(item, dict) and isinstance(item.get("msg"), str):
                where = ".".join(str(part) for part in item.get("loc", [])[1:] if isinstance(part, (str, int)))
                parts.append(f"{where}: {item['msg']}" if where else item["msg"])
        return "; ".join(parts)[:300] or None
    return None


def _failure(code: int, data: Any, what: str) -> dict[str, Any]:
    detail = _detail(data)
    if code == 0:
        return {"status": "unavailable", "message": tr("No se pudo contactar con MolDesign; no se confirmó nada.",
                                                    "Could not reach MolDesign; nothing was confirmed.")}
    if code in (401, 403):
        return {"status": "session_expired", "message": tr("La sesión con MolDesign caducó; reconecta MolChat.",
                                                        "The MolDesign session expired; reconnect MolChat.")}
    if code == 404:
        return {"status": "not_found", "message": tr("MolDesign no encontró esa corrida en tu cuenta.",
                                                  "MolDesign did not find that run in your account.")}
    if code in (409, 422):
        return {"status": "rejected", "message": tr(f"MolDesign rechazó la solicitud: {detail or what}",
                                                  f"MolDesign rejected the request: {detail or what}"), "detail": detail}
    return {"status": "failed", "message": tr(f"{what} MolDesign respondió con un error.", f"{what} MolDesign answered with an error."),
            "detail": detail}


async def _job_ref(bridge: MolDesignBridge, task_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", task_id):
        return None, {"status": "invalid", "message": "Identificador de tarea no válido."}
    job, abstention = await fetch_job(bridge, task_id)
    if abstention is not None:
        return None, abstention
    result = job.get("result")
    molecule_id = result.get("molecule_id") if isinstance(result, dict) else None
    if job["status"] != "SUCCESS" or not isinstance(molecule_id, str) or not _UUID.fullmatch(molecule_id):
        return None, {"status": "not_ready", "task_status": job["status"],
                      "message": tr("La evaluación no terminó con un resultado; no se puede guardar ni usar para un vídeo.",
                                     "The evaluation did not end with a result; it cannot be saved or used for a video.")}
    target = result.get("target_name") if isinstance(result.get("target_name"), str) else None
    return {"task_id": task_id, "molecule_id": molecule_id, "receptor": (target or "")[:120] or None}, None


async def _moldex_entry(bridge: MolDesignBridge, ref: dict[str, Any]) -> tuple[dict[str, Any] | None, bool]:
    """The saved run in ``/molcy/fuentes`` (``None`` if it is not saved) and whether the list could be read."""
    code, data = await _http(bridge, "GET", "/molcy/fuentes")
    if code != 200 or not isinstance(data, dict) or not isinstance(data.get("moldex"), list):
        return None, False
    for item in data["moldex"]:
        if isinstance(item, dict) and item.get("id") == ref["molecule_id"] and item.get("task_id") == ref["task_id"]:
            return item, True
    return None, True


# ── Presentation (Molcy's own recipe, validated again by Molcy) ───────────────────────────────────


def build_presentation(args: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """The cosmetic recipe the person asked for. Only what was asked travels; Molcy fills the rest."""
    recipe: dict[str, Any] = {}
    title = args.get("title")
    if title is not None:
        title = title.strip()
        if not title or len(title) > 80 or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in title):
            return None, "El título debe tener entre 1 y 80 caracteres legibles."
        recipe["titulo"] = title
    for key, field in (("color_receptor", "color_receptor"), ("color_residuos", "color_residuos")):
        if args.get(key) is not None:
            if not _COLOR.fullmatch(args[key]):
                return None, f"{key} debe ser un color #RRGGBB."
            recipe[field] = args[key].upper()
    lines: dict[str, str] = {}
    for key, field in (("color_polar", "polar"), ("color_apolar", "apolar")):
        if args.get(key) is not None:
            if not _COLOR.fullmatch(args[key]):
                return None, f"{key} debe ser un color #RRGGBB."
            lines[field] = args[key].upper()
    if lines:
        recipe["colores_lineas"] = lines
    if args.get("receptor") is not None:
        if args["receptor"] not in RECEPTOR_MODES:
            return None, "receptor debe ser automatico, visible u oculto."
        recipe["receptor"] = args["receptor"]
    for key, field in (("show_previous", "muestra_anterior"), ("labels", "etiquetas"), ("contacts", "contactos")):
        if args.get(key) is not None:
            if args[key] not in ("si", "no"):
                return None, f"{key} debe ser si o no."
            recipe[field] = args[key] == "si"
    return recipe, None


def _presentation_lines(recipe: dict[str, Any]) -> list[str]:
    lines = []
    if "titulo" in recipe:
        lines.append(f"Título: {recipe['titulo']}")
    colors = [f"{label} {recipe[key]}" for key, label in (("color_receptor", "receptor"), ("color_residuos", "residuos"))
              if key in recipe]
    colors += [f"líneas {label} {value}" for label, value in sorted((recipe.get("colores_lineas") or {}).items())]
    if colors:
        lines.append("Colores: " + ", ".join(colors))
    if "receptor" in recipe:
        lines.append(f"Receptor: {recipe['receptor']}")
    for key, label in (("muestra_anterior", "muestra anterior"), ("etiquetas", "etiquetas"), ("contactos", "contactos")):
        if key in recipe:
            lines.append(f"{label.capitalize()}: {'sí' if recipe[key] else 'no'}")
    return lines


# ── Preparing (read-only) ─────────────────────────────────────────────────────────────────────────


async def prepare_save(bridge: MolDesignBridge, args: dict[str, Any]) -> dict[str, Any]:
    ref, abstention = await _job_ref(bridge, args["task_id"].strip())
    if abstention is not None:
        return abstention
    entry, _ = await _moldex_entry(bridge, ref)
    if entry is not None:
        return {"status": "already_saved", "task_id": ref["task_id"], "message": "Esta corrida ya está guardada en Moldex."}
    name = args.get("name", "").strip() or None
    if name is not None and (len(name) > 200 or any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in name)):
        return {"status": "invalid", "message": "El nombre debe tener hasta 200 caracteres legibles."}
    lines = [f"Corrida {ref['task_id']}" + (f" · receptor {ref['receptor']}" if ref["receptor"] else "")]
    if name:
        lines.append(f"Nombre: {name}")
    lines.append("Quedará disponible en Moldex y como fuente de vídeo en Molcy.")
    return {"status": "ready", "spec": {"molecule_id": ref["molecule_id"], "task_id": ref["task_id"], "name": name},
            "summary": {"title": "Guardar en Moldex", "lines": lines}}


async def prepare_video(bridge: MolDesignBridge, args: dict[str, Any]) -> dict[str, Any]:
    scene, fmt = args["scene"], args["format"]
    if scene not in SCENES or fmt not in FORMATS:
        return {"status": "invalid", "message": "Escena o formato no válidos."}
    recipe, problem = build_presentation(args)
    if problem:
        return {"status": "invalid", "message": problem}
    ref, abstention = await _job_ref(bridge, args["task_id"].strip())
    if abstention is not None:
        return abstention
    entry, listed = await _moldex_entry(bridge, ref)
    save_first = entry is None
    if entry is not None:
        if not entry.get("disponible"):
            return {"status": "source_unavailable", "message": entry.get("motivo") or "Esta corrida no puede protagonizar un vídeo."}
        available = [item for item in entry.get("escenas_disponibles", []) if item in SCENES]
        if scene not in available:
            return {"status": "scene_unavailable", "available_scenes": available,
                    "message": f"La escena «{scene}» no está disponible para esta corrida."}
    elif not listed:
        return {"status": "unavailable", "message": "No se pudo consultar qué corridas pueden protagonizar un vídeo."}
    code, renderer = await _http(bridge, "GET", "/molcy/renderizador", timeout=120)
    if code != 200 or not isinstance(renderer, dict):
        return {"status": "unavailable", "message": "No se pudo comprobar si este equipo puede renderizar vídeo."}
    if not renderer.get("disponible"):
        return {"status": "renderer_unavailable", "message": str(renderer.get("motivo") or "Molcy no está disponible.")[:300]}
    if not renderer.get("gpu_disponible"):
        return {"status": "renderer_unavailable",
                "message": str(renderer.get("motivo_gpu") or "El vídeo necesita una GPU compatible.")[:300]}
    lines = [f"Corrida {ref['task_id']}" + (f" · receptor {ref['receptor']}" if ref["receptor"] else ""),
             f"Escena: {_SCENE_LABEL[scene]} · Formato: {_FORMAT_LABEL[fmt]}", *_presentation_lines(recipe or {})]
    if save_first:
        lines.append("Se guardará primero en Moldex: un vídeo solo puede salir de una corrida guardada.")
    lines.append("Usa tu GPU y puede tardar; podrás seguirlo en Molcy. El cierre de MolDesign se añade siempre.")
    return {"status": "ready", "spec": {"molecule_id": ref["molecule_id"], "task_id": ref["task_id"], "scene": scene,
                                        "format": fmt, "presentation": recipe or {}, "save_first": save_first},
            "summary": {"title": "Generar vídeo con Molcy", "lines": lines, "saves_first": save_first}}


# ── Executing (after the person confirmed) ────────────────────────────────────────────────────────


async def run_save(bridge: MolDesignBridge, spec: dict[str, Any]) -> dict[str, Any]:
    params = {"task_id": spec["task_id"], **({"name": spec["name"]} if spec.get("name") else {})}
    code, data = await _http(bridge, "POST", f"/history/save/{spec['molecule_id']}", params=params)
    if code == 200 and isinstance(data, dict) and data.get("status") == "saved":
        name = data.get("name") if isinstance(data.get("name"), str) else None
        return {"status": "saved", "task_id": spec["task_id"], "name": (name or "")[:200] or None,
                "message": tr("Corrida guardada en Moldex.", "Run saved to Moldex.")}
    return _failure(code, data, tr("No se pudo guardar en Moldex.", "Could not save to Moldex."))


async def run_video(bridge: MolDesignBridge, spec: dict[str, Any]) -> dict[str, Any]:
    if spec.get("save_first"):
        saved = await run_save(bridge, spec)
        if saved["status"] != "saved":
            return {**saved, "message": tr("No se guardó la corrida en Moldex, así que no se pidió el vídeo. ",
                                            "The run was not saved to Moldex, so no video was requested. ") + saved["message"]}
    entry, listed = await _moldex_entry(bridge, {"molecule_id": spec["molecule_id"], "task_id": spec["task_id"]})
    if not listed:
        return {"status": "unavailable", "message": tr("No se pudo comprobar la fuente del vídeo; no se pidió nada.",
                                                        "Could not check the video's source; nothing was requested.")}
    if entry is None or not entry.get("disponible"):
        return {"status": "source_unavailable", "message": (entry or {}).get("motivo") or tr(
            "La corrida no aparece como fuente de vídeo.", "The run is not listed as a video source.")}
    if spec["scene"] not in entry.get("escenas_disponibles", []):
        return {"status": "scene_unavailable", "available_scenes": [s for s in entry.get("escenas_disponibles", []) if s in SCENES],
                "message": tr(f"La escena «{spec['scene']}» no está disponible para esta corrida.",
                               f"The scene «{spec['scene']}» is not available for this run.")}
    body = {"origen": "moldex", "id": spec["molecule_id"], "task_id": spec["task_id"], "escena": spec["scene"],
            "formato": spec["format"], "dispositivo": "gpu", "presentacion": spec["presentation"]}
    code, data = await _http(bridge, "POST", "/molcy/trabajos", body=body, timeout=60)
    if code == 0:  # the request may have reached Molcy: never say "nothing happened"
        return {"status": "unknown", "message": tr(
            "No se pudo confirmar si el vídeo quedó en cola; revisa la pestaña Molcy antes de reintentar.",
            "Could not confirm whether the video was queued; check the Molcy tab before retrying.")}
    if code == 202 and isinstance(data, dict) and isinstance(data.get("id"), str) and _UUID.fullmatch(data["id"]):
        adjustments = data.get("ajustes") if isinstance(data.get("ajustes"), dict) else None
        return {"status": "started", "job_id": data["id"], "saved_first": bool(spec.get("save_first")),
                "adjustments": adjustments, "message": tr("Vídeo en cola en Molcy.", "Video queued in Molcy.")}
    if code == 202:  # accepted, but without an id we can follow
        return {"status": "unknown", "message": tr(
            "MolDesign aceptó la solicitud sin devolver un identificador válido; revisa la pestaña Molcy antes de reintentar.",
            "MolDesign accepted the request without returning a valid identifier; check the Molcy tab before retrying.")}
    return _failure(code, data, tr("No se pudo pedir el vídeo.", "Could not request the video."))


async def run_proposal(bridge: MolDesignBridge, proposal: Proposal) -> dict[str, Any]:
    return await (run_save if proposal.kind == SAVE else run_video)(bridge, proposal.spec)


def outcome_text(proposal: Proposal, outcome: dict[str, Any]) -> str:
    """The sentence the conversation keeps once a proposal is resolved."""
    what = "Guardar en Moldex" if proposal.kind == SAVE else "Generar vídeo con Molcy"
    status = outcome.get("status")
    if proposal.state == "cancelled":
        return f"{what}: cancelado; no se hizo nada."
    if status == "started":
        return f"{what}: vídeo en cola en Molcy (trabajo {outcome['job_id']}). Puedes seguirlo en la pestaña Molcy o preguntarme cómo va."
    if status == "saved":
        return f"{what}: la corrida quedó guardada en Moldex."
    lead = "no se pudo confirmar" if status == "unknown" else "no se completó"
    return f"{what}: {lead}. {outcome.get('message') or 'MolDesign no confirmó el resultado.'}"


def proposal_answer(proposals: list[Proposal]) -> str:
    """What the turn says when it left proposals: written by the host, so it cannot claim a done deed."""
    names = " y ".join(f"«{item.summary.get('title', 'acción')}»" for item in proposals)
    return (f"Dejé preparado {names}. Todavía no se hizo nada: confirma o cancela con los botones de la tarjeta. "
            "Si no la confirmas, caduca.")


_SAVE_CLAIM = re.compile(r"(?<!no )(?<!sin )\b(?:se\s+(?:ha\s+)?guard[oó]|se\s+ha\s+guardado|he\s+guardado|guardé|"
                         r"qued[oó]\s+guardad[ao])\b(?:[^.\n]{0,60}\b(?:moldex|corrida|evaluaci[oó]n|resultado)\b)?", re.I)
_VIDEO_CLAIM = re.compile(r"(?<!no )(?<!sin )\b(?:se\s+(?:ha\s+)?(?:gener[oó]|inici[oó]|empez[oó]|puso|envi[oó]|mand[oó]|cre[oó])|"
                          r"se\s+ha\s+(?:generado|iniciado|puesto|enviado|creado)|he\s+(?:generado|iniciado|puesto|enviado|creado)|"
                          r"generé|inicié|puse|envié)\b[^.\n]{0,60}\bv[ií]deo\b", re.I)


def mask_unconfirmed_actions(text: str) -> str:
    """Correct claims that a save or a video was done: only the person's click does either.

    Narrow on purpose (past-tense action verbs): a sentence like "ya está guardada" is not rewritten here,
    because ``save_to_moldex`` answers ``already_saved`` when MolDesign says so.
    """
    text = _SAVE_CLAIM.sub("No se confirmó el guardado en Moldex", text)
    return _VIDEO_CLAIM.sub("No se confirmó que el vídeo haya empezado", text)


# ── Tools ─────────────────────────────────────────────────────────────────────────────────────────

Propose = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any] | None]


def _awaiting(proposal: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    return {"status": "awaiting_confirmation", "action_id": proposal["id"], "summary": summary,
            "message": "Quedó una propuesta. NO está hecho: la persona debe confirmarla con el botón de la tarjeta."}


def save_to_moldex_tool(bridge: MolDesignBridge, propose: Propose) -> Tool:
    async def save(args: dict[str, Any]) -> dict[str, Any]:
        prepared = await prepare_save(bridge, args)
        if prepared["status"] != "ready":
            return prepared
        proposal = propose(SAVE, prepared["spec"], prepared["summary"])
        if proposal is None:
            return {"status": "busy", "message": "Ya hay una propuesta de este tipo en este turno o demasiadas pendientes."}
        return _awaiting(proposal, prepared["summary"])

    schema = {"type": "object", "properties": {"task_id": {"type": "string", "maxLength": 128},
                                                "name": {"type": "string", "maxLength": 200}},
              "required": ["task_id"], "additionalProperties": False}
    return Tool("save_to_moldex", "Prepara guardar en Moldex una corrida terminada (task_id de evaluate_case). No guarda nada: "
                "deja una propuesta que la persona confirma con un botón. Úsala solo si el usuario pidió guardar.",
                schema, save)


def molcy_video_tool(bridge: MolDesignBridge, propose: Propose) -> Tool:
    async def request(args: dict[str, Any]) -> dict[str, Any]:
        prepared = await prepare_video(bridge, args)
        if prepared["status"] != "ready":
            return prepared
        proposal = propose(VIDEO, prepared["spec"], prepared["summary"])
        if proposal is None:
            return {"status": "busy", "message": "Ya hay una propuesta de este tipo en este turno o demasiadas pendientes."}
        return _awaiting(proposal, prepared["summary"])

    color = {"type": "string", "maxLength": 7}
    switch = {"type": "string", "enum": ["si", "no"], "maxLength": 2}
    schema = {"type": "object", "properties": {
        "task_id": {"type": "string", "maxLength": 128},
        "scene": {"type": "string", "enum": list(SCENES), "maxLength": 10},
        "format": {"type": "string", "enum": list(FORMATS), "maxLength": 16},
        "title": {"type": "string", "maxLength": 80},
        "receptor": {"type": "string", "enum": list(RECEPTOR_MODES), "maxLength": 10},
        "color_receptor": color, "color_residuos": color, "color_polar": color, "color_apolar": color,
        "show_previous": switch, "labels": switch, "contacts": switch},
        "required": ["task_id", "scene", "format"], "additionalProperties": False}
    return Tool("request_molcy_video", "Prepara un vídeo de Molcy (solo GPU) de una corrida terminada (task_id de evaluate_case). "
                "No renderiza: comprueba corrida, escena y equipo, y deja una propuesta que la persona confirma con un botón. "
                "Si la corrida no está en Moldex, la propuesta la guarda primero. scene: resultado, receptor, busqueda o ensamble. "
                "format: horizontal, vertical o previsualizacion. Personalización opcional, solo lo que el usuario pidió: title, "
                "receptor (automatico/visible/oculto), colores #RRGGBB, show_previous, labels, contacts (si/no). "
                "El cierre de MolDesign es obligatorio. Úsala solo si el usuario pidió el vídeo.", schema, request)


def molcy_video_status_tool(bridge: MolDesignBridge) -> Tool:
    """Read-only: what Molcy says about a job the person already confirmed."""
    async def status(args: dict[str, Any]) -> dict[str, Any]:
        job_id = args["job_id"].strip()
        if not _UUID.fullmatch(job_id):
            return {"status": "invalid", "message": "Identificador de trabajo no válido."}
        code, data = await _http(bridge, "GET", f"/molcy/trabajos/{job_id}")
        if code in (403, 404):
            return {"status": "not_found", "job_id": job_id}
        if code != 200 or not isinstance(data, dict) or data.get("id") != job_id or not isinstance(data.get("estado"), str):
            return {"status": "unavailable", "message": "No se pudo consultar el trabajo en Molcy."}
        safe: dict[str, Any] = {"status": "ok", "job_id": job_id, "job_state": data["estado"][:20],
                                "source": "MolDesign GET /molcy/trabajos"}
        if isinstance(data.get("formato"), str):
            safe["format"] = data["formato"][:30]
        if isinstance(data.get("fase"), str):
            safe["phase"] = data["fase"][:60]
        if isinstance(data.get("motivo"), str):
            safe["reason"] = data["motivo"][:300]
        progress = data.get("progreso")
        if isinstance(progress, dict) and all(type(progress.get(key)) is int for key in ("fotogramas", "total")):
            safe["progress"] = {"frames": progress["fotogramas"], "total": progress["total"]}
        if type(data.get("restante_render_principal_s")) is int:
            safe["remaining_seconds"] = data["restante_render_principal_s"]
        if data["estado"] == "completo":
            safe["note"] = "El vídeo terminó; se abre y se guarda desde la pestaña Molcy, en la carpeta del caso."
        return safe

    schema = {"type": "object", "properties": {"job_id": {"type": "string", "maxLength": 36}},
              "required": ["job_id"], "additionalProperties": False}
    return Tool("get_molcy_video_status", "Solo lectura. Consulta en Molcy cómo va un vídeo que la persona ya confirmó (job_id de la "
                "tarjeta). No inicia, cancela ni reintenta nada.", schema, status)
