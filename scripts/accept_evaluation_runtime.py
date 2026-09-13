"""Aceptación runtime de Evaluación con Vina real, reinicio y dos cuentas.

No toca ``~/MolDesign``: crea SQLite, artefactos, logs y evidencia dentro de
``tmp/evaluation-runtime-*``. Devuelve 0 sólo si supera todo el gate.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent

# ── El arbol desde el que se SIRVE el backend ─────────────────────────
#
# Por defecto, el repositorio. Con `MOLDESIGN_GATE_BUNDLE=1`, el runtime STAGED
# -`frontend/src-tauri/resources`-, que es literalmente lo que se instala.
#
# La diferencia no es cosmetica. El repositorio tiene `data/target_library` y
# PDB sin comprimir que el instalador NO lleva, y esos archivos adelantan
# estructuras completas que en una maquina recien instalada no existen. Corriendo
# sobre el repositorio, 5VA1 preparaba su sitio A+B correctamente; sobre el
# bundle preparaba la cadena A sola, porque el ensamblaje biologico se generaba
# desde una copia filtrada que ya habia perdido los REMARK. Un gate que solo
# corre sobre el arbol de desarrollo no puede ver esa clase de defecto.
_STAGED = ROOT / "frontend" / "src-tauri" / "resources"
SOBRE_BUNDLE = os.environ.get("MOLDESIGN_GATE_BUNDLE") == "1"
if SOBRE_BUNDLE and not (_STAGED / "backend" / "api" / "main.py").is_file():
    raise SystemExit(
        f"MOLDESIGN_GATE_BUNDLE=1 pero no hay runtime staged en {_STAGED}.\n"
        "Ejecuta `npm run stage:desktop` dentro de frontend/ antes del gate."
    )
ARBOL = _STAGED if SOBRE_BUNDLE else ROOT
BACKEND = ARBOL / "backend"
PYTHON = (ARBOL / "python" / "python.exe") if SOBRE_BUNDLE else (ROOT / "python-embed" / "python.exe")
VINA_EXE = _STAGED / "tools" / "vina" / "vina.exe"
# Aspirina: ligando pequeño pero farmacológicamente plausible que supera el
# umbral mínimo del validador (a diferencia del etanol usado originalmente).
SMILES = "CC(=O)OC1=CC=CC=C1C(=O)O"
TARGET = "3F75"
CHAIN = "A"

# ── Segundo contrato: la ruta SIN `pipeline_config` ──────────────────────────
#
# `_run_full_evaluation_async` RETORNA ANTES cuando recibe `pipeline_config`,
# delegando en `services/pipeline/runner.py`. Este gate solo mandaba
# `pipeline_config`, asi que ejercitaba una de las dos ramas; la otra —la que
# toma un `POST /evaluation/submit` normal— llego a main rota: usaba
# `asyncio.to_thread` sin `import asyncio` a nivel de modulo y moria con
# `NameError` antes de calcular propiedades. Un gate que cubre una rama de dos
# declara verde un producto que no evalua nada.
#
# Paracetamol: distinto de la aspirina para que las dos corridas creen moleculas
# distintas y ninguna sobrescriba el resultado persistido de la otra.
SMILES_SIN_CONFIG = "CC(=O)Nc1ccc(O)cc1"
NOMBRE_SIN_CONFIG = "paracetamol-ruta-por-defecto"

PASSWORD = "Runtime-Gate-2026!"
EVALUATION_MAX_SECONDS = float(
    os.environ.get("MOLDESIGN_GATE_EVALUATION_MAX_SECONDS", "120")
)


class GateFailure(RuntimeError):
    pass


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(
    base: str,
    method: str,
    path: str,
    *,
    token: str | None = None,
    body: dict[str, Any] | None = None,
    expected: set[int] | None = None,
    timeout: float = 120.0,
) -> tuple[int, bytes, dict[str, str]]:
    # `timeout` es parámetro desde que el gate de MolChat comparte este arnés:
    # cargar el modelo local y responder el primer turno pasa de 120 s, y un
    # timeout fijo convertía eso en un fallo del gate en vez de una espera.
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            payload = response.read()
            response_headers = dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        payload = exc.read()
        response_headers = dict(exc.headers.items())
    allowed = expected or {200}
    if status not in allowed:
        detail = payload.decode("utf-8", errors="replace")[:2000]
        raise GateFailure(f"{method} {path}: HTTP {status}, esperado {sorted(allowed)}: {detail}")
    return status, payload, response_headers


def _json(*args: Any, **kwargs: Any) -> dict[str, Any]:
    _, payload, _ = _request(*args, **kwargs)
    decoded = json.loads(payload)
    if not isinstance(decoded, dict):
        raise GateFailure(f"Respuesta JSON no es un objeto: {type(decoded).__name__}")
    return decoded


def entorno_runtime(data_dir: Path, vina_tmp: Path) -> dict[str, str]:
    """El entorno del backend, el mismo en los cuatro gates.

    `PYTHONUTF8` y `PYTHONDONTWRITEBYTECODE` los pone `spawn_backend` en
    produccion (doc 73 §1). Sin el primero, el Python embebido -3.11.9- arranca
    con la pagina de codigos del sistema y una lectura de texto sin `encoding=`
    devuelve contenido corrompido SIN lanzar excepcion. Un gate que no los ponga
    esta midiendo un entorno que ningun usuario tiene.
    """
    env = os.environ.copy()
    env.update({
        "MOLDESIGN_TESTING": "1",
        "ENVIRONMENT": "testing",
        "LOCAL_DATA_DIR": str(data_dir),
        "VINA_TEMP_DIR": str(vina_tmp),
        "VINA_EXECUTABLE_PATH": str(VINA_EXE),
        "MEEKO_PREPARE_RECEPTOR_PATH": str(PYTHON.parent / "Scripts" / "mk_prepare_receptor.exe"),
        "MEEKO_PREPARE_LIGAND_PATH": str(PYTHON.parent / "Scripts" / "mk_prepare_ligand.exe"),
        "MEEKO_EXPORT_PATH": str(PYTHON.parent / "Scripts" / "mk_export.exe"),
        "SECRET_KEY": "runtime-gate-secret-key-2026-at-least-32-characters",
        "LOG_LEVEL": "INFO",
        "PYTHONPATH": str(BACKEND),
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


def _start_backend(env: dict[str, str], port: int, log_path: Path) -> tuple[subprocess.Popen[bytes], Any]:
    log_handle = log_path.open("ab")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [str(PYTHON), "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=BACKEND,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        creationflags=creationflags,
    )
    return process, log_handle


def _wait_ready(base: str, process: subprocess.Popen[bytes], timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise GateFailure(f"El backend terminó durante el arranque (exit={process.returncode}).")
        try:
            status, _, _ = _request(base, "GET", "/health", expected={200, 503})
            if status == 200:
                return
        except Exception:
            pass
        time.sleep(0.4)
    raise GateFailure("El backend no quedó listo dentro de 90 s.")


def _stop_backend(process: subprocess.Popen[bytes] | None, log_handle: Any | None) -> None:
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
    if log_handle is not None:
        log_handle.close()


def _auth(base: str, name: str) -> str:
    response = _json(
        base,
        "POST",
        "/auth/register",
        body={"email": f"{name}@example.com", "username": name, "password": PASSWORD},
        expected={201},
    )
    token = response.get("access_token")
    if not isinstance(token, str) or not token:
        raise GateFailure(f"Registro de {name} no devolvió access_token.")
    return token


def _projection(task_id: str, fingerprint: str, preflight: dict[str, Any]) -> dict[str, Any]:
    config = preflight["effective_config"]
    receptor = preflight["receptor"]
    ligand = preflight["ligand"]
    return {
        "projection_version": 1,
        "case_id": "runtime-evaluation-gate",
        "name": "Gate runtime Evaluación",
        "context": {"question": "¿La corrida real persiste y reaparece sin cambiar?"},
        "inputs": {
            "receptor": {"pdb_id": receptor["pdb_id"], "chain": receptor["chain"], "origin": "catalog"},
            "ligand": {"input_smiles": SMILES, "canonical_smiles": ligand.get("canonical_smiles")},
            "config": {
                "grid_center": config["grid_center"],
                "grid_size": config["grid_size"],
                "docking_engine": config["docking_engine"],
                "exhaustiveness": config["exhaustiveness"],
                "num_poses": config["num_poses"],
                "seed": config["seed"],
                "pipeline_config": config.get("pipeline_config"),
            },
        },
        "preflight": {
            "fingerprint": fingerprint,
            "generated_at": preflight.get("generated_at"),
            "schema_version": preflight.get("schema_version"),
            "execution_route": preflight.get("execution_route"),
            "blockers": preflight.get("technical_blockers", []),
            "warnings": preflight.get("warnings", []),
            "not_evaluated": preflight.get("not_evaluated", []),
        },
        "run": {"task_id": task_id, "input_fingerprint": fingerprint, "execution_state": "completed"},
        "run_inputs_relation": "corresponde",
    }


def _critical_result(result: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "molecule_id", "task_id", "affinity_kcal", "total_score", "vina_version",
        "vina_random_seed", "scientific_warnings", "receptor_sha256", "docking_protocol",
        "structural_evidence", "pose_selection", "docking_poses", "clgnn_score",
        "stacking_clgnn_weight", "stacking_effective_weights",
    )
    return {key: result.get(key) for key in keys}


def _assert_clgnn_observable(result: dict[str, Any], contract: str) -> None:
    """The shipped checkpoint must run, but cannot influence ranking yet."""
    clgnn_score = result.get("clgnn_score")
    if not isinstance(clgnn_score, (int, float)) or not (0.0 <= float(clgnn_score) <= 1.0):
        raise GateFailure(
            f"CL-GNN incluido pero sin inferencia real válida ({contract}): {clgnn_score!r}"
        )
    if result.get("stacking_clgnn_weight") not in (0, 0.0):
        raise GateFailure(
            "El checkpoint CL-GNN pendiente de validación influyó en el ranking "
            f"({contract}): peso={result.get('stacking_clgnn_weight')!r}"
        )


def _contrato_sin_pipeline_config(
    base: str,
    token: str,
    evidence: Path,
    molecule_id_del_primer_contrato: str,
) -> dict[str, Any]:
    """Corrida por la ruta por defecto: `submit` SIN `pipeline_config`.

    Debe terminar en SUCCESS y dejar resultado persistido y releible. Es la rama
    que `_run_full_evaluation_async` ejecuta en linea, sin delegar en el runner
    PRO, y la que estuvo rota sin que este gate se enterara.
    """
    preflight = _json(base, "POST", "/evaluation/preflight", token=token, body={
        "smiles": SMILES_SIN_CONFIG,
        "target_pdb_id": TARGET,
        "chain": CHAIN,
    })
    (evidence / "preflight-sin-config.json").write_text(
        json.dumps(preflight, indent=2, ensure_ascii=False), encoding="utf-8")
    blockers = preflight.get("technical_blockers") or []
    if blockers:
        raise GateFailure(f"Preflight (sin pipeline_config) bloqueado: {blockers}")
    fingerprint = preflight.get("input_fingerprint")
    if not isinstance(fingerprint, str):
        raise GateFailure("Preflight (sin pipeline_config) sin input_fingerprint.")

    # Sin `pipeline_config` a proposito: es el objeto de este contrato. Se manda
    # la huella del preflight porque el backend la exige igual por esta ruta.
    submitted = _json(base, "POST", "/evaluation/submit", token=token, expected={202}, body={
        "smiles": SMILES_SIN_CONFIG,
        "target_pdb_id": TARGET,
        "chain": CHAIN,
        "molecule_name": NOMBRE_SIN_CONFIG,
        "preflight_fingerprint": fingerprint,
    })
    task_id = submitted["task_id"]

    iniciado = time.monotonic()
    deadline = time.monotonic() + 900
    status: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        status = _json(base, "GET", f"/evaluation/status/{task_id}", token=token)
        if status.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
            break
        time.sleep(1.0)
    elapsed_s = round(time.monotonic() - iniciado, 3)
    if not status or status.get("status") != "SUCCESS":
        raise GateFailure(
            "La corrida SIN pipeline_config no termino en SUCCESS: "
            f"{status}. Es la ruta por defecto de /evaluation/submit."
        )
    resultado = status.get("result")
    if not isinstance(resultado, dict):
        raise GateFailure("SUCCESS sin pipeline_config pero sin resultado serializable.")
    molecule_id = resultado.get("molecule_id")
    if not molecule_id:
        raise GateFailure("El resultado sin pipeline_config no trae molecule_id.")
    if str(molecule_id) == str(molecule_id_del_primer_contrato):
        raise GateFailure(
            "Los dos contratos comparten molecule_id: uno sobrescribe al otro y "
            "el gate dejaria de probar dos corridas."
        )

    # Persistido y releible, no solo vivo.
    reabierto = _json(
        base, "GET",
        f"/evaluation/result/{molecule_id}?{urllib.parse.urlencode({'task_id': task_id})}",
        token=token,
    )
    if _critical_result(resultado) != _critical_result(reabierto):
        raise GateFailure(
            "Sin pipeline_config, el resultado vivo y el reabierto difieren en "
            "campos cientificos criticos."
        )
    _assert_clgnn_observable(reabierto, "sin pipeline_config")
    (evidence / "result-sin-config.json").write_text(
        json.dumps({"vivo": resultado, "reabierto": reabierto}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    return {
        "task_id": task_id,
        "molecule_id": str(molecule_id),
        "elapsed_s": elapsed_s,
        "affinity_kcal": reabierto.get("affinity_kcal"),
        "vina_version": reabierto.get("vina_version"),
    }


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence = ROOT / "tmp" / f"evaluation-runtime-{stamp}"
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
        alice = _auth(base, "alice_runtime")
        bob = _auth(base, "bob_runtime")

        pipeline_config = {
            "enabled_stages": ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
            "stage_params": {
                "properties": {"run_admet_ai": False},
                "conformer": {"conformers": 1},
                "docking": {"exhaustiveness": 8, "num_poses": 9, "seed": 42},
            },
            "docking_engine": "vina",
            "pro_selectivity": False,
            "pro_mmgbsa": False,
        }
        preflight_payload = {
            "smiles": SMILES,
            "target_pdb_id": TARGET,
            "chain": CHAIN,
            "docking_engine": "vina",
            "exhaustiveness": 8,
            "num_poses": 9,
            "conformers": 1,
            "pipeline_config": pipeline_config,
        }
        preflight = _json(base, "POST", "/evaluation/preflight", token=alice, body=preflight_payload)
        (evidence / "preflight.json").write_text(json.dumps(preflight, indent=2, ensure_ascii=False), encoding="utf-8")
        blockers = preflight.get("technical_blockers") or []
        if blockers:
            raise GateFailure(f"Preflight bloqueado: {blockers}")
        fingerprint = preflight.get("input_fingerprint")
        if not isinstance(fingerprint, str):
            raise GateFailure("Preflight sin input_fingerprint.")
        config = preflight["effective_config"]
        submit_payload = {
            "smiles": SMILES,
            "target_pdb_id": TARGET,
            "chain": CHAIN,
            "molecule_name": "aspirina-runtime-gate",
            "grid_center": config["grid_center"],
            "grid_size": config["grid_size"],
            "pipeline_config": pipeline_config,
            "preflight_fingerprint": fingerprint,
        }
        evaluation_started = time.monotonic()
        submitted = _json(base, "POST", "/evaluation/submit", token=alice, body=submit_payload, expected={202})
        task_id = submitted["task_id"]

        deadline = time.monotonic() + 900
        live_status: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            live_status = _json(base, "GET", f"/evaluation/status/{task_id}", token=alice)
            serialized = json.dumps(live_status)
            if "poseData" in serialized or "$$$$" in serialized or "M  END" in serialized:
                raise GateFailure("El polling transportó contenido de poses/SDF.")
            if live_status.get("status") in {"SUCCESS", "FAILURE", "REVOKED"}:
                break
            time.sleep(1.0)
        if not live_status or live_status.get("status") != "SUCCESS":
            raise GateFailure(f"La corrida no terminó en SUCCESS: {live_status}")
        evaluation_elapsed_s = round(time.monotonic() - evaluation_started, 3)
        if evaluation_elapsed_s > EVALUATION_MAX_SECONDS:
            raise GateFailure(
                "La evaluación base 3F75/8x9 terminó, pero tardó "
                f"{evaluation_elapsed_s:.1f} s (presupuesto del gate: "
                f"{EVALUATION_MAX_SECONDS:.1f} s)."
            )
        live_result = live_status.get("result")
        if not isinstance(live_result, dict):
            raise GateFailure("SUCCESS sin resultado serializable.")
        _assert_clgnn_observable(live_result, "con pipeline_config")
        # Suscripción tardía deliberada: el bus debe reproducir la cronología y
        # cerrar al encontrar pipeline_done. Además fija la regresión visual en
        # la que ETKDG ya había terminado pero nunca emitía stage_done.
        _, sse_payload, _ = _request(
            base,
            "GET",
            f"/evaluation/stream/{task_id}",
            token=alice,
            timeout=30,
        )
        stage_events: list[dict[str, Any]] = []
        for line in sse_payload.decode("utf-8").splitlines():
            if line.startswith("data:"):
                event = json.loads(line.removeprefix("data:").strip())
                if isinstance(event, dict):
                    stage_events.append(event)
        for stage_id in ("properties", "conformer"):
            event_types = {
                event.get("type")
                for event in stage_events
                if event.get("stage_id") == stage_id
            }
            if not {"stage_start", "stage_done"}.issubset(event_types):
                raise GateFailure(
                    f"Cronología incompleta para {stage_id}: {sorted(event_types)}"
                )
        if not any(event.get("type") == "pipeline_done" for event in stage_events):
            raise GateFailure("El replay SSE no contiene pipeline_done.")
        (evidence / "stage-events.json").write_text(
            json.dumps(stage_events, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        molecule_id = live_result["molecule_id"]
        (evidence / "result-live.json").write_text(json.dumps(live_result, indent=2, ensure_ascii=False), encoding="utf-8")

        # El SDF se solicita explícitamente sólo después del terminal.
        _, poses, _ = _request(base, "GET", f"/evaluation/files/poses/{molecule_id}", token=alice)
        if b"M  END" not in poses:
            raise GateFailure("El artefacto de poses no parece un SDF válido.")
        (evidence / "poses.sdf").write_bytes(poses)

        _stop_backend(process, log_handle)
        process = None
        log_handle = None
        process, log_handle = _start_backend(env, port, evidence / "backend-restart.log")
        _wait_ready(base, process)

        reopened_status = _json(base, "GET", f"/evaluation/status/{task_id}", token=alice)
        reopened = _json(
            base,
            "GET",
            f"/evaluation/result/{molecule_id}?{urllib.parse.urlencode({'task_id': task_id})}",
            token=alice,
        )
        (evidence / "result-reopened.json").write_text(json.dumps(reopened, indent=2, ensure_ascii=False), encoding="utf-8")
        if reopened_status.get("status") != "SUCCESS":
            raise GateFailure(f"Tras reiniciar, status no recuperó SUCCESS: {reopened_status.get('status')}")
        if _critical_result(live_result) != _critical_result(reopened):
            raise GateFailure("Resultado vivo y reabierto difieren en campos científicos críticos.")

        projection = _projection(task_id, fingerprint, preflight)
        _, package, _ = _request(
            base,
            "POST",
            f"/evaluation/dossier/{molecule_id}/package",
            token=alice,
            body=projection,
        )
        package_path = evidence / "dossier.zip"
        package_path.write_bytes(package)
        with zipfile.ZipFile(package_path) as archive:
            protocol_name = next(name for name in archive.namelist() if name.endswith("run/protocol.json"))
            protocol = json.loads(archive.read(protocol_name))
            protocol_task = protocol.get("task_id")
            if isinstance(protocol_task, dict):
                protocol_task = protocol_task.get("valor")
            if str(protocol_task) != task_id:
                raise GateFailure("El dossier no conserva el task_id de la corrida reabierta.")
            if not any(name.endswith("outputs/poses.sdf") for name in archive.namelist()):
                raise GateFailure("El dossier no contiene el SDF de poses registrado.")

        forbidden_checks = [
            ("GET", f"/evaluation/status/{task_id}", None),
            ("GET", f"/evaluation/result/{molecule_id}?task_id={task_id}", None),
            ("GET", f"/evaluation/files/poses/{molecule_id}", None),
            ("GET", f"/evaluation/files/protein/{molecule_id}", None),
            ("GET", f"/evaluation/files/complex/{molecule_id}", None),
            ("POST", f"/evaluation/dossier/{molecule_id}/package", projection),
        ]
        denials = []
        for method, path, body in forbidden_checks:
            status, payload, _ = _request(base, method, path, token=bob, body=body, expected={403, 404})
            denials.append({"method": method, "path": path, "status": status, "body": payload.decode("utf-8", errors="replace")[:500]})
        (evidence / "bob-denials.json").write_text(json.dumps(denials, indent=2, ensure_ascii=False), encoding="utf-8")

        # ── Contrato 2: la misma instalación, por la ruta por defecto ────────
        sin_config = _contrato_sin_pipeline_config(base, alice, evidence, molecule_id)

        summary.update({
            "status": "PASS",
            "contratos": {
                "con_pipeline_config": {
                    "task_id": task_id,
                    "molecule_id": molecule_id,
                    "elapsed_s": evaluation_elapsed_s,
                },
                "sin_pipeline_config": sin_config,
            },
            "task_id": task_id,
            "molecule_id": molecule_id,
            "affinity_kcal": reopened.get("affinity_kcal"),
            "vina_version": reopened.get("vina_version"),
            "clgnn_score": reopened.get("clgnn_score"),
            "receptor_sha256": reopened.get("receptor_sha256"),
            "evaluation_elapsed_s": evaluation_elapsed_s,
            "evaluation_budget_s": EVALUATION_MAX_SECONDS,
            "bob_denials": len(denials),
        })
        print(
            f"PASS: Evaluación runtime real · 2 contratos · "
            f"con_config={task_id} ({evaluation_elapsed_s:.1f} s) · "
            f"sin_config={sin_config['task_id']} ({sin_config['elapsed_s']:.1f} s) · "
            f"evidencia={evidence}"
        )
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
