"""An iteration the person approved once: a fixed list of molecules, a stop rule and a deterministic loop.

The model never loops. It reads the request, extracts the parameters (case, receptor, molecules, threshold) and
proposes a ``IterationSpec``; the host validates it, shows it on a card and runs it only after one click that is
bound to the spec's digest. From then on nothing waits for a person: every molecule is its own attempt, a failure
is recorded and the loop goes on, and the stop rule is written down before the first molecule is evaluated.

What the loop decides is narrow and stated on the card: a molecule qualifies when Vina's energy for its best pose
is at or below the threshold AND (unless the person turned it off) MolDesign's physical controls for that pose
passed. Energy alone is never enough: a pose that Vina likes and PoseBusters rejects is recorded as ``near``
and does not stop the loop. MolChat computes nothing; both numbers are read from MolDesign.

Science stays in the lock. This module only orders calls, keeps the record and says what happened.
"""
from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
import re
import time
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from ..lang import tr
from .evaluation import EvaluationStep

SCHEMA = "moldesign.molchat.iteration/1"
MAX_MOLECULES = 12
MAX_NAME = 80
MAX_SMILES = 500
THRESHOLD_RANGE = (-30.0, 0.0)
STOPS = ("first", "all")
SCENES = ("resultado", "receptor", "busqueda", "ensamble")
FORMATS = ("horizontal", "vertical", "previsualizacion")

_PDB = re.compile(r"[A-Za-z0-9_-]{1,64}")
_CASE_OK = frozenset({"created", "exists"})
_RECEPTOR_OK = frozenset({"applied", "already_selected"})


class SpecError(ValueError):
    """The proposed iteration is not valid; the message says which field and why."""


def _clean(text: Any, field_name: str, maximum: int) -> str:
    if not isinstance(text, str):
        raise SpecError(f"{field_name} debe ser texto.")
    value = text.strip()
    if not value or len(value) > maximum:
        raise SpecError(f"{field_name} debe tener entre 1 y {maximum} caracteres.")
    if any(unicodedata.category(char) in {"Cc", "Cf", "Cs"} for char in value):
        raise SpecError(f"{field_name} contiene caracteres de control.")
    return value


# Molcy's scenes as its tab names them in each language (MolDesign frontend/app/molcy/page.tsx).
_SCENE_NAMES = {"resultado": ("resultado", "Result"), "receptor": ("receptor", "Receptor"), "busqueda": ("búsqueda", "Search"),
                "ensamble": ("ensamble", "Ensemble")}

@dataclass(frozen=True)
class Molecule:
    name: str
    smiles: str


_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
RECEPTOR_VIEWS = ("automatico", "visible", "oculto")
ENSEMBLE_VARIANTS = ("lenta", "detallada", "referencia")
# Every presentation control Molcy's tab offers, with the name the model uses and the one Molcy's schema uses.
_COLORS = (("receptor_color", "color del receptor"), ("residue_color", "color de los residuos destacados"),
           ("polar_color", "color de las líneas polares"), ("apolar_color", "color de las líneas apolares"))
_SWITCHES = (("labels", "etiquetas"), ("contacts", "contactos"), ("previous_sample", "muestra anterior"))
VIDEO_FIELDS = {"scene", "format", "title", "receptor", "ensemble_variant"} | {k for k, _ in _COLORS} | {k for k, _ in _SWITCHES}


