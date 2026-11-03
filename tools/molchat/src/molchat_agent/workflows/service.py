"""Running an approved iteration end to end: the loop, the render, Preparación, the notebook and the one ZIP.

Three things live here and nothing else:

* ``PlatformHttp`` speaks to MolDesign with the person's session and reuses the checks the chat tools already do
  (the renderer exists, the scene exists, the run finished) so a plan cannot ask for what a card would have refused.
* ``HostRelay`` asks the person's window for the actions only the interface can do, over the same event stream and
  the same result endpoints as a chat turn, but outside a turn: an approved plan outlives the message that proposed it.
* ``execute`` orders the phases and writes down what each one did. The slow render and Preparación run at the same
  time; the ZIP waits for both and declares whatever one of them could not deliver.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
import re
import time
import uuid
from typing import Any, Protocol

import httpx

from ..bridge import MolDesignBridge
from ..conversation.harness_tools import fetch_job
from ..conversation.product_actions import _UUID, _http, _moldex_entry, prepare_video, run_save, run_video
from ..lang import current, tr, using
from .deliverable import build_deliverable, preparation_dir
from .notebook import build_notebook, notebook_json, now_iso, render_markdown, render_pdf
from .iteration import Emit, HostPort, IterationOutcome, IterationRunner, IterationSpec, VideoRequest

PROPOSAL_TTL_S = 900
MAX_PENDING = 5
MAX_VIDEO_BYTES = 600 * 1024 * 1024
MAX_PACKAGE_BYTES = 200 * 1024 * 1024
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_DISK_NAMES = {"cuaderno.md": "notebook.md", "cuaderno.json": "notebook.json", "cuaderno.pdf": "notebook.pdf",
               "entrega.zip": "delivery.zip"}


class PreparationPort(Protocol):
    """Audits the selected run in Preparación and exports MolDesign's own package. Never decides for the person."""
    async def audit_and_export(self, case_name: str, task_id: str, molecule_id: str) -> dict[str, Any]: ...


