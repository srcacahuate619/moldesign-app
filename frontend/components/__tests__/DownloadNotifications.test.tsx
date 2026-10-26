import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ACTIVITY_NOTIFICATION_EVENT,
  dismissActivityNotification,
  type ActivityNotification,
} from "@/lib/activityNotifications";
import { DownloadNotifications } from "../DownloadNotifications";

const ESMFOLD = "esmfold-weights";
const TOTAL = 8_442_062_570;

const downloadState: {
  manifest: Array<{ id: string; name: string; required: boolean; size_bytes: number }>;
  models: Record<string, string>;
  progress: Record<string, { model_id: string; bytes_downloaded: number; total_bytes: number }>;
  initialized: boolean;
  engine?: { state: string };
} = {
  manifest: [
    { id: "llm-qwen15", name: "Qwen 2.5 1.5B Instruct (Q4_K_M)", required: false, size_bytes: 1_117_320_736 },
    { id: ESMFOLD, name: "ESMFold v1 — pesos del modelo", required: false, size_bytes: TOTAL },
  ],
  models: {},
  progress: {},
  initialized: true,
};
const stored = new Map<string, string>();
const molcy = vi.hoisted(() => ({ renderizadorMolcy: vi.fn(), instalacionMolcy: vi.fn() }));
vi.mock("@/lib/molcy", async (original) => ({ ...(await original<typeof import("@/lib/molcy")>()), ...molcy }));

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

function avisoDeModelo(detail: Partial<ActivityNotification> = {}): ActivityNotification {
  return activity({
    id: `model:${ESMFOLD}`,
    source: "models",
    title: undefined,
    message: undefined,
    titleKey: "nt_modelo_descargando",
    messageKey: "nt_modelo_descargando_msg",
    moduleId: ESMFOLD,
    href: "/launcher",
    ...detail,
  });
}

function emitir(detail: ActivityNotification) {
  act(() => window.dispatchEvent(new CustomEvent(ACTIVITY_NOTIFICATION_EVENT, { detail })));
}

