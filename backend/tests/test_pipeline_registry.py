"""
Tests del registro de etapas del pipeline (services/pipeline/registry.py).

Cubre la lógica nueva de la v2.0 (cambio evaluation-e2e):

- Metadata del registro: dependencias (clgnn requiere docking, xgb requiere
  docking), defaults de enabled (openmm desactivado por defecto) y requeridos.
- validate_order(): auto-inclusión de requeridos, filtrado de ids desconocidos
  y orden topológico.
- expand_legacy_alias(): el alias legacy "rescoring" → ["xgb", "clgnn"] en
  enabled_stages, stage_order y stage_params (sin mutar la entrada).
- resolve_stage_order(): decisión del orden final (habilitados + requeridos).
- skipped_stage_ids(): qué etapas quedan fuera → el runner las emite como
  stage_skipped (contrato SSE).

Pura lógica, sin DB, sin red, sin mocks de infraestructura.

Cómo correr (desde backend/):
    python -m pytest tests/test_pipeline_registry.py -q
"""
from __future__ import annotations

import pytest

from services.pipeline.registry import (
    STAGE_REGISTRY,
    expand_legacy_alias,
    resolve_stage_order,
    skipped_stage_ids,
    validate_order,
)

# Orden canónico del registro (definición, no inferido del dict en runtime)
CANONICAL_STAGE_ORDER = [
    "validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn", "openmm", "selectivity",
]


# ═════════════════════════════════════════════════════════════════════════════
# Metadata del registro
# ═════════════════════════════════════════════════════════════════════════════


class TestStageRegistryMetadata:
    """Definición estática de etapas: ids, orden, dependencias, defaults."""

    def test_canonical_order_matches_definition(self):
        """El registro expone exactamente las etapas canónicas en orden."""
        assert list(STAGE_REGISTRY.keys()) == CANONICAL_STAGE_ORDER

    def test_ml_stages_depend_on_docking(self):
        """xgb y clgnn requieren docking (usan las poses de Vina)."""
        assert "docking" in STAGE_REGISTRY["xgb"].dependencies
        assert "docking" in STAGE_REGISTRY["clgnn"].dependencies
        assert "docking" in STAGE_REGISTRY["openmm"].dependencies

    def test_docking_depends_on_conformer_depends_on_properties(self):
        """Cadena de dependencias previa al docking."""
        assert "conformer" in STAGE_REGISTRY["docking"].dependencies
        assert "properties" in STAGE_REGISTRY["conformer"].dependencies
        assert "validation" in STAGE_REGISTRY["properties"].dependencies

    def test_required_stages(self):
        """validation→xgb son requeridas; etapas L2/L3 son opcionales."""
        for sid in ["validation", "properties", "sa_filter", "conformer", "docking", "xgb"]:
            assert STAGE_REGISTRY[sid].required is True, f"{sid} debería ser requerida"
        assert STAGE_REGISTRY["clgnn"].required is False
        assert STAGE_REGISTRY["openmm"].required is False
        assert STAGE_REGISTRY["selectivity"].required is False

    def test_expensive_optional_stages_are_disabled_by_default(self):
        """openmm y selectivity sólo corren por una solicitud explícita."""
        assert STAGE_REGISTRY["openmm"].enabled is False
        assert STAGE_REGISTRY["selectivity"].enabled is False
        # Las demás etapas están habilitadas por defecto
        for sid in ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"]:
            assert STAGE_REGISTRY[sid].enabled is True, f"{sid} debería estar enabled por defecto"

    def test_every_stage_has_unique_id_and_label(self):
        """Cada etapa se autodefine con id consistente con su key en el dict."""
        labels = set()
        for sid, stage in STAGE_REGISTRY.items():
            assert stage.id == sid
            assert stage.label
            assert stage.label not in labels
            labels.add(stage.label)


# ═════════════════════════════════════════════════════════════════════════════
# validate_order
# ═════════════════════════════════════════════════════════════════════════════


class TestValidateOrder:
    """Orden topológico + auto-inclusión de requeridas."""

    def test_required_stages_are_auto_added(self):
        """Una lista incompleta se completa con las requeridas faltantes."""
        ordered, warnings = validate_order(["docking"])
        assert set(["validation", "properties", "sa_filter", "conformer", "docking", "xgb"]).issubset(set(ordered))
        assert any("obligatoria" in w for w in warnings)

    def test_unknown_ids_are_filtered_out(self):
        """Ids que no existen en el registro se descartan sin crash."""
        ordered, _ = validate_order(["docking", "stage_fantasma"])
        assert "stage_fantasma" not in ordered
        assert "docking" in ordered

    def test_topological_order_docking_before_ml(self):
        """xgb/clgnn/openmm corren después de docking; xgb antes que clgnn."""
        ordered, _ = validate_order(["xgb", "clgnn", "openmm", "docking"])
        assert ordered.index("docking") < ordered.index("xgb")
        assert ordered.index("docking") < ordered.index("clgnn")
        assert ordered.index("docking") < ordered.index("openmm")
        assert ordered.index("xgb") < ordered.index("clgnn")

    def test_dependencies_are_satisfied_for_full_default_order(self):
        """Con el orden completo del registro, toda dependencia va antes."""
        ordered, _ = validate_order(list(STAGE_REGISTRY.keys()))
        for stage_id in ordered:
            for dep in STAGE_REGISTRY[stage_id].dependencies:
                assert ordered.index(dep) < ordered.index(stage_id)


