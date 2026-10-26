// =====================================================================
// Una descarga por módulo: la barra de ESMFold ya no avanza y retrocede
// =====================================================================
//
// EL FALLO (visto por el propietario, 2026-10-10): la barra de la descarga de
// ESMFold avanzaba y retrocedía una y otra vez hasta terminar. Rust emite un
// contador que sólo crece, así que una barra que retrocede son DOS descargas
// del mismo archivo. Y había tres caminos para arrancar la segunda, porque la
// interfaz volvía a ofrecer «Descargar» con Rust todavía bajando:
//
//   · «Verificar instalación» a mitad de descarga: mira el archivo final, que
//     aún no existe, y pisaba el «descargando» con un «no instalado»;
//   · la comprobación del arranque, que terminaba después de empezar una
//     descarga y la pisaba igual;
//   · recargar la ventana: la interfaz olvidaba la descarga y Rust la seguía.
//
// Rust ya no acepta una segunda descarga del mismo módulo (`downloader.rs`,
// con sus pruebas). Éstas fijan la parte de la interfaz.

import { act, renderHook, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { beforeEach, describe, expect, it } from "vitest";

import { useDownload } from "../../hooks/useDownload";
import { DownloadProvider, fundirComprobacion } from "../DownloadProvider";
import { mockFetch, mockTauriInvoke, setTauriEnv } from "../../vitest.setup";
import { ACTIVITY_NOTIFICATION_EVENT, type ActivityNotification } from "../../lib/activityNotifications";

type Oyente = (e: { payload: unknown }) => void;

const ESMFOLD = "esmfold-weights";
const TOTAL = 8_442_062_570;

function wrapper({ children }: { children: ReactNode }) {
  return <DownloadProvider>{children}</DownloadProvider>;
}

/** Tauri de prueba que guarda los oyentes para poder emitir eventos de Rust. */
function tauriConEventos(): Record<string, Oyente[]> {
  setTauriEnv(true);
  const oyentes: Record<string, Oyente[]> = {};
  (window as unknown as { __TAURI__: { event: { listen: unknown } } }).__TAURI__.event.listen =
    async (evento: string, oyente: Oyente) => {
      (oyentes[evento] ??= []).push(oyente);
      return () => { oyentes[evento] = (oyentes[evento] ?? []).filter((o) => o !== oyente); };
    };
  return oyentes;
}

function emitir(oyentes: Record<string, Oyente[]>, evento: string, payload: unknown) {
  act(() => { for (const oyente of oyentes[evento] ?? []) oyente({ payload }); });
}

function progreso(bytes: number) {
  return { model_id: ESMFOLD, bytes_downloaded: bytes, total_bytes: TOTAL, speed_bytes_per_sec: 1 };
}

describe("una descarga por módulo", () => {
  let descargas: number;
  let activos: string[];
  let soltar: (() => void) | null;

  beforeEach(() => {
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
    descargas = 0;
    activos = [];
    soltar = null;
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "verify_model") return false;
      if (cmd === "file_exists") return false;
      if (cmd === "active_downloads") return activos;
      if (cmd === "download_model") {
        descargas += 1;
        return new Promise<void>((resolve) => { soltar = resolve; });
      }
      throw new Error(`Unexpected: ${cmd}`);
    });
  });

  it("«Verificar instalación» a mitad de descarga no devuelve el botón de descargar", async () => {
    tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    act(() => { void result.current.startDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));

    // El archivo final aún no existe: verify_model dice «falta».
    await act(async () => { await result.current.checkModules(); });
    expect(result.current.models[ESMFOLD]).toBe("downloading");
  });

  it("un segundo clic no arranca otra descarga del mismo archivo", async () => {
    tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    act(() => {
      void result.current.startDownload(ESMFOLD);
      void result.current.startDownload(ESMFOLD);
    });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));
    act(() => { void result.current.startDownload(ESMFOLD); });
    expect(descargas).toBe(1);

    await act(async () => { soltar?.(); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("ready"));
  });

  it("al recargar la ventana retoma la descarga que Rust sigue haciendo", async () => {
    activos = [ESMFOLD];
    const oyentes = tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    // El disco dice «falta» (el archivo final no existe todavía), Rust dice «bajando».
    expect(result.current.models[ESMFOLD]).toBe("downloading");
    emitir(oyentes, "download:progress", progreso(4_000_000_000));
    expect(result.current.progress[ESMFOLD]?.bytes_downloaded).toBe(4_000_000_000);

    // Sin promesa propia, el final llega por el evento.
    emitir(oyentes, "download:complete", { model_id: ESMFOLD, success: true, error: null });
    expect(result.current.models[ESMFOLD]).toBe("ready");
    expect(result.current.progress[ESMFOLD]).toBeUndefined();
  });

  it("la barra no retrocede aunque llegue un contador menor", async () => {
    const oyentes = tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));
    act(() => { void result.current.startDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));

    emitir(oyentes, "download:progress", progreso(3_000_000_000));
    emitir(oyentes, "download:progress", progreso(2_900_000_000));
    expect(result.current.progress[ESMFOLD]?.bytes_downloaded).toBe(3_000_000_000);
    emitir(oyentes, "download:progress", progreso(3_100_000_000));
    expect(result.current.progress[ESMFOLD]?.bytes_downloaded).toBe(3_100_000_000);
  });

  it("si Rust ya baja el módulo, la interfaz se engancha en vez de marcar un error", async () => {
    const oyentes = tauriConEventos();
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "verify_model") return false;
      if (cmd === "active_downloads") return activos;
      if (cmd === "download_model") {
        activos = [ESMFOLD];
        throw `Ya hay una descarga en curso de este módulo: ${ESMFOLD}`;
      }
      throw new Error(`Unexpected: ${cmd}`);
    });
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    await act(async () => { await result.current.startDownload(ESMFOLD); });
    expect(result.current.models[ESMFOLD]).toBe("downloading");
    emitir(oyentes, "download:complete", { model_id: ESMFOLD, success: true, error: null });
    expect(result.current.models[ESMFOLD]).toBe("ready");
  });

  it("el final de una descarga cancelada no pisa la que acaba de empezar", async () => {
    const oyentes = tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));
    act(() => { void result.current.startDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));

    // Rust avisa del final de la anterior, cancelada, cuando la nueva ya corre.
    emitir(oyentes, "download:complete", { model_id: ESMFOLD, success: false, error: "Descarga cancelada por el usuario" });
    expect(result.current.models[ESMFOLD]).toBe("downloading");
  });

  it("un fallo de una descarga retomada llega por el evento y se dice", async () => {
    activos = [ESMFOLD];
    const oyentes = tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));
    emitir(oyentes, "download:complete", { model_id: ESMFOLD, success: false, error: "SHA-256 mismatch" });
    expect(result.current.models[ESMFOLD]).toBe("error");
  });
});

