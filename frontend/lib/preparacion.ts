// =====================================================================
// Preparación — contrato de la auditoría de readiness de UNA corrida
// =====================================================================
//
// Espejo de `backend/services/dossier/preparacion.py` (`preparacion/v1`).
// La interfaz pinta lo que el backend decide: no recalcula estados, no agrega
// y no convierte una ausencia en «cumple». Lo único que hace aquí es decidir
// QUÉ corrida de un caso se puede auditar, con la misma relación
// corrida↔inputs que el informe del caso.
//
// Lo que NO puede pasar, y por qué la validación es estricta: el backend tiene
// techo en REVISIÓN mientras `FEP-06` no esté sellado. Si algún día llegara
// «TRANSFERIBLE», la interfaz lo enseñaría tal cual; lo que no hará nunca es
// fabricarlo a partir de bloques que «parecen» completos.

import {
  relacionDeLaCorridaActiva,
  type CaseRecord,
  type CaseRun,
  type ReportableResult,
  type RunInputsRelation,
} from "./cases/types";

export const PREPARACION_SCHEMA = "preparacion/v1";

export const BLOQUES_PREPARACION = ["receptor", "ligando", "pose", "entorno", "procedencia"] as const;
export type BloquePreparacionId = (typeof BLOQUES_PREPARACION)[number];

/** Taxonomía del dossier (`services/dossier/taxonomy.py`). */
export type EstadoCampo =
  | "NO_DEFINIDO"
  | "NO_EVALUADO"
  | "NO_DISPONIBLE"
  | "NO_APLICA"
  | "REVISAR"
  | "ABSTENCION"
  | "REGISTRADO"
  | "PASA";

export type EstadoBloque = "BLOQUEADO" | "REVISION" | "REGISTRADO";
export type EstadoPreparacion = "BLOQUEADO" | "REVISION" | "TRANSFERIBLE";

export interface RequisitoPreparacion {
  readonly clave: string;
  readonly etiqueta: string;
  /** Sólo viene si el estado es afirmativo o el valor ES la clasificación. */
  readonly valor: string | null;
  readonly estado: EstadoCampo;
  readonly razon: string | null;
  readonly valor_es_clasificacion: boolean;
  readonly fuente: string;
  readonly imprescindible: boolean;
  readonly accion_recomendada?: string;
  /** La acción en datos: con qué volver a evaluar. La pestaña lo ofrece como botón. */
  readonly reevaluar?: readonly { readonly tautomero: "entrada" | "canonico"; readonly smiles: string }[];
  /**
   * Decisión del investigador sobre este requisito en esta corrida. `resuelve` es falso si el
   * requisito bloquea: la decisión queda escrita, pero un bloqueo no se levanta declarándolo.
   */
  readonly decision?: { readonly justificacion: string; readonly registrada: string | null; readonly resuelve: boolean };
  /**
   * La revisión que pide es rutinaria: la pide toda corrida de esta ruta (protonación por plantilla,
   * Demostración, recorte multicadena…). Sigue abierta; `motivo` dice por qué no es de este caso.
   */
  readonly rutinaria?: { readonly motivo: string };
  readonly ubicacion?: readonly {
    readonly chain: string;
    readonly after: string;
    readonly before: string;
    readonly c_n_distance_A: number;
    readonly missing_declared: number | null;
    readonly distance_to_box_A: number;
    /** Desde el 2026-10-10, cuando la auditoría pudo medir desde el ligando. */
    readonly distance_to_ligand_A?: number;
    readonly site_critical: boolean;
  }[];
  /**
   * Lo que el contexto de ensayo del caso dice de este requisito (`moldesign.contexto_ensayo/1`): la
   * comparación de un campo contrastable (`campo`, `ensayo`, `corrida`, `estado`) o, en el resumen
   * `entorno.ensayo`, lo declarado sin contraparte en la corrida. Es otra forma que `ubicacion`: nunca
   * se mezclan, y el validador pide a cada una la suya.
   */
  readonly ensayo?: {
    readonly contrato: string;
    readonly campo?: string;
    readonly estado?: "coincide" | "discrepancia" | "desconocido";
    readonly fuente_ensayo?: string;
    readonly fuente_corrida?: string;
    readonly ensayo?: unknown;
    readonly corrida?: unknown;
    readonly declarados_sin_contraparte?: Readonly<Record<string, string | number>>;
  };
}

