// =====================================================================
// Cliente de la comprobación previa
// =====================================================================
//
// Habla con `POST /evaluation/preflight`, que inspecciona la ruta REAL de
// preparación sin ejecutar docking. Aquí no se calcula ni se interpreta nada
// científico: se transporta el informe y se resume para poder guardarlo en el
// caso.
//
// DOS REGLAS QUE ESTE ARCHIVO NO PUEDE ROMPER
//
// 1. **La dirección sale de `getApiUrl()`.** Nunca un puerto fijo: en
//    escritorio lo elige Rust y puede no ser 8000.
//
// 2. **El fingerprint no se recalcula aquí.** Lo produce el backend sobre el
//    documento canónico de los inputs. Reimplementar el hash en el cliente
//    daría dos algoritmos que divergen en cuanto uno cambie, y el fingerprint
//    dejaría de poder demostrar que la corrida es la que se inspeccionó.
//
// La correspondencia entre preflight e inputs NO se resuelve comparando
// hashes: se resuelve invalidando el preflight en cuanto los inputs cambian
// (ver `inputsAffectRun` y `CaseContext.setInputs`). Un preflight presente
// corresponde a los inputs actuales por construcción.

import { getApiUrl } from "./config";
import type { CaseInputs, CasePipelineConfig, PreflightSummary } from "./cases/types";

export type PreflightControlState = "pasa" | "advertencia" | "bloquea" | "no_evaluado";

export interface PreflightControl {
  readonly code: string;
  readonly state: PreflightControlState;
  readonly title: string;
  readonly observation: string;
  readonly reason: string;
  readonly provenance: string;
}

export interface PreflightSpeciesCount {
  readonly atom_records: number;
  readonly hetatm_records: number;
  readonly waters: number;
  readonly metals: number;
  readonly organic_cofactors: number;
  readonly other_hetatm: number;
  readonly chains: readonly string[];
}

export interface PreflightDiff {
  readonly state: "evaluado" | "no_evaluado";
  readonly reason: string;
  readonly source: PreflightSpeciesCount | null;
  /** PDB filtrado que entra al preparador; todavía no es el PDBQT de Meeko. */
  readonly route_input: PreflightSpeciesCount | null;
  readonly removed: {
    readonly waters: number;
    readonly metals: number;
    readonly organic_cofactors: number;
    readonly other_hetatm: number;
  } | null;
  /** Identidad química concreta de lo retirado; `atom_count` cuenta registros PDB. */
  readonly removed_species?: readonly {
    readonly residue_code: string;
    readonly atom_count: number;
    readonly category: "water" | "metal" | "organic_cofactor" | "other_heteroatom";
  }[] | null;
  readonly preserved: {
    readonly atom_records: number;
    readonly organic_cofactors: number;
    readonly metals: number;
    readonly waters: number;
  } | null;
}

export interface PreflightReport {
  readonly schema_version: number;
  readonly generated_at: string;
  readonly execution_route: string;
  readonly input_fingerprint: string;
  readonly input_document: string;
  readonly receptor: {
    readonly reference: string | null;
    readonly pdb_id: string;
    readonly chain: string;
    readonly origin: string;
    readonly source_available: boolean;
    readonly source_sha256: string | null;
    readonly prepared_available: boolean;
    readonly prepared_sha256: string | null;
    readonly prepared_compatible: boolean | null;
    readonly prepared_chains: readonly string[];
  };
  readonly ligand: {
    readonly input_smiles: string;
    readonly canonical_smiles: string | null;
    readonly smiles_hash: string | null;
    readonly molecular_formula: string | null;
    readonly heavy_atom_count: number | null;
    readonly error: string | null;
    readonly vina_atom_compatibility: {
      readonly evaluated: boolean;
      readonly supported: boolean;
      readonly unsupported_elements: readonly string[];
    };
  };
  readonly effective_config: {
    readonly grid_center: readonly [number, number, number];
    readonly grid_size: readonly [number, number, number];
    readonly grid_center_origin: string;
    readonly grid_size_origin: string;
    readonly derived_box: { readonly center: readonly number[]; readonly size: number; readonly source: string } | null;
    readonly hotspots: readonly string[];
    readonly hotspots_origin: string;
    readonly docking_engine: string;
    readonly exhaustiveness: number;
    readonly num_poses: number;
    readonly seed: number;
    /** Conformaciones de entrada. 1 = confórmero único (protocolo por defecto). */
    readonly conformers?: number;
    readonly pipeline_config?: CasePipelineConfig | null;
    readonly heteroatom_policy: {
      readonly route: string;
      readonly waters: string;
      readonly metals: string;
      readonly organic_cofactors: string;
      readonly organic_cofactors_kept: readonly string[];
      readonly cofactors_whitelist_declared: readonly string[];
      readonly cofactors_whitelist_applied: boolean;
      readonly source: string;
    };
  };
  readonly preparation_diff: PreflightDiff;
  readonly controls: readonly PreflightControl[];
  readonly technical_blockers: readonly string[];
  readonly warnings: readonly string[];
  readonly not_evaluated: readonly string[];
}

