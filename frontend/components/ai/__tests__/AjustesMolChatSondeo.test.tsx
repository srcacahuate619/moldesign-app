// El modal de MolChat frente al sondeo de `/ai/status`.
//
// EL FALLO. El chat sondea `/ai/status` cada 8 s mientras está abierto, y cada
// sondeo trae una lista de proveedores NUEVA. Un efecto del modal dependía de
// esa lista: al llegar, devolvía la selección al proveedor activo y recargaba
// los campos. Elegir «Ollama» o «Clave de API» volvía solo a «llama.cpp», y una
// clave a medio escribir desaparecía. Además, guardar enviaba siempre
// `api_key: ""`, y como la clave no vuelve del backend, reabrir el modal y
// pulsar «Guardar» sobrescribía la clave guardada con una vacía.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AISettingsModal } from "../AISettingsModal";

type Proveedor = {
  id: string;
  name: string;
  description: string;
  requires_api_key: boolean;
  requires_base_url: boolean;
  default_base_url: string;
  default_model: string;
  available_models: string[];
  configured: boolean;
  active: boolean;
};

function catalogo(): Proveedor[] {
  // Objetos nuevos en cada llamada, como los de cada respuesta del sondeo.
  return [
    {
      id: "local", name: "MolChat Local", description: "", requires_api_key: false,
      requires_base_url: false, default_base_url: "", default_model: "qwen.gguf",
      available_models: [], configured: true, active: true,
    },
    {
      id: "ollama", name: "Ollama", description: "", requires_api_key: false,
      requires_base_url: true, default_base_url: "http://localhost:11434",
      default_model: "gemma3:1b", available_models: [], configured: false, active: false,
    },
    {
      id: "claude", name: "Claude (Anthropic)", description: "", requires_api_key: true,
      requires_base_url: false, default_base_url: "", default_model: "claude-x",
      available_models: [], configured: true, active: false,
    },
  ];
}

const mocks = vi.hoisted(() => ({
  state: {} as Record<string, unknown>,
  dispatch: vi.fn(),
  updateProviderConfig: vi.fn(async (_cfg: Record<string, unknown>) => null),
  setActiveProvider: vi.fn(async (_id: string) => undefined),
}));

vi.mock("@/context/AIContext", () => ({
  FALLBACK_PROVIDER: {
    id: "local", name: "Local", description: "", requires_api_key: false,
    requires_base_url: false, default_base_url: "", default_model: "", available_models: [],
    configured: false, active: false,
  },
  useAI: () => ({
    state: mocks.state,
    dispatch: mocks.dispatch,
    setActiveProvider: mocks.setActiveProvider,
    updateProviderConfig: mocks.updateProviderConfig,
    loadProviders: vi.fn(async () => undefined),
    detectStartup: vi.fn(async () => undefined),
    setKeepLoaded: vi.fn(async () => undefined),
  }),
}));

function sondeo(rerender: (ui: React.ReactElement) => void) {
  mocks.state = { ...mocks.state, providers: catalogo() };
  rerender(<AISettingsModal />);
}

describe("el modal de MolChat no se reinicia con el sondeo", () => {
  beforeEach(() => {
    mocks.dispatch.mockReset();
    mocks.updateProviderConfig.mockClear();
    mocks.setActiveProvider.mockClear();
    mocks.state = {
      isSettingsOpen: true,
      providers: catalogo(),
      activeProviderId: "local",
      providerConfigs: {},
      resourceStatus: null,
    };
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ models: [], options: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    ) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("Ollama sigue elegido, con su URL escrita, después de un sondeo", async () => {
    const { rerender } = render(<AISettingsModal />);
    fireEvent.click(screen.getByRole("button", { name: "Ollama" }));
    expect(screen.getByRole("button", { name: "Ollama" })).toHaveAttribute("aria-pressed", "true");

    const url = screen.getByDisplayValue("http://localhost:11434");
    fireEvent.change(url, { target: { value: "http://127.0.0.1:11500" } });

    sondeo(rerender);
    sondeo(rerender);

    expect(screen.getByRole("button", { name: "Ollama" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "llama.cpp" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByDisplayValue("http://127.0.0.1:11500")).toBeInTheDocument();
  });

  it("Clave de API sigue elegida y la clave a medio escribir no se borra", () => {
    const { rerender } = render(<AISettingsModal />);
    fireEvent.click(screen.getByRole("button", { name: "Clave de API" }));
    expect(screen.getByRole("button", { name: "Claude (Anthropic)" })).toHaveAttribute("aria-pressed", "true");

    const clave = screen.getByPlaceholderText(/Hay una clave guardada/);
    fireEvent.change(clave, { target: { value: "sk-ant-escribiendo" } });

    sondeo(rerender);

    expect(screen.getByRole("button", { name: "Claude (Anthropic)" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByDisplayValue("sk-ant-escribiendo")).toBeInTheDocument();
  });

  it("guardar sin reescribir la clave no la sobrescribe con una vacía", async () => {
    render(<AISettingsModal />);
    fireEvent.click(screen.getByRole("button", { name: "Clave de API" }));
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() => expect(mocks.updateProviderConfig).toHaveBeenCalledTimes(1));
    const enviado = mocks.updateProviderConfig.mock.calls[0][0];
    expect(enviado.provider_id).toBe("claude");
    expect(enviado).not.toHaveProperty("api_key");
  });

  it("guardar el modo local no le impone la temperatura de un deslizador que no enseña", async () => {
    render(<AISettingsModal />);
    fireEvent.click(screen.getByRole("button", { name: "Guardar configuración" }));

    await waitFor(() => expect(mocks.updateProviderConfig).toHaveBeenCalledTimes(1));
    const enviado = mocks.updateProviderConfig.mock.calls[0][0];
    expect(enviado.provider_id).toBe("local");
    expect(enviado).not.toHaveProperty("temperature");
    expect(enviado).not.toHaveProperty("api_key");
  });
});
