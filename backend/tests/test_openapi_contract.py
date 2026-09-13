"""Contratos mínimos para que la documentación OpenAPI sea generable."""

from __future__ import annotations

from collections import Counter

from fastapi.routing import APIRoute

from api.main import app


def test_openapi_operation_ids_are_unique():
    """Una ruta duplicada vuelve ambiguos clientes y snapshots de API."""
    schema = app.openapi()
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete", "head", "options"}
    ]

    assert len(operation_ids) == len(set(operation_ids))


def test_runtime_route_method_pairs_are_unique():
    """FastAPI resolvería sólo el primer handler si se repitiera una pareja."""
    pairs = [
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    ]

    assert not [pair for pair, count in Counter(pairs).items() if count > 1]
