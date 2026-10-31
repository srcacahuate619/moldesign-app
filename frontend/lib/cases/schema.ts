// =====================================================================
// Validacion, serializacion y versionado del manifiesto `case.json`
// =====================================================================
//
// REGLA CENTRAL: un manifiesto invalido NUNCA produce un caso parcial. Produce
// un `CaseError` con su codigo y su razon. Rellenar huecos con valores por
// defecto convertiria un archivo corrupto en un caso que parece sano, que es
// exactamente el modo de fallo que este producto no se puede permitir.
//
// El manifiesto en disco es la FUENTE DE VERDAD. El indice de recientes es solo
// una cache de ubicaciones y puede estar desactualizado sin consecuencias.
//
// Versionado: `parseCaseManifest` acepta versiones conocidas y migra hacia
// arriba con `migrateManifest`. Una version MAYOR que la soportada se rechaza
// con `UNSUPPORTED_VERSION` — leerla a medias seria peor que no leerla.

import { frontendMessage, type FrontendText } from "../frontendError";
import {
  ActiveRun,
  CASE_SCHEMA_VERSION,
  CASE_STATUSES,
  CASE_VIEWS,
  CASE_STUDY_KINDS,
  CaseContext,
  CaseDisposition,
  CaseDispositionKind,
  CaseError,
  CaseRecord,
  CaseStatus,
  CaseStorage,
  CaseStructuralSystem,
  CaseStudyKind,
  CaseGrid,
  CaseInputs,
  CasePipelineConfig,
  CaseLigand,
  CaseReceptor,
  CaseRun,
  CaseRunProtocol,
  CaseView,
  HumanDecision,
  latestRun,
  normalizeReceptorOrigin,
  PreflightSummary,
  viewFromLegacySection,
  RUN_EXECUTION_STATES,
  RunExecutionState,
  SUPPORTED_SCHEMA_VERSIONS,
  upsertRun,
} from "./types";

// ── Utilidades de tipo ───────────────────────────────────────────────

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readString(source: Record<string, unknown>, key: string): string | undefined {
  const value = source[key];
  return typeof value === "string" ? value : undefined;
}

function requireString(
  source: Record<string, unknown>,
  key: string,
  where: string,
): string {
  const value = source[key];
  if (typeof value !== "string" || value.length === 0) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_00", { v0: key }),
      frontendMessage("case_schema_01", { v0: where, v1: key, v2: describe(value) }),
    );
  }
  return value;
}

function describe(value: unknown): FrontendText {
  if (value === null) return "null";
  if (Array.isArray(value)) return frontendMessage("case_schema_array");
  return typeof value;
}

function requireEnum<T extends string>(
  source: Record<string, unknown>,
  key: string,
  allowed: readonly T[],
  where: string,
): T {
  const value = source[key];
  if (typeof value !== "string" || !allowed.includes(value as T)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_02", { v0: key }),
      frontendMessage("case_schema_03", { v0: where, v1: key, v2: allowed.join(", "), v3: describe(value) }),
    );
  }
  return value as T;
}

function requireBoolean(
  source: Record<string, unknown>,
  key: string,
  where: string,
): boolean {
  const value = source[key];
  if (typeof value !== "boolean") {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_04", { v0: key }),
      frontendMessage("case_schema_05", { v0: where, v1: key, v2: describe(value) }),
    );
  }
  return value;
}

/** ISO 8601 con `Z`. Se valida que sea una fecha real, no solo una cadena. */
function requireIsoDate(
  source: Record<string, unknown>,
  key: string,
  where: string,
): string {
  const value = requireString(source, key, where);
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_06", { v0: key }),
      frontendMessage("case_schema_07", { v0: where, v1: key, v2: JSON.stringify(value) }),
    );
  }
  return value;
}

// ── Nombres seguros ──────────────────────────────────────────────────

/**
 * Nombre de carpeta seguro a partir del nombre visible del caso.
 *
 * ESTA FUNCION ES UNA FRONTERA DE SEGURIDAD. Impide, por construccion:
 *   - separadores de ruta (`/`, `\`) — escapar del directorio elegido;
 *   - `.` y `..` — subir de nivel;
 *   - raices absolutas y letras de unidad (`C:`) — saltar a otro sitio;
 *   - caracteres reservados de Windows (`<>:"|?*`) y de control;
 *   - nombres reservados de Windows (CON, PRN, AUX, NUL, COM1..9, LPT1..9);
 *   - punto o espacio final, que Windows recorta en silencio.
 *
 * La misma regla esta implementada en Rust (`src-tauri/src/cases.rs`) porque el
 * proceso que escribe es el que debe defenderse: validar solo en el cliente es
 * una sugerencia, no un control.
 */
const RESERVED_WINDOWS_NAMES = new Set([
  "con", "prn", "aux", "nul",
  "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
  "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
]);

/**
 * Largo máximo del nombre de carpeta, en BYTES de UTF-8. Rust
 * (`validate_folder_name`) mide `trimmed.len()`, que en un `&str` son bytes: con
 * una `á` de dos bytes, 64 caracteres no caben. Medir aquí en caracteres dejaba
 * pasar nombres que Rust rechazaba después con `UNSAFE_NAME`.
 */
export const MAX_FOLDER_NAME_LENGTH = 64;

const utf8Bytes = (value: string): number => new TextEncoder().encode(value).length;

