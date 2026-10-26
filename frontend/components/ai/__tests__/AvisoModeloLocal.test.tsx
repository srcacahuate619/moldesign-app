// «Modelo LLM no descargado» lo decide el backend, no la comprobación de Tauri.
//
// EL FALLO. El aviso naranja salía siempre, con el modelo en disco y MolChat
// respondiendo (visto por el propietario). Se decidía con `models["llm-qwen15"]`:
// la comprobación de Tauri del archivo de Qwen2.5 1.5B, con su SHA-256, en el
// destino de su descarga. En `tauri dev` ese destino (`target/debug/models/llm`)
// no es donde busca el backend (`models/llm` del repositorio), y la comprobación
// ignora cualquier otro `.gguf` que el investigador haya elegido. Lo que decide
// ahora es la lista de modelos que el backend encuentra y puede cargar.
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "../ChatPanel";

const mocks = vi.hoisted(() => {
  const respaldo = {
    id: "local", name: "Local (llama.cpp)", description: "", requires_api_key: false,
    requires_base_url: false, default_base_url: "", default_model: "", available_models: [] as string[],
    configured: false, active: false,
  };
  return {
    respaldo,
    state: {} as Record<string, unknown>,
    models: {} as Record<string, string>,
  };
});

vi.mock("@/context/AIContext", () => ({
  FALLBACK_PROVIDER: mocks.respaldo,
  useAI: () => ({
    state: mocks.state,
    dispatch: vi.fn(),
    detectStartup: vi.fn(async () => undefined),
    pollResources: vi.fn(async () => undefined),
    sendMessage: vi.fn(async () => ({ ok: true })),
    retryLastTurn: vi.fn(async () => ({ ok: true })),
    stopStreaming: vi.fn(),
    newConversation: vi.fn(async () => undefined),
    fetchConversations: vi.fn(async () => undefined),
    loadConversation: vi.fn(async () => undefined),
    otorgarConsentimiento: vi.fn(async () => true),
    setActiveProvider: vi.fn(async () => undefined),
    updateProviderConfig: vi.fn(async () => null),
    loadProviders: vi.fn(async () => undefined),
    setKeepLoaded: vi.fn(async () => undefined),
  }),
}));

vi.mock("@/hooks/useDownload", () => ({
  useDownload: () => ({ models: mocks.models, startDownload: vi.fn() }),
}));

function local(available_models: string[]) {
  return {
    id: "local", name: "MolChat Local", description: "", requires_api_key: false,
    requires_base_url: false, default_base_url: "", default_model: available_models[0] ?? "",
    available_models, configured: available_models.length > 0, active: true,
  };
}

function abrir(providers: unknown[]) {
  mocks.state = {
    isPanelOpen: true,
    isSettingsOpen: false,
    isStreaming: false,
    streamingContent: "",
    messages: [],
    conversations: [],
    providers,
    destinos: [],
    activeProviderId: "local",
    providerConfigs: {},
    startupMode: "auto_start",
    startupMessage: "",
    warningBanner: null,
    resourceStatus: null,
    moleculeContext: null,
    chatMode: "speed",
    allowWeb: false,
    turnoFallido: null,
  };
  render(<ChatPanel />);
}

describe("el aviso del modelo local", () => {
  beforeEach(() => {
    // Tauri dice que falta el archivo de Qwen2.5 1.5B: es lo que veía el
    // propietario en `tauri dev` con el modelo en el `models/llm` del repo.
    mocks.models = { "llm-qwen15": "missing" };
    // jsdom no implementa el desplazamiento; el panel baja al último mensaje.
    Element.prototype.scrollIntoView = vi.fn();
    global.fetch = vi.fn(async () =>
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } })
    ) as unknown as typeof fetch;
  });

  it("no sale si el backend encuentra un modelo que puede cargar", () => {
    abrir([local(["qwen2.5-1.5b-instruct-q4_k_m.gguf"])]);
    expect(screen.queryByText("Modelo LLM no descargado")).toBeNull();
  });

  it("no sale con otro modelo elegido aunque falte el de Qwen2.5 1.5B", () => {
    abrir([local(["Qwen3.5-4B-Q4_K_M.gguf"])]);
    expect(screen.queryByText("Modelo LLM no descargado")).toBeNull();
  });

  it("sale si el backend no encuentra ninguno", () => {
    mocks.models = { "llm-qwen15": "ready" };
    abrir([local([])]);
    expect(screen.getByText("Modelo LLM no descargado")).toBeInTheDocument();
  });

  it("no afirma nada mientras el backend no ha contestado", () => {
    abrir([mocks.respaldo]);
    expect(screen.queryByText("Modelo LLM no descargado")).toBeNull();
  });
});