# ═════════════════════════════════════════════════════════════════════════════
# expand_legacy_alias ("rescoring" → xgb + clgnn)
# ═════════════════════════════════════════════════════════════════════════════


class TestExpandLegacyAlias:
    """El alias legacy "rescoring" se expande a xgb + clgnn en secuencia."""

    def test_enabled_stages_expansion(self):
        """enabled_stages con rescoring → xgb y clgnn agregados al final."""
        enabled, _, _ = expand_legacy_alias(["validation", "rescoring"], None, None)
        assert enabled == ["validation", "xgb", "clgnn"]

    def test_stage_order_expansion(self):
        """stage_order con rescoring → reemplazado por xgb + clgnn (al final)."""
        _, order, _ = expand_legacy_alias(None, ["conformer", "rescoring", "openmm"], None)
        assert order == ["conformer", "openmm", "xgb", "clgnn"]

    def test_no_rescoring_leaves_lists_untouched(self):
        """Sin el alias, las estructuras no cambian."""
        enabled, order, params = expand_legacy_alias(["validation", "xgb"], ["validation", "xgb"], {"xgb": {"trees": 500}})
        assert enabled == ["validation", "xgb"]
        assert order == ["validation", "xgb"]
        assert params == {"xgb": {"trees": 500}}

    def test_none_inputs_return_none(self):
        """Entradas None pasan sin crash (compatibilidad con callers)."""
        enabled, order, params = expand_legacy_alias(None, None, None)
        assert enabled is None
        assert order is None
        assert params is None

    def test_stage_params_merge_legacy_into_both(self):
        """Los params de rescoring se fusionan en xgb y clgnn."""
        _, _, params = expand_legacy_alias(
            None,
            None,
            {"rescoring": {"run_xgb": True}, "xgb": {"trees": 500}},
        )
        assert "rescoring" not in params
        assert params["xgb"] == {"run_xgb": True, "trees": 500}
        assert params["clgnn"] == {"run_xgb": True}

    def test_stage_params_do_not_mutate_input(self):
        """La expansión no muta el dict de entrada (devuelve uno nuevo)."""
        original = {"rescoring": {"run_xgb": True}}
        expand_legacy_alias(None, None, original)
        assert original == {"rescoring": {"run_xgb": True}}


# ═════════════════════════════════════════════════════════════════════════════
# resolve_stage_order + skipped_stage_ids (decisión de stages del runner)
# ═════════════════════════════════════════════════════════════════════════════