export function sanitizeFolderName(rawName: string): string {
  // NFC: un acento escrito como letra + marca combinada (teclados, IME y pegados
  // desde macOS) pasa a la letra compuesta, que es lo que se espera ver en disco.
  const trimmed = rawName.normalize("NFC").trim();
  if (trimmed.length === 0) {
    throw new CaseError("UNSAFE_NAME", frontendMessage("case_schema_08"));
  }

  // Sustituye TODO lo que no sea seguro. Lista blanca, no lista negra: una
  // lista negra siempre olvida un caracter.
  let safe = "";
  for (const char of trimmed) {
    const code = char.codePointAt(0) ?? 0;
    // Letras y números de CUALQUIER alfabeto (más sus marcas): «Inhibición» y
    // «piñón» son nombres de carpeta válidos en Windows. La lista blanca era sólo
    // ASCII y convertía «Prueba de cápsula» en «Prueba de c-psula» (QA1-001). Lo
    // que Windows no admite (`<>:"|?*`, controles) es puntuación y sigue fuera.
    const isAlnum = /^[\p{L}\p{N}\p{M}]$/u.test(char);
    const isAllowedPunct = char === "-" || char === "_" || char === " ";
    if (code < 32 || code === 127) safe += "-";
    else if (isAlnum || isAllowedPunct) safe += char;
    else safe += "-";
  }

  safe = safe.replace(/\s+/g, " ").replace(/-{2,}/g, "-").trim();
  // Windows recorta puntos y espacios finales sin avisar: quitarlos aqui evita
  // que la carpeta creada no coincida con la que creemos haber creado. Tambien
  // se quitan los guiones de los bordes, que son residuo de la sustitucion de
  // arriba y no informacion del usuario: `caso.` no debe quedar como `caso-`.
  const trimEdges = (value: string) => value.replace(/^[-. ]+/, "").replace(/[-. ]+$/, "");
  safe = trimEdges(safe);

  if (utf8Bytes(safe) > MAX_FOLDER_NAME_LENGTH) {
    let cut = "";
    for (const char of safe) {
      if (utf8Bytes(cut + char) > MAX_FOLDER_NAME_LENGTH) break;
      cut += char;
    }
    safe = trimEdges(cut);
  }

  if (safe.length === 0) {
    throw new CaseError(
      "UNSAFE_NAME",
      frontendMessage("case_schema_09"),
      frontendMessage("case_schema_10", { v0: JSON.stringify(rawName) }),
    );
  }

  if (RESERVED_WINDOWS_NAMES.has(safe.toLowerCase())) {
    throw new CaseError(
      "UNSAFE_NAME",
      frontendMessage("case_schema_11", { v0: safe }),
      frontendMessage("case_schema_12"),
    );
  }

  return safe;
}

/** `true` si el nombre puede convertirse en carpeta sin lanzar. */
export function isSafeFolderName(rawName: string): boolean {
  try {
    sanitizeFolderName(rawName);
    return true;
  } catch {
    return false;
  }
}

// ── Identificadores ──────────────────────────────────────────────────

export function generateCaseId(): string {
  const cryptoObj = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
    return cryptoObj.randomUUID();
  }
  // Fallback determinista en forma, aleatorio en contenido. jsdom antiguo y
  // algunos webviews no exponen randomUUID.
  const bytes = new Uint8Array(16);
  if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
    cryptoObj.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return [
    hex.slice(0, 8), hex.slice(8, 12), hex.slice(12, 16), hex.slice(16, 20), hex.slice(20, 32),
  ].join("-");
}

// ── Contexto ─────────────────────────────────────────────────────────

/**
 * Lee el contexto de forma ESTRICTA.
 *
 * La version anterior era tolerante: un `question: 42` se descartaba y el campo
 * aparecia como "No definido". Eso es exactamente lo que no se puede hacer —
 * confunde «nunca se respondio» con «la respuesta se perdio o se corrompio», y
 * el dossier acabaria declarando lo primero cuando pasó lo segundo.
 *
 * Un campo AUSENTE sigue siendo valido: la ausencia es un estado legitimo. Lo
 * que se rechaza es un campo PRESENTE con un tipo que no corresponde.
 */
function parseContext(value: unknown, where: string): CaseContext {
  if (value === undefined) return {};
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_13"),
      frontendMessage("case_schema_14", { v0: where, v1: describe(value) }),
    );
  }
  const context: {
    -readonly [K in keyof CaseContext]: CaseContext[K];
  } = {};

  if (value.studyKind !== undefined) {
    const studyKind = value.studyKind;
    if (typeof studyKind !== "string" || !CASE_STUDY_KINDS.includes(studyKind as CaseStudyKind)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_15"),
        frontendMessage("case_schema_16", { v0: where, v1: JSON.stringify(studyKind) }),
      );
    }
    context.studyKind = studyKind as CaseStudyKind;
  }

  for (const key of [
    "question", "decision", "systemRationale", "controls", "assumptions", "uncertainties", "notes",
  ] as const) {
    const raw = value[key];
    if (raw === undefined) continue;
    if (typeof raw !== "string") {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_17", { v0: key }),
        frontendMessage("case_schema_18", { v0: where, v1: key, v2: describe(raw) }),
      );
    }
    // Una cadena en blanco SI se normaliza a ausente: es lo que produce borrar
    // el campo en la interfaz, no una corrupcion.
    if (raw.trim().length > 0) context[key] = raw;
  }
  return context;
}

/**
 * Lee `activeRun` de forma ESTRICTA.
 *
 * Ausente es valido —no hay corrida— pero presente y mal formado NO se
 * descarta: una corrida que existe y cuyo registro esta roto es justo lo que no
 * se puede tratar como "no hay corrida", porque la tarea sigue viva en el
 * backend y perderiamos su rastro.
 */
