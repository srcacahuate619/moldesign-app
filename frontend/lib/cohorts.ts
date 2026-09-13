// =====================================================================
// Cliente de cohortes — comprobar, congelar, ejecutar, documentar
// =====================================================================
//
// LO QUE ESTE ARCHIVO NO HACE, Y ES EL PUNTO:
//
// No llama a `/evaluation/batch` en ninguna parte. El Batch histórico sigue
// publicado en el backend para no romper a quien lo use, pero la interfaz del
// MVP no lo toca: aquel flujo mezcla receptores bajo `ALL`, filtra con Early
// Exit sin declararlo y ordena por `total_score`. Ninguna de las tres cosas
// produce filas comparables entre sí.
//
// Tampoco inventa estimaciones de tiempo. El backend no las da, y una barra de
// progreso con «faltan 4 minutos» calculada aquí sería una cifra sin medida
// detrás.
//
// EL ESTADO VIVE EN EL BACKEND. La corrida es durable: al recargar la página se
// recupera preguntando, no restaurando algo que la pestaña recordaba. Esa es la
// diferencia con el Batch histórico, cuyo estado moría con el proceso.

import { getApiUrl } from "./config";
import { getAuthHeaders } from "./api";

// ── Contratos (espejo de backend/services/cohort) ────────────────────

export type CohortDecision = "ready" | "blocked";
export type RowEligibility = "eligible" | "invalid_input";
export type ControlRole = "reference" | "positive" | "negative" | "none";

export interface CohortStudy {
  readonly schema_version: 1;
  readonly name: string;
  readonly receptor: { readonly pdb_id: string; readonly chain?: string };
  readonly config: {
    readonly docking_engine: "vina" | "qvina2";
    readonly exhaustiveness: number;
    readonly num_poses: number;
    readonly grid_center?: readonly [number, number, number];
    readonly grid_size?: readonly [number, number, number];
    readonly seed?: number;
  };
}

export interface PreflightRow {
  readonly row_index: number;
  readonly source_name: string | null;
  readonly input_smiles: string;
  readonly canonical_smiles: string | null;
  readonly eligibility: RowEligibility;
  readonly reasons: readonly string[];
  readonly warnings: readonly string[];
  readonly active_label: boolean | null;
  readonly control_role: ControlRole;
  readonly duplicate_of_row: number | null;
}

export interface CohortSummary {
  readonly total_rows: number;
  readonly eligible_rows: number;
  readonly invalid_rows: number;
  readonly unique_canonical_ligands: number;
  readonly duplicate_rows: number;
  readonly explicit_reference_controls: number;
  readonly explicit_positive_controls: number;
  readonly explicit_negative_controls: number;
  /** `null` sin denominador: cero afirmaría un 0 % medido sobre nada. */
  readonly input_coverage: number | null;
  readonly input_coverage_denominator: number;
}

export interface CohortPreflightResult {
  readonly schema_version: number;
  readonly generated_at: string;
  readonly cohort_fingerprint: string;
  readonly normalized_study: CohortStudy;
  readonly decision: CohortDecision;
  readonly blockers: readonly string[];
  readonly warnings: readonly string[];
  readonly summary: CohortSummary;
  readonly rows: readonly PreflightRow[];
}

export interface CohortSourceFile {
  readonly filename: string;
  readonly content_type: string | null;
  readonly sha256: string;
  readonly size_bytes: number;
}

export interface CohortListItem {
  readonly id: string;
  readonly name: string;
  readonly status: string;
  readonly cohort_fingerprint: string;
  readonly receptor_pdb_id: string;
  readonly docking_engine: string;
  readonly created_at: string;
  readonly source: CohortSourceFile;
  readonly summary: CohortSummary;
}

export interface CohortRecord extends Omit<CohortListItem, "receptor_pdb_id" | "docking_engine" | "summary"> {
  readonly schema_version: number;
  readonly provenance: Record<string, unknown>;
  readonly preflight: CohortPreflightResult;
}

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_exceptions"
  | "failed"
  | "interrupted"
  | "cancelled";

export type RowStatus =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "not_evaluated"
  | "duplicate_reused"
  | "interrupted"
  | "cancelled";

