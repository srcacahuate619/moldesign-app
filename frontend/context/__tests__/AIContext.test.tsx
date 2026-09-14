// =====================================================================
// Tests para AIContext — Bug A regression + MolChat message lifecycle
// =====================================================================
//
// ANTECEDENTE Bug A (BUILD_GUIDE.md seccion 4):
//
//   Bug: MolChat se abria automaticamente al iniciar y al cambiar de pestana.
//
//   Causa: La funcion `detectStartup()` (AIContext.tsx) abria el panel
//   MolChat en modo "auto_start" Y en cualquier error de red (el backend
//   tarda ~5s en arrancar, error de red -> panel abierto).
//
//   Fix: 2 cambios en AIContext.tsx:
//     1. Solo abrir el panel en modo "notify_fallback", no en "auto_start".
//     2. Eliminar `SET_PANEL_OPEN` del bloque catch (error de red no debe
//        abrir panel).
//
// Estos tests protegen la validez cientifica: si `detectStartup` abre el
// panel en error de red, el usuario podria ver "MolChat inicia igual" como
// si fuera un resultado cientifico real, cuando en realidad el backend no
// esta corriendo. Es una distorsion de la representacion cientifica.
//
// Sub-batch A: MolChat message lifecycle. sendMessage es el componente
// que interpreta los resultados del pipeline para el usuario via SSE.
// Si el parser de streaming ensucia el contenido con tokens corruptos, el
// user lee respuestas de "la IA" que no corresponden a su entrada. Eso es
// bug de validez cientifica, no de UX.

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { type ReactNode } from "react";

import { AIProvider, useAI } from "../AIContext";
import { mockFetch } from "../../vitest.setup";

const authState = vi.hoisted(() => ({
  user: { user_id: "test-user", username: "Test", email: "test@example.com" } as {
    user_id: string;
    username: string;
    email: string;
  } | null,
}));

vi.mock("../../lib/auth", () => ({ useAuth: () => authState }));

beforeEach(() => {
  authState.user = { user_id: "test-user", username: "Test", email: "test@example.com" };
});

describe("AIContext — aislamiento de preferencias por sesión", () => {
  beforeEach(() => {
    global.fetch = vi.fn(async (url: string) => {
      if (url.endsWith("/ai/providers")) return jsonResponse([]);
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch;
  });

  it("cambiar de Alice a Bob limpia conversación y carga las preferencias de Bob", async () => {
    localStorage.setItem("moldesign_chat_mode:user:alice", "reasoning");
    localStorage.setItem("moldesign_allow_web:user:alice", "true");
    localStorage.setItem("moldesign_chat_mode:user:bob", "speed");
    localStorage.setItem("moldesign_allow_web:user:bob", "false");
    authState.user = { user_id: "alice", username: "Alice", email: "alice@example.com" };

    const { result, rerender } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(result.current.state.chatMode).toBe("reasoning"));
    expect(result.current.state.allowWeb).toBe(true);
    act(() => {
      result.current.dispatch({
        type: "ADD_MESSAGE",
        message: { id: "private-alice", role: "user", content: "secreto" },
      });
    });

    authState.user = { user_id: "bob", username: "Bob", email: "bob@example.com" };
    rerender();

    await waitFor(() => expect(result.current.state.chatMode).toBe("speed"));
    expect(result.current.state.allowWeb).toBe(false);
    expect(result.current.state.messages).toEqual([]);
    expect(localStorage.getItem("moldesign_chat_mode:user:alice")).toBe("reasoning");
    expect(localStorage.getItem("moldesign_chat_mode:user:bob")).toBe("speed");
  });

  it("logout elimina el estado visible sin escribir preferencias anónimas", async () => {
    authState.user = { user_id: "alice", username: "Alice", email: "alice@example.com" };
    const { result, rerender } = renderHook(() => useAI(), { wrapper });
    act(() => {
      result.current.dispatch({
        type: "ADD_MESSAGE",
        message: { id: "private", role: "assistant", content: "resultado privado" },
      });
    });

    authState.user = null;
    rerender();

    await waitFor(() => expect(result.current.state.messages).toEqual([]));
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).not.toContain(
      "moldesign_chat_mode:user:null",
    );
  });
});