/** Lo que se envía. Es EXACTAMENTE lo que después se manda a `/evaluation/submit`. */
export interface PreflightRequest {
  readonly smiles: string;
  readonly targetPdbId: string;
  readonly chain?: string;
  readonly gridCenter?: readonly [number, number, number];
  readonly gridSize?: readonly [number, number, number];
  readonly customHotspots?: readonly string[];
  readonly dockingEngine?: string;
  readonly exhaustiveness?: number;
  /**
   * Conformaciones de entrada por molécula.
   *
   * Se manda con el preflight —y no al ejecutar— porque forma parte de la
   * identidad de la corrida: entra en la huella y se congela con el caso. Un
   * control que lo cambiara después dejaría el resultado describiendo un
   * protocolo distinto del que se comprobó.
   */
  readonly conformers?: number;
  readonly numPoses?: number;
  readonly pipelineConfig?: CasePipelineConfig;
}

export class PreflightError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PreflightError";
  }
}

export async function requestPreflight(
  request: PreflightRequest,
  signal?: AbortSignal,
): Promise<PreflightReport> {
  const base = await getApiUrl();
  const response = await fetch(`${base}/evaluation/preflight`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    signal,
    body: JSON.stringify({
      smiles: request.smiles,
      target_pdb_id: request.targetPdbId,
      chain: request.chain ?? null,
      grid_center: request.gridCenter ?? null,
      grid_size: request.gridSize ?? null,
      custom_hotspots: request.customHotspots ?? null,
      docking_engine: request.dockingEngine ?? "vina",
      exhaustiveness: request.exhaustiveness ?? null,
      conformers: request.conformers ?? null,
      num_poses: request.numPoses ?? null,
      ...(request.pipelineConfig ? { pipeline_config: request.pipelineConfig } : {}),
    }),
  });

  if (!response.ok) {
    // El motor puede estar arrancando o caído. El mensaje lo dice tal cual: no
    // se convierte un fallo de transporte en «la molécula es inválida».
    throw new PreflightError(
      `La comprobación previa no se pudo completar (HTTP ${response.status}). ` +
        "Revisa el estado del motor y vuelve a intentarlo.",
    );
  }
  return (await response.json()) as PreflightReport;
}

// ── Resumen persistible ──────────────────────────────────────────────

function formatTriple(values: readonly number[]): string {
  return `(${values.map((v) => v.toFixed(2)).join(", ")})`;
}

/**
 * Reduce el informe a lo que el caso guarda en disco.
 *
 * NO se persiste el informe entero. Los controles, el diff y los hashes
 * pertenecen al backend, que los puede volver a calcular; copiarlos en
 * `case.json` los dejaría envejecer sin que nada los revalidara. Lo que sí
 * viaja al disco es lo que hace falta para dos cosas que deben funcionar sin
 * backend: enseñar el resumen al reabrir el caso, y decidir si el botón de
 * ejecutar puede ejecutar.
 */
export function summarizePreflight(report: PreflightReport): PreflightSummary {
  const { receptor, ligand, effective_config: config } = report;
  const gridLabel =
    config.grid_center_origin === "derivado_dinamico"
      ? `${formatTriple(config.grid_center)} · lado ${config.grid_size[0].toFixed(1)} Å · derivada del PDB`
      : `${formatTriple(config.grid_center)} · ${formatTriple(config.grid_size)} Å`;

  return {
    fingerprint: report.input_fingerprint,
    inputDocument: report.input_document,
    generatedAt: report.generated_at,
    schemaVersion: report.schema_version,
    executionRoute: report.execution_route,
    blockers: [...report.technical_blockers],
    warnings: [...report.warnings],
    notEvaluated: [...report.not_evaluated],
    receptorLabel: `${receptor.pdb_id} · cadena ${receptor.chain}`,
    ligandLabel: ligand.canonical_smiles ?? ligand.input_smiles,
    gridLabel,
    ...(receptor.source_sha256 ? { receptorSourceSha256: receptor.source_sha256 } : {}),
    ...(receptor.prepared_sha256 ? { preparedReceptorSha256: receptor.prepared_sha256 } : {}),
    executionConfig: {
      gridCenter: [...config.grid_center] as [number, number, number],
      gridSize: [...config.grid_size] as [number, number, number],
      customHotspots: [...config.hotspots],
      dockingEngine: config.docking_engine,
      exhaustiveness: config.exhaustiveness,
      numPoses: config.num_poses,
      seed: config.seed,
      // `?? 1` para corridas guardadas antes de existir el parámetro: su
      // protocolo era el confórmero único, y decirlo es exacto.
      conformers: config.conformers ?? 1,
      ...(config.pipeline_config ? { pipelineConfig: config.pipeline_config as CasePipelineConfig } : {}),
    },
  };
}

// ── Invalidación ─────────────────────────────────────────────────────

