// La tarjeta «Avanzado» del Intérprete IA: Qwen3.5 4B en vez de Phi-3.5 Mini.
//
// Decisión del propietario (2026-10-10): el Qwen más reciente de tamaño
// parecido con uso de herramientas. Qwen3.6 sólo salió en 27B y 35B-A3B; el
// candidato es Qwen3.5-4B (Apache-2.0). En el arnés de herramientas de MolChat
// (`scripts/bench_tool_calling`, 21 casos en español, CPU, llama-server b10199)
// acertó 21 de 21, contra 17 de Qwen2.5 1.5B, y es unas 3 veces más lento.
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

const peticiones: { url: string; body?: string }[] = [];

describe("modelos recomendados para descarga local", () => {
  beforeEach(() => {
    peticiones.length = 0;
    mocks.state = {
      isSettingsOpen: true,
      providers: [{
        id: "local", name: "MolChat Local", description: "", requires_api_key: false,
        requires_base_url: false, default_base_url: "", default_model: "", available_models: [],
        configured: false, active: true,
      }],
      activeProviderId: "local",
      providerConfigs: {},
      resourceStatus: null,
    };
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      peticiones.push({ url: String(url), body: init?.body as string | undefined });
      const cuerpo = String(url).includes("/ai/models/download") ? { id: "dl1" } : { models: [], options: [] };
      return new Response(JSON.stringify(cuerpo), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as unknown as typeof fetch;
  });

  it("ofrece Qwen3.5 4B como avanzado y ya no Phi-3.5", () => {
    render(<AISettingsModal />);
    expect(screen.getByText("Qwen3.5 4B (Avanzado)")).toBeInTheDocument();
    expect(screen.queryByText(/Phi-3\.5/)).toBeNull();
  });

  it("descarga el archivo Q4_K_M del repositorio GGUF de Qwen3.5 4B", async () => {
    render(<AISettingsModal />);
    const tarjeta = screen.getByText("Qwen3.5 4B (Avanzado)").closest("div")!.parentElement!;
    fireEvent.click(within(tarjeta).getByRole("button", { name: "Descargar" }));

    await waitFor(() => expect(peticiones.some((p) => p.url.endsWith("/ai/models/download"))).toBe(true));
    const pedido = JSON.parse(peticiones.find((p) => p.url.endsWith("/ai/models/download"))!.body!);
    expect(pedido).toEqual({ model_id: "unsloth/Qwen3.5-4B-GGUF", filename: "Qwen3.5-4B-Q4_K_M.gguf" });
  });
});
