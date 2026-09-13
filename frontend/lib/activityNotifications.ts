export const ACTIVITY_NOTIFICATION_EVENT = "moldesign:activity";

export type ActivitySource = "evaluation" | "batch" | "models" | "general";
export type ActivityStatus = "in_progress" | "success" | "error";

export interface ActivityNotification {
  readonly id: string;
  readonly source: ActivitySource;
  readonly status: ActivityStatus;
  readonly title: string;
  readonly message: string;
  readonly progress: number | null;
  readonly href?: string;
  readonly createdAt: string;
  readonly read: boolean;
}

type ActivityInput = Omit<ActivityNotification, "createdAt" | "read"> & {
  readonly suppressOnPath?: string;
};

function currentPath(): string {
  return typeof window === "undefined" ? "" : window.location.pathname;
}

/** Publica actividad global. Devuelve false cuando la ruta visible la suprime. */
export function emitActivityNotification(input: ActivityInput): boolean {
  if (typeof window === "undefined") return false;
  if (input.suppressOnPath && currentPath() === input.suppressOnPath) return false;
  const { suppressOnPath: _suppressed, ...notification } = input;
  window.dispatchEvent(new CustomEvent<ActivityNotification>(ACTIVITY_NOTIFICATION_EVENT, {
    detail: { ...notification, createdAt: new Date().toISOString(), read: false },
  }));
  return true;
}

function uniqueId(prefix: string): string {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}:${random}`;
}

export function beginFileDownload(filename: string, source: ActivitySource = "general"): string {
  const id = uniqueId(`download:${source}`);
  emitActivityNotification({
    id,
    source,
    status: "in_progress",
    title: "Preparando descarga",
    message: filename,
    progress: null,
  });
  return id;
}

export function completeFileDownload(id: string, filename: string, source: ActivitySource = "general"): void {
  emitActivityNotification({
    id,
    source,
    status: "success",
    title: "Descarga iniciada",
    message: `${filename} fue entregado al navegador.`,
    progress: 100,
  });
}

export function failFileDownload(id: string, filename: string, source: ActivitySource = "general"): void {
  emitActivityNotification({
    id,
    source,
    status: "error",
    title: "La descarga no pudo iniciarse",
    message: filename,
    progress: null,
  });
}

export function notifyRunFinished(options: {
  source: "evaluation" | "batch";
  runId: string;
  successful: boolean;
  withExceptions?: boolean;
}): boolean {
  const isBatch = options.source === "batch";
  const href = isBatch ? "/evaluation/batch" : "/evaluation";
  const title = options.successful
    ? isBatch ? "Batch terminado" : "Evaluación terminada"
    : isBatch ? "Batch sin resultados utilizables" : "La evaluación no terminó correctamente";
  const message = options.successful
    ? options.withExceptions
      ? "La cohorte terminó con excepciones. Revisa la cobertura y las filas no evaluadas."
      : "Los resultados ya están disponibles."
    : "Abre la corrida para revisar el estado y el diagnóstico.";

  return emitActivityNotification({
    id: `run:${options.source}:${options.runId}`,
    source: options.source,
    status: options.successful ? "success" : "error",
    title,
    message,
    progress: options.successful ? 100 : null,
    href,
    suppressOnPath: href,
  });
}

declare global {
  interface WindowEventMap {
    "moldesign:activity": CustomEvent<ActivityNotification>;
  }
}