export interface BloquePreparacion {
  readonly id: BloquePreparacionId;
  readonly estado: EstadoBloque;
  /** En REVISIÓN sólo por lo que pide toda corrida de esta ruta. */
  readonly solo_rutinaria?: boolean;
  readonly requisitos: readonly RequisitoPreparacion[];
}

export interface AuditoriaPreparacion {
  readonly schema: typeof PREPARACION_SCHEMA;
  readonly alcance: string;
  readonly transferencia_fep_demostrada: boolean;
  readonly estado: EstadoPreparacion;
  readonly razon: string;
  readonly bloqueantes: readonly string[];
  /** Todo lo que pide revisión, también lo rutinario: la rutinaria sigue abierta. */
  readonly en_revision: readonly string[];
  /** Cuáles de `en_revision` pide toda corrida de esta ruta; el resto es de este caso. */
  readonly en_revision_rutinaria?: readonly string[];
  /** Sin bloqueos y con todo lo abierto rutinario: nada propio de este caso pide revisión. */
  readonly solo_rutinaria?: boolean;
  /** Requisitos que pedían revisión y resolvió una decisión justificada. */
  readonly decididos?: readonly string[];
  /** Huella con la que se registra una decisión sobre ESTA corrida (`tarea:<task_id>`). */
  readonly huella_de_decision?: string;
  /** Decisiones de Preparación sobre otras corridas del caso: no se aplican a ésta. */
  readonly decisiones_de_otras_corridas?: number;
  readonly bloques: readonly BloquePreparacion[];
  readonly corrida: {
    readonly case_id: string;
    readonly molecule_id: string;
    readonly task_id: string | null;
    readonly target: string;
    readonly pdb_id?: string | null;
  };
  readonly generated_at: string;
  readonly paquete: { readonly rotulo: string; readonly aviso: string };
}

const ESTADOS_GLOBALES: readonly string[] = ["BLOQUEADO", "REVISION", "TRANSFERIBLE"];
const ESTADOS_BLOQUE: readonly string[] = ["BLOQUEADO", "REVISION", "REGISTRADO"];

const ESTADOS_COMPARACION: readonly string[] = ["coincide", "discrepancia", "desconocido"];

/** La forma de `Requisito.ensayo`: una comparación de campo o el resumen de lo declarado sin contraparte. */
function ensayoValido(valor: unknown): boolean {
  if (valor === null || typeof valor !== "object" || Array.isArray(valor)) return false;
  const e = valor as Record<string, unknown>;
  if (typeof e.contrato !== "string" || e.contrato.length === 0) return false;
  if (e.declarados_sin_contraparte !== undefined) {
    const d = e.declarados_sin_contraparte;
    if (d === null || typeof d !== "object" || Array.isArray(d)) return false;
    return Object.values(d).every((x) => typeof x === "string" || (typeof x === "number" && Number.isFinite(x)));
  }
  return typeof e.campo === "string" && typeof e.estado === "string" && ESTADOS_COMPARACION.includes(e.estado) &&
    typeof e.fuente_ensayo === "string" && typeof e.fuente_corrida === "string";
}

