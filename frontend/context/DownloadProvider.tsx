"use client";

import { createContext, useCallback, useEffect, useRef, useState } from "react";
import type { ModuleEntry, ModelStatus, DownloadProgressEvent, DownloadCompleteEvent } from "../lib/types";

type UnlistenFn = () => void;

// Puente UNICO con Tauri: `lib/tauri.ts`. Antes este archivo tenia su propio
// `import()` dinamico de `@tauri-apps/api/core`, que NO se resolvia porque el
// paquete no esta instalado —solo `@tauri-apps/cli`—, asi que el `catch` lo
// convertia en "Tauri no disponible" sin decir por que. El repositorio de casos
// tenia una copia del mismo mecanismo roto. Ahora hay uno solo y comprobable.
import { invoke, isTauriAvailable, listen } from "../lib/tauri";
import { resetApiUrl, setApiUrlFromPort, type BackendStatusPayload } from "../lib/config";

// =====================================================================
// Estado del MOTOR — distinguible, no un «faltan modelos» para todo
// =====================================================================
//
// Antes cualquier fallo del arranque se tragaba con un `catch {}` y acababa
// pintado como «modelos pendientes». Eso es un diagnóstico falso: con el motor
// instalado y el proceso arrancando mal, el usuario leía que le faltaban
// descargas y se ponía a bajar 800 MB que ya tenía.
//
// Los estados son los que Rust sabe distinguir de verdad (`backend.rs`), más
// `disconnected` para el caso en que estuvo listo y dejó de contestar.

export type EngineState =
  | "idle"
  | "starting"
  | "ready"
  | "not_installed"
  | "spawn_failed"
  | "health_failed"
  | "disconnected";

export interface EngineStatus {
  readonly state: EngineState;
  /** Puerto en el que quedó el backend. Fuente única para todo el frontend. */
  readonly port: number | null;
  /** Razón exacta del último fallo, tal como la reportó Rust. */
  readonly detail: string | null;
}

export const ENGINE_IDLE: EngineStatus = { state: "idle", port: null, detail: null };

/** Frases para la interfaz. Ni una sola menciona modelos: no es lo que falla. */
export const ENGINE_LABELS: Record<EngineState, string> = {
  idle: "Motor en espera",
  starting: "Iniciando motor…",
  ready: "Motor listo",
  not_installed: "Motor no instalado",
  spawn_failed: "El motor no pudo arrancar",
  health_failed: "El motor arrancó pero no superó la comprobación de salud",
  disconnected: "El motor se desconectó",
};

/**
 * Normaliza lo que devuelve Rust.
 *
 * Acepta también un número suelto: es lo que devolvía el comando antes de este
 * sprint, y un contenedor desactualizado debe degradar en vez de romper.
 */
export function toEngineStatus(raw: unknown): EngineStatus {
  if (typeof raw === "number" && Number.isInteger(raw) && raw > 0) {
    return { state: "ready", port: raw, detail: null };
  }
  if (raw && typeof raw === "object") {
    const payload = raw as Partial<BackendStatusPayload>;
    const state = payload.state;
    if (
      state === "idle" || state === "starting" || state === "ready" ||
      state === "not_installed" || state === "spawn_failed" || state === "health_failed"
    ) {
      return {
        state,
        port: typeof payload.port === "number" ? payload.port : null,
        detail: typeof payload.detail === "string" ? payload.detail : null,
      };
    }
  }
  return {
    state: "spawn_failed",
    port: null,
    detail: "El motor devolvió un estado que esta versión no reconoce.",
  };
}

/**
 * Misma identidad mínima que exige Rust antes de declarar el motor listo.
 *
 * Esta segunda lectura cubre la carrera entre el `ensure_backend` y el primer
 * render: si el proceso muere y otro servicio toma el puerto, «HTTP 200» no es
 * suficiente para seguir presentándolo como MolDesign.
 */
