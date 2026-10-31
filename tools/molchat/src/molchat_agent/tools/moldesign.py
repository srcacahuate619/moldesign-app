"""MolDesign tool-pack: capabilities against the platform API.

Every endpoint below was verified in ``backend/api/routers/`` at the
reference commit (Fase 3). Two §7.2 rows are deliberately absent:
``create_docking_proposal`` (proposal creation is in-process only, no POST
route exists) and ``start_batch`` (multipart file upload; the agent has no
legitimate file bytes in Fase 3). Both abstain by absence, documented in
``docs/CONTRATO_MOLDESIGN.md``.
"""

from __future__ import annotations

from typing import Any

from .catalog import (
    Capability,
    EpistemicClass,
    FieldSpec,
    register,
)

_IDENTIFIER = FieldSpec(str, max_length=128, pattern=r"[a-zA-Z0-9_-]+")
_SMILES = FieldSpec(str, max_length=2000)
_TARGET = FieldSpec(str, max_length=10, pattern=r"[A-Za-z0-9_-]{4,10}")
_UUID = FieldSpec(str, max_length=36, pattern=r"[0-9a-fA-F-]{36}")
_TASK_ID = FieldSpec(str, max_length=128, pattern=r"[a-zA-Z0-9_-]+")
_MOLECULE_ID = _UUID
_IDEMPOTENCY_KEY = FieldSpec(str, max_length=200, pattern=r"[A-Za-z0-9_.:\-]+")


def _dossier_body(arguments: dict[str, Any]) -> dict[str, Any]:
    """Minimal client projection: labels only, science stays server-side."""
    molecule_id = arguments["molecule_id"]
    task_id = arguments.get("task_id")
    body: dict[str, Any] = {
        "case_id": f"molchat-{molecule_id[:8]}-{(task_id or 'latest')[:8]}",
        "name": arguments.get("case_name") or f"MolChat {molecule_id[:8]}",
    }
    if task_id:
        body["run"] = {"task_id": task_id}
    return body