/**
 * Parsea UNA corrida del libro.
 *
 * `path` es la ruta exacta dentro del manifiesto —`case.json.runs[2]` o, al
 * migrar de v6, `case.json.activeRun`— porque el `detail` de un manifiesto
 * corrupto tiene que decir qué fila falla, no que «alguna» falla.
 */
function parseRunEntry(value: unknown, path: string): CaseRun {
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_19"),
      frontendMessage("case_schema_20", { v0: path, v1: describe(value) }),
    );
  }
  const taskId = requireString(value, "taskId", path);
  const executionState = requireEnum(
    value, "executionState", RUN_EXECUTION_STATES, path,
  ) as RunExecutionState;
  const startedAt = requireIsoDate(value, "startedAt", path);

  const run: { -readonly [K in keyof CaseRun]: CaseRun[K] } = {
    taskId, executionState, startedAt,
  };
  if (value.moleculeId !== undefined) {
    if (typeof value.moleculeId !== "string" || value.moleculeId.length === 0) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_21"),
        frontendMessage("case_schema_22", { v0: path }),
      );
    }
    run.moleculeId = value.moleculeId;
  }
  if (value.lastKnownProgress !== undefined) {
    if (typeof value.lastKnownProgress !== "number" || !Number.isFinite(value.lastKnownProgress)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_23"),
        frontendMessage("case_schema_24", { v0: path }),
      );
    }
    run.lastKnownProgress = value.lastKnownProgress;
  }
  if (value.lastError !== undefined) {
    if (typeof value.lastError !== "string") {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_25"),
        frontendMessage("case_schema_26", { v0: path }),
      );
    }
    run.lastError = value.lastError;
  }
  if (value.inputFingerprint !== undefined) {
    if (typeof value.inputFingerprint !== "string" || value.inputFingerprint.length === 0) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_27"),
        frontendMessage("case_schema_28", { v0: path }),
      );
    }
    run.inputFingerprint = value.inputFingerprint;
  }
  if (value.finishedAt !== undefined && value.finishedAt !== null) {
    run.finishedAt = requireIsoDate(value, "finishedAt", path);
  }
  const ligandSmiles = parseOptionalString(value.ligandSmiles, `${path}.ligandSmiles`);
  if (ligandSmiles) run.ligandSmiles = ligandSmiles;
  if (value.affinityKcal !== undefined && value.affinityKcal !== null) {
    if (typeof value.affinityKcal !== "number" || !Number.isFinite(value.affinityKcal)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_29"),
        frontendMessage("case_schema_30", { v0: path }),
      );
    }
    run.affinityKcal = value.affinityKcal;
  }
  const protocol = parseRunProtocol(value.protocol, `${path}.protocol`);
  if (protocol) run.protocol = protocol;
  return run;
}

function parseRunProtocol(value: unknown, path: string): CaseRunProtocol | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_31"),
      frontendMessage("case_schema_20", { v0: path, v1: describe(value) }),
    );
  }
  return {
    dockingEngine: requireString(value, "dockingEngine", path),
    exhaustiveness: parsePositiveInteger(value.exhaustiveness, `${path}.exhaustiveness`),
    numPoses: parsePositiveInteger(value.numPoses, `${path}.numPoses`),
    conformers: parsePositiveInteger(value.conformers, `${path}.conformers`),
  };
}

/**
 * Parsea el libro entero.
 *
 * AUSENTE ES VÁLIDO y significa libro vacío: un caso recién creado no ha
 * lanzado nada. Lo que no se acepta es un `runs` presente que no sea una lista,
 * ni dos filas con el mismo `taskId`: un libro con la misma corrida dos veces
 * no permitiría decir cuál de las dos es la buena.
 */
function parseCaseRuns(value: unknown, where: string): readonly CaseRun[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_32"),
      frontendMessage("case_schema_33", { v0: where, v1: describe(value) }),
    );
  }
  const runs = value.map((entry, index) => parseRunEntry(entry, `${where}.runs[${index}]`));
  const seen = new Set<string>();
  for (const run of runs) {
    if (seen.has(run.taskId)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_34"),
        frontendMessage("case_schema_35", { v0: where, v1: run.taskId }),
      );
    }
    seen.add(run.taskId);
  }
  return runs;
}

function parseStorage(value: unknown, where: string): CaseStorage {
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_36"),
      frontendMessage("case_schema_37", { v0: where, v1: describe(value) }),
    );
  }
  const mode = requireEnum(value, "mode", ["browser", "folder"] as const, `${where}.storage`);
  if (mode === "browser") {
    return { mode: "browser", label: "Guardado en este navegador" };
  }
  const path = requireString(value, "path", `${where}.storage`);
  return { mode: "folder", path };
}

// ── Inputs, preflight y decisiones ───────────────────────────────────
//
// MISMA REGLA QUE EL RESTO DEL ARCHIVO: ausente es válido, presente y mal
// formado NO se descarta en silencio. Un receptor corrupto que se leyera como
// «sin receptor» dejaría al usuario creyendo que nunca eligió uno, y el
// siguiente guardado borraría del disco lo que quedaba de su elección.

function parseNumberTriple(
  value: unknown,
  where: string,
): readonly [number, number, number] {
  if (
    !Array.isArray(value) ||
    value.length !== 3 ||
    value.some((v) => typeof v !== "number" || !Number.isFinite(v))
  ) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_38"),
      frontendMessage("case_schema_39", { v0: where, v1: describe(value) }),
    );
  }
  return [value[0] as number, value[1] as number, value[2] as number] as const;
}

