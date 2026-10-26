import { isDesktopRuntime, listen } from "./tauri";

export const ACTIVITY_NOTIFICATION_EVENT = "moldesign:activity";
export const ACTIVITY_DISMISS_EVENT = "moldesign:activity-dismiss";

export type ActivitySource = "evaluation" | "batch" | "molcy" | "models" | "general";
/** `info`: información sin veredicto de éxito/error, incluida una cancelación. */
export type ActivityStatus = "in_progress" | "success" | "error" | "info";

export interface ActivityNotification {
  readonly id: string;
  readonly source: ActivitySource;
  readonly status: ActivityStatus;
  /** Conserva la entrada sin abrir un aviso transitorio ni hacer sonar la campana. */
  readonly silent?: boolean;
  readonly outcome?: "completed" | "failed" | "cancelled";
  readonly ownerId?: string;
  readonly taskId?: string;
  readonly jobId?: string;
  readonly withExceptions?: boolean;
  /** Terminal recuperado: se conserva en Actividad y se omite el aviso del sistema. */
  readonly recovered?: boolean;
  readonly caseId?: string;
  /** Texto ya escrito: los avisos guardados antes de las claves. Los nuevos usan `titleKey`. */
  readonly title?: string;
  readonly message?: string;
  /** Claves del diccionario: el aviso se lee en el idioma de la interfaz al pintarlo, no al guardarlo. */
  readonly titleKey?: string;
  readonly messageKey?: string;
  readonly params?: Readonly<Record<string, string | number>>;
  /** Módulo descargable al que se refiere: su nombre y su barra se leen en vivo del gestor de descargas. */
  readonly moduleId?: string;
  readonly progress: number | null;
  readonly href?: string;
  /** Identificador nativo de un archivo cuya escritura ya terminó. */
  readonly fileId?: string;
  readonly createdAt: string;
  readonly read: boolean;
}

export type ActivityInput = Omit<ActivityNotification, "createdAt" | "read"> & {
  readonly suppressOnPath?: string;
};

export interface ActivityDismissal {
  readonly id: string;
  /** Si viene, sólo se retira el aviso que esté en ese estado. */
  readonly soloSi?: ActivityStatus;
}

function currentPath(): string {
  return typeof window === "undefined" ? "" : window.location.pathname;
}

/** Conserva actividad global; la ruta sólo suprime su presentación transitoria. */
export function emitActivityNotification(input: ActivityInput): boolean {
  if (typeof window === "undefined") return false;
  const silent = input.silent ?? Boolean(input.suppressOnPath && currentPath() === input.suppressOnPath);
  const { suppressOnPath: _suppressed, ...notification } = input;
  window.dispatchEvent(new CustomEvent<ActivityNotification>(ACTIVITY_NOTIFICATION_EVENT, {
    detail: { ...notification, silent, createdAt: new Date().toISOString(), read: false },
  }));
  return true;
}

/** Retira un aviso de la campana (p. ej. la descarga que el usuario canceló). */
export function dismissActivityNotification(id: string, soloSi?: ActivityStatus): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<ActivityDismissal>(ACTIVITY_DISMISS_EVENT, { detail: { id, soloSi } }));
}

