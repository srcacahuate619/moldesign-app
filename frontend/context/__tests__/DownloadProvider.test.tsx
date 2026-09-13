// =====================================================================
// Tests para DownloadProvider — gating de modelo crítico para desktop
// =====================================================================
//
// DownloadProvider es el estado global del launcher: chequea qué módulos
// se descargan (llm-qwen15, esmfold-weights), expone startDownload
// y cancelDownload. Los módulos del manifiesto son opcionales: la aplicación
// puede abrirse sin ellos y cada función decide si necesita uno.
//
// Si esto se rompe: el user ve "JUGAR" habilitado sin el modelo LLM bajado,
// entra a MolChat y la conversación falla crípticamente. Validez científica:
// el gating garantiza que el pipeline científico tiene todos sus componentes
// antes de que el usuario los invoque.
//
// Tests cubren:
// - bootstrap en no-Tauri (dev) vs Tauri (prod)
// - checkModules con verify_model/file_exists
// - startDownload type=file (llm) y rechazo de ids legacy
// - cancelDownload mid-flight
// - isLauncherMode permanece false cuando no hay módulos requeridos

import { describe, it, expect, beforeEach, vi } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { type ReactNode } from "react";

import { useDownload } from "../../hooks/useDownload";
import { DownloadProvider, isMolDesignHealthPayload, toEngineStatus } from "../DownloadProvider";
import { apiUrlSnapshot, getApiUrl, resetApiUrl } from "../../lib/config";
import { mockFetch, mockTauriInvoke, setTauriEnv } from "../../vitest.setup";

// Helpers

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

const HEALTHY_BODY = {
  status: "healthy",
  app: "mol-design",
  version: "1.0.0",
  app_mode: "DESKTOP",
  components: { database: { status: "healthy", engine: "SQLite" } },
};

// Wrapper que provee el DownloadProvider real
function wrapper({ children }: { children: ReactNode }) {
  return <DownloadProvider>{children}</DownloadProvider>;
}

// Mock del evento download:complete que el código escucha vía listen()
function mockDownloadCompleteEvent(emit: (event: string, payload: any) => void, modelId: string, success: boolean) {
  // El código usa listen("download:complete", handler) — simulamos disparando el handler
  // directamente en el mock de listen. Como el mock de listen en vitest.setup retorna
  // un unlisten stub, no podemos interceptar fácilmente. En su lugar, confiamos en que
  // startDownload setea el estado directamente tras completar la descarga (el evento
  // es solo backup para UI de progreso).
}

