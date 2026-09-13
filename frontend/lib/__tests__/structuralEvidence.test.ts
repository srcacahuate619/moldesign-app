// =====================================================================
// La evidencia estructural que lee la pestaña Evaluación
// =====================================================================
//
// LO QUE PROTEGEN, en orden de gravedad:
//
// 1. **`review` y `not_evaluated` NUNCA son «pose válida».** Es la afirmación
//    que este producto no puede permitirse: una pose que nadie midió y una que
//    falló no son poses buenas, y llamarlas así convierte un hueco en un aval.
//
// 2. **Vina top-1 se conserva y se enseña siempre.** Aunque el selector sugiera
//    otra, aunque se abstenga, aunque falle. Si sugerida y top-1 difieren, se
//    declara; no se elige por el lector.
//
// 3. **La pose sugerida que falla NO se sustituye.** Se declara revisión y las
//    alternativas se listan sin seleccionarse.
//
// 4. **Nada se inventa.** Lo que la corrida no persistió sale `null`, y el
//    fallback se declara fallback, no acierto del selector.

import { describe, expect, it } from "vitest";

import {
  deriveStructuralEvidence,
  isPhysicallyValid,
  type EvaluationResultWithEvidence,
  type PoseSelectionContract,
  type StructuralEvidenceContract,
} from "../structuralEvidence";

// ── Constructores de escenario ───────────────────────────────────────

const POSES = [
  { rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 },
  { rank: 2, affinity: -7.9, rmsd_lb: 1.1, rmsd_ub: 1.4 },
  { rank: 3, affinity: -6.1, rmsd_lb: 2.1, rmsd_ub: 2.8 },
];

function evidencia(
  stage: string,
  estados: Record<number, string>,
  extra: Partial<StructuralEvidenceContract> = {},
): StructuralEvidenceContract {
  const ranks = Object.keys(estados).map(Number);
  return {
    version_schema: 1,
    stage_status: stage,
    reason_code: null,
    detail: null,
    pose_strategy: "vina_top1",
    primary_pose_rank: 1,
    poses_produced: 3,
    poses_evaluated: ranks.filter((r) => estados[r] !== "not_evaluated").length,
    coverage: 1,
    receptor_sha256: "a".repeat(64),
    receptor_source: "targets/7E2Y/prepared.pdbqt",
    validation_engine: "posebusters:1.0:dock",
    evaluated_at: "2026-08-24T10:00:00+00:00",
    poses: ranks.map((rank) => ({
      rank,
      observed_vina_affinity_kcal_mol: POSES.find((p) => p.rank === rank)?.affinity ?? null,
      status: estados[rank],
      label: null,
      engine: "posebusters:1.0:dock",
      checks: [
        { check: "sanitization", estado: "PASA" },
        { check: "internal_energy", estado: estados[rank] === "failed" ? "FALLA" : "PASA" },
      ],
      checks_que_fallan: estados[rank] === "failed" ? ["internal_energy"] : [],
      detail: null,
      reason_code: null,
    })),
    ...extra,
  };
}

function seleccion(extra: Partial<PoseSelectionContract> = {}): PoseSelectionContract {
  return {
    version_schema: 1,
    contract: "pose_selection/v1",
    status: "selected",
    strategy: "pose_selector_v06",
    strategy_is_fallback: false,
    vina_top1_rank: 1,
    selected_pose_rank: 2,
    confidence: 0.412233,
    abstained: false,
    abstention_reason: null,
    detail: "El selector recomienda la pose 2.",
    pose_scores: [
      { rank: 1, score: 0.11 },
      { rank: 2, score: 0.52 },
      { rank: 3, score: 0.09 },
    ],
    model: {
      name: "pose_selector_v06",
      version: "pose_selector_v06",
      model_path: "pose_selector_v06.xgb",
      model_sha256: "b".repeat(64),
      meta_sha256: "c".repeat(64),
      abstention_threshold: 0.097663,
    },
    warnings: [],
    suggested_pose_physical_status: "passed",
    physical_review: false,
    physically_valid_alternatives: [],
    evaluated_at: "2026-08-24T10:00:00+00:00",
    ...extra,
  };
}

