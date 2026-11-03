"""Explain a finished evaluation: read-only facts, each with the condition MolDesign declares.

MolChat does not own the science. This reads what the lock already says about a run
(``GET /evaluation/status/{task_id}``) and keeps four facts: the Vina affinity and the
parameters that produced it, the receptor's calibration level, the scientific warnings
and whether the protocol is comparable with today's. Each fact carries its own limit,
taken from the lock's text when the lock has one.

The result is built from an allowlist, never by filtering: a field MolDesign adds later
(a local path, a composite score) does not reach the model until someone decides it
should. A field the lock did not declare is listed under ``absent`` and is never read as
good or as calibrated.
"""
from __future__ import annotations

import math
from typing import Any

from ..bridge import MolDesignBridge
from .harness_tools import fetch_job
from .tool_loop import Tool

#: Appended to the system prompt of the hosted chat. Static: no user data is formatted in.
EXPLAIN_GUIDANCE = (
    "Si el usuario pide explicar, interpretar o entender el resultado de una evaluación terminada, usa "
    "explain_evaluation con su task_id y explica solo con los hechos devueltos. Cita cada valor con su "
    "condición (receptor, versión de Vina, exhaustividad, número de poses, semilla) y con las cifras con que "
    "llega, sin redondear más. Si el nivel de calibración no es «calibrado», dilo antes de interpretar la "
    "afinidad; si lo es, di el n, el intervalo y la condición de la medida. Lee los avisos científicos con su "
    "texto y su severidad. Un campo ausente significa «no declarado», nunca «bueno» ni «calibrado». No "
    "recomiendes sintetizar, descartar ni priorizar una molécula por este resultado. ")

_AFFINITY_LIMIT = ("Energía de la mejor pose según Vina. No es una energía libre, ni un Ki, ni una medida de actividad.")
_RHO_READING = ("La ρ describe cómo ordena el motor una serie de análogos de este receptor; no predice el Ki de una molécula.")
_READING_RULES = (
    "Cita cada valor con su condición.",
    "Si la calibración no es «calibrado», dilo antes de interpretar la afinidad.",
    "Ausente significa no declarado, nunca bueno ni calibrado.",
)


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _text(value: Any, limit: int) -> str | None:
    return value.strip()[:limit] or None if isinstance(value, str) else None


def _condition(result: dict[str, Any]) -> dict[str, Any]:
    protocol = result.get("docking_protocol") if isinstance(result.get("docking_protocol"), dict) else {}
    condition: dict[str, Any] = {}
    if (engine := _text(protocol.get("engine"), 40)):
        condition["engine"] = engine
    if (version := _text(result.get("vina_version"), 40)):
        condition["vina_version"] = version
    for key in ("exhaustiveness", "num_poses"):
        if type(protocol.get(key)) is int:
            condition[key] = protocol[key]
    seed = result.get("vina_random_seed") if type(result.get("vina_random_seed")) is int else protocol.get("seed")
    if type(seed) is int:
        condition["seed"] = seed
    if (name := _text(result.get("target_name"), 120)):
        condition["receptor"] = name
    return condition


def _calibration(result: dict[str, Any]) -> dict[str, Any]:
    cal = result.get("target_calibracion")
    if not isinstance(cal, dict) or _text(cal.get("nivel"), 40) is None:
        return {"level": None, "note": "La corrida no declara la calibración del receptor; ausente no significa calibrado."}
    entry: dict[str, Any] = {"level": cal["nivel"].strip()[:40], "summary": _text(cal.get("resumen"), 300),
                             "warning": _text(cal.get("advertencia"), 600), "reason": _text(cal.get("motivo"), 300),
                             "backing": None}
    backing = cal.get("respaldo")
    if isinstance(backing, dict) and _number(backing.get("rho")) is not None:
        interval = backing.get("ic95")
        low, high = (interval if isinstance(interval, list) and len(interval) == 2 else (None, None))
        measured: dict[str, Any] = {"spearman_rho": backing["rho"], "n": _number(backing.get("n")),
                                    "panel": _text(backing.get("panel"), 200), "endpoint": _text(backing.get("endpoint"), 200)}
        if _number(low) is not None and _number(high) is not None:
            # The lock names the field ``ic95``: the level is part of the contract, so it is a fact.
            measured["ci95"] = [low, high]
            measured["ci_level_percent"] = 95
            measured["ci_excludes_zero"] = low > 0 or high < 0
        entry["backing"] = measured
        entry["reading"] = _RHO_READING
    elif _number(cal.get("rho_registrada_sin_respaldo")) is not None:
        entry["recorded_rho_without_backing"] = cal["rho_registrada_sin_respaldo"]
        entry["recorded_rho_note"] = "Valor escrito en la fila del receptor, sin n, intervalo ni protocolo. No concede calibración."
    return entry


def _warnings(result: dict[str, Any]) -> dict[str, Any] | None:
    raw = result.get("scientific_warnings")
    if not isinstance(raw, list):
        return None
    items: list[dict[str, Any]] = []
    for warning in raw[:12]:
        if isinstance(warning, dict):
            items.append({"code": _text(warning.get("codigo"), 60), "severity": _text(warning.get("severidad"), 30),
                          "message": _text(warning.get("mensaje"), 300)})
        elif isinstance(warning, str):
            items.append({"code": None, "severity": "heredada", "message": _text(warning, 300)})
    return {"count": len(raw), "shown": len(items), "items": items}