describe("DownloadNotifications", () => {
  beforeEach(() => {
    downloadState.models = { "llm-qwen15": "ready", [ESMFOLD]: "missing" };
    downloadState.progress = {};
    downloadState.initialized = true;
    stored.clear();
    // Salvo en las pruebas de la bienvenida, este usuario ya la recibió.
    stored.set("moldesign_activity_bienvenida_modelos:researcher-1", "2026-10-01T00:00:00Z");
  });

  it("el panel no lleva una sección fija de modelos ni un atajo a Evaluación", () => {
    render(<DownloadNotifications />);
    // Un modelo sin instalar ya no cuenta como pendiente: no es actividad.
    fireEvent.click(screen.getByRole("button", { name: /^Actividad$/ }));
    const panel = screen.getByRole("dialog", { name: /Actividad y notificaciones/i });
    expect(panel).not.toHaveTextContent("Modelos y motores");
    expect(panel).not.toHaveTextContent("Disponible para descargar");
    expect(screen.queryByRole("link", { name: /Evaluación/i })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Gestionar descargas/i })).toHaveAttribute("href", "/launcher");
    expect(screen.getByText("Sin actividad reciente")).toBeInTheDocument();
  });

  it("persists a silent terminal event without opening a banner or a progress indicator", () => {
    render(<DownloadNotifications />);
    emitir(activity({id:"run:cancelled",status:"info",title:"Cancelación registrada",outcome:"cancelled",silent:true}));
    expect(screen.queryByRole("button", {name:"Cerrar aviso"})).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", {name:/Actividad: 1 pendiente/i}));
    expect(screen.getByRole("dialog")).toHaveTextContent("Cancelación registrada");
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
    expect([...stored.values()].some(value => value.includes("run:cancelled"))).toBe(true);
  });

  it("actualiza una descarga sin duplicarla y muestra progreso", () => {
    render(<DownloadNotifications />);
    emitir(activity());
    expect(screen.getByRole("button", { name: /Actividad: 1 pendiente/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Actividad: 1 pendiente/i }));
    expect(screen.getByRole("progressbar", { name: "Preparando descarga" })).toBeInTheDocument();

    emitir(activity({ status: "success", title: "Descarga iniciada", progress: 100 }));
    expect(screen.getAllByText("informe.pdf")).toHaveLength(1);
    // Terminada, la barra se va aunque el aviso traiga su 100 % (avisos guardados antes de este cambio).
    expect(screen.queryByRole("progressbar", { name: "Descarga iniciada" })).not.toBeInTheDocument();
  });

  it("una descarga en curso con progreso conocido sí lleva su barra", () => {
    render(<DownloadNotifications />);
    emitir(activity({ title: "Exportando", progress: 40 }));
    fireEvent.click(screen.getByRole("button", { name: /Actividad: 1 pendiente/i }));
    expect(screen.getByRole("progressbar", { name: "Exportando" })).toHaveAttribute("aria-valuenow", "40");
  });

  it("una descarga de modelo es un aviso con su barra leída en vivo", () => {
    downloadState.models[ESMFOLD] = "downloading";
    downloadState.progress = { [ESMFOLD]: { model_id: ESMFOLD, bytes_downloaded: TOTAL / 2, total_bytes: TOTAL } };
    const { rerender } = render(<DownloadNotifications />);
    emitir(avisoDeModelo());
    fireEvent.click(screen.getByRole("button", { name: /Actividad: 1 pendiente/i }));

    const barra = screen.getByRole("progressbar", { name: "Descargando ESMFold v1 — pesos del modelo" });
    expect(barra).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText("4.22 GB / 8.44 GB · 50 %")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Descargando ESMFold/ })).toHaveAttribute("href", "/launcher");

    // Con todos los bytes, Rust verifica el SHA-256: la barra llena lo dice.
    downloadState.progress = { [ESMFOLD]: { model_id: ESMFOLD, bytes_downloaded: TOTAL, total_bytes: TOTAL } };
    rerender(<DownloadNotifications />);
    expect(screen.getByText("Verificando SHA-256…")).toBeInTheDocument();

    // Terminada: misma entrada, sin barra.
    emitir(avisoDeModelo({ status: "success", titleKey: "nt_modelo_instalado", messageKey: "nt_modelo_instalado_msg" }));
    expect(screen.getByText("ESMFold v1 — pesos del modelo, instalado")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("una descarga cancelada se retira, y una retirada condicionada respeta el estado", () => {
    render(<DownloadNotifications />);
    emitir(avisoDeModelo());
    expect(screen.getByRole("button", { name: /Actividad: 1 pendiente/i })).toBeInTheDocument();

    // Retirar «sólo si es una sugerencia» no toca una descarga en curso.
    act(() => dismissActivityNotification(`model:${ESMFOLD}`, "info"));
    expect(screen.getByRole("button", { name: /Actividad: 1 pendiente/i })).toBeInTheDocument();

    act(() => dismissActivityNotification(`model:${ESMFOLD}`, "in_progress"));
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
  });

  it("una descarga de modelo que la aplicación no terminó se dice interrumpida", () => {
    stored.set("moldesign_activity_notifications:researcher-1", JSON.stringify([avisoDeModelo({ read: true })]));
    render(<DownloadNotifications />);
    fireEvent.click(screen.getByRole("button", { name: /Actividad/ }));
    expect(screen.getByText("Se interrumpió la descarga de ESMFold v1 — pesos del modelo")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("una descarga de modelo que Rust sigue haciendo NO se dice interrumpida", () => {
    downloadState.models[ESMFOLD] = "downloading";
    stored.set("moldesign_activity_notifications:researcher-1", JSON.stringify([avisoDeModelo({ read: true })]));
    render(<DownloadNotifications />);
    expect(screen.getByTestId("actividad-en-curso")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Hay actividad en curso/ }));
    expect(screen.getByText("Descargando ESMFold v1 — pesos del modelo")).toBeInTheDocument();
  });

});

describe("DownloadNotifications · bienvenida", () => {
  beforeEach(() => {
    downloadState.models = { "llm-qwen15": "ready", [ESMFOLD]: "missing" };
    downloadState.progress = {};
    downloadState.initialized = true;
    stored.clear();
  });

  it("la primera vez sugiere descargar los modelos que faltan, y sólo una vez", () => {
    const { unmount } = render(<DownloadNotifications />);
    // Qwen ya está; ESMFold falta: una sola sugerencia.
    expect(screen.getByRole("button", { name: /Actividad: 1 pendiente/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Actividad: 1 pendiente/i }));
    expect(screen.getByText("Descarga ESMFold v1 — pesos del modelo")).toBeInTheDocument();
    expect(screen.queryByText(/Descarga Qwen/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Descarga ESMFold/ })).toHaveAttribute("href", "/launcher");
    unmount();

    // Se descarta; al volver a abrir la aplicación no reaparece.
    stored.set("moldesign_activity_notifications:researcher-1", "[]");
    render(<DownloadNotifications />);
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
  });

  it("con los dos modelos ya en disco no sugiere nada", () => {
    downloadState.models = { "llm-qwen15": "ready", [ESMFOLD]: "ready" };
    render(<DownloadNotifications />);
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
  });

  it("sin el estado real de los modelos todavía no sugiere nada", () => {
    downloadState.initialized = false;
    downloadState.models = {};
    render(<DownloadNotifications />);
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
    expect(stored.has("moldesign_activity_bienvenida_modelos:researcher-1")).toBe(false);
  });

  it("los dos que faltan salen como dos sugerencias que se pueden quitar", () => {
    downloadState.models = { "llm-qwen15": "missing", [ESMFOLD]: "missing" };
    render(<DownloadNotifications />);
    fireEvent.click(screen.getByRole("button", { name: /Actividad: 2 pendientes/i }));
    fireEvent.click(screen.getByRole("button", { name: "Descartar: Descarga Qwen 2.5 1.5B Instruct (Q4_K_M)" }));
    expect(screen.queryByText(/Descarga Qwen/)).not.toBeInTheDocument();
    expect(screen.getByText("Descarga ESMFold v1 — pesos del modelo")).toBeInTheDocument();
  });
});