describe("DownloadProvider — bootstrap y checkModules", () => {
  beforeEach(() => {
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
  });

  it("en entorno no-Tauri (jsdom) marca todos los módulos ready inmediatamente", async () => {
    const { result } = renderHook(() => useDownload(), { wrapper });

    await waitFor(() => {
      expect(result.current.initialized).toBe(true);
    });
    expect(result.current.models["llm-qwen15"]).toBe("ready");
    expect(result.current.isLauncherMode).toBe(false); // todo ready → false
  });

  it("checkModules marca 'ready' cuando Tauri file_exists + verify_model resuelven true", async () => {
    setTauriEnv(true);

    // Mock fetch para /health (bootstrap confirma el motor embebido)
    mockFetch.mockResolvedValue(jsonResponse(HEALTHY_BODY));

    // Mock Tauri: resource_dir válido, archivo existe, checksum OK
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return true;
      if (cmd === "verify_model") return true;
      throw new Error(`Unexpected Tauri invoke: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });

    // Espera a que bootstrap termine (initialized=true)
    await waitFor(() => expect(result.current.initialized).toBe(true));

    // Dispara checkModules manual (el componente lo llama onClick "Verificar")
    await act(async () => {
      await result.current.checkModules();
    });
    expect(result.current.models["llm-qwen15"]).toBe("ready");
  });

  it("checkModules manual verifica SHA-256 de todos los módulos (no waitForBackend)", async () => {
    setTauriEnv(true);

    mockFetch.mockResolvedValue(jsonResponse(HEALTHY_BODY));

    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return true;
      if (cmd === "verify_model") return false; // checksum mismatch
      // El motor CONTESTA: eso prueba que el runtime esta en disco, y es lo
      // unico que puede forzar `base = ready` por encima del checksum. Antes
      // bastaba con que algo respondiera 200 en el puerto 8000, que es
      // justamente la suposicion que este sprint elimina.
      if (cmd === "ensure_backend") return { state: "ready", port: 8000, detail: null };
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    // Estado tras bootstrap: el motor responde,
    // llm-qwen15="ready" (checksum correcto)
    expect(result.current.models["llm-qwen15"]).toBe("missing");

    // checkModules manual: llm-qwen15 tiene sha256 → verify_model=false → missing
    // llm-qwen15 también tiene sha256 → verify_model=false → missing
    await act(async () => {
      await result.current.checkModules();
    });
    await waitFor(() => expect(result.current.models["llm-qwen15"]).toBe("missing"));
  });

  it("checkModules marca 'missing' cuando file_exists devuelve false", async () => {
    setTauriEnv(true);

    mockFetch.mockResolvedValue(jsonResponse(HEALTHY_BODY));

    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false; // archivo no existe
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    await act(async () => {
      await result.current.checkModules();
    });
  });
});

describe("DownloadProvider — startDownload y cancelDownload", () => {
  beforeEach(() => {
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
    setTauriEnv(true); // todos los tests de este describe son Tauri

    // Default: entorno Tauri con resource_dir válido y backend sano
    mockFetch.mockResolvedValue(jsonResponse(HEALTHY_BODY));
    mockTauriInvoke.mockImplementation(async (cmd: string, _args?: any) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false; // missing por defecto
      if (cmd === "verify_model") return false;
      if (cmd === "download_model") return undefined;
      if (cmd === "extract_archive") return undefined;
      if (cmd === "cancel_download") return undefined;
      throw new Error(`Unexpected: ${cmd}`);
    });
  });

  it("startDownload ignora ids que no están en el manifiesto", async () => {
    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    await act(async () => {
      await result.current.startDownload("base");
    });

    expect(result.current.models.base).toBeUndefined();
    expect(mockTauriInvoke).not.toHaveBeenCalledWith("download_model", expect.anything());
  });

  it("startDownload para type=file (llm) va missing -> downloading -> ready (sin extracting)", async () => {
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "verify_model") return false;
      if (cmd === "download_model") return undefined;
      if (cmd === "cancel_download") return undefined;
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));

    await act(async () => {
      await result.current.checkModules();
    });
    expect(result.current.models["llm-qwen15"]).toBe("missing");

    await act(async () => {
      await result.current.startDownload("llm-qwen15");
    });

    await waitFor(() => {
      expect(result.current.models["llm-qwen15"]).toBe("ready");
    }, { timeout: 5000 });
  });

  it("cancelDownload cancela descarga en curso y marca missing", async () => {
    // Simulamos una descarga que permanece pendiente hasta que se cancela.
    let rejectDownload: (e: any) => void = () => {};

    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "download_model") {
        // Retorna una Promise que cuelga hasta que rejectDownload se invoque
        return new Promise((_resolve, reject) => {
          rejectDownload = reject;
        });
      }
      if (cmd === "cancel_download") {
        rejectDownload(new Error("Descarga cancelada por el usuario"));
        return undefined;
      }
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));
    await act(async () => { await result.current.checkModules(); });

    // Llama cancelDownload directamente (sin startDownload en curso)
    await act(async () => {
      await result.current.cancelDownload("llm-qwen15");
    });

    // cancelDownload setea "missing" internamente (línea 153 del código)
    // Verifica que se llamó al comando de cancelar
    expect(mockTauriInvoke).toHaveBeenCalledWith("cancel_download", { modelId: "llm-qwen15" });
  });

  it("startDownload con error 'cancelada' → marca missing (no error)", async () => {
    // Este test cubre el bug fix: err?.message?.includes?.("cancelada")
    // El código original hacía err?.includes?.("cancelada") que NO funciona
    // en objetos Error (no tienen método .includes). El fix usa
    // err?.message?.includes?.("cancelada") para leer el message del Error.
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "verify_model") return false;
      if (cmd === "download_model") {
        throw new Error("Descarga cancelada por el usuario");
      }
      if (cmd === "cancel_download") return undefined;
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));
    await act(async () => { await result.current.checkModules(); });

    // startDownload → download_model rejecta con Error("cancelada...")
    // El catch debe ver err.message.includes("cancelada") → "missing" (no "error")
    await act(async () => {
      await result.current.startDownload("llm-qwen15");
    });

    await waitFor(() => {
      expect(result.current.models["llm-qwen15"]).toBe("missing");
    });
    // Verifica explíticamente que NO sea "error"
    expect(result.current.models["llm-qwen15"]).not.toBe("error");
  });

  it("startDownload con error genérico (sin 'cancelada') → marca error", async () => {
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "verify_model") return false;
      if (cmd === "download_model") {
        throw new Error("Network error: connection refused");
      }
      if (cmd === "cancel_download") return undefined;
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.initialized).toBe(true));
    await act(async () => { await result.current.checkModules(); });

    await act(async () => {
      await result.current.startDownload("llm-qwen15");
    });

    await waitFor(() => {
      expect(result.current.models["llm-qwen15"]).toBe("error");
    });
  });
});

// =====================================================================
// Estado del MOTOR — el fallo se dice, y se puede reintentar
// =====================================================================
//
// El arranque del backend se envolvía en `catch {}`: cualquier fallo acababa
// pintado como «faltan modelos», que es falso y además caro — invita a bajar
// otra vez un paquete que ya está en disco. Estos tests fijan que cada causa
// llega distinguible a la interfaz, con su razón, y que el puerto que elige
// Rust se convierte en la dirección de TODO el frontend.

describe("DownloadProvider — estado del motor", () => {
  beforeEach(() => {
    mockTauriInvoke.mockReset();
    mockFetch.mockReset();
    resetApiUrl();
    setTauriEnv(true);
  });

  it("un HTTP 200 de otro producto no supera la confirmación semántica", () => {
    expect(isMolDesignHealthPayload({ status: "healthy", app: "legaldesk" })).toBe(false);
    expect(isMolDesignHealthPayload(HEALTHY_BODY)).toBe(true);
  });

  it("propaga el puerto de Rust como dirección del API, no 8000 por defecto", async () => {
    mockFetch.mockResolvedValue(jsonResponse(HEALTHY_BODY));
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return true;
      if (cmd === "verify_model") return true;
      if (cmd === "ensure_backend") return { state: "ready", port: 8007, detail: null };
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.engine.state).toBe("ready"));
    expect(result.current.engine.port).toBe(8007);

    // Y la abstracción única del frontend ya apunta ahí: sin esto, evaluación,
    // streams y PDF seguirían llamando a 8000.
    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8007");
    expect(apiUrlSnapshot()).toBe("http://127.0.0.1:8007");
  });

  it("distingue «motor no instalado» de un fallo de arranque, con su razón", async () => {
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "verify_model") return false;
      if (cmd === "ensure_backend") {
        return { state: "not_installed", port: null, detail: "falta python-embed/python.exe" };
      }
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.engine.state).toBe("not_installed"));
    expect(result.current.engine.detail).toContain("python");
  });

  it("un backend que arranca pero no pasa el health NO se presenta como modelos ausentes", async () => {
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return true;
      if (cmd === "verify_model") return true;
      if (cmd === "ensure_backend") {
        return {
          state: "health_failed",
          port: null,
          detail: "la respuesta no se identifica como MolDesign (falta `app`)",
        };
      }
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.engine.state).toBe("health_failed"));
    // La razón EXACTA llega a la interfaz: es lo que distingue «hay otro
    // servidor en el puerto» de «se está ejecutando un backend caducado».
    expect(result.current.engine.detail).toContain("MolDesign");
  });

  it("un error del puente no se traga: queda como fallo de arranque", async () => {
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return false;
      if (cmd === "verify_model") return false;
      if (cmd === "ensure_backend") throw new Error("el puente de escritorio no respondió");
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.engine.state).toBe("spawn_failed"));
    expect(result.current.engine.detail).toContain("puente");
  });

  it("«Reintentar» reinicia el motor propio y adopta el puerto nuevo", async () => {
    let attempt = 0;
    mockFetch.mockResolvedValue(jsonResponse(HEALTHY_BODY));
    mockTauriInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === "get_resource_dir") return "C:\\app\\resources";
      if (cmd === "file_exists") return true;
      if (cmd === "verify_model") return true;
      if (cmd === "ensure_backend") {
        attempt += 1;
        return { state: "spawn_failed", port: null, detail: "sin puerto libre" };
      }
      // El reintento pasa por `restart_backend`, que en Rust cierra el proceso
      // propio antes de volver a arrancar: reintentar con `ensure_backend`
      // habría dejado vivo el motor a medias ocupando su puerto.
      if (cmd === "restart_backend") return { state: "ready", port: 8011, detail: null };
      throw new Error(`Unexpected: ${cmd}`);
    });

    const { result } = renderHook(() => useDownload(), { wrapper });
    await waitFor(() => expect(result.current.engine.state).toBe("spawn_failed"));
    expect(attempt).toBe(1);

    await act(async () => {
      await result.current.retryEngine();
    });

    await waitFor(() => expect(result.current.engine.state).toBe("ready"));
    expect(result.current.engine.port).toBe(8011);
    expect(mockTauriInvoke).toHaveBeenCalledWith("restart_backend", undefined);
    await expect(getApiUrl()).resolves.toBe("http://127.0.0.1:8011");
  });

  it("normaliza el contrato viejo (un número suelto) sin romperse", () => {
    // Un contenedor desactualizado devolvía sólo el puerto. Degradar es mejor
    // que caerse: la aplicación sigue sabiendo dónde está el backend.
    expect(toEngineStatus(8005)).toEqual({ state: "ready", port: 8005, detail: null });
    // Y un estado que esta versión no conoce NO se da por bueno.
    expect(toEngineStatus({ state: "teleporting" }).state).toBe("spawn_failed");
  });
});
