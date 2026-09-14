// =====================================================================
// El motor cambia de puerto y la aplicación tiene que poder volver a él
// =====================================================================
//
// EL FALLO QUE FIJA. `getApiUrl()` memoriza el puerto —`if (resolved) return
// resolved`— y `ensure_backend` sólo se pregunta una vez, al arrancar. Si el
// backend moría y Rust lo relevantaba en otro puerto del rango 8000-8019, el
// frontend seguía llamando al viejo: `fetch` lanzaba y Moldex decía «no se pudo
// establecer contacto con el motor local» con el motor perfectamente sano.
//
// Y no se podía salir: el «Reintentar» de Moldex vuelve a pedir con la MISMA
// dirección memorizada. El mismo error, tantas veces como se pulse. Lo reportó
// un usuario y el síntoma era exactamente ése: «al presionar reintentar no
// mejora nada».
//
// LO QUE SE PRUEBA AQUÍ, en orden de importancia:
//
//   1. Que se sale del error: puerto nuevo ⇒ la petición llega.
//   2. Que NO se reintenta contra la misma dirección. Un reintento a ciegas
//      duplicaría un POST cuyo destino sí estuviera vivo, y aquí no se puede
//      saber si la petición llegó a entregarse.
//   3. Que diez peticiones cayendo a la vez preguntan UNA.
//   4. Que la recuperación es compartida: quien llame después ya va al bueno.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getJobStatus } from "../api";
import { getApiUrl, resetApiUrl } from "../config";
import { mockFetch, mockTauriInvoke, setTauriEnv } from "../../vitest.setup";

const ESTADO_OK = JSON.stringify({
  task_id: "task-1", status: "PENDING", progress: 0, result: null, error: null,
});

function respuestaOk(): Response {
  return new Response(ESTADO_OK, {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * `mockFetch` esta declarado sin parametros en `vitest.setup`, y aqui hace
 * falta mirar A QUE URL se llama: es lo unico que distingue "fue al puerto
 * viejo" de "fue al nuevo". El molde se confina a esta funcion en vez de
 * repetirlo en cada prueba.
 */
function responderSegunUrl(fn: (url: string) => Promise<Response>): void {
  mockFetch.mockImplementation(
    ((url: unknown) => fn(String(url))) as unknown as () => Promise<Response>,
  );
}

/** Rust responde con `puerto`. Cuenta cuántas veces se le pregunta. */
function motorEnPuerto(puerto: number) {
  mockTauriInvoke.mockImplementation(async (cmd: string) => {
    if (cmd === "ensure_backend") return { state: "ready", port: puerto, detail: null };
    throw new Error(`Unexpected: ${cmd}`);
  });
}

describe("el motor se mudó de puerto", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetApiUrl();
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
    setTauriEnv(true);
  });

  afterEach(() => {
    resetApiUrl();
    setTauriEnv(false);
  });

  it("vuelve a preguntar el puerto y llega al motor nuevo", async () => {
    motorEnPuerto(8000);
    await getApiUrl(); // el arranque memoriza :8000

    motorEnPuerto(8003); // Rust lo relevantó aquí
    const urls: string[] = [];
    responderSegunUrl(async (url) => {
      urls.push(url);
      if (url.includes(":8000")) throw new TypeError("Failed to fetch");
      return respuestaOk();
    });

    await expect(getJobStatus("task-1")).resolves.toMatchObject({ task_id: "task-1" });
    expect(urls[0]).toContain(":8000");
    expect(urls[1]).toContain(":8003");
  });

  it("la recuperación es compartida: la siguiente petición ya nace en el puerto bueno", async () => {
    motorEnPuerto(8000);
    await getApiUrl();
    motorEnPuerto(8003);
    responderSegunUrl(async (url) => {
      if (url.includes(":8000")) throw new TypeError("Failed to fetch");
      return respuestaOk();
    });
    await getJobStatus("task-1");

    // Sin esto, cada llamada pagaría su propio fallo antes de recuperarse.
    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8003");
  });

  it("NO reintenta si el puerto es el mismo: sería el mismo fallo dos veces", async () => {
    motorEnPuerto(8000);
    await getApiUrl();

    mockFetch.mockImplementation(async () => {
      throw new TypeError("Failed to fetch");
    });

    await expect(getJobStatus("task-1")).rejects.toThrow(/error de conexión/i);
    // Una sola entrega intentada. Un reintento a ciegas duplicaría un POST.
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("si el motor no contesta a Rust, se dice; no se inventa un puerto", async () => {
    motorEnPuerto(8000);
    await getApiUrl();

    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("el motor no arrancó");
    });
    mockFetch.mockImplementation(async () => {
      throw new TypeError("Failed to fetch");
    });

    await expect(getJobStatus("task-1")).rejects.toThrow(/error de conexión/i);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("diez peticiones que caen a la vez preguntan UNA sola vez por el puerto", async () => {
    motorEnPuerto(8000);
    await getApiUrl();

    let consultas = 0;
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "ensure_backend") {
        consultas += 1;
        return { state: "ready", port: 8003, detail: null };
      }
      throw new Error(`Unexpected: ${cmd}`);
    });
    responderSegunUrl(async (url) => {
      if (url.includes(":8000")) throw new TypeError("Failed to fetch");
      return respuestaOk();
    });

    await Promise.all(
      Array.from({ length: 10 }, (_, i) => getJobStatus(`task-${i}`)),
    );

    expect(consultas).toBe(1);
  });
});