@dataclass(frozen=True)
class VideoRequest:
    scene: str
    format: str
    title: str | None = None
    receptor: str = "automatico"  # automatico | visible | oculto
    receptor_color: str | None = None  # None = Molcy's automatic colour
    residue_color: str | None = None
    polar_color: str | None = None
    apolar_color: str | None = None
    labels: bool = True
    contacts: bool = True
    previous_sample: bool = True  # only in the search scene
    ensemble_variant: str = "lenta"  # only in the ensemble scene

    def presentation(self) -> dict[str, Any]:
        """Molcy's own presentation schema, as its tab stores it with the job."""
        return {"schema": "moldesign.presentacion/1", "titulo": self.title, "color_receptor": self.receptor_color,
                "color_residuos": self.residue_color, "colores_lineas": {"polar": self.polar_color, "apolar": self.apolar_color},
                "receptor": self.receptor, "muestra_anterior": self.previous_sample, "etiquetas": self.labels,
                "contactos": self.contacts}

    def as_dict(self) -> dict[str, Any]:
        return {"scene": self.scene, "format": self.format, "title": self.title, "receptor": self.receptor,
                "receptor_color": self.receptor_color, "residue_color": self.residue_color, "polar_color": self.polar_color,
                "apolar_color": self.apolar_color, "labels": self.labels, "contacts": self.contacts,
                "previous_sample": self.previous_sample, "ensemble_variant": self.ensemble_variant}

    def customized(self) -> list[str]:
        """What differs from Molcy's automatic presentation, in words for the card."""
        out = []
        if self.title:
            out.append(f"título «{self.title}»")
        if self.receptor != "automatico":
            out.append("receptor " + ("visible" if self.receptor == "visible" else "oculto"))
        out += [f"{label} {value}" for (key, label), value in zip(_COLORS, (self.receptor_color, self.residue_color,
                                                                             self.polar_color, self.apolar_color)) if value]
        out += [f"sin {label}" for (key, label) in _SWITCHES if not getattr(self, key)
                and (key != "previous_sample" or self.scene == "busqueda")]
        if self.scene == "ensamble" and self.ensemble_variant != "lenta":
            out.append(f"movimiento del ensamble: {self.ensemble_variant}")
        return out

    @classmethod
    def from_dict(cls, raw: Any) -> "VideoRequest":
        if not isinstance(raw, dict) or set(raw) - VIDEO_FIELDS:
            raise SpecError(f"video admite {', '.join(sorted(VIDEO_FIELDS))}.")
        if raw.get("scene") not in SCENES or raw.get("format", "horizontal") not in FORMATS:
            raise SpecError("video necesita una escena y un formato válidos.")
        title = _clean(raw["title"], "title del vídeo", 80) if raw.get("title") is not None else None
        receptor = raw.get("receptor", "automatico")
        if receptor not in RECEPTOR_VIEWS:
            raise SpecError("video.receptor debe ser automatico, visible u oculto.")
        colors = {}
        for key, label in _COLORS:
            value = raw.get(key)
            if value is not None and not (isinstance(value, str) and _HEX.fullmatch(value)):
                raise SpecError(f"video.{key} ({label}) debe ser un color #RRGGBB.")
            colors[key] = value.upper() if isinstance(value, str) else None
        switches = {}
        for key, label in _SWITCHES:
            value = raw.get(key, True)
            if not isinstance(value, bool):
                raise SpecError(f"video.{key} ({label}) debe ser verdadero o falso.")
            switches[key] = value
        variant = raw.get("ensemble_variant", "lenta")
        if variant not in ENSEMBLE_VARIANTS:
            raise SpecError("video.ensemble_variant debe ser lenta, detallada o referencia.")
        return cls(raw["scene"], raw.get("format", "horizontal"), title, receptor, colors["receptor_color"],
                   colors["residue_color"], colors["polar_color"], colors["apolar_color"], switches["labels"],
                   switches["contacts"], switches["previous_sample"], variant)


