"""Grupo A del doc 71: ocho sintomas, un contrato de datos roto.

El informe de la primera evaluacion en VM listo ocho defectos de "serializacion
y evidencia ML". El doc 71 sospechaba que eran uno solo: «ocho sintomas
apuntando al mismo sitio suelen ser un contrato de datos roto, no ocho bugs».

Lo eran, y el sitio era este: **dos lectores sobre dos fuentes distintas**. El
frontend leia los scores DIRECTAMENTE del ORM; el dossier construia su seccion
de evidencia desde `build_evidence_summary`, que no los tenia. Cada superficie
decia la verdad que veia, y las dos verdades no coincidian.

Estas pruebas fijan lo que cada defecto exigia:

    A1  el resumen serializa las salidas ML, con `None` explicito
    A2  una etapa con peso pero sin salida se DECLARA, no se presenta como si
        hubiera aportado
    A4  los dos XGBoost del producto se distinguen por nombre
    A5  no se atribuye dominancia a un modelo que no reporto nada
    A6  la dimension del modelo no nombra el motor de docking: son identidades
        distintas y confundirlas producia «motor no informado» en un documento
        que declara Vina 1.2.7 dos secciones mas abajo
"""

from __future__ import annotations

import pytest

from services.blockchain.evidence_summary import build_evidence_summary


class _Corrida:
    """Una corrida con lo minimo para que el resumen la considere completa."""

    docking_poses = [{"affinity": -9.4}, {"affinity": -8.1}]
    affinity_kcal = -9.4
    vina_version = "1.2.7"
    vina_random_seed = 42
    parsing_source = "vina_stdout"
    docking_protocol = {"engine": "vina"}
    engine_used = None          # el router hardware, que este camino no usa
    model_used = "universal"
    in_applicability_domain = False
    fallback_reason = None
    xgb_score = 0.05
    classifier_prob = 0.05
    shap_values = {"LogP": -0.2, "MW": 0.5}
    clgnn_score = None
    gnn_attention = None
    gnn_score = None
    quantum_score = None
    mmgbsa_score = None
    stacking_vina_weight = 0.10
    stacking_xgb_weight = 0.30
    # El peso que la fixture quiere modelar es el de CL-GNN, y hasta SCHEMA 17
    # se escribia en `stacking_gnn_weight` —el de la GNN LEGACY de RTMScore—
    # porque no habia columna propia. El resumen lo leia de ahi y lo etiquetaba
    # «CL-GNN», asi que la prueba pasaba con la atribucion equivocada.
    stacking_gnn_weight = 0.0
    stacking_clgnn_weight = 0.60
    target_family = "protease"


def _dimension(resumen: dict, ident: str) -> dict:
    return next(d for d in resumen["dimensions"] if d["id"] == ident)


@pytest.fixture()
def resumen() -> dict:
    return build_evidence_summary(_Corrida(), None, None)


# ── A1 ───────────────────────────────────────────────────────────────────────

def test_el_resumen_serializa_lo_que_el_modelo_produjo(resumen):
    """El frontend mostraba «salida 0.05 + SHAP» y el dossier no lo registraba."""
    ml = resumen["ml_signals"]
    assert ml["xgboost"]["salida"] == 0.05
    assert ml["xgboost"]["shap"] == {"LogP": -0.2, "MW": 0.5}
    assert ml["familia_del_objetivo"] == "protease"


def test_la_ausencia_se_declara_como_nula_y_no_como_cero(resumen):
    """Un cero es una prediccion; la ausencia no lo es.

    Sustituir una etapa no ejecutada por 0.0 -o por el 0.5 neutro que devuelve
    un modelo silenciado- convierte «no lo sabemos» en «lo medimos y da esto».
    """
    ml = resumen["ml_signals"]
    assert ml["cl_gnn"]["salida"] is None
    assert ml["cuantico"]["salida"] is None
    assert ml["mmgbsa"]["salida_kcal_mol"] is None
    assert "no se ejecuto" in ml["nota"] or "no se ejecutó" in ml["nota"]


