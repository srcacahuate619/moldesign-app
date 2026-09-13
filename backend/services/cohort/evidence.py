"""
Resumen científico de una corrida de cohorte: cobertura, evidencia y métricas.

# Qué es «evidencia» aquí

Lo que la corrida produjo de verdad, con sus denominadores a la vista: cuántas
filas traía el archivo, cuántas entraron, cuántas moléculas únicas se acoplaron,
cuántas fallaron y cuántas se abstuvieron. **No es un ranking de candidatos.**

La única magnitud científica que se publica por molécula es la **afinidad Vina
observada**. Se llama exactamente así en todo el producto —API, PDF e interfaz—
porque nombrarla «mejor», «probabilidad» o «éxito» convertiría una energía de
acoplamiento en una predicción de actividad, que es la afirmación que este
producto existe para no hacer.

`total_score` no aparece como conclusión en ninguna superficie de cohorte.

# Métricas etiquetadas: se abstienen por defecto

EF y ROC-AUC sólo se calculan cuando se cumplen TODAS las condiciones. Si falta
una, el resultado es `not_evaluated` con una razón estable — nunca un número
aproximado. Una métrica calculada sobre 4 moléculas, o sobre etiquetas que se
contradicen, es peor que no tener métrica: parece un resultado.

Y aunque se calculen, **no son validación prospectiva**. Miden si el
acoplamiento ordenó las etiquetas que ya venían en el archivo. Eso es un
diagnóstico retrospectivo del protocolo, no evidencia de que el método
encuentre fármacos.
"""

from __future__ import annotations

import math
import uuid
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import (
    CohortORM,
    CohortRunORM,
    CohortRunRowORM,
    EvaluationResultORM,
    EvaluationRunORM,
)
from services.cohort import execution as ex

#: Contrato de este resumen. Viaja en el JSON y en el paquete.
EVIDENCE_CONTRACT = "cohort_evidence/v1"

#: Mínimo de moléculas únicas etiquetadas para que una métrica signifique algo.
#: Por debajo, el intervalo de confianza cubre casi todo el rango posible y el
#: número sólo aporta autoridad falsa.
MIN_N_FOR_METRICS = 10

#: Fracciones de enriquecimiento que se intentan. Sólo se reportan las que
#: seleccionan al menos una molécula y menos que todas.
EF_FRACTIONS = (0.01, 0.05, 0.10)

#: El único orden que esta superficie ofrece, y su nombre EXACTO.
SORT_BY_OBSERVED_AFFINITY = "afinidad_vina_observada"


# ── Razones de abstención (estables) ─────────────────────────────────

SIN_ETIQUETAS = "SIN_ETIQUETAS"
SIN_POSITIVOS = "SIN_POSITIVOS"
SIN_NEGATIVOS = "SIN_NEGATIVOS"
MUESTRA_INSUFICIENTE = "MUESTRA_INSUFICIENTE"
SIN_AFINIDAD = "SIN_AFINIDAD"
ETIQUETAS_EN_CONFLICTO = "ETIQUETAS_EN_CONFLICTO"
CORRIDA_NO_TERMINAL = "CORRIDA_NO_TERMINAL"

METRIC_ABSTENTION_REASONS = (
    SIN_ETIQUETAS,
    SIN_POSITIVOS,
    SIN_NEGATIVOS,
    MUESTRA_INSUFICIENTE,
    SIN_AFINIDAD,
    ETIQUETAS_EN_CONFLICTO,
    CORRIDA_NO_TERMINAL,
)


def _observed_affinity(resultado: EvaluationResultORM | None) -> float | None:
    """
    La afinidad que Vina observó. `None` si la corrida no la registró.

    No se sustituye por cero ni por un valor «neutro»: un cero se leería como
    una afinidad medida de 0 kcal/mol, que es una afirmación, no una ausencia.
    """
    if resultado is None:
        return None
    valor = getattr(resultado, "affinity_kcal", None)
    if valor is None:
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


