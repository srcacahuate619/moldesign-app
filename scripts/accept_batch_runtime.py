"""Gate runtime de Batch/Cohortes con Vina real, reinicio y dos cuentas."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from accept_evaluation_runtime import (
    BACKEND,
    PASSWORD,
    PYTHON,
    ROOT,
    SMILES,
    TARGET,
    GateFailure,
    _auth,
    _free_port,
    _json,
    _request,
    _start_backend,
    _stop_backend,
    _wait_ready,
    entorno_runtime,
)


def _multipart(
    base: str,
    path: str,
    *,
    token: str,
    fields: dict[str, str],
    filename: str,
    content: bytes,
    expected: set[int],
) -> dict[str, Any]:
    boundary = f"----moldesign-runtime-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ])
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        b"Content-Type: text/csv\r\n\r\n",
        content,
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    request = urllib.request.Request(
        base + path,
        data=b"".join(chunks),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            status = int(response.status)
            payload = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        payload = exc.read()
    if status not in expected:
        raise GateFailure(
            f"POST {path}: HTTP {status}, esperado {sorted(expected)}: "
            f"{payload.decode('utf-8', errors='replace')[:2000]}"
        )
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise GateFailure(f"POST {path} no devolvió un objeto JSON.")
    return decoded


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = ROOT / "tmp" / f"batch-runtime-{stamp}"
    data_dir = evidence / "data"
    vina_tmp = evidence / "vina"
    evidence.mkdir(parents=True, exist_ok=False)
    data_dir.mkdir()
    vina_tmp.mkdir()
    port = _free_port()
    base = f"http://127.0.0.1:{port}"
    env = entorno_runtime(data_dir, vina_tmp)
    process = None
    log_handle = None
    summary: dict[str, Any] = {"status": "FAIL", "evidence_dir": str(evidence)}
    try:
        process, log_handle = _start_backend(env, port, evidence / "backend-first.log")
        _wait_ready(base, process)
        alice = _auth(base, "alice_batch_runtime")
        bob = _auth(base, "bob_batch_runtime")

        # La comprobación individual materializa y valida el mismo receptor
        # preparado que la cohorte exigirá después; no ejecuta docking.
        receptor_check = _json(
            base, "POST", "/evaluation/preflight", token=alice,
            body={
                "smiles": SMILES, "target_pdb_id": TARGET, "chain": "R",
                "docking_engine": "vina", "exhaustiveness": 1, "num_poses": 1,
                "pipeline_config": {"enabled_stages": ["validation", "conformer", "docking"]},
            },
        )
        if receptor_check.get("technical_blockers"):
            raise GateFailure(f"Receptor no ejecutable: {receptor_check['technical_blockers']}")
        effective = receptor_check["effective_config"]
        study = {
            "schema_version": 1,
            "name": "Gate runtime Batch",
            "receptor": {"pdb_id": TARGET, "chain": "R"},
            "config": {
                "docking_engine": "vina", "exhaustiveness": 1,
                "num_poses": 1, "seed": 73,
                "grid_center": effective["grid_center"],
                "grid_size": effective["grid_size"],
            },
        }
        csv = (
            "name,smiles,active,control_role\n"
            f"aspirina,{SMILES},1,reference\n"
            f"aspirina-duplicada,{SMILES},0,none\n"
        ).encode("utf-8")
        preflight = _multipart(
            base, "/evaluation/cohorts/preflight", token=alice,
            fields={"study": json.dumps(study)}, filename="runtime.csv", content=csv,
            expected={200},
        )
        (evidence / "preflight.json").write_text(json.dumps(preflight, indent=2, ensure_ascii=False), encoding="utf-8")
        if preflight.get("decision") != "ready":
            raise GateFailure(f"Cohorte bloqueada: {preflight.get('blockers')}")
        cohort = _multipart(
            base, "/evaluation/cohorts", token=alice,
            fields={
                "study": json.dumps(study),
                "expected_fingerprint": str(preflight["cohort_fingerprint"]),
            },
            filename="runtime.csv", content=csv, expected={201},
        )
        cohort_id = str(cohort["id"])
        _request(base, "GET", f"/evaluation/cohorts/{cohort_id}", token=bob, expected={404})
        _request(base, "POST", f"/evaluation/cohorts/{cohort_id}/runs?workers=1", token=bob, expected={404})

        accepted = _json(
            base, "POST", f"/evaluation/cohorts/{cohort_id}/runs?workers=1",
            token=alice, expected={202},
        )
        run_id = str(accepted["run_id"])
        deadline = time.monotonic() + 900
        run: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            run = _json(base, "GET", f"/evaluation/cohort-runs/{run_id}", token=alice)
            if run.get("status") not in {"queued", "running"}:
                break
            time.sleep(1)
        if not run or run.get("status") != "completed":
            raise GateFailure(f"La corrida Batch no terminó completa: {run}")
        if run.get("effective_config", {}).get("seed") != 73:
            raise GateFailure("La corrida no congeló la semilla solicitada (73).")
        statuses = sorted(row["status"] for row in run.get("rows", []))
        if statuses != ["completed", "duplicate_reused"]:
            raise GateFailure(f"Estados de filas inesperados: {statuses}")
        evidence_json = _json(base, "GET", f"/evaluation/cohort-runs/{run_id}/evidence", token=alice)
        (evidence / "evidence-live.json").write_text(json.dumps(evidence_json, indent=2, ensure_ascii=False), encoding="utf-8")
        affinities = [m.get("observed_vina_affinity_kcal_mol") for m in evidence_json.get("molecules", [])]
        if not any(isinstance(value, (int, float)) for value in affinities):
            raise GateFailure("La evidencia no contiene afinidad Vina observada.")

        _, pdf, _ = _request(base, "POST", f"/evaluation/cohort-runs/{run_id}/dossier/preview", token=alice)
        if not pdf.startswith(b"%PDF"):
            raise GateFailure("La vista previa del dossier no es PDF.")
        (evidence / "dossier.pdf").write_bytes(pdf)
        _, package, _ = _request(base, "POST", f"/evaluation/cohort-runs/{run_id}/dossier/package", token=alice)
        package_path = evidence / "dossier.zip"
        package_path.write_bytes(package)
        with zipfile.ZipFile(package_path) as archive:
            if not any(name.endswith("manifest.json") for name in archive.namelist()):
                raise GateFailure("El paquete Batch no contiene manifiesto.")

        _stop_backend(process, log_handle)
        process = None
        log_handle = None
        process, log_handle = _start_backend(env, port, evidence / "backend-restart.log")
        _wait_ready(base, process)
        reopened_cohort = _json(base, "GET", f"/evaluation/cohorts/{cohort_id}", token=alice)
        reopened_run = _json(base, "GET", f"/evaluation/cohort-runs/{run_id}", token=alice)
        latest_run = _json(base, "GET", f"/evaluation/cohorts/{cohort_id}/runs/latest", token=alice)
        reopened_evidence = _json(base, "GET", f"/evaluation/cohort-runs/{run_id}/evidence", token=alice)
        if reopened_cohort.get("cohort_fingerprint") != preflight.get("cohort_fingerprint"):
            raise GateFailure("La cohorte cambió tras reiniciar el backend.")
        if reopened_run.get("run_fingerprint") != run.get("run_fingerprint"):
            raise GateFailure("La identidad de la corrida cambió tras reiniciar.")
        if str(latest_run.get("id")) != run_id:
            raise GateFailure("La cohorte guardada no recuperó su última corrida.")
        if reopened_evidence.get("molecules") != evidence_json.get("molecules"):
            raise GateFailure("La evidencia reabierta difiere de la evidencia viva.")

        with sqlite3.connect(data_dir / "moldesign_local.db") as database:
            observed_seed, protocol_raw = database.execute(
                "SELECT vina_random_seed, docking_protocol FROM evaluation_results"
            ).fetchone()
        protocol = json.loads(protocol_raw)
        if observed_seed != 73 or protocol.get("seed") != 73:
            raise GateFailure(
                f"Vina/protocolo no observaron la semilla 73: {observed_seed}, {protocol}"
            )

        denials = []
        for method, path in [
            ("GET", f"/evaluation/cohorts/{cohort_id}"),
            ("GET", f"/evaluation/cohorts/{cohort_id}/runs/latest"),
            ("GET", f"/evaluation/cohort-runs/{run_id}"),
            ("GET", f"/evaluation/cohort-runs/{run_id}/evidence"),
            ("POST", f"/evaluation/cohort-runs/{run_id}/dossier/preview"),
            ("POST", f"/evaluation/cohort-runs/{run_id}/dossier/package"),
        ]:
            status, _, _ = _request(base, method, path, token=bob, expected={404})
            denials.append({"method": method, "path": path, "status": status})
        (evidence / "bob-denials.json").write_text(json.dumps(denials, indent=2), encoding="utf-8")

        summary.update({
            "status": "PASS", "cohort_id": cohort_id, "run_id": run_id,
            "run_fingerprint": run["run_fingerprint"], "seed": 73,
            "affinities": affinities, "row_statuses": statuses,
            "observed_vina_seed": observed_seed,
            "bob_denials": len(denials),
        })
        print(f"PASS: Batch runtime real · run={run_id} · evidencia={evidence}")
        return 0
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
        print(f"FAIL: {summary['error']} · evidencia={evidence}", file=sys.stderr)
        return 1
    finally:
        _stop_backend(process, log_handle)
        (evidence / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
