#!/usr/bin/env python3
"""Herramienta de manifest experimental (FND-01).

Implementa la infraestructura de registro único por experimento definida en
`docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`, sección 17:

    scripts/artifacts_science/<EXPERIMENT_ID>/
      manifest.json      registro único (config, hashes, código, ambiente, salida)
      metrics.json       métricas agregadas del experimento
      per_complex.jsonl  una línea JSON por complejo evaluado
      failures.jsonl     una línea JSON por fallo
      README.md          resumen legible generado desde el manifest

Flujo de trabajo:

    1. init     crea el directorio con manifest.json prellenado y skeletons vacíos
    2. ejecutar el experimento y escribir metrics/per_complex/failures
    3. validate verifica manifest.json contra manifest.schema.json
    4. seal     congela los SHA-256 de datasets/modelos/binarios/assets (soporta el cegamiento de FND-05)
    5. finish   escribe la decisión (GO/NO_GO/INCONCLUSIVE) y la duración
    6. maintain mantenimiento auditado de assets sellados que cambian tras el sello

`seal`, `finish` y `maintain` regeneran el README.md del experimento para
reflejar el estado post-operación. `seal` solo puede ejecutarse una vez por
experimento.

Solo biblioteca estándar de Python 3.14 (json, hashlib, platform, subprocess,
os, sys, argparse, datetime, ctypes). Sin pip ni dependencias externas.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ruta base de los artefactos experimentales. Los tests pueden reemplazarla.
TOOL_DIR = Path(__file__).resolve().parent
ARTIFACTS_BASE = TOOL_DIR / "artifacts_science"
SCHEMA_PATH = TOOL_DIR / "artifacts_science" / "manifest.schema.json"

# Patrones de validación (subconjunto de draft-07 usado por el schema).
EXPERIMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

# Tamaño del buffer de lectura para hashear archivos grandes sin cargarlos en memoria.
HASH_CHUNK_BYTES = 1024 * 1024


# ---------------------------------------------------------------------------
# Utilidades de entorno
# ---------------------------------------------------------------------------


def _reconfigure_stdio():
    """Fuerza UTF-8 en stdout/stderr (necesario en Windows para acentos)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def _creationflags():
    """Evita ventanas de consola parpadeantes al invocar subprocesos en Windows."""
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _run(cmd, timeout=15):
    """Ejecuta un comando y devuelve (exit_code, stdout). Silencioso ante errores."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            creationflags=_creationflags(),
        )
        return result.returncode, result.stdout.strip()
    except Exception:
        return -1, ""


def _git_state():
    """Captura el estado real del repositorio git (rama, commit, dirty)."""
    ok_branch, branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    ok_commit, commit = _run(["git", "rev-parse", "HEAD"])
    ok_status, status = _run(["git", "status", "--porcelain"])
    return {
        "branch": branch if ok_branch == 0 and branch else "unknown",
        "commit": commit if ok_commit == 0 and commit else "unknown",
        "dirty": bool(status) if ok_status == 0 else False,
    }


def _git_toplevel():
    """Raíz del repositorio git; si no hay repo, el directorio de trabajo actual."""
    ok, top = _run(["git", "rev-parse", "--show-toplevel"])
    if ok == 0 and top:
        return os.path.normpath(top)
    return os.getcwd()


def _total_ram_mb():
    """RAM física total en MB. En Windows usa ctypes GlobalMemoryStatusEx."""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)) == 0:
            raise OSError("GlobalMemoryStatusEx failed")
        return int(stat.ullTotalPhys // (1024 * 1024))
    except Exception:
        try:
            page = os.sysconf("SC_PAGE_SIZE")
            pages = os.sysconf("SC_PHYS_PAGES")
            return int((page * pages) // (1024 * 1024))
        except Exception:
            return 0


def _detect_gpu():
    """Nombres de GPU vía nvidia-smi; 'unknown' como fallback silencioso."""
    ok, out = _run(
        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], timeout=10
    )
    if ok == 0 and out:
        names = [line.strip() for line in out.splitlines() if line.strip()]
        if names:
            return "; ".join(names)
    return "unknown"


# ---------------------------------------------------------------------------
# Utilidades de archivos y hashes
# ---------------------------------------------------------------------------


def _atomic_write(path, text):
    """Escribe de forma atómica (temp + os.replace) para la salida atómica del gate."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(str(tmp), str(path))