function resultado(
  structural: StructuralEvidenceContract | null,
  pose: PoseSelectionContract | null,
  extra: Record<string, unknown> = {},
): EvaluationResultWithEvidence {
  return {
    affinity_kcal: -8.3,
    docking_poses: POSES,
    vina_version: "1.2.5",
    vina_random_seed: 42,
    parsing_source: "sdf",
    engine_used: "vina",
    scientific_warnings: [],
    structural_evidence: structural,
    pose_selection: pose,
    ...extra,
  } as unknown as EvaluationResultWithEvidence;
}

// ── 1. `passed` ──────────────────────────────────────────────────────

describe("controles físicos", () => {
  it("passed: la etapa se declara superada y la sugerida es válida", () => {
    const view = deriveStructuralEvidence(
      resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()),
    );

    expect(view.physical.stageStatus).toBe("passed");
    expect(view.physical.posesEvaluated).toBe(3);
    expect(view.physical.needsReview).toBe(false);
    expect(view.physical.suggestedPoseStatus).toBe("passed");
    expect(view.decision.nextStep).toBe("proceed_within_protocol");
    expect(view.comparison.every((row) => row.physicallyValid)).toBe(true);
  });

  it("failed: se abstiene de continuar y no se llama válida a ninguna que falle", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("failed", { 1: "failed", 2: "failed", 3: "failed" }),
        seleccion({ suggested_pose_physical_status: "failed", physical_review: true }),
      ),
    );

    expect(view.physical.stageStatus).toBe("failed");
    expect(view.decision.nextStep).toBe("abstain");
    expect(view.comparison.some((row) => row.physicallyValid)).toBe(false);
    expect(view.physical.poses[0].failingChecks).toEqual(["internal_energy"]);
  });

  it("review: NO es una pose válida y exige revisión antes de continuar", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("review", { 1: "review", 2: "review", 3: "passed" }),
        seleccion({ selected_pose_rank: 1, suggested_pose_physical_status: "review", physical_review: true }),
      ),
    );

    expect(view.physical.stageStatus).toBe("review");
    // La regla que no se negocia.
    expect(isPhysicallyValid("review")).toBe(false);
    expect(view.comparison.find((row) => row.rank === 1)?.physicallyValid).toBe(false);
    expect(view.decision.nextStep).toBe("review");
    expect(view.decision.uncertainties).toContain("suggested_pose_not_passed");
  });

  it("not_evaluated: describe al validador, no a la molécula, y tampoco es válida", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("not_evaluated", { 1: "not_evaluated", 2: "not_evaluated", 3: "not_evaluated" }, {
          reason_code: "VALIDADOR_NO_DISPONIBLE",
          poses_evaluated: 0,
        }),
        seleccion({ suggested_pose_physical_status: null, physical_review: true }),
      ),
    );

    expect(view.physical.stageStatus).toBe("not_evaluated");
    expect(view.physical.reasonCode).toBe("VALIDADOR_NO_DISPONIBLE");
    expect(isPhysicallyValid("not_evaluated")).toBe(false);
    expect(view.comparison.some((row) => row.physicallyValid)).toBe(false);
    expect(view.decision.uncertainties).toContain("no_physical_validation");
    expect(view.decision.nextStep).toBe("review");
  });

  it("cobertura parcial: se declara, no se redondea a completa", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("review", { 1: "passed", 2: "not_evaluated", 3: "not_evaluated" }),
        seleccion({ selected_pose_rank: 1 }),
      ),
    );

    expect(view.physical.posesEvaluated).toBe(1);
    expect(view.physical.posesProduced).toBe(3);
    expect(view.decision.uncertainties).toContain("partial_coverage");
  });
});

// ── 2. Selección: abstención, fallback, error, divergencia ───────────

