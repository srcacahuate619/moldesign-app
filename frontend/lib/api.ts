import type {
  AlphaFoldEntry,
  EvaluationSubmitResponse,
  EvaluationResult,
  HistoryResponse,
  InteractionsReport,
  JobStatus,
  SuggestionResponse,
  UserStats,
  ValidationResult,
  GlobalStats,
} from "./types";
import type { CasePipelineConfig } from "./cases/types";
import { beginFileDownload, completeFileDownload, failFileDownload, type ActivitySource } from "./activityNotifications";
import type { MoldexCatalog } from "./moldex";

import type { Calibracion } from "../components/science/RespaldoDelReceptor";

export interface Target {
  id?: string;
  pdb_id: string;
  name: string;
  organism: string;
  resolution: number;
  chain: string;
  requires_cns: boolean;
  structural_family?: string | null;
  therapeutic_family?: string | null;
  is_hot: boolean;
  spearman_rho: number | null;
  calibration_date: string | null;
  grid_center_x?: number;
  grid_center_y?: number;
  grid_center_z?: number;
  grid_size_x?: number;
  grid_size_y?: number;
  grid_size_z?: number;
  hotspots?: Array<{ name: string; importance: number; x?: number; y?: number; z?: number }>;
  /**
   * Doc 71. Qué cadenas FORMAN el sitio de unión, que no es lo mismo que
   * `chain` —la que se prepara—. Ausente en receptores anteriores al campo o
   * subidos por el usuario: se lee como «sin medir», NUNCA como «una sola».
   */
  site_chains?: string[] | null;
  site_chain_atoms?: Record<string, number> | null;
  /**
   * Con qué se sabe. `cocrystal_ligand` es la evidencia fuerte: las cadenas que
   * contactan el ligando cristalizado. `box_volume` sólo cuenta átomos dentro
   * de la caja y no distingue el bolsillo de la vecindad. Presentarlas igual
   * sería afirmar de más.
   */
  site_evidence?: "cocrystal_ligand" | "box_volume" | null;
  site_ligand?: string | null;
  /**
   * De dónde salen los hotspots. NINGUNO viene del RCSB: los generó este
   * repositorio. `auto_pocket_top15` son los 15 residuos más cercanos al
   * ligando holo autodetectado; `box_ligand_contacts`, los residuos a ≤4,5 Å
   * del ligando que ocupa la caja del catálogo, rederivados cuando los
   * primeros describían otro bolsillo. El campo existe para que la interfaz
   * no pueda presentarlos como anotación oficial.
   */
  hotspots_source?: "auto_pocket_top15" | "box_ligand_contacts" | null;
  is_private?: boolean;
  is_community?: boolean;
  creator_username?: string | null;
  calibration_status?: "listo" | "revisar" | "sin_datos";
  /**
   * SC-9. Qué respaldo científico tiene REALMENTE este receptor. Lo calcula el
   * backend en un solo sitio y lo manda con el catálogo; la interfaz lo muestra
   * pero no lo recalcula. Ausente en respuestas anteriores al campo: se lee
   * como «sin comprobar», nunca como «calibrado».
   */
  calibracion?: Calibracion | null;
  hotspot_count?: number;
  is_prepared?: boolean;
  grid_calibrated?: boolean;
  cofactors_whitelist?: string[];
  preparation_parent_id?: string | null;
  receptor_source_sha256?: string | null;
  prepared_receptor_sha256?: string | null;
  preparation_fingerprint?: string | null;
  preparation_recipe?: {
    schema_version: number;
    mode: string;
    parent_pdb_id?: string;
    chain?: string;
    grid_center?: number[];
    grid_size?: number[];
    cofactors_whitelist?: string[];
    waters?: string;
    altloc?: string;
  } | null;
  preparation_toolchain?: Record<string, string> | null;
}

