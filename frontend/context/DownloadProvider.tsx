"use client";

import { frontendMessage, type FrontendMessage } from "../lib/frontendError";

import { presentError } from "../lib/frontendError";

import { useLanguage } from "./LanguageContext";

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
import { dismissActivityNotification, emitActivityNotification } from "../lib/activityNotifications";
import { avisosPorTransicion } from "../lib/avisosDeModulos";

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
  /** Descriptor efímero de mensajes propios; nunca se serializa con casos. */
  readonly detailMessage?: FrontendMessage;
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
    detail: String(frontendMessage("c_engine_unknown")),
    detailMessage: frontendMessage("c_engine_unknown"),
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
async function ensureEngine(command: "ensure_backend" | "restart_backend", t: (key: string, values?: Readonly<Record<string, string | number>>) => string): Promise<EngineStatus> {
  try {
    return toEngineStatus(await invoke<BackendStatusPayload>(command));
  } catch (err) {
    return {
      state: "spawn_failed",
      port: null,
      detail: err instanceof Error ? presentError(err, t) : String(err),
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

/** Lo que dice Rust (`downloader.rs`, `YA_EN_CURSO`) si el módulo ya se está descargando. */
const YA_EN_CURSO = "descarga en curso";

/** Un estado que sólo puede cerrar la descarga misma, nunca una comprobación de disco. */
function enVuelo(status: ModelStatus | undefined): boolean {
  return status === "downloading" || status === "extracting";
}

/** Rust rechaza con un texto; el resto, con un `Error`. Aquí da igual cuál. */
function textoDelError(err: unknown): string {
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message;
  return String((err as { message?: unknown } | null)?.message ?? err ?? "");
}

function bytesDe(event: DownloadProgressEvent | undefined): number {
  return event ? event.bytes_downloaded ?? event.downloaded_bytes ?? 0 : 0;
}

/**
 * Funde una comprobación de disco con el estado vivo.
 *
 * La comprobación mira el archivo FINAL, que no existe hasta que la descarga
 * termina y se verifica. Pisar un «descargando» con su «falta» devolvía el botón
 * «Descargar» mientras Rust seguía bajando, y un segundo clic arrancaba otra
 * descarga del mismo archivo: la barra saltaba entre las dos (avanzaba y
 * retrocedía). Pasaba con «Verificar instalación» y cuando la comprobación del
 * arranque terminaba después de empezar una descarga. Lo que Rust dice estar
 * descargando (`active_downloads`) manda sobre el disco.
 */
export function fundirComprobacion(
  actual: Record<string, ModelStatus>,
  comprobado: Record<string, ModelStatus>,
  activos: readonly string[] = [],
): Record<string, ModelStatus> {
  const siguiente = { ...actual };
  for (const [id, status] of Object.entries(comprobado)) {
    if (!enVuelo(actual[id])) siguiente[id] = status;
  }
  for (const id of activos) {
    if (!enVuelo(siguiente[id])) siguiente[id] = "downloading";
  }
  return siguiente;
}

/** Los módulos que Rust está bajando. Un contenedor sin el comando no baja ninguno. */
async function descargasActivas(): Promise<string[]> {
  try {
    const ids = await invoke<unknown>("active_downloads");
    return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}

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
  const { t } = useLanguage();
  const [models, setModels] = useState<Record<string, ModelStatus>>({});
  const [progress, setProgress] = useState<Record<string, DownloadProgressEvent>>({});
  const [manifest] = useState<ModuleEntry[]>(FALLBACK_MANIFEST);
  const [initialized, setInitialized] = useState(false);
  const [resourceDir, setResourceDir] = useState<string | null>(null);
  const [engine, setEngine] = useState<EngineStatus>(ENGINE_IDLE);
  const unlistenRef = useRef<UnlistenFn[]>([]);
  const modelsRef = useRef(models);
  modelsRef.current = models;
  // Descargas que ESTA ventana pidió y aún esperan su respuesta. Su final lo da
  // la promesa; el evento `download:complete` es para las que la ventana no
  // pidió (se recargó a mitad de descarga) y, si llegara uno de una descarga
  // cancelada justo antes, pisaría a la nueva.
  const pendientesRef = useRef(new Set<string>());

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
    applyEngine(await ensureEngine("restart_backend", t));
  }, [applyEngine, t]);

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
    // Una descarga en curso no se arranca otra vez: es el segundo clic que
    // ponía a dos tareas a escribir el mismo archivo.
    if (enVuelo(modelsRef.current[moduleId]) || pendientesRef.current.has(moduleId)) return;
    // «Descargar de nuevo» sobre un modelo instalado: el archivo bueno sigue en
    // disco hasta que el nuevo pase el SHA-256 (Rust baja a `.part`).
    const estabaInstalado = modelsRef.current[moduleId] === "ready";
    pendientesRef.current.add(moduleId);
    modelsRef.current = { ...modelsRef.current, [moduleId]: "downloading" };
    setModels((prev) => ({ ...prev, [moduleId]: "downloading" }));
    // Cada descarga empieza su barra de cero; lo que quedara de un intento
    // anterior no cuenta como progreso de éste.
    setProgress((prev) => { const n = { ...prev }; delete n[moduleId]; return n; });
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
          } catch (err: unknown) {
            // Cancelar es una decisión del investigador, no un fallo de la
            // fuente: pasar a la siguiente sería reanudar lo que acaba de parar.
            // Si el módulo ya se está bajando, otra fuente tampoco lo arregla.
            const motivo = textoDelError(err);
            if (motivo.includes("cancelada") || motivo.includes(YA_EN_CURSO)) throw err;
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
      pendientesRef.current.delete(moduleId);
      setModels((prev) => ({ ...prev, [moduleId]: "ready" }));
    } catch (err: unknown) {
      pendientesRef.current.delete(moduleId);
      const motivo = textoDelError(err);
      if (motivo.includes(YA_EN_CURSO)) {
        // Rust ya baja este módulo y la ventana no lo sabía: se engancha a esa
        // descarga, cuyo final llegará por `download:complete`. Si acaba de
        // terminar, manda el disco.
        if ((await descargasActivas()).includes(moduleId)) {
          setModels((prev) => ({ ...prev, [moduleId]: "downloading" }));
        } else {
          const comprobado = await checkModules(resourceDir, [entry]);
          setModels((prev) => ({ ...prev, ...comprobado }));
        }
        return;
      }
      const cancelada = motivo.includes("cancelada");
      setModels((prev) => ({ ...prev, [moduleId]: cancelada ? "missing" : "error" }));
      // Cancelar una descarga «de nuevo» no desinstala nada: el archivo
      // anterior sigue intacto, y el disco lo dice.
      if (cancelada && estabaInstalado) {
        const comprobado = await checkModules(resourceDir, [entry]);
        setModels((prev) => fundirComprobacion(prev, comprobado));
      }
    }
  }, [manifest, resourceDir, checkModules]);

  // Cada descarga de un modelo es un aviso de la campana: empieza, avanza y
  // termina (o falla) en la misma entrada. Ver `lib/avisosDeModulos.ts`.
  const estadosAvisadosRef = useRef<Record<string, ModelStatus>>({});
  useEffect(() => {
    const acciones = avisosPorTransicion(estadosAvisadosRef.current, models);
    estadosAvisadosRef.current = models;
    for (const accion of acciones) {
      if (accion.tipo === "emitir") emitActivityNotification(accion.aviso);
      else dismissActivityNotification(accion.id, accion.soloSi);
    }
  }, [models]);

  const cancelDownload = useCallback(async (moduleId: string) => {
    try { await invoke("cancel_download", { modelId: moduleId }); setModels((prev) => ({ ...prev, [moduleId]: "missing" })); } catch {}
  }, []);

  useEffect(() => {
    let desmontado = false;
    const setup = async () => {
      try {
        // Una descarga sólo avanza: un evento con menos bytes que el último
        // no puede ser de la misma descarga, y no mueve la barra hacia atrás.
        const u1 = await listen("download:progress", (e: { payload: unknown }) => {
          const evento = e.payload as DownloadProgressEvent;
          setProgress((prev) => (
            bytesDe(evento) < bytesDe(prev[evento.model_id]) ? prev : { ...prev, [evento.model_id]: evento }
          ));
        });
        const u2 = await listen("download:complete", (e: { payload: unknown }) => {
          const { model_id: id, success, error } = e.payload as { model_id: string; success: boolean; error?: string | null };
          // La que pidió esta ventana la cierra su promesa (ver `pendientesRef`).
          if (pendientesRef.current.has(id)) return;
          setModels((prev) => ({ ...prev, [id]: success ? "ready" : textoDelError(error).includes("cancelada") ? "missing" : "error" }));
          setProgress((prev) => { const n = { ...prev }; delete n[id]; return n; });
        });
        // En desarrollo React monta, desmonta y vuelve a montar: si el
        // desmontaje llegó antes que `listen`, se suelta aquí y no queda un
        // segundo oyente vivo.
        if (desmontado) { u1(); u2(); return; }
        unlistenRef.current = [u1, u2];
      } catch {}
    };
    setup();
    return () => { desmontado = true; unlistenRef.current.forEach((u) => u()); unlistenRef.current = []; };
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
        const status = await ensureEngine("ensure_backend", t);
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
                detailMessage: frontendMessage("c_engine_lost_port", { port: status.port }),
              });
            }
          }
        } else {
          applyEngine(status);
        }

        const activos = await descargasActivas();
        if (!cancelled) setModels((prev) => fundirComprobacion(prev, statuses, activos));
      } catch (err) {
        // El fallo se DICE. El `catch` mudo anterior convertía cualquier
        // problema de arranque en «faltan modelos».
        if (!cancelled) {
          setEngine({
            state: "spawn_failed",
            port: null,
            detail: err instanceof Error ? presentError(err, t) : String(err),
          });
          const s: Record<string, ModelStatus> = {};
          manifest.forEach((m) => (s[m.id] = "missing"));
          setModels((prev) => fundirComprobacion(prev, s));
        }
      } finally {
        if (!cancelled) setInitialized(true);
      }
    }
    bootstrap();
    return () => { cancelled = true; clearTimeout(retryTimer); };
  }, [checkModules, manifest, applyEngine, t]);

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
        setModels((prev) => fundirComprobacion(prev, statuses));
      },
    }}>
      {children}
    </DownloadContext.Provider>
  );
}
