import { beginFileDownload, completeFileDownload, failFileDownload, type ActivitySource } from "./activityNotifications";

// =====================================================================
// Cliente del dossier de caso — proyección, PDF y paquete reproducible
// =====================================================================
//
// QUÉ HACE ESTE ARCHIVO. Traduce el caso —que vive en el cliente y en
// camelCase— a la `CaseProjection` que el backend acepta, y transporta las dos
// respuestas: el PDF del dossier y el ZIP reproducible.
//
// QUÉ NO HACE, Y NO ES CASUALIDAD:
//
// 1. **No envía nada científico.** Ni afinidades, ni poses, ni scores. El
//    backend los recupera de sus propias fuentes. Si el resultado llegara desde
//    aquí, el dossier dejaría de ser evidencia de lo que se ejecutó y pasaría a
//    ser evidencia de lo que el cliente escribió (ver `services/dossier/
//    schemas.py`).
//
// 2. **No rellena huecos.** Un campo sin responder se OMITE, no se manda como
//    `null` ni como cadena vacía. El backend imprime «NO DEFINIDO» y el lector
//    puede distinguir «nadie preguntó» de «nadie contestó». Mandar `""` haría
//    pasar un hueco por una respuesta vacía.
//
// 3. **No manda rutas.** `storage.path` no entra en la proyección. El backend
//    lo rechaza igualmente, pero el filtro empieza aquí: una ruta local acabaría
//    impresa en un PDF que circula.
//
// 4. **No recalcula el fingerprint.** Se transporta el que produjo el backend.
//
// POR QUÉ POST Y NO GET. El caso vive en el cliente y no cabe en una URL. La
// ruta histórica `GET /blockchain/certificate/{id}/preview` sigue existiendo
// para el certificado —otro documento, otra pregunta— y NO se toca.

import { getApiUrl } from "./config";
import { getAuthHeaders } from "./api";
import type { CasePipelineConfig, CaseRecord, ReportableResult, RunInputsRelation } from "./cases/types";

// ── Contrato: CaseProjection v1 ──────────────────────────────────────
//
// Espejo EXACTO de `backend/services/dossier/schemas.py`. El backend declara
// `extra="forbid"`: una propiedad de más es un 422, no un campo ignorado. Por
// eso estos tipos no llevan índice libre.

/** Versión del CONTRATO de proyección, no del caso. */
export const PROJECTION_VERSION = 1;

export interface ProjectedContext {
  study_kind?: string;
  question?: string;
  decision?: string;
  system_rationale?: string;
  controls?: string;
  assumptions?: string;
  uncertainties?: string;
  notes?: string;
}

export interface ProjectedReceptor {
  pdb_id: string;
  chain?: string;
  origin?: string;
  name?: string;
  target_id?: string;
}

export interface ProjectedLigand {
  input_smiles: string;
  canonical_smiles?: string;
  name?: string;
}

export interface ProjectedConfig {
  grid_center?: readonly [number, number, number];
  grid_size?: readonly [number, number, number];
  custom_hotspots?: readonly string[];
  docking_engine?: string;
  exhaustiveness?: number;
  num_poses?: number;
  seed?: number;
  pipeline_config?: CasePipelineConfig;
}

export interface ProjectedInputs {
  receptor?: ProjectedReceptor;
  ligand?: ProjectedLigand;
  config?: ProjectedConfig;
}

export interface ProjectedPreflight {
  fingerprint: string;
  generated_at?: string;
  schema_version?: number;
  execution_route?: string;
  blockers?: readonly string[];
  warnings?: readonly string[];
  not_evaluated?: readonly string[];
  receptor_label?: string;
  ligand_label?: string;
  grid_label?: string;
}

export interface ProjectedRun {
  task_id: string;
  input_fingerprint?: string;
  execution_state?: string;
  started_at?: string;
  last_error?: string;
}

export interface ProjectedDecision {
  control_code: string;
  fingerprint: string;
  decision: "reconocida";
  at?: string;
  note?: string;
}