def _protocol(result: dict[str, Any]) -> dict[str, Any] | None:
    protocol = result.get("protocolo")
    if not isinstance(protocol, dict):
        return None
    current = protocol.get("vigente")
    differences = protocol.get("diferencias")
    return {"comparable_with_today": current if isinstance(current, bool) else None,
            "differences": [_text(item, 60) for item in differences[:5] if _text(item, 60)] if isinstance(differences, list) else []}


def build_evaluation_facts(task_id: str, job: dict[str, Any]) -> dict[str, Any]:
    """The explainable facts of one job, from an allowlist; see the module docstring."""
    out: dict[str, Any] = {"status": "ok", "task_id": task_id, "task_status": job["status"],
                           "source": "MolDesign GET /evaluation/status"}
    result = job.get("result")
    if job["status"] != "SUCCESS" or not isinstance(result, dict):
        out["status"] = "not_ready"
        if type(job.get("progress")) is int:
            out["progress"] = job["progress"]
        if (error := _text(job.get("error"), 300)):
            out["error"] = error
        out["message"] = "La evaluación no terminó con un resultado; no hay nada que explicar todavía."
        return out
    absent: list[str] = []
    affinity = _number(result.get("affinity_kcal"))
    if affinity is None:
        out["affinity"] = None
        absent.append("affinity_kcal")
    else:
        out["affinity"] = {"value": affinity, "unit": "kcal/mol", "scope": "mejor pose", "limit": _AFFINITY_LIMIT,
                           "condition": _condition(result)}
    out["calibration"] = _calibration(result)
    if out["calibration"]["level"] is None:
        absent.append("target_calibracion")
    out["warnings"] = _warnings(result)
    if out["warnings"] is None:
        absent.append("scientific_warnings")
    out["protocol"] = _protocol(result)
    if out["protocol"] is None:
        absent.append("protocolo")
    out["absent"] = absent
    out["reading_rules"] = list(_READING_RULES)
    return out


def declared_limits(facts: dict[str, Any]) -> str:
    """The calibration as the lock declares it, for the host to append to the answer.

    A model can call a receptor calibrated when it is not; no check on numbers sees that.
    This is the lock's own sentence, added after the model's text so the two can be read together.
    """
    calibration = facts.get("calibration") or {}
    if calibration.get("level") is None:
        return "Calibración del receptor: MolDesign no la declara en esta corrida; ausente no significa calibrado."
    parts = [f"Calibración declarada por MolDesign: {calibration.get('summary') or calibration['level']}."]
    if calibration.get("warning"):
        parts.append(calibration["warning"])
    return " ".join(parts)


def evidence_values(facts: dict[str, Any]) -> dict[str, str]:
    """The short rows the interface shows for these facts."""
    values: dict[str, str] = {}
    affinity = facts.get("affinity")
    if isinstance(affinity, dict):
        values["afinidad Vina (kcal/mol)"] = str(affinity["value"])
        for key, label in (("vina_version", "versión de Vina"), ("exhaustiveness", "exhaustividad"),
                           ("num_poses", "poses"), ("seed", "semilla"), ("receptor", "receptor")):
            if key in affinity["condition"]:
                values[label] = str(affinity["condition"][key])
    calibration = facts.get("calibration") or {}
    values["calibración"] = str(calibration.get("level") or "no declarada")
    backing = calibration.get("backing")
    if isinstance(backing, dict):
        values["ρ de Spearman"] = str(backing["spearman_rho"])
        if "ci95" in backing:
            values["IC 95 %"] = f"{backing['ci95'][0]} a {backing['ci95'][1]}"
        if backing.get("n") is not None:
            values["n"] = str(backing["n"])
    warnings = facts.get("warnings")
    values["avisos científicos"] = str(warnings["count"]) if isinstance(warnings, dict) else "no declarados"
    protocol = facts.get("protocol")
    if isinstance(protocol, dict):
        comparable = protocol["comparable_with_today"]
        values["protocolo comparable con el vigente"] = "sí" if comparable is True else "no" if comparable is False else "no determinable"
    return values


def explain_evaluation_tool(bridge: MolDesignBridge) -> Tool:
    """Read-only: the lock's own account of a finished run, with its conditions."""
    async def explain(args: dict[str, Any]) -> dict[str, Any]:
        task_id = args["task_id"].strip()
        job, abstention = await fetch_job(bridge, task_id)
        if abstention is not None:
            return abstention
        return build_evaluation_facts(task_id, job)

    schema = {"type": "object", "properties": {"task_id": {"type": "string", "maxLength": 128}},
              "required": ["task_id"], "additionalProperties": False}
    return Tool("explain_evaluation", "Solo lectura. Lee en MolDesign una evaluación terminada (task_id de evaluate_case) y "
                "devuelve sus hechos con las condiciones que MolDesign declara: la afinidad de Vina y con qué parámetros, el nivel "
                "de calibración del receptor, los avisos científicos y si el protocolo es comparable con el vigente. Úsala cuando "
                "el usuario pida explicar o interpretar un resultado. No inicia, cancela, reintenta ni guarda nada.",
                schema, explain)
