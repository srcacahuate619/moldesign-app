import { ACTIVITY_NOTIFICATION_EVENT } from "./activityNotifications";
import { invoke, isDesktopRuntime } from "./tauri";

export type NativeJobSource = "evaluation" | "batch" | "molcy";
export interface NativeJobDestination {
  readonly ownerId: string;
  readonly source: NativeJobSource;
  readonly caseId?: string;
  readonly taskId?: string;
  readonly jobId?: string;
}
export interface NativeJobEvent extends NativeJobDestination {
  readonly id: string;
  readonly outcome: "completed" | "failed" | "cancelled";
  readonly withExceptions?: boolean;
  /** Un terminal histórico recuperado se conserva en Actividad, nunca se anuncia de nuevo. */
  readonly recovered?: boolean;
}
export interface NativeAttention {
  readonly focused: boolean;
  readonly visible: boolean;
  readonly minimized: boolean;
}
export type NativeDecision = "requested" | "duplicate" | "cancelled" | "historical" | "wrong-owner"
  | "missing-identity" | "origin-active" | "attention-unknown" | "permission-denied"
  | "unavailable" | "request-error" | "storage-unavailable";
export interface NativeJobBridge {
  listenAction(callback: (token: string) => void): Promise<() => void>;
  permissionGranted(): Promise<boolean>;
  attention(): Promise<NativeAttention>;
  send(notification: { id: number; token: string; body: string }): Promise<void>;
  restore(): Promise<void>;
}
export interface NativeJobOptions {
  getOwnerId(): string | null;
  translate(key: string): string;
  /** Valida acceso y abre la identidad exacta. false expresa que no fue resoluble. Nunca ejecuta. */
  openDestination(destination: NativeJobDestination): Promise<boolean>;
  onDecision?(eventId: string, decision: NativeDecision): void;
  onOpenFailure?(destination: NativeJobDestination): void;
  /** Inyección de fronteras para pruebas; producción usa Tauri y localStorage propios. */
  bridge?: NativeJobBridge;
  storage?: Pick<Storage, "getItem" | "setItem">;
  pathname?: () => string;
}
const STORAGE_PREFIX = "moldesign:native-job-decisions:v1:";
const MAX_DECISIONS = 2048;

function origin(path: string): NativeJobSource | "other" | null {
  if (!path.startsWith("/") || path.startsWith("//")) return null;
  if (path === "/evaluation/batch" || path.startsWith("/evaluation/batch/")) return "batch";
  if (path === "/evaluation" || path.startsWith("/evaluation/")) return "evaluation";
  if (path === "/molcy" || path.startsWith("/molcy/")) return "molcy";
  return "other";
}
function eventFrom(input: unknown): NativeJobEvent | null {
  if (!input || typeof input !== "object") return null;
  const event = input as Record<string, unknown>;
  if (!(["evaluation", "batch", "molcy"] as unknown[]).includes(event.source)) return null;
  if (!(event.outcome === "completed" || event.outcome === "failed" || event.outcome === "cancelled")) return null;
  if (typeof event.id !== "string" || typeof event.ownerId !== "string") return null;
  return event as unknown as NativeJobEvent;
}
function destinationOf(event: NativeJobEvent): NativeJobDestination | null {
  const valid = (id: unknown): id is string => typeof id === "string" && id.length > 0 && id.length <= 200;
  if (!valid(event.ownerId)) return null;
  if (event.source === "evaluation") return valid(event.caseId) && valid(event.taskId)
    ? { ownerId: event.ownerId, source: event.source, caseId: event.caseId, taskId: event.taskId } : null;
  return valid(event.jobId) ? { ownerId: event.ownerId, source: event.source, jobId: event.jobId } : null;
}

/**
 * Decide una vez por propietario/trabajo/transición, sin colas diferidas.
 * Persistir ANTES de solicitar favorece no duplicar tras crash; puede perder un banner si
 * el proceso termina entre ambos pasos. El acuse del plugin no acredita recepción del SO.
 */
