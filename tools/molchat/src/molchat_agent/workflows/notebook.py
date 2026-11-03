"""The agent's notebook: what was asked, what was approved, what each step really did.

It is written by the host from the run's record, never by the model, so it cannot claim a deed that did not
happen. Every number carries the source that produced it (MolDesign's Vina energy, MolDesign's physical controls)
and every step that did not happen says why. The notebook is evidence of the run, not a result of the science.

It is written in the language of the plan (see ``lang``): every label sits here in both languages, side by side.

The PDF needs ``reportlab`` (optional). Without it the notebook is still produced as JSON and Markdown and says
the PDF could not be written; nothing downstream pretends otherwise.
"""
from __future__ import annotations

import copy
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..lang import current, tr, using
from .iteration import SCHEMA, IterationOutcome

NOTEBOOK_SCHEMA = "moldesign.molchat.notebook/1"

_STATUS = {"evaluated": ("evaluada", "docked"), "failed": ("falló", "failed"),
           "timeout": ("sin terminar a tiempo", "did not finish in time"), "unknown": ("sin confirmar", "not confirmed"),
           "skipped": ("no se evaluó", "not docked"), "pending": ("pendiente", "pending")}
_OUTCOME = {"qualifies": ("cumple la regla", "meets the rule"),
            "near": ("energía suficiente, controles físicos no superados", "energy enough, physical checks not passed"),
            "below_threshold": ("no llega al umbral", "does not reach the threshold")}
# MolDesign's severity codes (services/avisos.py: Severidad) are Spanish words; the label follows the notebook's language.
_SEVERITY = {"positiva": ("positiva", "positive"), "info": ("info", "info"), "precaucion": ("precaución", "caution"),
             "critica": ("crítica", "critical"), "heredada": ("heredada", "legacy")}
_STATE = {"completed":("Terminó: hay una molécula que cumple la regla.", "Finished: one molecule meets the rule."),
          "none_qualified": ("Terminó: ninguna molécula cumplió la regla.", "Finished: no molecule met the rule."),
          "blocked": ("Se detuvo antes de evaluar: el caso no quedó preparado.",
                      "Stopped before docking: the case was not set up."),
          "budget_exhausted": ("Se agotó el tiempo total del plan; lo no evaluado queda declarado.",
                               "The plan's total time ran out; what was not docked is declared.")}
_LIMITS = ("La energía de Vina es la de la mejor pose según Vina: no es una energía libre, ni un Ki, ni una medida de "
           "actividad. Una iteración sobre pocas moléculas no ordena fármacos. Los controles físicos son los de PoseBusters "
           "tal como los declara MolDesign.",
           "The Vina energy is that of Vina's best pose: it is not a free energy, nor a Ki, nor a measure of activity. "
           "An iteration over a few molecules does not rank drugs. The physical checks are PoseBusters' as MolDesign "
           "declares them.")
LIMITS = _LIMITS[0]


def _pick(table: dict[str, tuple[str, str]], key: str | None, default: str) -> str:
    pair = table.get(key or "")
    return tr(*pair) if pair else default


def _fmt(value: Any, unit: str = "") -> str:
    return "—" if value is None else f"{value:g}{unit}"


def _unrecorded() -> str:
    return tr("sin registrar", "not recorded")


