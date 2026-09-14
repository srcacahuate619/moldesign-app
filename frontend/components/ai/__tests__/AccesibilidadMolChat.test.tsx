import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AISettingsModal } from "../AISettingsModal";

const mocks = vi.hoisted(() => ({
  state: {} as Record<string, unknown>,
  dispatch: vi.fn(),
  loadProviders: vi.fn(async () => undefined),
  proveedorLocal: {
    id: "local",
    name: "Local",
    description: "Modelo local",
    requires_api_key: false,
    requires_base_url: false,
    default_base_url: "",
    default_model: "qwen.gguf",
    available_models: [],
    configured: true,
    active: true,
  },
}));

vi.mock("@/context/AIContext", () => ({
  FALLBACK_PROVIDER: mocks.proveedorLocal,
  useAI: () => ({
    state: mocks.state,
    dispatch: mocks.dispatch,
    setActiveProvider: vi.fn(async () => undefined),
    updateProviderConfig: vi.fn(async () => null),
    loadProviders: mocks.loadProviders,
    detectStartup: vi.fn(async () => undefined),
    setKeepLoaded: vi.fn(async () => undefined),
  }),
}));

describe("diálogo de configuración de MolChat", () => {
  beforeEach(() => {
    mocks.dispatch.mockReset();
    mocks.loadProviders.mockClear();
    mocks.state = {
      isSettingsOpen: true,
      providers: [mocks.proveedorLocal],
      activeProviderId: "local",
      providerConfigs: {},
      resourceStatus: null,
    };
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("declara el diálogo, toma el foco, cierra con Escape y restaura el foco", () => {
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const { unmount } = render(<AISettingsModal />);
    const dialog = screen.getByRole("dialog", { name: "Intérprete IA" });
    const close = screen.getByRole("button", { name: "Cerrar configuración de MolChat" });

    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(close).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(mocks.dispatch).toHaveBeenCalledWith({ type: "SET_SETTINGS_OPEN", open: false });

    unmount();
    expect(trigger).toHaveFocus();
    trigger.remove();
  });

  it("muestra los non-2xx del navegador de modelos y autentica la petición", async () => {
    localStorage.setItem("moldesign_auth", JSON.stringify({ token: "session-token" }));
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "denied" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      })
    ) as unknown as typeof fetch;

    render(<AISettingsModal />);

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("HTTP 403"));
    const calls = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.length).toBeGreaterThanOrEqual(2);
    for (const [, init] of calls) {
      expect(init?.headers).toMatchObject({ Authorization: "Bearer session-token" });
    }
  });
});