def _register_all() -> None:
    std = [
        # Migrated Fase 0/1 capabilities (same contracts, declared fully).
        Capability("list_targets", "Listar receptores visibles para esta cuenta",
                   "GET", "/targets/", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /targets/"),
        Capability("check_preflight", "Auditoría factual de receptor y ligando, sin docking",
                   "POST", "/evaluation/preflight",
                   {"smiles": _SMILES, "target_pdb_id": _TARGET},
                   {"chain": FieldSpec(str, max_length=4),
                    "docking_engine": FieldSpec(str, max_length=32)},
                   epistemic_class=EpistemicClass.CALCULATION,
                   provenance="MolDesign POST /evaluation/preflight",
                   outputs=("technical_blockers", "warnings", "not_evaluated")),
        Capability("list_evaluations", "Consultar historial propio de evaluaciones",
                   "GET", "/history/evaluations", {},
                   {"page": FieldSpec(int, minimum=1, maximum=10000),
                    "page_size": FieldSpec(int, minimum=1, maximum=100),
                    "target_pdb_id": _TARGET},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /history/evaluations",
                   outputs=("items", "total", "page")),
        Capability("evaluation_status", "Consultar estado de una evaluación existente",
                   "GET", "/evaluation/status/{task_id}", {"task_id": _TASK_ID}, {},
                   path_fields=("task_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /evaluation/status/{task_id}",
                   outputs=("task_id", "status", "progress", "error")),
        Capability("get_docking_proposal", "Leer propuesta de docking para su revisión",
                   "GET", "/ai/proposals/{proposal_id}", {"proposal_id": _IDENTIFIER}, {},
                   path_fields=("proposal_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /ai/proposals/{proposal_id}",
                   outputs=("id", "hash", "estado")),
        Capability("approve_docking_proposal",
                   "Aprobar propuesta preexistente; puede iniciar cálculo costoso",
                   "POST", "/ai/proposals/{proposal_id}/approve",
                   {"proposal_id": _IDENTIFIER,
                    "proposal_hash": FieldSpec(str, max_length=71,
                                               pattern=r"sha256:[a-f0-9]{64}")},
                   {}, risk="approval_required", path_fields=("proposal_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /ai/proposals/{proposal_id}/approve",
                   outputs=("task_id", "target_pdb_id")),
        # Fase 3 (§7.2): orchestration reads.
        Capability("list_engines", "Qué motores hay y su estado",
                   "GET", "/evaluation/engines", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /evaluation/engines"),
        Capability("get_evaluation_result", "Resultado persistido con hashes",
                   "GET", "/evaluation/result/{molecule_id}",
                   {"molecule_id": _MOLECULE_ID},
                   {"task_id": FieldSpec(str, max_length=128, location="query")},
                   path_fields=("molecule_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /evaluation/result/{molecule_id}",
                   outputs=("id", "molecule_id", "task_id", "affinity_kcal")),
        Capability("get_interactions", "Contactos polares/apolares de la mejor pose",
                   "GET", "/evaluation/interactions/{molecule_id}",
                   {"molecule_id": _IDENTIFIER},
                   {"pose_rank": FieldSpec(int, minimum=1, maximum=20)},
                   path_fields=("molecule_id",),
                   epistemic_class=EpistemicClass.CALCULATION,
                   provenance="MolDesign GET /evaluation/interactions/{molecule_id}"),
        Capability("get_gnn_attention", "Atención GNN on-demand (SVG)",
                   "GET", "/evaluation/gnn-attention/{molecule_id}",
                   {"molecule_id": _MOLECULE_ID},
                   {"task_id": FieldSpec(str, max_length=128, location="query")},
                   path_fields=("molecule_id",),
                   epistemic_class=EpistemicClass.INFERENCE,
                   provenance="MolDesign GET /evaluation/gnn-attention/{molecule_id}"),
        Capability("stream_evaluation", "Eventos SSE de una evaluación",
                   "GET", "/evaluation/stream/{task_id}", {"task_id": _TASK_ID}, {},
                   path_fields=("task_id",), response="sse",
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /evaluation/stream/{task_id}",
                   outputs=("events",)),
        Capability("cancel_evaluation", "Cancelar una evaluación por task_id",
                   "POST", "/evaluation/cancel", {"task_id": _TASK_ID}, {},
                   risk="write",
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /evaluation/cancel"),
        # Fase 3: batch (start_batch excluded: multipart file, no agent bytes).
        Capability("batch_status", "Estado y parciales de un lote",
                   "GET", "/evaluation/batch/{batch_id}", {"batch_id": _IDENTIFIER}, {},
                   path_fields=("batch_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /evaluation/batch/{batch_id}",
                   outputs=("batch_id", "status", "total", "completed", "failed",
                            "active_task_id")),
        Capability("cancel_batch", "Detener un lote activo",
                   "POST", "/evaluation/batch/{batch_id}/cancel",
                   {"batch_id": _IDENTIFIER}, {}, risk="write",
                   path_fields=("batch_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /evaluation/batch/{batch_id}/cancel"),
        Capability("export_batch", "Artefactos del lote (xlsx o csv)",
                   "GET", "/evaluation/batch/{batch_id}/{format}",
                   {"batch_id": _IDENTIFIER,
                    "format": FieldSpec(str, max_length=6, pattern=r"export|csv")},
                   {}, path_fields=("batch_id", "format"), response="bytes",
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /evaluation/batch/{batch_id}/{export,csv}"),
        # Fase 3: informes y dossier.
        Capability("get_ai_report", "Informe IA persistido (genera bajo demanda si falta)",
                   "POST", "/evaluation/ai-report/{molecule_id}",
                   {"molecule_id": _MOLECULE_ID}, {},
                   path_fields=("molecule_id",),
                   epistemic_class=EpistemicClass.INFERENCE,
                   provenance="MolDesign POST /evaluation/ai-report/{molecule_id}",
                   outputs=("ai_report",)),
        Capability("stream_ai_report", "Informe IA en streaming (SSE)",
                   "GET", "/evaluation/ai-report/{molecule_id}/stream",
                   {"molecule_id": _MOLECULE_ID}, {},
                   path_fields=("molecule_id",), response="sse",
                   epistemic_class=EpistemicClass.INFERENCE,
                   provenance="MolDesign GET /evaluation/ai-report/{molecule_id}/stream",
                   outputs=("events",)),
        Capability("get_case_dossier", "Dossier del caso en PDF o ZIP con manifiesto",
                   "POST", "/evaluation/dossier/{molecule_id}/{format}",
                   {"molecule_id": _MOLECULE_ID,
                    "format": FieldSpec(str, max_length=7, pattern=r"preview|package")},
                   {"case_name": FieldSpec(str, max_length=300),
                    "task_id": FieldSpec(str, max_length=128)},
                   path_fields=("molecule_id", "format"), response="bytes",
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /evaluation/dossier/{molecule_id}/{preview,package}",
                   body_builder=_dossier_body),
        Capability("get_sar", "Análisis SAR de una molécula evaluada",
                   "GET", "/sar/{molecule_id}",
                   {"molecule_id": _IDENTIFIER},
                   {"task_id": FieldSpec(str, max_length=128, location="query")},
                   path_fields=("molecule_id",),
                   epistemic_class=EpistemicClass.CALCULATION,
                   provenance="MolDesign GET /sar/{molecule_id}"),
        Capability("get_history_stats", "Estadísticas del historial propio",
                   "GET", "/history/stats", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /history/stats"),
        Capability("save_molecule", "Guardar evaluación en la cuenta (Moldex)",
                   "POST", "/history/save/{molecule_id}",
                   {"molecule_id": _MOLECULE_ID},
                   {"name": FieldSpec(str, max_length=200, location="query"),
                    "task_id": FieldSpec(str, max_length=128, location="query")},
                   risk="write", path_fields=("molecule_id",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /history/save/{molecule_id}"),
        Capability("rescoring_health", "Estado del servicio de rescoring",
                   "GET", "/rescoring/health", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /rescoring/health"),
        Capability("rescoring_info", "Info del servicio de rescoring",
                   "GET", "/rescoring/info", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /rescoring/info"),
        Capability("rescoring_ram", "Memoria del servicio de rescoring",
                   "GET", "/rescoring/ram", {}, {},
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /rescoring/ram"),
        # Fase 5 (CR-07/CR-06, rama feat/molchat-plataforma-cr): proposal
        # creation exists now; reconcile reads what a lost response left.
        Capability("create_docking_proposal",
                   "Crear propuesta revisable sin lanzar cálculo (409 si el preflight bloquea)",
                   "POST", "/ai/proposals",
                   {"smiles": _SMILES},
                   {"target_pdb_id": _TARGET,
                    "chain": FieldSpec(str, max_length=4)},
                   risk="write",
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign POST /ai/proposals",
                   outputs=("proposal_id", "proposal_hash", "estado", "id", "hash")),
        Capability("reconcile_operation",
                   "Qué operación y trabajo existen para una clave de idempotencia",
                   "GET", "/ai/idempotency/{idempotency_key}",
                   {"idempotency_key": _IDEMPOTENCY_KEY}, {},
                   path_fields=("idempotency_key",),
                   epistemic_class=EpistemicClass.PERSISTED,
                   provenance="MolDesign GET /ai/idempotency/{idempotency_key}",
                   outputs=("operation", "status", "proposal_id", "task_id")),
    ]
    for capability in std:
        register(capability)


_register_all()