// Helpers para construir respuestas fetch.

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

// Construye un Response con un ReadableStream SSE real.
// El codigo de sendMessage hace `res.body.getReader()` y lee chunks binarios.
// Mockear getReader() haria que el codigo real no se ejecute (test mock-dirigido).
// En cambio, armamos un ReadableStream con TextEncoder y chunks separados por
// bloques SSE completos (`\n\n`). Esto prueba el comportamiento real del
// buffer y del parser conforme al contrato del backend.
function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
  return new Response(stream, {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

// El componente AIProvider no mounting directo desde el layout (que pide
// 7 providers + 3 Google Fonts + Tauri). AIProvider solo requiere API_URL
// from ../lib/config, que en jsdom default es http://localhost:8010.
//
// IMPORTANTE: AIProvider dispara `loadProviders()` automaticamente en mount
// (useEffect). Eso llamara a fetch(`${API_URL}/ai/providers`). Para no
// contaminar el test, mockeamos fetch con routing por URL: si el path termina
// en /ai/providers, retornamos array vacio; para /ai/startup, devolvemos lo
// que cada test quiera.
//
// Ademas, detectStartup no se dispara automaticamente: ChatPanel.tsx lo
// invoca desde su useEffect. Como no renderizamos ChatPanel, llamamos a
// `result.current.detectStartup()` explicitamente dentro de `act`.

function makeFetchRouting(startupResponse: unknown) {
  return vi.fn(async (url: string) => {
    if (typeof url === "string" && url.endsWith("/ai/providers")) {
      return jsonResponse([]); // array vacio de providers
    }
    if (typeof url === "string" && url.endsWith("/ai/startup")) {
      return jsonResponse(startupResponse);
    }
    // Cualquier otra llamada: fallo explicito (para detectar surprises).
    throw new Error(`Unexpected fetch in test: ${url}`);
  }) as unknown as typeof fetch;
}

function wrapper({ children }: { children: ReactNode }) {
  return <AIProvider>{children}</AIProvider>;
}

describe("AIContext — Bug A regression: detectStartup no abre MolChat en error de red", () => {
  beforeEach(() => {
    // Asegura reset absoluto entre tests.
    mockFetch.mockReset();
  });

  it("NO abre el panel cuando backend responde 200 con mode=auto_start", async () => {
    // Mock: /ai/providers retorna array vacio, /ai/startup Retorna auto_start.
    global.fetch = makeFetchRouting({ mode: "auto_start", reason: "ok" });

    const { result } = renderHook(() => useAI(), { wrapper });

    // detectStartup no se dispara solo; lo invocamos explicitamente.
    await act(async () => {
      await result.current.detectStartup();
    });

    // Esperamos a que el state se actualice con el resultado.
    await waitFor(() => {
      expect(result.current.state.startupMode).toBe("auto_start");
    });

    // REGRESION: el panel NO debe abrirse en auto_start.
    // Antes del fix, AIContext.tsx hacia
    //   if (data.mode === "auto_start" || data.mode === "notify_fallback")
    //     dispatch({ type: "SET_PANEL_OPEN", open: true });
    // Este test rompe si alguien reintroduce la rama auto_start.
    expect(result.current.state.isPanelOpen).toBe(false);
  });

  it("NO abre el panel cuando backend NO responde (error de red)", async () => {
    // Mock: /ai/providers rechaza (simula backend caido en el primer fetch
    // automatico), /ai/startup TAMBIEN rechaza. detectStartup va a caer al
    // catch y hara dispatch con mode=auto_start + mensaje de error.
    global.fetch = vi.fn(async () => {
      throw new Error("NetworkError");
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    await act(async () => {
      await result.current.detectStartup();
    });

    await waitFor(() => {
      expect(result.current.state.startupMode).toBe("auto_start");
    });

    // REGRESION: el bloque catch en detectStartup NO debe abrir el panel.
    // Antes del fix, el catch hacia dispatch({ type: "SET_PANEL_OPEN",
    // open: true }). Este test rompe si alguien reintroduce ese SET_PANEL_OPEN.
    expect(result.current.state.isPanelOpen).toBe(false);

    // Validacion adicional: el mensaje debe indicar que no se pudo conectar
    // (transparencia para el usuario).
    expect(result.current.state.startupMessage).toContain("No se pudo conectar");
  });

  it("SÍ abre el panel cuando backend dice notify_fallback (API keys sin saldo)", async () => {
    // Este test protege la FEATURE ORIGINAL que SI debe funcionar: cuando el
    // backend responde notify_fallback, MolChat SI debe abrirse y mostrar el
    // warning banner. Si esto falla, rompimos el feature original (regresión
    // inversa).
    global.fetch = makeFetchRouting({ mode: "notify_fallback", reason: "API keys sin saldo" });

    const { result } = renderHook(() => useAI(), { wrapper });

    await act(async () => {
      await result.current.detectStartup();
    });

    await waitFor(() => {
      expect(result.current.state.startupMode).toBe("notify_fallback");
    });

    // Feature original: el panel SI debe abrirse.
    expect(result.current.state.isPanelOpen).toBe(true);
    // Y el warning banner debe estar presente (informacion cientifica:
    // el user tiene que saber que MolChat esta en fallback local, no cloud).
    expect(result.current.state.warningBanner).toBeTruthy();
    expect(result.current.state.warningBanner).toContain("modo local");
  });
});

// =====================================================================
// Sub-batch A: MolChat message lifecycle
// =====================================================================
//
// sendMessage, stopStreaming, newConversation, setActiveProvider son el
// flujo critico que interpreta resultados del pipeline via SSE. Si rompe,
// el usuario lee respuestas corruptas como si fueran analisis cientificos.

describe("AIContext — sendMessage SSE lifecycle", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("rechaza si content esta vacio o solo whitespace", async () => {
    // Setup: cualquier fetch call default (loadProviders se dispara en mount).
    global.fetch = vi.fn(async (_url: string) => {
      return jsonResponse([]); // /ai/providers retorna array vacio
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    // Llamar sendMessage con string vacio o whitespace no debe disparar el fetch
    // SSE. La guarda temprana del codigo (linea 401) retorna inmediatamente.
    await act(async () => {
      await result.current.sendMessage("   \t  ");
    });

    // Esperar ticks para que cualquier side effect eventual termine.
    await new Promise((r) => setTimeout(r, 50));

    // Estado: no se agrego mensaje, no esta streaming.
    expect(result.current.state.messages).toHaveLength(0);
    expect(result.current.state.isStreaming).toBe(false);
    // El fetch SSE nunca debio llamarse.
    //
    // Antes se contaba el total de llamadas y se esperaba 1, la de
    // `/ai/providers` en el montaje. Eso ataba la prueba a cuántas sondas hace
    // el contexto al montar: al añadir `/ai/consent` (MOLCHAT-NET-005) empezó a
    // fallar sin que el comportamiento vigilado cambiara. Ahora se comprueba lo
    // que la prueba quiere decir: que no salió ningún turno.
    const llamadas = (global.fetch as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(llamadas.filter(([url]) => String(url).includes("/ai/chat"))).toHaveLength(0);
  });

  it("parsea tokens SSE y agrega mensaje assistant con el contenido acumulado", async () => {
    // 3 chunks que el reader recibe secuencialmente:
    //   "data: Hola\n\n"          (token 1)
    //   "data: mundo\n\n"         (token 2)
    //   "data: [DONE]\n\n"        (terminador SSE)
    //
    // El backend delimita cada evento con una linea vacia. El contenido final
    // debe ser "Holamundo" (sin el [DONE]).
    const sseChunks = ["data: Hola\n\n", "data: mundo\n\n", "data: [DONE]\n\n"];

    // Routing del fetch: /ai/providers -> [], /ai/chat -> SSE, /ai/conversations
    // -> se retorna al final del sendMessage.
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      const isString = typeof url === "string";
      const effectiveUrl = isString ? url : (init && (init as any).url) || "";
      if (effectiveUrl.endsWith("/ai/providers")) {
        return jsonResponse([]);
      }
      if (effectiveUrl.endsWith("/ai/chat")) {
        return sseResponse(sseChunks);
      }
      if (effectiveUrl.endsWith("/ai/conversations")) {
        return jsonResponse([]); // respuesta a fetchConversations al final
      }
      throw new Error(`Unexpected fetch in test: ${effectiveUrl}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    // sendMessage dispara todo el flow async.
    await act(async () => {
      await result.current.sendMessage("hola IA");
    });

    // validaciones:
    // - 2 messages: 1 user ("hola IA"), 1 assistant ("Holamundo")
    // - isStreaming en false (termino)
    // - streamingContent vacio (se reseteo)
    expect(result.current.state.messages).toHaveLength(2);
    expect(result.current.state.messages[0]).toMatchObject({
      role: "user",
      content: "hola IA",
    });
    expect(result.current.state.messages[1]).toMatchObject({
      role: "assistant",
      content: "Holamundo",
    });
    expect(result.current.state.isStreaming).toBe(false);
    expect(result.current.state.streamingContent).toBe("");
  });

  it("maneja advertencias __WARNING__ dentro del stream como warningBanner, no como contenido", async () => {
    // El parser distingue tokens que arrancan con "__WARNING__:" — los saca del
    // contenido y los manda a SET_WARNING_BANNER. Esto protege validez: si un
    // warning pasara como contenido del message, el usuario lo leeria como si
    // fuera respuesta cientifica.
    const sseChunks = [
      "event: warning\ndata: Rate limit exceeded\n\n",
      "data: respuesta-actual\n\n",
      "data: [DONE]\n\n",
    ];

    global.fetch = vi.fn(async (url: string) => {
      if (typeof url === "string" && url.endsWith("/ai/providers")) return jsonResponse([]);
      if (typeof url === "string" && url.endsWith("/ai/chat")) return sseResponse(sseChunks);
      if (typeof url === "string" && url.endsWith("/ai/conversations")) return jsonResponse([]);
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    await act(async () => {
      await result.current.sendMessage("test");
    });

    // El warning banner debe contener "Rate limit exceeded".
    expect(result.current.state.warningBanner).toContain("Rate limit exceeded");
    // El assistant message debe contener "respuesta-actual" (la parte legitima)
    // y NO contener "__WARNING__" o "Rate limit".
    const assistantMsg = result.current.state.messages.find((m) => m.role === "assistant");
    expect(assistantMsg).toBeDefined();
    expect(assistantMsg!.content).toContain("respuesta-actual");
    expect(assistantMsg!.content).not.toContain("__WARNING__");
    expect(assistantMsg!.content).not.toContain("Rate limit");
  });
});

describe("AIContext — stopStreaming aborta y persiste partial", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("stopStreaming agrega mensaje assistant con el partial acumulado", async () => {
    // Stream que se queda colgado (no envia [DONE]) — el reader nunca termina.
    // El usuario llama stopStreaming() manualmente: AbortController aborta el
    // fetch, y el partial ya recibido se persiste como assistant message.
    let controllerRef: AbortController | null = null;
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode("data: partial-1\n\n"));
        controller.enqueue(encoder.encode("data: partial-2\n\n"));
        // NO cerramos — simulamos streaming en progreso.
      },
    });

    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (typeof url === "string" && url.endsWith("/ai/providers")) return jsonResponse([]);
      if (typeof url === "string" && url.endsWith("/ai/chat")) {
        // Capturamos el AbortController para simular el abort luego.
        controllerRef = (init?.signal as any)?.constructor?.name === "AbortController"
          ? (init?.signal as any) as AbortController
          : null;
        return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
      }
      if (typeof url === "string" && url.endsWith("/ai/conversations")) return jsonResponse([]);
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    // Disparamos sendMessage SIN await — necesitamos que siga strameando.
    act(() => {
      result.current.sendMessage("test partial abort");
    });

    // Esperamos a que isStreaming sea true y que algo de contenido se acumule.
    await waitFor(() => {
      expect(result.current.state.isStreaming).toBe(true);
    });

    // Llamamos stopStreaming sin esperar el sendMessage completo (que esta
    // colgado en reader.read()).
    act(() => {
      result.current.stopStreaming();
    });

    // El partial "partial-1partial-2" (mas el "\n" final que el parser descarta
    // por ser linea incompleta). El contenido acumulado en streamingRef.current
    // debe persistir como assistant message.
    await waitFor(() => {
      expect(result.current.state.isStreaming).toBe(false);
    });

    const assistantMsg = result.current.state.messages.find((m) => m.role === "assistant");
    expect(assistantMsg).toBeDefined();
    expect(assistantMsg!.content).toContain("partial-1");
    expect(assistantMsg!.content).toContain("partial-2");
    expect(result.current.state.streamingContent).toBe("");
  });
});

describe("AIContext — setActiveProvider persiste y disparar loadProviders", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("POST a /ai/providers/active y dispatch SET_ACTIVE_PROVIDER", async () => {
    // Mock stateful: trackea qué provider está activo. loadProviders (GET) retorna
    // el array con el provider activo marcado. setActiveProvider (POST) actualiza
    // el estado y loadProviders subsiguiente refleja el cambio.
    let activeProviderId = "local";

    const baseProviders = [
      { id: "local", name: "Local", active: false, configured: true, requires_api_key: false,
        requires_base_url: false, default_base_url: "", default_model: "qwen2",
        available_models: [], env_key: undefined },
      { id: "gemini", name: "Gemini", active: false, configured: false, requires_api_key: true,
        requires_base_url: false, default_base_url: "", default_model: "gemini-flash",
        available_models: [], env_key: "GEMINI_API_KEY" },
    ];

    function providersWithActive() {
      return baseProviders.map(p => ({ ...p, active: p.id === activeProviderId }));
    }

    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (typeof url === "string" && url.endsWith("/ai/providers") && method === "GET") {
        return jsonResponse(providersWithActive());
      }
      if (typeof url === "string" && url.endsWith("/ai/providers/active") && method === "POST") {
        const body = JSON.parse(init?.body as string || "{}");
        activeProviderId = body.provider_id;
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    // Estado inicial: activeProviderId = "local" (default del initialState).
    expect(result.current.state.activeProviderId).toBe("local");

    await act(async () => {
      await result.current.setActiveProvider("gemini");
    });

    // dispatch SET_ACTIVE_PROVIDER cambia el provider activo a "gemini".
    expect(result.current.state.activeProviderId).toBe("gemini");
  });

  it("un non-2xx no cambia el proveedor activo", async () => {
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/ai/providers") && !init?.method) return jsonResponse([]);
      if (url.endsWith("/ai/providers/active")) {
        return jsonResponse({ detail: "denied" }, { status: 403 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    await act(async () => {
      await expect(result.current.setActiveProvider("gemini")).rejects.toThrow("HTTP 403");
    });

    expect(result.current.state.activeProviderId).toBe("local");
  });

  it("un non-2xx no guarda configuración local ni informa éxito", async () => {
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/ai/providers") && !init?.method) return jsonResponse([]);
      if (url.endsWith("/ai/providers/configure")) {
        return jsonResponse({ detail: "invalid" }, { status: 422 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());

    await act(async () => {
      await expect(
        result.current.updateProviderConfig({
          provider_id: "gemini",
          api_key: "invalid",
          base_url: "",
          model: "gemini-flash",
          temperature: 0.5,
        })
      ).rejects.toThrow("HTTP 422");
    });

    expect(result.current.state.providerConfigs.gemini).toBeUndefined();
  });

  it("POST exitoso seguido de recarga 500 conserva el proveedor activo anterior", async () => {
    let providerLoads = 0;
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (url.endsWith("/ai/providers") && method === "GET") {
        providerLoads += 1;
        if (providerLoads === 1) {
          return jsonResponse([
            { id: "local", name: "Local", active: true, configured: true },
          ]);
        }
        return jsonResponse({ detail: "reload failed" }, { status: 500 });
      }
      if (url.endsWith("/ai/providers/active") && method === "POST") {
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(providerLoads).toBe(1));

    await act(async () => {
      await expect(result.current.setActiveProvider("gemini")).rejects.toThrow("HTTP 500");
    });

    expect(result.current.state.activeProviderId).toBe("local");
  });

  it("configuración exitosa seguida de recarga 500 conserva la configuración anterior", async () => {
    let providerLoads = 0;
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (url.endsWith("/ai/providers") && method === "GET") {
        providerLoads += 1;
        if (providerLoads === 1) return jsonResponse([]);
        return jsonResponse({ detail: "reload failed" }, { status: 500 });
      }
      if (url.endsWith("/ai/providers/configure") && method === "POST") {
        return jsonResponse({ ok: true });
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });
    await waitFor(() => expect(providerLoads).toBe(1));
    act(() => {
      result.current.dispatch({
        type: "SET_PROVIDER_CONFIG",
        config: {
          provider_id: "gemini",
          api_key: "old-key",
          base_url: "https://old.example",
          model: "old-model",
          temperature: 0.2,
        },
      });
    });

    await act(async () => {
      await expect(
        result.current.updateProviderConfig({
          provider_id: "gemini",
          api_key: "new-key",
          base_url: "https://new.example",
          model: "new-model",
          temperature: 0.7,
        })
      ).rejects.toThrow("HTTP 500");
    });

    expect(result.current.state.providerConfigs.gemini).toMatchObject({
      api_key: "old-key",
      base_url: "https://old.example",
      model: "old-model",
      temperature: 0.2,
    });
  });
});

describe("AIContext — newConversation resetea estado y clear warning", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("POST a /ai/conversations, dispatch SET_MESSAGES [] y SET_WARNING_BANNER null", async () => {
    // Simulamos estado con 1 message y 1 warning banner (viene de notify_fallback).
    // Despues de newConversation, messages debe ser [] y warning debe ser null.
    global.fetch = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method || "GET";
      if (typeof url === "string" && url.endsWith("/ai/providers") && method === "GET") {
        return jsonResponse([]);
      }
      if (typeof url === "string" && url.endsWith("/ai/startup") && method === "GET") {
        return jsonResponse({ mode: "notify_fallback", reason: "API keys sin saldo" });
      }
      if (typeof url === "string" && url.endsWith("/ai/conversations")) {
        if (method === "POST") {
          // newConversation POST espera { id } en la respuesta
          return jsonResponse({ id: "conv-001" });
        }
        // GET (fetchConversations despues de reset)
        return jsonResponse([]);
      }
      throw new Error(`Unexpected fetch: ${method} ${url}`);
    }) as unknown as typeof fetch;

    const { result } = renderHook(() => useAI(), { wrapper });

    // Prima el estado: dispara detectStartup para que tenga warning banner.
    await act(async () => {
      await result.current.detectStartup();
    });

    // validamos precondition: hay warning banner.
    await waitFor(() => {
      expect(result.current.state.warningBanner).toBeTruthy();
    });
    expect(result.current.state.warningBanner).toContain("modo local");

    // Simulamos un message preexistente agregando manualmente via dispatch.
    act(() => {
      result.current.dispatch({
        type: "ADD_MESSAGE",
        message: { role: "user", content: "old message", id: "old-1" },
      });
    });
    expect(result.current.state.messages).toHaveLength(1);

    // Ejecutamos newConversation.
    await act(async () => {
      await result.current.newConversation();
    });

    // SUT: messages debe ser [], warningBanner debe ser null, activeConversation
    // debe ser el nuevo id "conv-001".
    expect(result.current.state.messages).toHaveLength(0);
    expect(result.current.state.warningBanner).toBeNull();
    expect(result.current.state.activeConversationId).toBe("conv-001");
  });
});