class TestResolveStageOrder:
    """Decisión del orden final: habilitados + requeridos, topo-sort."""

    def test_none_enabled_runs_only_required(self):
        """enabled_stages=None → corren solo las requeridas (clgnn/openmm/selectivity
        opcionales quedan fuera y se emiten como stage_skipped). Es el default
        del runner: pipeline_config.get('enabled_stages', []) → []."""
        ordered = resolve_stage_order(None, None)
        assert ordered == ["validation", "properties", "sa_filter", "conformer", "docking", "xgb"]
        assert skipped_stage_ids(ordered) == ["clgnn", "openmm", "selectivity"]

    def test_full_enabled_list_runs_all(self):
        """Todas las etapas + pro_selectivity → corre el grafo canónico completo."""
        ordered = resolve_stage_order(
            list(STAGE_REGISTRY.keys()),
            None,
            selectivity_enabled=True,
        )
        assert ordered == CANONICAL_STAGE_ORDER

    def test_disabled_optional_stages_are_excluded(self):
        """openmm/selectivity no solicitados → quedan fuera del plan."""
        enabled = [s for s in CANONICAL_STAGE_ORDER if s != "openmm"]
        ordered = resolve_stage_order(enabled, None)
        assert "openmm" not in ordered
        assert "selectivity" not in ordered
        assert "openmm" in skipped_stage_ids(ordered)

    def test_selectivity_requires_explicit_product_option(self):
        """pro_selectivity gobierna la etapa aunque el cliente omita su id."""
        enabled = ["validation", "properties", "sa_filter", "conformer", "docking", "xgb"]
        ordered = resolve_stage_order(enabled, None, selectivity_enabled=True)
        assert ordered[-1] == "selectivity"
        assert "docking" in ordered
        assert ordered.index("docking") < ordered.index("selectivity")

    def test_selectivity_is_not_enabled_by_a_stale_stage_list(self):
        """Un payload legacy no puede activar Safety Panel sin pro_selectivity."""
        ordered = resolve_stage_order(["selectivity"], None, selectivity_enabled=False)
        assert "selectivity" not in ordered

    def test_required_stages_are_kept_even_if_not_enabled(self):
        """Las requeridas corren aunque no vengan en enabled_stages."""
        ordered = resolve_stage_order(["docking"], None)
        for sid in ["validation", "properties", "sa_filter", "conformer", "xgb"]:
            assert sid in ordered

    def test_enabled_none_means_only_required(self):
        """enabled_stages=None → corren solo las requeridas (sin crash)."""
        ordered = resolve_stage_order(None, ["docking", "openmm", "clgnn"])
        assert "openmm" not in ordered
        assert "clgnn" not in ordered
        for sid in ["validation", "properties", "sa_filter", "conformer", "docking", "xgb"]:
            assert sid in ordered

    def test_un_flujo_controlado_puede_omitir_xgb_sin_cambiar_el_default(self):
        stages = {"validation", "properties", "sa_filter", "conformer", "docking"}
        ordered = resolve_stage_order(list(stages), None, required_stage_ids=stages)
        assert set(ordered) == stages
        assert "xgb" not in ordered
        assert "xgb" in resolve_stage_order(["docking"], None)


class TestSkippedStageIds:
    """Qué etapas se emiten como stage_skipped (contrato SSE del runner)."""

    def test_full_order_skips_nothing(self):
        assert skipped_stage_ids(CANONICAL_STAGE_ORDER) == []

    def test_missing_stage_is_skipped(self):
        """Una etapa fuera del plan aparece en skipped (orden del registro)."""
        plan = [s for s in CANONICAL_STAGE_ORDER if s != "openmm"]
        assert skipped_stage_ids(plan) == ["openmm"]

    def test_disabled_ml_stages_are_skipped(self):
        """Stages opcionales/ML fuera del plan → SSE los explica como skipped."""
        plan = ["validation", "properties", "sa_filter", "conformer", "docking"]
        assert skipped_stage_ids(plan) == ["xgb", "clgnn", "openmm", "selectivity"]


# ═════════════════════════════════════════════════════════════════════════════
# Contrato SSE entre backend y frontend
# ═════════════════════════════════════════════════════════════════════════════


class TestSseContract:
    """Los stage_id del SSE son ids válidos del registro (contrato cross-stack)."""

    # Espejo del map SSE_TO_ORB del frontend (lib/pipelineStream.ts). Se
    # hardcodea acá a propósito: es un contrato entre dos lenguajes.
    SSE_STAGE_IDS = {
        "validation", "conformer", "docking", "xgb", "clgnn", "openmm", "mmgbsa",
    }
    # Stages del registro SIN orb: pre-score o panel post-hoc de seguridad.
    NON_ORB_STAGE_IDS = {"properties", "sa_filter", "selectivity"}

    def test_all_sse_stage_ids_exist_in_registry(self):
        """Cada stage_id que el frontend mapea a un orb existe en el registro."""
        for sid in self.SSE_STAGE_IDS - {"mmgbsa"}:  # mmgbsa es post-hoc del frontend
            assert sid in STAGE_REGISTRY, f"SSE stage_id '{sid}' no está en STAGE_REGISTRY"

    def test_non_orb_stages_exist_in_registry(self):
        """properties/sa_filter emiten SSE pero no tienen orb en el DOT."""
        for sid in self.NON_ORB_STAGE_IDS:
            assert sid in STAGE_REGISTRY

    def test_mmgbsa_is_frontend_only(self):
        """mmgbsa no es etapa del registro (se calcula on-demand / post-hoc)."""
        assert "mmgbsa" not in STAGE_REGISTRY

    @pytest.mark.parametrize(
        "enabled_subset,expected_skipped",
        [
            # openmm/selectivity no solicitados → stage_skipped en el SSE
            (["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"], ["openmm", "selectivity"]),
            # CL-GNN y etapas costosas fuera → stage_skipped en el SSE
            (["validation", "properties", "sa_filter", "conformer", "docking", "xgb"], ["clgnn", "openmm", "selectivity"]),
        ],
    )
    def test_skipped_stages_contract(self, enabled_subset, expected_skipped):
        """Etapas no habilitadas → el runner las emite como stage_skipped."""
        ordered = resolve_stage_order(enabled_subset, None)
        assert skipped_stage_ids(ordered) == expected_skipped