export function createNativeJobDispatcher(options: NativeJobOptions, bridge: NativeJobBridge) {
  let ready = false;
  let disposed = false;
  let nextId = 1;
  const destinations = new Map<string, NativeJobDestination>();
  const storage = options.storage ?? {
    getItem: (key: string) => window.localStorage.getItem(key),
    setItem: (key: string, value: string) => window.localStorage.setItem(key, value),
  };
  const pathname = options.pathname ?? (() => window.location.pathname);
  const report = (id: string, decision: NativeDecision) => { options.onDecision?.(id, decision); return decision; };
  const handle = async (input: unknown): Promise<NativeDecision | null> => {
    const event = eventFrom(input);
    if (!event || disposed) return null;
    if (event.ownerId !== options.getOwnerId()) return report(event.id, "wrong-owner");
    const destination = destinationOf(event);
    if (!destination) return report(event.id, "missing-identity");
    const identity = destination.taskId ?? destination.jobId;
    const key = `${destination.source}:${destination.caseId ?? ""}:${identity}:${event.outcome}`;
    try {
      const stored = JSON.parse(storage.getItem(STORAGE_PREFIX + event.ownerId) ?? "[]");
      if (!Array.isArray(stored)) return report(event.id, "storage-unavailable");
      if (stored.includes(key)) return report(event.id, "duplicate");
      storage.setItem(STORAGE_PREFIX + event.ownerId, JSON.stringify([...stored.slice(-(MAX_DECISIONS - 1)), key]));
    } catch { return report(event.id, "storage-unavailable"); }
    if (event.outcome === "cancelled") return report(event.id, "cancelled");
    if (event.recovered) return report(event.id, "historical");
    if (!ready) return report(event.id, "unavailable");
    try {
      if (!(await bridge.permissionGranted())) return report(event.id, "permission-denied");
      let attention: NativeAttention;
      try { attention = await bridge.attention(); }
      catch { return report(event.id, "attention-unknown"); }
      if (disposed || options.getOwnerId() !== event.ownerId) return report(event.id, "wrong-owner");
      const current = origin(pathname());
      if (current === null || [attention.focused, attention.visible, attention.minimized].some(value => typeof value !== "boolean")) {
        return report(event.id, "attention-unknown");
      }
      if (attention.focused && attention.visible && !attention.minimized && current === event.source) {
        return report(event.id, "origin-active");
      }
      // El único dato del trabajo que viaja al SO es un token opaco de esta sesión.
      const token = crypto.randomUUID();
      if (destinations.size >= MAX_DECISIONS) destinations.delete(destinations.keys().next().value!);
      destinations.set(token, destination);
      const bodyKey = event.outcome === "failed" ? "nt_native_failed" : event.withExceptions ? "nt_native_exceptions" : "nt_native_completed";
      await bridge.send({ id: nextId++, token, body: options.translate(bodyKey) });
      return report(event.id, "requested");
    } catch { return report(event.id, "request-error"); }
  };
  return {
    handle,
    async start() {
      const remove = await bridge.listenAction(token => {
        const destination = destinations.get(token);
        if (!destination || disposed || options.getOwnerId() !== destination.ownerId) return;
        // Sólo una activación por token; no se confía en destinos recibidos del SO.
        destinations.delete(token);
        void (async () => {
          try {
            await bridge.restore();
            if (disposed || options.getOwnerId() !== destination.ownerId) return;
            if (!(await options.openDestination(destination))) options.onOpenFailure?.(destination);
          } catch { options.onOpenFailure?.(destination); }
        })();
      });
      ready = true;
      return () => { disposed = true; ready = false; destinations.clear(); remove(); };
    },
  };
}

export async function createTauriNativeJobBridge(): Promise<NativeJobBridge> {
  const { onAction } = await import("@tauri-apps/plugin-notification");
  return {
    listenAction: async callback => {
      const listener = await onAction(event => {
        const token = event.notification?.extra?.jobToken;
        if (event.actionId === "tap" && typeof token === "string") callback(token);
      });
      return () => { void listener.unregister().catch(() => {}); };
    },
    permissionGranted: () => invoke<boolean>("plugin:notification|is_permission_granted"),
    attention: () => invoke<NativeAttention>("job_notification_attention"),
    send: notification => invoke<void>("job_notification_send", notification),
    restore: () => invoke<void>("job_notification_restore"),
  };
}

/** Montar una sola vez. La aplicación web conserva únicamente su Actividad interna. */
export async function startNativeJobNotifications(options: NativeJobOptions): Promise<() => void> {
  if (!options.bridge && !isDesktopRuntime()) return () => {};
  const bridge = options.bridge ?? await createTauriNativeJobBridge();
  const dispatcher = createNativeJobDispatcher(options, bridge);
  const receive = (event: Event) => { void dispatcher.handle((event as CustomEvent<unknown>).detail); };
  window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
  try {
    const stop = await dispatcher.start();
    return () => { window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive); stop(); };
  } catch {
    window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
    return () => {};
  }
}


type DestinationResolver = (destination: NativeJobDestination) => Promise<boolean>;
const destinationResolvers = new Map<NativeJobSource, DestinationResolver>();
const resolverWaiters = new Map<NativeJobSource, Set<(resolver: DestinationResolver) => void>>();
/** Lo registra el workspace capaz de verificar la identidad y seleccionar sin ejecutar. */
export function registerNativeJobDestinationResolver(source: NativeJobSource, resolver: DestinationResolver): () => void {
  destinationResolvers.set(source, resolver);
  resolverWaiters.get(source)?.forEach(ready => ready(resolver));
  return () => { if (destinationResolvers.get(source) === resolver) destinationResolvers.delete(source); };
}
/**
 * Se usa sólo por un clic de la persona: esperar al montaje no difiere una notificación.
 * Navegar a la sección no acredita abrir el trabajo; el resolver debe confirmarlo.
 */
export async function openNativeJobDestination(destination: NativeJobDestination, options: {
  getOwnerId(): string | null;
  navigate(path: string): void;
  timeoutMs?: number;
}): Promise<boolean> {
  if (options.getOwnerId() !== destination.ownerId || !destinationOf({ ...destination, id: "click", outcome: "completed" })) return false;
  const path = destination.source === "evaluation" ? "/evaluation" : destination.source === "batch" ? "/evaluation/batch" : "/molcy";
  options.navigate(path);
  let resolver = destinationResolvers.get(destination.source);
  if (!resolver) {
    const found = await new Promise<DestinationResolver | null>(resolve => {
      const pending = resolverWaiters.get(destination.source) ?? new Set();
      const ready = (value: DestinationResolver) => { clearTimeout(timer); pending.delete(ready); resolve(value); };
      const timer = setTimeout(() => { pending.delete(ready); resolve(null); }, options.timeoutMs ?? 10000);
      pending.add(ready); resolverWaiters.set(destination.source, pending);
      // La suscripción y la segunda lectura cierran el hueco entre ambos pasos.
      const available = destinationResolvers.get(destination.source);
      if (available) ready(available);
    });
    if (!found) return false;
    resolver = found;
  }
  if (options.getOwnerId() !== destination.ownerId) return false;
  try { return Boolean(await resolver(destination)) && options.getOwnerId() === destination.ownerId; }
  catch { return false; }
}
