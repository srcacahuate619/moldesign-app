// Hueco del sidecar: estados, apretón de sesión y deep links.
//
// El iframe incrusta la UI verificada del sidecar; la sesión viaja por
// postMessage (orígenes loopback) y los deep links vuelven con esquema
// cerrado. Nada de fuera de loopback mueve nada.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import MolChatHostMount, {
  colocar,
  estadoDelChat,
  esMensajeHost,
  esOrigenLoopback,
  rutaPara,
} from "../MolChatHostMount";
import { progresoDelChat } from "../PilotoAutomatico";
import { apuntarCursorDelChat } from "@/lib/cursorDelChat";

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
  it("pide la auditoría de Preparación una sola vez, enseña la pestaña y devuelve sólo molécula, estado y proyección", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const projection = { projection_version: 1, case_id: "c-1", name: "prueba" };
    const listener = vi.fn((event: Event) => {
      const detail = (event as CustomEvent).detail;
      detail.handled = true;
      // lo que no es del contrato no viaja: el host ya no deja pasar campos sueltos
      detail.respond({ status: "audited", molecule_id: "m-1", estado: "REVISION", projection, secreto: "no debe salir" });
    });
    window.addEventListener("molchat-audit-preparation", listener);
    const req = { type: "molchat-host-message", kind: "audit_case_preparation", request_id: "f".repeat(32), case_name: "prueba", task_id: "task-9" };
    mensaje("https://evil.example.com", req);
    expect(listener).not.toHaveBeenCalled();
    mensaje(SESION.url, req);
    mensaje(SESION.url, req);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0]).toMatchObject({ detail: { caseName: "prueba", taskId: "task-9" } });
    expect(push).toHaveBeenCalledWith("/preparacion");
    expect(postea).toHaveBeenCalledWith({ type: "molchat-preparation-result", request_id: "f".repeat(32), status: "audited",
      molecule_id: "m-1", estado: "REVISION", projection }, SESION.url);
    window.removeEventListener("molchat-audit-preparation", listener);
  });
  it("no deja pasar un estado que no está en el contrato de la auditoría", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const listener = vi.fn((event: Event) => { const detail = (event as CustomEvent).detail; detail.handled = true; detail.respond({ status: "todo_perfecto" }); });
    window.addEventListener("molchat-audit-preparation", listener);
    mensaje(SESION.url, { type: "molchat-host-message", kind: "audit_case_preparation", request_id: "9".repeat(32), case_name: "prueba", task_id: "t-1" });
    expect(postea).toHaveBeenCalledWith({ type: "molchat-preparation-result", request_id: "9".repeat(32), status: "unknown" }, SESION.url);
    window.removeEventListener("molchat-audit-preparation", listener);
  });
  it("convierte los avisos de descarga de MolChat en entradas del panel, y sólo los del contrato", async () => {
    await abrir();
    const avisos: Array<Record<string, unknown>> = [];
    const oir = (event: Event) => avisos.push((event as CustomEvent).detail);
    window.addEventListener("moldesign:activity", oir);
    const base = { type: "molchat-host-message", kind: "notify_download", request_id: "e".repeat(32), name: "entrega.zip" };
    mensaje(SESION.url, { ...base, phase: "started" });
    mensaje(SESION.url, { ...base, phase: "done" });
    mensaje(SESION.url, { ...base, phase: "borrar_todo" });
    mensaje(SESION.url, { ...base, phase: "done", name: "<img src=x>" });
    window.removeEventListener("moldesign:activity", oir);
    expect(avisos.map((a) => [a.id, a.status, a.titleKey])).toEqual([
      [`molchat-descarga:${"e".repeat(32)}`, "in_progress", "nt_molchat_descargando"],
      [`molchat-descarga:${"e".repeat(32)}`, "success", "nt_molchat_descargado"],
    ]);
    expect(avisos[1].params).toEqual({ name: "entrega.zip" });
  });
  it("pide el vídeo a la pestaña de Molcy a la vista y sólo deja pasar el estado y el trabajo", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const listener = vi.fn((event: Event) => {
      const detail = (event as CustomEvent).detail;
      detail.handled = true;
      detail.respond({ status: "started", job_id: "d2b13faf-3185-4aa1-95a2-228163cd8a74", reason: "no viaja" });
    });
    window.addEventListener("molchat-molcy-render", listener);
    const presentation = JSON.stringify({ schema: "moldesign.presentacion/1", titulo: null, color_receptor: "#8B5CF6", color_residuos: "#22C55E",
      colores_lineas: { polar: null, apolar: null }, receptor: "automatico", muestra_anterior: true, etiquetas: true, contactos: true, ensamble_variante: "lenta" });
    const req = { type: "molchat-host-message", kind: "molcy_render", request_id: "a".repeat(32), task_id: "task-9", scene: "busqueda", format: "horizontal", presentation };
    // un ajuste que la pestaña no tiene, o un color que no es un color, invalida la petición entera
    mensaje(SESION.url, { ...req, request_id: "c".repeat(32), presentation: presentation.replace('"#22C55E"', '"verde"') });
    mensaje(SESION.url, { ...req, request_id: "d".repeat(32), presentation: presentation.replace('"etiquetas":true', '"etiquetas":true,"brillo":9') });
    mensaje(SESION.url, { ...req, request_id: "b".repeat(32), scene: "inventada" });
    expect(listener).not.toHaveBeenCalled();
    mensaje(SESION.url, req);
    mensaje(SESION.url, req);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener.mock.calls[0][0]).toMatchObject({ detail: { taskId: "task-9", scene: "busqueda", format: "horizontal", variante: "lenta",
      presentacion: { color_receptor: "#8B5CF6", color_residuos: "#22C55E", etiquetas: true } } });
    expect(push).toHaveBeenCalledWith("/molcy");
    expect(postea).toHaveBeenCalledWith({ type: "molchat-molcy-result", request_id: "a".repeat(32), status: "started",
      job_id: "d2b13faf-3185-4aa1-95a2-228163cd8a74" }, SESION.url);
    window.removeEventListener("molchat-molcy-render", listener);
  });
  it("pregunta el estado del caso sin navegar y sólo deja pasar estado, corrida y task_id", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo") as HTMLIFrameElement;
    const postea = vi.spyOn(iframe.contentWindow!, "postMessage").mockImplementation(() => {});
    const listener = vi.fn((event: Event) => {
      const detail = (event as CustomEvent).detail;
      detail.handled = true;
      detail.respond({ status: "busy", run_state: "running", task_id: "task-7", secreto: "no debe salir" });
    });
    window.addEventListener("molchat-case-status", listener);
    push.mockClear();
    const req = { type: "molchat-host-message", kind: "case_status", request_id: "c".repeat(32), case_name: "prueba" };
    mensaje(SESION.url, req);
    mensaje(SESION.url, req);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
    expect(postea).toHaveBeenCalledWith({ type: "molchat-case-status-result", request_id: "c".repeat(32), status: "busy",
      run_state: "running", task_id: "task-7" }, SESION.url);
    window.removeEventListener("molchat-case-status", listener);
    // Sin espacio de casos que conteste, la respuesta es «unknown», nunca «idle».
    mensaje(SESION.url, { ...req, request_id: "d".repeat(32) });
    expect(postea).toHaveBeenCalledWith({ type: "molchat-case-status-result", request_id: "d".repeat(32), status: "unknown" }, SESION.url);
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
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("mantiene el mismo iframe al cerrar y reabrir y permite pedir el micrófono", async () => {
    await abrir();
    const iframe = screen.getByTitle("molchat_host_titulo");
    expect(iframe.getAttribute("allow")).toBe("microphone");
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
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

describe("panel minimizado", () => {
  it("el estado del chat tiene una forma cerrada", () => {
    expect(estadoDelChat({ type: "molchat-ui-status", state: "working", text: "Evaluando 2 de 3" })).toEqual({ state: "working", text: "Evaluando 2 de 3" });
    expect(estadoDelChat({ type: "molchat-ui-status", state: "idle", text: "" })).toBeNull();
    expect(estadoDelChat({ type: "molchat-ui-status", state: "borrar", text: "x" })).toBeNull();
    expect(estadoDelChat({ type: "molchat-ui-status", state: "working", text: "a\nb" })).toBeNull();
    expect(estadoDelChat({ type: "molchat-ui-status", state: "working", text: "x".repeat(141) })).toBeNull();
    expect(estadoDelChat({ type: "molchat-ui-status", state: "working", text: "x", extra: 1 })).toBeNull();
  });

  it("el botón movible no se sale de la ventana", () => {
    expect(colocar({ right: -50, bottom: 5000 }, 1280, 800)).toEqual({ right: 8, bottom: 800 - 52 - 8 });
    expect(colocar({ right: 300, bottom: 200 }, 1280, 800)).toEqual({ right: 300, bottom: 200 });
  });

  it("minimizado, la burbuja dice en qué está el chat y un clic lo vuelve a abrir", async () => {
    await abrir();
    mensaje(SESION.url, { type: "molchat-ui-status", state: "working", text: "Evaluando 2 de 3 · última Vina −7.2" });
    // Con el panel abierto no hay burbuja.
    expect(screen.queryByText("Evaluando 2 de 3 · última Vina −7.2")).toBeNull();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
    const burbuja = screen.getByRole("button", { name: "opt_ai_chat_open: Evaluando 2 de 3 · última Vina −7.2" });
    // Un estado mal formado o «idle» la apaga.
    mensaje(SESION.url, { type: "molchat-ui-status", state: "idle", text: "" });
    expect(screen.queryByText("Evaluando 2 de 3 · última Vina −7.2")).toBeNull();
    mensaje(SESION.url, { type: "molchat-ui-status", state: "attention", text: "Un plan espera tu aprobación" });
    fireEvent.click(screen.getByRole("button", { name: "opt_ai_chat_open: Un plan espera tu aprobación" }));
    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(burbuja.isConnected).toBe(false);
  });

  it("un resultado ya visto con el panel abierto no vuelve a salir al minimizar", async () => {
    await abrir();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
    mensaje(SESION.url, { type: "molchat-ui-status", state: "done", text: "Listo: Mol 2 · Vina −9.6" });
    fireEvent.click(screen.getByRole("button", { name: "opt_ai_chat_open: Listo: Mol 2 · Vina −9.6" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
    expect(screen.queryByText("Listo: Mol 2 · Vina −9.6")).toBeNull();
  });

  it("un estado de otro origen no enciende la burbuja", async () => {
    await abrir();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
    mensaje("https://evil.example.com", { type: "molchat-ui-status", state: "attention", text: "Pulsa aquí" });
    expect(screen.queryByText("Pulsa aquí")).toBeNull();
  });
});

describe("piloto automático", () => {
  const plan = (phase: string, extra: Record<string, unknown> = {}) => ({
    title: "Caso «VMAT2» · receptor 8T69", phase, now: "Evaluando 2 de 3 · última Vina −6.2",
    steps: [{ label: "Caso", state: "done" }, { label: "Moléculas", state: "running" }, { label: "Entrega", state: "pending" }],
    molecules: [{ name: "cafeína", state: "done", vina: -6.2, meets: false }, { name: "cetanserina", state: "running", vina: null, meets: false }],
    ...extra,
  });

  it("el progreso del plan tiene una forma cerrada", () => {
    expect(progresoDelChat({ type: "molchat-ui-progress", progress: plan("running") })?.molecules).toHaveLength(2);
    expect(progresoDelChat({ type: "molchat-ui-progress", progress: null })).toBeNull();
    for (const malo of [plan("pensando"), plan("running", { extra: 1 }), plan("running", { now: "a\nb" }),
      plan("running", { molecules: [{ name: "x", state: "done", vina: "−6", meets: false }] }),
      plan("running", { molecules: new Array(13).fill({ name: "x", state: "done", vina: null, meets: false }) }),
      plan("running", { steps: [{ label: "<b>x</b>".repeat(20), state: "done" }] })]) {
      expect(progresoDelChat({ type: "molchat-ui-progress", progress: malo })).toBeNull();
    }
    expect(progresoDelChat({ type: "molchat-ui-progress", progress: plan("running"), extra: 1 })).toBeNull();
  });

  it("mientras el plan maneja la aplicación se ven el cartel y el cursor de MolChat, y la burbuja enseña el plan", async () => {
    await abrir();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "molchat_host_minimizar" }));
    mensaje(SESION.url, { type: "molchat-ui-status", state: "working", text: "Evaluando 2 de 3 · última Vina −6.2" });
    mensaje(SESION.url, { type: "molchat-ui-progress", progress: plan("running") });
    expect(screen.getByTestId("molchat-piloto").textContent).toContain("molchat_piloto");
    const burbuja = screen.getByRole("button", { name: "opt_ai_chat_open: Evaluando 2 de 3 · última Vina −6.2" });
    expect(within(burbuja).getByText("cafeína")).not.toBeNull();
    expect(within(burbuja).getByText("−6.2")).not.toBeNull();
    expect(within(burbuja).getByText("1/2")).not.toBeNull();
    // El cursor sale de la esquina de MolChat y va al control sobre el que actúa la pestaña.
    const cursor = document.querySelector(".molchat-piloto-cursor") as HTMLElement;
    expect(cursor).not.toBeNull();
    const boton = document.createElement("button");
    boton.getBoundingClientRect = () => ({ left: 100, top: 200, width: 80, height: 40, right: 180, bottom: 240, x: 100, y: 200, toJSON: () => ({}) });
    document.body.appendChild(boton);
    vi.useFakeTimers();
    try {
      apuntarCursorDelChat(boton, true);
      vi.advanceTimersByTime(900);
    } finally { vi.useRealTimers(); }
    await waitFor(() => expect(cursor.style.transform).toBe("translate(140px, 220px)"));
    // Terminado, el marco y el cartel se van; la burbuja dice que terminó.
    mensaje(SESION.url, { type: "molchat-ui-progress", progress: plan("done") });
    expect(screen.queryByTestId("molchat-piloto")).toBeNull();
    expect(document.querySelector(".molchat-piloto-marco")).toBeNull();
  });

  it("un progreso de otro origen no enciende el piloto", async () => {
    await abrir();
    mensaje("https://evil.example.com", { type: "molchat-ui-progress", progress: plan("running") });
    expect(screen.queryByTestId("molchat-piloto")).toBeNull();
  });
});

