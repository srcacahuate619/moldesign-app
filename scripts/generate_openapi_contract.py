"""Genera y verifica el contrato OpenAPI versionado de MolDesign.

Uso:
    python scripts/generate_openapi_contract.py --write
    python scripts/generate_openapi_contract.py --check
    python scripts/generate_openapi_contract.py --diff

El snapshot JSON y el mapa Markdown se derivan del mismo ``FastAPI.app``. No
hay una segunda lista de endpoints mantenida a mano.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SNAPSHOT_PATH = ROOT / "docs" / "api" / "openapi-current.json"
MAP_PATH = ROOT / "docs" / "45_API_CONTRACT_CURRENT.md"
HTTP_METHODS = ("delete", "get", "head", "options", "patch", "post", "put")


def load_schema() -> dict:
    """Carga el schema sin arrancar lifespan, red ni recursos pesados."""
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))

    from api.main import app

    return app.openapi()


def serialize_schema(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _operations(schema: dict) -> dict[tuple[str, str], dict]:
    return {
        (method, path): operation
        for path, path_item in schema.get("paths", {}).items()
        for method, operation in path_item.items()
        if method in HTTP_METHODS
    }


def _required_parameters(schema: dict, method: str, path: str) -> set[tuple[str, str]]:
    path_item = schema["paths"][path]
    operation = path_item[method]
    parameters = [*path_item.get("parameters", []), *operation.get("parameters", [])]
    return {
        (parameter.get("in", ""), parameter.get("name", ""))
        for parameter in parameters
        if parameter.get("required") and parameter.get("in") and parameter.get("name")
    }


def _success_responses(operation: dict) -> set[str]:
    return {
        str(status)
        for status in operation.get("responses", {})
        if str(status).startswith("2")
    }


def breaking_changes(previous: dict, current: dict) -> list[str]:
    """Devuelve incompatibilidades HTTP detectables sin adivinar schemas.

    Es deliberadamente conservador: una adición no es breaking; retirar una
    ruta/operación/respuesta 2xx o exigir un parámetro nuevo sí requiere que el
    maintainer lo revise. La compatibilidad profunda de schemas queda explícita
    como mejora futura, no como una afirmación falsa de cobertura total.
    """
    changes: list[str] = []
    previous_paths = set(previous.get("paths", {}))
    current_paths = set(current.get("paths", {}))
    for path in sorted(previous_paths - current_paths):
        changes.append(f"ruta eliminada: {path}")

    old_operations = _operations(previous)
    new_operations = _operations(current)
    for method, path in sorted(old_operations):
        label = f"{method.upper()} {path}"
        if (method, path) not in new_operations:
            changes.append(f"operación eliminada: {label}")
            continue

        old_required = _required_parameters(previous, method, path)
        new_required = _required_parameters(current, method, path)
        for location, name in sorted(new_required - old_required):
            changes.append(f"parámetro requerido nuevo: {label} ({location} {name})")
        for location, name in sorted(old_required - new_required):
            changes.append(f"parámetro requerido retirado: {label} ({location} {name})")

        removed_success = _success_responses(old_operations[(method, path)]) - _success_responses(
            new_operations[(method, path)]
        )
        for status in sorted(removed_success):
            changes.append(f"respuesta exitosa retirada: {label} ({status})")
    return changes


def _cell(value: object) -> str:
    return " ".join(str(value or "—").split()).replace("|", "\\|")


def render_map(schema: dict, snapshot_text: str) -> str:
    paths = schema["paths"]
    operations = [
        (path, method, operation)
        for path, path_item in sorted(paths.items())
        for method, operation in sorted(path_item.items())
        if method in HTTP_METHODS
    ]
    digest = hashlib.sha256(snapshot_text.encode("utf-8")).hexdigest()

    rows = [
        "| Método | Ruta | operationId | Resumen | Tags |",
        "|---|---|---|---|---|",
    ]
    for path, method, operation in operations:
        rows.append(
            "| "
            f"`{method.upper()}` | `{path}` | `{_cell(operation.get('operationId'))}` | "
            f"{_cell(operation.get('summary'))} | {_cell(', '.join(operation.get('tags', [])))} |"
        )

    return "\n".join(
        [
            "# 45 — Contrato API actual (generado)",
            "",
            "**Estado:** 🟢 Contrato vigente generado desde el backend.",
            "",
            "Este mapa y el snapshot JSON se derivan de `backend/api/main.py`; "
            "no se editan manualmente. `docs/31_PIPELINE_DATA_INVENTORY.md` y "
            "`docs/32_CROSS_VALIDATION_EVALUATION_TAB.md` permanecen como "
            "inventarios históricos de UX.",
            "",
            "## Identidad del snapshot",
            "",
            f"- Paths: **{len(paths)}**",
            f"- Operaciones HTTP: **{len(operations)}**",
            f"- Versión declarada: `{schema.get('info', {}).get('version', '—')}`",
            f"- SHA-256: `{digest}`",
            f"- Schema completo: [api/openapi-current.json](api/openapi-current.json)",
            "- Regenerar: `python scripts/generate_openapi_contract.py --write`",
            "- Verificar en CI: `python scripts/generate_openapi_contract.py --check`",
            "- Revisar incompatibilidades: `python scripts/generate_openapi_contract.py --diff`",
            "",
            "## Operaciones",
            "",
            *rows,
            "",
        ]
    )


def expected_outputs() -> dict[Path, str]:
    schema = load_schema()
    snapshot_text = serialize_schema(schema)
    return {
        SNAPSHOT_PATH: snapshot_text,
        MAP_PATH: render_map(schema, snapshot_text),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="escribe los artefactos generados")
    mode.add_argument("--check", action="store_true", help="falla si los artefactos están desactualizados")
    mode.add_argument("--diff", action="store_true", help="reporta incompatibilidades contra el snapshot")
    parser.add_argument(
        "--allow-breaking",
        action="store_true",
        help="reconoce una incompatibilidad al actualizar el snapshot",
    )
    args = parser.parse_args()

    outputs = expected_outputs()
    stale = [path for path, content in outputs.items() if not path.is_file() or path.read_text(encoding="utf-8") != content]
    current_schema = json.loads(outputs[SNAPSHOT_PATH])
    previous_schema = (
        json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        if SNAPSHOT_PATH.is_file()
        else None
    )
    changes = breaking_changes(previous_schema, current_schema) if previous_schema else []

    if args.diff:
        if previous_schema is None:
            print("No existe snapshot previo para comparar")
            return 1
        if changes:
            print("Incompatibilidades OpenAPI detectadas:")
            for change in changes:
                print(f" - {change}")
            return 1
        print("OpenAPI: no se detectaron incompatibilidades HTTP básicas")
        return 0

    if args.check:
        if stale:
            print("OpenAPI desactualizado: ejecuta python scripts/generate_openapi_contract.py --write")
            if changes:
                print("Incompatibilidades detectadas antes de actualizarlo:")
                for change in changes:
                    print(f" - {change}")
            for path in stale:
                print(f" - {path.relative_to(ROOT)}")
            return 1
        print(f"OpenAPI verificado: {len(outputs)} artefactos vigentes")
        return 0

    if changes and not args.allow_breaking:
        print("Se rechazó actualizar un snapshot con incompatibilidades OpenAPI:")
        for change in changes:
            print(f" - {change}")
        print("Revisa los clientes y repite con --write --allow-breaking si el cambio es intencional.")
        return 1

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Generado: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
