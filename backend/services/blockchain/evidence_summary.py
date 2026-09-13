"""Resumen determinista y auditable para la UI y el dossier PDF.

No estima confianza ni validez experimental. Resume únicamente datos que el
pipeline ya serializó y marca de forma explícita lo que no fue evaluado.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from services.avisos import normalizar_avisos, textos
from services.chemistry.mmgbsa_contrato import MMGBSA_CONDICION


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def derive_target_readiness(target: Any) -> str:
    if target is None:
        return "sin_datos"

    explicit = getattr(target, "calibration_status", None)
    if explicit in {"listo", "revisar", "sin_datos"}:
        return explicit

    prepared = bool(getattr(target, "is_prepared", False))
    grid_fields = (
        "grid_center_x", "grid_center_y", "grid_center_z",
        "grid_size_x", "grid_size_y", "grid_size_z",
    )
    grid_ready = all(getattr(target, field, None) is not None for field in grid_fields)
    hotspots = getattr(target, "hotspots", None) or []
    hotspot_count = len(hotspots)
    pdb_id = str(getattr(target, "pdb_id", "")).upper()
    is_manual = bool(getattr(target, "is_private", False)) or pdb_id.startswith("USR_")

    if prepared and grid_ready and (hotspot_count >= 5 or is_manual):
        return "listo"
    if prepared and grid_ready and hotspot_count > 0:
        return "revisar"
    return "sin_datos"


def _sha256_de(valor: Any) -> str | None:
    """SHA-256 de un valor serializable. `None` si no hay nada que sellar."""
    if valor in (None, ""):
        return None
    texto = valor if isinstance(valor, str) else json.dumps(
        valor, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode("utf-8", "replace")).hexdigest()


def build_provenance(
    eval_result: Any, target: Any = None, molecule: Any = None
) -> dict[str, Any]:
    """Hashes de las entradas y de la configuracion que produjeron esta corrida.

    Sin esto el dossier no es verificable: un revisor externo lee conclusiones y no puede
    comprobar que se calcularon sobre lo que dice el documento. El programa experimental
    sella cada artefacto con SHA-256 desde `FND-01`; el producto, que es la superficie de
    entrega, no lo hacia. Anclar la integridad en un registro en cadena que ademas puede
    estar pendiente no sustituye al hash del insumo: son cosas distintas y la segunda es
    la que permite reproducir.

    Devuelve `None` en cada campo que la corrida no serializo, en vez de omitirlo: un
    hueco declarado es informacion, un campo ausente es una duda.
    """
    smiles = getattr(eval_result, "smiles", None) or _value(molecule, "smiles")
    protocol = getattr(eval_result, "docking_protocol", None) or {}
    receptor_ref = (getattr(eval_result, "receptor_path", None)
                    or _value(target, "pdb_id")
                    or _value(target, "name"))
    config = {
        "vina_version": getattr(eval_result, "vina_version", None),
        "random_seed": getattr(eval_result, "vina_random_seed", None),
        "exhaustiveness": (
            getattr(eval_result, "vina_exhaustiveness", None)
            or _value(protocol, "exhaustiveness")
        ),
        "num_modes": (
            getattr(eval_result, "vina_num_modes", None)
            or _value(protocol, "num_poses")
        ),
        "grid_center": [_value(target, "grid_center_x"), _value(target, "grid_center_y"),
                        _value(target, "grid_center_z")],
        "grid_size": [_value(target, "grid_size_x"), _value(target, "grid_size_y"),
                      _value(target, "grid_size_z")],
    }
    poses = getattr(eval_result, "docking_poses", None) or []
    bloques = [_value(p, "pdbqt_block") for p in poses]
    bloques = [b for b in bloques if b]

    campos = {
        "ligando_smiles_sha256": _sha256_de(smiles),
        "receptor_referencia": receptor_ref,
        "configuracion_sha256": _sha256_de(config),
        "poses_sha256": _sha256_de("\n".join(bloques)) if bloques else None,
        "motor": getattr(eval_result, "engine_used", None) or _value(protocol, "engine"),
        "modelo": getattr(eval_result, "model_used", None),
        "vocabulario_especies": None,   # lo rellena el diff de preparacion cuando exista
    }
    faltan = sorted(k for k, v in campos.items() if v is None)
    return {
        **campos,
        "configuracion": config,
        "completo": not faltan,
        "campos_ausentes": faltan,
        "nota": (
            "Estos hashes permiten a un tercero comprobar que las conclusiones de este "
            "dossier se calcularon sobre las entradas que declara. Un registro en cadena "
            "certifica CUANDO se emitio el documento; no certifica SOBRE QUE se calculo. "
            "Los dos son necesarios y no se sustituyen."
        ),
    }


def build_evidence_summary(
    eval_result: Any, target: Any = None, molecule: Any = None
) -> dict[str, Any]:
    raw_poses = getattr(eval_result, "docking_poses", None) or []
    affinities = []
    for pose in raw_poses:
        affinity = _value(pose, "affinity")
        if isinstance(affinity, (int, float)):
            affinities.append(float(affinity))
    affinities.sort()

    top_pose_affinity = affinities[0] if affinities else None
    pose_gap = round(affinities[1] - affinities[0], 3) if len(affinities) > 1 else None
    near_tie_count = (
        sum(1 for affinity in affinities if affinity - top_pose_affinity <= 1.0)
        if top_pose_affinity is not None else 0
    )

    protocol_stub = getattr(eval_result, "docking_protocol", None) or {}
    vina_version = getattr(eval_result, "vina_version", None)
    random_seed = getattr(eval_result, "vina_random_seed", None)
    parsing_source = getattr(eval_result, "parsing_source", None)
    reproducibility_count = sum(value not in (None, "") for value in (vina_version, random_seed, parsing_source))
    # `str(item)` sobre un aviso nuevo imprimiría el diccionario entero. Los
    # avisos completos viajan aparte en `avisos_declarados`; aquí van sólo los
    # mensajes, que es lo que este resumen lleva como prosa.
    warnings = textos(getattr(eval_result, "scientific_warnings", None))
    avisos_declarados = normalizar_avisos(getattr(eval_result, "scientific_warnings", None))
    target_readiness = derive_target_readiness(target)
    descriptor_fields = (
        "molecular_weight", "log_p", "tpsa", "hbd", "hba",
        "rotatable_bonds", "qed", "sa_score",
    )
    descriptor_count = sum(
        isinstance(getattr(eval_result, field, None), (int, float))
        for field in descriptor_fields
    )
    selectivity_ran = bool(getattr(eval_result, "selectivity_ran", False))
    selectivity_count = len(getattr(eval_result, "anti_target_results", None) or []) if selectivity_ran else 0

    # ── Validez física: el contrato REAL, no un campo que nunca existió ──
    #
    # CORRECCIÓN. Esto leía `eval_result.pose_validation`, un atributo que el
    # backend no ha emitido jamás, así que caía SIEMPRE en la rama de
    # abstención e imprimía en el PDF «esta versión no ejecuta un validador
    # geométrico de poses en producción». Desde P0-A el validador corre por
    # pose y persiste `structural_evidence`; desde P0-B el selector persiste
    # `pose_selection`. Un dossier que declara no evaluado lo que sí se midió
    # no es prudente: es incorrecto, y encima firma esa incorrección con un
    # SHA-256 que la hace parecer verificada.
    #
    # Se LEE lo persistido. Aquí no se revalida ni se recalcula nada: dos
    # veredictos sobre la misma pose serían peor que uno.
    structural = getattr(eval_result, "structural_evidence", None)
    stage_status = _value(structural, "stage_status")
    poses_produced = _value(structural, "poses_produced") or 0
    poses_evaluated = _value(structural, "poses_evaluated") or 0
    validation_engine = _value(structural, "validation_engine")
    if isinstance(validation_engine, (list, tuple)):
        validation_engine = " · ".join(str(m) for m in validation_engine) or None

    if stage_status in {"passed", "review", "failed"}:
        etiquetas = {
            "passed": "CONTROLES SUPERADOS",
            "review": "REVISIÓN NECESARIA",
            "failed": "CONTROLES FALLIDOS",
        }
        detalles = {
            "passed": (
                f"{poses_evaluated} de {poses_produced} poses recibieron veredicto y ninguna "
                f"falla los controles de química o geometría."
            ),
            "failed": (
                "Al menos la pose principal falla los controles de química o geometría."
            ),
            "review": (
                "La batería no corrió entera sobre todas las poses. «Revisión necesaria» "
                "describe una comprobación incompleta, NO una pose aprobada."
            ),
        }
        physical_validity = {
            "status": stage_status,
            "label": etiquetas[stage_status],
            "detail": (
                f"{detalles[stage_status]} Motor: {validation_engine or 'no declarado'}. "
                f"Cobertura {poses_evaluated}/{poses_produced} poses."
            ),
            "engine": validation_engine,
            "poses_produced": poses_produced,
            "poses_evaluated": poses_evaluated,
            "reason_code": _value(structural, "reason_code"),
        }
    else:
        physical_validity = {
            "status": "not_evaluated",
            "label": "NO EVALUADA",
            "detail": (
                (
                    "Los controles físicos no llegaron a emitir veredicto "
                    f"({_value(structural, 'reason_code') or 'sin código de razón'}). "
                    "Describe lo que le pasó al validador, no a la molécula."
                )
                if structural
                else (
                    "Esta corrida es anterior a la etapa de validación física: no se ejecutó. "
                    "Que no se midiera no dice nada sobre las poses."
                )
            ),
            "engine": validation_engine,
            "poses_produced": poses_produced,
            "poses_evaluated": poses_evaluated,
            "reason_code": _value(structural, "reason_code"),
        }

    # ── Selección de pose: recomendación, no sustitución ────────────────
    #
    # Vina top-1 se conserva SIEMPRE. El selector emite una recomendación con su
    # margen, su modelo y su hash; si se abstiene, falta o falla, la referencia
    # sigue siendo Vina top-1 y se etiqueta como FALLBACK — no como un acierto
    # del selector. Un dossier que presentara una ausencia de recomendación como
    # si fuera una elección estaría fabricando la decisión que nadie tomó.
    seleccion_cruda = getattr(eval_result, "pose_selection", None)
    sel_status = _value(seleccion_cruda, "status")
    if sel_status not in {"selected", "abstained", "unavailable", "error"}:
        sel_status = "unavailable"
    sel_modelo = _value(seleccion_cruda, "model") or {}
    sel_top1 = _value(seleccion_cruda, "vina_top1_rank")
    sel_sugerida = _value(seleccion_cruda, "selected_pose_rank")
    sel_estado_fisico = _value(seleccion_cruda, "suggested_pose_physical_status")
    etiquetas_sel = {
        "selected": "RECOMENDACIÓN EMITIDA",
        "abstained": "SELECTOR ABSTENIDO",
        "unavailable": "SELECTOR NO DISPONIBLE",
        "error": "SELECTOR FALLIDO",
    }
    pose_selection = {
        "status": sel_status,
        "label": etiquetas_sel[sel_status],
        "vina_top1_rank": sel_top1,
        "suggested_pose_rank": sel_sugerida,
        "would_have_suggested_rank": _value(seleccion_cruda, "would_have_suggested_rank"),
        "confidence": _value(seleccion_cruda, "confidence"),
        "abstention_threshold": _value(sel_modelo, "abstention_threshold"),
        "abstained": bool(_value(seleccion_cruda, "abstained")),
        "abstention_reason": _value(seleccion_cruda, "abstention_reason"),
        # Si el contrato no lo declara, se asume fallback salvo que haya
        # recomendación: el sesgo por defecto va del lado de no afirmar.
        "is_fallback": (
            _value(seleccion_cruda, "strategy_is_fallback")
            if _value(seleccion_cruda, "strategy_is_fallback") is not None
            else sel_status != "selected"
        ),
        "diverges_from_vina_top1": (
            sel_sugerida is not None and sel_top1 is not None and sel_sugerida != sel_top1
        ),
        "model_name": _value(sel_modelo, "name"),
        "model_version": _value(sel_modelo, "version"),
        "model_sha256": _value(sel_modelo, "model_sha256"),
        "meta_sha256": _value(sel_modelo, "meta_sha256"),
        # DOC 71, DEFECTO C2. Este campo se emitia SIEMPRE, aunque el selector
        # se hubiera abstenido. El dossier acababa diciendo, con veinte lineas
        # de distancia, «el selector no recomendo ninguna pose» y «estado fisico
        # de la pose recomendada: passed». Las dos frases eran ciertas por
        # separado: cuando hay abstencion, el estado que trae el contrato es el
        # de la pose que HABRIA recomendado, no el de una recomendacion que no
        # existe.
        #
        # No se borra el dato -es util saber que la candidata descartada pasaba
        # los controles-: se le pone el nombre de quien es. Un campo que
        # atribuye una propiedad a algo inexistente no es un dato de mas, es una
        # contradiccion dentro del mismo documento.
        "suggested_pose_physical_status": (
            sel_estado_fisico if sel_sugerida is not None else None
        ),
        "would_have_suggested_physical_status": (
            sel_estado_fisico if sel_sugerida is None else None
        ),
        "physical_review": bool(_value(seleccion_cruda, "physical_review")),
        "physically_valid_alternatives": [
            _value(item, "rank")
            for item in (_value(seleccion_cruda, "physically_valid_alternatives") or [])
            if _value(item, "rank") is not None
        ],
        "pose_scores": [
            {"rank": _value(item, "rank"), "score": _value(item, "score")}
            for item in (_value(seleccion_cruda, "pose_scores") or [])
        ],
        "detail": _value(seleccion_cruda, "detail"),
        "warnings": [str(w) for w in (_value(seleccion_cruda, "warnings") or []) if w],
    }

    # ── Evidencia por pose: afinidad, veredicto físico y papel ──────────
    # Una fila por pose que la corrida conservó. Los papeles CONVIVEN: la top-1
    # de Vina puede ser además una alternativa físicamente válida.
    alternativas = set(pose_selection["physically_valid_alternatives"])
    scores_por_rango = {
        item["rank"]: item["score"] for item in pose_selection["pose_scores"]
        if item["rank"] is not None
    }
    pose_evidence: list[dict[str, Any]] = []
    for entrada in (_value(structural, "poses") or []):
        rango = _value(entrada, "rank")
        estado_pose = _value(entrada, "status") or "not_evaluated"
        pose_evidence.append({
            "rank": rango,
            "observed_vina_affinity_kcal_mol": _value(entrada, "observed_vina_affinity_kcal_mol"),
            "physical_status": estado_pose,
            # SÓLO `passed` explícito. `review` y `not_evaluated` no son poses
            # válidas: una describe una batería incompleta y la otra un
            # validador que no corrió.
            "physically_valid": estado_pose == "passed",
            "engine": _value(entrada, "engine"),
            "failing_checks": [str(c) for c in (_value(entrada, "checks_que_fallan") or [])],
            "checks_total": len(_value(entrada, "checks") or []),
            "detail": _value(entrada, "detail"),
            "reason_code": _value(entrada, "reason_code"),
            "selector_score": scores_por_rango.get(rango),
            "is_vina_top1": rango is not None and rango == sel_top1,
            "is_suggested": rango is not None and rango == sel_sugerida,
            "is_alternative": rango in alternativas,
        })

    incomplete = getattr(eval_result, "affinity_kcal", None) is None or not affinities
    needs_review = any((
        warnings,
        target_readiness != "listo",
        getattr(eval_result, "in_applicability_domain", None) is False,
        bool(getattr(eval_result, "fallback_reason", None)),
        reproducibility_count < 3,
    ))
    status = "incomplete" if incomplete else "review" if needs_review else "ready"

    labels = {
        "ready": "EVIDENCIA DISPONIBLE",
        "review": "REVISIÓN NECESARIA",
        "incomplete": "EVIDENCIA INCOMPLETA",
    }
    summaries = {
        "ready": "La corrida conserva poses, procedencia y parámetros suficientes para revisión y reproducción técnica.",
        "review": "La corrida produjo evidencia útil, pero contiene reservas que deben revisarse antes de continuar.",
        "incomplete": "Faltan afinidad o poses; esta corrida no debe usarse para priorizar el ligando.",
    }

    if not affinities:
        sampling_status, sampling_label = "missing", "SIN EVIDENCIA"
        sampling_detail = "No hay poses para describir la separación interna."
    elif len(affinities) == 1:
        sampling_status, sampling_label = "review", "NO COMPARABLE"
        sampling_detail = "Solo hay una pose; no puede describirse separación interna."
    elif near_tie_count > 1:
        sampling_status, sampling_label = "review", "AMBIGUO"
        sampling_detail = (
            f"{near_tie_count} poses quedan a <=1 kcal/mol; diferencia pose 1-2 "
            f"{pose_gap:.2f} kcal/mol. No se registraron réplicas ni ensemble."
        )
    else:
        sampling_status, sampling_label = "available", "DESCRIPTIVO"
        sampling_detail = (
            f"Diferencia pose 1-2 {pose_gap:.2f} kcal/mol. "
            "No se registraron réplicas ni ensemble."
        )

    model_in_domain = getattr(eval_result, "in_applicability_domain", None)
    fallback_reason = getattr(eval_result, "fallback_reason", None)

    # DOC 71, DEFECTO A6. Aqui se leia `engine_used` y se imprimia como si fuera
    # el motor de docking, produciendo «motor no informado / universal» en un
    # dossier que dos secciones mas abajo declara Vina 1.2.7.
    #
    # Es una COLISION DE NOMBRES, no un dato que falte: `engine_used` es el motor
    # HARDWARE del router (gpu/cpu) y su propia columna lo dice —«None en
    # pipeline eval»—, porque ese camino no usa el router. El motor de docking
    # vive en `docking_protocol.engine` y su version en `vina_version`, y las dos
    # ya se reportan en la dimension de reproducibilidad.
    #
    # La dimension «Dominio del modelo» habla del MODELO, y eso es lo que debe
    # decir. Mezclar las dos identidades es lo que hacia que el documento se
    # contradijera consigo mismo.
    modelo = getattr(eval_result, "model_used", None)
    model_name = {
        "family": "modelo de familia",
        "universal": "modelo universal",
    }.get(modelo, modelo or "modelo no informado")
    engine_name = (
        getattr(eval_result, "engine_used", None)
        or _value(protocol_stub, "engine")
        or "motor no informado"
    )
    dimensions = [
        {
            "id": "system",
            "label": "Preparación del sistema",
            "status": "available" if target_readiness == "listo" else "review" if target_readiness == "revisar" else "missing",
            "status_label": "DOCUMENTADA" if target_readiness == "listo" else "REVISAR" if target_readiness == "revisar" else "INSUFICIENTE",
            "detail": (
                "El inventario registra receptor preparado, grid y referencias estructurales."
                if target_readiness == "listo"
                else "El inventario no permite confirmar todos los requisitos de preparación."
            ),
        },
        {
            "id": "docking",
            "label": "Señal de docking",
            "status": "missing" if incomplete else "available",
            "status_label": "INSUFICIENTE" if incomplete else "DISPONIBLE",
            "detail": (
                "Faltan poses o afinidad serializada."
                if incomplete
                else (
                    f"{len(affinities)} poses serializadas; mejor afinidad cruda "
                    f"{top_pose_affinity:.2f} kcal/mol"
                    + (f" · {engine_name}" if engine_name != "motor no informado" else "")
                    + (f" {vina_version}" if vina_version else "")
                    + "."
                )
            ),
        },
        {
            "id": "sampling",
            "label": "Muestreo de poses",
            "status": sampling_status,
            "status_label": sampling_label,
            "detail": sampling_detail,
        },
        {
            "id": "reproducibility",
            "label": "Reproducibilidad técnica",
            "status": "available" if reproducibility_count == 3 else "review" if reproducibility_count else "missing",
            "status_label": "COMPLETA" if reproducibility_count == 3 else "PARCIAL" if reproducibility_count else "INSUFICIENTE",
            "detail": f"{reproducibility_count}/3 trazas: versión del motor, semilla y parser.",
        },
        {
            "id": "physical",
            "label": "Validez física de poses",
            "status": "available" if physical_validity["status"] == "passed" else "not_evaluated" if physical_validity["status"] == "not_evaluated" else "review",
            "status_label": physical_validity["label"],
            "detail": physical_validity["detail"],
        },
        {
            "id": "model",
            "label": "Dominio del modelo",
            "status": "available" if model_in_domain is True else "review" if model_in_domain is False else "not_evaluated",
            "status_label": "DENTRO DEL DOMINIO DECLARADO" if model_in_domain is True else "FUERA DEL DOMINIO" if model_in_domain is False else "NO INFORMADO",
            "detail": (
                f"{model_name}"
                + (f"; fallback: {fallback_reason}." if fallback_reason else ".")
                + " El motor de acoplamiento y su version se declaran en la traza de"
                  " reproducibilidad, no aqui: son identidades distintas."
            ),
        },
        {
            "id": "physicochemical",
            "label": "Descriptores fisicoquímicos",
            "status": "available" if descriptor_count >= 3 else "review" if descriptor_count else "missing",
            "status_label": f"{descriptor_count} SEÑALES REPORTADAS" if descriptor_count else "SIN DATOS",
            "detail": "Se reportan valores y reglas por separado; no se convierten en una calificación global.",
        },
        {
            "id": "selectivity",
            "label": "Evidencia de selectividad",
            "status": "available" if selectivity_ran and selectivity_count else "review" if selectivity_ran else "not_evaluated",
            "status_label": f"{selectivity_count} ANTI-TARGETS EVALUADOS" if selectivity_count else "EJECUCIÓN SIN RESULTADOS" if selectivity_ran else "NO EVALUADA",
            "detail": (
                "Comparación computacional relativa al protocolo; no demuestra selectividad experimental."
                if selectivity_ran
                else "La corrida no registró un panel de anti-targets."
            ),
        },
    ]

    assumptions = [
        "Las afinidades se interpretan como señales de ranking dentro del protocolo, no como mediciones de energía libre experimental.",
        "La mejor pose cruda se identifica por el orden de afinidad serializado; ese orden no demuestra validez geométrica.",
        "No se atribuyen operaciones de preparación, protonación o minimización que la corrida no haya registrado.",
        # ── Desolvatación ──────────────────────────────────────────────────
        #
        # `services/docking/preparer.py` elimina TODAS las aguas
        # cristalográficas (HOH, WAT, DOD) sin excepción. Para acoplamiento
        # generalista es la práctica estándar, y no se cambia aquí. Lo que
        # faltaba era decirlo: hay dianas —la proteasa del VIH-1 con su agua
        # catalítica, la red de la bisagra en varias quinasas— donde una o
        # varias aguas puente forman parte del reconocimiento molecular, y
        # acoplar contra el bolsillo seco cambia los contactos disponibles.
        #
        # Un dossier que no declara esta condición describe un sistema que no
        # es el que se acopló.
        "Preparación en condición desolvatada: se eliminaron todas las aguas "
        "cristalográficas del receptor. Si esta diana requiere aguas puente "
        "conservadas para el reconocimiento molecular, los contactos y las "
        "afinidades de esta corrida no las incluyen.",
    ]
    # DOC 71, DEFECTOS A2 y A5. El stacking por familia reparte pesos ANTES de
    # correr: la proteasa da 0,60 a CL-GNN porque asi lo midio el diagnostico de
    # familia. Si esa etapa despues no serializa nada, el documento acaba
    # atribuyendo dominancia a un modelo que no dijo una palabra -«CL-GNN
    # dominante», peso 0,00, salida no reportada-, y el lector no tiene forma de
    # saber que el peso es una expectativa y no una contribucion.
    #
    # No se corrige bajando el peso -es un dato del protocolo, no de la corrida-
    # sino DECLARANDO la contradiccion donde se lee la conclusion.
    pesos_sin_salida = [
        etiqueta for etiqueta, peso, salida in (
            ("XGBoost", getattr(eval_result, "stacking_xgb_weight", None),
             getattr(eval_result, "xgb_score", None)),
            ("CL-GNN", getattr(eval_result, "stacking_clgnn_weight", None),
             getattr(eval_result, "clgnn_score", None)),
            ("GNN legacy (RTMScore)", getattr(eval_result, "stacking_gnn_weight", None),
             getattr(eval_result, "gnn_score", None)),
            ("Vina", getattr(eval_result, "stacking_vina_weight", None),
             getattr(eval_result, "affinity_kcal", None)),
        )
        if peso not in (None, 0) and salida is None
    ]

    uncertainties = []
    stacking_degradado = getattr(eval_result, "stacking_degraded", None)
    stacking_ausentes = getattr(eval_result, "stacking_missing_components", None)
    if stacking_degradado:
        nombres = ", ".join(map(str, stacking_ausentes or [])) or "no registrados"
        uncertainties.append(
            "El stacking M4 se ejecuto degradado: se excluyeron componentes "
            f"ausentes ({nombres}) y se renormalizaron los pesos. La formula "
            "efectiva queda conservada aparte de los pesos nominales del diseno."
        )
    if pesos_sin_salida:
        uncertainties.append(
            "El protocolo de familia asigna peso en el stacking a "
            + ", ".join(pesos_sin_salida)
            + ", pero esas etapas no serializaron salida en esta corrida. El peso"
              " describe lo que el protocolo esperaba, no lo que aporto: no debe"
              " leerse como que ese modelo domino el resultado."
        )
    if physical_validity["status"] == "not_evaluated":
        uncertainties.append(physical_validity["detail"])
    if near_tie_count > 1:
        uncertainties.append(
            f"{near_tie_count} poses quedan dentro de 1 kcal/mol; la selección de una sola pose es ambigua."
        )
    if physical_validity["status"] == "review":
        uncertainties.append(
            "Los controles físicos no corrieron enteros sobre todas las poses; «revisión "
            "necesaria» no equivale a pose aprobada."
        )
    if 0 < physical_validity["poses_evaluated"] < physical_validity["poses_produced"]:
        uncertainties.append(
            f"Sólo {physical_validity['poses_evaluated']} de "
            f"{physical_validity['poses_produced']} poses recibieron veredicto físico."
        )
    if pose_selection["status"] == "abstained":
        uncertainties.append(
            "El selector de pose se abstuvo: no recomendó ninguna pose. La referencia es "
            "Vina top-1 como fallback, no como acierto del selector."
        )
    elif pose_selection["status"] == "unavailable":
        uncertainties.append(
            "El selector de pose no se ejecutó en esta corrida; la referencia es Vina top-1."
        )
    elif pose_selection["status"] == "error":
        uncertainties.append(
            "El selector de pose falló, así que no hay recomendación que leer."
        )
    if pose_selection["diverges_from_vina_top1"]:
        uncertainties.append(
            f"La pose sugerida (#{pose_selection['suggested_pose_rank']}) y la top-1 de Vina "
            f"(#{pose_selection['vina_top1_rank']}) no son la misma. Ambas se conservan."
        )
    if pose_selection["suggested_pose_rank"] is not None and (
        pose_selection["suggested_pose_physical_status"] != "passed"
    ):
        uncertainties.append(
            "La pose sugerida no está confirmada como físicamente válida, y NO se sustituye "
            "por otra: elegir «la siguiente que pase» sería una decisión que nadie tomó."
        )
    if reproducibility_count < 3:
        uncertainties.append("La traza de reproducibilidad está incompleta.")
    if model_in_domain is False:
        uncertainties.append("La salida derivada está fuera del dominio de aplicabilidad declarado.")
    elif model_in_domain is None:
        uncertainties.append("El dominio de aplicabilidad del modelo no fue informado.")
    uncertainties.extend(warnings)

    if incomplete or physical_validity["status"] == "failed":
        next_action = {
            "status": "abstain",
            "label": "ABSTENCIÓN: COMPLETAR LA CORRIDA",
            "detail": "No priorizar el ligando ni iniciar cálculos posteriores hasta recuperar poses y resolver los controles fallidos.",
        }
    elif physical_validity["status"] != "passed":
        next_action = {
            "status": "review",
            "label": "VALIDAR GEOMETRÍA ANTES DE CONTINUAR",
            "detail": "Comprobar choques, valencias, geometría, strain y consistencia del complejo antes de MM-GBSA, dinámica molecular o priorización experimental.",
        }
    elif needs_review:
        next_action = {
            "status": "review",
            "label": "RESOLVER RESERVAS ANTES DE COMPARAR",
            "detail": "Documentar las reservas de preparación, dominio o reproducibilidad antes de comparar esta corrida con otras.",
        }
    else:
        next_action = {
            "status": "proceed",
            "label": "APTA PARA ANÁLISIS POSTERIOR",
            "detail": "La evidencia disponible permite continuar dentro del mismo protocolo, conservando las limitaciones documentadas.",
        }

    provenance = build_provenance(eval_result, target, molecule)

    return {
        "status": status,
        "label": labels[status],
        "summary": summaries[status],
        "provenance": provenance,
        "pose_count": len(affinities),
        "top_pose_affinity": top_pose_affinity,
        "pose_gap": pose_gap,
        "near_tie_count": near_tie_count,
        "target_readiness": target_readiness,
        "reproducibility": {
            "available_count": reproducibility_count,
            "total_count": 3,
            "vina_version": vina_version,
            "random_seed": random_seed,
            "parsing_source": parsing_source,
        },
        # DOC 71, DEFECTO A1. El frontend leia `xgb_score`, `shap_values` y
        # `clgnn_score` DIRECTAMENTE del ORM, mientras el dossier construia su
        # seccion de evidencia desde este resumen, que no los tenia. Dos
        # lectores sobre dos fuentes distintas es como se llega a que la
        # interfaz muestre «salida 0.05 con SHAP» y el documento diga que solo
        # consta el modelo universal y el aviso de dominio.
        #
        # Aqui se serializan una vez, con `None` explicito donde la corrida no
        # produjo nada. `None` significa NO SE EJECUTO o NO SE SERIALIZO, nunca
        # cero: un cero es una prediccion y la ausencia no lo es.
        "ml_signals": {
            "xgboost": {
                "salida": getattr(eval_result, "xgb_score", None),
                "probabilidad_clasificador": getattr(eval_result, "classifier_prob", None),
                "shap": getattr(eval_result, "shap_values", None) or None,
                "peso_en_el_stacking": getattr(eval_result, "stacking_xgb_weight", None),
                # A4: hay DOS XGBoost en el producto y compartian nombre. Este es
                # el de rescoring; el selector de poses es un XGBRanker distinto,
                # con su propia version, y vive en `pose_selection`.
                "cual": "rescoring",
            },
            "cl_gnn": {
                "salida": getattr(eval_result, "clgnn_score", None),
                "atencion": bool(getattr(eval_result, "gnn_attention", None)),
                # Hasta v17 esto leia `stacking_gnn_weight`, que es el peso de
                # la GNN LEGACY. Para GPCR eso ponia «CL-GNN, peso 0.40» sobre
                # un modelo cuyo peso real es 0.00.
                "peso_en_el_stacking": getattr(eval_result, "stacking_clgnn_weight", None),
            },
            "gnn_geometrico": {
                "salida": getattr(eval_result, "gnn_score", None),
                "peso_en_el_stacking": getattr(eval_result, "stacking_gnn_weight", None),
                "nota": "RTMScore, deprecada. Conserva peso en algunas familias del artefacto vigente.",
            },
            "cuantico": {"salida": getattr(eval_result, "quantum_score", None)},
            "mmgbsa": {
                "salida_kcal_mol": getattr(eval_result, "mmgbsa_score", None),
                # La condición viaja PEGADA al número, aquí y en el dossier.
                # Un ΔG de MM-GBSA sin decir con qué se parametrizó el ligando
                # es exactamente la clase de número que este producto existe
                # para no emitir. Ver `services/chemistry/molchamb_v2.py`:
                # el ligando se tipa con átomos de la biblioteca de PROTEÍNA de
                # AMBER14 porque no hay GAFF/antechamber en el paquete.
                "condicion_de_validez": (
                    MMGBSA_CONDICION
                    if getattr(eval_result, "mmgbsa_score", None) is not None
                    else None
                ),
            },
            "familia_del_objetivo": getattr(eval_result, "target_family", None),
            "stacking": {
                "pesos_nominales": {
                    "vina": getattr(eval_result, "stacking_vina_weight", None),
                    "xgb": getattr(eval_result, "stacking_xgb_weight", None),
                    "gnn": getattr(eval_result, "stacking_gnn_weight", None),
                    "clgnn": getattr(eval_result, "stacking_clgnn_weight", None),
                },
                "pesos_efectivos": getattr(eval_result, "stacking_effective_weights", None),
                "degradado": stacking_degradado,
                "componentes_ausentes": stacking_ausentes,
            },
            "nota": (
                "Un valor nulo significa que la etapa no se ejecuto o no serializo su "
                "salida. No se sustituye por cero ni por un neutro: eso convertiria una "
                "ausencia en una prediccion."
            ),
        },
        "model_context": {
            "engine": (
                getattr(eval_result, "engine_used", None)
                or _value(getattr(eval_result, "docking_protocol", None), "engine")
            ),
            "model": getattr(eval_result, "model_used", None),
            "in_domain": getattr(eval_result, "in_applicability_domain", None),
            "fallback_reason": getattr(eval_result, "fallback_reason", None),
        },
        "physical_validity": physical_validity,
        "pose_selection": pose_selection,
        "pose_evidence": pose_evidence,
        "dimensions": dimensions,
        "assumptions": assumptions,
        "uncertainties": uncertainties,
        "next_action": next_action,
        "warnings": warnings,
        #: Los mismos avisos con su severidad DECLARADA por quien los emitió.
        #: `warnings` se conserva —el dossier los imprime como prosa— pero la
        #: severidad ya no se deduce de la redacción en ningún lector.
        "avisos_declarados": avisos_declarados,
    }
