/** Apply the same UI gate before asking the real evaluation button to run. */
/** Un bloqueo de pantalla (caso cargando, botón aún deshabilitado) se espera; el resto se responde ya. */
export function debeEsperarLaPantalla(blocked: string | null, transcurridoMs: number, limiteMs: number): boolean {
  return (blocked === "blocked" || blocked === "busy") && transcurridoMs < limiteMs;
}

type Traductor = (clave: string) => string;

export function motivoDeBloqueoDesdeChat(
  state: { busy: boolean; buttonDisabled: boolean; running: boolean }, t: Traductor,
): string {
  if (state.running) return t("ev_chat_motivo_en_marcha");
  if (state.buttonDisabled) return t("ev_chat_motivo_deshabilitado");
  return t("ev_chat_motivo_ocupada");
}

export function bloqueoDeEvaluacionDesdeChat(state: {
  expired: boolean; reviewing: boolean; exampleLigand: boolean; canRun: boolean;
  runBlocked: boolean; antiNeedsReview: boolean; hasButton: boolean; busy: boolean;
}): "unknown" | "needs_review" | "blocked" | "busy" | null {
  if (state.expired) return "unknown";
  if (state.reviewing) return "needs_review";
  if (state.exampleLigand || !state.canRun || state.runBlocked || state.antiNeedsReview || !state.hasButton) return "blocked";
  if (state.busy) return "busy";
  return null;
}

/** Última etapa alcanzada por cada petición de evaluación del chat: si vence el plazo, se dice dónde se quedó. */
const etapas = new Map<string, string>();
export function marcarEtapaDeEvaluacionChat(requestId: string, etapa: string): void {
  etapas.delete(requestId);
  etapas.set(requestId, etapa);
  if (etapas.size > 20) etapas.delete(etapas.keys().next().value as string);
}
export function etapaDeEvaluacionChat(requestId: string, t: Traductor): string {
  return etapas.get(requestId) ?? t("ev_chat_sin_etapa");
}
