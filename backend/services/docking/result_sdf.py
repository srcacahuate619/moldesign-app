"""Artefacto SDF de una corrida: archivo propio o composición declarada y verificada.

No genera poses ni modifica snapshots. La composición reutiliza las seis puertas
existentes de pose_recovery y conserva cada registro geométrico y su orden global.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from core.models import DockingPose
from services.docking.pose_recovery import PoseNoRecuperable, recuperar_pose_agrupada


class ResultSdfUnavailable(ValueError):
    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class ResultSdf:
    content: str
    sha256: str
    source_path: str | None
    source_kind: str
    manifest: dict[str, Any] | None = None

    def headers(self, task_id: str | None) -> dict[str, str]:
        return {"X-MolDesign-Poses-Sha256": self.sha256,
                "X-MolDesign-Poses-Assembly": self.source_kind,
                **({"X-MolDesign-Task-Id": task_id} if task_id else {})}


async def read_result_sdf(selected: Any, *, reader: Callable[[str], Awaitable[str]] | None = None) -> ResultSdf:
    """El SDF seleccionado, sin buscar otra proyección o deducir geometría."""
    if reader is None:
        from utils.local_storage import read_text
        reader = read_text
    path = getattr(selected, "poses_file_path", None)
    if path:
        try:
            content = await reader(path)
        except Exception as exc:
            raise ResultSdfUnavailable("No se pudo leer el SDF de esta corrida.", 404) from exc
        if not content or "M  END" not in content:
            raise ResultSdfUnavailable("El SDF de poses está vacío o es inválido.", 422)
        return ResultSdf(content, hashlib.sha256(content.encode()).hexdigest(), path, "stored")

    raw = getattr(selected, "docking_poses", None)
    if not raw:
        raise ResultSdfUnavailable("Esta corrida no conserva poses recuperables.", 404)
    try:
        poses = sorted((pose if isinstance(pose, DockingPose) else DockingPose.model_validate(pose) for pose in raw), key=lambda pose: pose.rank)
    except Exception as exc:
        raise ResultSdfUnavailable("La corrida no conserva un contrato legible de poses.") from exc
    if [pose.rank for pose in poses] != list(range(1, len(poses) + 1)):
        raise ResultSdfUnavailable("Los rangos globales de la piscina son incompletos o repetidos.")
    records, sources = [], []
    task_id = getattr(selected, "task_id", None)
    for pose in poses:
        try:
            recovered = await recuperar_pose_agrupada(pose)
        except PoseNoRecuperable as exc:
            raise ResultSdfUnavailable(f"No se puede demostrar la pose global {pose.rank}: {exc}") from exc
        source = {"global_rank": pose.rank, "original_rank": recovered.rank_original,
                  "conformer_index": pose.conformer_index, "source_provenance": pose.source_provenance,
                  "verified_atoms": recovered.atomos_verificados,
                  "max_displacement_A": recovered.max_desplazamiento_A}
        sources.append(source)
        # Sólo se añaden propiedades SDF: los bytes de la geometría recuperada no cambian.
        metadata = json.dumps(source, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        record = recovered.sdf_record
        if not record.endswith("\n"):
            record += "\n"
        record += "\n> <MOLDESIGN_POOL_RANK>\n" + str(pose.rank) + "\n\n"
        if task_id:
            record += "> <MOLDESIGN_TASK_ID>\n" + json.dumps(task_id, ensure_ascii=True) + "\n\n"
        record += "> <MOLDESIGN_SOURCE_PROVENANCE_JSON>\n" + metadata + "\n\n$$$$\n"
        records.append(record)
    content = "".join(records)
    manifest = {"schema": "moldesign.verified-ensemble-sdf/1", "task_id": task_id,
                "source": "snapshot.docking_poses", "geometry_modified": False, "poses": sources}
    return ResultSdf(content, hashlib.sha256(content.encode()).hexdigest(), None, "verified_ensemble", manifest)
