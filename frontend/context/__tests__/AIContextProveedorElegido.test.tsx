// El proveedor que se ve es el que responde.
//
// EL FALLO. Tres sitios cambiaban el proveedor activo a «local» sólo en la
// interfaz, sin decírselo al backend:
//   · `detectStartup` con `auto_start`, y el modal lo llama 500 ms después de
//     guardar: elegir Ollama o una clave de API volvía a «local» en pantalla;
//   · el botón «Abrir chat» de Opciones;
// y el chat enviaba `provider_id: null` cuando la interfaz decía «local», así
// que el backend usaba el activo de la cuenta. Resultado: la insignia decía
// «Los datos se quedan en esta máquina» mientras respondía Ollama, o MolChat
// bloqueaba cada turno de Claude por falta de consentimiento sin enseñar la
// barra «Autorizar» (que se calcula para el proveedor que se ve).
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { act, renderHook, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AIProvider, useAI } from "../AIContext";

// Un objeto estable: un usuario nuevo en cada render relanza el efecto de sesión.
const sesion = vi.hoisted(() => ({ user: { user_id: "test-user", username: "Test", email: "t@example.com" } }));
vi.mock("../../lib/auth", () => ({ useAuth: () => sesion }));

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

function sse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(
    new ReadableStream<Uint8Array>({
      start(c) {
        for (const chunk of chunks) c.enqueue(encoder.encode(chunk));
        c.close();
      },
    }),
    { status: 200, headers: { "Content-Type": "text/event-stream" } },
  );
}

const PROVEEDORES = [
  {
    id: "local", name: "MolChat Local", description: "", requires_api_key: false,
    requires_base_url: false, default_base_url: "", default_model: "q.gguf",
    available_models: ["q.gguf"], configured: true, active: false,
  },
  {
    id: "claude", name: "Claude (Anthropic)", description: "", requires_api_key: true,
    requires_base_url: false, default_base_url: "", default_model: "claude-x",
    available_models: [], configured: true, active: true,
  },
];

const cuerposDeChat: Record<string, unknown>[] = [];

function wrapper({ children }: { children: ReactNode }) {
  return <AIProvider>{children}</AIProvider>;
}

describe("el proveedor activo no cambia a espaldas del backend", () => {
  beforeEach(() => {
    cuerposDeChat.length = 0;
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/ai/providers")) return json(PROVEEDORES);
      if (url.endsWith("/ai/consent")) return json({ destinos: [] });
      if (url.endsWith("/ai/conversations")) return json([]);
      if (url.endsWith("/ai/startup")) {
        return json({
          mode: "auto_start",
          reason: "No consulté los proveedores cloud configurados (Claude): su destino no está autorizado.",
        });
      }
      if (url.endsWith("/ai/chat")) {
        cuerposDeChat.push(JSON.parse(String(init?.body)));
        return sse(["data: hola\n\n", "data: [DONE]\n\n"]);
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch;
  });

  it("auto_start no devuelve a «local» la elección de la cuenta", async () => {
    const { result } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(result.current.state.activeProviderId).toBe("claude"));

    await act(async () => {
      await result.current.detectStartup();
    });

    expect(result.current.state.startupMode).toBe("auto_start");
    expect(result.current.state.activeProviderId).toBe("claude");
  });

  it("el turno nombra el proveedor que se ve, también «local»", async () => {
    const { result } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(result.current.state.activeProviderId).toBe("claude"));
    act(() => result.current.dispatch({ type: "SET_ACTIVE_PROVIDER", id: "local" }));

    await act(async () => {
      await result.current.sendMessage("hola");
    });

    expect(cuerposDeChat).toHaveLength(1);
    expect(cuerposDeChat[0].provider_id).toBe("local");
  });
});

describe("abrir el chat desde Opciones no cambia de proveedor", () => {
  it("el botón no despacha SET_ACTIVE_PROVIDER", () => {
    const aqui = dirname(fileURLToPath(import.meta.url));
    const opciones = readFileSync(resolve(aqui, "..", "..", "components", "OptionsPanel.tsx"), "utf8");
    expect(opciones).not.toContain("SET_ACTIVE_PROVIDER");
  });
});
