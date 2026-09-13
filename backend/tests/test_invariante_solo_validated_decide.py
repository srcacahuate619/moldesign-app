"""Un score no validado no toca ninguna decisión. Cerrado por defecto.

═══════════════════════════════════════════════════════════════════════════
LA REGLA QUE ESTA SUITE DEFIENDE
═══════════════════════════════════════════════════════════════════════════

    Sólo un resultado con estado explícito VALIDATED puede alimentar una
    decisión derivada. Cualquier otro estado queda excluido.

Lista blanca de un elemento, no lista negra. El día que aparezca un estado
nuevo, una lista negra lo dejaría pasar por omisión — y este producto ya vivió
esa forma de fallo: `REVIEW_INVALID_BENCHMARK_SITE` y
`REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING` nacieron DESPUÉS de conectar
M5-Zn al pipeline.

═══════════════════════════════════════════════════════════════════════════
CÓMO SE COMPRUEBA
═══════════════════════════════════════════════════════════════════════════

Se inyecta deliberadamente un `m5_score` ALTO —0.99, el mejor posible— junto a
cada estado no validado, y se comprueba que no aparece en ninguna superficie de
decisión. Un score bajo no probaría nada: podría estar entrando y no notarse.
"""

from __future__ import annotations

import json

import pytest

from services.pipeline.protocols.interpretabilidad import (
    bloque_de_auditoria,
    es_interpretable,
    score_para_decision,
)

#: Todos los estados que M5-Zn puede producir hoy, más un inventado. El último
#: es el importante: representa el estado que se añadirá mañana.
ESTADOS_NO_VALIDADOS = [
    "NOT_EVALUATED_MISSING_COMPONENT",
    "NOT_EVALUATED_PROTOCOL_NOT_EXECUTED",
    "REVIEW_OUT_OF_VALIDATED_TARGET",
    "REVIEW_OUT_OF_VALIDATED_STRUCTURE",
    "REVIEW_INVALID_BENCHMARK_SITE",
    "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE",
    "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING",
    "BLOCKED_PROTOCOL_NOT_AVAILABLE",
    "UN_ESTADO_QUE_TODAVIA_NO_EXISTE",
    None,
    "",
]

#: Deliberadamente alto: si se colara en un ranking, se notaría.
SCORE_ALTO = 0.99


# ── La regla, en su forma más desnuda ────────────────────────────────────

@pytest.mark.parametrize("estado", ESTADOS_NO_VALIDADOS)
def test_ningun_estado_no_validado_habilita(estado):
    assert es_interpretable(estado) is False


def test_solo_validated_habilita():
    assert es_interpretable("VALIDATED") is True
    assert es_interpretable("validated") is True, "la comparación normaliza caja"
    assert es_interpretable("VALIDATED_PROFILE") is False, (
        "el estado habilitante es exactamente VALIDATED; un nombre parecido no "
        "cuenta, porque la lista blanca sólo protege si es literal"
    )


@pytest.mark.parametrize("estado", ESTADOS_NO_VALIDADOS)
def test_el_score_no_llega_a_la_decision(estado):
    assert score_para_decision(SCORE_ALTO, estado) is None


def test_la_exclusion_no_es_un_cero():
    """Un cero es una predicción; la exclusión no lo es.

    Devolver 0.0 metería el caso al final del ranking, que es una posición —y
    por tanto una afirmación—. `None` lo saca del ranking.
    """
    assert score_para_decision(SCORE_ALTO, "REVIEW_INVALID_BENCHMARK_SITE") is None
    assert score_para_decision(SCORE_ALTO, "VALIDATED") == pytest.approx(0.99)


# ── Las siete superficies de decisión ────────────────────────────────────

def _resultado(estado, score=SCORE_ALTO):
    """Un resultado con M5 puntuado alto y en el estado dado."""
    from types import SimpleNamespace

    return SimpleNamespace(
        affinity_kcal=-6.5,
        docking_poses=[{"affinity": -6.5}],
        heavy_atom_count=16,
        target_family="metalloenzyme",
        xgb_score=0.84,
        clgnn_score=None,
        gnn_score=None,
        quantum_score=None,
        mmgbsa_score=None,
        ums_score=0.9167,
        ums_warhead=0.9167,
        m5_score=score,
        m5_protocol_id="M5_ZN_MMP9_1GKC_V1",
        m5_scientific_status=estado,
        model_used="universal",
        in_applicability_domain=True,
        shap_values={"LogP": -0.2},
        total_score=71.0,
        stacking_vina_weight=0.2,
        stacking_xgb_weight=0.6,
        stacking_gnn_weight=0.0,
        stacking_clgnn_weight=0.2,
    )


@pytest.mark.parametrize("estado", [e for e in ESTADOS_NO_VALIDADOS if e])
def test_no_entra_en_el_resumen_de_evidencia_como_conclusion(estado):
    """Puede estar en la auditoría; no puede estar en las conclusiones."""
    from services.blockchain.evidence_summary import build_evidence_summary

    resumen = build_evidence_summary(_resultado(estado), None, None)
    # Las superficies que un lector toma como conclusión.
    conclusiones = json.dumps(
        {
            "dimensions": resumen.get("dimensions"),
            "uncertainties": resumen.get("uncertainties"),
            "next_action": resumen.get("next_action"),
        },
        ensure_ascii=False, default=str,
    )
    assert "0.99" not in conclusiones, (
        f"con estado {estado!r}, el score M5 aparece en una conclusión del "
        f"resumen de evidencia"
    )