function uniqueId(prefix: string): string {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}:${random}`;
}

/** Los avisos antiguos no guardaban destino; conserva al menos su sección de origen. */
export function activityHref(item: Pick<ActivityNotification, "href" | "source" | "message" | "moduleId">): string {
  if (item.href?.startsWith("/") && !item.href.startsWith("//")) return item.href;
  if (item.message?.startsWith("molcy_")) return "/molcy";
  if (item.source === "molcy") return "/molcy";
  if (item.source === "batch") return "/evaluation/batch";
  if (item.source === "evaluation") return "/evaluation";
  if (item.source === "models" || item.moduleId) return "/launcher";
  return "/moldex";
}

type FileDownloadContext = { filename: string; source: ActivitySource; href: string };
// Las URLs de acceso sólo viven en memoria, nunca en el historial persistido.
const fileDownloads = new Map<string, FileDownloadContext>();
const pendingUrls = new Map<string, string[]>();

export function beginFileDownload(filename: string, source: ActivitySource = "general"): string {
  const id = uniqueId(`download:${source}`);
  const href = currentPath() || activityHref({ source, message: filename });
  fileDownloads.set(id, { filename, source, href });
  emitActivityNotification({
    id,
    source,
    status: "in_progress",
    titleKey: "nt_archivo_preparando",
    message: filename,
    progress: null,
    href,
  });
  return id;
}

/** Se llama ANTES del clic, para no perder el evento de un archivo pequeño. */
export function handoffFileDownload(id: string, filename: string, url: string, source: ActivitySource = "general"): void {
  const href = fileDownloads.get(id)?.href ?? activityHref({ source, message: filename });
  const desktop = isDesktopRuntime();
  if (desktop) {
    fileDownloads.set(id, { filename, source, href });
    pendingUrls.set(url, [...(pendingUrls.get(url) ?? []), id]);
  } else {
    fileDownloads.delete(id);
  }
  emitActivityNotification({
    id, source, href, message: filename, progress: null,
    status: desktop ? "in_progress" : "info",
    titleKey: desktop ? "nt_archivo_descargando" : "nt_archivo_iniciada",
  });
}

/** Sólo el contenedor nativo puede confirmar que el archivo terminó de guardarse. */
export async function listenForFileDownloads(): Promise<() => void> {
  return listen("file-download:finished", ({ payload }) => {
    if (!payload || typeof payload !== "object") return;
    const data = payload as { url?: unknown; success?: unknown; fileId?: unknown };
    if (typeof data.url !== "string" || typeof data.success !== "boolean") return;
    const queue = pendingUrls.get(data.url);
    const id = queue?.shift();
    if (!queue?.length) pendingUrls.delete(data.url);
    if (!id) return;
    const context = fileDownloads.get(id);
    if (!context) return;
    if (data.success) completeFileDownload(id, context.filename, context.source,
      typeof data.fileId === "string" ? data.fileId : undefined);
    else failFileDownload(id, context.filename, context.source);
  });
}

export function completeFileDownload(id: string, filename: string, source: ActivitySource = "general", fileId?: string): void {
  const href = fileDownloads.get(id)?.href ?? activityHref({ source, message: filename });
  fileDownloads.delete(id);
  emitActivityNotification({
    id,
    source,
    status: "success",
    titleKey: "nt_archivo_completada",
    message: filename,
    // Terminada no lleva barra: el 100 % se leía como «sigue descargando».
    progress: null,
    href,
    fileId,
  });
}

export function failFileDownload(id: string, filename: string, source: ActivitySource = "general"): void {
  const href = fileDownloads.get(id)?.href ?? activityHref({ source, message: filename });
  fileDownloads.delete(id);
  for (const [url, queue] of pendingUrls) {
    const remaining = queue.filter(value => value !== id);
    if (remaining.length) pendingUrls.set(url, remaining);
    else pendingUrls.delete(url);
  }
  emitActivityNotification({
    id,
    source,
    status: "error",
    titleKey: "nt_archivo_fallo",
    message: filename,
    progress: null,
    href,
  });
}

export function notifyRunFinished(options: {
  source: "evaluation" | "batch";
  runId: string;
  successful: boolean;
  outcome?: "completed" | "failed" | "cancelled";
  ownerId?: string;
  jobId?: string;
  taskId?: string;
  caseId?: string;
  withExceptions?: boolean;
}): boolean {
  const isBatch = options.source === "batch";
  const href = isBatch ? "/evaluation/batch" : "/evaluation";
  const outcome = options.outcome ?? (options.successful ? "completed" : "failed");
  const cancelled = outcome === "cancelled";
  const titleKey = `nt_corrida_${isBatch ? "batch" : "eval"}_${cancelled ? "cancelada" : outcome === "completed" ? "ok" : "fallo"}`;
  const messageKey = cancelled ? "nt_corrida_cancelada_msg"
    : outcome === "completed"
      ? options.withExceptions ? "nt_corrida_excepciones_msg" : "nt_corrida_ok_msg"
      : "nt_corrida_fallo_msg";

  return emitActivityNotification({
    id: `run:${options.source}:${options.runId}`,
    source: options.source,
    status: cancelled ? "info" : outcome === "completed" ? "success" : "error",
    outcome,
    ...(options.ownerId ? { ownerId: options.ownerId } : {}),
    ...(options.jobId ? { jobId: options.jobId } : {}),
    ...(options.taskId ? { taskId: options.taskId } : {}),
    ...(options.caseId ? { caseId: options.caseId } : {}),
    ...(options.withExceptions ? { withExceptions: true } : {}),
    ...(cancelled ? { silent: true } : {}),
    titleKey,
    messageKey,
    progress: null,
    href,
    suppressOnPath: href,
  });
}

declare global {
  interface WindowEventMap {
    "moldesign:activity": CustomEvent<ActivityNotification>;
    "moldesign:activity-dismiss": CustomEvent<ActivityDismissal>;
  }
}
