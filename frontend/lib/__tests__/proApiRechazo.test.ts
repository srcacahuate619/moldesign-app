import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999" }));

import { ProApiError, dockSingleAntiTarget } from "../proApi";

// AMP-10. Un 409 («la corrida cambió») no es un fallo de cálculo: el panel de
// selectividad necesita distinguirlo para conservar lo registrado. El rechazo
// sigue siendo un `Error` con el mismo mensaje del backend; ahora además lleva
// el código HTTP.
describe("rechazos del backend en los módulos profesionales", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("un 409 llega como ProApiError con status y el detalle del backend", async () => {
    global.fetch = vi.fn(async () =>
      new Response(JSON.stringify({ detail: "La corrida cambió; no se calcula selectividad para otra evaluación." }), {
        status: 409,
        headers: { "Content-Type": "application/json" },
      }),
    ) as typeof fetch;

    const fallo = await dockSingleAntiTarget("mol-1", "5VA1").catch((e) => e);

    expect(fallo).toBeInstanceOf(ProApiError);
    expect(fallo).toBeInstanceOf(Error);
    expect(fallo.status).toBe(409);
    expect(fallo.message).toBe("La corrida cambió; no se calcula selectividad para otra evaluación.");
  });

  it("sin cuerpo útil el mensaje cae al código y el status se conserva", async () => {
    global.fetch = vi.fn(async () => new Response("", { status: 500, statusText: "Internal Server Error" })) as typeof fetch;
    const fallo = await dockSingleAntiTarget("mol-1", "5VA1").catch((e) => e);
    expect(fallo.status).toBe(500);
    expect(fallo.message).toContain("500");
  });
});