@pytest.mark.parametrize("estado", [e for e in ESTADOS_NO_VALIDADOS if e])
def test_no_entra_en_total_score_ni_en_el_ranking(estado):
    """`total_score` no lo mira, y esta prueba lo fija por si algún día lo mira.

    Hoy `scoring/engine.py` ni siquiera recibe `m5_score`: el ADR 75 retiró el
    empujón aditivo de UMS y el score compuesto lo calcula el perfil aparte.
    Comprobarlo aquí impide que se reconecte sin pasar por la regla.
    """
    import inspect

    from scoring import engine

    fuente = inspect.getsource(engine)
    codigo = "\n".join(
        l for l in fuente.splitlines() if not l.strip().startswith("#")
    )
    assert "m5_score" not in codigo, (
        "el motor de scoring empezó a leer `m5_score`. Si es intencional, tiene "
        "que pasar por `score_para_decision`, que excluye todo lo que no esté "
        "VALIDATED."
    )


@pytest.mark.parametrize("estado", [e for e in ESTADOS_NO_VALIDADOS if e])
def test_el_dossier_no_lo_presenta_como_conclusion(estado):
    """En el dossier el número SÍ se ve — y nunca sin su estado al lado."""
    from services.dossier.bloques_protocolo import campos_de_m5_zn
    from services.dossier.model import Campo, _campo_dato, _v
    from types import SimpleNamespace

    campos = [
        c.as_dict() for c in campos_de_m5_zn(
            Campo, _campo_dato, _v, _resultado(estado),
            {"top_pose_affinity": -7.2}, SimpleNamespace(pdb_id="1GKC"),
        )
    ]
    score = next(c for c in campos if c["etiqueta"].startswith("Score compuesto"))
    assert score["estado"] != "REGISTRADO", (
        f"con estado {estado!r} el dossier presenta el score como un dato "
        "registrado, es decir, como conclusión"
    )
    if score["valor"] and "0.99" in score["valor"]:
        assert score["razon"], (
            "si el número se imprime, tiene que venir con su motivo: un score "
            "sin explicación es indistinguible de una conclusión"
        )


def test_el_bloque_de_auditoria_declara_que_no_habilita():
    """La única forma en que un score no validado puede viajar."""
    bloque = bloque_de_auditoria(
        SCORE_ALTO, "REVIEW_INVALID_BENCHMARK_SITE", "el benchmark está en revisión"
    )
    assert bloque["score"] == pytest.approx(0.99), "el número no se oculta"
    assert bloque["eligible_for_scientific_interpretation"] is False
    assert bloque["scientific_status"] == "REVIEW_INVALID_BENCHMARK_SITE"
    assert bloque["reason"]

    validado = bloque_de_auditoria(SCORE_ALTO, "VALIDATED")
    assert validado["eligible_for_scientific_interpretation"] is True


# ── Las dos señales de UMS siguen siendo informativas ────────────────────

def test_ums_no_modifica_total_score():
    """El §1 del ADR 75 retiró el empujón aditivo de 0.06. Sigue retirado.

    Se comprueba variando `ums_score` entre sus extremos y midiendo el
    `total_score`: si el UMS entrara en el ranking, cambiaría.
    """
    from core.models import DockingPose, DockingResult, PhysicochemicalProperties
    from scoring.engine import calculate_score_breakdown

    docking = DockingResult(
        best_affinity=-8.0,
        poses=[DockingPose(rank=1, affinity=-8.0, rmsd_lb=0.0, rmsd_ub=0.0)],
    )
    propiedades = PhysicochemicalProperties(
        molecular_weight=300.0, log_p=2.0, tpsa=60.0, hbd=1, hba=4,
        rotatable_bonds=3, heavy_atom_count=21, ring_count=2,
        qed=0.7, sa_score=2.5, lipinski_pass=True, veber_pass=True,
    )
    scores = [
        calculate_score_breakdown(
            docking, propiedades, xgb_prob=0.8, ums_score=ums,
            target_family="metalloenzyme",
        ).total_score
        for ums in (0.0, 0.5, 0.95)
    ]
    assert len(set(scores)) == 1, (
        f"`ums_score` cambió el total_score: {scores}. El ADR 75 §1 lo retiró "
        "del ranking; sólo viaja como señal para el dossier."
    )


def test_ums_warhead_no_entra_en_el_motor_de_scoring():
    """La señal autorizada tampoco puntúa: sólo alimenta el perfil M5-Zn."""
    import inspect

    from scoring import engine

    codigo = "\n".join(
        l for l in inspect.getsource(engine).splitlines()
        if not l.strip().startswith("#")
    )
    assert "ums_warhead" not in codigo, (
        "el motor empezó a leer `ums_warhead`. Es la señal de los tres perfiles "
        "M5-Zn, no un componente de M4."
    )
