import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999" }));

import { getGpuStatus, runMmgbsa } from "../proApi";

// ─────────────────────────────────────────────────────────────────────────
// «MM-GBSA calcula tres minutos y termina en Failed to fetch»
//
// El calculo no llegaba a correr. `customFetch` reintentaba CUALQUIER peticion
// 60 veces con un segundo de espera, asi que un error de red instantaneo
// tardaba mas de un minuto en aparecer —y aparecia con el texto crudo del
// navegador, que no dice nada—.
//
// Lo grave era lo otro: `POST /pro/mmgbsa` lanza una minimizacion de OpenMM en
// el equipo del usuario. Si la conexion se cortaba DESPUES de que el backend
// hubiera recibido la peticion, el navegador da el mismo error que si nunca
// hubiera salido, y el bucle mandaba otras 59.
//
// La regla nueva se apoya en una pregunta que si se puede contestar: se sondea
// `/health`. Si el motor no contesta, la peticion no llego a nadie y repetirla
// es seguro. Si contesta, fallo esta operacion, y un POST no se repite.
// ─────────────────────────────────────────────────────────────────────────

const OK_MMGBSA = () =>
  new Response(JSON.stringify({ delta_g_total_kcal: -21.4 }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

describe("reintentos de proApi", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("no repite un POST caro cuando el motor esta vivo", async () => {
    const llamadas: string[] = [];
    global.fetch = vi.fn(async (url: unknown, init?: RequestInit) => {
      const u = String(url);
      llamadas.push(u);
      if (u.endsWith("/health")) return new Response("{}", { status: 200 });
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    await expect(runMmgbsa("mol-1")).rejects.toThrow(/se interrumpió/);

    const intentosMmgbsa = llamadas.filter((u) => u.includes("/pro/mmgbsa/"));
    expect(intentosMmgbsa).toHaveLength(1);
  });

  it("el mensaje distingue «se cayo a mitad» de «no arranco»", async () => {
    global.fetch = vi.fn(async (url: unknown) => {
      if (String(url).endsWith("/health")) return new Response("{}", { status: 200 });
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    // Ni el usuario ni nosotros ganamos nada leyendo «Failed to fetch».
    await expect(runMmgbsa("mol-1")).rejects.toThrow(/El motor sigue en pie/);
  });

  it("si el motor no contesta, si repite el POST: no lo proceso nadie", async () => {
    // El backend esta arrancando: `/health` no contesta durante los dos
    // primeros fallos y el POST entra al tercer intento.
    let intentos = 0;
    global.fetch = vi.fn(async (url: unknown) => {
      const u = String(url);
      if (u.endsWith("/health")) throw new TypeError("Failed to fetch");
      intentos++;
      if (intentos >= 3) return OK_MMGBSA();
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    await expect(runMmgbsa("mol-1")).resolves.toMatchObject({ delta_g_total_kcal: -21.4 });
    expect(intentos).toBe(3);
  });

  it("un GET si se repite aunque el motor este vivo", async () => {
    let intentos = 0;
    global.fetch = vi.fn(async (url: unknown) => {
      const u = String(url);
      if (u.endsWith("/health")) return new Response("{}", { status: 200 });
      intentos++;
      if (intentos >= 2) {
        return new Response(JSON.stringify({ openmm_gpu: false, torch_cuda: false, platforms: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    await expect(getGpuStatus()).resolves.toMatchObject({ openmm_gpu: false });
    expect(intentos).toBe(2);
  });

  it("cuando el motor no arranca, lo dice en vez de culpar a la operacion", async () => {
    global.fetch = vi.fn(async () => {
      throw new TypeError("Failed to fetch");
    }) as unknown as typeof fetch;

    // Con 30 intentos y 1 s de espera esto tardaria medio minuto en tiempo
    // real; el reloj falso lo resuelve sin esperar.
    vi.useFakeTimers();
    const promesa = runMmgbsa("mol-1").catch((e: Error) => e);
    await vi.runAllTimersAsync();
    const error = (await promesa) as Error;
    vi.useRealTimers();

    expect(error).toBeInstanceOf(Error);
    expect(error.message).toMatch(/no responde/);
    expect(error.message).toMatch(/terminó de arrancar/);
  });
});
