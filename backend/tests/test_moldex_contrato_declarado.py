"""MOLDEX-INT-013 — el catálogo debe tener contrato declarado.

`GET /moldex` devolvía `dict[str, Any]`. FastAPI no puede derivar esquema de
eso, así que la ruta **no aparecía** en `docs/api/openapi-current.json` y la
guarda que detecta campos renombrados u omitidos
(`frontend/lib/__tests__/evaluationResultContract.test.ts`) no podía cubrirla.

El contrato del catálogo dependía de que alguien recordara actualizar
`lib/moldex.ts` a mano. Es exactamente la deriva que esa guarda existe para
impedir — y el precedente es reciente: al tipar el estado de la página,
TypeScript encontró en el acto un defecto que la lectura no había visto
(MOLDEX-SCI-014).
"""

from __future__ import annotations

from api import moldex


def _ruta_del_catalogo():
    for ruta in moldex.router.routes:
        if "GET" in getattr(ruta, "methods", set()):
            return ruta
    raise AssertionError("no se encontró la ruta del catálogo")


def test_el_catalogo_declara_response_model():
    ruta = _ruta_del_catalogo()

    assert ruta.response_model is not None
    assert ruta.response_model is moldex.MoldexCatalogRead


def test_el_esquema_declara_la_procedencia_de_cada_ficha():
    campos = moldex.MoldexProvenanceRead.model_fields

    assert set(campos) == {
        "task_id",
        "receptor_sha256",
        "engine_version",
        "random_seed",
        "docking_protocol",
    }
    # Todo puede faltar en una corrida heredada; nada se rellena.
    assert all(not campo.is_required() for campo in campos.values())


def test_el_esquema_del_sello_admite_indeterminado():
    campos = moldex.MoldexSealRead.model_fields

    assert "matches_current_run" in campos
    # MOLDEX-SCI-001: el tercer valor es `None`, y tiene que caber en el tipo.
    assert not campos["matches_current_run"].is_required()


def test_las_metricas_admiten_ausencia_sin_convertirse_en_cero():
    campos = moldex.MoldexMetricsRead.model_fields

    for nombre in ("affinity", "log_p", "mw", "tpsa", "score"):
        assert nombre in campos
        assert not campos[nombre].is_required()


def test_el_esquema_no_publica_la_ruta_local_del_receptor():
    # EVAL-INT-008: el hash se publica, la ruta privada del usuario no.
    assert "receptor_path" not in moldex.MoldexProvenanceRead.model_fields
    assert "receptor_path" not in moldex.MoldexMoleculeRead.model_fields


def test_la_cl_gnn_llega_a_moldex_y_la_gnn_legacy_no_se_rompe():
    """Decisión del propietario (2026-09-23): la CL-GNN se enseña, marcada experimental.

    `gnn_score` (RTMScore) se queda en el contrato por las bases antiguas, aunque en
    una corrida de escritorio siempre llegue nulo. Ninguna de las dos es obligatoria:
    una ausencia no puede convertirse en un cero.
    """
    campos = moldex.MoldexMetricsRead.model_fields

    for nombre in ("gnn_score", "clgnn_score"):
        assert nombre in campos
        assert not campos[nombre].is_required()