describe("DownloadNotifications · teclado", () => {
  beforeEach(() => {
    stored.clear();
    stored.set("moldesign_activity_bienvenida_modelos:researcher-1", "2026-10-01T00:00:00Z");
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

describe("DownloadNotifications · aviso junto a la campana", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    downloadState.models = { "llm-qwen15": "ready", [ESMFOLD]: "ready" };
    downloadState.progress = {};
    downloadState.initialized = true;
    stored.clear();
    stored.set("moldesign_activity_bienvenida_modelos:researcher-1", "2026-10-01T00:00:00Z");
  });
  afterEach(() => vi.useRealTimers());

  const aviso = () => screen.queryByTestId("aviso-de-actividad");
  const avanzar = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });

  it("un aviso nuevo sale junto a la campana, la hace sonar y se va solo", () => {
    render(<DownloadNotifications />);
    const campana = () => screen.getByRole("button", { name: /Actividad/ }).querySelector("svg");
    // Al abrir la aplicación no suena nada.
    expect(campana()).not.toHaveClass("motion-safe:animate-campana");
    expect(aviso()).toBeNull();

    emitir(activity({ status: "success", title: undefined, titleKey: "nt_archivo_iniciada", message: "informe.pdf" }));
    expect(aviso()).toHaveTextContent("Descarga iniciada");
    expect(aviso()).toHaveTextContent("informe.pdf");
    expect(campana()).toHaveClass("motion-safe:animate-campana");
    expect(screen.getByRole("status")).toHaveTextContent("Descarga iniciada. informe.pdf");

    avanzar(5_900);
    expect(aviso()).not.toBeNull();
    avanzar(200);
    expect(aviso()).toBeNull();
    // Se fue el aviso, no la notificación: sigue sin leer en la campana.
    expect(screen.getByRole("button", { name: /Actividad: 1 pendiente/ })).toBeInTheDocument();
  });

  it("con el ratón encima no se va, y un error se queda más tiempo", () => {
    render(<DownloadNotifications />);
    emitir(activity({ status: "error", title: undefined, titleKey: "nt_archivo_fallo" }));
    avanzar(9_000);
    expect(aviso()).toHaveTextContent("No se pudo completar la descarga");

    fireEvent.mouseEnter(aviso()!);
    avanzar(60_000);
    expect(aviso()).not.toBeNull();
    fireEvent.mouseLeave(aviso()!);
    avanzar(10_100);
    expect(aviso()).toBeNull();
  });

  it("el progreso de una descarga no repite el aviso; terminar sí", () => {
    render(<DownloadNotifications />);
    emitir(activity({ title: "Exportando", progress: 10 }));
    fireEvent.click(screen.getByRole("button", { name: "Cerrar aviso" }));
    expect(aviso()).toBeNull();

    emitir(activity({ title: "Exportando", progress: 60 }));
    expect(aviso()).toBeNull();

    emitir(activity({ status: "success", title: "Exportado", progress: null }));
    expect(aviso()).toHaveTextContent("Exportado");
  });

  it("con el panel abierto no sale: ya se ve dentro", () => {
    render(<DownloadNotifications />);
    fireEvent.click(screen.getByRole("button", { name: /^Actividad$/ }));
    emitir(activity({ status: "success", title: "Visto dentro" }));
    expect(aviso()).toBeNull();
    expect(screen.getByRole("dialog")).toHaveTextContent("Visto dentro");
  });

  it("dice cuántos más hay sin leer, y pulsarlo lleva a su sitio y lo marca leído", () => {
    render(<DownloadNotifications />);
    emitir(activity({ id: "a", status: "success", title: "Primero", href: "/evaluation" }));
    emitir(activity({ id: "b", status: "success", title: "Segundo", href: "/evaluation/batch" }));
    expect(aviso()).toHaveTextContent("Segundo");
    expect(aviso()).toHaveTextContent("y 1 aviso más sin leer");

    fireEvent.click(screen.getByRole("link", { name: /Segundo/ }));
    expect(aviso()).toBeNull();
    expect(screen.getByRole("button", { name: /Actividad: 1 pendiente/ })).toBeInTheDocument();
  });

  it("un aviso antiguo sin enlace lleva a su sección de origen", () => {
    render(<DownloadNotifications />);
    emitir(activity({ status: "success", title: "Sin enlace" }));
    const link = screen.getByRole("link", { name: /Sin enlace/ });
    expect(link).toHaveAttribute("href", "/evaluation");
    fireEvent.click(link);
    expect(aviso()).toBeNull();
  });

  it("«Borrar todo» vacía el panel", () => {
    render(<DownloadNotifications />);
    emitir(activity({ id: "a", status: "success", title: "Uno" }));
    emitir(activity({ id: "b", status: "error", title: "Dos" }));
    fireEvent.click(screen.getByRole("button", { name: /Actividad: 2 pendientes/ }));
    fireEvent.click(screen.getByRole("button", { name: "Borrar todo" }));
    expect(screen.getByText("Sin actividad reciente")).toBeInTheDocument();
    expect(stored.get("moldesign_activity_notifications:researcher-1")).toBe("[]");
  });

  it("un archivo que se preparaba cuando se cerró la ventana no gira para siempre", () => {
    stored.set("moldesign_activity_notifications:researcher-1", JSON.stringify([activity({ read: true })]));
    render(<DownloadNotifications />);
    fireEvent.click(screen.getByRole("button", { name: /^Actividad$/ }));
    expect(screen.getByText("La descarga no terminó")).toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });
});