@dataclass(frozen=True)
class IterationSpec:
    case_name: str
    pdb_id: str
    molecules: tuple[Molecule, ...]
    threshold_kcal: float
    stop: str = "first"
    require_physical: bool = True
    save: bool = True
    video: VideoRequest | None = None
    preparation: bool = False
    package: bool = False
    original_request: str = ""
    per_molecule_timeout_s: int = 420
    budget_s: int = 2400

    @classmethod
    def from_dict(cls, data: Any) -> "IterationSpec":
        if not isinstance(data, dict):
            raise SpecError("La iteración debe ser un objeto.")
        known = {"case_name", "pdb_id", "molecules", "threshold_kcal", "stop", "require_physical", "save", "video",
                 "preparation", "package", "original_request", "per_molecule_timeout_s", "budget_s"}
        if set(data) - known:
            raise SpecError(f"Campos desconocidos: {sorted(set(data) - known)}.")
        for required in ("case_name", "pdb_id", "molecules", "threshold_kcal"):
            if required not in data:
                raise SpecError(f"Falta {required}.")
        case_name = _clean(data["case_name"], "case_name", 100)
        pdb_id = _clean(data["pdb_id"], "pdb_id", 64).upper()
        if not _PDB.fullmatch(pdb_id):
            raise SpecError("pdb_id no es un identificador de receptor válido.")
        raw = data["molecules"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_MOLECULES:
            raise SpecError(f"La lista debe tener entre 1 y {MAX_MOLECULES} moléculas.")
        molecules: list[Molecule] = []
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, dict) or set(item) - {"name", "smiles"} or "smiles" not in item:
                raise SpecError(f"Molécula {index}: indica name (opcional) y smiles.")
            smiles = _clean(item["smiles"], f"smiles de la molécula {index}", MAX_SMILES)
            if re.search(r"\s", smiles):
                raise SpecError(f"smiles de la molécula {index} no puede llevar espacios.")
            name = _clean(item.get("name") or f"molécula {index}", f"name de la molécula {index}", MAX_NAME)
            molecules.append(Molecule(name, smiles))
        if len({m.smiles for m in molecules}) != len(molecules):
            raise SpecError("La lista repite un SMILES: cada molécula se evalúa una sola vez.")
        threshold = data["threshold_kcal"]
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
            raise SpecError("threshold_kcal debe ser un número.")
        if not THRESHOLD_RANGE[0] <= threshold < THRESHOLD_RANGE[1]:
            raise SpecError("threshold_kcal debe ser negativo (la energía de Vina buena es más baja) y no menor que -30.")
        stop = data.get("stop", "first")
        if stop not in STOPS:
            raise SpecError("stop debe ser first o all.")
        for key in ("require_physical", "save", "preparation", "package"):
            if key in data and not isinstance(data[key], bool):
                raise SpecError(f"{key} debe ser verdadero o falso.")
        video = VideoRequest.from_dict(data["video"]) if data.get("video") is not None else None
        save = data.get("save", True)
        if video is not None and not save:
            save = True  # a video can only come from a run saved in Moldex: say it on the card, not silently
        request = data.get("original_request", "")
        if not isinstance(request, str) or len(request) > 4000:
            raise SpecError("original_request debe ser texto de hasta 4000 caracteres.")
        timeout = data.get("per_molecule_timeout_s", 420)
        budget = data.get("budget_s", 2400)
        for label, value, low, high in (("per_molecule_timeout_s", timeout, 30, 1800), ("budget_s", budget, 60, 7200)):
            if type(value) is not int or not low <= value <= high:
                raise SpecError(f"{label} debe ser un entero entre {low} y {high}.")
        return cls(case_name, pdb_id, tuple(molecules), float(threshold), stop, data.get("require_physical", True), save,
                   video, data.get("preparation", False), data.get("package", False), request, timeout, budget)

    def as_dict(self) -> dict[str, Any]:
        return {"case_name": self.case_name, "pdb_id": self.pdb_id,
                "molecules": [{"name": m.name, "smiles": m.smiles} for m in self.molecules],
                "threshold_kcal": self.threshold_kcal, "stop": self.stop, "require_physical": self.require_physical,
                "save": self.save,
                "video": None if self.video is None else self.video.as_dict(),
                "preparation": self.preparation, "package": self.package, "original_request": self.original_request,
                "per_molecule_timeout_s": self.per_molecule_timeout_s, "budget_s": self.budget_s}

    @property
    def digest(self) -> str:
        normal = json.dumps({"schema": SCHEMA, **self.as_dict()}, sort_keys=True, ensure_ascii=False,
                            separators=(",", ":"))
        return "sha256:" + sha256(normal.encode("utf-8")).hexdigest()

    def card_lines(self) -> list[str]:
        """What the approval card shows: everything the run will do, and the rule that stops it."""
        rule = f"Vina ≤ {self.threshold_kcal:g} kcal/mol"
        if self.require_physical:
            rule += tr(" y controles físicos de la mejor pose superados", " and the best pose passes the physical checks")
        names = ", ".join(m.name for m in self.molecules)
        stop = (tr("en la primera que cumple", "at the first one that meets it") if self.stop == "first"
                else tr("al recorrer la lista entera", "after the whole list"))
        lines = [tr(f"Caso «{self.case_name}» · receptor {self.pdb_id}", f"Case “{self.case_name}” · receptor {self.pdb_id}"),
                 tr(f"{len(self.molecules)} moléculas, una tras otra en este mismo caso: ",
                    f"{len(self.molecules)} molecules, one after another in this same case: ") + names,
                 tr(f"Se detiene {stop}: {rule}", f"Stops {stop}: {rule}"),
                 tr("Si una molécula falla, se anota y se sigue con la siguiente.",
                    "If a molecule fails, it is noted and the next one goes on.")]
        if self.save:
            lines.append(tr("La que cumpla se guarda en Moldex.", "The one that meets it is saved to Moldex."))
        if self.video is not None:
            shown = {"previsualizacion": tr("prueba (vista previa corta)", "test (short preview)")}.get(self.video.format, self.video.format)
            scene = _SCENE_NAMES.get(self.video.scene, (self.video.scene, self.video.scene))
            lines.append(tr(f"Vídeo de Molcy (solo GPU): escena {scene[0]}, formato {shown}; "
                            "el cierre de MolDesign se añade siempre.",
                            f"Molcy video (GPU only): scene {scene[1]}, format {shown}; "
                            "MolDesign's closing is always added."))
            custom = self.video.customized()
            lines.append(tr("Presentación: ", "Presentation: ")
                         + ("; ".join(custom) if custom else tr("la automática de Molcy", "Molcy's automatic one")) + ".")
        if self.preparation:
            lines.append(tr("Se audita la corrida en Preparación; si queda en revisión, se declara, no se decide.",
                            "The run is audited in Preparation; if it needs review, that is declared, not decided."))
        if self.package:
            lines.append(tr("Al final se junta todo en un único ZIP.", "At the end everything goes into a single ZIP."))
        lines.append(tr(f"Tope: {self.per_molecule_timeout_s // 60} min por molécula y {self.budget_s // 60} min en total.",
                        f"Limit: {self.per_molecule_timeout_s // 60} min per molecule and {self.budget_s // 60} min in total."))
        return lines


