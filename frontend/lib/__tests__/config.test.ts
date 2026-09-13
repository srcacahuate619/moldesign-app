// =====================================================================
// Tests de la dirección del backend — una sola fuente para el puerto
// =====================================================================
//
// EL FALLO QUE FIJAN. `lib/config.ts` exportaba `API_URL` como una constante de
// módulo con `http://127.0.0.1:8000` dentro. Rust elige el primer puerto libre
// del rango 8000-8019, así que con 8000 ocupado por cualquier otro proceso el
// backend quedaba en 8001 y toda la aplicación —REST, SSE, descargas, PDF—
// seguía hablando con 8000. El arranque «funcionaba» y la evaluación fallaba
// sin causa visible.
//
// Lo que se prueba aquí es la precedencia (Rust manda en escritorio), que no se
// memoriza un fallo —reintentar tiene que poder cambiar el resultado— y que los
// enlaces pintados en render se enteran cuando llega el puerto real.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DEFAULT_API_URL,
  apiUrlSnapshot,
  getApiUrl,
  resetApiUrl,
  setApiUrlFromPort,
  subscribeApiUrl,
} from "../config";
import { mockTauriInvoke, setTauriEnv } from "../../vitest.setup";

describe("dirección del backend", () => {
  beforeEach(() => {
    resetApiUrl();
    mockTauriInvoke.mockReset();
  });

  afterEach(() => {
    resetApiUrl();
    setTauriEnv(false);
  });

  it("en navegador usa el valor por defecto sin preguntar a nadie", async () => {
    await expect(getApiUrl()).resolves.toBe(DEFAULT_API_URL);
    expect(mockTauriInvoke).not.toHaveBeenCalled();
  });

  it("en escritorio manda el puerto que devuelve Rust", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "ensure_backend") return { state: "ready", port: 8003, detail: null };
      throw new Error(`Unexpected: ${cmd}`);
    });

    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8003");
  });

  it("no pregunta dos veces: las llamadas concurrentes comparten una resolución", async () => {
    setTauriEnv(true);
    let calls = 0;
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "ensure_backend") {
        calls += 1;
        return { state: "ready", port: 8004, detail: null };
      }
      throw new Error(`Unexpected: ${cmd}`);
    });

    // Media aplicación arrancando a la vez no puede producir media docena de
    // invocaciones al puente.
    const urls = await Promise.all([getApiUrl(), getApiUrl(), getApiUrl()]);
    expect(urls).toEqual([
      "http://127.0.0.1:8004",
      "http://127.0.0.1:8004",
      "http://127.0.0.1:8004",
    ]);
    expect(calls).toBe(1);

    // Y una vez resuelto, ya no se vuelve a preguntar nunca.
    await getApiUrl();
    expect(calls).toBe(1);
  });

  it("un arranque fallido NO se memoriza: el reintento puede cambiarlo", async () => {
    setTauriEnv(true);
    let attempt = 0;
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd !== "ensure_backend") throw new Error(`Unexpected: ${cmd}`);
      attempt += 1;
      if (attempt === 1) throw new Error("el motor no arrancó");
      return { state: "ready", port: 8009, detail: null };
    });

    // En escritorio NO se adivina 8000: podría pertenecer a otro producto.
    await expect(getApiUrl()).rejects.toThrow("el motor no arrancó");
    // Y el segundo ya encuentra el puerto real.
    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8009");
  });

  it("un estado sin puerto utilizable no se acepta como dirección", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "ensure_backend") {
        return { state: "health_failed", port: null, detail: "no pasó el health" };
      }
      throw new Error(`Unexpected: ${cmd}`);
    });

    await expect(getApiUrl()).rejects.toThrow("no pasó el health");
  });

  it("acepta el contrato viejo: un número suelto sigue siendo un puerto", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "ensure_backend") return 8012;
      throw new Error(`Unexpected: ${cmd}`);
    });

    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8012");
  });

  it("avisa a los enlaces pintados en render cuando llega el puerto real", () => {
    // Un `href` a un PDF se construye en render y no puede esperar a una
    // promesa. Sin la suscripción se quedaría apuntando a 8000 para siempre.
    const seen: Array<string | null> = [];
    const unsubscribe = subscribeApiUrl((url) => seen.push(url));

    // Fuera de escritorio la resolución es inmediata, así que el primer aviso
    // es el propio valor por defecto: en navegador ESA es la dirección real, no
    // un marcador de posición.
    expect(apiUrlSnapshot()).toBe(DEFAULT_API_URL);
    setApiUrlFromPort(8005);

    expect(seen).toEqual([DEFAULT_API_URL, "http://127.0.0.1:8005"]);
    expect(apiUrlSnapshot()).toBe("http://127.0.0.1:8005");

    unsubscribe();
    setApiUrlFromPort(8006);
    // Tras darse de baja no llegan más avisos.
    expect(seen).toEqual([DEFAULT_API_URL, "http://127.0.0.1:8005"]);
  });

  it("en Tauri un enlace queda sin destino hasta conocer el puerto real", () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("motor todavía no disponible");
    });

    expect(apiUrlSnapshot()).toBeNull();
    setApiUrlFromPort(8014);
    expect(apiUrlSnapshot()).toBe("http://127.0.0.1:8014");
  });

  it("ignora una resolución tardía del arranque anterior después de reintentar", async () => {
    setTauriEnv(true);
    let resolveOld!: (value: unknown) => void;
    mockTauriInvoke.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveOld = resolve;
        }),
    );

    const oldResolution = getApiUrl();
    // El proveedor del motor reinicia y publica el puerto de la corrida nueva.
    resetApiUrl();
    setApiUrlFromPort(8016);
    resolveOld({ state: "ready", port: 8002, detail: null });

    // La promesa antigua puede completar para su llamador original, pero no
    // debe volver a contaminar el estado compartido de la aplicación.
    await expect(oldResolution).resolves.toBe("http://127.0.0.1:8002");
    expect(apiUrlSnapshot()).toBe("http://127.0.0.1:8016");
  });

  it("no notifica si el valor no ha cambiado", () => {
    const seen: Array<string | null> = [];
    setApiUrlFromPort(8008);
    const unsubscribe = subscribeApiUrl((url) => seen.push(url));
    setApiUrlFromPort(8008);
    expect(seen).toEqual([]);
    unsubscribe();
  });

  it("ignora un puerto imposible en vez de fabricar una URL rota", () => {
    setApiUrlFromPort(8010);
    setApiUrlFromPort(0);
    setApiUrlFromPort(-1);
    expect(apiUrlSnapshot()).toBe("http://127.0.0.1:8010");
  });

  it("`getApiUrl` es la vía para pedir, y devuelve lo ya resuelto sin volver a invocar", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("no debería preguntarse: el puerto ya se conoce");
    });
    setApiUrlFromPort(8013);
    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8013");
    expect(mockTauriInvoke).not.toHaveBeenCalled();
  });
});