class PlatformHttp:
    """``PlatformPort`` over MolDesign's HTTP API, with the account's session."""

    def __init__(self, bridge: MolDesignBridge) -> None:
        self.bridge = bridge

    async def job(self, task_id: str) -> dict[str, Any]:
        job, abstention = await fetch_job(self.bridge, task_id)
        if job is None:  # a read that failed is not a verdict: the loop keeps polling until its own deadline
            return {"status": "UNAVAILABLE", "error": (abstention or {}).get("message")}
        return job

    async def top_pose(self, task_id: str) -> dict[str, Any]:
        code, data = await _http(self.bridge, "GET", f"/evaluation/pose-comparison/{task_id}",
                                 params={"left": "1", "right": "2"})
        left = data.get("left") if code == 200 and isinstance(data, dict) else None
        if not isinstance(left, dict) or left.get("found") is not True or not isinstance(left.get("physical_status"), str):
            return {"physical_status": None}
        return {"physical_status": left["physical_status"][:20]}

    async def save(self, task_id: str, molecule_id: str, name: str | None) -> dict[str, Any]:
        entry, _ = await _moldex_entry(self.bridge, {"task_id": task_id, "molecule_id": molecule_id})
        if entry is not None:
            return {"status": "already_saved", "task_id": task_id}
        return await run_save(self.bridge, {"task_id": task_id, "molecule_id": molecule_id, "name": name})

    async def request_video(self, task_id: str, molecule_id: str, video: VideoRequest) -> dict[str, Any]:
        args: dict[str, Any] = {"task_id": task_id, "scene": video.scene, "format": video.format}
        if video.title:
            args["title"] = video.title
        prepared = await prepare_video(self.bridge, args)
        if prepared["status"] != "ready":
            return {"status": prepared["status"], "message": prepared.get("message")}
        return await run_video(self.bridge, {**prepared["spec"], "save_first": False})

    async def post_json(self, path: str, body: dict[str, Any]) -> tuple[int, Any]:
        """``(status, json)`` of a POST with the account's session; ``(0, None)`` when MolDesign cannot be reached."""
        return await _http(self.bridge, "POST", path, body=body, timeout=180)

    async def post_bytes(self, path: str, body: dict[str, Any]) -> tuple[int, bytes, str | None]:
        """``(status, bytes, file name)`` of a POST whose answer is a file (MolDesign's package), untouched."""
        if not getattr(self.bridge, "token", None):
            return 0, b"", None
        try:
            response = await self.bridge.client.post(path, json=body, timeout=300, follow_redirects=False,
                                                     headers={"Authorization": f"Bearer {self.bridge.token}"})
        except httpx.RequestError:
            return 0, b"", None
        if len(response.content) > MAX_PACKAGE_BYTES:
            return response.status_code, b"", None
        match = re.search(r'filename="?([^";]+)"?', response.headers.get("content-disposition", ""))
        return response.status_code, response.content, match.group(1) if match else None

    async def video_status(self, job_id: str) -> dict[str, Any]:
        if not _UUID.fullmatch(job_id):
            return {"status": "invalid"}
        code, data = await _http(self.bridge, "GET", f"/molcy/trabajos/{job_id}")
        if code in (403, 404):
            return {"status": "not_found"}
        if code != 200 or not isinstance(data, dict) or data.get("id") != job_id or not isinstance(data.get("estado"), str):
            return {"status": "unavailable"}
        out: dict[str, Any] = {"status": "ok", "job_state": data["estado"][:20]}
        if isinstance(data.get("fase"), str):
            out["phase"] = data["fase"][:60]
        progress = data.get("progreso")
        if isinstance(progress, dict) and all(type(progress.get(k)) is int for k in ("fotogramas", "total")):
            out["progress"] = {"frames": progress["fotogramas"], "total": progress["total"]}
        return out

    async def fetch_video(self, job_id: str) -> tuple[str, bytes] | None:
        """The finished MP4 exactly as Molcy produced it, or ``None`` (never a partial file)."""
        if not _UUID.fullmatch(job_id) or not getattr(self.bridge, "token", None):
            return None
        try:
            response = await self.bridge.client.get(f"/molcy/trabajos/{job_id}/video", timeout=300, follow_redirects=False,
                                                    headers={"Authorization": f"Bearer {self.bridge.token}"})
        except httpx.RequestError:
            return None
        if response.status_code != 200 or not response.content or len(response.content) > MAX_VIDEO_BYTES:
            return None
        return f"molcy_{job_id[:8]}.mp4", response.content