function parseStringList(value: unknown, where: string): readonly string[] {
  if (!Array.isArray(value) || value.some((v) => typeof v !== "string")) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_40"),
      frontendMessage("case_schema_41", { v0: where, v1: describe(value) }),
    );
  }
  return value as string[];
}

function parsePositiveInteger(value: unknown, where: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_42"),
      frontendMessage("case_schema_43", { v0: where, v1: describe(value) }),
    );
  }
  return value;
}

function parsePipelineConfig(value: unknown, where: string): CasePipelineConfig | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_44"),
      frontendMessage("case_schema_45", { v0: where }),
    );
  }
  const config: {
    -readonly [K in keyof CasePipelineConfig]?: CasePipelineConfig[K]
  } = {};
  if (value.enabled_stages !== undefined) {
    config.enabled_stages = parseStringList(value.enabled_stages, `${where}.enabled_stages`);
  }
  if (value.stage_order !== undefined) {
    config.stage_order = parseStringList(value.stage_order, `${where}.stage_order`);
  }
  if (value.docking_engine !== undefined) config.docking_engine = requireString(value, "docking_engine", where);
  if (value.peptide_docking_engine !== undefined) config.peptide_docking_engine = requireString(value, "peptide_docking_engine", where);
  if (value.gnn_precision !== undefined) config.gnn_precision = requireString(value, "gnn_precision", where);
  for (const key of ["pro_workers", "pro_parallel_docks", "pro_mmgbsa_steps"] as const) {
    if (value[key] !== undefined && value[key] !== null) config[key] = parsePositiveInteger(value[key], `${where}.${key}`);
  }
  for (const key of ["pro_selectivity", "pro_mmgbsa"] as const) {
    if (value[key] !== undefined && typeof value[key] !== "boolean") {
      throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_46"), frontendMessage("case_schema_47", { v0: where, v1: key }));
    }
    if (typeof value[key] === "boolean") config[key] = value[key];
  }
  if (value.pro_anti_targets !== undefined) {
    config.pro_anti_targets = parseStringList(value.pro_anti_targets, `${where}.pro_anti_targets`);
  }
  if (value.stage_params !== undefined) {
    if (!isRecord(value.stage_params)) throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_48"), frontendMessage("case_schema_49", { v0: where }));
    const stageParams: Record<string, Record<string, unknown>> = {};
    for (const [stage, params] of Object.entries(value.stage_params)) {
      if (!isRecord(params)) throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_50"), frontendMessage("case_schema_51", { v0: where, v1: stage }));
      stageParams[stage] = { ...params };
    }
    config.stage_params = stageParams;
  }
  return Object.keys(config).length > 0 ? config : undefined;
}

function parseOptionalString(value: unknown, where: string): string | undefined {
  if (value === undefined || value === null) return undefined;
  if (typeof value !== "string" || value.length === 0) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_52"),
      frontendMessage("case_schema_53", { v0: where, v1: describe(value) }),
    );
  }
  return value;
}

function parseNonNegativeInteger(value: unknown, where: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_54"),
      frontendMessage("case_schema_55", { v0: where, v1: describe(value) }),
    );
  }
  return value;
}

function parseReceptor(value: unknown, where: string): CaseReceptor {
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_56"),
      frontendMessage("case_schema_20", { v0: where, v1: describe(value) }),
    );
  }
  const receptor: { -readonly [K in keyof CaseReceptor]: CaseReceptor[K] } = {
    pdbId: requireString(value, "pdbId", where),
    // Un origen desconocido NO invalida el receptor: es un estado legítimo y
    // el catálogo puede no declararlo.
    origin: normalizeReceptorOrigin(value.origin),
  };
  const targetId = readString(value, "targetId");
  if (targetId) receptor.targetId = targetId;
  const chain = readString(value, "chain");
  if (chain) receptor.chain = chain;
  const name = readString(value, "name");
  if (name) receptor.name = name;
  return receptor;
}

function parseLigand(value: unknown, where: string): CaseLigand {
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_57"),
      frontendMessage("case_schema_20", { v0: where, v1: describe(value) }),
    );
  }
  const ligand: { -readonly [K in keyof CaseLigand]: CaseLigand[K] } = {
    inputSmiles: requireString(value, "inputSmiles", where),
  };
  const canonical = readString(value, "canonicalSmiles");
  if (canonical) ligand.canonicalSmiles = canonical;
  const name = readString(value, "name");
  if (name) ligand.name = name;
  return ligand;
}

