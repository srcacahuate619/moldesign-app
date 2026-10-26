import { afterEach, describe, expect, it, vi } from "vitest";
import { ACTIVITY_NOTIFICATION_EVENT, type ActivityNotification } from "../activityNotifications";
import { watchMolcyJobActivity } from "../molcyJobActivity";

// Frontera real del polling: la creación se confirmó, pero ningún listado llegó
// a observar al trabajo en estado activo antes de que terminara.
let stop: (() => void) | undefined;
afterEach(() => { stop?.(); vi.useRealTimers(); });
describe("Molcy: terminal de un trabajo recién creado y rápido", () => {
  it("conserva Actividad aunque no se alcanzara a observar el estado intermedio", async () => {
    vi.useFakeTimers(); window.localStorage.clear();
    const received: ActivityNotification[] = [];
    const receive = (event: Event) => received.push((event as CustomEvent<ActivityNotification>).detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
    const list = vi.fn().mockResolvedValueOnce({ trabajos: [] }).mockResolvedValue({ trabajos: [{ id: "job-fast", estado: "completo" }] });
    stop = watchMolcyJobActivity("owner-A", { list });
    try {
      await vi.advanceTimersByTimeAsync(0);
      window.dispatchEvent(new CustomEvent("moldesign:molcy-job-created", { detail: { ownerId: "owner-A", jobId: "job-fast" } }));
      await vi.advanceTimersByTimeAsync(0);
      expect(list).toHaveBeenCalledTimes(2);
      expect(received).toHaveLength(1);
      expect(received[0]).toMatchObject({ ownerId: "owner-A", jobId: "job-fast", source: "molcy", outcome: "completed", recovered: false });
      await vi.advanceTimersByTimeAsync(10000);
      expect(received).toHaveLength(1);
    } finally { window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive); }
  });
  it("la creación durante un listado en vuelo se comprueba de nuevo sin perder el terminal", async () => {
    vi.useFakeTimers(); window.localStorage.clear();
    const received: ActivityNotification[] = [];
    const receive = (event: Event) => received.push((event as CustomEvent<ActivityNotification>).detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
    let resolve!: (value: { trabajos: unknown[] }) => void;
    const initial = new Promise<{ trabajos: unknown[] }>(done => { resolve = done; });
    const list = vi.fn().mockReturnValueOnce(initial).mockResolvedValue({ trabajos: [{ id: "job-fast", estado: "completo" }] });
    stop = watchMolcyJobActivity("owner-A", { list });
    try {
      window.dispatchEvent(new CustomEvent("moldesign:molcy-job-created", { detail: { ownerId: "owner-A", jobId: "job-fast" } }));
      resolve({ trabajos: [] });
      await vi.advanceTimersByTimeAsync(1);
      expect(list).toHaveBeenCalledTimes(2);
      expect(received).toHaveLength(1);
      expect(received[0]).toMatchObject({ ownerId: "owner-A", jobId: "job-fast", outcome: "completed", recovered: false });
    } finally { window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive); }
  });

  it("una creación de otra cuenta no convierte un terminal histórico en aviso nuevo", async () => {
    vi.useFakeTimers(); window.localStorage.clear();
    const received: ActivityNotification[] = [];
    const receive = (event: Event) => received.push((event as CustomEvent<ActivityNotification>).detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, receive);
    const list = vi.fn().mockResolvedValue({ trabajos: [{ id: "job-ajeno", estado: "completo" }] });
    stop = watchMolcyJobActivity("owner-A", { list });
    try {
      await vi.advanceTimersByTimeAsync(0);
      window.dispatchEvent(new CustomEvent("moldesign:molcy-job-created", { detail: { ownerId: "owner-B", jobId: "job-ajeno" } }));
      await vi.advanceTimersByTimeAsync(0);
      expect(received).toHaveLength(0);
    } finally { window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, receive); }
  });

});