# ── Ports: what the loop needs from the host's interface and from MolDesign ─────────────────────────


class HostPort(Protocol):
    """The interface in the person's window. Each call returns the host's closed status vocabulary."""
    async def create_case(self, name: str) -> dict[str, Any]: ...
    async def assign_receptor(self, case_name: str, pdb_id: str) -> dict[str, Any]: ...
    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]: ...
    async def evaluate(self, case_name: str) -> dict[str, Any]: ...
    async def case_status(self, case_name: str) -> dict[str, Any]: ...  # read-only: can the case take another molecule?


class PlatformPort(Protocol):
    """MolDesign over HTTP, with the person's session."""
    async def job(self, task_id: str) -> dict[str, Any]: ...
    async def top_pose(self, task_id: str) -> dict[str, Any]: ...
    async def save(self, task_id: str, molecule_id: str, name: str | None) -> dict[str, Any]: ...
    async def request_video(self, task_id: str, molecule_id: str, video: VideoRequest) -> dict[str, Any]: ...
    async def video_status(self, job_id: str) -> dict[str, Any]: ...


Emit = Callable[[dict[str, Any]], None]


@dataclass
class MoleculeRecord:
    index: int
    name: str
    smiles: str
    status: str = "pending"  # pending | evaluated | failed | timeout | unknown | skipped
    outcome: str | None = None  # qualifies | near | below_threshold (only when evaluated)
    task_id: str | None = None
    molecule_id: str | None = None
    affinity_kcal: float | None = None
    physical_status: str | None = None
    reason: str | None = None
    seconds: float | None = None
    seconds_waiting_case: float | None = None  # until the window said the previous run was closed
    case_state_before: str | None = None  # what the window answered (idle, busy, unknown...)
    seconds_to_start: float | None = None
    seconds_to_result: float | None = None  # run start → backend terminal: when the number was known
    source: dict[str, Any] | None = None  # where the SMILES came from (a PubChem lookup of this conversation), if known
    run: dict[str, Any] | None = None  # protocol, warnings and docked species as MolDesign returned them

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self.__dict__)