function parseInputs(value: unknown, where: string): CaseInputs | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_58"),
      frontendMessage("case_schema_59", { v0: where, v1: describe(value) }),
    );
  }
  const inputs: { -readonly [K in keyof CaseInputs]: CaseInputs[K] } = {};
  if (value.receptor !== undefined && value.receptor !== null) {
    inputs.receptor = parseReceptor(value.receptor, `${where}.inputs.receptor`);
  }
  if (value.ligand !== undefined && value.ligand !== null) {
    inputs.ligand = parseLigand(value.ligand, `${where}.inputs.ligand`);
  }
  if (value.grid !== undefined && value.grid !== null) {
    if (!isRecord(value.grid)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_38"),
        frontendMessage("case_schema_60", { v0: where }),
      );
    }
    const grid: CaseGrid = {
      center: parseNumberTriple(value.grid.center, `${where}.inputs.grid.center`),
      size: parseNumberTriple(value.grid.size, `${where}.inputs.grid.size`),
    };
    inputs.grid = grid;
  }
  if (value.customHotspots !== undefined && value.customHotspots !== null) {
    inputs.customHotspots = parseStringList(
      value.customHotspots,
      `${where}.inputs.customHotspots`,
    );
  }
  const engine = readString(value, "dockingEngine");
  if (engine) inputs.dockingEngine = engine;
  if (value.exhaustiveness !== undefined && value.exhaustiveness !== null) {
    inputs.exhaustiveness = parsePositiveInteger(
      value.exhaustiveness,
      `${where}.inputs.exhaustiveness`,
    );
  }
  if (value.numPoses !== undefined && value.numPoses !== null) {
    inputs.numPoses = parsePositiveInteger(value.numPoses, `${where}.inputs.numPoses`);
  }
  if (value.conformers !== undefined && value.conformers !== null) {
    inputs.conformers = parsePositiveInteger(value.conformers, `${where}.inputs.conformers`);
  }
  const pipelineConfig = parsePipelineConfig(value.pipelineConfig, `${where}.inputs.pipelineConfig`);
  if (pipelineConfig) inputs.pipelineConfig = pipelineConfig;
  return Object.keys(inputs).length > 0 ? inputs : undefined;
}

function parsePreflight(value: unknown, where: string): PreflightSummary | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_61"),
      frontendMessage("case_schema_62", { v0: where, v1: describe(value) }),
    );
  }
  const summary: { -readonly [K in keyof PreflightSummary]: PreflightSummary[K] } = {
    fingerprint: requireString(value, "fingerprint", `${where}.preflight`),
    inputDocument: requireString(value, "inputDocument", `${where}.preflight`),
    generatedAt: requireIsoDate(value, "generatedAt", `${where}.preflight`),
    schemaVersion: typeof value.schemaVersion === "number" ? value.schemaVersion : 1,
    executionRoute: readString(value, "executionRoute") ?? "desconocida",
    blockers: parseStringList(value.blockers ?? [], `${where}.preflight.blockers`),
    warnings: parseStringList(value.warnings ?? [], `${where}.preflight.warnings`),
    notEvaluated: parseStringList(value.notEvaluated ?? [], `${where}.preflight.notEvaluated`),
    receptorLabel: readString(value, "receptorLabel") ?? "No definido",
    ligandLabel: readString(value, "ligandLabel") ?? "No definido",
    gridLabel: readString(value, "gridLabel") ?? "No definido",
  };
  const receptorSourceSha256 = parseOptionalString(
    value.receptorSourceSha256,
    `${where}.preflight.receptorSourceSha256`,
  );
  if (receptorSourceSha256) summary.receptorSourceSha256 = receptorSourceSha256;
  const preparedReceptorSha256 = parseOptionalString(
    value.preparedReceptorSha256,
    `${where}.preflight.preparedReceptorSha256`,
  );
  if (preparedReceptorSha256) summary.preparedReceptorSha256 = preparedReceptorSha256;
  if (value.executionConfig !== undefined && value.executionConfig !== null) {
    if (!isRecord(value.executionConfig)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_63"),
        frontendMessage("case_schema_64", { v0: where }),
      );
    }
    const config = value.executionConfig;
    const pipelineConfig = parsePipelineConfig(
      config.pipelineConfig,
      `${where}.preflight.executionConfig.pipelineConfig`,
    );
    summary.executionConfig = {
      gridCenter: parseNumberTriple(
        config.gridCenter,
        `${where}.preflight.executionConfig.gridCenter`,
      ),
      gridSize: parseNumberTriple(
        config.gridSize,
        `${where}.preflight.executionConfig.gridSize`,
      ),
      customHotspots: parseStringList(
        config.customHotspots,
        `${where}.preflight.executionConfig.customHotspots`,
      ),
      dockingEngine: requireString(
        config,
        "dockingEngine",
        `${where}.preflight.executionConfig`,
      ),
      exhaustiveness: parsePositiveInteger(
        config.exhaustiveness,
        `${where}.preflight.executionConfig.exhaustiveness`,
      ),
      numPoses: parsePositiveInteger(
        config.numPoses,
        `${where}.preflight.executionConfig.numPoses`,
      ),
      seed: parseNonNegativeInteger(
        config.seed,
        `${where}.preflight.executionConfig.seed`,
      ),
      ...(config.conformers !== undefined && config.conformers !== null
        ? {
            conformers: parsePositiveInteger(
              config.conformers,
              `${where}.preflight.executionConfig.conformers`,
            ),
          }
        : {}),
      ...(pipelineConfig ? { pipelineConfig } : {}),
    };
  }
  return summary;
}

