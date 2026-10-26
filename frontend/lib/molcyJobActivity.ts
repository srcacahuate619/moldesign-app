import { trabajosMolcy, type MolcyJob } from "./molcy";
import { emitActivityNotification } from "./activityNotifications";

const MAX_JOBS = 256;
const active = (status: string) => status === "en_cola" || status === "renderizando";
export function watchMolcyJobActivity(ownerId: string, options: {
  list?: typeof trabajosMolcy;
  storage?: Pick<Storage,"getItem"|"setItem">;
  schedule?: typeof setTimeout;
  unschedule?: typeof clearTimeout;
} = {}): () => void {
  const list = options.list ?? trabajosMolcy;
  const schedule = options.schedule ?? setTimeout;
  const unschedule = options.unschedule ?? clearTimeout;
  let storage: Pick<Storage,"getItem"|"setItem"> | undefined = options.storage;
  try { storage ??= window.localStorage; } catch {}
  const key = `moldesign:molcy-terminal:v1:${ownerId}`;
  let states: Record<string,string> = {};
  try { const saved: unknown = JSON.parse(storage?.getItem(key) ?? "{}"); if (saved && typeof saved === "object" && !Array.isArray(saved)) states = Object.fromEntries(Object.entries(saved).filter((entry): entry is [string,string] => typeof entry[1] === "string")); } catch {}
  let initial = true;
  let disposed = false;
  let running = false;
  let refreshRequested = false;
  const acceptedThisSession = new Set<string>();
  const freshlyAccepted = new Set<string>();
  let timer: ReturnType<typeof setTimeout> | undefined;
  const tick = async () => {
    if (disposed || running) return;
    running = true;
    let hasActive = false;
    try {
      const response = await list();
      if (disposed) return;
      for (const job of response.trabajos) {
        const prior = states[job.id];
        hasActive ||= active(job.estado);
        if (prior && active(prior) && !active(job.estado)) {
          const cancelled = job.estado === "cancelado";
          const recovered = initial && !freshlyAccepted.has(job.id);
          emitActivityNotification({ id: `molcy-job:${job.id}`, source: "molcy", status: cancelled ? "info" : job.estado === "completo" ? "success" : "error", outcome: cancelled ? "cancelled" : job.estado === "completo" ? "completed" : "failed", ownerId, jobId: job.id, progress: null,
            recovered, silent: cancelled || recovered || window.location.pathname.replace(/\/$/, "") === "/molcy",
            titleKey: cancelled ? "nt_molcy_cancelled" : job.estado === "completo" ? "nt_molcy_ok" : "nt_molcy_failed", messageKey: cancelled ? "nt_corrida_cancelada_msg" : "nt_molcy_msg", href: "/molcy" });
        }
        if (!active(job.estado)) freshlyAccepted.delete(job.id);
        states[job.id] = job.estado;
      }
      states = Object.fromEntries(Object.entries(states).slice(-MAX_JOBS));
      try { storage?.setItem(key, JSON.stringify(states)); } catch {}
      initial = false;
    } catch { /* A failed poll is not a failed job. */ }
    finally { running = false; if (!disposed) { const delay = refreshRequested ? 0 : hasActive ? 3000 : 10000; refreshRequested = false; timer = schedule(tick, delay); } }
  };
  const created = (event: Event) => {
    const detail: unknown = (event as CustomEvent<unknown>).detail;
    if (!detail || typeof detail !== "object") return;
    const accepted = detail as { ownerId?: unknown; jobId?: unknown };
    if (accepted.ownerId !== ownerId || typeof accepted.jobId !== "string" || !accepted.jobId || accepted.jobId.length > 200 || acceptedThisSession.has(accepted.jobId)) return;
    acceptedThisSession.add(accepted.jobId); freshlyAccepted.add(accepted.jobId);
    // This tracks acceptance, not an invented backend status displayed to the user.
    states[accepted.jobId] = "en_cola";
    try { storage?.setItem(key, JSON.stringify(states)); } catch {}
    if (timer) unschedule(timer);
    if (running) refreshRequested = true; else void tick();
  };
  window.addEventListener("moldesign:molcy-job-created", created);
  void tick();
  return () => { disposed = true; if (timer) unschedule(timer); window.removeEventListener("moldesign:molcy-job-created",created); };
}