describe("DownloadNotifications · bienvenida de Blender + Molecular Nodes", () => {
  beforeEach(() => {
    downloadState.models = { "llm-qwen15": "ready", [ESMFOLD]: "ready" };
    downloadState.progress = {};
    downloadState.initialized = true;
    downloadState.engine = { state: "ready" };
    stored.clear();
    molcy.renderizadorMolcy.mockReset();
    molcy.instalacionMolcy.mockReset();
    molcy.instalacionMolcy.mockResolvedValue({ descarga_bytes: 404_453_484 });
  });
  afterEach(() => { downloadState.engine = undefined; });

  it("si falta Blender, la primera vez sugiere el paquete, y sólo una vez", async () => {
    molcy.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo_codigo: "falta_blender", motivo: "No se encontró Blender." });
    const { unmount } = render(<DownloadNotifications />);
    fireEvent.click(await screen.findByRole("button", { name: /Actividad: 1 pendiente/i }));
    expect(screen.getByText("Descarga Blender + Molecular Nodes")).toBeInTheDocument();
    expect(screen.getByText(/Para que Molcy haga fotos y vídeos.*unos 538 MB/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Descarga Blender/ })).toHaveAttribute("href", "/launcher");
    unmount();

    stored.set("moldesign_activity_notifications:researcher-1", "[]");
    render(<DownloadNotifications />);
    await act(async () => {});
    expect(molcy.renderizadorMolcy).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
  });

  it("con Blender y sin Molecular Nodes también lo sugiere", async () => {
    molcy.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo_codigo: "falta_addon", motivo: "Falta Molecular Nodes." });
    render(<DownloadNotifications />);
    expect(await screen.findByRole("button", { name: /Actividad: 1 pendiente/i })).toBeInTheDocument();
  });

  it("con Molcy listo, o con un problema que no se arregla descargando, no sugiere nada", async () => {
    molcy.renderizadorMolcy.mockResolvedValue({ disponible: true, motivo: null });
    const { unmount } = render(<DownloadNotifications />);
    await act(async () => {});
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
    unmount();

    stored.clear();
    molcy.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo_codigo: "motor_alterado", motivo: "Reinstala MolDesign." });
    render(<DownloadNotifications />);
    await act(async () => {});
    expect(screen.getByRole("button", { name: /^Actividad$/ })).toBeInTheDocument();
  });

  it("sin el motor listo no pregunta; si el backend no contesta, no gasta la bienvenida", async () => {
    downloadState.engine = { state: "starting" };
    const { unmount } = render(<DownloadNotifications />);
    await act(async () => {});
    expect(molcy.renderizadorMolcy).not.toHaveBeenCalled();
    unmount();

    downloadState.engine = { state: "ready" };
    molcy.renderizadorMolcy.mockRejectedValue(new Error("Failed to fetch"));
    render(<DownloadNotifications />);
    await act(async () => {});
    expect(molcy.renderizadorMolcy).toHaveBeenCalledTimes(1);
    expect(stored.has("moldesign_activity_bienvenida_molcy:researcher-1")).toBe(false);
  });
});
