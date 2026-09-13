"""Contratos del detector de incompatibilidades del snapshot OpenAPI."""

from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_openapi_contract.py"
SPEC = importlib.util.spec_from_file_location("openapi_contract_generator", SCRIPT)
assert SPEC and SPEC.loader
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


def _schema(path_item: dict) -> dict:
    return {"paths": {"/evaluation": path_item}}


def test_breaking_changes_ignores_additive_api_changes():
    previous = _schema({"get": {"responses": {"200": {}}}})
    current = _schema(
        {
            "get": {"responses": {"200": {}}},
            "post": {"responses": {"201": {}}},
        }
    )

    assert GENERATOR.breaking_changes(previous, current) == []


def test_breaking_changes_reports_removed_operation_required_parameter_and_success_response():
    previous = _schema(
        {
            "parameters": [{"in": "query", "name": "limit", "required": True}],
            "get": {"responses": {"200": {}, "204": {}}},
            "post": {"responses": {"201": {}}},
        }
    )
    current = _schema(
        {
            "parameters": [{"in": "query", "name": "limit", "required": True}],
            "get": {
                "parameters": [{"in": "header", "name": "x-client", "required": True}],
                "responses": {"200": {}},
            },
        }
    )

    changes = GENERATOR.breaking_changes(previous, current)

    assert "operación eliminada: POST /evaluation" in changes
    assert "parámetro requerido nuevo: GET /evaluation (header x-client)" in changes
    assert "respuesta exitosa retirada: GET /evaluation (204)" in changes
