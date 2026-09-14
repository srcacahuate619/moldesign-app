import { beforeEach, describe, expect, it, vi } from "vitest";

// `resetApiUrl` la usa `api.ts` para revalidar el puerto cuando `fetch` lanza.
// Aquí no hay puerto que revalidar —la dirección es fija— así que no hace nada
// y la revalidación devuelve la misma: exactamente el caso en que NO se
// reintenta. Ver `puertoDelMotor.test.ts`.
vi.mock("../config", () => ({
  getApiUrl: async () => "http://127.0.0.1:9999",
  resetApiUrl: () => {},
}));

import { ApiError, createTargetVariant, getEvaluationResult, getJobStatus, submitEvaluation } from "../api";

describe("contrato de errores HTTP", () => {
  beforeEach(() => window.localStorage.clear());

  it("conserva status y body para que 403 no parezca pérdida de datos", async () => {
    global.fetch = vi.fn(async () => new Response('{"detail":"caso ajeno"}', { status: 403 })) as typeof fetch;

    const error = await getJobStatus("task-private").catch((cause) => cause);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 403, responseBody: '{"detail":"caso ajeno"}' });
    expect(error.message).toContain("HTTP 403");
  });

  it("conserva también los errores 5xx sin intentar reinterpretarlos", async () => {
    global.fetch = vi.fn(async () => new Response("motor roto", { status: 503 })) as typeof fetch;

    await expect(getJobStatus("task-down")).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      responseBody: "motor roto",
    });
  });

  it("distingue un fallo de red de una respuesta HTTP", async () => {
    global.fetch = vi.fn(async () => { throw new TypeError("Failed to fetch"); }) as typeof fetch;

    const error = await getJobStatus("task-offline").catch((cause) => cause);
    expect(error).not.toBeInstanceOf(ApiError);
    expect(error.message).toMatch(/error de conexión/i);
  });

  it("envía la sesión almacenada al consultar la corrida", async () => {
    window.localStorage.setItem("moldesign_auth", JSON.stringify({ token: "token-alice" }));
    const fetchSpy = vi.fn(async () => new Response(JSON.stringify({
      task_id: "task-1", status: "PENDING", progress: 0, result: null, error: null,
    }), { status: 200, headers: { "Content-Type": "application/json" } }));
    global.fetch = fetchSpy as typeof fetch;

    await getJobStatus("task-1");

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://127.0.0.1:9999/evaluation/status/task-1",
      expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer token-alice" }) }),
    );
  });

  it("fija la lectura durable al task_id exacto de la corrida", async () => {
    const fetchSpy = vi.fn(async () => new Response("{}", {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    global.fetch = fetchSpy as typeof fetch;

    await getEvaluationResult("mol-1", "run/1 con espacio");

    expect(fetchSpy).toHaveBeenCalledWith(
      "http://127.0.0.1:9999/evaluation/result/mol-1?task_id=run%2F1%20con%20espacio",
      expect.any(Object),
    );
  });

  it("transporta la cadena comprobada en el submit", async () => {
    const fetchSpy = vi.fn(
      async (_input: RequestInfo | URL, _init?: RequestInit) => new Response("{}", {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    global.fetch = fetchSpy as typeof fetch;

    await submitEvaluation(
      "CCO", "7E2Y", false, undefined, undefined, undefined,
      undefined, undefined, "sha256:" + "a".repeat(64), "R",
    );

    const options = fetchSpy.mock.calls[0]?.[1];
    expect(options).toBeDefined();
    expect(JSON.parse(String(options?.body))).toMatchObject({
      target_pdb_id: "7E2Y",
      chain: "R",
      preflight_fingerprint: "sha256:" + "a".repeat(64),
    });
  });

  it("transporta la receta de una variante al receptor padre exacto", async () => {
    const fetchSpy = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify({ pdb_id: "USR_123456" }), {
      status: 201,
      headers: { "Content-Type": "application/json" },
    }));
    global.fetch = fetchSpy as unknown as typeof fetch;

    await createTargetVariant("USR/parent", {
      name: "Con zinc",
      chain_id: "A",
      grid_center: [1, 2, 3],
      grid_size: [20, 20, 20],
      cofactors_whitelist: ["ZN"],
    });

    const [url, init] = fetchSpy.mock.calls[0]!;
    expect(url).toBe(
      "http://127.0.0.1:9999/targets/USR%2Fparent/variants",
    );
    expect(JSON.parse(String(init?.body))).toMatchObject({
      chain_id: "A",
      cofactors_whitelist: ["ZN"],
    });
  });
});