def build_notebook(outcome: IterationOutcome, *, approved_at: str | None, finished_at: str | None = None,
                   versions: dict[str, str] | None = None) -> dict[str, Any]:
    """The notebook as data. Same input, same output: the timestamps are arguments, not read from the clock."""
    spec = outcome.spec
    rows = []
    for record in outcome.records:
        rows.append({"n": record.index, "name": record.name, "smiles": record.smiles,
                     "status": _pick(_STATUS, record.status, record.status), "status_code": record.status,
                     "vina_kcal_mol": record.affinity_kcal, "physical_controls": record.physical_status,
                     "reading": _pick(_OUTCOME, record.outcome, record.reason or ""), "reason": record.reason,
                     "task_id": record.task_id, "seconds": record.seconds,
                     "timing": {"waiting_case_s": record.seconds_waiting_case, "case_state_before": record.case_state_before,
                                "to_start_s": record.seconds_to_start, "to_result_s": record.seconds_to_result},
                     "source": copy.deepcopy(record.source), "run": copy.deepcopy(record.run)})
    selected = next((r for r in outcome.records if r.index == outcome.selected), None)
    runs = [row["run"] for row in rows if isinstance(row["run"], dict)]
    vina = sorted({run["vina_version"] for run in runs if run.get("vina_version")})
    if vina and not versions:
        versions = {"vina": ", ".join(vina)}
    return {
        "schema": NOTEBOOK_SCHEMA, "iteration_schema": SCHEMA, "lang": current(),
        "case": spec["case_name"], "receptor": spec["pdb_id"],
        "request": spec.get("original_request") or "", "approved_at": approved_at, "finished_at": finished_at,
        "plan_digest": outcome.digest, "plan": _plan_lines(spec), "state": outcome.state,
        "state_text": _pick(_STATE, outcome.state, outcome.state),
        "rule": {"threshold_kcal_mol": spec["threshold_kcal"], "require_physical": spec["require_physical"],
                 "stop": spec["stop"]},
        "molecules": rows,
        "selected": None if selected is None else {"n": selected.index, "name": selected.name, "task_id": selected.task_id,
                                                   "vina_kcal_mol": selected.affinity_kcal,
                                                   "physical_controls": selected.physical_status},
        "saved": outcome.saved, "video": outcome.video, "preparation": outcome.preparation,
        "deliverable": outcome.deliverable, "notes": list(outcome.notes), "limits": tr(*_LIMITS),
        "comparability": comparability(runs),
        "provenance": tr("Las energías, los controles físicos, el protocolo, los avisos y la especie acoplada los dio "
                         "MolDesign; la identidad de cada molécula, la consulta de PubChem de esta conversación cuyo SMILES "
                         "coincide literalmente. MolChat ordenó las llamadas, anotó lo ocurrido y escribió este cuaderno "
                         "sin intervención del modelo.",
                         "The energies, the physical checks, the protocol, the warnings and the docked species came from "
                         "MolDesign; each molecule's identity, from the PubChem lookup of this conversation whose SMILES "
                         "matches literally. MolChat ordered the calls, recorded what happened and wrote this notebook "
                         "without the model."),
        "versions": versions or {}}


_COMPARED = (("receptor_sha256", ("receptor preparado", "prepared receptor")),
             ("vina_version", ("versión de Vina", "Vina version")))
_COMPARED_PROTOCOL = (("engine", ("motor", "engine")), ("exhaustiveness", ("exhaustividad", "exhaustiveness")),
                      ("num_poses", ("poses", "poses")), ("seed", ("semilla", "seed")),
                      ("box_center", ("centro de la caja", "box center")), ("box_size", ("tamaño de la caja", "box size")))