export function isMolDesignHealthPayload(raw: unknown): boolean {
  if (!raw || typeof raw !== "object") return false;
  const body = raw as Record<string, any>;
  const status = body.status;
  return (
    body.app === "mol-design" &&
    typeof body.version === "string" &&
    body.version.trim().length > 0 &&
    body.app_mode === "DESKTOP" &&
    body.components?.database?.status === "healthy" &&
    (status === "healthy" || status === "degraded")
  );
}

/**
 * Arranca el motor (o recupera el ya arrancado) y devuelve su estado.
 *
 * `ensure_backend` es idempotente en Rust: dos llamadas concurrentes comparten
 * un único proceso. Aquí NO se silencia el fallo — el `catch {}` anterior es
 * exactamente lo que hacía invisible el problema de arranque.
 */
async function ensureEngine(command: "ensure_backend" | "restart_backend"): Promise<EngineStatus> {
  try {
    return toEngineStatus(await invoke<BackendStatusPayload>(command));
  } catch (err) {
    return {
      state: "spawn_failed",
      port: null,
      detail: err instanceof Error ? err.message : String(err),
    };
  }
}

export type DownloadContextValue = {
  models: Record<string, ModelStatus>;
  progress: Record<string, DownloadProgressEvent>;
  manifest: ModuleEntry[];
  isLauncherMode: boolean | undefined;
  initialized: boolean;
  /** Estado del motor de cálculo, con su razón. */
  engine: EngineStatus;
  /** Cierra el motor propio y vuelve a arrancarlo. Es el botón «Reintentar». */
  retryEngine: () => Promise<void>;
  startDownload: (moduleId: string) => Promise<void>;
  cancelDownload: (moduleId: string) => Promise<void>;
  checkModules: () => Promise<void>;
};

export const DownloadContext = createContext<DownloadContextValue | null>(null);

const NOTA_REVISION =
  "Commit inmutable. Antes decia 'main', que es un puntero movil: el dia que upstream lo mueva, el SHA-256 fijado deja de coincidir y la descarga falla sin que nadie lo haya decidido.";

export const FALLBACK_MANIFEST: ModuleEntry[] = [
  {
    id: "llm-qwen15", name: "Qwen 2.5 1.5B Instruct (Q4_K_M)",
    description: "LLM local para MolChat",
    type: "file", filename: "qwen2.5-1.5b-instruct-q4_k_m.gguf", size_bytes: 1117320736,
    sha256: "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
    urls: ["https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/qwen2.5-1.5b-instruct-q4_k_m.gguf"],
    required: false, destination: "models/llm/", features: ["molchat"],
    license: "Apache-2.0", source_url: "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF",
    license_url: "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/blob/main/LICENSE", revision: "91cad51170dc346986eccefdc2dd33a9da36ead9",
    revision_nota: NOTA_REVISION,
  },
  {
    id: "esmfold-weights", name: "ESMFold v1 — pesos del modelo",
    description:
      "Plegamiento de péptidos con ESMFold (Meta AI); el acoplamiento lo hace " +
      "después AutoDock Vina. Con GPU tarda minutos; en CPU, bastante más. El " +
      "tokenizer ya viene en el instalador: esto es sólo el checkpoint.",
    // Qué motor habilita esta descarga y qué necesita el runtime para cargarla.
    // El catálogo del backend (`services/motores`) usa lo mismo para decidir si
    // el módulo está instalado y si se puede encender.
    engine_id: "esmfold",
    requires_python: ["torch", "transformers"],
    notes:
      "Los archivos pequeños que `from_pretrained` necesita —config.json, vocab.txt, " +
      "tokenizer_config.json y special_tokens_map.json— viajan en el instalador " +
      "(bundle_helper, paso 4b). Sin ellos este .bin no carga.",
    type: "file", filename: "pytorch_model.bin", size_bytes: 8442062570,
    sha256: "2ee07356b125d1e3e57503c204111fd7323347fc4735d41d3caac57c2a78e116",
    urls: ["https://huggingface.co/srcacahuate/moldesign-models/resolve/a12fe0cc72c86cb0f8326fba17879c300508a04e/v1.0.0/esmfold/models/pytorch_model.bin"],
    required: false, destination: "esmfold/models/", features: ["peptide_docking"],
    license: "MIT", source_url: "https://huggingface.co/facebook/esmfold_v1",
    license_url: "https://github.com/facebookresearch/esm/blob/main/LICENSE", revision: "a12fe0cc72c86cb0f8326fba17879c300508a04e",
    revision_nota: NOTA_REVISION,
  },
];