async def collect_rows(
    db: AsyncSession, run_id: uuid.UUID
) -> tuple[list[CohortRunRowORM], dict[uuid.UUID, EvaluationResultORM]]:
    """
    Filas de la corrida y sus resultados, buscados **por `result_id`**.

    Nunca por «el resultado más reciente de esta molécula»: dos corridas de la
    misma cohorte, o una molécula compartida con una evaluación individual,
    harían que esa búsqueda devolviera el resultado de otra ejecución y la
    evidencia describiría algo que no ocurrió.
    """
    filas = list(
        (
            await db.execute(
                select(CohortRunRowORM)
                .where(CohortRunRowORM.run_id == run_id)
                .order_by(CohortRunRowORM.source_row_index.asc())
            )
        )
        .scalars()
        .all()
    )
    ids = {fila.result_id for fila in filas if fila.result_id}
    if not ids:
        return filas, {}
    snapshots = (
        (await db.execute(select(EvaluationRunORM).where(EvaluationRunORM.id.in_(ids))))
        .scalars()
        .all()
    )
    encontrados: dict[uuid.UUID, Any] = {
        r.id: SimpleNamespace(**dict(r.snapshot_json or {})) for r in snapshots
    }
    faltantes = ids.difference(encontrados)
    if faltantes:
        # Compatibilidad con filas creadas antes de schema v11.
        resultados = (
            (await db.execute(
                select(EvaluationResultORM).where(EvaluationResultORM.id.in_(faltantes))
            ))
            .scalars()
            .all()
        )
        encontrados.update({r.id: r for r in resultados})
    return filas, encontrados