class HostRelay:
    """``HostPort`` through the person's window: an event out on the stream, the answer back on a result endpoint."""

    def __init__(self, state: Any, owner: str, queue: "asyncio.Queue[dict[str, Any]]") -> None:
        self.state, self.owner, self.queue = state, owner, queue

    async def _ask(self, registry: dict[str, Any], kind: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        future = asyncio.get_running_loop().create_future()
        registry[request_id] = (self.owner, future)
        try:
            await self.queue.put({"type": kind, "request_id": request_id, **payload})
            try:
                return await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                return {"status": "unknown"}
        finally:
            registry.pop(request_id, None)

    async def create_case(self, name: str) -> dict[str, Any]:
        return await self._ask(self.state.case_requests, "case_create", {"name": name}, 60)

    async def assign_receptor(self, case_name: str, pdb_id: str) -> dict[str, Any]:
        return await self._ask(self.state.receptor_requests, "case_receptor", {"case_name": case_name, "pdb_id": pdb_id}, 60)

    async def load_smiles(self, case_name: str, smiles: str) -> dict[str, Any]:
        return await self._ask(self.state.smiles_requests, "case_smiles", {"case_name": case_name, "smiles": smiles}, 60)

    async def evaluate(self, case_name: str) -> dict[str, Any]:
        return await self._ask(self.state.evaluation_requests, "case_evaluation", {"case_name": case_name}, 150)

    async def case_status(self, case_name: str) -> dict[str, Any]:
        """Read-only: can the case take another molecule? The window answers idle or busy (closing the last run)."""
        return await self._ask(self.state.case_status_requests, "case_status", {"case_name": case_name}, 20)

    async def render_video(self, task_id: str, scene: str, format: str, video: VideoRequest | None = None) -> dict[str, Any]:
        """The Molcy tab prepares the video in view (run, scene, format and the presentation the plan approved) and
        presses its own button; it answers with the job it started."""
        chosen = video or VideoRequest(scene, format)
        payload: dict[str, Any] = {"task_id": task_id, "scene": scene, "format": format,
                                   "presentation": json.dumps({**chosen.presentation(), "ensamble_variante": chosen.ensemble_variant},
                                                              ensure_ascii=False, separators=(",", ":"), sort_keys=True)}
        return await self._ask(self.state.molcy_requests, "case_molcy", payload, 100)

    async def audit_preparation(self, case_name: str, task_id: str) -> dict[str, Any]:
        """Preparación audits the run in the person's window and hands back the case projection it built."""
        return await self._ask(self.state.preparation_requests, "case_preparation",
                               {"case_name": case_name, "task_id": task_id}, 130)


_PREPARATION_PROBLEMS = {
    "case_not_found": ("Ningún caso del usuario contiene esa corrida: no hay nada que auditar.",
                       "None of your cases holds that run: there is nothing to audit."),
    "case_mismatch": ("La corrida pertenece a otro caso que el indicado; no se entregó nada.",
                      "The run belongs to a different case than the one named; nothing was delivered."),
    "not_auditable": ("La corrida no está en un estado auditable (no terminó o no tiene molécula).",
                      "The run cannot be audited (it did not finish or has no molecule)."),
    "audit_failed": ("La auditoría de Preparación falló.", "The Preparation audit failed."),
    "busy": ("Preparación estaba atendiendo otra petición.", "Preparation was busy with another request."),
    "failed": ("La ventana de MolDesign no pudo atender la petición.", "The MolDesign window could not handle the request."),
    "unknown": ("No se pudo confirmar la auditoría; no se repitió.", "The audit could not be confirmed; it was not repeated."),
}


def _problem(status: str) -> str:
    return tr(*_PREPARATION_PROBLEMS.get(status, _PREPARATION_PROBLEMS["unknown"]))


class PreparationHttp:
    """Audits the selected run in Preparación and exports MolDesign's own package.

    The window builds the case projection (only it has the case); the audit and the package are MolDesign's, asked
    for here with the account's session. The state that goes in the notebook is the one MolDesign's endpoint
    returned, not the one the window reported. Human decisions are never created: whatever the case already holds
    travels as it is, and a REVISION or a BLOQUEADO is declared, not decided.
    """

    def __init__(self, platform: PlatformHttp, relay: HostRelay) -> None:
        self.platform, self.relay = platform, relay

    async def audit_and_export(self, case_name: str, task_id: str, molecule_id: str) -> dict[str, Any]:
        asked = await self.relay.audit_preparation(case_name, task_id)
        status = asked.get("status") if isinstance(asked, dict) else None
        if status != "audited":
            return {"status": status if status in _PREPARATION_PROBLEMS else "unknown",
                    "message": _problem(status),
                    **({"reason": asked["reason"]} if isinstance(asked.get("reason"), str) else {})}
        projection = asked.get("projection")
        if asked.get("molecule_id") != molecule_id or not isinstance(projection, dict):
            return {"status": "case_mismatch", "message": _problem("case_mismatch")}
        base = f"/evaluation/dossier/{molecule_id}"
        code, audit = await self.platform.post_json(f"{base}/preparacion", projection)
        if code != 200 or not isinstance(audit, dict) or audit.get("estado") not in {"BLOQUEADO", "REVISION", "TRANSFERIBLE"}:
            return {"status": "audit_failed", "message": tr("MolDesign no devolvió la auditoría de Preparación.",
                                                            "MolDesign did not return the Preparation audit.")}
        readiness = audit["estado"]
        label = readiness_label(readiness)
        blockers = [str(item)[:120] for item in (audit.get("bloqueantes") or [])][:10]
        review = [str(item)[:120] for item in (audit.get("en_revision") or [])][:10]
        out: dict[str, Any] = {"status": "audited", "readiness": readiness, "reason": str(audit.get("razon") or "")[:300],
                               "blockers": blockers, "in_review": review}
        code, blob, name = await self.platform.post_bytes(f"{base}/package", projection)
        if code != 200 or not blob:
            out.update(status="export_failed", message=tr(f"Preparación quedó en {label}, pero MolDesign no entregó el paquete.",
                                                          f"Preparation ended in {label}, but MolDesign did not deliver the package."))
            return out
        out.update(status="exported", package=(name or f"dossier_{_fname(task_id)}.zip", blob),
                   message=(tr(f"Preparación: {label}. ", f"Preparation: {label}. ") + (
                       tr("Nada propio del caso pide revisión.", "Nothing in the case asks for review.")
                       if readiness == "TRANSFERIBLE" else
                       tr(f"{len(blockers)} bloqueantes y {len(review)} requisitos en revisión; MolChat no los decidió.",
                          f"{len(blockers)} blockers and {len(review)} requirements under review; MolChat did not decide them."))))
        return out


# Preparation's state is a MolDesign code (Spanish); the plan's texts name it as MolDesign's English interface does.
_READINESS_EN = {"BLOQUEADO": "BLOCKED", "REVISION": "REVIEW", "TRANSFERIBLE": "TRANSFERABLE"}


def readiness_label(code: str | None) -> str | None:
    return tr(code, _READINESS_EN.get(code, code)) if code else code


@dataclass
class WorkflowProposal:
    id: str
    owner: str
    conv_id: str | None
    spec: IterationSpec
    expires: float
    state: str = "pending"  # pending | running | done | cancelled
    outcome: IterationOutcome | None = None
    approved_at: str | None = None
    files: dict[str, bytes] = field(default_factory=dict)
    saved_paths: dict[str, str] = field(default_factory=dict)
    summary: dict[str, Any] | None = None
    prep_package: tuple[str, bytes] | None = None  # MolDesign's Preparación package, byte for byte
    video_file: tuple[str, bytes] | None = None  # the MP4, once the background render finished
    folder: Path | None = None  # where the files were written; the finished render rewrites them there
    sources: list[dict[str, Any] | None] = field(default_factory=list)  # per molecule, from the conversation's PubChem lookups
    lang: str = "es"  # the language of the turn that proposed it: its events and notebook keep it

    def view(self) -> dict[str, Any]:
        with using(self.lang):  # read from any request, it shows the card in the plan's language
            return self._view()

    def _view(self) -> dict[str, Any]:
        spec = self.spec
        steps = ["case", "receptor", "molecules"] + (["moldex"] if spec.save else []) + (["video"] if spec.video else []) \
            + (["preparation"] if spec.preparation else []) + (["deliverable"] if spec.package else [])
        return {"id": self.id, "kind": "iteration", "digest": spec.digest, "title": tr("Iteración de moléculas", "Molecule iteration"),
                "lines": spec.card_lines(), "molecules": [m.name for m in spec.molecules], "steps": steps}


def new_workflow(workflows: dict[str, WorkflowProposal], owner: str, conv_id: str | None,
                 spec: IterationSpec) -> WorkflowProposal | None:
    now = time.monotonic()
    for key in [key for key, item in workflows.items() if item.state == "pending" and item.expires < now]:
        del workflows[key]
    if sum(1 for item in workflows.values() if item.owner == owner and item.state in {"pending", "running"}) >= MAX_PENDING:
        return None
    proposal = WorkflowProposal(uuid.uuid4().hex, owner, conv_id, spec, now + PROPOSAL_TTL_S, lang=current())
    workflows[proposal.id] = proposal
    return proposal


def workflow_answer(proposal: WorkflowProposal) -> str:
    """What the turn says once it left a plan: written by the host, so it cannot claim a done deed."""
    spec = proposal.spec
    return tr(f"Dejé preparado una iteración de {len(spec.molecules)} moléculas con el umbral de "
              f"{spec.threshold_kcal:g} kcal/mol; el receptor y las reglas están en la tarjeta. Todavía no se evaluó nada: "
              "revísala y apruébala con un solo botón; después no necesitará más intervención. Si no la apruebas, caduca.",
              f"I prepared an iteration over {len(spec.molecules)} molecule{'' if len(spec.molecules) == 1 else 's'} with a threshold of "
              f"{spec.threshold_kcal:g} kcal/mol; the receptor and the rules are on the card. Nothing has been docked yet: "
              "review it and approve it with one button; after that it needs nothing else from you. If you don't approve it, it expires.")


def workflow_outcome_text(proposal: WorkflowProposal) -> str:
    """The sentence the conversation keeps once the plan ended, written from the record (no model)."""
    summary = proposal.summary or {}
    counts = summary.get("counts") or {}
    done = counts.get("evaluated", 0)
    total = len(proposal.spec.molecules)
    parts = [tr(f"Iteración «{proposal.spec.case_name}» terminada: {done} de {total} moléculas evaluadas.",
                f"Iteration “{proposal.spec.case_name}” finished: {done} of {total} molecules docked.")]
    selected = summary.get("selected")
    if selected:
        energy = selected.get("vina_kcal_mol")
        physical = selected.get('physical_status') or tr('no evaluados', 'not evaluated')
        parts.append(tr(f"Cumplió la regla {selected['name']}: energía de Vina {energy:g} kcal/mol, controles físicos "
                        f"«{physical}» (tarea {selected['task_id']}).",
                        f"{selected['name']} met the rule: Vina energy {energy:g} kcal/mol, physical checks "
                        f"“{physical}” (task {selected['task_id']})."))
        for label, key in (("Moldex", "saved"), (tr("vídeo de Molcy", "Molcy video"), "video"),
                           (tr("Preparación", "Preparation"), "preparation")):
            if summary.get(key):
                parts.append(f"{label}: {summary[key]}.")
    else:
        parts.append(tr("Ninguna molécula cumplió la regla; no se guardó nada ni se pidió el vídeo.",
                        "No molecule met the rule; nothing was saved and no video was requested."))
    if "entrega.zip" in (summary.get("files") or {}):
        where = (summary.get("paths") or {}).get("entrega.zip")
        parts.append(tr("Entrega lista", "Delivery ready") + (f": {where}" if where else "."))
    return " ".join(parts)


def _fname(text: str) -> str:
    return _SAFE.sub("-", text).strip("-._")[:60] or "entrega"


async def execute(proposal: WorkflowProposal, host: HostPort, platform: PlatformHttp, emit: Emit, *,
                  preparation: PreparationPort | None = None, output_dir: Path | None = None,
                  runner_kwargs: dict[str, Any] | None = None) -> IterationOutcome:
    """Run an approved plan. It always ends with an honest record, whatever each phase managed to do.

    The video is not waited for: Molcy renders it in the background (minutes, on the GPU) while Preparación audits the
    run, and the notebook and the ZIP are written as soon as Preparación is done, with the video declared as still
    rendering. ``complete_video`` follows the render afterwards and rewrites the delivery with the MP4 in it.
    """
    spec = proposal.spec
    runner = IterationRunner(spec, host, platform, emit, sources=proposal.sources, **(runner_kwargs or {}))
    outcome = await runner.run()
    selected = next((r for r in outcome.records if r.index == outcome.selected), None)
    if outcome.video and outcome.video.get("job_id"):
        outcome.video["final"] = None
        emit({"type": "workflow", "event": "phase", "phase": "video",
              "message": tr("Molcy renderiza el vídeo en segundo plano; mientras tanto sigue el plan.",
                            "Molcy renders the video in the background; the plan goes on meanwhile.")})

    if spec.preparation:
        if selected is None or not selected.task_id or not selected.molecule_id:
            outcome.preparation = {"status": "not_run", "message": tr(
                "Ninguna molécula quedó seleccionada: no hay corrida que auditar.",
                "No molecule was selected: there is no run to audit.")}
        elif preparation is None:
            outcome.preparation = {"status": "unavailable", "message": tr(
                "Esta versión de MolDesign no permite auditar en Preparación desde el chat.",
                "This version of MolDesign cannot run the Preparation audit from the chat.")}
        else:
            emit({"type": "workflow", "event": "phase", "phase": "preparation",
                  "message": tr("Auditando la corrida en Preparación.", "Auditing the run in Preparation.")})
            try:
                outcome.preparation = await preparation.audit_and_export(spec.case_name, selected.task_id, selected.molecule_id)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                outcome.preparation = {"status": "failed", "message": tr(f"La auditoría falló ({type(exc).__name__}).",
                                                                         f"The audit failed ({type(exc).__name__}).")}

    prep_zip = outcome.preparation.pop("package", None) if isinstance(outcome.preparation, dict) else None
    proposal.prep_package = prep_zip if isinstance(prep_zip, tuple) and len(prep_zip) == 2 else None
    proposal.outcome = outcome
    _write_outputs(proposal, output_dir)
    emit({"type": "workflow", "event": "done", "summary": proposal.summary})
    return outcome


def video_pending(outcome: IterationOutcome | None) -> bool:
    video = outcome.video if outcome is not None else None
    return isinstance(video, dict) and isinstance(video.get("job_id"), str) and not video.get("final")


def _write_outputs(proposal: WorkflowProposal, output_dir: Path | None) -> None:
    """Notebook and delivery from what the plan has now. Called again when the background render finishes."""
    outcome, spec = proposal.outcome, proposal.spec
    assert outcome is not None
    finished = now_iso()
    if spec.package:
        outcome.deliverable = {"status": "building", "message": tr("Este cuaderno forma parte de la entrega.",
                                                                   "This notebook is part of the delivery.")}
    notebook = build_notebook(outcome, approved_at=proposal.approved_at, finished_at=finished)
    pdf = render_pdf(notebook)
    md, js = render_markdown(notebook).encode("utf-8"), notebook_json(notebook)
    files = {"cuaderno.md": md, "cuaderno.json": js}
    if pdf is not None:
        files["cuaderno.pdf"] = pdf
    if spec.package:
        missing: dict[str, str] = {}
        if proposal.video_file is None:
            missing["video/"] = _why_no_video(outcome)
        if proposal.prep_package is None:
            missing[preparation_dir()] = _why_no_preparation(outcome)
        blob, manifest = build_deliverable(spec.case_name, outcome.digest, notebook_pdf=pdf, notebook_md=md, notebook_json=js,
                                           preparation=proposal.prep_package, video=proposal.video_file, missing=missing)
        files["entrega.zip"] = blob
        outcome.deliverable = {"status": "ready", "pieces": len(manifest["pieces"]), "missing": len(manifest["missing"])}
    proposal.files = files
    if output_dir is not None:
        if proposal.folder is None:
            proposal.folder = output_dir / f"{_fname(spec.case_name)}-{finished.replace(':', '').replace('-', '')[:15]}"
        proposal.folder.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            # The keys are the API's names; on disk the person reads them in the plan's language.
            path = proposal.folder / (_DISK_NAMES.get(name, name) if current() == "en" else name)
            path.write_bytes(data)
            proposal.saved_paths[name] = str(path)
    proposal.summary = summarize(outcome, proposal)


async def complete_video(proposal: WorkflowProposal, platform: PlatformHttp, *, output_dir: Path | None = None,
                         poll_s: float = 6.0, timeout_s: float = 3600.0,
                         clock: Callable[[], float] = time.monotonic,
                         sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
    """Follow the background render and, when it ends, rewrite the notebook and the delivery with what came out."""
    outcome = proposal.outcome
    if outcome is None or not video_pending(outcome):
        return
    video = outcome.video
    deadline = clock() + timeout_s
    while True:
        try:
            status = await platform.video_status(video["job_id"])
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - a lost poll is retried until the deadline
            status = {}
        status = status if isinstance(status, dict) else {}
        video.update({"job_state": status.get("job_state"), "phase": status.get("phase"), "progress": status.get("progress")})
        if status.get("job_state") in {"completo", "fallido", "cancelado"} or status.get("status") in {"not_found", "invalid"}:
            video["final"] = status.get("job_state") or status.get("status")
            break
        if clock() >= deadline:
            video["final"] = "timeout"
            break
        proposal.summary = summarize(outcome, proposal)
        await sleep(poll_s)
    if video["final"] == "completo":
        fetched = await platform.fetch_video(video["job_id"])
        if fetched is None:
            video["file"] = tr("no se pudo descargar el MP4", "the MP4 could not be downloaded")
        else:
            proposal.video_file, video["file"] = fetched, fetched[0]
    _write_outputs(proposal, output_dir)


def _why_no_video(outcome: IterationOutcome) -> str:
    video = outcome.video
    if video is None:
        return (tr("El plan no pidió vídeo, o ninguna molécula cumplió la regla.",
                   "The plan did not ask for a video, or no molecule met the rule.") if outcome.selected is None
                else tr("El plan no pidió vídeo.", "The plan did not ask for a video."))
    if video.get("status") != "started":
        return tr("No se pidió el vídeo: ", "The video was not requested: ") + str(video.get('message') or video.get('status'))
    if not video.get("final"):
        return tr("Molcy sigue renderizando el vídeo en segundo plano; cuando termine, esta entrega se rehace con el MP4 "
                  "en la misma carpeta.",
                  "Molcy is still rendering the video in the background; when it ends, this delivery is rebuilt with the "
                  "MP4 in the same folder.")
    final = video.get('final') or tr('sin estado', 'no state')
    return tr(f"El vídeo terminó en «{final}»", f"The video ended as “{final}”") + (f"; {video['file']}" if video.get("file") else ".")


def _why_no_preparation(outcome: IterationOutcome) -> str:
    prep = outcome.preparation
    if prep is None:
        return tr("El plan no pidió auditar en Preparación.", "The plan did not ask for a Preparation audit.")
    return str(prep.get("message") or tr(f"Preparación terminó en «{prep.get('status')}».",
                                         f"Preparation ended as “{prep.get('status')}”."))


def summarize(outcome: IterationOutcome, proposal: WorkflowProposal) -> dict[str, Any]:
    """What the interface shows at the end. Plain facts from the record; no model text."""
    selected = next((r for r in outcome.records if r.index == outcome.selected), None)
    counts: dict[str, int] = {}
    for record in outcome.records:
        counts[record.status] = counts.get(record.status, 0) + 1
    return {"state": outcome.state, "counts": counts,
            "selected": None if selected is None else {"name": selected.name, "task_id": selected.task_id,
                                                       "vina_kcal_mol": selected.affinity_kcal,
                                                       "physical_status": selected.physical_status},
            "saved": (outcome.saved or {}).get("status"), "video": (outcome.video or {}).get("final") or (outcome.video or {}).get("status"),
            "preparation": readiness_label((outcome.preparation or {}).get("readiness")) or (outcome.preparation or {}).get("status"),
            "video_pending": video_pending(outcome), "video_progress": (outcome.video or {}).get("progress"),
            "files": {name: len(data) for name, data in proposal.files.items()}, "paths": dict(proposal.saved_paths),
            "notes": list(outcome.notes)}
