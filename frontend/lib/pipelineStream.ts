import { getApiUrl } from "./config";
import { getAuthHeaders } from "./api";

export interface PipelineEvent {
  type:
    | "pipeline_started"
    | "stage_start"
    | "stage_progress"
    | "stage_done"
    | "stage_error"
    | "stage_skipped"
    | "pipeline_done"
    | "pipeline_error";
  stage_id?: string;
  timestamp: string;
  label?: string;
  duration_ms?: number;
  error?: string;
  reason?: string;
  /** Sólo en `stage_progress`: unidades de trabajo terminadas y totales. */
  done?: number;
  total?: number;
}

// ── Mapeo stage_id SSE (backend registry.py) → orb id del DOT/timeline ──
// validation→Curación, properties→Propiedades (/ ADMET), conformer→3D ETKDG,
// docking→Vina, xgb→XGBoost, clgnn→CL-GNN, openmm→OpenMM, mmgbsa→MM-GBSA
// (post-hoc). sa_filter no tiene orb (filtro, alimenta Parámetros);
// selectivity es canónica pero se muestra en el panel Safety post-hoc, no en
// el grafo de orbs.
//
// `properties` SÍ tiene orb, y no es cosmético. Esa etapa es donde corre
// ADMET-AI (`runner.py`, rama `stage_id == "properties"`), que en su primera
// carga se lleva la mayor parte del reloj de la corrida —en una VM, minutos—.
// Sin orb propio, ese tiempo transcurría con la línea temporal parada entre
// Curación y «3D ETKDG», y quien miraba se lo apuntaba al conformero, que en
// realidad ya se había generado en paralelo dentro de esta misma etapa. Un
// modelo que tarda no puede facturarle el tiempo a otra cosa.
export const SSE_TO_ORB: Record<string, string> = {
  validation: "validation",
  properties: "properties",
  conformer: "conformer",
  docking: "vina",
  xgb: "xgb",
  clgnn: "clgnn",
  openmm: "openmm",
  mmgbsa: "mmgbsa",
};

// Etapas conocidas que deliberadamente no modifican el DOT. Mantener este
// contrato explícito distingue un evento válido sin orb de un stage desconocido
// y documenta que selectivity se consume desde el Safety Panel post-hoc.
export const NON_ORB_STAGE_IDS = ["sa_filter", "selectivity"] as const;

export type OrbState = "running" | "done" | "error" | "skipped";

export interface OrbUpdate {
  orb: string;
  state: OrbState;
  /** Solo para stage_error (error) y stage_skipped (reason). */
  message?: string;
  /**
   * Avance REAL de la etapa, cuando la etapa sabe contarlo.
   *
   * Hoy sólo el ensemble conformacional: con K alto el docking pasa de
   * instantáneo a minutos, y un orbe en «running» sin más parece congelado.
   * Son unidades CONTADAS —conformaciones acopladas de K—, no una animación
   * que finja saber cuánto falta.
   */
  progress?: { readonly done: number; readonly total: number };
}

// Traduce un evento de etapa SSE a la actualización del orb correspondiente.
// Devuelve null para stages sin orb (sa_filter, selectivity, stage_id
// desconocidos) y para eventos no relacionados con etapas (pipeline_*),
// que el consumidor maneja aparte. Stage desconocido → null (degradación
// suave: el DOT ignora eventos que no sabe mapear, no crashea).
export function stageEventToOrbUpdate(event: PipelineEvent): OrbUpdate | null {
  const orb = SSE_TO_ORB[event.stage_id ?? ""];
  if (!orb) return null;
  switch (event.type) {
    case "stage_start":
      return { orb, state: "running" };
    case "stage_progress": {
      // Un progreso sin cifras utilizables no se publica: mejor «running» a
      // secas que una barra que no corresponde a nada.
      const done = event.done;
      const total = event.total;
      if (typeof done !== "number" || typeof total !== "number" || total <= 0) {
        return { orb, state: "running" };
      }
      return {
        orb,
        state: "running",
        progress: { done: Math.min(Math.max(done, 0), total), total },
      };
    }
    case "stage_done":
      return { orb, state: "done" };
    case "stage_error":
      return { orb, state: "error", message: event.error ?? "Error en la etapa" };
    case "stage_skipped":
      return { orb, state: "skipped", message: event.reason ?? "no se calculó" };
    default:
      return null;
  }
}

/**
 * Abre el stream SSE de una corrida.
 *
 * ES ASÍNCRONA porque la dirección del backend lo es: en escritorio el puerto
 * lo elige Rust y preguntarlo es una operación, no una constante. Devolver el
 * `unsubscribe` en una promesa es el precio de no cablear 8000 aquí dentro; el
 * llamador guarda la promesa y cierra cuando resuelve.
 */
export async function subscribeToPipelineEvents(
  taskId: string,
  onEvent: (event: PipelineEvent) => void,
  onClose: () => void
): Promise<() => void> {
  // EventSource no permite enviar Authorization. Las evaluaciones de una
  // cuenta autenticada se abrían por tanto como "demo" y el backend respondía
  // 403 al comparar el propietario de la tarea. Consumimos SSE sobre fetch para
  // reutilizar exactamente la misma cabecera Bearer que el resto de la API.
  const controller = new AbortController();
  const url = `${await getApiUrl()}/evaluation/stream/${encodeURIComponent(taskId)}`;
  let closeNotified = false;
  const notifyClose = () => {
    if (closeNotified) return;
    closeNotified = true;
    onClose();
  };

  void (async () => {
    try {
      const response = await fetch(url, {
        headers: { Accept: "text/event-stream", ...getAuthHeaders() },
        cache: "no-store",
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      if (!response.body) throw new Error("El stream SSE no tiene cuerpo legible");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let terminal = false;

      while (!terminal) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const frames = buffer.split(/\r?\n\r?\n/);
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const payload = frame
            .split(/\r?\n/)
            .filter((line) => line.startsWith("data:"))
            .map((line) => line.slice(5).trimStart())
            .join("\n");
          if (!payload) continue;
          try {
            const event = JSON.parse(payload) as PipelineEvent;
            onEvent(event);
            if (event.type === "pipeline_done" || event.type === "pipeline_error") {
              terminal = true;
              notifyClose();
              break;
            }
          } catch (error) {
            console.error("Failed to parse pipeline event", error);
          }
        }

        if (done) break;
      }
      if (!controller.signal.aborted) notifyClose();
    } catch (error) {
      if (controller.signal.aborted) return;
      console.error("SSE fetch failed", error);
      notifyClose();
    }
  })();

  return () => controller.abort();
}