let _resourceDir: string | null = null;

async function getResourceDir(): Promise<string | null> {
  if (_resourceDir) return _resourceDir;
  try {
    _resourceDir = await invoke<string>("get_resource_dir");
    return _resourceDir;
  } catch {
    return null;
  }
}

function joinPath(base: string | null, filename: string): string | null {
  if (!base) return null;
  const sep = base.includes("\\") ? "\\" : "/";
  return `${base}${sep}${filename.replace(/\//g, sep)}`;
}

// Delega en el puente compartido: comprueba que `invoke` EXISTE, no solo que
// el objeto global este presente. Un `__TAURI__` sin `core.invoke` prometia una
// capacidad que despues fallaba al usarse.
function isTauri(): boolean {
  return isTauriAvailable();
}

export function DownloadProvider({ children }: { children: React.ReactNode }) {
  const [models, setModels] = useState<Record<string, ModelStatus>>({});
  const [progress, setProgress] = useState<Record<string, DownloadProgressEvent>>({});
  const [manifest] = useState<ModuleEntry[]>(FALLBACK_MANIFEST);
  const [initialized, setInitialized] = useState(false);
  const [resourceDir, setResourceDir] = useState<string | null>(null);
  const [engine, setEngine] = useState<EngineStatus>(ENGINE_IDLE);
  const unlistenRef = useRef<UnlistenFn[]>([]);

  /**
   * Aplica el estado del motor Y propaga su puerto.
   *
   * El puerto que devuelve Rust es la FUENTE ÚNICA para todo el frontend —REST,
   * SSE, descargas, PDF—. Propagarlo desde aquí es lo que evita que cada
   * módulo se invente su propia dirección; hacerlo sólo para `/health`, como
   * antes, dejaba al resto de la aplicación hablando con un puerto vacío.
   */
  const applyEngine = useCallback((status: EngineStatus) => {
    setEngine(status);
    if (status.state === "ready" && status.port) setApiUrlFromPort(status.port);
    else resetApiUrl();
  }, []);

  const retryEngine = useCallback(async () => {
    // Mientras Rust decide un puerto nuevo no se conserva un enlace al proceso
    // anterior: podría estar muerto o incluso haber sido sustituido por otro
    // servicio local.
    resetApiUrl();
    setEngine((current) => ({ ...current, state: "starting", detail: null }));
    // `restart_backend` cierra el proceso propio antes de reintentar: un motor
    // a medias seguiría ocupando su puerto y el intento nuevo dejaría huérfano
    // al anterior.
    applyEngine(await ensureEngine("restart_backend"));
  }, [applyEngine]);

  const checkModules = useCallback(async (rd: string | null, mod: ModuleEntry[]) => {
    const statuses: Record<string, ModelStatus> = {};
    for (const entry of mod) {
      if (!rd) { statuses[entry.id] = "missing"; continue; }
      const filename = entry.filename || "";
      const destination = entry.destination || ".";
      const destPath = destination === "." ? filename : destination + filename;
      const dest = destPath ? joinPath(rd, destPath) : null;
      if (!dest) { statuses[entry.id] = "missing"; continue; }
      try {
        const ok: boolean = entry.sha256
          ? await invoke("verify_model", { dest, sha256: entry.sha256 })
          : await invoke("file_exists", { dest });
        statuses[entry.id] = ok ? "ready" : "missing";
      } catch {
        statuses[entry.id] = "missing";
      }
    }
    return statuses;
  }, []);

  const startDownload = useCallback(async (moduleId: string) => {
    const entry = manifest.find((m) => m.id === moduleId);
    if (!entry || !resourceDir) return;
    setModels((prev) => ({ ...prev, [moduleId]: "downloading" }));
    try {
      const filename = entry.filename || "";
      const destination = entry.destination || ".";

      /**
       * Intenta cada URL declarada hasta que una funcione.
       *
       * `urls` siempre fue un array y sólo se usaba `[0]`: si esa dirección
       * fallaba —el repositorio movido, un bloqueo regional, un corte— la
       * descarga moría con un error genérico aunque hubiera un espejo escrito
       * al lado. Ahora la lista significa lo que parecía significar: la primera
       * es la procedencia preferida y las demás son respaldo.
       *
       * Lo que NO cambia: el `sha256` se verifica igual en todas. Que un espejo
       * responda no lo autoriza a entregar otro archivo, y una cancelación del
       * usuario no se reintenta contra el siguiente.
       */
      const descargarCon = async (dest: string) => {
        const urls = (entry.urls || []).filter(Boolean);
        if (urls.length === 0) throw new Error("El módulo no declara ninguna URL de descarga.");

        let ultimoError: unknown = null;
        for (let i = 0; i < urls.length; i += 1) {
          try {
            await invoke("download_model", {
              modelId: entry.id, url: urls[i], dest, sha256: entry.sha256, resume: true,
            });
            if (i > 0) {
              console.info(`[descargas] ${entry.id}: la fuente ${i + 1} de ${urls.length} funcionó`);
            }
            return;
          } catch (err: any) {
            // Cancelar es una decisión del investigador, no un fallo de la
            // fuente: pasar a la siguiente sería reanudar lo que acaba de parar.
            if (err?.message?.includes?.("cancelada")) throw err;
            ultimoError = err;
            if (i < urls.length - 1) {
              console.warn(`[descargas] ${entry.id}: la fuente ${i + 1} falló, probando la siguiente`);
            }
          }
        }
        throw ultimoError instanceof Error
          ? ultimoError
          : new Error(String(ultimoError ?? "descarga fallida"));
      };

      if (entry.type === "archive") {
        const archiveDest = joinPath(resourceDir, filename);
        if (!archiveDest) return;
        await descargarCon(archiveDest);
        setModels((prev) => ({ ...prev, [moduleId]: "extracting" }));
        await invoke("extract_archive", { archivePath: archiveDest, destDir: resourceDir, moduleId: entry.id });
      } else {
        const dest = joinPath(resourceDir, destination + filename);
        if (!dest) return;
        await descargarCon(dest);
      }
      setModels((prev) => ({ ...prev, [moduleId]: "ready" }));
    } catch (err: any) {
      setModels((prev) => ({ ...prev, [moduleId]: err?.message?.includes?.("cancelada") ? "missing" : "error" }));
    }
  }, [manifest, resourceDir, applyEngine]);

  const cancelDownload = useCallback(async (moduleId: string) => {
    try { await invoke("cancel_download", { modelId: moduleId }); setModels((prev) => ({ ...prev, [moduleId]: "missing" })); } catch {}
  }, []);

  useEffect(() => {
    const setup = async () => {
      try {
        const u1 = await listen("download:progress", (e: any) => setProgress((prev) => ({ ...prev, [e.payload.model_id]: e.payload })));
        const u2 = await listen("download:complete", (e: any) => {
          setModels((prev) => ({ ...prev, [e.payload.model_id]: e.payload.success ? "ready" : "error" }));
          setProgress((prev) => { const n = { ...prev }; delete n[e.payload.model_id]; return n; });
        });
        unlistenRef.current = [u1, u2];
      } catch {}
    };
    setup();
    return () => unlistenRef.current.forEach((u) => u());
  }, []);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    /**
     * Confirma contra el puerto REAL que devolvió Rust.
     *
     * Antes esta función tenía `port = 8000` por defecto y era el segundo sitio
     * donde el frontend daba por hecho un puerto que Rust no había elegido.
     * Ahora el puerto es obligatorio: si no se sabe, no hay a quién preguntar.
     */
    async function confirmHealth(port: number, maxRetries = 5): Promise<boolean> {
      for (let i = 0; i < maxRetries; i++) {
        if (cancelled) return false;
        try {
          const res = await fetch(`http://127.0.0.1:${port}/health`, {
            signal: AbortSignal.timeout(3000),
          });
          const body = await res.json();
          if (isMolDesignHealthPayload(body)) return true;
        } catch {}
        if (i < maxRetries - 1) await new Promise((r) => { retryTimer = setTimeout(r, 2000); });
      }
      return false;
    }

    async function bootstrap() {
      if (!isTauri()) {
        // En navegador no hay motor que arrancar: la dirección la fija
        // `NEXT_PUBLIC_API_URL` o el valor por defecto, y los módulos no se
        // pueden verificar en disco.
        const ready: Record<string, ModelStatus> = {};
        manifest.forEach((m) => (ready[m.id] = "ready"));
        setModels(ready);
        setInitialized(true);
        return;
      }

      setEngine((current) => ({ ...current, state: "starting", detail: null }));
      try {
        const rd = await getResourceDir();
        if (cancelled) return;
        setResourceDir(rd);
        const statuses = await checkModules(rd, manifest);
        if (cancelled) return;

        // Se pide el motor SIEMPRE, esté el manifiesto de modelos como esté.
        // Rust ya lo habrá arrancado desde su `setup`; esta llamada es
        // idempotente y sirve para conocer el puerto y el estado real.
        const status = await ensureEngine("ensure_backend");
        if (cancelled) return;

        if (status.state === "ready" && status.port) {
          applyEngine(status);
          // El motor contesta ⇒ está instalado, diga lo que diga el checksum
          // del paquete de descarga.
          if (!(await confirmHealth(status.port))) {
            // Estuvo listo y dejó de contestar entre una cosa y la otra.
            if (!cancelled) {
              resetApiUrl();
              setEngine({
                state: "disconnected",
                port: status.port,
                detail: `El motor dejó de responder en el puerto ${status.port}.`,
              });
            }
          }
        } else {
          applyEngine(status);
        }

        if (!cancelled) setModels((prev) => ({ ...prev, ...statuses }));
      } catch (err) {
        // El fallo se DICE. El `catch` mudo anterior convertía cualquier
        // problema de arranque en «faltan modelos».
        if (!cancelled) {
          setEngine({
            state: "spawn_failed",
            port: null,
            detail: err instanceof Error ? err.message : String(err),
          });
          const s: Record<string, ModelStatus> = {};
          manifest.forEach((m) => (s[m.id] = "missing"));
          setModels((prev) => ({ ...prev, ...s }));
        }
      } finally {
        if (!cancelled) setInitialized(true);
      }
    }
    bootstrap();
    return () => { cancelled = true; clearTimeout(retryTimer); };
  }, [checkModules, manifest, applyEngine]);

  // Optional model downloads must not put the installed application into a
  // legacy "launcher mode". Required modules are embedded in the installer;
  // this flag is only a compatibility signal for future required modules.
  const requiredModules = manifest.filter((m) => m.required);
  const isLauncherMode = !requiredModules.every((m) => models[m.id] === "ready");

  return (
    <DownloadContext.Provider value={{
      models, progress, manifest, isLauncherMode, initialized,
      engine, retryEngine,
      startDownload, cancelDownload,
      checkModules: async () => {
        const statuses = await checkModules(resourceDir, manifest);
        setModels((prev) => ({ ...prev, ...statuses }));
      },
    }}>
      {children}
    </DownloadContext.Provider>
  );
}
