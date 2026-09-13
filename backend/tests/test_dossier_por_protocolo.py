"""El dossier separa observación, interpretación y abstención.

`docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §10 y
`docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §5-§7.

═══════════════════════════════════════════════════════════════════════════
LAS TRES COSAS QUE NO PUEDEN CONFUNDIRSE
═══════════════════════════════════════════════════════════════════════════

    observación     lo que un motor midió: el score de Vina, el pLDDT
    interpretación  lo que un modelo dedujo: la regresión de XGBoost, un score
                    compuesto — con su dominio de validez al lado
    abstención      que no hay dato, y por qué no lo hay

Un valor neutral fabricado no es ninguna de las tres. En este producto ya
existieron dos: el 0.5 que se ponía cuando un modelo no respondía, y el −4.0
que devolvía la ruta peptídica. El dossier es el sitio donde esa diferencia
tiene que ser visible, porque es lo que un tercero lee.

Hasta el 2026-09-04 la observación y la interpretación de M4 ni siquiera
coexistían: la regresión de XGBoost se convertía con −1.36·pKi y se escribía
SOBRE `affinity_kcal`. El dossier heredaba la confusión y llamaba «escala de
Vina» a un número que no lo era.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GOLDENS = RAIZ / "backend" / "tests" / "goldens"


def _golden(nombre: str) -> dict:
    return json.loads((GOLDENS / f"{nombre}.json").read_text(encoding="utf-8"))


def _campo(campos: list[dict], prefijo: str) -> dict:
    coincidencias = [c for c in campos if c["etiqueta"].startswith(prefijo)]
    assert coincidencias, f"no hay campo que empiece por «{prefijo}»"
    return coincidencias[0]


# ── M4: observación e interpretación coexisten y se distinguen ───────────

def test_m4_muestra_la_afinidad_de_vina_como_observacion():
    campos = _golden("dossier_m4")["estados"]["ml_dentro_del_dominio"]
    obs = _campo(campos, "Observación · afinidad AutoDock Vina")
    assert obs["estado"] == "REGISTRADO"
    assert "sin transformar" in obs["valor"], (
        "el dossier tiene que decir que la afinidad no está transformada: es "
        "justo lo que dejó de ser cierto durante meses"
    )


def test_m4_muestra_la_regresion_de_ml_como_interpretacion():
    campos = _golden("dossier_m4")["estados"]["ml_dentro_del_dominio"]
    interp = _campo(campos, "Interpretación · regresión XGBoost")
    assert interp["estado"] == "REGISTRADO"
    assert "dentro del dominio" in interp["valor"]
    assert "no en su lugar" in interp["razon"], (
        "tiene que decir que se informa JUNTO a la afinidad de Vina, no en su "
        "lugar"
    )


def test_m4_marca_para_revisar_la_regresion_fuera_de_dominio():
    """Un pKi extrapolado y uno interpolado no se presentan igual."""
    campos = _golden("dossier_m4")["estados"]["ml_fuera_del_dominio"]
    interp = _campo(campos, "Interpretación · regresión XGBoost")
    assert interp["estado"] == "REVISAR"
    assert "FUERA del dominio" in interp["razon"]
    assert "La afinidad del caso es la de Vina" in interp["razon"]


def test_m4_sin_regresion_declara_la_ausencia_y_su_motivo():
    campos = _golden("dossier_m4")["estados"]["sin_regresion_de_ml"]
    interp = _campo(campos, "Interpretación · regresión XGBoost")
    assert interp["estado"] == "NO_EVALUADO"
    assert interp["valor"] is None, "una ausencia no puede imprimir un valor"
    assert "se perdía al sobrescribir" in interp["razon"], (
        "las corridas antiguas tienen este campo vacío por un motivo concreto, "
        "y el dossier tiene que poder decirlo"
    )


@pytest.mark.parametrize(
    "estado", ["ml_dentro_del_dominio", "ml_fuera_del_dominio", "sin_regresion_de_ml"]
)
def test_m4_nunca_presenta_el_ml_como_la_afinidad(estado: str):
    campos = _golden("dossier_m4")["estados"][estado]
    obs = _campo(campos, "Observación · afinidad AutoDock Vina")
    interp = _campo(campos, "Interpretación · regresión XGBoost")
    assert obs["etiqueta"] != interp["etiqueta"]
    if interp["valor"]:
        assert "kcal/mol" in obs["valor"]
        # La equivalencia en kcal se muestra, pero etiquetada como derivada.
        assert "pKi" in interp["valor"]


# ── M5-Zn: los tres estados ──────────────────────────────────────────────

def test_m5_perfil_completo_muestra_formula_y_normalizador():
    campos = _golden("dossier_m5_zn")["estados"]["perfil_con_benchmark_en_revision"]
    assert _campo(campos, "Protocolo M5-Zn")["valor"] == "M5_ZN_MMP9_1GKC_V2"
    formula = _campo(campos, "Fórmula del perfil")["valor"]
    assert "0.75*XGBoost" in formula and "0.25*UMS_warhead" in formula


def test_el_score_en_cuarentena_se_muestra_con_su_advertencia():
    """Hay número Y hay advertencia, en el mismo campo.

    Ocultar el número habría sido la otra tentación y es peor: dejaría de poder
    auditarse justo cuando hace falta auditarlo. Lo que no puede pasar es que se
    lea como evidencia de acoplamiento metaloproteico.
    """
    campos = _golden("dossier_m5_zn")["estados"]["perfil_con_benchmark_en_revision"]
    score = _campo(campos, "Score compuesto M5-Zn")
    assert score["estado"] == "REVISAR"
    assert "0.8508" in score["valor"] and "M5_ZN_MMP9_1GKC_V2" in score["valor"]
    assert "BENCHMARK EN REVISIÓN" in score["valor"]
    assert "no una afinidad" in score["valor"], (
        "el score compuesto es una interpretación de ranking, y el dossier "
        "tiene que decirlo donde se lee"
    )
    for pista in ("−17.34", "4 de sus 22", "calcio", "15.99", "docs/77_CORRIGENDUM"):
        assert pista in score["razon"], (
            f"el motivo no contiene «{pista}»: quien lee tiene que poder llegar "
            "a la evidencia sin salir del documento"
        )


def test_top1_que_no_coordina_es_su_propio_estado():
    """Los estados de cuarentena dicen cosas distintas, y se nota al leer.

    ACE tiene el sitio BIEN —su zinc es el centro exacto de la caja y las poses
    caen dentro— y aun así ninguno de los 47 activos evaluables acerca un
    donante al metal. No es «la caja estaba mal» ni «no se puede comprobar»: se
    comprobó, y la interacción no está.
    """
    campos = _golden("dossier_m5_zn")["estados"]["perfil_con_top1_que_no_coordina"]
    score = _campo(campos, "Score compuesto M5-Zn")
    assert score["estado"] == "REVISAR"
    assert "0.8399" in score["valor"] and "TOP-1 SIN COORDINAR EL METAL" in score["valor"]
    assert "SÍ contenía el zinc" in score["razon"]
    assert "6.13" in score["razon"] and "47 activos" in score["razon"]
    assert "NINGUNA POSE TOP-1" in score["razon"]
    assert "NO se sabe si alguna pose descartada" in score["razon"], (
        "el motivo tiene que declarar el límite: no se puede afirmar que la "
        "búsqueda nunca explorara la coordinación"
    )


def test_ningun_estado_del_golden_dice_validated():
    """El estado liberable de M5-Zn, fijado también en el dossier."""
    import json as _json

    texto = _json.dumps(_golden("dossier_m5_zn"), ensure_ascii=False)
    assert "VALIDATED_PROFILE" not in texto and '"VALIDATED"' not in texto


def test_ca2_se_abstiene_porque_gnn_d_no_tiene_productor():
    """No es un caso hipotético: es lo que 3DC3 devuelve hoy.

    GNN-D sólo existe en los checkpoints de benchmark; no hay componente de
    producción que la calcule. El §4.1 del ADR prohíbe sustituirla por CL-GNN o
    redistribuir su peso, así que el perfil más completo de los tres se abstiene.
    """
    campos = _golden("dossier_m5_zn")["estados"]["perfil_exacto_falta_componente"]
    assert _campo(campos, "Protocolo M5-Zn")["valor"] == "M5_ZN_CA2_3DC3_V2"
    score = _campo(campos, "Score compuesto M5-Zn")
    assert score["valor"] == "NOT_EVALUATED_MISSING_COMPONENT"
    assert "gnn_d" in score["razon"].lower()
    assert "no existe productor" in score["razon"] or "no tiene productor" in score["razon"]


def test_una_corrida_vieja_no_se_lee_como_un_fallo_del_protocolo():
    """Anterior a SCHEMA 18: el protocolo no se ejecutó, punto.

    Deducir «falta un componente» sería una conclusión del dossier sobre un
    cálculo que nadie intentó. Y su única señal de warheads es el UMS histórico,
    que NO es la variante autorizada — el campo lo dice donde se lee.
    """
    campos = _golden("dossier_m5_zn")["estados"]["corrida_anterior_a_schema_18"]
    score = _campo(campos, "Score compuesto M5-Zn")
    assert score["valor"] == "NOT_EVALUATED_PROTOCOL_NOT_EXECUTED"
    assert "SCHEMA 18" in score["razon"]

    ums = _campo(campos, "Señal · warheads de zinc")
    assert "HISTÓRICO" in ums["valor"], (
        "una corrida vieja guardó el UMS con donantes y MolChamb; presentarlo "
        "como la señal SMARTS-only del ADR sería la misma confusión de etiqueta "
        "que ponía el peso de la GNN legacy bajo el nombre de CL-GNN"
    )


def test_gnn_d_no_se_lee_de_la_gnn_legacy():
    """`gnn_score` es RTMScore. GNN-D es otro modelo.

    El bloque leía el primero para declarar presente el segundo, que es cómo un
    perfil podía parecer completo sin que su componente existiera.
    """
    from types import SimpleNamespace

    resultado = SimpleNamespace(
        target_family="metalloenzyme", xgb_score=0.84,
        gnn_score=0.66,          # la GNN legacy SÍ reportó
        ums_warhead=0.9167,
    )
    campos = _bloque_m5(resultado, SimpleNamespace(pdb_id="3DC3"))
    componentes = _campo(campos, "Componentes requeridos y presentes")["valor"]
    assert "presentes: vina · xgb · ums" in componentes, componentes
    assert "gnn_d" not in componentes.split("presentes:")[1]


def test_m5_falta_componente_deja_el_score_en_null():
    """§5: no se renormaliza, no se sustituye, no se fabrica un neutro."""
    campos = _golden("dossier_m5_zn")["estados"]["perfil_exacto_falta_componente"]
    score = _campo(campos, "Score compuesto M5-Zn")
    assert score["estado"] == "NO_EVALUADO"
    assert score["valor"] == "NOT_EVALUATED_MISSING_COMPONENT"
    assert "gnn_d" in score["razon"], "tiene que nombrar el componente que falta"
    assert "No se renormalizan pesos" in score["razon"]


def test_m5_falta_componente_conserva_las_senales_que_si_hay():
    """Que falte una no borra las demás."""
    campos = _golden("dossier_m5_zn")["estados"]["perfil_exacto_falta_componente"]
    ums = _campo(campos, "Señal · warheads de zinc")
    assert ums["estado"] == "REGISTRADO" and ums["valor"]
    afinidad = _campo(campos, "Observación · afinidad AutoDock Vina")
    assert afinidad["estado"] == "REGISTRADO"


def test_m5_fuera_de_diana_se_abstiene_con_motivo():
    """§7.2: se ejecuta la auditoría, no se heredan pesos."""
    campos = _golden("dossier_m5_zn")["estados"]["zinc_fuera_de_las_tres_dianas"]
    protocolo = _campo(campos, "Protocolo M5-Zn")
    assert protocolo["estado"] == "ABSTENCION"
    assert protocolo["valor"] == "REVIEW_OUT_OF_VALIDATED_TARGET"
    assert "NO hereda los pesos" in protocolo["razon"]

    score = _campo(campos, "Score compuesto M5-Zn")
    assert score["estado"] == "NO_EVALUADO" and score["valor"] is None


def test_m5_fuera_de_diana_conserva_las_senales_individuales():
    """Lo que pide el plan: señales sí, score compuesto no."""
    campos = _golden("dossier_m5_zn")["estados"]["zinc_fuera_de_las_tres_dianas"]
    assert _campo(campos, "Señal · warheads de zinc")["estado"] == "REGISTRADO"
    assert _campo(campos, "Observación · afinidad AutoDock Vina")["estado"] == "REGISTRADO"


def test_m5_fuera_de_diana_no_declara_formula():
    """Sin perfil no hay fórmula que enseñar; enseñar una sería atribuirla."""
    campos = _golden("dossier_m5_zn")["estados"]["zinc_fuera_de_las_tres_dianas"]
    assert not [c for c in campos if c["etiqueta"].startswith("Fórmula")]


def test_el_alias_de_grafia_no_cambia_la_decision():
    """§6: `metaloenzyme` es alias de lectura, no otra familia."""
    alias = _golden("dossier_m5_zn")["alias_de_grafia"]
    assert alias["la_decision_coincide"] is True


def test_la_grafia_historica_se_conserva_como_procedencia():
    """§6.5: el expediente antiguo sigue diciendo lo que guardó."""
    alias = _golden("dossier_m5_zn")["alias_de_grafia"]
    assert "metaloenzyme" in alias["procedencia_legacy"], (
        "un expediente que guardó la grafía vieja tiene que seguir mostrándola"
    )
    assert "metalloenzyme" in alias["procedencia_legacy"], (
        "y a la vez decir con qué familia canónica se le trató"
    )
    assert alias["procedencia_canonica"] == "metalloenzyme"


# ── Péptidos: la abstención de frontera ──────────────────────────────────

def test_el_dossier_peptidico_usa_la_formulacion_del_adr():
    campos = _golden("dossier_peptido")["estados"]["estructura_generada_sin_acoplamiento"]
    estado = _campo(campos, "Estado del acoplamiento")
    assert estado["valor"] == "Estructura peptídica generada; docking no evaluado"
    assert estado["estado"] == "NO_EVALUADO"
    assert "no se sustituye por un valor derivado de la confianza" in estado["razon"].lower()


def test_el_dossier_declara_el_motor_sustituido():
    campos = _golden("dossier_peptido")["estados"]["motor_sustituido_por_vina"]
    motor = _campo(campos, "Motor solicitado frente a ejecutado")
    assert motor["estado"] == "REVISAR"
    assert "esmfold -> vina" in motor["valor"]
    assert "no es comparable" in motor["razon"]


# ── Invariantes que valen para los tres ──────────────────────────────────

@pytest.mark.parametrize("nombre", ["dossier_m4", "dossier_m5_zn", "dossier_peptido"])
def test_ninguna_ausencia_imprime_un_valor(nombre: str):
    """`Campo.as_dict` ya lo garantiza; esto lo fija sobre datos reales."""
    for estado, campos in _golden(nombre)["estados"].items():
        for c in campos:
            if c["estado"] in ("NO_EVALUADO", "NO_DISPONIBLE", "NO_DEFINIDO", "NO_APLICA"):
                # Un valor bajo un estado de ausencia sólo es legítimo cuando
                # ES la clasificación, y eso tiene que venir marcado: si no,
                # una fuga y una clasificación se ven igual desde fuera.
                if c["valor"] is not None:
                    assert c.get("valor_es_clasificacion") is True, (
                        f"{nombre}/{estado}: «{c['etiqueta']}» está en "
                        f"{c['estado']} e imprime «{c['valor']}» sin declararse "
                        "como clasificación. O es una fuga, o falta la marca."
                    )


@pytest.mark.parametrize("nombre", ["dossier_m4", "dossier_m5_zn", "dossier_peptido"])
def test_toda_ausencia_trae_su_motivo(nombre: str):
    for estado, campos in _golden(nombre)["estados"].items():
        for c in campos:
            if c["estado"] != "REGISTRADO":
                assert c["razon"], (
                    f"{nombre}/{estado}: «{c['etiqueta']}» no está registrado y "
                    "no dice por qué. Una ausencia sin motivo no se puede revisar."
                )


@pytest.mark.parametrize("nombre", ["dossier_m4", "dossier_m5_zn", "dossier_peptido"])
def test_no_aparece_ningun_valor_neutral_fabricado(nombre: str):
    """Los dos que existieron en este producto: el 0.5 y el −4.0."""
    texto = json.dumps(_golden(nombre), ensure_ascii=False)
    for prohibido in ("-4.0 kcal", "-4.00 kcal"):
        assert prohibido not in texto, (
            f"{nombre} contiene «{prohibido}»: la afinidad fabricada de la ruta "
            "peptídica volvió al dossier"
        )


# ── El PDB sale del objetivo, no del resultado ───────────────────────────
#
# Lo encontró `scripts/verify_embedded_dossier.py` pidiendo el dossier por HTTP
# al backend empaquetado: una corrida contra 3DC3 —el perfil más completo— se
# documentaba como «El PDB "sin declarar" no es ninguno de los tres perfiles
# validados». El bloque leía `target_pdb_id` del resultado de la evaluación, y
# esa columna no existe.
#
# Estas pruebas no habrían servido escritas como las de arriba: las de arriba
# leen goldens, y el golden le pasaba al bloque un diccionario CON el campo.


def test_el_pdb_no_es_una_columna_del_resultado():
    """El hecho que obliga a pasar el objetivo.

    Si algún día alguien añade la columna, esta prueba falla y hay que decidir
    cuál manda: el PDB congelado con la corrida, o el del objetivo actual de la
    molécula. Hoy sólo existe el segundo.
    """
    from core.models import EvaluationResultORM

    columnas = set(EvaluationResultORM.__table__.columns.keys())
    assert "target_pdb_id" not in columnas
    assert "target_family" in columnas, (
        "la familia sí es columna: es la asimetría que hacía verosímil el error"
    )


def _bloque_m5(eval_result, target):
    from services.dossier.bloques_protocolo import campos_de_m5_zn
    from services.dossier.model import Campo, _campo_dato, _v

    return [c.as_dict() for c in campos_de_m5_zn(
        Campo, _campo_dato, _v, eval_result, {"top_pose_affinity": -7.2}, target
    )]


def test_el_perfil_se_resuelve_con_un_resultado_con_forma_de_orm():
    """La regresión: un `eval_result` SIN `target_pdb_id`, como el de verdad."""
    from types import SimpleNamespace

    resultado = SimpleNamespace(
        target_family="metalloenzyme", xgb_score=0.84, gnn_score=0.66,
        ums_score=0.9167,
    )
    campos = _bloque_m5(resultado, SimpleNamespace(pdb_id="3DC3"))
    assert _campo(campos, "Protocolo M5-Zn")["valor"] == "M5_ZN_CA2_3DC3_V2"
    assert _campo(campos, "Fórmula del perfil")["estado"] == "REGISTRADO"


def test_sin_objetivo_se_abstiene_en_vez_de_romperse():
    """Una molécula sin objetivo legible no revienta el dossier: se abstiene."""
    from types import SimpleNamespace

    resultado = SimpleNamespace(target_family="metalloenzyme", ums_score=0.9167)
    campos = _bloque_m5(resultado, None)
    protocolo = _campo(campos, "Protocolo M5-Zn")
    assert protocolo["estado"] == "ABSTENCION"
    assert protocolo["valor"] == "REVIEW_OUT_OF_VALIDATED_TARGET"


def test_el_bloque_exige_el_objetivo():
    """Sin valor por defecto: olvidarlo tiene que ser un TypeError, no un None.

    Un `target=None` implícito reproduciría el fallo en silencio en el próximo
    sitio que llame a esta función, que es justo como llegó hasta producción.
    """
    import inspect

    from services.dossier.bloques_protocolo import campos_de_m5_zn

    parametro = inspect.signature(campos_de_m5_zn).parameters["target"]
    assert parametro.default is inspect.Parameter.empty

def test_el_dossier_lee_la_transferencia_peptidica_persistida():
    from types import SimpleNamespace
    from services.dossier.model import _campos_de_protocolo_y_abstencion

    resultado = SimpleNamespace(
        docking_protocol={"engine_executed": "esmfold", "engine_requested": "esmfold"},
        ligand_state={
            "peptide_transfer": {
                "status": "completed",
                "coordinates_transferred": 15,
                "coordinates_completed": 1,
                "completion_method": "rdkit_constrained_v1",
                "mapping_version": "peptide_atom_map_v1",
            }
        },
    )
    campos = [c.as_dict() for c in _campos_de_protocolo_y_abstencion(
        resultado, {"top_pose_affinity": -4.2}
    )]
    transferencia = _campo(campos, "Transferencia química ESMFold")
    assert transferencia["valor"] == "COMPLETADA"
    recuento = _campo(campos, "Átomos transferidos / completados")
    assert recuento["valor"] == "15 / 1"
    assert _campo(campos, "Método de completado geométrico")["valor"] == "rdkit_constrained_v1"


def test_el_dossier_conserva_la_abstencion_de_transferencia():
    from types import SimpleNamespace
    from services.dossier.model import _campos_de_protocolo_y_abstencion

    resultado = SimpleNamespace(
        docking_protocol={"engine_executed": "esmfold"},
        ligand_state={
            "peptide_transfer": {
                "status": "abstained",
                "failure_code": "D_PEPTIDE_UNSUPPORTED",
                "failure_message": "ESMFold V1 solo admite aminoácidos L.",
            }
        },
    )
    campos = [c.as_dict() for c in _campos_de_protocolo_y_abstencion(
        resultado, {"top_pose_affinity": None}
    )]
    transferencia = _campo(campos, "Transferencia química ESMFold")
    assert transferencia["estado"] == "NO_EVALUADO"
    assert transferencia["valor_es_clasificacion"] is True
    assert "D_PEPTIDE_UNSUPPORTED" in transferencia["valor"]
    assert "aminoácidos L" in transferencia["razon"]