export function resolveTargetName(pdbId: string, targetsList?: Target[]): string {
  if (!pdbId) return "Target Proteico";
  if (targetsList && targetsList.length > 0) {
    const found = targetsList.find((t) => t.pdb_id?.toUpperCase() === pdbId.toUpperCase());
    if (found?.name) return found.name;
  }
  return `Target ${pdbId}`;
}

export async function getTargetPdb(pdbId: string): Promise<string> {
  const res = await fetch(`${await getApiUrl()}/targets/${pdbId}/pdb`);
  if (!res.ok) throw new Error("Error fetching PDB file");
  return res.text();
}

import { getApiUrl, resetApiUrl } from "./config";

// ── Recuperación de un puerto que dejó de ser el del backend ────────────────
//
// EL FALLO QUE ARREGLA. `getApiUrl()` memoriza el puerto —`if (resolved) return
// resolved`— y `ensure_backend` sólo se pregunta UNA vez, en el arranque de
// `DownloadProvider`. No hay nadie escuchando después. Si el backend muere y
// Rust lo relevanta en otro puerto del rango 8000-8019, el frontend se queda
// llamando al viejo: `fetch` lanza, la interfaz dice «no se pudo establecer
// contacto con el motor local» y el motor está perfectamente sano.
//
// Lo peor no era el error, era que no se podía salir de él. El «Reintentar» de
// Moldex es `loadMoldex()`, que vuelve a pedir con LA MISMA dirección
// memorizada: el mismo fallo, tantas veces como se pulse.
//
// LA REGLA. Un `fetch` que lanza no es un error del servidor —un 500 no lanza—:
// es que la petición no llegó a ninguna parte. Así que se le vuelve a preguntar
// a Rust dónde está el backend y **sólo se reintenta si el puerto resultó ser
// otro**. Reintentar contra la misma URL muerta no es un reintento: es el mismo
// fallo dos veces, y encima duplicaría un POST cuyo destino sí estuviera vivo.
//
// Al revalidar se actualiza la caché compartida de `config.ts`, así que una
// sola recuperación arregla también a quien llama a `fetch` por su cuenta
// —descargas, PDF, SSE— sin que cada sitio tenga que repetir esta lógica.

/** Revalidación en curso. Diez peticiones que fallan a la vez preguntan UNA. */
let revalidacionDelPuerto: Promise<string | null> | null = null;

/**
 * Vuelve a resolver la dirección del backend.
 *
 * Devuelve la nueva SÓLO si difiere de la que acaba de fallar; `null` en
 * cualquier otro caso —misma dirección, o no se pudo resolver—, que es la señal
 * de que no hay nada que reintentar.
 */
async function revalidarPuertoDelMotor(baseQueFallo: string): Promise<string | null> {
  if (!revalidacionDelPuerto) {
    revalidacionDelPuerto = (async () => {
      resetApiUrl();
      try {
        return await getApiUrl();
      } catch {
        // El motor no está: se dirá con el error de conexión de siempre. Aquí
        // sólo se declara que no hay una dirección nueva a la que ir.
        return null;
      } finally {
        revalidacionDelPuerto = null;
      }
    })();
  }
  const nueva = await revalidacionDelPuerto;
  return nueva && nueva !== baseQueFallo ? nueva : null;
}

const ERROR_DE_CONEXION =
  "Error de conexión: no se pudo establecer contacto con el motor local de MolDesign. " +
  "Revisa su estado en la aplicación y vuelve a intentarlo.";

/**
 * Detección de runtime Tauri v2. Mismo criterio que lib/auth.tsx
 * (ver comentario alla). Sin esto el flujo de recovery no puede distinguir
 * Desktop (auto-login silencioso) de web (redirigir a /login).
 */
function isDesktopRuntime(): boolean {
  if (typeof window === "undefined") return false;
  return "__TAURI_INTERNALS__" in window || "__TAURI__" in window;
}

