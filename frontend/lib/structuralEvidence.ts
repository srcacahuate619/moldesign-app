// =====================================================================
// structuralEvidence — leer los contratos de P0-A y P0-B, sin adornarlos
// =====================================================================
//
// QUÉ HACE Y QUÉ NO. Este módulo traduce dos contratos del backend
// —`structural_evidence` (validación física por pose) y `pose_selection`
// (recomendación del selector)— a una vista que la pestaña Evaluación puede
// pintar. No calcula nada científico, no reordena poses, no convierte nada en
// una nota, y no rellena huecos: lo que la corrida no persistió se declara
// ausente con su motivo.
//
// POR QUÉ DEVUELVE CÓDIGOS Y NO FRASES. La versión anterior de este hueco
// (`evaluationEvidence.ts`) cocinaba las frases en español dentro de la
// derivación, y por eso la mitad de la pestaña no puede traducirse sin
// reescribirla. Aquí sale el ESTADO y salen los NÚMEROS; el texto lo resuelve
// el componente contra el diccionario, así que español e inglés no pueden
// desincronizarse.
//
// LAS DOS REGLAS QUE NO SE NEGOCIAN:
//
//   1. `review` y `not_evaluated` NUNCA son «pose válida». Una pose que nadie
//      midió y una pose que falló son cosas distintas, y ninguna de las dos es
//      una pose buena. `physicallyValid` sólo es `true` con `passed` explícito.
//
//   2. Vina top-1 se conserva y se enseña SIEMPRE, aunque el selector sugiera
//      otra. Si difieren, se dice; no se elige por el lector.

import type { EvaluationResult } from "./types";

// ── Contratos del backend, tal y como llegan ─────────────────────────

/** `services/chemistry/pose_physical_validity.py`: veredicto de UNA pose. */
export type PhysicalStatus = "passed" | "failed" | "review" | "not_evaluated";

/** `services/chemistry/pose_selection.py`: estado de la etapa de selección. */
export type SelectionStatus = "selected" | "abstained" | "unavailable" | "error";

export type CheckState = "PASA" | "FALLA" | "NO_EVALUADO";

export interface PoseCheck {
  check: string;
  estado: CheckState | string;
}

export interface StructuralPoseEntry {
  rank: number | null;
  observed_vina_affinity_kcal_mol: number | null;
  status: PhysicalStatus | string;
  label?: string | null;
  engine?: string | null;
  checks?: PoseCheck[] | null;
  checks_que_fallan?: string[] | null;
  detail?: string | null;
  reason_code?: string | null;
}

/** Contrato `structural_evidence` (P0-A). `null` en corridas anteriores. */
export interface StructuralEvidenceContract {
  version_schema?: number;
  stage_status?: PhysicalStatus | string;
  reason_code?: string | null;
  detail?: string | null;
  pose_strategy?: string | null;
  primary_pose_rank?: number | null;
  poses_produced?: number | null;
  poses_evaluated?: number | null;
  coverage?: number | null;
  receptor_sha256?: string | null;
  receptor_source?: string | null;
  validation_engine?: string | string[] | null;
  evaluated_at?: string | null;
  poses?: StructuralPoseEntry[] | null;
}

/** Contrato `pose_selection` (P0-B). El backend nunca lo manda `null`. */
export interface PoseSelectionContract {
  version_schema?: number;
  contract?: string;
  status?: SelectionStatus | string;
  strategy?: string | null;
  strategy_is_fallback?: boolean | null;
  vina_top1_rank?: number | null;
  selected_pose_rank?: number | null;
  confidence?: number | null;
  abstained?: boolean | null;
  abstention_reason?: string | null;
  detail?: string | null;
  pose_scores?: { rank: number | null; score: number | null }[] | null;
  model?: {
    name?: string | null;
    version?: string | null;
    model_path?: string | null;
    model_sha256?: string | null;
    meta_sha256?: string | null;
    abstention_threshold?: number | null;
  } | null;
  inputs?: Record<string, unknown> | null;
  warnings?: string[] | null;
  suggested_pose_physical_status?: PhysicalStatus | string | null;
  physical_review?: boolean | null;
  physically_valid_alternatives?: { rank: number | null; physical_status?: string | null }[] | null;
  evaluated_at?: string | null;
  would_have_suggested_rank?: number | null;
}

