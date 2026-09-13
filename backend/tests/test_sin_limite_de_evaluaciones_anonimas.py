"""TRANS-ANON-002 — el escritorio no cuenta evaluaciones anónimas.

`_enforce_submission_gates` aplicaba un cupo de evaluaciones gratuitas por
**dirección IP** (`AnonymousLimitORM`, `anonymous_rate_limit`). Es maquinaria de
un embudo de conversión SaaS que en un producto de escritorio local no mide nada:

- todo corre sobre `127.0.0.1`, así que la IP no distingue a nadie;
- el cupo acababa siendo por máquina, no por persona;
- el ajuste ya estaba neutralizado con `default=999` y la descripción «Sin
  límite en desktop», pero el contador seguía escribiendo en la base y el 403
  seguía existiendo al llegar al tope;
- el endpoint `/evaluation/limit-status` y su cliente `getLimitStatus` no
  tenían ningún consumidor en la interfaz.

Decisión del propietario (2026-08-30): sin cuenta se puede **evaluar** sin
límite; hace falta cuenta para **guardar** en Moldex y para **certificar**.
"""

from __future__ import annotations

import pytest

from api.routers import evaluation
from db.repository import Repository
from tests._fuente import codigo_ejecutable


def test_el_router_no_conserva_la_maquinaria_del_cupo():
    fuente = codigo_ejecutable(evaluation)

    assert "get_anonymous_limit" not in fuente
    assert "increment_anonymous_count" not in fuente
    assert "anonymous_rate_limit" not in fuente


def test_el_repositorio_no_expone_contadores_anonimos():
    assert not hasattr(Repository, "get_anonymous_limit")
    assert not hasattr(Repository, "increment_anonymous_count")


def test_no_queda_endpoint_de_estado_de_limite():
    rutas = {
        getattr(r, "path", None) for r in evaluation.router.routes
    }

    assert "/limit-status" not in rutas
    assert not any(r and "limit" in r for r in rutas)


@pytest.mark.asyncio
async def test_una_evaluacion_anonima_no_se_bloquea_por_cupo(monkeypatch):
    """El camino sin cuenta llega al final de las compuertas sin 403 de cupo.

    Se ejercita `_enforce_submission_gates` con preflight ya conforme: lo único
    que podía interponerse después era el cupo. Si alguien lo reintroduce, esta
    llamada vuelve a lanzar.
    """
    from types import SimpleNamespace

    llamadas: list[str] = []

    class _RepoEspia:
        def __getattr__(self, nombre):
            llamadas.append(nombre)
            raise AssertionError(
                f"el camino anónimo no debe consultar el repositorio para cupos: {nombre}"
            )

    datos = SimpleNamespace(
        smiles="CCO",
        target_pdb_id="7E2Y",
        chain=None,
        pipeline_config=None,
        preflight_fingerprint=None,
    )

    # Sin `preflight_fingerprint` la revalidación no entra, así que la función
    # sólo puede fallar si el cupo sigue ahí.
    await evaluation._enforce_submission_gates(
        data=datos,
        canonical_smiles="CCO",
        request=SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"), headers={}),
        repository=_RepoEspia(),
        db=object(),
        current_user=None,
        submission_target=None,
    )

    assert llamadas == []
