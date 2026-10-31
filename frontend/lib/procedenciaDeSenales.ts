// =====================================================================
// Procedencia de las señales: qué dijo REALMENTE esta corrida por etapa
// =====================================================================
//
// El DOT de «Procedencia de las señales» pinta una etapa por modelo —Vina,
// XGBoost, CL-GNN, MM-GBSA…— con un valor y un pie de descripción. Los valores
// que trae `pipelineDefinitions.ts` son LITERALES DE EJEMPLO («-9.4 kcal/mol»,
// «p = 0.81»): describen la forma del pipeline por familia, no lo que calculó
// esta molécula contra este receptor. Presentarlos como resultado sería
// inventarlo, y ya se corrigió una vez para MM-GBSA (fix UI-8).
//
// DOC 71, DEFECTOS A3 y A7. El pie caía a «sin salida serializada» siempre que
// no se hubiera sobrescrito, y sólo se sobrescribía para MM-GBSA. Una etapa con
// valor real —Vina con sus nueve poses, XGBoost con su score— se mostraba como
// «-7.0 kcal/mol · sin salida serializada»: dos afirmaciones contradictorias en
// la misma tarjeta, con la segunda desmintiendo a la primera. De ahí salieron
// los dos defectos que el informe listó por separado, y el desacuerdo con el
// dossier, que decía «9 poses serializadas» y daba su hash. El dossier tenía
// razón.
//
// La regla, en una frase: **«sin salida serializada» sólo cuando no hay valor.**

/** Lo que el backend serializó para una etapa, si serializó algo. */
export type SenalReal = { value?: string; weight?: number; sub?: string };

/** El perfil más específico que produjo una salida, nunca un aviso de aplicabilidad. */
export function protocoloRegistrado(real: Parameters<typeof pesosRegistrados>[0] & {
  weights_calibration_id?: string | null;
  m5_protocol_id?: string | null;
  m5_score?: number | null;
  m5_scientific_status?: string | null;
}): "M4" | "M5-Zn" | null {
  const estadosConCalculo = ["VALIDATED", "REVIEW_INVALID_BENCHMARK_SITE",
    "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE", "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING"];
  if (real.m5_protocol_id?.trim() && typeof real.m5_score === "number"
    && Number.isFinite(real.m5_score) && estadosConCalculo.includes(real.m5_scientific_status ?? "")) {
    return "M5-Zn";
  }
  return pesosRegistrados(real).source !== "missing" || real.weights_calibration_id?.trim() ? "M4" : null;
}

/** Pesos persistidos, sin rellenarlos desde el diseño de una familia. */
export function pesosRegistrados(real: {
  stacking_effective_weights?: Record<string, number> | null;
  stacking_vina_weight?: number | null;
  stacking_xgb_weight?: number | null;
  stacking_gnn_weight?: number | null;
  stacking_clgnn_weight?: number | null;
}): { source: "effective" | "individual" | "missing"; values: Record<string, number> } {
  const valid = (value: unknown): value is number =>
    typeof value === "number" && Number.isFinite(value) && value >= 0;
  const effective = Object.fromEntries(
    ["vina", "xgb", "gnn", "clgnn"]
      .filter((key) => valid(real.stacking_effective_weights?.[key]))
      .map((key) => [key, real.stacking_effective_weights![key]]),
  );
  if (Object.keys(effective).length > 0) return { source: "effective", values: effective };
  const individual = Object.fromEntries(Object.entries({
    vina: real.stacking_vina_weight,
    xgb: real.stacking_xgb_weight,
    gnn: real.stacking_gnn_weight,
    clgnn: real.stacking_clgnn_weight,
  }).filter((entry): entry is [string, number] => valid(entry[1])));
  return { source: Object.keys(individual).length > 0 ? "individual" : "missing", values: individual };
}
/**
 * La señal autorizada en M5 es `ums_warhead`; `ums_score` sólo conserva el
 * valor histórico de corridas antiguas. Cualquiera de las dos cuenta como
 * salida, pero nunca se sustituyen ni se mezclan.
 */
export function tieneSalidaUms(real: {
  ums_warhead?: number | null;
  ums_score?: number | null;
}): boolean {
  return real.ums_warhead != null || real.ums_score != null;
}