describe("selección de pose", () => {
  it("abstención: no hay recomendación, y la referencia es fallback declarado", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({
          status: "abstained",
          abstained: true,
          strategy: "vina_top1",
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "MARGEN_BAJO_UMBRAL",
          confidence: 0.02,
          would_have_suggested_rank: 2,
        }),
      ),
    );

    expect(view.selection.status).toBe("abstained");
    expect(view.selection.suggestedRank).toBeNull();
    // Vina top-1 sobrevive a la abstención.
    expect(view.selection.vinaTop1Rank).toBe(1);
    expect(view.selection.isFallback).toBe(true);
    // Y lo medido se conserva, para poder auditar por qué se abstuvo.
    expect(view.selection.confidence).toBe(0.02);
    expect(view.selection.wouldHaveSuggestedRank).toBe(2);
    expect(view.decision.uncertainties).toContain("selector_abstained");
    // Abstenerse NO es divergir: no hay sugerida con la que comparar.
    expect(view.selection.divergesFromVinaTop1).toBe(false);
  });

  it("unavailable: el selector no corrió, y eso no es un fallo suyo", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({
          status: "unavailable",
          abstained: false,
          strategy: "vina_top1",
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "MODELO_AUSENTE",
          confidence: null,
          pose_scores: [],
          model: null,
        }),
      ),
    );

    expect(view.selection.status).toBe("unavailable");
    expect(view.selection.isFallback).toBe(true);
    expect(view.selection.vinaTop1Rank).toBe(1);
    expect(view.decision.uncertainties).toContain("selector_unavailable");
    expect(view.decision.uncertainties).not.toContain("selector_abstained");
  });

  it("error: se declara y la corrida sigue teniendo su top-1", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({
          status: "error",
          strategy: "vina_top1",
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "SELECTOR_FALLO",
        }),
      ),
    );

    expect(view.selection.status).toBe("error");
    expect(view.selection.vinaTop1Rank).toBe(1);
    expect(view.decision.uncertainties).toContain("selector_error");
    expect(view.decision.nextStep).toBe("review");
  });

  it("pose discordante: sugerida ≠ top-1 se declara, y las dos se conservan", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("review", { 1: "passed", 2: "failed", 3: "passed" }),
        seleccion({
          selected_pose_rank: 2,
          suggested_pose_physical_status: "failed",
          physical_review: true,
          physically_valid_alternatives: [
            { rank: 1, physical_status: "passed" },
            { rank: 3, physical_status: "passed" },
          ],
        }),
      ),
    );

    expect(view.selection.divergesFromVinaTop1).toBe(true);
    expect(view.selection.vinaTop1Rank).toBe(1);
    expect(view.selection.suggestedRank).toBe(2);
    expect(view.decision.uncertainties).toContain("selection_diverges");

    // La sugerida FALLA y aun así sigue siendo la sugerida: no se sustituye.
    expect(view.physical.suggestedPoseStatus).toBe("failed");
    expect(view.physical.needsReview).toBe(true);
    // Las alternativas se listan…
    expect(view.decision.alternatives).toEqual([1, 3]);
    // …y ninguna queda marcada como la elegida.
    expect(view.comparison.filter((row) => row.isSuggested).map((row) => row.rank)).toEqual([2]);
    expect(view.comparison.find((row) => row.rank === 1)?.isAlternative).toBe(true);
    expect(view.comparison.find((row) => row.rank === 1)?.isSuggested).toBe(false);
  });

  it("los papeles de una misma pose conviven: top-1 y sugerida a la vez", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }),
        seleccion({ selected_pose_rank: 1 }),
      ),
    );

    const primera = view.comparison.find((row) => row.rank === 1);
    expect(primera?.isVinaTop1).toBe(true);
    expect(primera?.isSuggested).toBe(true);
    expect(view.selection.divergesFromVinaTop1).toBe(false);
  });
});

// ── 3. Generación: lo que no se guardó, no se rellena ────────────────