export interface RunProgress {
  readonly total_rows: number;
  readonly eligible_rows: number;
  readonly completed_rows: number;
  readonly failed_rows: number;
  readonly not_evaluated_rows: number;
  readonly pending_rows: number;
  readonly running_rows: number;
  readonly duplicate_reused_rows: number;
  readonly cancelled_rows: number;
  readonly interrupted_rows: number;
}

export interface CohortRun {
  readonly id: string;
  readonly cohort_id: string;
  readonly status: RunStatus;
  readonly cohort_fingerprint: string;
  readonly run_fingerprint: string;
  readonly cancel_requested: boolean;
  readonly effective_config: Record<string, unknown>;
  readonly receptor_provenance: Record<string, unknown>;
  readonly progress: RunProgress;
  readonly created_at: string | null;
  readonly started_at: string | null;
  readonly finished_at: string | null;
  readonly last_error: string | null;
  readonly rows: readonly {
    readonly source_row_index: number;
    readonly canonical_smiles: string;
    readonly source_name: string | null;
    readonly control_role: ControlRole;
    readonly active_label: boolean | null;
    readonly status: RowStatus;
    readonly reused_from_row: number | null;
    readonly error_code: string | null;
    readonly error_detail: string | null;
  }[];
}

export interface RunAccepted {
  readonly run_id: string;
  readonly cohort_id: string;
  readonly status: RunStatus;
  readonly run_fingerprint: string;
  readonly eligible_rows: number;
  readonly workers: number;
}

export interface EvidenceMolecule {
  readonly source_row_index: number;
  readonly source_name: string | null;
  readonly canonical_smiles: string;
  readonly status: RowStatus;
  /** La afinidad que Vina observó. NO es una probabilidad ni un score. */
  readonly observed_vina_affinity_kcal_mol: number | null;
  readonly molecule_id: string | null;
  readonly result_id: string | null;
  readonly active_label: boolean | null;
  readonly control_role: ControlRole;
  readonly duplicate_of_row: number | null;
  readonly reused_from_row: number | null;
  readonly error_code: string | null;
  readonly error_detail: string | null;
}

export interface LabeledMetrics {
  readonly status: "evaluated" | "not_evaluated";
  readonly reason_code: string | null;
  readonly reason: string | null;
  readonly roc_auc: number | null;
  readonly enrichment_factors: readonly {
    readonly fraction: number;
    readonly n_selected: number;
    readonly n_actives_selected: number;
    readonly value: number | null;
  }[];
  readonly n_total: number;
  readonly n_positive: number;
  readonly n_negative: number;
  readonly coverage: number | null;
  readonly interpretation_limit?: string;
  readonly controls: readonly {
    readonly source_row_index: number;
    readonly source_name: string | null;
    readonly control_role: ControlRole;
    readonly active_label: boolean | null;
    readonly status: RowStatus;
    readonly observed_vina_affinity_kcal_mol: number | null;
  }[];
}

export interface RunEvidence {
  readonly contract: string;
  readonly run_id: string;
  readonly cohort_id: string;
  readonly cohort_name: string;
  readonly run_status: RunStatus;
  readonly sorted_by: string;
  readonly cohort_fingerprint: string;
  readonly run_fingerprint: string;
  readonly effective_config: Record<string, unknown>;
  readonly receptor: Record<string, unknown>;
  readonly coverage: {
    readonly source_rows: number;
    readonly eligible_rows: number;
    readonly not_eligible_rows: number;
    readonly unique_molecules_executed: number;
    readonly completed_rows: number;
    readonly failed_rows: number;
    readonly not_evaluated_rows: number;
    readonly duplicate_reused_rows: number;
    readonly pending_rows: number;
    readonly running_rows: number;
    readonly interrupted_rows: number;
    readonly cancelled_rows: number;
    readonly denominators: Record<
      string,
      { readonly numerator: number; readonly denominator: number; readonly value: number | null }
    >;
  };
  readonly molecules: readonly EvidenceMolecule[];
  readonly labeled_metrics: LabeledMetrics;
  readonly provenance: Record<string, unknown>;
  readonly limits: readonly string[];
}

/** El único orden que el backend ofrece, con su nombre EXACTO. */
export const SORT_BY_OBSERVED_AFFINITY = "afinidad_vina_observada";