def build_coverage(
    run: CohortRunORM,
    filas: list[CohortRunRowORM],
    resultados: dict[uuid.UUID, EvaluationResultORM] | None = None,
) -> dict[str, Any]:
    """
    Cobertura con denominadores EXPLÍCITOS.

    `source_rows` es lo que traía el archivo; `eligible_rows` lo que entró como
    trabajo. La diferencia son las filas que el preflight declaró no elegibles y
    que nunca iban a ejecutarse — y siguen contando, porque desaparecer del
    denominador es cómo una cobertura del 60 % se presenta como del 100 %.
    """
    por_estado: dict[str, int] = {}
    for fila in filas:
        por_estado[fila.status] = por_estado.get(fila.status, 0) + 1

    # Moléculas ÚNICAS que se acoplaron de verdad: las filas que ejecutaron,
    # sin contar las que reutilizaron el resultado de otra.
    unicas = {
        fila.canonical_smiles
        for fila in filas
        if fila.reused_from_row is None and fila.status == ex.ROW_COMPLETED
    }

    total_archivo = int(run.total_rows or 0)
    elegibles = int(run.eligible_rows or 0)
    completadas = por_estado.get(ex.ROW_COMPLETED, 0)
    reutilizadas = por_estado.get(ex.ROW_DUPLICATE_REUSED, 0)

    # ── Denominadores estructurales, dichos en voz alta ─────────────
    #
    # Cada embudo tiene su propio denominador y ninguno se hereda del anterior
    # sin decirlo. «5 poses válidas» no significa nada si no se sabe sobre
    # cuántas se midió: una cobertura del 100% sobre 2 de 40 moléculas es una
    # cobertura del 5% del trabajo, y presentarla como completa sería mentir
    # por omisión del denominador.
    resultados = resultados or {}
    con_poses = 0
    seleccionables = 0
    fisicamente_evaluadas = 0
    por_veredicto = {"passed": 0, "failed": 0, "review": 0, "not_evaluated": 0}
    selector = {"selected": 0, "abstained": 0, "unavailable": 0, "error": 0}

    for fila in filas:
        resultado = resultados.get(fila.result_id) if fila.result_id else None
        if resultado is None:
            continue
        poses = getattr(resultado, "docking_poses", None) or []
        if poses:
            con_poses += 1
        # Seleccionable = el selector TENÍA con qué opinar (dos poses o más).
        # No es lo mismo que «el selector opinó»: eso lo cuenta `selector`.
        if len(poses) > 1:
            seleccionables += 1

        evidencia_fisica = getattr(resultado, "structural_evidence", None)
        estado = (evidencia_fisica or {}).get("stage_status") if isinstance(evidencia_fisica, dict) else None
        if estado in por_veredicto:
            por_veredicto[estado] += 1
            if estado != "not_evaluated":
                fisicamente_evaluadas += 1
        else:
            por_veredicto["not_evaluated"] += 1

        seleccion = getattr(resultado, "pose_selection", None)
        estado_sel = (seleccion or {}).get("status") if isinstance(seleccion, dict) else None
        selector[estado_sel if estado_sel in selector else "unavailable"] += 1

    # ── Exclusiones con su causa ────────────────────────────────────
    # Una molécula que no llegó al final no desaparece: se cuenta y se dice por
    # qué. Esconderlas dejaría un informe que sólo habla de lo que salió bien.
    exclusiones: dict[str, int] = {}
    for fila in filas:
        if fila.status in (ex.ROW_COMPLETED, ex.ROW_DUPLICATE_REUSED):
            continue
        causa = fila.error_code or fila.status or "sin_causa_registrada"
        exclusiones[str(causa)] = exclusiones.get(str(causa), 0) + 1
    no_elegibles = max(total_archivo - elegibles, 0)
    if no_elegibles:
        exclusiones["no_elegible_en_preflight"] = (
            exclusiones.get("no_elegible_en_preflight", 0) + no_elegibles
        )

    return {
        "source_rows": total_archivo,
        "eligible_rows": elegibles,
        "not_eligible_rows": max(total_archivo - elegibles, 0),
        "unique_molecules_executed": len(unicas),
        "completed_rows": completadas,
        "failed_rows": por_estado.get(ex.ROW_FAILED, 0),
        "not_evaluated_rows": por_estado.get(ex.ROW_NOT_EVALUATED, 0),
        "duplicate_reused_rows": reutilizadas,
        "pending_rows": por_estado.get(ex.ROW_PENDING, 0),
        "running_rows": por_estado.get(ex.ROW_RUNNING, 0),
        "interrupted_rows": por_estado.get(ex.ROW_INTERRUPTED, 0),
        "cancelled_rows": por_estado.get(ex.ROW_CANCELLED, 0),
        # ── Embudo estructural, con el denominador de cada escalón ──
        "structural_funnel": {
            "input_rows": total_archivo,
            "eligible_rows": elegibles,
            "executed_rows": completadas + reutilizadas,
            "rows_with_poses": con_poses,
            "selectable_rows": seleccionables,
            "physically_evaluated_rows": fisicamente_evaluadas,
            "physical_verdicts": dict(por_veredicto),
            "selector_states": dict(selector),
            "note": (
                "Cada escalón se cuenta sobre el archivo COMPLETO, no sobre el escalón "
                "anterior. Un veredicto físico sólo cuenta como evaluado si la etapa emitió "
                "uno: `not_evaluated` describe al validador, nunca a la molécula, y no es "
                "evidencia negativa."
            ),
        },
        # Qué quedó fuera y por qué. Ninguna fila desaparece del recuento.
        "exclusions": {
            "total": sum(exclusiones.values()),
            "by_cause": dict(sorted(exclusiones.items())),
        },
        # Los denominadores, dichos en voz alta y no derivados por el lector.
        "denominators": {
            "eligible_over_source": {
                "numerator": elegibles,
                "denominator": total_archivo,
                "value": round(elegibles / total_archivo, 6) if total_archivo else None,
            },
            "resolved_over_eligible": {
                "numerator": completadas + reutilizadas,
                "denominator": elegibles,
                "value": (
                    round((completadas + reutilizadas) / elegibles, 6) if elegibles else None
                ),
            },
        },
    }