describe("generación", () => {
  it("expone el protocolo persistido y declara ausentes conformeros y restarts", () => {
    const view = deriveStructuralEvidence(
      resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()),
    );

    expect(view.generation.posesProduced).toBe(3);
    expect(view.generation.topAffinity).toBe(-8.3);
    expect(view.generation.affinityGap).toBeCloseTo(0.4);
    expect(view.generation.seed).toBe(42);
    expect(view.generation.vinaVersion).toBe("1.2.5");
    expect(view.generation.provenancePresent).toBe(3);
    expect(view.generation.receptorSha256).toBe("a".repeat(64));
    // La corrida no los persiste, así que salen nulos. NUNCA un valor típico.
    expect(view.generation.conformers).toBeNull();
    expect(view.generation.restarts).toBeNull();
  });

  it("datos parciales: sin semilla ni parser, la traza se declara incompleta", () => {
    const view = deriveStructuralEvidence(
      resultado(null, seleccion(), { vina_random_seed: null, parsing_source: null }),
    );

    expect(view.generation.provenancePresent).toBe(1);
    expect(view.generation.seed).toBeNull();
    expect(view.generation.status).toBe("partial");
    expect(view.decision.uncertainties).toContain("incomplete_provenance");
    expect(view.decision.uncertainties).toContain("no_seed");
  });

  it("sin poses: no hay nada que seleccionar ni que validar", () => {
    const view = deriveStructuralEvidence(
      resultado(null, seleccion({ status: "unavailable", selected_pose_rank: null }), {
        docking_poses: [],
        affinity_kcal: null,
      }),
    );

    expect(view.generation.posesProduced).toBe(0);
    expect(view.generation.status).toBe("absent");
    expect(view.comparison).toEqual([]);
    expect(view.decision.nextStep).toBe("abstain");
  });

  it("una sola pose: se declara que no hay separación que medir", () => {
    const view = deriveStructuralEvidence(
      resultado(null, seleccion({ status: "abstained", abstained: true, selected_pose_rank: null }), {
        docking_poses: [POSES[0]],
      }),
    );

    expect(view.generation.affinityGap).toBeNull();
    expect(view.decision.uncertainties).toContain("single_pose");
    expect(view.decision.uncertainties).not.toContain("near_tie");
  });

  it("poses casi empatadas: quedarse con una sola es ambiguo", () => {
    const view = deriveStructuralEvidence(
      resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion()),
    );

    // -8.3 y -7.9 quedan dentro de 1 kcal/mol.
    expect(view.decision.uncertainties).toContain("near_tie");
  });
});

// ── 4. Resultado antiguo y datos parciales ───────────────────────────

describe("resultado antiguo", () => {
  it("sin contratos: se lee como corrida anterior, nunca como fallo", () => {
    const view = deriveStructuralEvidence(resultado(null, null));

    expect(view.isLegacyRun).toBe(true);
    expect(view.hasAnything).toBe(true);
    expect(view.physical.stageStatus).toBe("not_evaluated");
    expect(view.selection.status).toBe("unavailable");
    // La referencia sigue existiendo: Vina top-1 sale de las poses.
    expect(view.selection.vinaTop1Rank).toBe(1);
    expect(view.selection.isFallback).toBe(true);
    expect(view.decision.uncertainties).toContain("no_physical_validation");
    expect(view.decision.uncertainties).toContain("selector_unavailable");
  });

  it("con el contrato `unavailable` que sirve el backend, sigue siendo antigua", () => {
    const view = deriveStructuralEvidence(
      resultado(
        null,
        seleccion({
          status: "unavailable",
          abstained: false,
          strategy: "vina_top1",
          strategy_is_fallback: true,
          selected_pose_rank: null,
          abstention_reason: "SELECCION_AUSENTE",
          confidence: null,
          pose_scores: [],
          model: null,
          evaluated_at: null,
        }),
      ),
    );

    expect(view.isLegacyRun).toBe(true);
    expect(view.selection.abstentionReason).toBe("SELECCION_AUSENTE");
    expect(view.selection.abstained).toBe(false);
  });

  it("un resultado nulo no revienta la vista", () => {
    const view = deriveStructuralEvidence(null);

    expect(view.hasAnything).toBe(false);
    expect(view.comparison).toEqual([]);
    expect(view.generation.posesProduced).toBe(0);
  });

  it("un contrato con campos desconocidos se degrada a `not_evaluated`", () => {
    const view = deriveStructuralEvidence(
      resultado(
        evidencia("lo_que_sea", { 1: "algo_raro", 2: "passed", 3: "passed" }),
        seleccion({ status: "otra_cosa" as unknown as "selected" }),
      ),
    );

    expect(view.physical.stageStatus).toBe("not_evaluated");
    expect(view.physical.poses[0].status).toBe("not_evaluated");
    expect(view.selection.status).toBe("unavailable");
  });
});

// ── 5. Nada de notas 0-100 ───────────────────────────────────────────

describe("lo que la vista NO produce", () => {
  it("no expone ninguna puntuación agregada del producto", () => {
    const view = deriveStructuralEvidence(
      resultado(evidencia("passed", { 1: "passed", 2: "passed", 3: "passed" }), seleccion(), {
        total_score: 87.4,
        adme_score: 62,
      }),
    );

    const plano = JSON.stringify(view).toLowerCase();
    expect(plano).not.toContain("total_score");
    expect(plano).not.toContain("87.4");
    expect(plano).not.toContain("adme");
  });
});
