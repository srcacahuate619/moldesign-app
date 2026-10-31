"""Molcy tool-pack: video jobs orchestrated, never rendered here.

MolChat asks MolDesign for renders (``POST /molcy/trabajos``), follows the
job like any other (§9.3), and links the acta bundle
(``molcy.procedencia/1``) into the execution report. The MP4 itself never
passes through the agent: the UI offers it via the ``open_molcy`` deep link.
GPU renders are ``write``: a human approval gates every request.
"""

from __future__ import annotations

from .catalog import (
    Capability,
    EpistemicClass,
    FieldSpec,
    register,
)

_MOLCY_ID = FieldSpec(str, max_length=36, pattern=r"[A-Za-z0-9-]{4,36}")
_MOLCY_JOB = FieldSpec(str, max_length=36, pattern=r"[0-9a-fA-F-]{36}")
_ORIGEN = FieldSpec(str, max_length=8, pattern=r"moldex|receptor")
_ESCENA = FieldSpec(str, max_length=10, pattern=r"resultado|receptor|busqueda|ensamble")
_FORMATO = FieldSpec(str, max_length=16,
                     pattern=r"horizontal|vertical|previsualizacion")
_TASK_ID = FieldSpec(str, max_length=128, pattern=r"[a-zA-Z0-9_-]+")


def _register_all() -> None:
    for capability in [
        Capability("molcy_fuentes",
                   "Qué corridas y receptores pueden protagonizar un vídeo",
                   "GET", "/molcy/fuentes", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /molcy/fuentes",
                   outputs=("moldex", "receptores")),
        Capability("request_case_video",
                   "Pedir un render GPU de una corrida (revisa molcy_fuentes primero)",
                   "POST", "/molcy/trabajos",
                   {"origen": _ORIGEN, "id": _MOLCY_ID, "escena": _ESCENA,
                    "formato": _FORMATO},
                   {"task_id": _TASK_ID},
                   risk="write",
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /molcy/trabajos",
                   outputs=("id", "estado")),
        Capability("molcy_job_status",
                   "Estado de un trabajo de render",
                   "GET", "/molcy/trabajos/{job_id}", {"job_id": _MOLCY_JOB}, {},
                   path_fields=("job_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /molcy/trabajos/{job_id}",
                   outputs=("id", "estado")),
        Capability("get_video_acta",
                   "Acta de procedencia del vídeo (hashes, build, manifiestos)",
                   "GET", "/molcy/trabajos/{job_id}/procedencia",
                   {"job_id": _MOLCY_JOB}, {},
                   path_fields=("job_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /molcy/trabajos/{job_id}/procedencia",
                   outputs=("schema", "trabajo", "build")),
        Capability("cancel_molcy_job",
                   "Cancelar un trabajo de render en curso",
                   "POST", "/molcy/trabajos/{job_id}/cancelar",
                   {"job_id": _MOLCY_JOB}, {}, risk="write",
                   path_fields=("job_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /molcy/trabajos/{job_id}/cancelar"),
    ]:
        register(capability)


_register_all()