def build_molecule_evidence(
    filas: list[CohortRunRowORM], resultados: dict[uuid.UUID, EvaluationResultORM]
) -> list[dict[str, Any]]:
    """Una entrada por FILA del trabajo. Ninguna se resume ni se agrupa."""
    from services.chemistry.pose_selection import pose_selection_para_lectura

    evidencia: list[dict[str, Any]] = []
    for fila in filas:
        resultado = resultados.get(fila.result_id) if fila.result_id else None
        afinidad = _observed_affinity(resultado)
        # Una fila que reutiliza hereda la afinidad de la que acopló: es la
        # misma molécula y el mismo cálculo, no uno nuevo.
        if afinidad is None and fila.reused_from_row is not None:
            hermana = next(
                (
                    otra
                    for otra in filas
                    if otra.source_row_index == fila.reused_from_row
                ),
                None,
            )
            if hermana is not None and hermana.result_id:
                afinidad = _observed_affinity(resultados.get(hermana.result_id))
        evidencia.append(
            {
                "source_row_index": fila.source_row_index,
                "source_name": fila.source_name,
                "canonical_smiles": fila.canonical_smiles,
                "status": fila.status,
                # El nombre es el contrato: es lo que Vina observó, no una
                # predicción de actividad ni una probabilidad.
                "observed_vina_affinity_kcal_mol": afinidad,
                "molecule_id": str(fila.molecule_id) if fila.molecule_id else None,
                "result_id": str(fila.result_id) if fila.result_id else None,
                "active_label": fila.active_label,
                "control_role": fila.control_role,
                "duplicate_of_row": fila.duplicate_of_row,
                "reused_from_row": fila.reused_from_row,
                "error_code": fila.error_code,
                "error_detail": fila.error_detail,
                # La evidencia geometrica/fisica de ESTA ejecucion, tal como la
                # persistio la etapa estructural. Viaja por referencia al mismo
                # `result_id`, asi que no se recalcula ni se puede desincronizar.
                # `None` significa que la evaluacion es anterior a la etapa: no
                # evaluada, nunca una pose invalida.
                "structural_evidence": (
                    getattr(resultado, "structural_evidence", None) if resultado else None
                ),
                # La recomendacion del selector de pose de ESTA ejecucion, por
                # el mismo `result_id`. Nunca `None`: una fila anterior a la
                # etapa —o una que no llego a acoplar— abre como `unavailable`
                # con su razon, y con Vina top-1 declarado como fallback. Un
                # `null` obligaria a cada lector a decidir si el selector no
                # existia, se abstuvo o fallo, que no son lo mismo.
                #
                # Se LEE lo persistido: aqui no se ejecuta el selector, asi que
                # una cohorte no puede discrepar del caso sobre la misma pose.
                "pose_selection": pose_selection_para_lectura(
                    getattr(resultado, "pose_selection", None) if resultado else None
                ),
            }
        )
    return evidencia


