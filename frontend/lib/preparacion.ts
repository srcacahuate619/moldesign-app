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
}

export interface BloquePreparacion {
  readonly id: BloquePreparacionId;
  readonly estado: EstadoBloque;
  readonly requisitos: readonly RequisitoPreparacion[];
}

export interface AuditoriaPreparacion {
  readonly schema: typeof PREPARACION_SCHEMA;
  readonly alcance: string;
  readonly transferencia_fep_demostrada: boolean;
  readonly estado: EstadoPreparacion;
  readonly razon: string;
  readonly bloqueantes: readonly string[];
  readonly en_revision: readonly string[];
  readonly bloques: readonly BloquePreparacion[];
  readonly corrida: {
    readonly case_id: string;
    readonly molecule_id: string;
    readonly task_id: string | null;
    readonly target: string;
  };
  readonly generated_at: string;
  readonly paquete: { readonly rotulo: string; readonly aviso: string };
}

const ESTADOS_GLOBALES: readonly string[] = ["BLOQUEADO", "REVISION", "TRANSFERIBLE"];
const ESTADOS_BLOQUE: readonly string[] = ["BLOQUEADO", "REVISION", "REGISTRADO"];

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
          typeof r?.clave === "string" && typeof r?.estado === "string",
      ),
  );
}

/** Qué se puede auditar de un caso. */
export type CorridaAuditable =
  | {
      readonly kind: "auditable";
      readonly reportable: ReportableResult;
      readonly relation: RunInputsRelation;
    }
  | { readonly kind: "sin_corrida" }
  | { readonly kind: "sin_terminar" }
  | { readonly kind: "sin_molecula" };

/**
 * La corrida que se audita es la ACTIVA del caso, terminada y con su
 * `moleculeId` guardado. Nunca «el último resultado de la molécula»: el backend
 * contrasta el `task_id` y devuelve 409 si el resultado es de otra corrida.
 */
export function corridaDelCaso(record: CaseRecord): CorridaAuditable {
  const run = record.activeRun;
  if (!run) return { kind: "sin_corrida" };
  if (run.executionState !== "completed") return { kind: "sin_terminar" };
  if (!run.moleculeId) return { kind: "sin_molecula" };
  return {
    kind: "auditable",
    reportable: { taskId: run.taskId, moleculeId: run.moleculeId, certified: false },
    relation: relacionDeLaCorridaActiva(record),
  };
}

/** El valor que se puede enseñar: sólo lo que el backend marcó como visible. */
export function valorVisible(requisito: RequisitoPreparacion): string | null {
  const afirmativo = requisito.estado === "REGISTRADO" || requisito.estado === "PASA";
  return afirmativo || requisito.valor_es_clasificacion ? requisito.valor : null;
}
