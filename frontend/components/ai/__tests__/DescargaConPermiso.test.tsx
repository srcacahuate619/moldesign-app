// Los botones «Descargar» y «Cuantización» del Intérprete IA.
//
// LOS FALLOS. (1) Descargar sale a huggingface.co y exige que la cuenta lo haya
// autorizado; el modal sólo enseñaba «HTTP 403» y ninguna pantalla de MolChat
// ofrecía autorizarlo, así que el botón no podía funcionar. (2) Los botones de
// cuantización lanzaban una descarga con nombre de archivo vacío (el backend
// contesta 400) y buscaban «Q4_K_M» en nombres en minúscula: nunca
// encontraban el archivo que sí estaba.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AISettingsModal } from "../AISettingsModal";

const mocks = vi.hoisted(() => ({ state: {} as Record<string, unknown> }));

vi.mock("@/context/AIContext", () => ({
  FALLBACK_PROVIDER: {
    id: "local", name: "Local", description: "", requires_api_key: false,
    requires_base_url: false, default_base_url: "", default_model: "", available_models: [],
    configured: false, active: false,
  },
  useAI: () => ({
    state: mocks.state,
    dispatch: vi.fn(),
    setActiveProvider: vi.fn(async () => undefined),
    updateProviderConfig: vi.fn(async () => null),
    loadProviders: vi.fn(async () => undefined),
    detectStartup: vi.fn(async () => undefined),
    setKeepLoaded: vi.fn(async () => undefined),
  }),
}));

const MENSAJE = "Esta cuenta no autorizó huggingface (huggingface.co). Hacia allí saldría: el nombre del modelo.";

let pedidos: { url: string; body?: string }[] = [];
let permisoOtorgado = false;
let offline = false;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function abrir(modelosLocales: { filename: string; quant: string }[] = [], modelo = "") {
  mocks.state = {
    isSettingsOpen: true,
    providers: [{
      id: "local", name: "MolChat Local", description: "", requires_api_key: false,
      requires_base_url: false, default_base_url: "", default_model: modelo,
      available_models: modelosLocales.map((m) => m.filename), configured: true, active: true, model: modelo,
    }],
    activeProviderId: "local",
    providerConfigs: {},
    resourceStatus: null,
  };
  global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    pedidos.push({ url: u, body: init?.body as string | undefined });
    if (u.endsWith("/ai/models/local")) return json({ models: modelosLocales.map((m) => ({ ...m, size_display: "1 GB" })) });
    if (u.endsWith("/ai/models/recommend-quant")) {
      return json({
        options: [
          { quant: "Q4_K_M", label: "Q4_K_M", description: "", model_size_gb: 1.1, min_ram_gb: 2.5, fits: true, is_recommended: true },
          { quant: "Q5_K_M", label: "Q5_K_M", description: "", model_size_gb: 3, min_ram_gb: 5, fits: true, is_recommended: false },
        ],
      });
    }
    if (u.endsWith("/ai/consent/red")) {
      permisoOtorgado = true;
      return json({ status: "ok" });
    }
    if (u.endsWith("/ai/models/download")) {
      if (!permisoOtorgado) {
        return json({
          detail: {
            motivo: offline ? "offline" : "sin_permiso",
            mensaje: offline ? "El equipo está en modo offline." : MENSAJE,
            servicio: "huggingface", host: "huggingface.co",
          },
        }, 403);
      }
      return json({ id: "dl1" });
    }
    if (u.includes("/ai/models/download/")) return json({ status: "downloading", progress_pct: 1 });
    throw new Error(`Unexpected fetch: ${u}`);
  }) as unknown as typeof fetch;
  render(<AISettingsModal />);
}

function descargarQwen35() {
  const tarjeta = screen.getByText("Qwen3.5 4B (Avanzado)").closest("div")!.parentElement!;
  fireEvent.click(within(tarjeta).getByRole("button", { name: "Descargar" }));
}

describe("descargar desde el Intérprete IA", () => {
  beforeEach(() => {
    pedidos = [];
    permisoOtorgado = false;
    offline = false;
  });

  it("sin permiso, dice a dónde saldría y ofrece autorizarlo y descargar", async () => {
    abrir();
    descargarQwen35();

    const aviso = await screen.findByTestId("permiso-descarga");
    expect(aviso).toHaveTextContent(MENSAJE);
    fireEvent.click(within(aviso).getByRole("button", { name: "Autorizar huggingface.co y descargar" }));

    await waitFor(() => expect(pedidos.filter((p) => p.url.endsWith("/ai/models/download"))).toHaveLength(2));
    const permiso = pedidos.find((p) => p.url.endsWith("/ai/consent/red"))!;
    expect(JSON.parse(permiso.body!)).toEqual({ servicio: "huggingface", host: "huggingface.co" });
    await waitFor(() => expect(screen.queryByTestId("permiso-descarga")).toBeNull());
  });

  it("en modo offline lo dice y no ofrece una autorización que no lo arreglaría", async () => {
    offline = true;
    abrir();
    descargarQwen35();

    expect(await screen.findByRole("alert")).toHaveTextContent("modo offline");
    expect(screen.queryByRole("button", { name: /Autorizar huggingface\.co/ })).toBeNull();
  });
});

describe("los botones de cuantización", () => {
  beforeEach(() => {
    pedidos = [];
  });

  it("eligen tu modelo de esa cuantización y nunca lanzan una descarga", async () => {
    abrir([{ filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf", quant: "Q4_K_M" }], "otro.gguf");

    const q4 = await screen.findByRole("button", { name: /^Q4_K_M/ });
    const q5 = screen.getByRole("button", { name: /^Q5_K_M/ });
    await waitFor(() => expect(q4).not.toBeDisabled());
    expect(q5).toBeDisabled();
    fireEvent.click(q5);
    fireEvent.click(q4);

    expect(q4).toHaveAttribute("aria-pressed", "true");
    expect(pedidos.some((p) => p.url.endsWith("/ai/models/download"))).toBe(false);
  });
});
