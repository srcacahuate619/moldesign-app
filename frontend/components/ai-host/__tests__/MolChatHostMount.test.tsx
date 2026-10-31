// Hueco del sidecar: estados, apretón de sesión y deep links.
//
// El iframe incrusta la UI verificada del sidecar; la sesión viaja por
// postMessage (orígenes loopback) y los deep links vuelven con esquema
// cerrado. Nada de fuera de loopback mueve nada.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MolChatHostMount, {
  esMensajeHost,
  esOrigenLoopback,
  rutaPara,
} from "../MolChatHostMount";

const push = vi.fn();
const traeBackend = vi.fn();
let locale: "es" | "en" = "es";
let theme: "dark" | "light" = "dark";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/context/LanguageContext", () => ({
  useLanguage: () => ({ t: (k: string) => k, locale }),
}));
vi.mock("@/context/ThemeContext", () => ({ useTheme: () => ({ theme }) }));
vi.mock("@/lib/backendFetch", () => ({
  fetchBackend: (...args: unknown[]) => traeBackend(...args),
}));
vi.mock("@/lib/api", () => ({ getAuthHeaders: () => ({}) }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "test-owner" } }) }));

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const SESION = {
  url: "http://127.0.0.1:52368",
  token: "mh1.sesion.firma",
  expira_en_s: 3600,
};

beforeEach(() => {
  locale = "es";
  theme = "dark";
  push.mockClear();
  traeBackend.mockReset();
  traeBackend.mockImplementation((ruta: string) => {
    if (ruta === "/molchat-host/status")
      return Promise.resolve(json({ disponible: true, motivo: "ok" }));
    if (ruta === "/molchat-host/session") return Promise.resolve(json(SESION));
    return Promise.resolve(json({}, 404));
  });
});

async function abrir(): Promise<void> {
  render(<MolChatHostMount />);
  fireEvent.click(screen.getByRole("button", { name: "opt_ai_chat_open" }));
  await waitFor(() =>
    expect(screen.queryByTitle("molchat_host_titulo")).not.toBeNull(),
  );
}

function mensaje(origin: string, data: unknown, source?: MessageEventSource): void {
  const iframe = screen.queryByTitle("molchat_host_titulo") as HTMLIFrameElement | null;
  fireEvent(
    window,
    new window.MessageEvent("message", { origin, data, source: source ?? iframe?.contentWindow }),
  );
}

describe("purezas del puente", () => {
  it("orígenes loopback y nada más", () => {
    expect(esOrigenLoopback("http://127.0.0.1:52368")).toBe(true);
    expect(esOrigenLoopback("http://localhost:8771")).toBe(true);
    expect(esOrigenLoopback("https://127.0.0.1.evil.com")).toBe(false);
    expect(esOrigenLoopback("https://example.com")).toBe(false);
    expect(esOrigenLoopback("basura")).toBe(false);
  });

  it("esquema cerrado de deep links", () => {
    expect(esMensajeHost({ kind: "open_molcy", job_id: "j-1" })).toBe(true);
    expect(esMensajeHost({ kind: "open_molcy" })).toBe(false);
    expect(esMensajeHost({ kind: "open_molcy", job_id: "" })).toBe(false);
    expect(esMensajeHost({ kind: "borrar_todo", job_id: "j-1" })).toBe(false);
    expect(
      esMensajeHost({ kind: "open_molcy", job_id: "j-1", extra: 1 }),
    ).toBe(false);
  });

  it("rutas reales o aviso", () => {
    expect(rutaPara({ kind: "open_molcy", job_id: "j-1" })).toBe("/molcy");
    expect(
      rutaPara({ kind: "open_evaluation", molecule_id: "m-1" }),
    ).toBe("/history");
    expect(rutaPara({ kind: "open_report", molecule_id: "m-1" })).toBe(
      "/history",
    );
    expect(rutaPara({ kind: "open_case", case_id: "c-1" })).toBe("/moldex");
    expect(
      rutaPara({ kind: "request_platform_approval", proposal_id: "p-1" }),
    ).toBeNull();
  });
});