def _write_json(path, data):
    """Serializa y escribe JSON atómicamente con salto de línea final."""
    _atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def _sha256_file(path):
    """SHA-256 de un archivo leyendo por bloques (apto para datasets grandes)."""
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(HASH_CHUNK_BYTES)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _stored_path(abs_path):
    """Ruta a guardar en el manifest: relativa al repo git (o absoluta cross-drive)."""
    try:
        rel = os.path.relpath(abs_path, _git_toplevel())
    except ValueError:
        # En Windows, rutas en otra unidad no admiten relpath; se guarda la absoluta.
        rel = abs_path
    return rel.replace("\\", "/")


def _resolve_stored_path(stored, base):
    """Resuelve una ruta guardada (relativa al repo o absoluta) contra el repo actual."""
    if os.path.isabs(stored):
        return os.path.normpath(stored)
    return os.path.normpath(os.path.join(base, stored))


def _collect_hashes(path):
    """Mapa {ruta_relativa: sha256} de un archivo, o de cada archivo si es directorio."""
    abs_path = os.path.abspath(path)
    entries = {}
    if os.path.isfile(abs_path):
        entries[_stored_path(abs_path)] = _sha256_file(abs_path)
    elif os.path.isdir(abs_path):
        files = []
        for root, dirs, names in os.walk(abs_path):
            dirs.sort()
            for name in sorted(names):
                files.append(os.path.join(root, name))
        for file_path in files:
            entries[_stored_path(file_path)] = _sha256_file(file_path)
    else:
        raise FileNotFoundError(f"path not found: {path}")
    return entries


# ---------------------------------------------------------------------------
# Validador de schema (subconjunto de draft-07 usado por manifest.schema.json)
# ---------------------------------------------------------------------------


def _type_name(instance):
    """Nombre legible del tipo del valor, para mensajes de error."""
    return type(instance).__name__


def _matches_type(instance, expected):
    """Evalúa el keyword 'type' de draft-07 (acepta listas de unión)."""
    if isinstance(expected, list):
        return any(_matches_type(instance, item) for item in expected)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    return False


def _validate(instance, schema, path, errors):
    """Validador recursivo del subconjunto de draft-07 que usa el schema.

    Soportado: const, type, required, properties, additionalProperties,
    items, enum, pattern, minLength, minimum y format ('date-time').
    No soportado: $ref, $defs, oneOf/anyOf/allOf, if/then/else.
    """
    if isinstance(schema, bool):
        if schema is False:
            errors.append(f"{path}: schema prohibits any value here")
        return
    if not isinstance(schema, dict):
        errors.append(f"{path}: invalid schema definition")
        return

    if "const" in schema and instance != schema["const"]:
        errors.append(
            f"{path}: expected constant {schema['const']!r}, got {instance!r}"
        )
        return

    declared_type = schema.get("type")
    if declared_type is not None and not _matches_type(instance, declared_type):
        errors.append(
            f"{path}: type mismatch: expected {declared_type!r}, "
            f"got {_type_name(instance)}"
        )
        return

    if isinstance(instance, dict):
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property '{key}'")
        properties = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                _validate(value, properties[key], child_path, errors)
            elif additional is False:
                errors.append(f"{path}: unexpected property '{key}'")
            elif isinstance(additional, dict):
                _validate(value, additional, child_path, errors)

    if isinstance(instance, list):
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(instance):
                _validate(item, items, f"{path}[{index}]", errors)

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value {instance!r} not in enum {schema['enum']!r}")

    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(
        instance, bool
    ):
        if instance < schema["minimum"]:
            errors.append(
                f"{path}: value {instance!r} is below minimum {schema['minimum']!r}"
            )

    if "pattern" in schema and isinstance(instance, str):
        if re.fullmatch(schema["pattern"], instance) is None:
            errors.append(
                f"{path}: string {instance!r} does not match pattern "
                f"{schema['pattern']!r}"
            )

    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < schema["minLength"]:
            errors.append(
                f"{path}: string length {len(instance)} is below minimum "
                f"{schema['minLength']}"
            )

    if schema.get("format") == "date-time" and isinstance(instance, str):
        if DATETIME_RE.fullmatch(instance) is None:
            errors.append(f"{path}: string {instance!r} is not a valid date-time")


