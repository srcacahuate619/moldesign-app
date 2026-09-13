import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACTIVITY_NOTIFICATION_EVENT,
  beginFileDownload,
  completeFileDownload,
  notifyRunFinished,
  type ActivityNotification,
} from "../activityNotifications";

describe("activityNotifications", () => {
  beforeEach(() => window.history.replaceState({}, "", "/science"));

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

  it("suprime el aviso si la corrida termina en su propia pestaña", () => {
    window.history.replaceState({}, "", "/evaluation/batch");
    const listener = vi.fn();
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);

    expect(notifyRunFinished({ source: "batch", runId: "run-1", successful: true })).toBe(false);
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
  });

  it("actualiza la misma entrada desde preparación hasta entrega al navegador", () => {
    const received: ActivityNotification[] = [];
    const listener = (event: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => received.push(event.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);

    const id = beginFileDownload("informe.pdf", "evaluation");
    completeFileDownload(id, "informe.pdf", "evaluation");

    expect(received.map((item) => item.id)).toEqual([id, id]);
    expect(received.map((item) => item.status)).toEqual(["in_progress", "success"]);
    expect(received[1].title).toBe("Descarga iniciada");
    window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, listener);
  });
});