function sameTriple(
  a: readonly [number, number, number] | undefined,
  b: readonly [number, number, number] | undefined,
): boolean {
  if (!a || !b) return a === b;
  // Se comparan a 3 decimales, el mismo redondeo que aplica el backend al
  // construir el documento canónico. Sin esto, el ruido de coma flotante
  // invalidaría el preflight sin que nada hubiera cambiado de verdad.
  return a.every((value, index) => Math.round(value * 1000) === Math.round(b[index] * 1000));
}

function sameList(a: readonly string[] | undefined, b: readonly string[] | undefined): boolean {
  const left = [...(a ?? [])].sort();
  const right = [...(b ?? [])].sort();
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

/** Serializa opciones anidadas sin que el orden de las claves parezca un cambio científico. */
function stableJson(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value ?? null);
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  const record = value as Record<string, unknown>;
  return `{${Object.keys(record).sort().map((key) => `${JSON.stringify(key)}:${stableJson(record[key])}`).join(",")}}`;
}

/**
 * `true` si el cambio puede alterar la corrida y, por tanto, invalida el
 * preflight anterior.
 *
 * SE COMPARAN LOS INPUTS, NO LOS HASHES. El cliente no reproduce el algoritmo
 * del backend; compara los valores que él mismo posee. El sesgo es
 * deliberado: ante la duda se invalida. Un preflight de más cuesta una
 * petición barata; un preflight de menos deja ejecutar una corrida que nadie
 * inspeccionó.
 *
 * Consecuencia asumida: escribir la misma molécula de otra forma («OCC» tras
 * «CCO») invalida aunque el canónico sea el mismo. Se vuelve a comprobar y el
 * fingerprint resultante es idéntico. Preferimos ese trabajo extra a la
 * alternativa.
 */
export function inputsAffectRun(previous: CaseInputs | undefined, next: CaseInputs | undefined): boolean {
  const a = previous ?? {};
  const b = next ?? {};
  if ((a.receptor?.pdbId ?? null) !== (b.receptor?.pdbId ?? null)) return true;
  if ((a.receptor?.chain ?? null) !== (b.receptor?.chain ?? null)) return true;
  if ((a.ligand?.inputSmiles ?? null) !== (b.ligand?.inputSmiles ?? null)) return true;
  if (!sameTriple(a.grid?.center as [number, number, number] | undefined, b.grid?.center as [number, number, number] | undefined)) {
    return true;
  }
  if (!sameTriple(a.grid?.size as [number, number, number] | undefined, b.grid?.size as [number, number, number] | undefined)) {
    return true;
  }
  if (!sameList(a.customHotspots, b.customHotspots)) return true;
  if ((a.dockingEngine ?? "vina") !== (b.dockingEngine ?? "vina")) return true;
  if ((a.exhaustiveness ?? null) !== (b.exhaustiveness ?? null)) return true;
  // Cambiar K cambia lo que se ejecuta: el informe deja de describir la corrida.
  if ((a.conformers ?? null) !== (b.conformers ?? null)) return true;
  if ((a.numPoses ?? null) !== (b.numPoses ?? null)) return true;
  if (stableJson(a.pipelineConfig ?? null) !== stableJson(b.pipelineConfig ?? null)) return true;
  return false;
}

/** `true` si los inputs bastan para pedir una comprobación previa. */
export function inputsAreComplete(inputs: CaseInputs | undefined): boolean {
  return Boolean(inputs?.receptor?.pdbId && inputs?.ligand?.inputSmiles?.trim());
}

/**
 * Por qué NO se puede ejecutar todavía, o `null` si se puede.
 *
 * Un botón deshabilitado sin explicación es un callejón sin salida. Cada rama
 * devuelve la frase que el usuario necesita para desbloquearse.
 */
export function describeRunBlock(
  inputs: CaseInputs | undefined,
  preflight: PreflightSummary | undefined,
): string | null {
  if (!inputs?.receptor?.pdbId) return "Elige un receptor antes de ejecutar.";
  if (!inputs?.ligand?.inputSmiles?.trim()) return "Introduce o dibuja un ligando antes de ejecutar.";
  if (!preflight) {
    return (
      "Ejecuta «Comprobar preparación» antes de lanzar la corrida: sin eso no se puede " +
      "afirmar que lo que se ejecuta es lo que se muestra."
    );
  }
  if (preflight.blockers.length > 0) {
    return (
      `La comprobación previa encontró ${preflight.blockers.length} ` +
      `${preflight.blockers.length === 1 ? "bloqueante técnico" : "bloqueantes técnicos"}: ` +
      `${preflight.blockers.join(", ")}. La corrida fallaría igual, más tarde.`
    );
  }
  if (!preflight.executionConfig) {
    return (
      "Esta comprobación pertenece a una versión anterior y no conserva la configuración " +
      "efectiva de ejecución. Vuelve a comprobar antes de ejecutar."
    );
  }
  return null;
}