@dataclass
class IterationOutcome:
    spec: dict[str, Any]
    digest: str
    state: str = "running"  # completed | none_qualified | blocked | budget_exhausted
    records: list[MoleculeRecord] = field(default_factory=list)
    selected: int | None = None  # index of the molecule the rest of the plan used
    saved: dict[str, Any] | None = None
    video: dict[str, Any] | None = None
    preparation: dict[str, Any] | None = None
    deliverable: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "spec": copy.deepcopy(self.spec), "digest": self.digest, "state": self.state,
                "records": [r.as_dict() for r in self.records], "selected": self.selected, "saved": self.saved,
                "video": self.video, "preparation": self.preparation, "deliverable": self.deliverable,
                "notes": list(self.notes)}



def judge(spec: IterationSpec, affinity: float | None, physical: str | None) -> tuple[str, str]:
    """``(outcome, reason)`` for one evaluated molecule, from numbers MolDesign returned."""
    if affinity is None:
        return "below_threshold", tr("MolDesign no devolvió la energía de Vina.", "MolDesign did not return the Vina energy.")
    if affinity > spec.threshold_kcal:
        return "below_threshold", tr(f"Vina {affinity:g} kcal/mol no llega al umbral de {spec.threshold_kcal:g}.",
                                     f"Vina {affinity:g} kcal/mol does not reach the {spec.threshold_kcal:g} threshold.")
    if spec.require_physical and physical != "passed":
        shown = physical or tr("no evaluados", "not evaluated")
        return "near", tr(f"Vina {affinity:g} kcal/mol llega al umbral, pero los controles físicos de la mejor pose "
                          f"quedaron «{shown}»: no cumple la regla.",
                          f"Vina {affinity:g} kcal/mol reaches the threshold, but the best pose's physical checks "
                          f"came out “{shown}”: it does not meet the rule.")
    return "qualifies", tr(f"Vina {affinity:g} kcal/mol y controles físicos superados.",
                           f"Vina {affinity:g} kcal/mol and physical checks passed.")


def _could_not(what: str) -> str:
    return tr(f"No se pudo {what}", f"Could not {what}")


async def _noop_sleep(_: float) -> None:
    return None