function parseStructuralSystem(value: unknown, where: string): CaseStructuralSystem | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_65"),
      frontendMessage("case_schema_66", { v0: where, v1: describe(value) }),
    );
  }
  if (!isRecord(value.grid)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_67"),
      frontendMessage("case_schema_68", { v0: where }),
    );
  }
  const pipelineConfig = parsePipelineConfig(
    value.pipelineConfig,
    `${where}.structuralSystem.pipelineConfig`,
  );
  const system: { -readonly [K in keyof CaseStructuralSystem]: CaseStructuralSystem[K] } = {
    lockedAt: requireIsoDate(value, "lockedAt", `${where}.structuralSystem`),
    sourceRunTaskId: requireString(value, "sourceRunTaskId", `${where}.structuralSystem`),
    inputFingerprint: requireString(value, "inputFingerprint", `${where}.structuralSystem`),
    receptor: parseReceptor(value.receptor, `${where}.structuralSystem.receptor`),
    grid: {
      center: parseNumberTriple(value.grid.center, `${where}.structuralSystem.grid.center`),
      size: parseNumberTriple(value.grid.size, `${where}.structuralSystem.grid.size`),
    },
    customHotspots: parseStringList(
      value.customHotspots,
      `${where}.structuralSystem.customHotspots`,
    ),
    dockingEngine: requireString(value, "dockingEngine", `${where}.structuralSystem`),
    exhaustiveness: parsePositiveInteger(
      value.exhaustiveness,
      `${where}.structuralSystem.exhaustiveness`,
    ),
    numPoses: parsePositiveInteger(value.numPoses, `${where}.structuralSystem.numPoses`),
    conformers: parsePositiveInteger(value.conformers, `${where}.structuralSystem.conformers`),
    ...(pipelineConfig ? { pipelineConfig } : {}),
  };
  const sourceHash = parseOptionalString(
    value.receptorSourceSha256,
    `${where}.structuralSystem.receptorSourceSha256`,
  );
  if (sourceHash) system.receptorSourceSha256 = sourceHash;
  const preparedHash = parseOptionalString(
    value.preparedReceptorSha256,
    `${where}.structuralSystem.preparedReceptorSha256`,
  );
  if (preparedHash) system.preparedReceptorSha256 = preparedHash;
  return system;
}

function parseDecisions(value: unknown, where: string): readonly HumanDecision[] | undefined {
  if (value === undefined || value === null) return undefined;
  if (!Array.isArray(value)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_69"),
      frontendMessage("case_schema_70", { v0: where, v1: describe(value) }),
    );
  }
  const decisions: HumanDecision[] = value.map((entry, index) => {
    if (!isRecord(entry)) {
      throw new CaseError(
        "INVALID_MANIFEST",
        frontendMessage("case_schema_71"),
        frontendMessage("case_schema_72", { v0: where, v1: index }),
      );
    }
    const decision: { -readonly [K in keyof HumanDecision]: HumanDecision[K] } = {
      controlCode: requireString(entry, "controlCode", `${where}.decisions[${index}]`),
      fingerprint: requireString(entry, "fingerprint", `${where}.decisions[${index}]`),
      decision: "reconocida",
      at: requireIsoDate(entry, "at", `${where}.decisions[${index}]`),
    };
    const note = readString(entry, "note");
    if (note) decision.note = note;
    return decision;
  });
  return decisions.length > 0 ? decisions : undefined;
}

function parseDisposition(value: unknown, where: string): CaseDisposition | undefined {
  if (value === undefined || value === null) return undefined;
  if (!isRecord(value)) {
    throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_73"), frontendMessage("case_schema_74", { v0: where }));
  }
  const kind = requireEnum(value, "kind", ["accept", "limit", "abstain"] as const, `${where}.disposition`) as CaseDispositionKind;
  const rationale = requireString(value, "rationale", `${where}.disposition`);
  if (rationale.length < 3 || rationale.length > 4000) {
    throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_75"), frontendMessage("case_schema_76", { v0: where }));
  }
  return {
    kind,
    rationale,
    fingerprint: requireString(value, "fingerprint", `${where}.disposition`),
    at: requireIsoDate(value, "at", `${where}.disposition`),
  };
}

/**
 * Historial durable de disposiciones (AMP-01). Cada entrada valida igual
 * que la vigente: un historial corrupto no se recorta en silencio, se
 * declara.
 */
function parseDispositions(value: unknown, where: string): readonly CaseDisposition[] | undefined {
  if (value === undefined || value === null) return undefined;
  if (!Array.isArray(value)) {
    throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_77"), frontendMessage("case_schema_78", { v0: where }));
  }
  const dispositions = value.map(
    (entry, index) => parseDisposition(entry, `${where}.dispositions[${index}]`),
  );
  if (dispositions.some((entry) => entry === undefined)) {
    throw new CaseError("INVALID_MANIFEST", frontendMessage("case_schema_77"), frontendMessage("case_schema_79", { v0: where }));
  }
  return dispositions.length > 0 ? (dispositions as CaseDisposition[]) : undefined;
}

// ── Migracion ────────────────────────────────────────────────────────

/**
 * Migra un manifiesto de una version soportada a la actual.
 *
 * v1 → v2: `activeSection` (siete valores, cinco de ellos destinos inertes)
 * pasa a `activeView` (dos modos reales). La conversion NO es una biyeccion y
 * no pretende serlo: `viewFromLegacySection` manda todo a `evaluation`, que es
 * lo unico afirmable sin comprobar si existe evidencia recuperable.
 *
 * v2 → v3: aparecen `inputs`, `preflight` y `decisions`. Los tres quedan
 * AUSENTES en un caso migrado: no habia donde guardarlos, asi que no hay nada
 * que recuperar y no se inventa.
 *
 * La clave vieja se ELIMINA. Dejarla conviviendo con la nueva daria dos
 * fuentes de verdad para lo mismo, y la proxima escritura tendria que decidir
 * cual gana.
 *
 * v3 → v4: aparece `structuralSystem`. Los casos anteriores conservan sus
 * corridas y sus inputs, pero no se les atribuye retrospectivamente un sistema
 * que nunca se selló junto al taskId.
 */
