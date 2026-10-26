// Ollama en el modal de MolChat: lo que se enseña es lo medido, no un texto fijo.
//
// LOS FALLOS. (1) El panel decía «Ollama debe estar instalado y en ejecución en
// …» tanto si respondía como si no, y el modelo era un campo libre con
// `gemma3:1b` por defecto, lo hubiera o no: el turno volvía «Error Ollama (404)».
// (2) Al reabrir, el modal enseñaba `localhost` y el modelo por defecto en vez de
// lo que la cuenta tenía guardado. (3) La insignia decía «llama.cpp no
// detectado» cuando el que no respondía era Ollama.
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AISettingsModal } from "../AISettingsModal";
import { ProviderBadge } from "../ProviderBadge";

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

function ollama(extra: Record<string, unknown>) {
  return {
    id: "ollama", name: "Ollama", description: "", requires_api_key: false,
    requires_base_url: true, default_base_url: "http://localhost:11434",
    default_model: "gemma3:1b", available_models: [] as string[], configured: false,
    active: true, model: "gemma3:1b", base_url: "http://localhost:11434", estado: "",
    ...extra,
  };
}

function abrir(proveedor: ReturnType<typeof ollama>) {
  mocks.state = {
    isSettingsOpen: true,
    providers: [proveedor],
    activeProviderId: "ollama",
    providerConfigs: {},
    resourceStatus: null,
  };
  render(<AISettingsModal />);
}

describe("Ollama en el modal", () => {
  beforeEach(() => {
    global.fetch = vi.fn(async () =>
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } })
    ) as unknown as typeof fetch;
  });

  it("si no responde, dice lo que midió el backend", () => {
    const estado = "Ollama no responde en http://localhost:11434 (No se pudo conectar a Ollama: rechazada).";
    abrir(ollama({ estado }));
    expect(screen.getByTestId("estado-ollama")).toHaveTextContent(estado);
  });

  it("si responde, enseña la URL y los modelos instalados, elegibles", () => {
    abrir(ollama({
      configured: true,
      available_models: ["qwen3:4b", "llama3.2:latest"],
      default_model: "qwen3:4b",
      model: "qwen3:4b",
    }));

    expect(screen.getByTestId("estado-ollama")).toHaveTextContent(
      "Ollama responde en http://localhost:11434 · 2 modelos instalados.",
    );
    expect(screen.getByRole("button", { name: "qwen3:4b" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: "llama3.2:latest" }));
    expect(screen.getByDisplayValue("llama3.2:latest")).toBeInTheDocument();
  });

  it("al reabrir enseña la URL y el modelo guardados, no los de por defecto", () => {
    abrir(ollama({
      configured: true,
      available_models: ["qwen3:4b"],
      default_model: "qwen3:4b",
      model: "qwen3:4b",
      base_url: "http://192.168.1.20:11434",
    }));

    expect(screen.getByDisplayValue("http://192.168.1.20:11434")).toBeInTheDocument();
    expect(screen.getByDisplayValue("qwen3:4b")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("http://localhost:11434")).toBeNull();
  });
});

describe("la insignia de Ollama", () => {
  it("no habla de llama.cpp cuando el que falta es Ollama", () => {
    render(
      <ProviderBadge
        provider={ollama({ estado: "Ollama no responde en http://localhost:11434." })}
        isStreaming={false}
        resourceStatus={null}
        destino={{
          provider_id: "ollama", name: "Ollama", host: "localhost", url: "http://localhost:11434",
          es_remoto: false, huella: "ollama@localhost", activo: true, consentido: true, otorgado_en: null,
        }}
      />,
    );
    expect(screen.getByText("Ollama no disponible")).toBeInTheDocument();
    expect(screen.queryByText(/llama\.cpp/)).toBeNull();
  });
});