describe("descargar de nuevo un modelo instalado", () => {
  beforeEach(() => {
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
  });

  it("cancelarla no lo desinstala: el archivo anterior sigue en disco", async () => {
    let rechazar: (motivo: unknown) => void = () => {};
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\app\resources";
      if (cmd === "verify_model") return true;
      if (cmd === "active_downloads") return [];
      if (cmd === "download_model") return new Promise<void>((_resolve, reject) => { rechazar = reject; });
      if (cmd === "cancel_download") { rechazar("Descarga cancelada por el usuario"); return undefined; }
      throw new Error(`Unexpected: ${cmd}`);
    });
    tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("ready"));

    act(() => { void result.current.startDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));
    await act(async () => { await result.current.cancelDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("ready"));
  });

  it("cancelar una descarga nueva sí la deja sin instalar", async () => {
    let rechazar: (motivo: unknown) => void = () => {};
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\app\resources";
      if (cmd === "verify_model") return false;
      if (cmd === "active_downloads") return [];
      if (cmd === "download_model") return new Promise<void>((_resolve, reject) => { rechazar = reject; });
      if (cmd === "cancel_download") { rechazar("Descarga cancelada por el usuario"); return undefined; }
      throw new Error(`Unexpected: ${cmd}`);
    });
    tauriConEventos();
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("missing"));
    act(() => { void result.current.startDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("downloading"));
    await act(async () => { await result.current.cancelDownload(ESMFOLD); });
    await waitFor(() => expect(result.current.models[ESMFOLD]).toBe("missing"));
  });
});

describe("avisos de la campana", () => {
  beforeEach(() => {
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
  });

  it("empezar y terminar una descarga avisa a la campana en la misma entrada", async () => {
    let soltar: () => void = () => {};
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\app\resources";
      if (cmd === "verify_model") return false;
      if (cmd === "active_downloads") return [];
      if (cmd === "download_model") return new Promise<void>((resolve) => { soltar = resolve; });
      throw new Error(`Unexpected: ${cmd}`);
    });
    tauriConEventos();
    const recibidos: ActivityNotification[] = [];
    const oir = (e: WindowEventMap[typeof ACTIVITY_NOTIFICATION_EVENT]) => recibidos.push(e.detail);
    window.addEventListener(ACTIVITY_NOTIFICATION_EVENT, oir);
    try {
      const { result } = renderHook(() => useDownload(), { wrapper });
      await waitFor(() => expect(result.current.initialized).toBe(true));
      // Instalado o no, al arrancar no hay nada que avisar.
      expect(recibidos).toEqual([]);

      act(() => { void result.current.startDownload(ESMFOLD); });
      await waitFor(() => expect(recibidos.map((r) => r.status)).toEqual(["in_progress"]));
      await act(async () => { soltar(); });
      await waitFor(() => expect(recibidos.map((r) => r.status)).toEqual(["in_progress", "success"]));
      expect(new Set(recibidos.map((r) => r.id))).toEqual(new Set([`model:${ESMFOLD}`]));
    } finally {
      window.removeEventListener(ACTIVITY_NOTIFICATION_EVENT, oir);
    }
  });
});

describe("fundirComprobacion", () => {
  it("el disco no pisa lo que está en vuelo; Rust manda sobre el disco", () => {
    expect(fundirComprobacion(
      { a: "downloading", b: "extracting", c: "ready", d: "error" },
      { a: "missing", b: "missing", c: "missing", d: "ready" },
      ["c"],
    )).toEqual({ a: "downloading", b: "extracting", c: "downloading", d: "ready" });
  });
});
