"""Observational Vina trace: validate, freeze and recover the actual docking.

Replica 0 has per-step metrics and sparse retained geometries; all replicas
have counters. These are search objectives, not experimental free energies.
No Molcy module is imported and no docking is replayed to invent a history.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
import zipfile

from utils.local_storage import read_bytes, write_bytes
from core.exceptions import LocalStorageError

SCHEMA = "moldesign.vina-search/1"
LIMIT = 64 * 1024 * 1024
MAX_REPLICAS = 128  # Same upper bound as the evaluation API.


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def instrumented(reference: str | None) -> tuple[str | None, dict | None]:
    """Only select the audited companion of the configured bundled Vina."""
    if not reference:
        return reference, None
    folder = Path(reference).resolve().parent
    manifest = folder / "vina-trace-manifest.json"
    if not manifest.is_file():
        return reference, None  # custom/old installations have no trace capability
    info = json.loads(manifest.read_text(encoding="utf-8"))
    if info.get("schema") != "moldesign.vina-trace/1" or info.get("binary") != "vina_trace.exe":
        raise ValueError("Invalid Vina trace manifest")
    if sha(Path(reference).read_bytes()) != info.get("reference_binary_sha256"):
        return reference, None  # a explicitly configured different Vina is never replaced
    binary = folder / "vina_trace.exe"
    if not binary.is_file() or sha(binary.read_bytes()) != info.get("binary_sha256"):
        raise ValueError("The bundled Vina trace executable does not match its SHA-256")
    return str(binary), {"binary_sha256": info["binary_sha256"],
                         "upstream_commit": info["upstream_commit"],
                         "version": info["upstream_version"],
                         "capture": info["capture"]}


def models(data: bytes) -> list[bytes]:
    blocks = re.findall(rb"^MODEL\s+\d+\s*\r?\n(.*?)^ENDMDL\s*$", data, re.M | re.S)
    if not blocks:
        raise ValueError("Missing PDBQT models in Vina trace")
    for block in blocks:
        atoms = [line for line in block.decode("utf-8").splitlines()
                 if line.startswith(("ATOM  ", "HETATM"))]
        if not atoms or not all(len(line) >= 54 and all(math.isfinite(float(line[i:i+8]))
                                                      for i in (30, 38, 46)) for line in atoms):
            raise ValueError("Invalid trace coordinates")
    return blocks


def parse(files: dict[str, bytes], replicas: int) -> dict:
    if not 1 <= replicas <= MAX_REPLICAS:
        raise ValueError("Invalid Vina replica count")
    expected = {"replica_0.csv", "states.pdbqt", "poses.pdbqt"} | {
        f"replica_{i}.txt" for i in range(replicas)}
    if set(files) != expected or sum(map(len, files.values())) > LIMIT:
        raise ValueError("Incomplete or oversized Vina trace")
    summaries = []
    for i in range(replicas):
        summary = dict(line.split("=", 1) for line in files[f"replica_{i}.txt"].decode().splitlines())
        task, steps, accepted = (int(summary[key]) for key in ("task", "steps", "accepted"))
        energy = float(summary["best_energy"])
        if task != i or not 0 < accepted <= steps or not math.isfinite(energy):
            raise ValueError("Invalid replica summary")
        summaries.append(dict(task=task, steps=steps, accepted=accepted, best_energy=energy))
    metrics = {}
    cumulative = 0
    for index, row in enumerate(csv.DictReader(io.StringIO(files["replica_0.csv"].decode())), 1):
        if int(row["task"]) != 0 or int(row["step"]) != index or row["accepted"] not in {"0", "1"}:
            raise ValueError("Invalid Vina step sequence")
        energies = [float(row[key]) for key in ("candidate_energy", "retained_energy", "best_energy")]
        if not all(map(math.isfinite, energies)):
            raise ValueError("Non-finite Vina trace energy")
        cumulative += int(row["accepted"])
        metrics[index] = {"candidata": energies[0], "retenida": energies[1],
                          "mejor_hasta_paso": energies[2], "aceptada_en_paso": bool(int(row["accepted"])),
                          "aceptadas_acumuladas": cumulative}
    if len(metrics) != summaries[0]["steps"] or cumulative != summaries[0]["accepted"]:
        raise ValueError("Replica counters do not match recorded steps")
    snapshots = []
    previous = 0
    for block in models(files["states.pdbqt"]):
        match = re.search(rb"REMARK VINA TRACE TASK (\d+) STEP (\d+) ACCEPTED ([01]) ENERGY (\S+)", block)
        if not match:
            raise ValueError("Missing native snapshot identity")
        task, step, accepted = map(int, match.group(1, 2, 3))
        energy = float(match.group(4))
        metric = metrics.get(step)
        if task != 0 or step <= previous or metric is None or energy != metric["retenida"] or bool(accepted) != metric["aceptada_en_paso"]:
            raise ValueError("Snapshot does not match its native step")
        snapshots.append({"task": 0, "step": step, "energy": energy, "metrica_interna": metric})
        previous = step
    poses = []
    for rank, block in enumerate(models(files["poses.pdbqt"]), 1):
        match = re.search(rb"REMARK VINA RESULT:\s+(\S+)\s+(\S+)\s+(\S+)", block)
        if not match:
            raise ValueError("Missing final pose affinity")
        values = list(map(float, match.group(1, 2, 3)))
        if not all(map(math.isfinite, values)):
            raise ValueError("Invalid final pose metrics")
        poses.append({"rank": rank, "afinidad_kcal_mol": values[0],
                      "rmsd_vina_inferior_a": values[1], "rmsd_vina_superior_a": values[2]})
    return {"tipo": "vina_monte_carlo_bfgs_interno", "replicas": replicas,
            "pasos_totales": sum(s["steps"] for s in summaries),
            "aceptados_totales": sum(s["accepted"] for s in summaries),
            "replica_visualizada": 0, "pasos_replica": summaries[0]["steps"],
            "resumenes": summaries, "instantaneas": snapshots, "poses": poses,
            "muestreo_visual": "Estados retenidos de la réplica 0; geometrías muestreadas, métricas de todos sus pasos."}


async def persist(prefix: Path, output: Path, *, replicas: int, identity: dict,
                  receptor: bytes, ligand: bytes, seed: int, cpu: int,
                  center: tuple, size: tuple, poses_sdf_sha256: str | None = None) -> dict:
    files = {"replica_0.csv": Path(str(prefix) + "_task_0.csv").read_bytes(),
             "states.pdbqt": Path(str(prefix) + "_task_0.pdbqt").read_bytes(),
             "poses.pdbqt": output.read_bytes()}
    for i in range(replicas):
        files[f"replica_{i}.txt"] = Path(str(prefix) + f"_task_{i}_summary.txt").read_bytes()
    trace = parse(files, replicas)
    metadata = {"schema": SCHEMA, "instrumentation": identity, "seed": seed, "cpu": cpu,
                "poses_sdf_sha256": poses_sdf_sha256,
                "box_center": list(center), "box_size": list(size),
                "receptor_sha256": sha(receptor), "ligand_pdbqt_sha256": sha(ligand),
                "files": {name: sha(data) for name, data in files.items()}, "trace": trace}
    files["manifest.json"] = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), data,
                             compress_type=zipfile.ZIP_DEFLATED)
    data = buffer.getvalue()
    digest = sha(data)
    name = f"runs/vina-search/{digest}.zip"
    await write_bytes(data, name)
    return {"schema": SCHEMA, "archive_path": name, "archive_sha256": digest,
            "poses_sdf_sha256": poses_sdf_sha256,
            "receptor_sha256": metadata["receptor_sha256"],
            "ligand_pdbqt_sha256": metadata["ligand_pdbqt_sha256"],
            "instrumentation": identity, "replicas": replicas,
            "steps": trace["pasos_totales"], "snapshots": len(trace["instantaneas"])}


async def recover(info: dict) -> tuple[dict, dict[str, bytes]]:
    try:
        data = await read_bytes(info["archive_path"])
    except LocalStorageError as exc:
        raise ValueError("Vina trace archive is missing") from exc
    if info.get("schema") != SCHEMA or sha(data) != info.get("archive_sha256"):
        raise ValueError("Vina trace archive hash mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or len(names) > MAX_REPLICAS + 4 or sum(i.file_size for i in archive.infolist()) > LIMIT:
            raise ValueError("Invalid Vina trace archive")
        files = {name: archive.read(name) for name in names}
    metadata = json.loads(files.pop("manifest.json"))
    if metadata.get("schema") != SCHEMA or metadata["instrumentation"] != info["instrumentation"]:
        raise ValueError("Invalid Vina trace provenance")
    if metadata["files"] != {name: sha(data) for name, data in files.items()}:
        raise ValueError("Vina trace file hash mismatch")
    for key in ("receptor_sha256", "ligand_pdbqt_sha256", "poses_sdf_sha256"):
        if metadata[key] != info[key]:
            raise ValueError("Vina trace input mismatch")
    parsed = parse(files, info["replicas"])
    if parsed != metadata["trace"]:
        raise ValueError("Vina trace metrics mismatch")
    return metadata, files
