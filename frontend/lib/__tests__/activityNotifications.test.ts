import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACTIVITY_NOTIFICATION_EVENT,
  beginFileDownload,
  completeFileDownload,
  handoffFileDownload,
  listenForFileDownloads,
  activityHref,
  failFileDownload,
  notifyRunFinished,
  type ActivityNotification,
} from "../activityNotifications";

const bridge = vi.hoisted(() => ({ isDesktopRuntime: vi.fn(() => false), listen: vi.fn() }));
vi.mock("../tauri", () => bridge);

describe("activityNotifications", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/science");
    bridge.isDesktopRuntime.mockReturnValue(false);
    bridge.listen.mockReset().mockResolvedValue(vi.fn());
  });

  it("notifica una evaluación terminada si el usuario está en otra pestaña", () => {
    const received: ActivityNotification[] = [];
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, (event) => received.push(event.detail), { once: true });

    expect(notifyRunFinished({ source: "evaluation", runId: "task-7", successful: true })).toBe(true);
    expect(received[0]).toMatchObject({
      id: "run:evaluation:task-7",
      href: "/evaluation",
      status: "success",
      read: false,
    });
  });

  it("conserva actividad silenciosa si la corrida termina en su propia pestaña", () => {
    window.history.replaceState({}, "", "/evaluation/batch");
    const listener = vi.fn();
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);

    expect(notifyRunFinished({ source: "batch", runId: "run-1", successful: true })).toBe(true);
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0].detail).toMatchObject({
      id: "run:batch:run-1", status: "success", outcome: "completed", silent: true,
    });
    window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
  });

  it("conserva la cancelación voluntaria como información silenciosa, con identidad", () => {
    const received: ActivityNotification[] = [];
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, (event) => received.push(event.detail), { once: true });
    notifyRunFinished({ source: "evaluation", runId: "task-cancelled", successful: false,
      outcome: "cancelled", taskId: "task-cancelled", caseId: "case-A", ownerId: "owner-A" });
    expect(received[0]).toMatchObject({
      status: "info", outcome: "cancelled", silent: true,
      titleKey: "nt_corrida_eval_cancelada", messageKey: "nt_corrida_cancelada_msg",
      taskId: "task-cancelled", caseId: "case-A", ownerId: "owner-A",
    });
  });

  it("actualiza la misma entrada desde preparación hasta finalización confirmada", () => {
    const received: ActivityNotification[] = [];
    const listener = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => received.push(event.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);

    const id = beginFileDownload("informe.pdf", "evaluation");
    completeFileDownload(id, "informe.pdf", "evaluation");

    expect(received.map((item) => item.id)).toEqual([id, id]);
    expect(received.map((item) => item.status)).toEqual(["in_progress", "success"]);
    // Con su clave: se lee en el idioma de la interfaz al pintarse, no al guardarse.
    expect(received[1].titleKey).toBe("nt_archivo_completada");
    expect(received[1].message).toBe("informe.pdf");
    // Terminada no lleva barra.
    expect(received[1].progress).toBeNull();
    window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
  });

  it("espera la escritura nativa, conserva el origen y permite mostrar el archivo", async () => {
    bridge.isDesktopRuntime.mockReturnValue(true);
    const received: ActivityNotification[] = [];
    const listener = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => received.push(event.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
    const cleanup = await listenForFileDownloads();
    try {
      window.history.replaceState({}, "", "/molcy");
      const id = beginFileDownload("molcy_1.mp4");
      window.history.replaceState({}, "", "/science");
      handoffFileDownload(id, "molcy_1.mp4", "blob:video-1");
      expect(received.at(-1)).toMatchObject({ status: "in_progress", titleKey: "nt_archivo_descargando", href: "/molcy" });
      const receive = bridge.listen.mock.calls[0][1];
      receive({ payload: { url: "blob:unrelated", success: true } });
      expect(received).toHaveLength(2);
      receive({ payload: { url: "blob:video-1", success: true, fileId: "native-file-1" } });
      expect(received.at(-1)).toMatchObject({ id, status: "success", titleKey: "nt_archivo_completada", href: "/molcy", fileId: "native-file-1" });
      // El evento nativo duplicado no crea otra entrada.
      receive({ payload: { url: "blob:video-1", success: true } });
      expect(received).toHaveLength(3);
    } finally { cleanup(); window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener); }
  });

  it("una descarga interrumpida por el navegador termina en error", async () => {
    bridge.isDesktopRuntime.mockReturnValue(true);
    const received: ActivityNotification[] = [];
    const listener = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => received.push(event.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
    const cleanup = await listenForFileDownloads();
    try {
      const id = beginFileDownload("informe.zip", "evaluation");
      handoffFileDownload(id, "informe.zip", "blob:zip-1", "evaluation");
      bridge.listen.mock.calls[0][1]({ payload: { url: "blob:zip-1", success: false } });
      expect(received.at(-1)).toMatchObject({ id, status: "error", titleKey: "nt_archivo_fallo" });
    } finally { cleanup(); window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener); }
  });

  it("el navegador web no afirma que ya guardó un archivo", () => {
    const received: ActivityNotification[] = [];
    const listener = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => received.push(event.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
    try {
      const id = beginFileDownload("informe.pdf");
      handoffFileDownload(id, "informe.pdf", "blob:pdf-1");
      expect(received.at(-1)).toMatchObject({ status: "info", titleKey: "nt_archivo_iniciada" });
      failFileDownload(id, "informe.pdf");
    } finally { window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener); }
  });

  it("los avisos anteriores sin enlace recuperan su sección", () => {
    expect(activityHref({ source: "general", message: "molcy_1.mp4" })).toBe("/molcy");
    expect(activityHref({ source: "batch" })).toBe("/evaluation/batch");
    expect(activityHref({ source: "molcy" })).toBe("/molcy");
    expect(activityHref({ source: "evaluation" })).toBe("/evaluation");
    expect(activityHref({ source: "models", href: "//external.example" })).toBe("/launcher");
  });
});