/**
 * El resultado que esta vista lee.
 *
 * `EvaluationResult` ya declara los dos contratos (ver `types.ts`); el alias se
 * conserva porque nombra la precondición de esta función: ambos campos pueden
 * faltar, y faltar no es un error.
 */
export type EvaluationResultWithEvidence = EvaluationResult;

// ── Vista derivada ───────────────────────────────────────────────────

/** Estado de una sección. `partial`: hay algo, pero no todo. */
export type SectionStatus = "ok" | "partial" | "review" | "failed" | "absent";

export interface GenerationView {
  status: SectionStatus;
  posesProduced: number;
  topAffinity: number | null;
  /** Δ entre la pose 1 y la 2, en kcal/mol. `null` con menos de dos poses. */
  affinityGap: number | null;
  engine: string | null;
  vinaVersion: string | null;
  /** `null` = la corrida no la persistió. NO se sustituye por un valor típico. */
  seed: number | null;
  parsingSource: string | null;
  receptorSha256: string | null;
  receptorSource: string | null;
  /**
   * Conformeros y restarts. La corrida NO los persiste en el resultado, así
   * que siempre viajan como `null` y la interfaz lo declara. Rellenarlos con
   * la configuración del caso sería atribuir a esta corrida un parámetro que
   * nadie guardó con ella.
   */
  conformers: number | null;
  restarts: number | null;
  /** Qué trazas de reproducibilidad existen, sin convertirlo en una nota. */
  provenancePresent: number;
  provenanceTotal: 3;
}

export interface SelectionView {
  status: SelectionStatus;
  /** La referencia del producto. Se conserva pase lo que pase. */
  vinaTop1Rank: number | null;
  /** `null` si el selector no recomendó (abstención, ausencia o fallo). */
  suggestedRank: number | null;
  /** Lo que HABRÍA sugerido, cuando se abstuvo. Se enseña como tal. */
  wouldHaveSuggestedRank: number | null;
  /** Margen top1 − top2 del selector. No es una probabilidad ni una nota. */
  confidence: number | null;
  abstentionThreshold: number | null;
  abstained: boolean;
  abstentionReason: string | null;
  /** `true` cuando la referencia es Vina top-1 por defecto, no por elección. */
  isFallback: boolean;
  /** El caso que no se puede esconder: sugerida ≠ top-1. */
  divergesFromVinaTop1: boolean;
  modelName: string | null;
  modelVersion: string | null;
  modelSha256: string | null;
  detail: string | null;
  warnings: string[];
  poseScores: { rank: number; score: number }[];
}

export interface PhysicalPoseView {
  rank: number | null;
  status: PhysicalStatus;
  affinity: number | null;
  engine: string | null;
  failingChecks: string[];
  passedCount: number;
  failedCount: number;
  notEvaluatedCount: number;
  detail: string | null;
  reasonCode: string | null;
}

export interface PhysicalView {
  status: SectionStatus;
  stageStatus: PhysicalStatus;
  posesProduced: number;
  posesEvaluated: number;
  engine: string | null;
  reasonCode: string | null;
  detail: string | null;
  receptorSha256: string | null;
  poses: PhysicalPoseView[];
  /** Estado físico de la pose que el selector sugirió, leído de P0-B. */
  suggestedPoseStatus: PhysicalStatus | null;
  /** `true` = la sugerida NO está confirmada como válida. NO se sustituye. */
  needsReview: boolean;
}

export interface PoseComparisonRow {
  rank: number;
  affinity: number | null;
  selectorScore: number | null;
  physicalStatus: PhysicalStatus;
  isVinaTop1: boolean;
  isSuggested: boolean;
  isAlternative: boolean;
  /** Sólo `passed` explícito. `review` y `not_evaluated` NUNCA son válidas. */
  physicallyValid: boolean;
}