/** Comprueba la forma antes de pintar nada. Una forma desconocida no es una auditoría. */
export function esAuditoriaPreparacion(value: unknown): value is AuditoriaPreparacion {
  if (!value || typeof value !== "object") return false;
  const v = value as Partial<AuditoriaPreparacion>;
  if (v.schema !== PREPARACION_SCHEMA) return false;
  if (typeof v.estado !== "string" || !ESTADOS_GLOBALES.includes(v.estado)) return false;
  if (!Array.isArray(v.bloques) || v.bloques.length !== BLOQUES_PREPARACION.length) return false;
  return v.bloques.every(
    (bloque, i) =>
      bloque?.id === BLOQUES_PREPARACION[i] &&
      ESTADOS_BLOQUE.includes(bloque.estado) &&
      Array.isArray(bloque.requisitos) &&
      bloque.requisitos.every(
        (r: Partial<RequisitoPreparacion> | null) =>
          typeof r?.clave === "string" && typeof r?.estado === "string" &&
          (r.accion_recomendada === undefined || typeof r.accion_recomendada === "string") &&
          (r.decision === undefined || (r.decision !== null && typeof r.decision === "object" &&
            typeof r.decision.justificacion === "string" && typeof r.decision.resuelve === "boolean")) &&
          (r.rutinaria === undefined || (r.rutinaria !== null && typeof r.rutinaria === "object" &&
            typeof r.rutinaria.motivo === "string" && r.rutinaria.motivo.length > 0)) &&
          (r.reevaluar === undefined || (Array.isArray(r.reevaluar) && r.reevaluar.every((o) =>
            o !== null && typeof o === "object" &&
            (o.tautomero === "entrada" || o.tautomero === "canonico") &&
            typeof o.smiles === "string" && o.smiles.length > 0,
          ))) &&
          (r.ensayo === undefined || ensayoValido(r.ensayo)) &&
          (r.ubicacion === undefined || (Array.isArray(r.ubicacion) && r.ubicacion.every((h) =>
            h !== null && typeof h === "object" &&
            typeof h.chain === "string" && typeof h.after === "string" && typeof h.before === "string" &&
            Number.isFinite(h.c_n_distance_A) && h.c_n_distance_A > 2 &&
            Number.isFinite(h.distance_to_box_A) && h.distance_to_box_A >= 0 &&
            (h.missing_declared === null || (typeof h.missing_declared === "number" && Number.isInteger(h.missing_declared) && h.missing_declared >= 0)) &&
            typeof h.site_critical === "boolean",
          ))),
      ),
  );
}

/** Qué se puede auditar de un caso. */
export type CorridaAuditable =
  | {
      readonly kind: "auditable";
      readonly run: CaseRun;
      readonly reportable: ReportableResult;
      readonly relation: RunInputsRelation;
    }
  | { readonly kind: "sin_corrida" }
  | { readonly kind: "corrida_no_encontrada" }
  | { readonly kind: "sin_terminar" }
  /** Terminó, pero cancelada o fallida: decir «no ha terminado» sería falso. */
  | { readonly kind: "sin_completar" }
  | { readonly kind: "sin_molecula" };

/** Libro en orden de arranque; conserva metadatos y el respaldo de casos antiguos. */
export function corridasDelCaso(record: CaseRecord): readonly CaseRun[] {
  const book = record.runs ?? [];
  const active = record.activeRun;
  if (!active) return book;
  return book.some((entry) => entry.taskId === active.taskId)
    ? book.map((entry) => entry.taskId === active.taskId ? { ...entry, ...active } : entry)
    : [...book, active];
}

/**
 * Resuelve la evaluación elegida, sin modificar el caso ni sustituirla por otra.
 * Sin selección explícita conserva el comportamiento de última completada.
 */
export function corridaDelCaso(record: CaseRecord, taskId?: string): CorridaAuditable {
  const candidates = corridasDelCaso(record);
  const run = taskId === undefined
    ? [...candidates].reverse().find((entry) => entry.executionState === "completed")
    : candidates.find((entry) => entry.taskId === taskId);
  if (!run) {
    if (taskId !== undefined) return { kind: "corrida_no_encontrada" };
    if (candidates.length === 0) return { kind: "sin_corrida" };
    const pending = candidates.some((entry) => entry.executionState !== "cancelled" && entry.executionState !== "failed");
    return { kind: pending ? "sin_terminar" : "sin_completar" };
  }
  if (run.executionState === "failed" || run.executionState === "cancelled") return { kind: "sin_completar" };
  if (run.executionState !== "completed") return { kind: "sin_terminar" };
  if (!run.moleculeId) return { kind: "sin_molecula" };
  return {
    kind: "auditable",
    run,
    reportable: { taskId: run.taskId, moleculeId: run.moleculeId, certified: false },
    relation: relacionDeLaCorridaActiva({ ...record, activeRun: run }),
  };
}

/** El valor que se puede enseñar: sólo lo que el backend marcó como visible. */
export function valorVisible(requisito: RequisitoPreparacion): string | null {
  const afirmativo = requisito.estado === "REGISTRADO" || requisito.estado === "PASA";
  return afirmativo || requisito.valor_es_clasificacion ? requisito.valor : null;
}