export interface ProjectedDisposition {
  kind: "accept" | "limit" | "abstain";
  rationale: string;
  fingerprint: string;
  at?: string;
}

export interface CaseProjection {
  projection_version: number;
  case_id: string;
  case_schema_version?: number;
  name: string;
  created_at?: string;
  context: ProjectedContext;
  inputs: ProjectedInputs;
  preflight?: ProjectedPreflight;
  run?: ProjectedRun;
  decisions?: readonly ProjectedDecision[];
  disposition?: ProjectedDisposition;
  run_inputs_relation: RunInputsRelation;
}

// ── Construcción de la proyección ────────────────────────────────────

/**
 * Asigna sólo si hay algo que asignar.
 *
 * `undefined` sobrevive a `JSON.stringify` como clave ausente, pero una cadena
 * vacía NO: viajaría como respuesta vacía y el dossier la imprimiría como si
 * alguien hubiera contestado en blanco. Aquí un hueco se queda hueco.
 */
function put<T extends object, K extends keyof T>(
  target: T,
  key: K,
  value: T[K] | null | undefined,
): void {
  if (value === undefined || value === null) return;
  if (typeof value === "string" && value.trim().length === 0) return;
  target[key] = value;
}

/** Copia una lista sólo si tiene elementos. El backend no acepta `null` aquí. */
function putList<T extends object, K extends keyof T>(
  target: T,
  key: K,
  value: readonly unknown[] | undefined,
): void {
  if (!value || value.length === 0) return;
  target[key] = [...value] as unknown as T[K];
}

function projectContext(caseRecord: CaseRecord): ProjectedContext {
  const context = caseRecord.context ?? {};
  const projected: ProjectedContext = {};
  put(projected, "study_kind", context.studyKind);
  put(projected, "question", context.question);
  put(projected, "decision", context.decision);
  put(projected, "system_rationale", context.systemRationale);
  put(projected, "controls", context.controls);
  put(projected, "assumptions", context.assumptions);
  put(projected, "uncertainties", context.uncertainties);
  put(projected, "notes", context.notes);
  return projected;
}

/**
 * Configuración declarada.
 *
 * PRIORIDAD AL PREFLIGHT. `executionConfig` es la configuración EFECTIVA que el
 * backend inspeccionó y con la que se ejecutó — incluida la caja que derivó él
 * mismo cuando la interfaz partía del sentinel (0,0,0). Los inputs del caso son
 * lo que se pidió; el preflight es lo que se comprobó. El dossier documenta lo
 * segundo, y sólo cae en lo primero cuando no hay preflight que consultar.
 */
function projectConfig(caseRecord: CaseRecord): ProjectedConfig | undefined {
  const effective = caseRecord.preflight?.executionConfig;
  const config: ProjectedConfig = {};
  if (effective) {
    put(config, "grid_center", effective.gridCenter as [number, number, number]);
    put(config, "grid_size", effective.gridSize as [number, number, number]);
    putList(config, "custom_hotspots", effective.customHotspots);
    put(config, "docking_engine", effective.dockingEngine);
    put(config, "exhaustiveness", effective.exhaustiveness);
    put(config, "num_poses", effective.numPoses);
    put(config, "seed", effective.seed);
    put(config, "pipeline_config", effective.pipelineConfig);
  } else {
    const inputs = caseRecord.inputs;
    put(config, "grid_center", inputs?.grid?.center as [number, number, number] | undefined);
    put(config, "grid_size", inputs?.grid?.size as [number, number, number] | undefined);
    putList(config, "custom_hotspots", inputs?.customHotspots);
    put(config, "docking_engine", inputs?.dockingEngine);
    put(config, "exhaustiveness", inputs?.exhaustiveness);
    put(config, "num_poses", inputs?.numPoses);
    put(config, "pipeline_config", inputs?.pipelineConfig);
    // `seed` NO tiene equivalente en los inputs del caso: sólo existe si el
    // preflight la fijó. No se inventa una.
  }
  return Object.keys(config).length > 0 ? config : undefined;
}