# ── A4 ───────────────────────────────────────────────────────────────────────

def test_los_dos_xgboost_del_producto_se_distinguen(resumen):
    """El selector de poses es un XGBRanker; el de rescoring es otro modelo.

    Compartir el nombre «XGBoost» hacia imposible saber cual de los dos produjo
    que numero, y ambos aparecen en el mismo documento.
    """
    assert resumen["ml_signals"]["xgboost"]["cual"] == "rescoring"


# ── A2 y A5 ──────────────────────────────────────────────────────────────────

def test_un_peso_sin_salida_se_declara(resumen):
    """CL-GNN lleva 0,60 del stacking en la fixture y no reporto nada.

    El peso viene del protocolo de familia, se reparte ANTES de correr y no es
    un error: lo que no puede pasar es que se lea como contribucion.
    """
    aviso = [u for u in resumen["uncertainties"] if "CL-GNN" in u]
    assert aviso, f"no se declara el peso sin salida: {resumen['uncertainties']}"
    assert "no debe" in aviso[0] and "domin" in aviso[0]


def test_el_aviso_nombra_al_modelo_que_de_verdad_lleva_el_peso():
    """Un peso en la GNN legacy no se declara como si fuera de CL-GNN.

    Es el caso REAL del artefacto vigente: en GPCR reparte `gnn: 0.40` y no
    declara `clgnn`, que resuelve a 0.00. El resumen leia `stacking_gnn_weight`
    bajo la etiqueta «CL-GNN», asi que atribuia la influencia al modelo
    equivocado dentro del documento que un tercero lee como evidencia.
    """
    class SoloLegacy(_Corrida):
        stacking_clgnn_weight = 0.0
        stacking_gnn_weight = 0.40
        clgnn_score = 0.74   # CL-GNN SI reporto, y su peso es cero
        gnn_score = None     # la legacy es la que lleva peso y no reporto

    resumen = build_evidence_summary(SoloLegacy(), None, None)
    avisos = [u for u in resumen["uncertainties"] if "no serializaron salida" in u]
    assert avisos, "un peso sin salida en la GNN legacy tambien hay que declararlo"
    assert "GNN legacy" in avisos[0]
    assert "CL-GNN" not in avisos[0], (
        "se esta atribuyendo a CL-GNN el peso de la GNN legacy: es el defecto "
        "que SCHEMA 17 separa"
    )


def test_no_se_avisa_cuando_la_etapa_si_reporto():
    """XGBoost tiene peso 0,30 y salida 0,05: eso no es una contradiccion."""
    resumen = build_evidence_summary(_Corrida(), None, None)
    assert not [u for u in resumen["uncertainties"]
                if "XGBoost" in u and "no serializaron" in u]


def test_una_corrida_completa_no_genera_el_aviso():
    class Completa(_Corrida):
        clgnn_score = 0.74

    resumen = build_evidence_summary(Completa(), None, None)
    assert not [u for u in resumen["uncertainties"] if "no serializaron salida" in u]


# ── A6 ───────────────────────────────────────────────────────────────────────

def test_la_dimension_del_modelo_no_nombra_el_motor_de_docking(resumen):
    """`engine_used` es el router gpu/cpu, no Vina. Leerlo como motor producia
    «motor no informado» en un documento que declara Vina 1.2.7."""
    detalle = _dimension(resumen, "model")["detail"]
    assert "motor no informado" not in detalle
    assert "modelo universal" in detalle


def test_el_motor_se_declara_donde_corresponde(resumen):
    """En la senal de docking, que es de donde sale, y con su version."""
    detalle = _dimension(resumen, "docking")["detail"]
    assert "vina" in detalle.lower()
    assert "1.2.7" in detalle