/** La etapa tal como la define el pipeline de la familia. */
export type EtapaDefinida = {
  id: string;
  post_hoc?: boolean;
  /** Peso que la familia le asigna por diseño. No es el de esta corrida. */
  weight?: number;
  label?: string;
  /**
   * La evidencia externa que justifica el peso de diseño («Δ AUC +0.086»,
   * «AUC 0.95 en HIV-1»). Viene de un diagnóstico sobre otro conjunto de datos,
   * NO de esta molécula.
   */
  note?: string;
};

export type EtapaMostrada = {
  value: string;
  sub: string;
  reportedWeight?: number;
  /** La nota de validación, sólo si la etapa participó de verdad. */
  note?: string;
  /** ¿Esta etapa produjo salida en esta corrida? */
  aporto: boolean;
};

/** Pie cuando hay valor pero no sabemos describir su origen. */
export const SIN_DESCRIPCION = "de esta corrida";
export const SIN_SERIALIZAR = "sin salida serializada";

/**
 * Traduce una etapa del pipeline a lo que se muestra, sin afirmar de más.
 *
 * No se recurre al `sub` de `pipelineDefinitions` («v1.2.7», «500 trees») como
 * respaldo: son literales de la definición de familia y presentarlos como la
 * procedencia de esta corrida sería la misma invención, en letra pequeña.
 */
export function describirEtapa(etapa: EtapaDefinida, real?: SenalReal, t?: (key: string) => string): EtapaMostrada {
  const tieneValor = real?.value != null;
  return {
    reportedWeight: real?.weight,
    aporto: tieneValor,
    value: real?.value ?? (etapa.post_hoc ? t?.("pr_signal_not_calculated") ?? "no calculado" : t?.("pr_signal_not_reported") ?? "no reportado"),
    sub: real?.sub
      ?? (tieneValor
        ? t?.("pr_pipeline_sub_this_run") ?? SIN_DESCRIPCION
        : etapa.post_hoc ? t?.("pr_signal_optional") ?? "cálculo opcional" : t?.("pr_signal_no_output") ?? SIN_SERIALIZAR),
    // ── La nota de validación se retira cuando la etapa no produjo nada ────
    //
    // La VM lo enseñó en 2BQV: la tarjeta de CL-GNN decía a la vez
    //
    //     «no reportado»  ·  «sin salida serializada»  ·  w=0.00
    //     Δ AUC +0.086 (HIV-1) · CL-GNN solo AUC 0.95
    //
    // Las dos primeras líneas dicen que el modelo no corrió; la tercera es su
    // hoja de resultados en un estudio ajeno, y colocada justo debajo se lee
    // como la calidad de ESTE número. Es el mismo error que el fix UI-8 quitó
    // de MM-GBSA —presentar un literal de la definición de familia como salida
    // de la corrida—, sólo que en la letra pequeña.
    note: tieneValor ? etapa.note : undefined,
  };
}

/** Una etapa que la familia pesa por diseño y que esta corrida no produjo. */
export type EtapaAusente = { id: string; label: string; pesoDeDiseno: number };

/**
 * Las etapas que el pipeline declara importantes y que no llegaron a opinar.
 *
 * Existe porque la cabecera del DOT —«M4 Proteasa · CL-GNN-dominante»— y su pie
 * —«CL-GNN domina; Vina+XGB peso bajo porque CL-GNN solo supera a cualquiera»—
 * describen el DISEÑO de la familia y se pintan pase lo que pase. Cuando el
 * modelo dominante no corre, el encabezado sigue anunciándolo y el lector se
 * lleva una corrida hecha por Vina+XGB creyendo que la hizo CL-GNN.
 *
 * Devolver la lista permite decirlo arriba, una vez, en vez de esperar que
 * alguien cruce el título con la tercera tarjeta.
 */
export function etapasAusentes(
  etapas: ReadonlyArray<EtapaDefinida & { aporto: boolean }>,
): EtapaAusente[] {
  return etapas
    .filter((etapa) => !etapa.post_hoc && (etapa.weight ?? 0) > 0 && !etapa.aporto)
    .map((etapa) => ({
      id: etapa.id,
      label: etapa.label ?? etapa.id,
      pesoDeDiseno: etapa.weight ?? 0,
    }));
}