function projectInputs(caseRecord: CaseRecord): ProjectedInputs {
  const inputs: ProjectedInputs = {};

  const receptor = caseRecord.inputs?.receptor;
  if (receptor?.pdbId && receptor.pdbId.trim().length > 0) {
    const projected: ProjectedReceptor = { pdb_id: receptor.pdbId };
    put(projected, "chain", receptor.chain);
    put(projected, "origin", receptor.origin);
    put(projected, "name", receptor.name);
    put(projected, "target_id", receptor.targetId);
    inputs.receptor = projected;
  }

  const ligand = caseRecord.inputs?.ligand;
  if (ligand?.inputSmiles && ligand.inputSmiles.trim().length > 0) {
    const projected: ProjectedLigand = { input_smiles: ligand.inputSmiles };
    put(projected, "canonical_smiles", ligand.canonicalSmiles);
    put(projected, "name", ligand.name);
    inputs.ligand = projected;
  }

  const config = projectConfig(caseRecord);
  if (config) inputs.config = config;

  return inputs;
}

function projectPreflight(caseRecord: CaseRecord): ProjectedPreflight | undefined {
  const preflight = caseRecord.preflight;
  if (!preflight?.fingerprint) return undefined;
  const projected: ProjectedPreflight = { fingerprint: preflight.fingerprint };
  put(projected, "generated_at", preflight.generatedAt);
  put(projected, "schema_version", preflight.schemaVersion);
  put(projected, "execution_route", preflight.executionRoute);
  putList(projected, "blockers", preflight.blockers);
  putList(projected, "warnings", preflight.warnings);
  putList(projected, "not_evaluated", preflight.notEvaluated);
  put(projected, "receptor_label", preflight.receptorLabel);
  put(projected, "ligand_label", preflight.ligandLabel);
  put(projected, "grid_label", preflight.gridLabel);
  // `inputDocument` NO viaja: es procedencia local del caso, el contrato no lo
  // acepta (`extra="forbid"`) y enviarlo sería un 422.
  return projected;
}

/**
 * Identidad de la corrida.
 *
 * Sale de `activeRun`, que es lo que el CASO afirma haber lanzado. Si el caso
 * no conserva corrida, se declara la del resultado que se está documentando:
 * es un identificador real y observado, no un valor inventado. Sin `task_id` el
 * backend no podría comprobar que el resultado guardado es de esta corrida, y
 * ese contraste —el 409— es justo lo que impide empaquetar en silencio el
 * resultado de otra.
 */
function projectRun(
  caseRecord: CaseRecord,
  reportable: ReportableResult | null | undefined,
): ProjectedRun | undefined {
  const run = caseRecord.activeRun;
  if (run?.taskId) {
    const projected: ProjectedRun = { task_id: run.taskId };
    put(projected, "input_fingerprint", run.inputFingerprint);
    put(projected, "execution_state", run.executionState);
    put(projected, "started_at", run.startedAt);
    put(projected, "last_error", run.lastError);
    return projected;
  }
  if (reportable?.taskId) return { task_id: reportable.taskId };
  return undefined;
}

function projectDecisions(caseRecord: CaseRecord): readonly ProjectedDecision[] | undefined {
  const decisions = caseRecord.decisions;
  if (!decisions || decisions.length === 0) return undefined;
  return decisions.map((decision) => {
    const entry: ProjectedDecision = {
      control_code: decision.controlCode,
      fingerprint: decision.fingerprint,
      decision: decision.decision,
    };
    put(entry, "at", decision.at);
    put(entry, "note", decision.note);
    return entry;
  });
}

/**
 * Traduce el caso a la proyección que acepta el backend. Función PURA.
 *
 * Es pura a propósito: la conversión camelCase → snake_case es exactamente la
 * clase de código que se rompe en silencio, y una función sin entorno se puede
 * comprobar campo a campo sin montar nada.
 */