def test_sin_motor_declarado_no_se_inventa_uno():
    class SinProtocolo(_Corrida):
        docking_protocol = {}
        vina_version = None

    detalle = _dimension(build_evidence_summary(SinProtocolo(), None, None),
                         "docking")["detail"]
    assert "motor no informado" not in detalle
    assert "poses serializadas" in detalle


# ── A8: los controles sin evaluar del preflight ──────────────────────────────

def test_el_dossier_declara_los_controles_que_el_preflight_no_evaluo():
    """DOC 71, DEFECTO A8.

    El caso guarda TRES listas del preflight -bloqueantes, advertencias y
    controles no evaluados- y el dossier solo pintaba las dos primeras. La
    interfaz mostraba «dos advertencias y tres controles sin evaluar» y el
    documento hablaba unicamente de las advertencias.

    Un control que NO SE EVALUO no es un control que paso. Es la misma
    distincion que este producto sostiene en la validez fisica de poses:
    `not_evaluated` nunca se mezcla con `passed`.
    """
    from services.dossier.schemas import PreflightDeclarado

    preflight = PreflightDeclarado(
        fingerprint="sha256:" + "0" * 16,
        warnings=["GRID_SIN_CALIBRAR", "RECEPTOR_SIN_RHO"],
        not_evaluated=["METALES_EN_SITIO", "AGUAS_ESTRUCTURALES", "ALTLOC_AMBIGUO"],
    )
    # El esquema los conserva por separado: el dossier no puede alegar que no
    # los tenia.
    assert len(preflight.not_evaluated) == 3
    assert not set(preflight.warnings) & set(preflight.not_evaluated)

    import inspect

    from services.dossier import model as dossier_model

    fuente = inspect.getsource(dossier_model)
    assert "preflight.not_evaluated" in fuente, (
        "el dossier no lee los controles sin evaluar del preflight"
    )
    assert "Controles sin evaluar" in fuente


# ── C2: la pose recomendada que no existe ────────────────────────────────────

class _ConAbstencion(_Corrida):
    """El selector se abstuvo, pero midio la candidata que descarto."""

    pose_selection = {
        "status": "abstained",
        "selected_pose_rank": None,
        "vina_top1_rank": 1,
        "would_have_suggested_rank": 2,
        "suggested_pose_physical_status": "passed",
        "abstained": True,
    }


def test_no_se_atribuye_estado_fisico_a_una_recomendacion_que_no_existe():
    """DOC 71, DEFECTO C2.

    Con veinte lineas de distancia el dossier decia «el selector no recomendo
    ninguna pose» y «estado fisico de la pose recomendada: passed». Las dos
    frases eran ciertas por separado: cuando hay abstencion, el estado que trae
    el contrato es el de la pose que HABRIA recomendado.
    """
    sel = build_evidence_summary(_ConAbstencion(), None, None)["pose_selection"]
    assert sel["suggested_pose_rank"] is None
    assert sel["suggested_pose_physical_status"] is None, (
        "se atribuye un estado fisico a una recomendacion inexistente"
    )


def test_el_dato_no_se_pierde_sino_que_se_le_pone_nombre():
    """Callarlo perderia informacion util -que la descartada pasaba-."""
    sel = build_evidence_summary(_ConAbstencion(), None, None)["pose_selection"]
    assert sel["would_have_suggested_rank"] == 2
    assert sel["would_have_suggested_physical_status"] == "passed"


def test_con_recomendacion_el_estado_sigue_donde_siempre():
    class ConSeleccion(_Corrida):
        pose_selection = {
            "status": "selected",
            "selected_pose_rank": 3,
            "vina_top1_rank": 1,
            "suggested_pose_physical_status": "passed",
        }

    sel = build_evidence_summary(ConSeleccion(), None, None)["pose_selection"]
    assert sel["suggested_pose_rank"] == 3
    assert sel["suggested_pose_physical_status"] == "passed"
    assert sel["would_have_suggested_physical_status"] is None
