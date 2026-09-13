import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999" }));

import { runMmgbsa, runSelectivityStream, saveSelectivityResults } from "../proApi";

function authorizationFromCall(call: unknown[]): string | null {
  const init = call[1] as RequestInit | undefined;
  return new Headers(init?.headers).get("Authorization");
}

describe("autenticación de los módulos profesionales", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.localStorage.setItem("moldesign_auth", JSON.stringify({ token: "token-produccion" }));
    vi.restoreAllMocks();
  });

  it("envía la sesión al ejecutar MM-GBSA", async () => {
    const fetchSpy = vi.fn(async () =>
      new Response(JSON.stringify({ delta_g_total_kcal: -21.4 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = fetchSpy as typeof fetch;

    await runMmgbsa("mol-1");

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(authorizationFromCall(fetchSpy.mock.calls[0])).toBe("Bearer token-produccion");
  });

  it("envía la sesión al stream de selectividad post-docking", async () => {
    const onEvent = vi.fn();
    const fetchSpy = vi.fn(async () =>
      new Response('data: {"type":"complete","selectivity_ratio":4.2}\n\n', {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      }),
    );
    global.fetch = fetchSpy as typeof fetch;

    await runSelectivityStream("mol-2", onEvent);

    expect(authorizationFromCall(fetchSpy.mock.calls[0])).toBe("Bearer token-produccion");
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: "complete", selectivity_ratio: 4.2 }),
    );
  });

  it("combina Authorization con Content-Type en las escrituras JSON", async () => {
    const fetchSpy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = fetchSpy as typeof fetch;

    await saveSelectivityResults("mol-3", { off_targets: [] });

    const init = fetchSpy.mock.calls[0][1];
    expect(init).toBeDefined();
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer token-produccion");
    expect(headers.get("Content-Type")).toBe("application/json");
  });
});