export function buildCaseProjection(
  caseRecord: CaseRecord,
  reportable: ReportableResult | null | undefined,
  runInputsRelation: RunInputsRelation,
): CaseProjection {
  const projection: CaseProjection = {
    projection_version: PROJECTION_VERSION,
    case_id: caseRecord.id,
    name: caseRecord.name,
    context: projectContext(caseRecord),
    inputs: projectInputs(caseRecord),
    run_inputs_relation: runInputsRelation,
  };

  put(projection, "case_schema_version", caseRecord.schemaVersion);
  put(projection, "created_at", caseRecord.createdAt);

  const preflight = projectPreflight(caseRecord);
  if (preflight) projection.preflight = preflight;

  const run = projectRun(caseRecord, reportable);
  if (run) projection.run = run;

  const decisions = projectDecisions(caseRecord);
  if (decisions) projection.decisions = decisions;

  if (caseRecord.disposition) {
    projection.disposition = {
      kind: caseRecord.disposition.kind,
      rationale: caseRecord.disposition.rationale,
      fingerprint: caseRecord.disposition.fingerprint,
      at: caseRecord.disposition.at,
    };
  }

  return projection;
}

// ── Transporte ───────────────────────────────────────────────────────

/**
 * Fallo del dossier, con el código para poder decidir qué ofrecer.
 *
 * `status` es `null` cuando ni siquiera hubo respuesta (motor apagado, red
 * caída). Se distingue a propósito: «no contestó» y «contestó que no» piden
 * cosas distintas del usuario.
 */
export class DossierError extends Error {
  readonly status: number | null;

  constructor(message: string, status: number | null) {
    super(message);
    this.name = "DossierError";
    this.status = status;
  }
}

/** El backend contesta `{"detail": …}`; en 422, una lista de errores. */
function extractDetail(body: unknown): string | null {
  if (typeof body === "string") return body.trim() || null;
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail.trim() || null;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const entry = item as { loc?: unknown; msg?: unknown };
        const msg = typeof entry.msg === "string" ? entry.msg : null;
        if (!msg) return null;
        const loc = Array.isArray(entry.loc)
          ? entry.loc.filter((part) => part !== "body").join(".")
          : "";
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter((part): part is string => Boolean(part));
    return parts.length > 0 ? parts.join(" · ") : null;
  }
  return null;
}

/** Lo que se dice cuando el backend no dijo nada útil. Nunca sustituye a lo suyo. */
function fallbackMessage(status: number): string {
  switch (status) {
    case 403:
      return "Este resultado no pertenece a la sesión actual, así que su dossier no se puede generar.";
    case 404:
      return "El motor no encuentra la molécula o su resultado. Puede que la corrida ya no esté guardada.";
    case 409:
      return (
        "El caso pide una corrida y el resultado almacenado pertenece a otra. " +
        "No se genera un dossier que afirme describir algo que no describe."
      );
    case 422:
      return "El motor rechazó la proyección del caso: hay un campo que el contrato del dossier no acepta.";
    default:
      return `El dossier no se pudo generar (HTTP ${status}).`;
  }
}

async function describeFailure(response: Response): Promise<string> {
  let raw = "";
  try {
    raw = await response.text();
  } catch {
    // Cuerpo ilegible: queda el código, que ya dice bastante.
  }
  let detail: string | null = null;
  if (raw) {
    try {
      detail = extractDetail(JSON.parse(raw));
    } catch {
      // No era JSON. El texto crudo puede seguir siendo útil, pero no se
      // vuelca entero en la interfaz: un stack trace no ayuda a nadie.
      detail = raw.length <= 300 ? raw.trim() || null : null;
    }
  }
  return detail ?? fallbackMessage(response.status);
}

function isAbort(error: unknown): boolean {
  return (error as { name?: string } | null)?.name === "AbortError";
}