/**
 * Cabecera de sesión. Exportada para que los clientes que NO pasan por
 * `request()` —los que devuelven binarios, como el dossier del caso— usen el
 * mismo mecanismo de autenticación en vez de leer `localStorage` por su cuenta.
 * El comportamiento no cambia: es la misma función que ya usaban `request()`,
 * `downloadCertificate` y `fetchCertificateBlobUrl`.
 */
export function getAuthHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const stored = localStorage.getItem("moldesign_auth");
    if (stored) {
      const { token } = JSON.parse(stored);
      if (token) return { Authorization: `Bearer ${token}` };
    }
  } catch {}
  return {};
}

let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

/** Error HTTP conservando el status para que la UI no confunda 401/403 con
 * pérdida de datos o con una caída de red. El mensaje mantiene el formato
 * histórico para no romper consumidores que lo muestran directamente. */
export class ApiError extends Error {
  readonly status: number;
  readonly responseBody: string;

  constructor(status: number, responseBody: string) {
    super(`HTTP ${status}: ${responseBody}`);
    this.name = "ApiError";
    this.status = status;
    this.responseBody = responseBody;
  }
}

async function attemptRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const stored = localStorage.getItem("moldesign_auth");
      if (!stored) return false;

      const { refreshToken, user } = JSON.parse(stored);
      if (!refreshToken) return false;

      const res = await fetch(`${await getApiUrl()}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) throw new Error("Refresh failed");

      const data = await res.json();
      localStorage.setItem(
        "moldesign_auth",
        JSON.stringify({
          token: data.access_token,
          refreshToken: data.refresh_token,
          user: {
            user_id: data.user_id,
            username: data.username,
            email: data.email,
          },
        })
      );
      return true;
    } catch (err) {
      console.error("Token refresh failed:", err);
      localStorage.removeItem("moldesign_auth");
      return false;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const base = await getApiUrl();
  let fetchUrl = `${base}${path}`;
  const fetchInit = {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
      ...getAuthHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store" as RequestCache,
  };

  let response;
  try {
    response = await fetch(fetchUrl, fetchInit);
  } catch (err) {
    console.error(`Fetch error on ${fetchUrl}:`, err);
    // El motor pudo haberse movido de puerto. Se pregunta de nuevo y se
    // reintenta SÓLO si la dirección cambió; ver `revalidarPuertoDelMotor`.
    const nuevaBase = await revalidarPuertoDelMotor(base);
    if (nuevaBase === null) throw new Error(ERROR_DE_CONEXION);
    fetchUrl = `${nuevaBase}${path}`;
    try {
      response = await fetch(fetchUrl, fetchInit);
    } catch (err2) {
      console.error(`Fetch error on ${fetchUrl} (tras revalidar el puerto):`, err2);
      throw new Error(ERROR_DE_CONEXION);
    }
  }

  if (response.status === 401) {
    const refreshed = await attemptRefresh();
    if (refreshed) {
      // Retry with new headers
      try {
        response = await fetch(fetchUrl, {
          ...fetchInit,
          headers: {
            ...fetchInit.headers,
            ...getAuthHeaders(),
          },
        });
      } catch (err) {
        console.error(`Fetch retry error on ${fetchUrl}:`, err);
        throw new Error("Error de conexión: No se pudo establecer contacto con el servidor de la API en el reintento.");
      }
    } else {
      // Si el refresh falla, borramos el token muerto del storage
      if (typeof window !== "undefined") {
        // Detectar si la sesion que caducó era de cuenta PERSONAL (no invitado
        // Desktop). Si era personal, NO hacer auto-login silencioso: el usuario
        // podria haber estado separando sus moleculas de las del invitado, asi
        // que avisarle y dejarle decidir (re-login o entrar como invitado).
        let wasPersonalAccount = false;
        try {
          const old = localStorage.getItem("moldesign_auth");
          if (old) {
            const parsed = JSON.parse(old);
            const uname = parsed?.user?.username;
            if (uname && uname !== "Desktop User") wasPersonalAccount = true;
          }
        } catch {}

        localStorage.removeItem("moldesign_auth");
        window.dispatchEvent(new Event('auth_expired'));

        if (wasPersonalAccount) {
          // Cuenta personal caducada: mensaje claro, sin recuperar a invitado
          // silenciosamente (evita mezclar moleculas de cuentas distintas).
          if (!window.location.pathname.startsWith("/evaluation")) {
            window.location.href = "/login?expired=true";
          }
          // En /evaluation el error se surfacea via el banner de error del
          // ProEvaluation cuando el siguiente guardado tira 401/404.
        } else if (isDesktopRuntime()) {
          // Invitado Desktop caduco (caso raro): recuperar silenciosamente.
          fetch(`${await getApiUrl()}/auth/desktop-login`, {
            headers: { "ngrok-skip-browser-warning": "true" },
            cache: "no-store",
          })
            .then((r) => (r.ok ? r.json() : null))
            .then((data) => {
              if (data?.access_token) {
                localStorage.setItem(
                  "moldesign_auth",
                  JSON.stringify({
                    token: data.access_token,
                    refreshToken: data.refresh_token,
                    user: { user_id: data.user_id, username: data.username, email: data.email },
                  })
                );
              }
            })
            .catch(() => {});
        } else if (!window.location.pathname.startsWith("/evaluation")) {
          window.location.href = "/login?expired=true";
        }
      }
    }
  }

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text);
  }

  return (await response.json()) as T;
}

// ── Chemistry ────────────────────────────────────────────────────

export async function validateSmiles(smiles: string): Promise<ValidationResult> {
  return request<ValidationResult>("/chem/validate", {
    method: "POST",
    body: JSON.stringify({ smiles }),
  });
}

// ── Motores ──────────────────────────────────────────────────────

/** Un motor del menú avanzado, con la verdad sobre si esta instalación lo ejecuta. */
export interface MotorDeclarado {
  id: string;
  etiqueta: string;
  familia?: string;
  /**
   * En qué punto está. Los cuatro que importan llevan a acciones distintas:
   * `no_instalado` se descarga, `instalado_apagado` se enciende,
   * `dependencias_faltantes` necesita otra versión de la aplicación, y
   * `listo` es el único que se puede usar.
   */
  estado: string;
  disponible: boolean;
  /** `binario_empaquetado`, `binario_externo`, `servicio_externo` o `descarga_bajo_demanda`. */
  requiere: string;
  /** Obligatorio cuando `disponible` es false: por qué no, en una frase. */
  motivo: string | null;
  /** `descargar` | `encender` | `reintentar` | null. Qué resolvería el estado. */
  accion: string | null;
  /** Tamaño de la descarga, para poder decirlo antes de empezarla. */
  bytes_descarga: number;
  archivos_faltantes: string[];
  dependencias_faltantes: string[];
  /** `id` del módulo en el gestor de modelos, cuando la acción es descargar. */
  modulo_launcher: string | null;
  url_configurada?: string | null;
}

export interface InventarioDeMotores {
  docking: MotorDeclarado[];
  peptido: MotorDeclarado[];
}

/**
 * Qué motores puede ejecutar de verdad esta instalación.
 *
 * No hace red hacia los servicios externos: comprueba binarios y configuración.
 * Que un motor esté configurado no significa que responda, y el contrato lo
 * distingue en vez de prometerlo.
 */
export async function inventarioDeMotores(): Promise<InventarioDeMotores> {
  return request<InventarioDeMotores>("/evaluation/engines");
}

/**
 * Enciende un motor descargable que ya está instalado.
 *
 * Idempotente y explícito: nadie levanta un modelo de 8 GB porque se abrió una
 * pantalla. Devuelve el estado completo, no un booleano, porque quien lo llamó
 * necesita saber si lo que falta ahora es otra cosa.
 */
export async function encenderMotor(motorId: string): Promise<MotorDeclarado & { encendido: boolean }> {
  return request<MotorDeclarado & { encendido: boolean }>(
    `/evaluation/engines/${encodeURIComponent(motorId)}/encender`,
    { method: "POST" },
  );
}

// ── Evaluation ───────────────────────────────────────────────────

export async function submitEvaluation(
  smiles: string, 
  targetPdbId = "7E2Y", 
  isControl = false,
  gridCenter?: [number, number, number],
  gridSize?: [number, number, number],
  customHotspots?: string[],
  peptideDockingEngine?: "colabfold" | "esmfold" | "esmfold-pro" | "esmfold-experimental",
  pipelineConfig?: CasePipelineConfig,
  preflightFingerprint?: string,
  chain?: string,
) {
  return request<EvaluationSubmitResponse>("/evaluation/submit", {
    method: "POST",
    body: JSON.stringify({ 
      smiles, 
      target_pdb_id: targetPdbId, 
      chain,
      is_control: isControl,
      grid_center: gridCenter,
      grid_size: gridSize,
      custom_hotspots: customHotspots,
      peptide_docking_engine: peptideDockingEngine,
      pipeline_config: pipelineConfig,
      preflight_fingerprint: preflightFingerprint,
    }),
  });
}

export async function cancelEvaluation(taskId: string) {
  return request<{ cancelled: boolean; mmgbsa_killed: number }>("/evaluation/cancel", {
    method: "POST",
    body: JSON.stringify({ task_id: taskId }),
  });
}

export async function getJobStatus(taskId: string) {
  return request<JobStatus>(`/evaluation/status/${taskId}`);
}

/**
 * v1.7.4: Lee el resultado persistido de una molécula directamente desde DB.
 * Usado por ProSelectivityPanel para poll en background: cuando el pipeline
 * lanza el panel de selectividad como subprocess, el frontend consulta este
 * endpoint hasta ver selectivity_ran=true (el subprocess persiste post-hoc).
 */
export async function getEvaluationResult(
  moleculeId: string,
  taskId?: string,
): Promise<EvaluationResult> {
  const runQuery = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  return request<EvaluationResult>(`/evaluation/result/${moleculeId}${runQuery}`);
}

/**
 * UI-7 (2026-08-04): lee el SVG de atención GNN on-demand.
 * El payload completo (50-200 KB) ya NO viaja en el JobStatus del polling;
 * el frontend llama a este endpoint SOLO cuando el usuario abre el tab
 * "Explicabilidad". Ver docs/36 UI-7.
 */
export async function getGnnAttentionSvg(moleculeId: string): Promise<{ gnn_attention_svg: string | null; gnn_attention: number[] | null } | null> {
  try {
    return await request<{ gnn_attention_svg: string | null; gnn_attention: number[] | null }>(
      `/evaluation/gnn-attention/${moleculeId}`,
    );
  } catch {
    return null;
  }
}

export async function getAiReport(moleculeId: string): Promise<string | null> {
  try {
    const data = await request<{ ai_report: string | null }>(
      `/evaluation/ai-report/${moleculeId}`,
      { method: "POST" },
    );
    return data.ai_report ?? null;
  } catch {
    return null;
  }
}


/**
 * Descarga el archivo SDF con las poses de docking desde MinIO.
 * Retorna texto plano (SDF) o null si no hay archivo.
 */
export async function getPoseFile(moleculeId: string): Promise<string | null> {
  try {
    const res = await fetch(`${await getApiUrl()}/evaluation/files/poses/${moleculeId}`, {
      headers: {
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders()
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

/**
 * Análisis de interacciones no-covalentes ligando-proteína (PLIF).
 * Retorna H-bonds, hidrofóbicos, π-stacking, salt bridges, cation-π y
 * halogen bonds con coordenadas de ambos átomos en contacto.
 */
export async function getInteractions(moleculeId: string, poseRank = 1): Promise<InteractionsReport | null> {
  try {
    const res = await fetch(`${await getApiUrl()}/evaluation/interactions/${moleculeId}?pose_rank=${poseRank}`, {
      headers: {
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders()
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return (await res.json()) as InteractionsReport;
  } catch {
    return null;
  }
}

/**
 * Descarga el archivo PDB del target biológico.
 * Retorna texto plano (PDB) o null si no está disponible.
 */
export async function getProteinFile(moleculeId: string): Promise<string | null> {
  try {
    const res = await fetch(`${await getApiUrl()}/evaluation/files/protein/${moleculeId}`, {
      headers: {
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders()
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

/**
 * Descarga el archivo PDB complejo (proteína + ligando HETATM).
 * Retorna texto plano (PDB) o null si no está disponible.
 */
/**
 * Descarga el complejo PDB como archivo.
 *
 * MOLDEX-INT-006: Moldex ofrecía este archivo con un `<a href>` crudo. El token
 * de sesión vive en `getAuthHeaders()`, y una navegación del navegador no lo
 * adjunta: para una cuenta real la descarga fallaba. Se resuelve por `fetch`
 * autenticado, como ya hacía `downloadCertificate`.
 */
export async function downloadComplexFile(
  moleculeId: string,
  source: ActivitySource = "general",
): Promise<void> {
  const filename = `complex_${moleculeId}.pdb`;
  const activityId = beginFileDownload(filename, source);
  try {
    const contenido = await getComplexFile(moleculeId);
    if (contenido === null) throw new Error("No se pudo descargar el complejo 3D");
    const blob = new Blob([contenido], { type: "chemical/x-pdb" });
    const url = window.URL.createObjectURL(blob);
    try {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      completeFileDownload(activityId, filename, source);
    } finally { window.URL.revokeObjectURL(url); }
  } catch (error) {
    failFileDownload(activityId, filename, source);
    throw error;
  }
}

export async function getComplexFile(moleculeId: string): Promise<string | null> {
  try {
    const res = await fetch(`${await getApiUrl()}/evaluation/files/complex/${moleculeId}`, {
      headers: {
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders()
      },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

// ── History ──────────────────────────────────────────────────────

export async function getEvaluationHistory(
  page = 1,
  pageSize = 20,
  sortBy = "created_at",
  sortOrder = "desc",
  status?: string,
): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  });
  if (status) params.set("status", status);
  return request<HistoryResponse>(`/history/evaluations?${params}`);
}

/**
 * Lleva a la cuenta autenticada el trabajo hecho como invitado.
 *
 * Selectivo por diseño —se envía exactamente lo que el investigador aceptó
 * mover—, transaccional e idempotente en el backend: reintentar tras un fallo
 * de red no duplica nada ni deja el traspaso a medias.
 */
export async function traspasarDelInvitado(
  moleculeIds: string[],
  cohortIds: string[] = [],
): Promise<{ moleculas_traspasadas: number; cohortes_traspasadas: number; corridas_traspasadas?: number }> {
  return request("/auth/traspaso", {
    method: "POST",
    body: JSON.stringify({ molecule_ids: moleculeIds, cohort_ids: cohortIds }),
  });
}

export async function saveMolecule(moleculeId: string, name?: string): Promise<void> {
  let url = `/history/save/${moleculeId}`;
  if (name) {
    url += `?name=${encodeURIComponent(name)}`;
  }
  await request(url, { method: "POST" });
}

export async function getMoldex(targetPdbId?: string, limit?: number, offset?: number): Promise<MoldexCatalog> {
  const params = new URLSearchParams();
  if (targetPdbId) params.set("target_pdb_id", targetPdbId);
  if (typeof limit === "number") params.set("limit", String(limit));
  if (typeof offset === "number") params.set("offset", String(offset));
  const query = params.toString() ? `?${params.toString()}` : "";
  return request(`/moldex${query}`);
}

export async function getUserStats(): Promise<UserStats> {
  return request<UserStats>("/history/stats");
}

// ── Suggestions ──────────────────────────────────────────────────

export async function getSuggestions(
  smiles: string,
  properties?: Record<string, unknown>,
  scores?: Record<string, unknown>,
): Promise<SuggestionResponse> {
  return request<SuggestionResponse>("/suggestions/generate", {
    method: "POST",
    body: JSON.stringify({ smiles, properties, scores, max_suggestions: 5 }),
  });
}

// ── AlphaFold ────────────────────────────────────────────────────

export async function lookupAlphaFold(uniprotId: string): Promise<AlphaFoldEntry> {
  return request<AlphaFoldEntry>(`/targets/alphafold/lookup/${uniprotId}`);
}

// ── Targets ──────────────────────────────────────────────────────

export async function getTargets(): Promise<Target[]> {
  // El backend deriva los receptores privados de la cuenta autenticada. Un
  // listado de IDs aportado por el navegador no es una prueba de propiedad.
  return request<Target[]>("/targets/");
}

export async function uploadCustomTarget(formData: FormData): Promise<{ success: boolean; message: string; target: Target }> {
  const fetchUrl = `${await getApiUrl()}/targets/upload`;
  const fetchInit = {
    method: "POST",
    body: formData,
    headers: {
      "ngrok-skip-browser-warning": "true",
      ...getAuthHeaders(),
    },
  };

  const response = await fetch(fetchUrl, fetchInit);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Fallo al subir el receptor personalizado");
  }
  
  return response.json();
}

export interface TargetVariantInput {
  name: string;
  chain_id?: string;
  grid_center?: [number, number, number];
  grid_size?: [number, number, number];
  cofactors_whitelist: string[];
}

export async function createTargetVariant(
  parentPdbId: string,
  input: TargetVariantInput,
): Promise<Target> {
  return request<Target>(`/targets/${encodeURIComponent(parentPdbId)}/variants`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function shareCustomTarget(targetId: string): Promise<{ success: boolean; message: string }> {
  return request<{ success: boolean; message: string }>(`/targets/${targetId}/share`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
}

// ── Blockchain ────────────────────────────────────────────────────

export async function prepareCertification(
  moleculeId: string,
  userWallet: string
): Promise<{ already_certified: boolean; signature?: string; memo?: string }> {
  return request<{ already_certified: boolean; signature?: string; memo?: string }>(
    `/blockchain/certify/${moleculeId}/prepare?user_wallet=${encodeURIComponent(userWallet)}`
  );
}

export async function linkCertification(
  moleculeId: string,
  signature: string
): Promise<{ success: boolean; signature: string }> {
  return request<{ success: boolean; signature: string }>("/blockchain/certify/link", {
    method: "POST",
    body: JSON.stringify({
      molecule_id: moleculeId,
      signature,
    }),
  });
}

export async function downloadCertificate(
  moleculeId: string,
  source: ActivitySource = "general",
): Promise<void> {
  let filename = `MolDesign_Dossier_${moleculeId}.pdf`;
  const activityId = beginFileDownload(filename, source);
  try {
    const headers = await getAuthHeaders();
    const url = `${await getApiUrl()}/blockchain/certificate/${moleculeId}`;
    const response = await fetch(url, {
      method: "GET",
      headers: { "ngrok-skip-browser-warning": "true", ...headers },
    });
    if (!response.ok) throw new Error("No se pudo descargar el certificado");
    const disposition = response.headers.get("content-disposition") || response.headers.get("Content-Disposition");
    if (disposition?.includes("filename=")) {
      const proposed = disposition.split("filename=")[1]?.split(";")[0]?.replace(/['"]/g, "").trim();
      if (proposed) filename = proposed;
    }
    const blob = await response.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    try {
      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      completeFileDownload(activityId, filename, source);
    } finally { window.URL.revokeObjectURL(downloadUrl); }
  } catch (error) {
    failFileDownload(activityId, filename, source);
    throw error;
  }
}

export async function fetchCertificateBlobUrl(
  moleculeId: string,
  signal?: AbortSignal,
): Promise<string> {
  const headers = await getAuthHeaders();
  const url = `${await getApiUrl()}/blockchain/certificate/${moleculeId}/preview`;

  // `signal`: doc 71, defecto E1. El visor montaba el efecto, React lo volvía a
  // montar (StrictMode) y la primera petición seguía viva sin que nadie fuera a
  // usar su resultado. Generar el certificado es caro —ReportLab componiendo el
  // documento entero— así que eran dos renders simultáneos del mismo PDF contra
  // un backend de escritorio de un solo proceso. Abortar la que se descarta no
  // es higiene: es la mitad del trabajo que deja de hacerse.
  const response = await fetch(url, {
    method: "GET",
    headers: {
      "ngrok-skip-browser-warning": "true",
      ...headers
    },
    signal,
  });

  if (!response.ok) {
    throw new Error("No se pudo cargar la vista previa del certificado");
  }

  const blob = await response.blob();
  return window.URL.createObjectURL(blob);
}

export async function getGlobalStats(): Promise<GlobalStats> {
  return request<GlobalStats>("/stats/global");
}

export async function checkBlockchainHealth(): Promise<{
  available: boolean;
  rpc_url: string;
  network: string;
  rpc_reachable?: boolean;
  signer?: string;
  balance_lamports?: number;
  reason?: string | null;
}> {
  try {
    return await request<{
      available: boolean;
      rpc_url: string;
      network: string;
      rpc_reachable?: boolean;
      signer?: string;
      balance_lamports?: number;
      reason?: string | null;
    }>("/blockchain/health");
  } catch {
    return { available: false, rpc_url: "", network: "unknown" };
  }
}

// ── Cuánto va a tardar esta corrida ────────────────────────────────

/**
 * Una etapa del desglose. El usuario tiene derecho a ver de qué se compone el
 * número, no sólo el número.
 */
export interface EtapaEstimada {
  etapa: string;
  segundos_min: number;
  segundos_max: number;
  nota: string;
}

export interface EstimacionDeCorrida {
  segundos_min: number;
  segundos_max: number;
  /** `historial` si se calibró con corridas reales de este equipo. */
  apoyo: "historial" | "modelo";
  detalle_apoyo: string;
  etapas: EtapaEstimada[];
  /** Coste que se paga UNA vez —preparar el receptor—, o `null`. */
  una_vez: EtapaEstimada | null;
  avisos: string[];
  ligandos: number;
}

export interface PeticionDeEstimacion {
  exhaustiveness: number;
  conformers?: number;
  targetPdbId?: string;
  gridSize?: readonly [number, number, number];
  rotables?: number;
  antiTargets?: number;
  mmgbsa?: boolean;
  ligandos?: number;
}

/**
 * Estima una corrida, un ensemble o una cohorte en ESTE equipo.
 *
 * `targetPdbId` no es decorativo: con él el backend comprueba en disco si el
 * receptor ya está preparado, que es el coste de una sola vez —8.8 s medidos—
 * responsable de que una primera corrida parezca rota al lado de la segunda.
 */
export async function estimarCorrida(p: PeticionDeEstimacion): Promise<EstimacionDeCorrida> {
  const params = new URLSearchParams({ exhaustiveness: String(p.exhaustiveness) });
  if (p.conformers) params.set("conformers", String(p.conformers));
  if (p.targetPdbId) params.set("target_pdb_id", p.targetPdbId);
  if (p.gridSize) {
    params.set("grid_size_x", String(p.gridSize[0]));
    params.set("grid_size_y", String(p.gridSize[1]));
    params.set("grid_size_z", String(p.gridSize[2]));
  }
  if (typeof p.rotables === "number") params.set("rotables", String(p.rotables));
  if (p.antiTargets) params.set("anti_targets", String(p.antiTargets));
  if (p.mmgbsa) params.set("mmgbsa", "true");
  if (p.ligandos && p.ligandos > 1) params.set("ligandos", String(p.ligandos));
  return request<EstimacionDeCorrida>(`/evaluation/estimate?${params}`);
}