# ---------------------------------------------------------------------------
# Gestión del manifest
# ---------------------------------------------------------------------------


def _experiment_dir(experiment_id):
    """Directorio del experimento, validando el identificador contra la convención."""
    if not experiment_id or EXPERIMENT_ID_RE.fullmatch(experiment_id) is None:
        raise ValueError(
            f"invalid experiment_id {experiment_id!r}: must match "
            "^[A-Za-z0-9][A-Za-z0-9._-]*$"
        )
    return ARTIFACTS_BASE / experiment_id


def _load_manifest(experiment_id):
    """Carga manifest.json del experimento. Lanza ValueError con mensaje legible."""
    exp_dir = _experiment_dir(experiment_id)
    manifest_path = exp_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(
            f"manifest.json not found in {exp_dir}; run 'init' first"
        )
    try:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            return json.load(fh), manifest_path
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest.json is not valid JSON: {exc}") from exc


def _load_schema():
    """Carga manifest.schema.json del árbol de artefactos."""
    if not SCHEMA_PATH.is_file():
        raise ValueError(f"schema not found: {SCHEMA_PATH}")
    with open(SCHEMA_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _now_iso():
    """Fecha/hora UTC en formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat()


def _check_sealed_hashes(manifest, errors):
    """Recomputa los hashes sellados y compara; soporta el cegamiento de FND-05."""
    base = _git_toplevel()
    for key in (
        "dataset_hashes",
        "model_hashes",
        "binary_hashes",
        "assets_hashes",
    ):
        entries = manifest.get(key) or {}
        for stored, expected in entries.items():
            resolved = _resolve_stored_path(stored, base)
            if not os.path.isfile(resolved):
                errors.append(f"{key}: sealed file is missing: {stored}")
                continue
            actual = _sha256_file(resolved)
            if actual != expected:
                errors.append(
                    f"{key}: hash mismatch for {stored}: "
                    f"expected {expected}, got {actual}"
                )


def _render_readme(manifest):
    """Genera el README.md del experimento a partir del manifest."""
    git = manifest.get("git_state", {})
    env = manifest.get("environment", {})
    deps = manifest.get("dependencies", {})
    gate = manifest.get("gate", {})
    lines = [
        f"# {manifest.get('experiment_id', '')}",
        "",
        "Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).",
        "Este archivo se regenera desde `manifest.json`; no editar a mano.",
        "",
        "## Hipótesis",
        "",
        str(manifest.get("hypothesis", "")),
        "",
        "## Protocolo",
        "",
        f"Referencia: `{manifest.get('protocol', '')}`",
        "",
        "## Gate",
        "",
        str(gate.get("description", "")),
        "",
        "## Ambiente",
        "",
        f"- Sistema operativo: {env.get('os')} ({env.get('arch')})",
        f"- CPU: {env.get('cpu_count')} núcleos",
        f"- RAM total: {env.get('total_ram_mb')} MB",
        f"- GPU: {env.get('gpu')}",
        f"- Python: {deps.get('python_version')}",
        f"- Seeds: {manifest.get('seeds')}",
        f"- Git: rama `{git.get('branch')}`, commit `{git.get('commit')}`, dirty={git.get('dirty')}",
        "",
        "## Estado",
        "",
        f"- Creado: {manifest.get('created_at')}",
        f"- Status: {manifest.get('status')}",
        f"- Decisión: {manifest.get('decision')}",
    ]
    if manifest.get("sealed"):
        lines.append(f"- Sellado: sí ({manifest.get('sealed_at')})")
    if manifest.get("finished_at"):
        lines.append(f"- Finalizado: {manifest.get('finished_at')}")
    if manifest.get("decision_rationale"):
        lines.append(f"- Razón de la decisión: {manifest.get('decision_rationale')}")
    for key, label in (
        ("dataset_hashes", "dataset"),
        ("model_hashes", "modelos"),
        ("binary_hashes", "binarios"),
        ("assets_hashes", "assets"),
    ):
        entries = manifest.get(key) or {}
        if entries:
            lines.append(f"- Hashes de {label}: {len(entries)} archivo(s) con SHA-256")
    maintenance = manifest.get("seal_maintenance") or []
    if maintenance:
        lines += ["", "## Mantenimiento del sello", ""]
        for entry in maintenance:
            lines.append(
                f"- {entry.get('date', '')}: `{entry.get('path', '')}` "
                f"`{entry.get('previous_hash', '')[:8]}→{entry.get('new_hash', '')[:8]}` "
                f"— {entry.get('reason', '')} "
                f"(commit {entry.get('content_commit', '')})"
            )
    lines += [
        "",
        "## Flujo de trabajo",
        "",
        "1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.",
        "2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.",
        "3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.",
        "4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.",
        "5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.",
        "6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.",
        "",
        "Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.",
        "",
        "## Inmutabilidad post-seal",
        "",
        "- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).",
        "- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.",
        "- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.",
        "- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.",
        "- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).",
        "",
        "## Archivos",
        "",
        "- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).",
        "- `metrics.json`: métricas agregadas del experimento.",
        "- `per_complex.jsonl`: una línea JSON por complejo evaluado.",
        "- `failures.jsonl`: una línea JSON por fallo.",
        "- `README.md`: este archivo.",
        "",
    ]
    return "\n".join(lines)


def _generar_readme(experimento_dir):
    """Regenera README.md desde manifest.json (usado por init, seal y finish)."""
    with open(experimento_dir / "manifest.json", "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    _atomic_write(experimento_dir / "README.md", _render_readme(manifest))


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------


def _run_init(args):
    """Subcomando init: crea el directorio con manifest y skeletons vacíos."""
    try:
        exp_dir = _experiment_dir(args.experiment_id)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if exp_dir.exists() and not args.force:
        print(
            f"ERROR: experiment directory already exists: {exp_dir}. "
            "Use --force to regenerate empty skeletons "
            "(an existing manifest.json is never modified).",
            file=sys.stderr,
        )
        return 1

    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = exp_dir / "manifest.json"

    manifest = None
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
        except json.JSONDecodeError:
            manifest = None
    else:
        manifest = {
            "schema_version": 1,
            "experiment_id": args.experiment_id,
            "hypothesis": args.hypothesis,
            "protocol": args.protocol,
            "created_at": _now_iso(),
            "status": "created",
            "git_state": _git_state(),
            "environment": {
                "os": platform.system(),
                "arch": platform.machine(),
                "cpu_count": os.cpu_count() or 1,
                "total_ram_mb": _total_ram_mb(),
                "gpu": _detect_gpu(),
            },
            "seeds": args.seeds,
            "dependencies": {
                "python_version": platform.python_version(),
                "packages": [],
            },
            "gate": {"description": args.gate},
            "decision": "PENDING",
        }
        _write_json(manifest_path, manifest)

    # Los skeletons se regeneran siempre (son la "salida atómica" inicial).
    _atomic_write(exp_dir / "metrics.json", "{}\n")
    _atomic_write(exp_dir / "per_complex.jsonl", "")
    _atomic_write(exp_dir / "failures.jsonl", "")
    if manifest is not None:
        _generar_readme(exp_dir)
    else:
        print(
            "WARNING: existing manifest.json is not valid JSON; README.md was not regenerated.",
            file=sys.stderr,
        )

    print(f"Experiment '{args.experiment_id}' initialized at {exp_dir}")
    return 0


def _run_validate(args):
    """Subcomando validate: valida el manifest contra el schema y los hashes sellados."""
    try:
        manifest, manifest_path = _load_manifest(args.experiment_id)
        schema = _load_schema()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    errors = []
    _validate(manifest, schema, "$", errors)
    if manifest.get("sealed"):
        _check_sealed_hashes(manifest, errors)

    if errors:
        print("Validation FAILED:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validation OK: {manifest_path}")
    return 0


def _run_seal(args):
    """Subcomando seal: registra SHA-256 de los paths dados y congela el manifest."""
    try:
        manifest, manifest_path = _load_manifest(args.experiment_id)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if manifest.get("sealed"):
        print(
            "ERROR: experiment is already sealed. Re-sealing would break the "
            "blinding protocol (FND-05); seal each experiment only once.",
            file=sys.stderr,
        )
        return 1

    collected = {
        "dataset_hashes": {},
        "model_hashes": {},
        "binary_hashes": {},
        "assets_hashes": {},
    }
    for flag, key in (
        ("dataset", "dataset_hashes"),
        ("models", "model_hashes"),
        ("binaries", "binary_hashes"),
        ("assets", "assets_hashes"),
    ):
        for group in getattr(args, flag, None) or []:
            for raw_path in group:
                try:
                    collected[key].update(_collect_hashes(raw_path))
                except FileNotFoundError as exc:
                    print(f"ERROR: {exc}", file=sys.stderr)
                    return 1

    total_files = 0
    for key, entries in collected.items():
        if entries:
            manifest[key] = {**(manifest.get(key) or {}), **entries}
            total_files += len(entries)
    if total_files == 0:
        print(
            "WARNING: no paths given; sealing with the hash entries already "
            "recorded in the manifest (none added).",
            file=sys.stderr,
        )

    manifest["sealed"] = True
    manifest["sealed_at"] = _now_iso()
    if manifest.get("status") in ("created", "running"):
        manifest["status"] = "sealed"
    _write_json(manifest_path, manifest)
    _generar_readme(manifest_path.parent)

    print(
        f"Experiment '{args.experiment_id}' sealed: "
        f"{len(collected['dataset_hashes'])} dataset, "
        f"{len(collected['model_hashes'])} model, "
        f"{len(collected['binary_hashes'])} binary, "
        f"{len(collected['assets_hashes'])} asset file hash(es) recorded."
    )
    return 0


def _run_finish(args):
    """Subcomando finish: escribe la decisión final, la razón y la duración."""
    try:
        manifest, manifest_path = _load_manifest(args.experiment_id)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not manifest.get("sealed"):
        if args.decision == "GO":
            print(
                "ERROR: cannot record decision GO on an unsealed experiment; "
                "run 'seal' first.",
                file=sys.stderr,
            )
            return 1
        print(
            "WARNING: experiment was not sealed; the finish is recorded anyway "
            "(only non-GO decisions are allowed unsealed).",
            file=sys.stderr,
        )

    manifest["decision"] = args.decision
    manifest["decision_rationale"] = args.rationale
    manifest["finished_at"] = _now_iso()
    if args.duration_seconds is not None:
        manifest["duration_seconds"] = args.duration_seconds
    manifest["status"] = "finished"
    _write_json(manifest_path, manifest)
    _generar_readme(manifest_path.parent)

    print(
        f"Experiment '{args.experiment_id}' finished with decision {args.decision}."
    )
    return 0


def _run_maintain(args):
    """Subcomando maintain: mantenimiento auditado de assets sellados.

    Solo aplica a experimentos sellados y solo a assets. Cada asset cambiado
    registra una entrada en `seal_maintenance` (con el hash viejo preservado
    en `previous_hash`) y actualiza `assets_hashes`. Los buckets de
    datasets/modelos/binarios son inmutables.
    """
    try:
        manifest, manifest_path = _load_manifest(args.experiment_id)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not manifest.get("sealed"):
        print(
            "ERROR: maintain solo aplica a experimentos sellados.",
            file=sys.stderr,
        )
        return 1

    if not args.reason or not args.content_commit:
        print(
            "ERROR: --reason y --content-commit son obligatorios en maintain.",
            file=sys.stderr,
        )
        return 1

    if args.dataset or args.models or args.binaries:
        print(
            "ERROR: maintain solo mantiene assets; "
            "datasets/modelos/binarios son inmutables.",
            file=sys.stderr,
        )
        return 1

    current = {}
    for group in args.assets or []:
        for raw_path in group:
            try:
                current.update(_collect_hashes(raw_path))
            except FileNotFoundError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 1

    assets = manifest.get("assets_hashes") or {}
    immutable = {
        **(manifest.get("dataset_hashes") or {}),
        **(manifest.get("model_hashes") or {}),
        **(manifest.get("binary_hashes") or {}),
    }
    for stored in current:
        if stored in immutable:
            print(
                f"ERROR: {stored} belongs to dataset/model/binary hashes; "
                "those buckets are immutable (path not touched).",
                file=sys.stderr,
            )
            return 1
        if stored not in assets:
            print(
                f"ERROR: {stored} is not a sealed asset; "
                "maintain solo actualiza assets ya sellados.",
                file=sys.stderr,
            )
            return 1

    date = _now_iso()
    entries = manifest.get("seal_maintenance") or []
    maintained = 0
    unchanged = 0
    for stored, new_hash in sorted(current.items()):
        old_hash = assets[stored]
        if new_hash == old_hash:
            unchanged += 1
            print(f"- {stored}: unchanged, skipped")
            continue
        entries.append(
            {
                "date": date,
                "reason": args.reason,
                "path": stored,
                "previous_hash": old_hash,
                "new_hash": new_hash,
                "content_commit": args.content_commit,
            }
        )
        assets[stored] = new_hash
        maintained += 1

    manifest["seal_maintenance"] = entries
    manifest["assets_hashes"] = assets
    _write_json(manifest_path, manifest)
    _generar_readme(manifest_path.parent)

    print(f"{maintained} maintained, {unchanged} unchanged.")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser():
    """Construye el parser de argumentos con los cuatro subcomandos."""
    parser = argparse.ArgumentParser(
        prog="experiment_manifest.py",
        description=(
            "Registro único por experimento (FND-01): manifest prellenado, "
            "validación contra schema, sellado de hashes SHA-256 y decisión final."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_init = subparsers.add_parser(
        "init", help="crea el directorio del experimento con manifest y skeletons"
    )
    parser_init.add_argument("experiment_id", metavar="EXPERIMENT_ID")
    parser_init.add_argument("--hypothesis", required=True, help="hipótesis preregistrada")
    parser_init.add_argument("--protocol", required=True, help="referencia al protocolo")
    parser_init.add_argument("--gate", required=True, help="criterio de decisión (gate)")
    parser_init.add_argument(
        "--seeds", type=int, default=42, help="semilla preregistrada (default: 42)"
    )
    parser_init.add_argument(
        "--force",
        action="store_true",
        help="regenera los skeletons vacíos sin tocar un manifest.json existente",
    )
    parser_init.set_defaults(func=_run_init)

    parser_validate = subparsers.add_parser(
        "validate", help="valida el manifest contra el schema y los hashes sellados"
    )
    parser_validate.add_argument("experiment_id", metavar="EXPERIMENT_ID")
    parser_validate.set_defaults(func=_run_validate)

    parser_seal = subparsers.add_parser(
        "seal", help="registra SHA-256 de datasets/modelos/binarios/assets y sella el manifest"
    )
    parser_seal.add_argument("experiment_id", metavar="EXPERIMENT_ID")
    parser_seal.add_argument(
        "--dataset", action="append", nargs="+", default=None, metavar="PATH",
        help="archivo o directorio de dataset (recursivo); repetible",
    )
    parser_seal.add_argument(
        "--models", action="append", nargs="+", default=None, metavar="PATH",
        help="archivo o directorio de modelos (recursivo); repetible",
    )
    parser_seal.add_argument(
        "--binaries", action="append", nargs="+", default=None, metavar="PATH",
        help="archivo o directorio de binarios (recursivo); repetible",
    )
    parser_seal.add_argument(
        "--assets", action="append", nargs="+", default=None, metavar="PATH",
        help="archivo o directorio de assets (recursivo); repetible",
    )
    parser_seal.set_defaults(func=_run_seal)

    parser_finish = subparsers.add_parser(
        "finish", help="escribe la decisión final, la razón y la duración"
    )
    parser_finish.add_argument("experiment_id", metavar="EXPERIMENT_ID")
    parser_finish.add_argument(
        "--decision", required=True, choices=["GO", "NO_GO", "INCONCLUSIVE"],
        help="decisión del gate",
    )
    parser_finish.add_argument("--rationale", required=True, help="razonamiento de la decisión")
    parser_finish.add_argument(
        "--duration-seconds", type=float, default=None,
        help="duración total de la ejecución en segundos",
    )
    parser_finish.set_defaults(func=_run_finish)

    parser_maintain = subparsers.add_parser(
        "maintain",
        help="mantenimiento auditado de assets sellados que cambiaron tras el sello",
    )
    parser_maintain.add_argument("experiment_id", metavar="EXPERIMENT_ID")
    parser_maintain.add_argument(
        "--assets", action="append", nargs="+", default=None, metavar="PATH",
        help="archivo o directorio de assets a mantener (repetible); solo assets",
    )
    parser_maintain.add_argument(
        "--reason", default=None,
        help="motivo del mantenimiento (obligatorio)",
    )
    parser_maintain.add_argument(
        "--content-commit", default=None,
        help="commit git del cambio de contenido (obligatorio)",
    )
    parser_maintain.add_argument(
        "--dataset", action="append", nargs="+", default=None, metavar="PATH",
        help="rechazado en maintain: los datasets son inmutables",
    )
    parser_maintain.add_argument(
        "--models", action="append", nargs="+", default=None, metavar="PATH",
        help="rechazado en maintain: los modelos son inmutables",
    )
    parser_maintain.add_argument(
        "--binaries", action="append", nargs="+", default=None, metavar="PATH",
        help="rechazado en maintain: los binarios son inmutables",
    )
    parser_maintain.set_defaults(func=_run_maintain)

    return parser


def cmd_init(argv):
    """Punto de entrada del subcomando init, invocable desde tests."""
    return _run_init(_build_parser().parse_args(["init"] + list(argv)))


def cmd_validate(argv):
    """Punto de entrada del subcomando validate, invocable desde tests."""
    return _run_validate(_build_parser().parse_args(["validate"] + list(argv)))


def cmd_seal(argv):
    """Punto de entrada del subcomando seal, invocable desde tests."""
    return _run_seal(_build_parser().parse_args(["seal"] + list(argv)))


def cmd_finish(argv):
    """Punto de entrada del subcomando finish, invocable desde tests."""
    return _run_finish(_build_parser().parse_args(["finish"] + list(argv)))


def cmd_maintain(argv):
    """Punto de entrada del subcomando maintain, invocable desde tests."""
    return _run_maintain(_build_parser().parse_args(["maintain"] + list(argv)))


def main(argv=None):
    """Punto de entrada del CLI."""
    _reconfigure_stdio()
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
