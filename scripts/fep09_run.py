"""FEP-09: cápsula -> upload B -> preflight -> Vina -> result -> Preparación.

Sólo API; las respuestas de riesgo se conservan completas. No importa producto.
La evidencia pública no contiene estructuras, poses ni secretos de lanzamiento.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fep09_inputs import PLB_COMMIT, materialize, write_json

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-SENSIBILIDAD"
PREREG = "9cdd0eab826bbbbe10d9b2469c52fbd0a0cf1638"
STAGES = ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"]
PIPELINE = {"enabled_stages": STAGES, "stage_params": {"conformer": {"conformers": 1, "ph": 7.4},
            "docking": {"exhaustiveness": 8, "num_poses": 9, "seed": 42}}, "docking_engine": "vina"}


class ApiError(RuntimeError):
    def __init__(self, code, data, path):
        self.code, self.data, self.path = code, data, path
        super().__init__(f"HTTP {code} {path}: {str(data)[:1500]}")


class API:
    def __init__(self, manifest):
        serve = json.loads((manifest.parent / "serve.json").read_text(encoding="utf-8"))
        self.base = f"http://127.0.0.1:{serve['puertoBack']}"
        self.launch = serve["token"]
        self.token = None
        self.token_time = 0

    def call(self, method, path, body=None, multipart=None, auth=True, timeout=240):
        headers = {"Accept": "application/json", "Accept-Language": "es"}
        if auth and time.monotonic()-self.token_time > 900:
            login = self.call("GET", "/auth/desktop-login", auth=False)
            self.token, self.token_time = login["access_token"], time.monotonic()
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        else:
            headers["X-MolDesign-Launch"] = self.launch
        data = None
        if multipart:
            data, boundary = multipart
            headers["Content-Type"] = "multipart/form-data; boundary=" + boundary
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base+path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                data = json.loads(raw)
            except ValueError:
                data = raw.decode(errors="replace")
            raise ApiError(e.code, data, path) from e


def multipart(fields, file):
    boundary = "fep09_"+uuid.uuid4().hex
    pieces = []
    for key, value in fields.items():
        pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
    pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="input.pdb"\r\nContent-Type: chemical/x-pdb\r\n\r\n'.encode())
    pieces.extend([file.read_bytes(), f"\r\n--{boundary}--\r\n".encode()])
    return b"".join(pieces), boundary


def projection(case, task, preflight):
    config, rec, lig = preflight["effective_config"], preflight["receptor"], preflight["ligand"]
    return {"projection_version": 1, "case_id": case["case_id"], "name": case["case_id"],
            "context": {"question": "Sensibilidad por requisito a un defecto preregistrado"},
            "inputs": {"receptor": {"pdb_id": rec["pdb_id"], "chain": rec["chain"], "origin": "user"},
                       "ligand": {"input_smiles": case["smiles"], "canonical_smiles": lig.get("canonical_smiles")},
                       "config": {k: config.get(k) for k in ("grid_center", "grid_size", "docking_engine", "exhaustiveness", "num_poses", "seed", "pipeline_config")}},
            "preflight": {"fingerprint": preflight["input_fingerprint"], "generated_at": preflight.get("generated_at"),
                          "schema_version": preflight.get("schema_version"), "execution_route": preflight.get("execution_route"),
                          "blockers": preflight.get("technical_blockers", []), "warnings": preflight.get("warnings", []),
                          "not_evaluated": preflight.get("not_evaluated", [])},
            "run": {"task_id": task, "input_fingerprint": preflight["input_fingerprint"], "execution_state": "completed"},
            "run_inputs_relation": "corresponde"}


def flatten(audit):
    return [r for b in audit["bloques"] for r in b["requisitos"]] if isinstance(audit["bloques"], list) else [r for b in audit["bloques"].values() for r in b["requisitos"]]


def public_result(result):
    keys = ["molecule_id", "task_id", "receptor_sha256", "receptor_path", "vina_version", "vina_random_seed", "docking_protocol", "ligand_state", "scientific_warnings", "affinity_kcal", "model_used"]
    return {k: result.get(k) for k in keys}


def append_json(path, value):
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, ensure_ascii=False, sort_keys=True)+"\n")
        fh.flush()
        os.fsync(fh.fileno())


def run_case(api, plb, system, case, dest, temp, deadline):
    started = time.monotonic()
    row = {**case, "product_commit": "f183e0af", "preregistration_commit": PREREG,
           "phase": "pilot" if dest.name == "pilot" else "confirmatory", "started_utc": datetime.now(timezone.utc).isoformat(),
           "parameters": {"mode": "respetar", "pipeline_config": PIPELINE, "grid_center": system["grid_center"], "grid_size": system["grid_size"]},
           "task_id": None, "receptor_sha256": None, "requirements": [], "global_state": None}
    evidence = dest / "evidence" / case["case_id"]
    evidence.mkdir(parents=True, exist_ok=True)
    stage = "materialize"
    try:
        file = (temp / f"{case['case_id']}.pdb").resolve()
        row.update(materialize(plb, system, case, file))
        fields = {"name": "FEP09 "+case["case_id"], "is_curated": "false", "modo_preparacion": "respetar", "chain_id": system["chain"]}
        for dim, value in zip("xyz", system["grid_center"]):
            fields["grid_center_"+dim] = value
        for dim, value in zip("xyz", system["grid_size"]):
            fields["grid_size_"+dim] = value
        write_json(evidence / "upload_request.json", {"fields": fields, "input_sha256": row["input_sha256"], "input_file": str(file)})
        stage = "upload"
        uploaded = api.call("POST", "/targets/upload", multipart=multipart(fields, file), timeout=600)
        write_json(evidence / "upload_response.json", uploaded)
        target = uploaded.get("target", uploaded)
        pdb_id = target["pdb_id"]
        row["target_pdb_id"] = pdb_id
        pre_body = {"smiles": case["smiles"], "target_pdb_id": pdb_id, "chain": system["chain"],
                    "grid_center": system["grid_center"], "grid_size": system["grid_size"], "docking_engine": "vina",
                    "exhaustiveness": 8, "num_poses": 9, "conformers": 1, "pipeline_config": PIPELINE}
        write_json(evidence / "preflight_request.json", pre_body)
        stage = "preflight"
        preflight = api.call("POST", "/evaluation/preflight", pre_body)
        write_json(evidence / "preflight_response.json", preflight)
        if preflight.get("technical_blockers"):
            row.update(outcome="detected_before", detection_stage="preflight", rejection=preflight["technical_blockers"])
            return row
        stage = "submit"
        config = preflight["effective_config"]
        submit = {"smiles": case["smiles"], "target_pdb_id": pdb_id, "chain": system["chain"], "molecule_name": case["case_id"],
                  "grid_center": config["grid_center"], "grid_size": config["grid_size"], "pipeline_config": PIPELINE,
                  "preflight_fingerprint": preflight["input_fingerprint"]}
        write_json(evidence / "submit_request.json", submit)
        submitted = api.call("POST", "/evaluation/submit", submit)
        write_json(evidence / "submit_response.json", submitted)
        task = row["task_id"] = submitted["task_id"]
        stage = "status"
        end = time.monotonic()+deadline
        while time.monotonic() < end:
            status = api.call("GET", "/evaluation/status/"+task)
            if status.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
                break
            time.sleep(2)
        else:
            raise RuntimeError("timeout de tarea")
        write_json(evidence / "status_terminal.json", {k: v for k, v in status.items() if k != "result"})
        if status.get("status") != "SUCCESS":
            raise RuntimeError("tarea no termina SUCCESS: "+str({k: v for k, v in status.items() if k != "result"})[:1800])
        molecule = status["result"]["molecule_id"]
        stage = "result"
        result = api.call("GET", f"/evaluation/result/{molecule}?task_id={task}")
        write_json(evidence / "result_metadata.json", public_result(result))
        observed = result.get("docking_protocol") or {}
        if result.get("vina_version") != "1.2.7" or any(observed.get(k) != v for k, v in {"exhaustiveness": 8, "num_poses": 9, "seed": 42}.items()):
            raise RuntimeError("La corrida no declara los parámetros preregistrados de Vina")
        if (observed.get("execution_provenance") or {}).get("receptor_prep", {}).get("modo_de_preparacion") != "respetar":
            raise RuntimeError("La corrida cambió el camino B preregistrado")
        row["molecule_id"], row["receptor_sha256"] = molecule, result.get("receptor_sha256")
        row["docking_protocol"] = result.get("docking_protocol")
        row["ligand_state"] = result.get("ligand_state")
        row["vina_version"] = result.get("vina_version")
        row["recipe_hash"] = (result.get("docking_protocol") or {}).get("execution_provenance", {}).get("receptor_prep", {}).get("recipe_hash")
        stage = "projection"
        proj = projection(case, task, preflight)
        write_json(evidence / "projection.json", proj)
        stage = "preparacion"
        audit = api.call("POST", f"/evaluation/dossier/{molecule}/preparacion", proj)
        write_json(evidence / "preparacion.json", audit)
        row.update(outcome="audited", requirements=flatten(audit), global_state=audit["estado"],
                   blockers=audit["bloqueantes"], reviews=audit["en_revision"], routine_reviews=audit["en_revision_rutinaria"])
    except ApiError as e:
        write_json(evidence / "error_response.json", {"stage": stage, "http_status": e.code, "path": e.path, "body": e.data})
        # Sólo rechazos técnicos explícitos de la entrada ANTES de la auditoría.
        if stage in {"upload", "preflight", "submit"} and e.code in {400, 409, 422}:
            row.update(outcome="detected_before", detection_stage=stage, rejection=e.data, http_status=e.code)
        else:
            row.update(outcome="infrastructure_failure", failure_stage=stage, error=str(e))
    except Exception as e:
        row.update(outcome="infrastructure_failure", failure_stage=stage, error=type(e).__name__+": "+str(e))
    finally:
        row["elapsed_s"] = round(time.monotonic()-started, 3)
        row["evidence_dir"] = str(evidence.relative_to(ROOT)).replace("\\", "/")
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plb", type=Path, default=Path("E:/MolDesign-science/openff-plb"))
    ap.add_argument("--capsule", type=Path, required=True)
    ap.add_argument("--shard", type=int, choices=(0, 1, 2))
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--task-timeout", type=float, default=3600)
    args = ap.parse_args()
    if not args.pilot and args.shard is None:
        ap.error("requiere --pilot o --shard")
    current = subprocess.check_output(["git", "-C", str(args.plb), "rev-parse", "HEAD"], text=True).strip()
    if current != PLB_COMMIT:
        raise SystemExit("Benchmark modificado")
    if subprocess.check_output(["git", "diff", "f183e0af", "--", "backend", "frontend", "rescoring", "tools"], cwd=ROOT):
        raise SystemExit("Producto modificado respecto a f183e0af")
    plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    register = ART / "registered_conditions.json"
    reg = json.loads((register if register.exists() else ART / "manifest.json").read_text(encoding="utf-8"))["preregistration"]
    if hashlib.sha256((ART / "inventory.json").read_bytes()).hexdigest() != reg["inventory_sha256"]:
        raise SystemExit("Inventario difiere del prerregistro")
    systems = {s["target"]: s for s in plan["systems"]}
    targets = [s["target"] for i, s in enumerate(plan["systems"]) if args.pilot and s["target"] == "cdk2" or not args.pilot and i % 3 == args.shard]
    cases = [c for c in plan["cases"] if c["target"] in targets]
    dest = ART / "_work" / ("pilot" if args.pilot else f"shard-{args.shard}")
    dest.mkdir(parents=True, exist_ok=True)
    terminal = dest / "per_complex.jsonl"
    terminal.touch(exist_ok=True)
    failures = dest / "failures.jsonl"
    failures.touch(exist_ok=True)
    existing = [json.loads(line) for line in terminal.read_text(encoding="utf-8").splitlines() if line]
    done = {row["case_id"] for row in existing}
    failed, attempted = sum(r["outcome"] == "infrastructure_failure" for r in existing), len(existing)
    api = API(args.capsule / "manifest.json")
    manifest = json.loads((args.capsule / "manifest.json").read_text(encoding="utf-8"))
    # El manifiesto QA no guarda credenciales; se conservan condiciones y desvíos.
    write_json(dest / "capsule_conditions.json", {k: manifest.get(k) for k in ("repositorio", "puertos", "vina_cpu", "runtime_compartido", "export", "desviaciones_respecto_a_la_app_instalada", "autoverificacion")})
    if attempted and failed / attempted > .30:
        raise SystemExit("PARADA previa: infraestructura >30%; no se reintenta ni sobrescribe")
    for case in cases:
        if case["case_id"] in done:
            continue
        row = run_case(api, args.plb.resolve(), systems[case["target"]], case, dest, args.capsule / "tmp/inputs", args.task_timeout)
        append_json(terminal, row)
        attempted += 1
        if row["outcome"] == "infrastructure_failure":
            append_json(failures, row)
            failed += 1
        print(json.dumps({"case": case["case_id"], "outcome": row["outcome"], "elapsed_s": row["elapsed_s"],
                          "global": row["global_state"], "error": row.get("error"), "rejection": row.get("rejection")}, ensure_ascii=False), flush=True)
        if failed / attempted > .30:
            write_json(dest / "stop.json", {"reason": "infraestructura supera 30%", "failed": failed, "attempted": attempted})
            return 2
    write_json(dest / "complete.json", {"attempted": attempted, "failed": failed, "targets": targets, "pilot": args.pilot})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