def comparability(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether the evaluated molecules ran under the same conditions, field by field, from what each run recorded.

    A field a run did not record is «not recorded», never assumed equal: comparing scores is only fair when the
    receptor, the engine and the search were the same, and that is exactly what a reader cannot see in a table.
    """
    if not runs:
        return {"runs": 0, "same": [], "different": [], "not_recorded": []}
    fields = [(key, tr(*label), lambda run, key=key: run.get(key)) for key, label in _COMPARED]
    fields += [(key, tr(*label), lambda run, key=key: (run.get("protocol") or {}).get(key))
               for key, label in _COMPARED_PROTOCOL]
    same, different, missing = [], [], []
    for key, label, read in fields:
        values = [read(run) for run in runs]
        if any(value is None for value in values):
            missing.append(label)
            continue
        distinct = list(dict.fromkeys(json.dumps(value, sort_keys=True) for value in values))  # in the molecules' order
        if len(distinct) == 1:
            same.append({"field": label, "value": values[0]})
        else:
            different.append({"field": label, "values": [json.loads(text) for text in distinct]})
    return {"runs": len(runs), "same": same, "different": different, "not_recorded": missing}


def _plan_lines(spec: dict[str, Any]) -> list[str]:
    from .iteration import IterationSpec
    return IterationSpec.from_dict(spec).card_lines()


_MATCH = {"exact": ("el SMILES coincide con el de PubChem", "the SMILES matches PubChem's"),
          "connectivity_only": ("el SMILES coincide sólo con la conectividad de PubChem: se usó sin su estereoquímica",
                                "the SMILES matches only PubChem's connectivity: it was used without its stereochemistry")}


def source_line(source: dict[str, Any] | None) -> str:
    if not isinstance(source, dict):
        return tr("Procedencia: no registrada (el SMILES no coincide literalmente con ninguna consulta de PubChem de "
                  "esta conversación).",
                  "Source: not recorded (the SMILES does not match literally any PubChem lookup of this conversation).")
    if source.get("match") == "ambiguous":
        cids = ", ".join(map(str, source["cids"]))
        return tr(f"Procedencia: ambigua; el SMILES coincide con varios compuestos de PubChem (CID {cids}).",
                  f"Source: ambiguous; the SMILES matches several PubChem compounds (CID {cids}).")
    name = source.get("name") or tr("sin nombre", "no name")
    query = (tr(f", búsqueda «{source['query']}»", f", search “{source['query']}”") if source.get("query") else "")
    match = _pick(_MATCH, source.get("match"), source.get("match") or "")
    return (tr(f"Procedencia: PubChem CID {source['cid']} («{name}»{query}); ",
               f"Source: PubChem CID {source['cid']} (“{name}”{query}); ")
            + f"{match}." + (f" {source['url']}" if source.get("url") else ""))


def _n(count: Any, one: str, many: str) -> str:
    return f"{count} {one if count == 1 else many}"


def _alternatives(count: Any) -> str:
    return _n(count, tr("alternativa", "alternative"), tr("alternativas", "alternatives"))


def run_lines(run: dict[str, Any] | None) -> list[str]:
    """What MolDesign recorded about one run, in plain lines; nothing derived, nothing added."""
    if not isinstance(run, dict):
        return []
    out: list[str] = []
    species = run.get("species") or {}
    written, docked = species.get("input_smiles"), species.get("docked_smiles_3d")
    if written or docked:
        same = written is not None and written == docked
        out.append(tr(f"SMILES de entrada (canónico): {written or 'no registrado'}; especie acoplada (desde el 3D): "
                      f"{docked or 'no registrada'}",
                      f"Input SMILES (canonical): {written or 'not recorded'}; docked species (from the 3D): "
                      f"{docked or 'not recorded'}") + (tr(" (la misma).", " (the same).") if same else "."))
    proton, tauto, stereo = species.get("protonation") or {}, species.get("tautomer") or {}, species.get("stereo") or {}
    alternatives = lambda item: (f", {_alternatives(item['alternatives'])}"  # noqa: E731
                                 if isinstance(item.get("alternatives"), int) else "")
    if proton.get("applied") is True:
        ph = proton.get("ph")
        out.append(tr("Protonación: ", "Protonation: ")
                   + (f"{tr('a', 'at')} pH {ph:g}" if isinstance(ph, (int, float)) else tr("aplicada", "applied"))
                   + alternatives(proton) + ".")
    elif proton.get("applied") is False:
        out.append(tr("Protonación: no aplicada", "Protonation: not applied")
                   + (f" ({proton['reason']})" if proton.get("reason") else "") + ".")
    if tauto.get("applied") is not None:
        out.append(tr("Tautómero: ", "Tautomer: ")
                   + (tr("canonicalizado", "canonicalized") if tauto.get("applied") else tr("el de entrada", "the input one"))
                   + alternatives(tauto) + ".")
    centers, doubles = stereo.get("unassigned_centers"), stereo.get("unassigned_double_bonds")
    if isinstance(centers, int) or isinstance(doubles, int):
        shown_centers = centers if isinstance(centers, int) else "—"
        shown_doubles = doubles if isinstance(doubles, int) else "—"
        out.append(tr(f"Estereoquímica sin asignar en la entrada: {shown_centers} centros y {shown_doubles} dobles enlaces.",
                      f"Unassigned stereochemistry in the input: {shown_centers} centers and {shown_doubles} double bonds."))
    lost = stereo.get("lost_in_docked_species") or {}
    if lost.get("centros") or lost.get("dobles"):
        out.append(tr("La especie acoplada perdió estereoquímica escrita: ",
                      "The docked species lost written stereochemistry: ")
                   + _n(lost.get("centros", 0), tr("centro", "center"), tr("centros", "centers")) + tr(" y ", " and ")
                   + _n(lost.get("dobles", 0), tr("doble enlace", "double bond"), tr("dobles enlaces", "double bonds")) + ".")
    protocol = run.get("protocol") or {}
    if protocol:
        parts = [f"{protocol.get('engine') or tr('motor no registrado', 'engine not recorded')} {run.get('vina_version') or ''}".strip()]
        for key, label in (("exhaustiveness", tr("exhaustividad", "exhaustiveness")), ("num_poses", "poses"),
                           ("seed", tr("semilla", "seed"))):
            parts.append(f"{label} {protocol[key]}" if protocol.get(key) is not None
                         else f"{label} {tr('no registrada', 'not recorded')}")
        if protocol.get("box_center") and protocol.get("box_size"):
            parts.append(tr(f"caja centro {protocol['box_center']} tamaño {protocol['box_size']} Å",
                            f"box center {protocol['box_center']} size {protocol['box_size']} Å"))
        out.append(tr("Protocolo ejecutado: ", "Protocol run: ") + ", ".join(parts) + ".")
        if protocol.get("requested"):
            out.append(tr(f"Se pidió otra cosa y MolDesign ejecutó la de arriba: {protocol['requested']}.",
                          f"Something else was requested and MolDesign ran the one above: {protocol['requested']}."))
    warnings = run.get("warnings")
    if warnings is None:
        out.append(tr("Avisos de la corrida: no registrados.", "Run warnings: not recorded."))
    elif not warnings:
        out.append(tr("Avisos de la corrida: ninguno.", "Run warnings: none."))
    else:
        out.append(tr(f"Avisos de la corrida ({len(warnings)}):", f"Run warnings ({len(warnings)}):"))
        out += [f"  - [{_pick(_SEVERITY, w.get('severity'), w.get('severity') or tr('sin severidad', 'no severity'))}] "
                f"{w['message']}" + (f" ({w['code']})" if w.get("code") else "") for w in warnings]
    return out


def comparability_lines(c: dict[str, Any]) -> list[str]:
    if not c.get("runs"):
        return [tr("Ninguna molécula llegó a evaluarse: no hay condiciones que comparar.",
                   "No molecule was docked: there are no conditions to compare.")]
    out = [tr(f"Sobre las {c['runs']} corridas evaluadas:", f"Across the {c['runs']} docked runs:")]
    if c["same"]:
        out.append(tr("- Iguales en todas: ", "- The same in all: ")
                   + "; ".join(f"{item['field']} {item['value']}" for item in c["same"]) + ".")
    for item in c["different"]:
        values = " / ".join(map(str, item["values"]))
        out.append(tr(f"- Distinto entre corridas: {item['field']} ({values}). "
                      "Las energías no se comparan en las mismas condiciones.",
                      f"- Different between runs: {item['field']} ({values}). "
                      "The energies are not compared under the same conditions."))
    if c["not_recorded"]:
        out.append(tr("- Sin registrar en alguna corrida: ", "- Not recorded in some run: ") + ", ".join(c["not_recorded"])
                   + tr("; no se da por igual.", "; not assumed equal."))
    return out


def _title(nb: dict[str, Any]) -> str:
    return tr(f"Cuaderno del agente — {nb['case']}", f"Agent notebook — {nb['case']}")


def _meta(nb: dict[str, Any]) -> list[str]:
    return [f"Receptor: {nb['receptor']}", tr("Aprobado: ", "Approved: ") + (nb["approved_at"] or _unrecorded()),
            tr("Terminó: ", "Finished: ") + (nb["finished_at"] or _unrecorded())]


def _request(nb: dict[str, Any]) -> str:
    return nb["request"] or tr("(no se guardó el texto original)", "(the original text was not kept)")


def _failed_lines(nb: dict[str, Any]) -> list[str]:
    return [tr(f"Molécula {row['n']} ({row['name']}): {row['reason']}", f"Molecule {row['n']} ({row['name']}): {row['reason']}")
            for row in nb["molecules"] if row["reason"] and row.get("status_code", "evaluated") != "evaluated"]


def _selected_line(nb: dict[str, Any]) -> str:
    sel = nb["selected"]
    if sel is None:
        return tr("Ninguna molécula quedó seleccionada.", "No molecule was selected.")
    physical = sel["physical_controls"] or tr("no evaluados", "not evaluated")
    return tr(f"{sel['name']} (tarea {sel['task_id']}): Vina {_fmt(sel['vina_kcal_mol'], ' kcal/mol')}, "
              f"controles físicos {physical}.",
              f"{sel['name']} (task {sel['task_id']}): Vina {_fmt(sel['vina_kcal_mol'], ' kcal/mol')}, "
              f"physical checks {physical}.")


def _followups() -> tuple[tuple[str, str], ...]:
    return (("Moldex", "saved"), (tr("Vídeo de Molcy", "Molcy video"), "video"), (tr("Preparación", "Preparation"), "preparation"),
            (tr("Entrega", "Delivery"), "deliverable"))


def render_markdown(nb: dict[str, Any]) -> str:
    """In the notebook's own language, whatever the caller's."""
    with using(nb.get("lang", "es")):
        return _render_markdown(nb)


def _render_markdown(nb: dict[str, Any]) -> str:
    out = [f"# {_title(nb)}", ""]
    out += [f"- {line}" for line in _meta(nb)] + [tr("- Huella del plan: ", "- Plan digest: ") + f"`{nb['plan_digest']}`", ""]
    out += [tr("## Lo que se pidió", "## What was asked"), "", _request(nb), ""]
    out += [tr("## Lo que se aprobó", "## What was approved"), ""] + [f"- {line}" for line in nb["plan"]] + [""]
    out += [tr("## Qué ocurrió", "## What happened"), "", nb["state_text"], ""]
    out += [tr("| # | Molécula | Estado | Vina (kcal/mol) | Controles físicos | Lectura |",
               "| # | Molecule | Status | Vina (kcal/mol) | Physical checks | Reading |"), "|---|---|---|---|---|---|"]
    for row in nb["molecules"]:
        out.append(f"| {row['n']} | {row['name']} | {row['status']} | {_fmt(row['vina_kcal_mol'])} | "
                   f"{row['physical_controls'] or '—'} | {row['reading']} |")
    out.append("")
    out += [f"- {line}" for line in _failed_lines(nb)]
    timed = [row for row in nb["molecules"] if any(v is not None for v in (row.get("timing") or {}).values())]
    if timed:
        out += ["", tr("### Tiempos medidos", "### Measured times"), "",
                tr("Espera del caso: hasta que la ventana dijo que la corrida anterior había cerrado. Resultado: desde que "
                   "arrancó la corrida hasta que el backend la dio por terminada con su energía.",
                   "Case wait: until the window said the previous run had closed. Result: from the start of the run until "
                   "the backend declared it finished with its energy."), ""]
        for row in timed:
            t = row["timing"]
            before = t["case_state_before"] or tr("sin respuesta", "no answer")
            out.append(tr(f"- Molécula {row['n']} ({row['name']}): espera del caso {_fmt(t['waiting_case_s'], ' s')} "
                          f"(«{before}»), arranque {_fmt(t['to_start_s'], ' s')}, "
                          f"resultado {_fmt(t['to_result_s'], ' s')}, total {_fmt(row['seconds'], ' s')}.",
                          f"- Molecule {row['n']} ({row['name']}): case wait {_fmt(t['waiting_case_s'], ' s')} "
                          f"(“{before}”), start {_fmt(t['to_start_s'], ' s')}, "
                          f"result {_fmt(t['to_result_s'], ' s')}, total {_fmt(row['seconds'], ' s')}."))
    out += ["", tr("## Condiciones de las corridas", "## Run conditions"), ""] + comparability_lines(nb.get("comparability") or {})
    out += ["", tr("## Registro por molécula", "## Record per molecule"), "",
            tr("Lo que MolDesign registró de cada corrida y de dónde salió cada SMILES, tal cual; nada se interpreta aquí.",
               "What MolDesign recorded about each run and where each SMILES came from, as is; nothing is interpreted here."), ""]
    for row in nb["molecules"]:
        out.append(f"### {row['n']}. {row['name']}")
        out += ["", tr("- SMILES del plan: ", "- SMILES in the plan: ") + f"`{row['smiles']}`", f"- {source_line(row.get('source'))}"]
        out += [f"- {line}" if not line.startswith("  ") else line for line in run_lines(row.get("run"))]
        if row.get("task_id"):
            out.append(tr("- Tarea: ", "- Task: ") + row["task_id"])
        out.append("")
    out += [tr("## Lo que se hizo con la elegida", "## What was done with the chosen one"), "", _selected_line(nb)]
    for label, key in _followups():
        item = nb[key]
        if item is not None:
            out.append(f"- {label}: {_describe(item)}")
    if nb["notes"]:
        out += ["", tr("## Anotaciones", "## Notes"), ""] + [f"- {note}" for note in nb["notes"]]
    out += ["", tr("## Límites y procedencia", "## Limits and provenance"), "", nb["limits"], "", nb["provenance"], ""]
    return "\n".join(out)


def _describe(item: dict[str, Any]) -> str:
    parts = [str(item.get("status") or item.get("final") or item.get("job_state") or tr("sin estado", "no state"))]
    for key in ("message", "job_id", "readiness", "file", "sha256"):
        if item.get(key):
            parts.append(f"{key}: {item[key]}")
    return " · ".join(parts)


def notebook_json(nb: dict[str, Any]) -> bytes:
    return (json.dumps(nb, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


# ── PDF (optional) ──────────────────────────────────────────────────────────────────────────────────

_TRANSLIT = {"≤": "<=", "≥": ">=", "−": "-", "—": "-", "–": "-", "·": "-", "“": '"', "”": '"', "’": "'", "→": "->"}


def _system_fonts() -> tuple[tuple[str, str], ...]:
    """Regular and bold font files to try, in order. The Windows folder comes from the environment, never a literal path."""
    root = os.environ.get("SystemRoot")
    windows = ((str(Path(root) / "Fonts" / "arial.ttf"), str(Path(root) / "Fonts" / "arialbd.ttf")),) if root else ()
    return windows + (("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),)


_FONT_CANDIDATES = _system_fonts()


def pdf_available() -> bool:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def render_pdf(nb: dict[str, Any]) -> bytes | None:
    """The notebook as a PDF, or ``None`` when ``reportlab`` is not installed. Deterministic for equal input."""
    with using(nb.get("lang", "es")):
        return _render_pdf(nb)


def _render_pdf(nb: dict[str, Any]) -> bytes | None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        from xml.sax.saxutils import escape
    except ImportError:
        return None

    regular, bold, unicode_ok = "Helvetica", "Helvetica-Bold", False
    for normal_path, bold_path in _FONT_CANDIDATES:
        if Path(normal_path).is_file() and Path(bold_path).is_file():
            try:
                pdfmetrics.registerFont(TTFont("MolChatSans", normal_path))
                pdfmetrics.registerFont(TTFont("MolChatSans-Bold", bold_path))
                regular, bold, unicode_ok = "MolChatSans", "MolChatSans-Bold", True
                break
            except Exception:  # noqa: BLE001 - an unreadable font falls back to the built-in one
                continue

    def text(value: Any) -> str:
        shown = "" if value is None else str(value)
        if not unicode_ok:
            for char, replacement in _TRANSLIT.items():
                shown = shown.replace(char, replacement)
        return escape(shown)

    body = ParagraphStyle("body", fontName=regular, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10.5)
    h1 = ParagraphStyle("h1", parent=body, fontName=bold, fontSize=16, leading=20, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=body, fontName=bold, fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=3)

    story: list[Any] = [Paragraph(text(_title(nb)), h1)]
    meta = _meta(nb) + [tr("Huella del plan: ", "Plan digest: ") + nb["plan_digest"]]
    story += [Paragraph(text(line), small) for line in meta]
    story += [Paragraph(text(tr("Lo que se pidió", "What was asked")), h2), Paragraph(text(_request(nb)), body),
              Paragraph(text(tr("Lo que se aprobó", "What was approved")), h2)]
    story += [Paragraph(text("• " + line), body) for line in nb["plan"]]
    story += [Paragraph(text(tr("Qué ocurrió", "What happened")), h2), Paragraph(text(nb["state_text"]), body), Spacer(1, 4)]

    head = ["#", tr("Molécula", "Molecule"), tr("Estado", "Status"), "Vina", tr("Controles", "Checks"),
            tr("Lectura", "Reading")]
    data = [[Paragraph(text(h), ParagraphStyle("th", parent=small, fontName=bold)) for h in head]]
    for row in nb["molecules"]:
        data.append([Paragraph(text(cell), small) for cell in (
            row["n"], row["name"], row["status"], _fmt(row["vina_kcal_mol"]), row["physical_controls"] or "—",
            row["reading"])])
    table = Table(data, colWidths=[8 * mm, 32 * mm, 26 * mm, 16 * mm, 24 * mm, 64 * mm], repeatRows=1)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF4")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(table)
    story += [Paragraph(text(line), small) for line in _failed_lines(nb)]
    story.append(Paragraph(text(tr("Condiciones de las corridas", "Run conditions")), h2))
    story += [Paragraph(text(line), small) for line in comparability_lines(nb.get("comparability") or {})]
    story.append(Paragraph(text(tr("Registro por molécula", "Record per molecule")), h2))
    for row in nb["molecules"]:
        story.append(Paragraph(text(f"{row['n']}. {row['name']}"), ParagraphStyle("h3", parent=body, fontName=bold)))
        lines = [tr("SMILES del plan: ", "SMILES in the plan: ") + row["smiles"], source_line(row.get("source"))] \
            + run_lines(row.get("run"))
        if row.get("task_id"):
            lines.append(tr("Tarea: ", "Task: ") + row["task_id"])
        story += [Paragraph(text(line.strip()), small) for line in lines]
        story.append(Spacer(1, 3))
    story.append(Paragraph(text(tr("Lo que se hizo con la elegida", "What was done with the chosen one")), h2))
    story.append(Paragraph(text(_selected_line(nb)), body))
    for label, key in _followups():
        if nb[key] is not None:
            story.append(Paragraph(text(f"{label}: {_describe(nb[key])}"), body))
    if nb["notes"]:
        story.append(Paragraph(text(tr("Anotaciones", "Notes")), h2))
        story += [Paragraph(text("• " + note), small) for note in nb["notes"]]
    story += [Paragraph(text(tr("Límites y procedencia", "Limits and provenance")), h2), Paragraph(text(nb["limits"]), small),
              Spacer(1, 3), Paragraph(text(nb["provenance"]), small)]

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                                 bottomMargin=16 * mm, title=_title(nb), author="MolChat", invariant=1)
    document.build(story)
    return buffer.getvalue()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