/** Códigos de incertidumbre. El texto lo pone el diccionario. */
export type UncertaintyCode =
  | "no_physical_validation"
  | "partial_coverage"
  | "suggested_pose_not_passed"
  | "selector_abstained"
  | "selector_unavailable"
  | "selector_error"
  | "selection_diverges"
  | "single_pose"
  | "near_tie"
  | "incomplete_provenance"
  | "no_seed";

export type NextStep = "abstain" | "review" | "proceed_within_protocol";

export interface DecisionView {
  /** Qué evidencia existe DE VERDAD, en códigos. */
  established: ("poses_generated" | "physical_checks_run" | "selector_ran" | "provenance_sealed")[];
  uncertainties: UncertaintyCode[];
  /** Alternativas físicamente válidas. Se listan; nadie las selecciona. */
  alternatives: number[];
  nextStep: NextStep;
}

export interface StructuralEvidenceView {
  /** `false` sólo cuando no hay ni poses ni contratos que enseñar. */
  hasAnything: boolean;
  /** Corrida anterior a las etapas: ni validación ni selección existían. */
  isLegacyRun: boolean;
  generation: GenerationView;
  selection: SelectionView;
  physical: PhysicalView;
  decision: DecisionView;
  comparison: PoseComparisonRow[];
}

// ── Utilidades ───────────────────────────────────────────────────────

const PHYSICAL_STATUSES: PhysicalStatus[] = ["passed", "failed", "review", "not_evaluated"];
const SELECTION_STATUSES: SelectionStatus[] = ["selected", "abstained", "unavailable", "error"];

function asPhysicalStatus(value: unknown): PhysicalStatus {
  return PHYSICAL_STATUSES.includes(value as PhysicalStatus)
    ? (value as PhysicalStatus)
    : "not_evaluated";
}

function asSelectionStatus(value: unknown): SelectionStatus {
  return SELECTION_STATUSES.includes(value as SelectionStatus)
    ? (value as SelectionStatus)
    : "unavailable";
}

function finiteOrNull(value: unknown): number | null {
  const n = Number(value);
  return value != null && Number.isFinite(n) ? n : null;
}

/**
 * Una pose es «físicamente válida» SÓLO con `passed`.
 *
 * Es la regla que impide que la interfaz llame válido a lo que nadie midió.
 * `review` significa que la batería no corrió entera; `not_evaluated`, que no
 * corrió en absoluto. Ninguna de las dos autoriza la palabra.
 */
export function isPhysicallyValid(status: PhysicalStatus | string | null | undefined): boolean {
  return status === "passed";
}

/** Motor de validación: el contrato admite uno o varios. */
function engineLabel(engine: string | string[] | null | undefined): string | null {
  if (Array.isArray(engine)) return engine.length > 0 ? engine.join(" · ") : null;
  return engine ?? null;
}

// ── Derivación ───────────────────────────────────────────────────────

