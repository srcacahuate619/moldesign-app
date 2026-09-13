import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ACTIVITY_NOTIFICATION_EVENT, type ActivityNotification } from "@/lib/activityNotifications";
import { DownloadNotifications } from "../DownloadNotifications";

const downloadState = {
  manifest: [
    { id: "llm-qwen15", name: "Qwen local", required: false },
    { id: "qwen", name: "Qwen local", required: false },
  ],
  models: { "llm-qwen15": "ready", qwen: "error" },
  progress: {},
};
const stored = new Map<string, string>();

vi.mock("@/hooks/useDownload", () => ({ useDownload: () => downloadState }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "researcher-1" } }) }));
vi.mock("@/lib/userStorage", () => ({
  getUserItem: (key: string, userId: string) => stored.get(`${key}:${userId}`) ?? null,
  setUserItem: (key: string, value: string, userId: string) => {
    stored.set(`${key}:${userId}`, value);
    return true;
  },
}));

function activity(detail: Partial<ActivityNotification> = {}): ActivityNotification {
  return {
    id: "download:evaluation:1",
    source: "evaluation",
    status: "in_progress",
    title: "Preparando descarga",
    message: "informe.pdf",
    progress: null,
    createdAt: "2026-09-01T00:00:00Z",
    read: false,
    ...detail,
  };
}

describe("DownloadNotifications", () => {
  beforeEach(() => {
    downloadState.models = { "llm-qwen15": "ready", qwen: "error" };
    stored.clear();
  });

  it("señala actividad que requiere atención y enlaza al gestor", () => {
    render(<DownloadNotifications />);
    const trigger = screen.getByRole("button", { name: /Actividad: 1 pendiente/i });
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: /Actividad y notificaciones/i })).toBeInTheDocument();
    expect(screen.getByText("Requiere atención")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Descargas/i })).toHaveAttribute("href", "/launcher");
  });

  it("actualiza una descarga sin duplicarla y muestra progreso", () => {
    render(<DownloadNotifications />);
    act(() => window.dispatchEvent(new CustomEvent(ACTIVITY_NOTIFICATION_EVENT, { detail: activity() })));
    expect(screen.getByRole("button", { name: /Actividad: 2 pendiente/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Actividad: 2 pendiente/i }));
    expect(screen.getByRole("progressbar", { name: "Preparando descarga" })).toBeInTheDocument();

    act(() => window.dispatchEvent(new CustomEvent(ACTIVITY_NOTIFICATION_EVENT, {
      detail: activity({ status: "success", title: "Descarga iniciada", progress: 100 }),
    })));
    expect(screen.getAllByText("informe.pdf")).toHaveLength(1);
    expect(screen.getByRole("progressbar", { name: "Descarga iniciada" })).toHaveAttribute("aria-valuenow", "100");
  });

  it("cierra con Escape y devuelve el foco", () => {
    render(<DownloadNotifications />);
    const trigger = screen.getByRole("button", { name: /Actividad/i });
    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});