// ── Errores ──────────────────────────────────────────────────────────

export class CohortError extends Error {
  readonly status: number | null;
  /** Código estable del backend cuando lo hay (`CORRIDA_ACTIVA`, etc.). */
  readonly code: string | null;
  readonly detail: unknown;

  constructor(message: string, status: number | null, detail: unknown = null) {
    super(message);
    this.name = "CohortError";
    this.status = status;
    this.detail = detail;
    const code =
      detail && typeof detail === "object" ? (detail as { code?: unknown }).code : null;
    this.code = typeof code === "string" ? code : null;
  }
}

function describe(status: number, body: unknown): { message: string; detail: unknown } {
  const detalle = body && typeof body === "object" ? (body as { detail?: unknown }).detail : null;
  if (typeof detalle === "string") return { message: detalle, detail: detalle };
  // Los errores 422 de FastAPI son arreglos. `Array` también es `object`,
  // por lo que este caso debe resolverse antes del objeto genérico.
  if (Array.isArray(detalle)) {
    const partes = detalle
      .map((item) => (item && typeof item === "object" ? (item as { msg?: string }).msg : null))
      .filter(Boolean);
    if (partes.length) return { message: partes.join(" · "), detail: detalle };
  }
  if (detalle && typeof detalle === "object") {
    const mensaje = (detalle as { message?: unknown }).message;
    if (typeof mensaje === "string") return { message: mensaje, detail: detalle };
    return { message: `La operación no se pudo completar (HTTP ${status}).`, detail: detalle };
  }
  return { message: `La operación no se pudo completar (HTTP ${status}).`, detail: detalle };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = await getApiUrl();
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: {
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders(),
        ...(init.headers || {}),
      },
      cache: "no-store",
    });
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") throw error;
    // El transporte NO se traduce a un diagnóstico científico.
    throw new CohortError(
      "Error de conexión: no se pudo contactar con el motor local de MolDesign. " +
        "Revisa su estado y vuelve a intentarlo.",
      null,
    );
  }

  if (!response.ok) {
    let cuerpo: unknown = null;
    try {
      cuerpo = await response.json();
    } catch {
      /* respuesta sin JSON: queda el código */
    }
    const { message, detail } = describe(response.status, cuerpo);
    throw new CohortError(message, response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

async function requestBlob(path: string, init: RequestInit = {}): Promise<{ blob: Blob; filename: string | null }> {
  const base = await getApiUrl();
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      headers: { "ngrok-skip-browser-warning": "true", ...getAuthHeaders(), ...(init.headers || {}) },
      cache: "no-store",
    });
  } catch (error) {
    if ((error as { name?: string })?.name === "AbortError") throw error;
    throw new CohortError(
      "Error de conexión: no se pudo contactar con el motor local de MolDesign.",
      null,
    );
  }
  if (!response.ok) {
    let cuerpo: unknown = null;
    try {
      cuerpo = await response.json();
    } catch {
      /* sin JSON */
    }
    const { message, detail } = describe(response.status, cuerpo);
    throw new CohortError(message, response.status, detail);
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const bruto = disposition.includes("filename=")
    ? disposition.split("filename=")[1]?.split(";")[0]?.replace(/['"]/g, "").trim()
    : null;
  return { blob: await response.blob(), filename: bruto || null };
}

// ── Operaciones ──────────────────────────────────────────────────────

export function preflightCohort(
  file: File,
  study: CohortStudy,
  signal?: AbortSignal,
): Promise<CohortPreflightResult> {
  const cuerpo = new FormData();
  cuerpo.append("file", file);
  cuerpo.append("study", JSON.stringify(study));
  return request<CohortPreflightResult>("/evaluation/cohorts/preflight", {
    method: "POST",
    body: cuerpo,
    signal,
  });
}

/**
 * Congela la cohorte. `expectedFingerprint` es el que devolvió la comprobación.
 *
 * No es una credencial: es cómo el servidor comprueba que el archivo que se
 * está guardando es el que se enseñó. Si el usuario cambió el archivo entre la
 * comprobación y el guardado, esto devuelve 409 y no se guarda nada.
 */
export function createCohort(
  file: File,
  study: CohortStudy,
  expectedFingerprint: string,
  signal?: AbortSignal,
): Promise<CohortRecord> {
  const cuerpo = new FormData();
  cuerpo.append("file", file);
  cuerpo.append("study", JSON.stringify(study));
  cuerpo.append("expected_fingerprint", expectedFingerprint);
  return request<CohortRecord>("/evaluation/cohorts", { method: "POST", body: cuerpo, signal });
}

export function listCohorts(signal?: AbortSignal): Promise<CohortListItem[]> {
  return request<CohortListItem[]>("/evaluation/cohorts", { signal });
}

export function getCohort(cohortId: string, signal?: AbortSignal): Promise<CohortRecord> {
  return request<CohortRecord>(`/evaluation/cohorts/${encodeURIComponent(cohortId)}`, { signal });
}

export function openRun(
  cohortId: string,
  workers = 2,
  signal?: AbortSignal,
): Promise<RunAccepted> {
  return request<RunAccepted>(
    `/evaluation/cohorts/${encodeURIComponent(cohortId)}/runs?workers=${workers}`,
    { method: "POST", signal },
  );
}

export function getRun(runId: string, signal?: AbortSignal): Promise<CohortRun> {
  return request<CohortRun>(`/evaluation/cohort-runs/${encodeURIComponent(runId)}`, { signal });
}

export function getLatestRun(cohortId: string, signal?: AbortSignal): Promise<CohortRun> {
  return request<CohortRun>(
    `/evaluation/cohorts/${encodeURIComponent(cohortId)}/runs/latest`,
    { signal },
  );
}

export function resumeRun(runId: string, workers = 2, signal?: AbortSignal): Promise<RunAccepted> {
  return request<RunAccepted>(
    `/evaluation/cohort-runs/${encodeURIComponent(runId)}/resume?workers=${workers}`,
    { method: "POST", signal },
  );
}

export function cancelRun(runId: string, signal?: AbortSignal): Promise<CohortRun> {
  return request<CohortRun>(`/evaluation/cohort-runs/${encodeURIComponent(runId)}/cancel`, {
    method: "POST",
    signal,
  });
}

export function getEvidence(
  runId: string,
  sort?: string,
  signal?: AbortSignal,
): Promise<RunEvidence> {
  const query = sort ? `?sort=${encodeURIComponent(sort)}` : "";
  return request<RunEvidence>(
    `/evaluation/cohort-runs/${encodeURIComponent(runId)}/evidence${query}`,
    { signal },
  );
}

export function dossierPreview(runId: string, signal?: AbortSignal) {
  return requestBlob(`/evaluation/cohort-runs/${encodeURIComponent(runId)}/dossier/preview`, {
    method: "POST",
    signal,
  });
}

export function dossierPackage(runId: string, signal?: AbortSignal) {
  return requestBlob(`/evaluation/cohort-runs/${encodeURIComponent(runId)}/dossier/package`, {
    method: "POST",
    signal,
  });
}

// ── Estados terminales y etiquetas ───────────────────────────────────

export const TERMINAL_RUN_STATUSES: readonly RunStatus[] = [
  "completed",
  "completed_with_exceptions",
  "failed",
  "cancelled",
  "interrupted",
];

export function isRunActive(status: RunStatus): boolean {
  return status === "queued" || status === "running";
}

/**
 * Etiquetas en castellano. La lógica NUNCA depende de estos textos: depende de
 * los códigos estables del backend. Cambiar una tilde aquí no puede romper un
 * recuento.
 */
export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  queued: "En cola",
  running: "Ejecutando",
  completed: "Completada",
  completed_with_exceptions: "Completada con excepciones",
  failed: "Sin resultados utilizables",
  interrupted: "Interrumpida",
  cancelled: "Cancelada",
};

export const ROW_STATUS_LABELS: Record<RowStatus, string> = {
  pending: "Pendiente",
  running: "Ejecutando",
  completed: "Completada",
  failed: "Fallida",
  not_evaluated: "No evaluada",
  duplicate_reused: "Duplicado reutilizado",
  interrupted: "Interrumpida",
  cancelled: "Cancelada",
};

export const CONTROL_ROLE_LABELS: Record<ControlRole, string> = {
  reference: "Referencia",
  positive: "Positivo",
  negative: "Negativo",
  none: "—",
};