def sort_by_observed_affinity(evidencia: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Ordena por afinidad Vina observada, la más negativa primero.

    Es un ORDEN, no un veredicto. Las filas sin afinidad van al final y
    conservan su estado: no se les asigna un valor para poder colocarlas.
    """
    con_valor = [e for e in evidencia if e["observed_vina_affinity_kcal_mol"] is not None]
    sin_valor = [e for e in evidencia if e["observed_vina_affinity_kcal_mol"] is None]
    con_valor.sort(key=lambda e: e["observed_vina_affinity_kcal_mol"])
    return [*con_valor, *sin_valor]


# ── Métricas etiquetadas ─────────────────────────────────────────────


def _abstencion(razon: str, mensaje: str, **extra: Any) -> dict[str, Any]:
    return {
        "status": "not_evaluated",
        "reason_code": razon,
        "reason": mensaje,
        "roc_auc": None,
        "enrichment_factors": [],
        **extra,
    }


def build_labeled_metrics(
    evidencia: list[dict[str, Any]], *, run_status: str
) -> dict[str, Any]:
    """
    EF y ROC-AUC, o una abstención con razón estable. Nunca un número a medias.

    # Política, en el orden en que se aplica

    1. **La corrida tiene que haber terminado.** Métricas sobre una corrida a
       medias medirían el orden en que el planificador despachó, no la química.
    2. **Una molécula canónica cuenta UNA vez.** Los duplicados no inflan: si el
       archivo trae la misma molécula diez veces, sigue siendo una observación.
    3. **Los controles se reportan aparte**, fuera de la población de la métrica.
       Un control de referencia positivo, metido en la población, sube el
       enriquecimiento sin decir nada sobre la cohorte.
    4. **Etiquetas en conflicto abstienen.** Si dos filas de la misma molécula
       canónica dicen `active=1` y `active=0`, no se elige una: no sabemos cuál
       es y elegir sería inventar la respuesta.
    5. Hacen falta positivos, negativos, afinidad y tamaño suficiente.
    """
    if run_status not in (
        ex.RUN_COMPLETED,
        ex.RUN_COMPLETED_WITH_EXCEPTIONS,
        ex.RUN_FAILED,
        ex.RUN_CANCELLED,
    ):
        return _abstencion(
            CORRIDA_NO_TERMINAL,
            "La corrida todavía no ha terminado. Una métrica sobre una corrida a "
            "medias mediría el orden de despacho, no el acoplamiento.",
            n_total=0,
            n_positive=0,
            n_negative=0,
            coverage=None,
            controls=[],
        )

    # ── Controles, aparte ────────────────────────────────────────────
    controles = [
        {
            "source_row_index": e["source_row_index"],
            "source_name": e["source_name"],
            "canonical_smiles": e["canonical_smiles"],
            "control_role": e["control_role"],
            "active_label": e["active_label"],
            "status": e["status"],
            "observed_vina_affinity_kcal_mol": e["observed_vina_affinity_kcal_mol"],
        }
        for e in evidencia
        if e["control_role"] != "none"
    ]
    poblacion = [e for e in evidencia if e["control_role"] == "none"]

    # ── Una molécula canónica, una observación ───────────────────────
    por_canonico: dict[str, dict[str, Any]] = {}
    etiquetas: dict[str, set[bool]] = {}
    for e in poblacion:
        canonico = e["canonical_smiles"]
        if e["active_label"] is not None:
            etiquetas.setdefault(canonico, set()).add(bool(e["active_label"]))
        previo = por_canonico.get(canonico)
        # Se conserva la observación que TIENE afinidad; entre dos con afinidad,
        # la primera del archivo. No se promedian: es el mismo cálculo repetido,
        # no dos medidas independientes.
        if previo is None or (
            previo["observed_vina_affinity_kcal_mol"] is None
            and e["observed_vina_affinity_kcal_mol"] is not None
        ):
            por_canonico[canonico] = e

    en_conflicto = sorted(c for c, valores in etiquetas.items() if len(valores) > 1)
    if en_conflicto:
        return _abstencion(
            ETIQUETAS_EN_CONFLICTO,
            f"{len(en_conflicto)} molécula(s) canónica(s) llevan etiquetas `active` "
            "contradictorias en distintas filas. No se elige una por el usuario.",
            n_total=len(por_canonico),
            n_positive=0,
            n_negative=0,
            coverage=None,
            controls=controles,
            conflicting_molecules=en_conflicto[:20],
        )

    etiquetadas = [
        e for e in por_canonico.values() if e["active_label"] is not None
    ]
    if not etiquetadas:
        return _abstencion(
            SIN_ETIQUETAS,
            "La cohorte no declara etiquetas `active`. Sin etiquetas no hay nada "
            "contra lo que medir enriquecimiento.",
            n_total=len(por_canonico),
            n_positive=0,
            n_negative=0,
            coverage=None,
            controls=controles,
        )

    con_afinidad = [
        e for e in etiquetadas if e["observed_vina_affinity_kcal_mol"] is not None
    ]
    cobertura = round(len(con_afinidad) / len(etiquetadas), 6) if etiquetadas else None
    positivos = [e for e in con_afinidad if e["active_label"] is True]
    negativos = [e for e in con_afinidad if e["active_label"] is False]

    base = {
        "n_total": len(con_afinidad),
        "n_positive": len(positivos),
        "n_negative": len(negativos),
        "n_labeled_molecules": len(etiquetadas),
        "coverage": cobertura,
        "controls": controles,
    }

    if not con_afinidad:
        return _abstencion(
            SIN_AFINIDAD,
            "Ninguna molécula etiquetada tiene afinidad Vina observada.",
            **base,
        )
    if not positivos:
        return _abstencion(SIN_POSITIVOS, "No hay ninguna molécula etiquetada como activa.", **base)
    if not negativos:
        return _abstencion(SIN_NEGATIVOS, "No hay ninguna molécula etiquetada como inactiva.", **base)
    if len(con_afinidad) < MIN_N_FOR_METRICS:
        return _abstencion(
            MUESTRA_INSUFICIENTE,
            f"Sólo hay {len(con_afinidad)} moléculas etiquetadas con afinidad; el mínimo "
            f"para que la métrica signifique algo es {MIN_N_FOR_METRICS}.",
            **base,
        )

    # ── Cálculo ──────────────────────────────────────────────────────
    # Mejor = más negativo. Se ordena ascendente por afinidad.
    ordenadas = sorted(con_afinidad, key=lambda e: e["observed_vina_affinity_kcal_mol"])
    n = len(ordenadas)
    n_pos = len(positivos)
    tasa_base = n_pos / n

    # ROC-AUC por Mann-Whitney con empates a 0.5, sobre el score = -afinidad.
    concordantes = 0.0
    for p in positivos:
        for q in negativos:
            a, b = p["observed_vina_affinity_kcal_mol"], q["observed_vina_affinity_kcal_mol"]
            if a < b:
                concordantes += 1.0
            elif a == b:
                concordantes += 0.5
    roc_auc = round(concordantes / (n_pos * len(negativos)), 6)

    factores = []
    for fraccion in EF_FRACTIONS:
        k = math.ceil(n * fraccion)
        if k < 1 or k >= n:
            continue
        aciertos = sum(1 for e in ordenadas[:k] if e["active_label"] is True)
        factores.append(
            {
                "fraction": fraccion,
                "n_selected": k,
                "n_actives_selected": aciertos,
                "value": round((aciertos / k) / tasa_base, 6) if tasa_base else None,
            }
        )

    return {
        "status": "evaluated",
        "reason_code": None,
        "reason": None,
        "roc_auc": roc_auc,
        "enrichment_factors": factores,
        "base_rate": round(tasa_base, 6),
        # La frase va DENTRO de la métrica, no en una nota al pie que se pierde
        # al copiar el JSON a otro sitio.
        "interpretation_limit": (
            "Mide si el acoplamiento ordenó las etiquetas que ya venían en el archivo. "
            "Es un diagnóstico retrospectivo del protocolo sobre ESTA cohorte; no es "
            "validación prospectiva ni evidencia de que el método encuentre fármacos."
        ),
        **base,
    }


# ── Ensamblado ───────────────────────────────────────────────────────


async def build_run_evidence(
    db: AsyncSession, *, run: CohortRunORM, cohort: CohortORM, sort: str | None = None
) -> dict[str, Any]:
    """El resumen completo. Determinista salvo por lo que ya guardó la corrida."""
    filas, resultados = await collect_rows(db, run.id)
    evidencia = build_molecule_evidence(filas, resultados)
    if sort == SORT_BY_OBSERVED_AFFINITY:
        evidencia = sort_by_observed_affinity(evidencia)

    snapshot = cohort.preflight_snapshot_json or {}
    return {
        "contract": EVIDENCE_CONTRACT,
        "run_id": str(run.id),
        "cohort_id": str(cohort.id),
        "cohort_name": cohort.name,
        "run_status": run.status,
        "sorted_by": sort or "source_row_index",
        "cohort_fingerprint": run.cohort_fingerprint,
        "run_fingerprint": run.run_fingerprint,
        "effective_config": run.effective_config_json,
        "receptor": run.receptor_provenance_json,
        "coverage": build_coverage(run, filas, resultados),
        "molecules": evidencia,
        "labeled_metrics": build_labeled_metrics(evidencia, run_status=run.status),
        "provenance": {
            "cohort": cohort.provenance_json,
            "preflight_summary": snapshot.get("summary"),
            "execution_contract": ex.RUN_CONTRACT,
            "evidence_contract": EVIDENCE_CONTRACT,
            "stages": list(ex.COHORT_RUN_STAGES),
        },
        "limits": [
            "Completar un acoplamiento no demuestra actividad ni afinidad experimental.",
            "Las poses de esta cohorte no han superado todavía una validación geométrica/física "
            "automática; una afinidad sólo es interpretable después de revisar la pose.",
            "La afinidad Vina observada es una señal de ranking dentro de este protocolo, "
            "no una medida de energía libre.",
            "No hay puntuación agregada ni ranking de candidatos: este resumen no ordena "
            "moléculas por mérito farmacológico.",
            "Las filas `failed` y `not_evaluated` no son evidencia negativa sobre sus "
            "moléculas: describen lo que le pasó al motor.",
        ],
    }