export function deriveStructuralEvidence(
  result: EvaluationResultWithEvidence | null | undefined,
): StructuralEvidenceView {
  const evidence = result?.structural_evidence ?? null;
  const selectionContract = result?.pose_selection ?? null;

  const poses = (result?.docking_poses ?? [])
    .filter((pose) => Number.isFinite(pose.affinity))
    .slice()
    .sort((a, b) => a.affinity - b.affinity);

  // ── 1. Generación ──────────────────────────────────────────────────
  const posesProduced = finiteOrNull(evidence?.poses_produced) ?? poses.length;
  const topAffinity = poses[0]?.affinity ?? finiteOrNull(result?.affinity_kcal);
  const affinityGap =
    poses.length > 1 ? Number((poses[1].affinity - poses[0].affinity).toFixed(3)) : null;

  const vinaVersion = result?.vina_version ?? null;
  const seed = finiteOrNull(result?.vina_random_seed);
  const parsingSource = result?.parsing_source ?? null;
  const provenancePresent = [vinaVersion, seed, parsingSource].filter(
    (value) => value != null && value !== "",
  ).length;

  const generation: GenerationView = {
    status: posesProduced === 0 ? "absent" : topAffinity == null ? "partial" : provenancePresent === 3 ? "ok" : "partial",
    posesProduced,
    topAffinity,
    affinityGap,
    engine: result?.engine_used ?? null,
    vinaVersion,
    seed,
    parsingSource,
    receptorSha256: evidence?.receptor_sha256 ?? null,
    receptorSource: evidence?.receptor_source ?? null,
    // La corrida no los persiste. Se declaran ausentes, no se inventan.
    conformers: null,
    restarts: null,
    provenancePresent,
    provenanceTotal: 3,
  };

  // ── 2. Selección ───────────────────────────────────────────────────
  const selStatus = asSelectionStatus(selectionContract?.status);
  const vinaTop1Rank =
    finiteOrNull(selectionContract?.vina_top1_rank) ??
    finiteOrNull(evidence?.primary_pose_rank) ??
    (poses[0]?.rank ?? null);
  const suggestedRank = finiteOrNull(selectionContract?.selected_pose_rank);
  const wouldHaveSuggestedRank = finiteOrNull(selectionContract?.would_have_suggested_rank);

  const poseScores = (selectionContract?.pose_scores ?? [])
    .map((entry) => ({ rank: finiteOrNull(entry?.rank), score: finiteOrNull(entry?.score) }))
    .filter((entry): entry is { rank: number; score: number } => entry.rank != null && entry.score != null);

  const selection: SelectionView = {
    status: selStatus,
    vinaTop1Rank,
    suggestedRank,
    wouldHaveSuggestedRank,
    confidence: finiteOrNull(selectionContract?.confidence),
    abstentionThreshold: finiteOrNull(selectionContract?.model?.abstention_threshold),
    abstained: selectionContract?.abstained === true,
    abstentionReason: selectionContract?.abstention_reason ?? null,
    // Si el backend no lo declara, se asume fallback salvo que haya
    // recomendación: presentar una ausencia como elección sería el error.
    isFallback: selectionContract?.strategy_is_fallback ?? selStatus !== "selected",
    divergesFromVinaTop1:
      suggestedRank != null && vinaTop1Rank != null && suggestedRank !== vinaTop1Rank,
    modelName: selectionContract?.model?.name ?? null,
    modelVersion: selectionContract?.model?.version ?? null,
    modelSha256: selectionContract?.model?.model_sha256 ?? null,
    detail: selectionContract?.detail ?? null,
    warnings: (selectionContract?.warnings ?? []).filter(Boolean),
    poseScores,
  };

  // ── 3. Controles físicos ───────────────────────────────────────────
  const posesEvaluated = finiteOrNull(evidence?.poses_evaluated) ?? 0;
  const stageStatus = asPhysicalStatus(evidence?.stage_status);

  const physicalPoses: PhysicalPoseView[] = (evidence?.poses ?? []).map((entry) => {
    const checks = entry?.checks ?? [];
    return {
      rank: finiteOrNull(entry?.rank),
      status: asPhysicalStatus(entry?.status),
      affinity: finiteOrNull(entry?.observed_vina_affinity_kcal_mol),
      engine: entry?.engine ?? null,
      failingChecks: (entry?.checks_que_fallan ?? []).filter(Boolean),
      passedCount: checks.filter((c) => c?.estado === "PASA").length,
      failedCount: checks.filter((c) => c?.estado === "FALLA").length,
      notEvaluatedCount: checks.filter((c) => c?.estado === "NO_EVALUADO").length,
      detail: entry?.detail ?? null,
      reasonCode: entry?.reason_code ?? null,
    };
  });

  const suggestedPoseStatus = selectionContract?.suggested_pose_physical_status
    ? asPhysicalStatus(selectionContract.suggested_pose_physical_status)
    : suggestedRank != null
      ? (physicalPoses.find((p) => p.rank === suggestedRank)?.status ?? null)
      : null;

  const physical: PhysicalView = {
    status: !evidence
      ? "absent"
      : stageStatus === "passed"
        ? "ok"
        : stageStatus === "failed"
          ? "failed"
          : stageStatus === "review"
            ? "review"
            : "absent",
    stageStatus: evidence ? stageStatus : "not_evaluated",
    posesProduced: finiteOrNull(evidence?.poses_produced) ?? posesProduced,
    posesEvaluated,
    engine: engineLabel(evidence?.validation_engine),
    reasonCode: evidence?.reason_code ?? null,
    detail: evidence?.detail ?? null,
    receptorSha256: evidence?.receptor_sha256 ?? null,
    poses: physicalPoses,
    suggestedPoseStatus,
    // El backend ya lo decidió en P0-B; aquí sólo se respeta. Si no lo dijo,
    // una sugerida sin `passed` explícito exige revisión igualmente.
    needsReview:
      selectionContract?.physical_review === true ||
      (suggestedRank != null && !isPhysicallyValid(suggestedPoseStatus)),
  };

  // ── 4. Decisión justificable ───────────────────────────────────────
  const alternatives = (selectionContract?.physically_valid_alternatives ?? [])
    .map((entry) => finiteOrNull(entry?.rank))
    .filter((rank): rank is number => rank != null);

  const nearTieCount =
    topAffinity == null ? 0 : poses.filter((pose) => pose.affinity - topAffinity <= 1).length;

  const established: DecisionView["established"] = [];
  if (posesProduced > 0) established.push("poses_generated");
  if (posesEvaluated > 0) established.push("physical_checks_run");
  if (selStatus === "selected" || selStatus === "abstained") established.push("selector_ran");
  if (generation.receptorSha256) established.push("provenance_sealed");

  const uncertainties: UncertaintyCode[] = [];
  if (!evidence || posesEvaluated === 0) uncertainties.push("no_physical_validation");
  else if (posesEvaluated < physical.posesProduced) uncertainties.push("partial_coverage");
  if (suggestedRank != null && !isPhysicallyValid(suggestedPoseStatus)) {
    uncertainties.push("suggested_pose_not_passed");
  }
  if (selStatus === "abstained") uncertainties.push("selector_abstained");
  if (selStatus === "unavailable") uncertainties.push("selector_unavailable");
  if (selStatus === "error") uncertainties.push("selector_error");
  if (selection.divergesFromVinaTop1) uncertainties.push("selection_diverges");
  if (posesProduced === 1) uncertainties.push("single_pose");
  else if (nearTieCount > 1) uncertainties.push("near_tie");
  if (provenancePresent < 3) uncertainties.push("incomplete_provenance");
  if (seed == null) uncertainties.push("no_seed");

  // El siguiente paso NO afirma actividad ni éxito: sólo dice qué es
  // justificable hacer con lo que hay.
  const nextStep: NextStep =
    posesProduced === 0 || stageStatus === "failed"
      ? "abstain"
      : stageStatus !== "passed" || physical.needsReview || selStatus === "error"
        ? "review"
        : "proceed_within_protocol";

  const decision: DecisionView = { established, uncertainties, alternatives, nextStep };

  // ── Comparación: top-1, sugerida y alternativas, en una sola tabla ──
  const scoreByRank = new Map(poseScores.map((entry) => [entry.rank, entry.score]));
  const physicalByRank = new Map(
    physicalPoses.filter((p) => p.rank != null).map((p) => [p.rank as number, p.status]),
  );

  const comparison: PoseComparisonRow[] = poses.map((pose) => {
    const status = physicalByRank.get(pose.rank) ?? "not_evaluated";
    return {
      rank: pose.rank,
      affinity: pose.affinity,
      selectorScore: scoreByRank.get(pose.rank) ?? null,
      physicalStatus: status,
      isVinaTop1: vinaTop1Rank != null && pose.rank === vinaTop1Rank,
      isSuggested: suggestedRank != null && pose.rank === suggestedRank,
      isAlternative: alternatives.includes(pose.rank),
      physicallyValid: isPhysicallyValid(status),
    };
  });

  const isLegacyRun = !evidence && (selStatus === "unavailable" || selectionContract == null);

  return {
    hasAnything: posesProduced > 0 || evidence != null || selectionContract != null,
    isLegacyRun,
    generation,
    selection,
    physical,
    decision,
    comparison,
  };
}