describe("ciclo del panel", () => {
  it("acepta una sola solicitud de evaluación desde el iframe y transmite el resultado del host", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const listener = vi.fn((event: Event) => { const detail = (event as CustomEvent).detail; detail.handled = true; detail.respond({ status: "started", task_id: "task-123" }); });
    window.addEventListener("molchat-evaluate-case", listener);
    const req = { type: "molchat-host-message", kind: "evaluate_case", request_id: "e".repeat(32), case_name: "prueba" };
    mensaje("https://evil.example.com", req);
    expect(listener).not.toHaveBeenCalled();
    mensaje(SESION.url, req);
    mensaje(SESION.url, req);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(postea).toHaveBeenCalledWith({ type: "molchat-evaluation-result", request_id: "e".repeat(32), status: "started", task_id: "task-123" }, SESION.url);
    window.removeEventListener("molchat-evaluate-case", listener);
  });
  it("acepta la asignación una sola vez y solo desde el iframe autorizado", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const listener = vi.fn((event: Event) => { const detail = (event as CustomEvent).detail; detail.handled = true; detail.respond("locked"); });
    window.addEventListener("molchat-assign-receptor", listener);
    const req = { type: "molchat-host-message", kind: "assign_case_receptor", request_id: "d".repeat(32), case_name: "prueba", pdb_id: "7E2Y" };
    mensaje("https://evil.example.com", req);
    expect(listener).not.toHaveBeenCalled();
    mensaje(SESION.url, req);
    mensaje(SESION.url, req);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(postea).toHaveBeenCalledWith({ type: "molchat-receptor-result", request_id: "d".repeat(32), status: "locked" }, SESION.url);
    window.removeEventListener("molchat-assign-receptor", listener);
  });
  it("acepta lectura del editor solo del iframe vinculado", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const receptor = vi.fn((event: Event) => { const detail = (event as CustomEvent).detail; detail.handled = true; detail.respond({ status: "ok", molfile: "dibujo", revision: "1:2" }); });
    window.addEventListener("molchat-read-editor", receptor);
    const req = { type: "molchat-host-message", kind: "read_editor", request_id: "c".repeat(32), case_name: "prueba", operation: "snapshot", revision: "-" };
    mensaje("https://evil.example.com", req);
    expect(receptor).not.toHaveBeenCalled();
    mensaje(SESION.url, req);
    expect(receptor).toHaveBeenCalledTimes(1);
    expect(postea).toHaveBeenCalledWith({ type: "molchat-editor-result", request_id: "c".repeat(32), status: "ok", molfile: "dibujo", revision: "1:2" }, SESION.url);
    window.removeEventListener("molchat-read-editor", receptor);
  });
  it("entrega el SMILES sólo desde el iframe autorizado y responde con la confirmación del receptor", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const receptor = vi.fn((event: Event) => { const detail = (event as CustomEvent).detail; detail.handled = true; detail.respond("applied"); });
    window.addEventListener("molchat-load-smiles", receptor);
    const req = { type: "molchat-host-message", kind: "load_case_smiles", request_id: "b".repeat(32), case_name: "prueba", smiles: "CCO" };
    mensaje("https://evil.example.com", req);
    expect(receptor).not.toHaveBeenCalled();
    mensaje(SESION.url, req);
    mensaje(SESION.url, req);
    expect(receptor).toHaveBeenCalledTimes(1);
    expect(postea).toHaveBeenCalledWith({ type: "molchat-smiles-result", request_id: "b".repeat(32), status: "applied" }, SESION.url);
    window.removeEventListener("molchat-load-smiles", receptor);
  });
  it("transmite una sola solicitud de caso y confirma solo el resultado del receptor", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const receptor = vi.fn((event: Event) => {
      const detail = (event as CustomEvent).detail;
      detail.handled = true;
      detail.respond("created");
    });
    window.addEventListener("molchat-create-case", receptor);
    const solicitud = { type: "molchat-host-message", kind: "create_case", request_id: "a".repeat(32), name: "holamundo" };
    mensaje("https://evil.example.com", solicitud);
    expect(receptor).not.toHaveBeenCalled();
    mensaje(SESION.url, solicitud);
    mensaje(SESION.url, solicitud);
    expect(receptor).toHaveBeenCalledTimes(1);
    expect(postea).toHaveBeenCalledWith({ type: "molchat-case-result", request_id: "a".repeat(32), status: "created" }, SESION.url);
    window.removeEventListener("molchat-create-case", receptor);
  });
  it("tiene un botón de cierre visible dentro del panel", async () => {
    await abrir();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "opt_ai_chat_close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("mantiene el mismo iframe al cerrar y reabrir y permite pedir el micrófono", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo");
    expect(iframe.getAttribute("allow")).toBe("microphone");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "opt_ai_chat_close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "opt_ai_chat_open" }));
    expect(screen.getByTitle("molchat_host_titulo")).toBe(iframe);
    expect(traeBackend).toHaveBeenCalledTimes(2);
  });

  it("envía el tema vigente al sidecar", async () => {
    theme = "light";
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    mensaje(SESION.url, { type: "molchat-ui-ready" });
    await waitFor(() => expect(postea).toHaveBeenCalledWith(
      { type: "molchat-host-session", token: SESION.token, locale: "es", theme: "light" }, SESION.url,
    ));
  });
  it("abre perezoso: estado, sesión, iframe", async () => {
    render(<MolChatHostMount />);
    expect(traeBackend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "opt_ai_chat_open" }));
    await waitFor(() =>
      expect(screen.queryByTitle("molchat_host_titulo")).not.toBeNull(),
    );
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    expect(iframe.getAttribute("src")).toBe(SESION.url);
    expect(traeBackend).toHaveBeenCalledTimes(2);
  });

  it("ausente y error se declaran con reintento", async () => {
    traeBackend.mockImplementationOnce(() =>
      Promise.resolve(json({ disponible: false, motivo: "sin sidecar" })),
    );
    render(<MolChatHostMount />);
    fireEvent.click(screen.getByRole("button", { name: "opt_ai_chat_open" }));
    await waitFor(() =>
      expect(screen.queryByText(/molchat_host_ausente/)).not.toBeNull(),
    );
    expect(screen.queryByTitle("molchat_host_titulo")).toBeNull();
  });

  it("apretón: al listo del iframe responde la sesión", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    mensaje("http://127.0.0.1:52368", { type: "molchat-ui-ready" });
    await waitFor(() => expect(postea).toHaveBeenCalledTimes(1));
    expect(postea).toHaveBeenCalledWith(
      { type: "molchat-host-session", token: SESION.token, locale: "es", theme: "dark" },
      SESION.url,
    );
    mensaje("https://evil.example.com", { type: "molchat-ui-ready" });
    expect(postea).toHaveBeenCalledTimes(1);
  });

  it("envía el idioma de MolDesign junto a la sesión", async () => {
    locale = "en";
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    mensaje(SESION.url, { type: "molchat-ui-ready" });
    await waitFor(() => expect(postea).toHaveBeenCalledWith(
      { type: "molchat-host-session", token: SESION.token, locale: "en", theme: "dark" }, SESION.url,
    ));
  });

  it("ignora otros puertos locales y otras ventanas", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    mensaje("http://127.0.0.1:52369", { type: "molchat-ui-ready" });
    mensaje(SESION.url, { type: "molchat-ui-ready" }, window);
    mensaje(SESION.url, { type: "molchat-host-message", kind: "open_molcy", job_id: "j-1" }, window);
    expect(postea).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("deep links navegan y la aprobación avisa", async () => {
    await abrir();
    mensaje("http://127.0.0.1:52368", {
      type: "molchat-host-message",
      kind: "open_molcy",
      job_id: "j-1",
    });
    await waitFor(() => expect(push).toHaveBeenCalledWith("/molcy"));
    mensaje("http://127.0.0.1:52368", {
      type: "molchat-host-message",
      kind: "request_platform_approval",
      proposal_id: "p-1",
    });
    await waitFor(() =>
      expect(screen.queryByText("molchat_host_aprobacion")).not.toBeNull(),
    );
    mensaje("https://evil.example.com", {
      type: "molchat-host-message",
      kind: "open_molcy",
      job_id: "j-9",
    });
    mensaje("http://127.0.0.1:52368", {
      type: "molchat-host-message",
      kind: "borrar_todo",
    });
    expect(push).toHaveBeenCalledTimes(1);
  });
});
