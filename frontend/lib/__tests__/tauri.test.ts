// =====================================================================
// Tests del puente ÚNICO con Tauri
// =====================================================================
//
// POR QUÉ EXISTE ESTE ARCHIVO. Antes había dos mecanismos distintos —uno en
// `DownloadProvider`, otro en el repositorio de casos— y los dos hacían
// `await import("@tauri-apps/api/core")`. Ese paquete NO está instalado: sólo
// está `@tauri-apps/cli`. El import fallaba siempre, el `catch` lo convertía en
// "Tauri no disponible", y nadie se enteraba porque ningún test invocaba de
// verdad. Un puente roto que se comporta como un puente ausente es exactamente
// el fallo que no se detecta solo.
//
// Ahora hay UNA abstracción sobre `window.__TAURI__.core.invoke` —lo que
// inyecta el runtime porque `tauri.conf.json` declara `withGlobalTauri: true`—
// y estos tests demuestran una invocación real a través de ella.

import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  invoke,
  isDesktopRuntime,
  isTauriAvailable,
  listen,
  tauriBridgeSmokeTest,
  TauriBridgeError,
} from "../tauri";
import { mockTauriInvoke, setTauriEnv } from "../../vitest.setup";

describe("detección del puente", () => {
  beforeEach(() => setTauriEnv(false));

  it("sin runtime, no hay puente ni escritorio", () => {
    expect(isTauriAvailable()).toBe(false);
    expect(isDesktopRuntime()).toBe(false);
  });

  it("con runtime, hay puente y escritorio", () => {
    setTauriEnv(true);
    expect(isTauriAvailable()).toBe(true);
    expect(isDesktopRuntime()).toBe(true);
  });

  it("distingue «runtime presente» de «puente usable»", () => {
    // Es el caso que rompía en silencio: el objeto global existe pero sin
    // `core.invoke`, por ejemplo si se desactivara `withGlobalTauri`.
    (window as unknown as Record<string, unknown>).__TAURI__ = {};
    (window as unknown as Record<string, unknown>).__TAURI_INTERNALS__ = {};
    expect(isDesktopRuntime()).toBe(true);
    expect(isTauriAvailable()).toBe(false);
  });
});

describe("invoke", () => {
  beforeEach(() => setTauriEnv(false));

  it("lanza un error explícito si no hay puente, en vez de degradar en silencio", async () => {
    await expect(invoke("case_read", { caseId: "x" })).rejects.toBeInstanceOf(TauriBridgeError);
    await expect(invoke("case_read")).rejects.toThrowError(/aplicación de escritorio/i);
  });

  it("invoca DE VERDAD a través de window.__TAURI__.core.invoke", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async (cmd: string, args?: Record<string, unknown>) => {
      if (cmd === "case_list_authorized") return [{ case_id: "abc", path: "/tmp/abc", available: true }];
      throw new Error(`comando inesperado: ${cmd} ${JSON.stringify(args)}`);
    });

    const result = await invoke<Array<{ case_id: string }>>("case_list_authorized");
    expect(mockTauriInvoke).toHaveBeenCalledWith("case_list_authorized", undefined);
    expect(result[0].case_id).toBe("abc");
  });

  it("propaga el mensaje de error de Rust sin envolverlo", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("UNAUTHORIZED: el caso no está autorizado en este equipo.");
    });
    await expect(invoke("case_read", { caseId: "x" })).rejects.toThrowError(/^UNAUTHORIZED:/);
  });

  it("pasa los argumentos tal cual al comando", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async () => null);
    await invoke("case_write", { caseId: "abc", contents: "{}" });
    expect(mockTauriInvoke).toHaveBeenCalledWith("case_write", { caseId: "abc", contents: "{}" });
  });
});

describe("listen", () => {
  beforeEach(() => setTauriEnv(false));

  it("devuelve un unlisten inerte si no hay puente", async () => {
    const unlisten = await listen("download:progress", vi.fn());
    expect(typeof unlisten).toBe("function");
    expect(() => unlisten()).not.toThrow();
  });
});

describe("smoke test del puente", () => {
  beforeEach(() => setTauriEnv(false));

  it("en web informa de que no hay puente, y que es lo esperado", async () => {
    const result = await tauriBridgeSmokeTest();
    expect(result.available).toBe(false);
    expect(result.invoked).toBe(false);
    expect(result.detail).toMatch(/entorno web/i);
  });

  it("en escritorio invoca un comando real y lo reporta", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "case_list_authorized") return [];
      throw new Error(`comando inesperado: ${cmd}`);
    });
    const result = await tauriBridgeSmokeTest();
    expect(result.available).toBe(true);
    expect(result.invoked).toBe(true);
    expect(result.detail).toMatch(/Puente operativo/);
  });

  it("distingue «no hay puente» de «el puente falló»", async () => {
    setTauriEnv(true);
    mockTauriInvoke.mockImplementation(async () => {
      throw new Error("IO_ERROR: registro ilegible");
    });
    const result = await tauriBridgeSmokeTest();
    expect(result.available).toBe(true);
    expect(result.invoked).toBe(false);
    expect(result.detail).toMatch(/la invocación falló/i);
  });
});
