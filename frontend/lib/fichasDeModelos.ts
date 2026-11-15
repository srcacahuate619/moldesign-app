// =====================================================================
// Fichas de modelos: qué guardó CADA modelo en esta evaluación
// =====================================================================
//
// La sección «Modelos» de Análisis enseña lo que cada modelo devolvió, sin
// juzgarlo: la calidad de un resultado la decide quien lo lee, y lo que decida
// valdrá igual cuando los modelos sean los de cada persona y no los de
// demostración. Esta función es el contrato de esa sección: de un resultado
// guardado saca una ficha por modelo, y nada más.
//
// Reglas (las mismas que `ml_signals` del dossier, DOC 71 A1):
//
//  1. **Un campo nulo es ausencia, nunca cero.** Un modelo sin salida guardada
//     no recibe ficha con un valor neutro: va a `sinSalida`, con un motivo que
//     no inventa lo que no se sabe (no se ejecutó, falló, o la corrida es
//     anterior a su registro).
//  2. **Cada salida se rotula con el modelo que la produjo.** `xgb_score` es la
//     probabilidad del CLASIFICADOR de binder (el productor la escribe desde
//     `classifier_prob`, runner.py); `ml_pki` es la REGRESIÓN. Son dos modelos
//     de XGBoost con salidas distintas y comparten nombre en el stacking.
//  3. **Sin identificador no se inventa uno.** Sólo la regresión (`model_used`,
//     el nombre, y `shap_model_id`, el SHA-256 del archivo) y el selector
//     (`pose_selection.model`) dejan su identificador en el resultado. Para el clasificador y CL-GNN la ficha dice
//     que no se registró.
//  4. **No se lista un modelo sin productor.** La GNN legacy (`gnn_score`) se
//     fija a `null` en el backend, así que no tiene ficha ni línea de «sin
//     salida»: ofrecerla sería la mentira que ENG-001 prohíbe.
//
// El peso en el índice compuesto sale de `pesosRegistrados`, que no rellena
// nada desde el diseño de una familia.

import type { EvaluationResult } from "./types";
import { pesosRegistrados } from "./procedenciaDeSenales";

export type IdDeModelo = "regresor" | "clasificador" | "clgnn";

const esNumero = (valor: unknown): valor is number =>
  typeof valor === "number" && Number.isFinite(valor);

const textoOnulo = (valor: unknown): string | null =>
  typeof valor === "string" && valor.trim() !== "" ? valor.trim() : null;

/** XGBoost que regresa el pKi (Model A). */
export interface FichaRegresor {
  /** pKi guardado. `null` en corridas anteriores a SCHEMA 16: no consta. */
  pki: number | null;
  /** `true`/`false` si se registró; `null` = no se registró, no «sí». */
  enDominio: boolean | null;
  /** `model_used`, tal cual. */
  modelo: string | null;
  /**
   * `shap_model_id`: el SHA-256 del archivo del modelo que produjo el SHAP (no
   * un nombre; `model_used` es el nombre). Sólo existe si hubo SHAP.
   */
  huellaDelModelo: string | null;
  /** Motivo por el que se usó el modelo universal en vez del de la familia. */
  motivoDeRespaldo: string | null;
  /** Contribuciones SHAP, o `null` si la corrida no las guardó. */
  shap: Record<string, number> | null;
  /** Qué magnitud explica el SHAP (`delta_pKi`, `pKi` o `null` si no consta). */
  salidaDelShap: string | null;
}

/** XGBoost que clasifica «buen binder». */
export interface FichaClasificador {
  /** Probabilidad entre 0 y 1. */
  probabilidad: number;
  peso: number | null;
  /** El índice compuesto lo declaró ausente (sólo ocurre con peso > 0). */
  declaradoAusente: boolean;
}

export interface FichaClGnn {
  /** Probabilidad entre 0 y 1 sobre la pose acoplada. */
  valor: number;
  peso: number | null;
  declaradoAusente: boolean;
}

export interface ModeloSinSalida {
  id: IdDeModelo;
  /** El stacking lo listó como componente ausente (requiere peso > 0). */
  declaradoAusente: boolean;
}

export interface FichasDeModelos {
  regresor: FichaRegresor | null;
  clasificador: FichaClasificador | null;
  clgnn: FichaClGnn | null;
  sinSalida: ModeloSinSalida[];
  /** ¿Hay al menos una ficha? Decide el estado de la pestaña. */
  conAlguna: boolean;
}

/**
 * Las fichas de los modelos que dejaron salida en el resultado.
 *
 * El orden de `sinSalida` es el de la interfaz y no depende de los datos.
 */
export function fichasDeModelos(result: EvaluationResult | null | undefined): FichasDeModelos {
  if (!result) {
    return { regresor: null, clasificador: null, clgnn: null, sinSalida: [], conAlguna: false };
  }

  const pesos = pesosRegistrados(result).values;
  const ausentes = new Set((result.stacking_missing_components ?? []).map(String));

  // ── Regresión de XGBoost ───────────────────────────────────────────────
  const shap = result.shap_values && Object.keys(result.shap_values).length > 0 ? result.shap_values : null;
  const pki = esNumero(result.ml_pki) ? result.ml_pki : null;
  const modelo = textoOnulo(result.model_used);
  const regresor: FichaRegresor | null =
    pki != null || shap != null
      ? {
          pki,
          // Los dos campos salen del mismo flag en el productor (queue_handler):
          // el segundo sólo cubre corridas que no guardaron el primero.
          enDominio: result.in_applicability_domain ?? result.ml_pki_aplicada ?? null,
          modelo,
          huellaDelModelo: textoOnulo(result.shap_model_id),
          motivoDeRespaldo: textoOnulo(result.fallback_reason),
          shap,
          salidaDelShap: textoOnulo(result.shap_output),
        }
      : null;

  // ── Clasificador de binder (`xgb_score`) ───────────────────────────────
  const clasificador: FichaClasificador | null = esNumero(result.xgb_score)
    ? {
        probabilidad: result.xgb_score,
        peso: esNumero(pesos.xgb) ? pesos.xgb : null,
        declaradoAusente: ausentes.has("xgb"),
      }
    : null;

  // ── CL-GNN ─────────────────────────────────────────────────────────────
  const clgnn: FichaClGnn | null = esNumero(result.clgnn_score)
    ? {
        valor: result.clgnn_score,
        peso: esNumero(pesos.clgnn) ? pesos.clgnn : null,
        declaradoAusente: ausentes.has("clgnn"),
      }
    : null;

  const sinSalida: ModeloSinSalida[] = [];
  if (!regresor) sinSalida.push({ id: "regresor", declaradoAusente: false });
  if (!clasificador) sinSalida.push({ id: "clasificador", declaradoAusente: ausentes.has("xgb") });
  if (!clgnn) sinSalida.push({ id: "clgnn", declaradoAusente: ausentes.has("clgnn") });

  return {
    regresor,
    clasificador,
    clgnn,
    sinSalida,
    conAlguna: Boolean(regresor || clasificador || clgnn),
  };
}