class IterationRunner:
    def __init__(self, spec: IterationSpec, host: HostPort, platform: PlatformPort, emit: Emit | None = None, *,
                 clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 poll_s: float = 3.0, busy_wait_s: float = 5.0, busy_budget_s: float = 240.0,
                 sources: list[dict[str, Any] | None] | None = None) -> None:
        self.spec, self.host, self.platform = spec, host, platform
        self._emit = emit or (lambda _event: None)
        self._clock, self._sleep = clock, sleep
        self._poll_s, self._busy_wait_s, self._busy_budget_s = poll_s, busy_wait_s, busy_budget_s
        self._plan_started = clock()
        self.outcome = IterationOutcome(spec.as_dict(), spec.digest,
                                        records=[MoleculeRecord(i, m.name, m.smiles)
                                                 for i, m in enumerate(spec.molecules, start=1)])
        for record, source in zip(self.outcome.records, sources or []):
            record.source = copy.deepcopy(source)

    def emit(self, kind: str, **data: Any) -> None:
        self._emit({"type": "workflow", "event": kind, **data})

    def _record(self, index: int) -> MoleculeRecord:
        return self.outcome.records[index - 1]

    async def run(self) -> IterationOutcome:
        out, spec = self.outcome, self.spec
        started = self._plan_started = self._clock()
        self.emit("started", digest=out.digest, molecules=len(spec.molecules))
        if not await self._prepare_case():
            out.state = "blocked"
            for record in out.records:
                record.status, record.reason = "skipped", tr("El caso no quedó preparado: no se evaluó nada.",
                                                             "The case was not set up: nothing was docked.")
            self.emit("finished", state=out.state)
            return out
        qualifiers: list[MoleculeRecord] = []
        for record in out.records:
            if qualifiers and spec.stop == "first":
                record.status, record.reason = "skipped", tr("Ya se cumplió la regla de parada.", "The stop rule was already met.")
                continue
            if self._clock() - started >= spec.budget_s:
                record.status, record.reason = "skipped", tr("Se agotó el tiempo total del plan.", "The plan's total time ran out.")
                out.state = "budget_exhausted"
                continue
            await self._run_one(record)
            shown = record.as_dict()
            if isinstance(shown.get("run"), dict):
                shown["run"].pop("raw", None)  # the card needs the summary; the full copy stays in the notebook
            self.emit("molecule", record=shown)
            if record.outcome == "qualifies":
                qualifiers.append(record)
        if qualifiers:
            best = min(qualifiers, key=lambda r: (r.affinity_kcal if r.affinity_kcal is not None else 0.0, r.index))
            out.selected = best.index
            if out.state == "running":
                out.state = "completed"
            await self._after_selection(best)
        elif out.state == "running":
            out.state = "none_qualified"
            out.notes.append(tr("Ninguna molécula cumplió la regla: no se guardó nada ni se pidió el vídeo.",
                                "No molecule met the rule: nothing was saved and no video was requested."))
        self.emit("finished", state=out.state)
        return out

    async def _prepare_case(self) -> bool:
        spec, out = self.spec, self.outcome
        for key, label, call, ok in (("case", tr("crear el caso", "create the case"), lambda: self.host.create_case(spec.case_name), _CASE_OK),
                                     ("receptor", tr("asignar el receptor", "assign the receptor"),
                                      lambda: self.host.assign_receptor(spec.case_name, spec.pdb_id), _RECEPTOR_OK)):
            try:
                result, waited = await self._until_free(label, call)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - the plan must end with an honest state, never hang
                out.notes.append(_could_not(label) + f": {type(exc).__name__}.")
                return False
            status = result.get("status") if isinstance(result, dict) else None
            # «key» is stable; «step» is the label in the plan's language (the card used to compare the Spanish one)
            self.emit("case_step", step=label, key=key, status=status)
            if status not in ok:
                answered = status or tr("sin respuesta", "no answer")
                out.notes.append(_could_not(label) + ": " + (
                    tr(f"MolDesign siguió ocupado {waited:.0f} s.", f"MolDesign stayed busy for {waited:.0f} s.") if status == "busy"
                    else tr(f"el host respondió «{answered}».", f"the host answered “{answered}”.")))
                return False
            if status == "exists":
                out.notes.append(tr("El caso ya existía: se reutilizó con su nombre; sus inputs se reemplazan molécula a molécula.",
                                    "The case already existed: it was reused by name; its inputs are replaced molecule by molecule."))
        return True

    async def _until_free(self, label: str, call: Callable[[], Awaitable[dict[str, Any]]]) -> tuple[dict[str, Any], float]:
        """One call to the host, repeated while MolDesign answers «busy». Returns the last answer and the seconds waited.

        «busy» means the window is still closing something else: the interface keeps the case locked until the previous
        run is fully closed, and in development that took about 45 s after Vina had already finished. Nothing was done,
        so asking again is safe, and it is the only status that is ever repeated (``unknown`` may have done something).
        The wait is bounded by ``busy_budget_s`` and by what is left of the plan's own time.
        """
        waited, announced = 0.0, False
        while True:
            result = await call()
            if not isinstance(result, dict) or result.get("status") != "busy":
                break
            left = self.spec.budget_s - (self._clock() - self._plan_started)
            if waited + self._busy_wait_s > self._busy_budget_s or self._busy_wait_s > left:
                break
            if not announced:
                announced = True
                self.emit("phase", message=tr(f"MolDesign sigue cerrando la corrida anterior; espero a que esté libre para {label}.",
                                              f"MolDesign is still closing the previous run; waiting until it is free to {label}."))
            await self._sleep(self._busy_wait_s)
            waited += self._busy_wait_s
        if announced:
            self.emit("phase", message=None)
        return result, waited

    def _left(self) -> float:
        return self.spec.budget_s - (self._clock() - self._plan_started)

    async def _run_one(self, record: MoleculeRecord) -> None:
        """One molecule: wait for the case to be free, evaluate, decide on the number. The decision is made as soon
        as the backend gives Vina's energy; whether the window has closed the run only matters for the next molecule."""
        began = self._clock()
        self.emit("molecule_started", index=record.index, name=record.name)
        step = EvaluationStep(self.host, self.platform, clock=self._clock, sleep=self._sleep, poll_s=self._poll_s,
                              busy_wait_s=self._busy_wait_s, busy_budget_s=self._busy_budget_s,
                              on_wait=lambda message: self.emit("phase", message=message))
        try:
            free = await step.wait_until_free(self.spec.case_name, self._left())
            record.case_state_before, record.seconds_waiting_case = free.status, free.seconds
            if free.status in {"not_found", "ambiguous"}:
                record.status = "failed"
                record.reason = tr(f"MolDesign no encontró un único caso «{self.spec.case_name}» ({free.status}).",
                                   f"MolDesign did not find a single case “{self.spec.case_name}” ({free.status}).")
            else:
                reading = await step.evaluate(self.spec.case_name, record.smiles,
                                              timeout_s=self.spec.per_molecule_timeout_s, budget_s=self._left())
                record.status, record.reason, record.task_id = reading.status, reading.reason, reading.task_id
                record.molecule_id, record.affinity_kcal = reading.molecule_id, reading.vina_kcal
                record.physical_status, record.run = reading.physical_status, reading.run
                record.seconds_to_start, record.seconds_to_result = reading.seconds_to_start, reading.seconds_to_result
                if reading.retried_for == "memoria":
                    ok = reading.status == "evaluated"
                    self.outcome.notes.append(tr(
                        f"Molécula {record.index} ({record.name}): a Vina le faltó memoria del equipo; "
                        "se repitió una vez" + (" y salió bien." if ok else " y volvió a fallar."),
                        f"Molecule {record.index} ({record.name}): Vina ran out of memory on this computer; "
                        "it was repeated once" + (" and worked." if ok else " and failed again.")))
                if reading.status == "evaluated":
                    record.outcome, record.reason = judge(self.spec, record.affinity_kcal, record.physical_status)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - one molecule never stops the others
            record.status, record.reason = "failed", tr(f"Error inesperado ({type(exc).__name__}); se siguió con la siguiente.",
                                                        f"Unexpected error ({type(exc).__name__}); moved on to the next one.")
        record.seconds = round(self._clock() - began, 1)

    async def _after_selection(self, best: MoleculeRecord) -> None:
        """Save, ask for the video and follow it. Each step is its own attempt and its own line in the record."""
        spec, out = self.spec, self.outcome
        if spec.save and best.task_id and best.molecule_id:
            out.saved = await self._guarded(tr("guardar en Moldex", "save to Moldex"),
                                            self.platform.save(best.task_id, best.molecule_id, best.name))
            self.emit("saved", result=out.saved)
        if spec.video is not None and best.task_id and best.molecule_id:
            if out.saved is None or out.saved.get("status") not in {"saved", "already_saved"}:
                out.video = {"status": "not_requested", "message": tr(
                    "No se pidió el vídeo porque la corrida no quedó guardada en Moldex.",
                    "The video was not requested because the run was not saved to Moldex.")}
            else:
                out.video = await self._guarded(tr("pedir el vídeo", "request the video"), self._request_video(best))
            self.emit("video", result=out.video)
        # Preparation and the package are added by the callers that own those ports (see runner_extras).

    async def _request_video(self, best: MoleculeRecord) -> dict[str, Any]:
        """The video is asked to the Molcy tab, which chooses the run, the scene and the format in view and presses its
        own button (``molcy_render``), so the person sees what the agent does. A host without that action falls back
        to asking MolDesign's backend directly. «unknown» is never retried: the tab may have started a render."""
        video = self.spec.video
        assert video is not None and best.task_id and best.molecule_id
        render = getattr(self.host, "render_video", None)
        if render is None:
            result = await self.platform.request_video(best.task_id, best.molecule_id, video)
            dropped = [item for item in video.customized() if not item.startswith("título")]
            if dropped and isinstance(result, dict):
                dropped_text = "; ".join(dropped)
                result = {**result, "message": f"{result.get('message') or ''} " + tr(
                    f"Esta vía no aplica la presentación pedida ({dropped_text}): el vídeo sale con la automática.",
                    f"This route does not apply the requested presentation ({dropped_text}): the video uses the automatic one.")}
                result["message"] = result["message"].strip()
            return result
        self.emit("phase", message=tr("Preparando el vídeo en la pestaña de Molcy.", "Setting up the video in the Molcy tab."))
        answer = await render(best.task_id, video.scene, video.format, video)
        status = answer.get("status") if isinstance(answer, dict) else None
        if status == "started" and isinstance(answer.get("job_id"), str):
            return {"status": "started", "job_id": answer["job_id"], "message": tr(
                "Vídeo en cola en Molcy (lanzado desde su pestaña).", "Video queued in Molcy (started from its tab).")}
        reason = answer.get("reason") if isinstance(answer, dict) and isinstance(answer.get("reason"), str) else None
        messages = {"not_found": tr("La corrida no aparece entre las guardadas en Moldex.", "The run is not among those saved in Moldex."),
                    "unavailable": tr("Molcy no puede generar el vídeo ahora.", "Molcy cannot make the video right now."),
                    "busy": tr("Molcy está ocupado con otro trabajo.", "Molcy is busy with another job."),
                    "unknown": tr("No se pudo confirmar si Molcy empezó el vídeo; no se repitió.",
                                  "Could not confirm whether Molcy started the video; it was not repeated.")}
        return {"status": status or "failed", "message": (messages.get(status or "", tr("Molcy no empezó el vídeo.",
                                                                                         "Molcy did not start the video."))
                                                          + (f" {reason}" if reason else ""))}

    async def _guarded(self, what: str, call: Awaitable[dict[str, Any]]) -> dict[str, Any]:
        try:
            result = await call
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            self.outcome.notes.append(_could_not(what) + f": {type(exc).__name__}.")
            return {"status": "failed", "message": _could_not(what) + "."}
        return result if isinstance(result, dict) else {"status": "failed", "message": _could_not(what) + "."}

    async def follow_video(self, timeout_s: int = 1800) -> dict[str, Any] | None:
        """Wait for the Molcy job the loop started; the video is the slow step and Preparación runs meanwhile."""
        video = self.outcome.video
        job_id = video.get("job_id") if isinstance(video, dict) else None
        if not isinstance(job_id, str):
            return video
        deadline = self._clock() + timeout_s
        while True:
            status = await self._guarded(tr("consultar el vídeo", "check the video"), self.platform.video_status(job_id))
            video.update({"job_state": status.get("job_state"), "phase": status.get("phase"),
                          "progress": status.get("progress")})
            if status.get("job_state") in {"completo", "fallido", "cancelado"} or status.get("status") in {"not_found", "invalid"}:
                video["final"] = status.get("job_state") or status.get("status")
                return video
            if self._clock() >= deadline:
                video["final"] = "timeout"
                return video
            await self._sleep(self._poll_s * 2)