export function migrateManifest(
  raw: Record<string, unknown>,
  fromVersion: number,
): Record<string, unknown> {
  let current = raw;
  let version = fromVersion;

  if (version === 1) {
    const { activeSection, ...rest } = current;
    current = { ...rest, activeView: viewFromLegacySection(activeSection), schemaVersion: 2 };
    version = 2;
  }

  if (version === 2) {
    // v2 → v3: sólo se sube la versión.
    //
    // NO se inventan inputs. Un caso v2 se ejecutó con un receptor y un SMILES
    // que el manifiesto nunca guardó: rellenarlos con un valor por defecto
    // afirmaría una hipótesis que nadie declaró. Quedan ausentes, la interfaz
    // los pide, y la corrida guardada queda sin `inputFingerprint` — que es
    // exactamente lo que hace que se etiquete como «corrida anterior» en vez
    // de atribuirse a la hipótesis nueva.
    current = { ...current, schemaVersion: 3 };
    version = 3;
  }

  if (version === 3) {
    current = { ...current, schemaVersion: 4 };
    version = 4;
  }

  if (version === 4) {
    // v4 → v5: la disposición final se separa de los acuses de controles.
    // Queda ausente en los casos existentes: nunca se inventa una decisión.
    current = { ...current, schemaVersion: 5 };
    version = 5;
  }

  if (version === 5) {
    // v5 → v6 introduce aislamiento por cuenta. No se inventa propietario:
    // los casos legacy se reclaman únicamente después de que el backend
    // confirme que la sesión puede acceder a su corrida persistida.
    current = { ...current, schemaVersion: 6 };
    version = 6;
  }

  if (version === 6) {
    // v6 → v7: `activeRun` —una sola corrida, sobrescrita por la siguiente—
    // pasa a ser la primera fila del LIBRO. La corrida que el caso tenía se
    // conserva tal cual: es la única que ese manifiesto llegó a guardar y no
    // se inventan las anteriores, que nunca estuvieron ahí.
    //
    // La clave vieja se ELIMINA. `activeRun` se deriva ahora de la última fila
    // del libro; dejar las dos en disco daría dos fuentes de verdad para lo
    // mismo y la próxima escritura tendría que decidir cuál gana.
    const { activeRun: legacyRun, ...rest } = current;
    current = {
      ...rest,
      ...(legacyRun !== undefined && legacyRun !== null ? { runs: [legacyRun] } : {}),
      schemaVersion: 7,
    };
    version = 7;
  }

  if (version === CASE_SCHEMA_VERSION) return current;
  throw new CaseError(
    "UNSUPPORTED_VERSION",
    frontendMessage("case_schema_80", { v0: fromVersion }),
    frontendMessage("case_schema_81", { v0: SUPPORTED_SCHEMA_VERSIONS.join(", ") }),
  );
}

// ── Parseo ───────────────────────────────────────────────────────────

/**
 * Convierte JSON crudo en un `CaseRecord` validado, o lanza `CaseError`.
 *
 * No devuelve nunca un caso a medias. Los codigos posibles son
 * `INVALID_MANIFEST` y `UNSUPPORTED_VERSION`, y los dos llevan `detail` con el
 * campo exacto que fallo, para que el mensaje al usuario pueda ser concreto.
 */
export function parseCaseManifest(input: unknown, where = "case.json"): CaseRecord {
  if (!isRecord(input)) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_82"),
      frontendMessage("case_schema_83", { v0: describe(input) }),
    );
  }

  const rawVersion = input.schemaVersion;
  if (typeof rawVersion !== "number" || !Number.isInteger(rawVersion) || rawVersion < 1) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_84"),
      frontendMessage("case_schema_85", { v0: where, v1: describe(rawVersion) }),
    );
  }
  if (!SUPPORTED_SCHEMA_VERSIONS.includes(rawVersion)) {
    throw new CaseError(
      "UNSUPPORTED_VERSION",
      rawVersion > CASE_SCHEMA_VERSION
        ? frontendMessage("case_schema_86", { v0: rawVersion })
        : frontendMessage("case_schema_87", { v0: rawVersion }),
      frontendMessage("case_schema_88", { v0: SUPPORTED_SCHEMA_VERSIONS.join(", ") }),
    );
  }

  const migrated = migrateManifest(input, rawVersion);
  const runs = parseCaseRuns(migrated.runs, where);
  // `activeRun` NO se lee del manifiesto: se DERIVA de la última fila. Es lo
  // que hace estructuralmente imposible que el disco lleve una contradicción
  // entre el puntero y el libro.
  const activeRun = latestRun(runs);
  const inputs = parseInputs(migrated.inputs, where);
  const preflight = parsePreflight(migrated.preflight, where);
  const structuralSystem = parseStructuralSystem(migrated.structuralSystem, where);
  const decisions = parseDecisions(migrated.decisions, where);
  const disposition = parseDisposition(migrated.disposition, where);
  const dispositions = parseDispositions(migrated.dispositions, where);
  return {
    schemaVersion: CASE_SCHEMA_VERSION,
    id: requireString(migrated, "id", where),
    ...(readString(migrated, "ownerUserId")
      ? { ownerUserId: requireString(migrated, "ownerUserId", where) }
      : {}),
    name: requireString(migrated, "name", where),
    createdAt: requireIsoDate(migrated, "createdAt", where),
    updatedAt: requireIsoDate(migrated, "updatedAt", where),
    lastOpenedAt: requireIsoDate(migrated, "lastOpenedAt", where),
    status: requireEnum(migrated, "status", CASE_STATUSES, where) as CaseStatus,
    storage: parseStorage(migrated.storage, where),
    activeView: requireEnum(migrated, "activeView", CASE_VIEWS, where) as CaseView,
    context: parseContext(migrated.context, where),
    // No normalizar corrupción a `false`: en navegador no hay una segunda
    // frontera Rust que pueda detectar el tipo incorrecto.
    archived: requireBoolean(migrated, "archived", where),
    runs,
    ...(activeRun ? { activeRun } : {}),
    ...(inputs ? { inputs } : {}),
    ...(preflight ? { preflight } : {}),
    ...(structuralSystem ? { structuralSystem } : {}),
    ...(decisions ? { decisions } : {}),
    ...(disposition ? { disposition } : {}),
    ...(dispositions ? { dispositions } : {}),
  };
}