/** Nombre propuesto por el backend en `Content-Disposition`, si lo hay. */
function filenameFromDisposition(response: Response): string | null {
  const disposition =
    response.headers.get("content-disposition") ?? response.headers.get("Content-Disposition");
  if (!disposition || !disposition.includes("filename=")) return null;
  const raw = disposition.split("filename=")[1]?.split(";")[0];
  const clean = raw?.replace(/['"]/g, "").trim();
  return clean && clean.length > 0 ? clean : null;
}

export interface DossierArtifact {
  readonly blob: Blob;
  /** El que propuso el backend. `null` si no propuso ninguno. */
  readonly filename: string | null;
}

async function postProjection(
  moleculeId: string,
  kind: "preview" | "package",
  projection: CaseProjection,
  signal?: AbortSignal,
): Promise<DossierArtifact> {
  const base = await getApiUrl();
  const url = `${base}/evaluation/dossier/${encodeURIComponent(moleculeId)}/${kind}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "ngrok-skip-browser-warning": "true",
        ...getAuthHeaders(),
      },
      cache: "no-store",
      signal,
      body: JSON.stringify(projection),
    });
  } catch (error) {
    if (isAbort(error)) throw error;
    // El transporte NO se convierte en un diagnóstico científico: «no se pudo
    // contactar» nunca se cuenta como «el caso es inválido».
    throw new DossierError(
      "Error de conexión: no se pudo contactar con el motor local de MolDesign. " +
        "Revisa su estado y vuelve a intentarlo.",
      null,
    );
  }

  if (!response.ok) {
    throw new DossierError(await describeFailure(response), response.status);
  }

  return { blob: await response.blob(), filename: filenameFromDisposition(response) };
}

/** Dossier PDF del caso, para leer en pantalla. */
export function requestDossierPreview(
  moleculeId: string,
  projection: CaseProjection,
  signal?: AbortSignal,
): Promise<DossierArtifact> {
  return postProjection(moleculeId, "preview", projection, signal);
}

/** Paquete reproducible (ZIP con manifiesto y hashes). */
export function requestDossierPackage(
  moleculeId: string,
  projection: CaseProjection,
  signal?: AbortSignal,
): Promise<DossierArtifact> {
  return postProjection(moleculeId, "package", projection, signal);
}

// ── Nombres de archivo ───────────────────────────────────────────────

/** Misma lista blanca que `services/dossier/package.py::sanitizar`. */
export function sanitizeFilenamePart(value: string, maximum = 64): string {
  let clean = (value ?? "").trim().replace(/[^A-Za-z0-9._-]+/g, "-");
  clean = clean.replace(/\.{2,}/g, ".");
  clean = clean.replace(/-{2,}/g, "-").replace(/^[-._]+|[-._]+$/g, "");
  if (!clean) clean = "sin-nombre";
  return clean.slice(0, maximum);
}

/** Nombre del PDF derivado del caso. Espejo del que compone el backend. */
export function dossierPdfFilename(caseName: string): string {
  return `dossier_${sanitizeFilenamePart(caseName, 60)}.pdf`;
}

/** Nombre del ZIP derivado del caso y la corrida. Espejo de `raiz_paquete`. */
export function dossierPackageFilename(caseId: string, taskId: string | undefined): string {
  const short = sanitizeFilenamePart(taskId || "sin-corrida", 12);
  return `moldesign_case_${sanitizeFilenamePart(caseId, 40)}_run_${short}.zip`;
}

/**
 * Guarda un blob con el mismo mecanismo que ya usa el producto.
 *
 * Es el idioma de `lib/api.ts::downloadCertificate` y del complejo PDB en la
 * evaluación: object URL, ancla con `download`, y revocación inmediata. NO se
 * cuelga de `DownloadProvider`, que gestiona la descarga de MODELOS y del motor
 * —progreso, cancelación, reintento— y no tiene nada que ver con entregar un
 * archivo que ya está en memoria.
 */
export function saveBlobAs(
  blob: Blob,
  filename: string,
  source: ActivitySource = "general",
  activityId = beginFileDownload(filename, source),
): void {
  const url = window.URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    completeFileDownload(activityId, filename, source);
  } catch (error) {
    failFileDownload(activityId, filename, source);
    throw error;
  } finally {
    window.URL.revokeObjectURL(url);
  }
}