/** Serializa con claves ordenadas y salto final: diffs limpios en disco. */
export function serializeCaseManifest(record: CaseRecord): string {
  const ordered = {
    schemaVersion: record.schemaVersion,
    id: record.id,
    ...(record.ownerUserId ? { ownerUserId: record.ownerUserId } : {}),
    name: record.name,
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
    lastOpenedAt: record.lastOpenedAt,
    status: record.status,
    storage: record.storage,
    activeView: record.activeView,
    context: record.context,
    archived: record.archived,
    // Se omite si no hay corrida: un `null` en disco obligaria a distinguir
    // "sin corrida" de "corrida borrada", y no hay tal distincion. Lo mismo
    // vale para inputs, preflight, sistema estructural y decisiones.
    //
    // `activeRun` NO SE ESCRIBE. Es la última fila de `runs` y al releer se
    // deriva de ahí; persistirlo además dejaría en disco dos respuestas a la
    // misma pregunta, que es justo lo que la v7 vino a quitar.
    // `?? []` defensivo: el tipo lo exige, pero serializar es el paso que
    // ESCRIBE en disco y no puede reventar por un registro construido a mano
    // en un test o por un legacy que se coló sin pasar por el parser.
    ...((record.runs ?? []).length > 0 ? { runs: record.runs } : {}),
    ...(record.inputs ? { inputs: record.inputs } : {}),
    ...(record.preflight ? { preflight: record.preflight } : {}),
    ...(record.structuralSystem ? { structuralSystem: record.structuralSystem } : {}),
    ...(record.decisions && record.decisions.length > 0
      ? { decisions: record.decisions }
      : {}),
    ...(record.disposition ? { disposition: record.disposition } : {}),
    // AMP-01: el historial de disposiciones es durable. Se omite vacío por
    // la misma regla que todo lo demás: ausencia y vacío no se distinguen.
    ...(record.dispositions && record.dispositions.length > 0
      ? { dispositions: record.dispositions }
      : {}),
  };
  return `${JSON.stringify(ordered, null, 2)}\n`;
}

/** Parsea texto crudo. Un JSON malformado es `INVALID_MANIFEST`, no un crash. */
export function parseCaseManifestText(text: string, where = "case.json"): CaseRecord {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (error) {
    throw new CaseError(
      "INVALID_MANIFEST",
      frontendMessage("case_schema_89"),
      error instanceof Error ? error.message : String(error),
    );
  }
  return parseCaseManifest(parsed, where);
}

// ── Construccion ─────────────────────────────────────────────────────

export interface CreateCaseInput {
  readonly name: string;
  readonly studyKind: CaseStudyKind;
  readonly storage: CaseStorage;
  readonly ownerUserId: string;
  /** Inyectable para tests deterministas. */
  readonly now?: string;
  readonly id?: string;
}

/**
 * Construye un caso nuevo. Solo exige nombre, tipo y almacenamiento: las
 * preguntas cientificas NO bloquean la creacion (docs/53 §4 — declarar
 * supuestos es un paso posterior, no un peaje de entrada).
 */
export function createCaseRecord(input: CreateCaseInput): CaseRecord {
  const name = input.name.trim();
  if (name.length === 0) {
    throw new CaseError("UNSAFE_NAME", frontendMessage("case_schema_08"));
  }
  if (input.storage.mode === "folder") {
    // Falla temprano y con el mismo criterio que usara Rust al escribir.
    sanitizeFolderName(name);
  }
  const now = input.now ?? new Date().toISOString();
  return {
    schemaVersion: CASE_SCHEMA_VERSION,
    id: input.id ?? generateCaseId(),
    ownerUserId: input.ownerUserId,
    name,
    createdAt: now,
    updatedAt: now,
    lastOpenedAt: now,
    status: "draft",
    storage: input.storage,
    runs: [],
    activeView: "evaluation",
    context: { studyKind: input.studyKind },
    archived: false,
  };
}

/** Aplica cambios y actualiza `updatedAt`. `id` y `createdAt` son inmutables. */
export function touchCase(
  record: CaseRecord,
  changes: Partial<Omit<CaseRecord, "id" | "createdAt" | "schemaVersion">>,
  now = new Date().toISOString(),
): CaseRecord {
  return { ...record, ...changes, updatedAt: now };
}

/**
 * Escribe una corrida en el libro y reproyecta `activeRun` DE UNA VEZ.
 *
 * Única puerta por la que el libro cambia. Existe para que el invariante
 * —`activeRun` es la última fila— no dependa de que cada llamante se acuerde
 * de actualizar las dos cosas: en memoria no hay parseo que lo reconcilie, así
 * que un `touchCase({ runs })` suelto dejaría el puntero apuntando a la corrida
 * anterior hasta la próxima recarga.
 */
export function caseWithRun(
  record: CaseRecord,
  run: CaseRun,
  now = new Date().toISOString(),
): CaseRecord {
  const runs = upsertRun(record.runs, run);
  const projected = latestRun(runs);
  return touchCase(record, { runs, ...(projected ? { activeRun: projected } : {}) }, now);
}
