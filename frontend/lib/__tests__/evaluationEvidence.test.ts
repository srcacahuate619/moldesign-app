import { describe, expect, it } from "vitest";
import type { Target } from "../api";
import type { EvaluationResult } from "../types";
import { deriveEvaluationEvidence, deriveEvaluationReadiness } from "../evaluationEvidence";

const readyTarget: Target = {
  pdb_id: "7E2Y",
  name: "5-HT1A",
  organism: "Homo sapiens",
  resolution: 2.8,
  chain: "R",
  requires_cns: true,
  is_hot: true,
  spearman_rho: 0.51,
  calibration_date: "2026-08-01",
  calibration_status: "listo",
  is_prepared: true,
  grid_calibrated: true,
  hotspot_count: 6,
};

const baseResult = {
  affinity_kcal: -7.4,
  docking_poses: [
    { rank: 1, affinity: -7.6, rmsd_lb: 0, rmsd_ub: 0 },
    { rank: 2, affinity: -7.2, rmsd_lb: 1.1, rmsd_ub: 1.4 },
    { rank: 3, affinity: -6.1, rmsd_lb: 2.1, rmsd_ub: 2.8 },
  ],
  vina_version: "1.2.5",
  vina_random_seed: 42,
  parsing_source: "sdf",
  scientific_warnings: [],
  in_applicability_domain: true,
  fallback_reason: null,
  engine_used: "vina",
  model_used: "pose_selector_v06",
} as unknown as EvaluationResult;

describe("evaluation evidence", () => {
  it("permite ejecutar cuando la entrada mínima está disponible", () => {
    const readiness = deriveEvaluationReadiness("CCO", readyTarget, null);
    expect(readiness.canRun).toBe(true);
    expect(readiness.status).toBe("ready");
  });

  it("no confunde separación de poses con confianza calibrada", () => {
    const evidence = deriveEvaluationEvidence(baseResult, readyTarget);
    expect(evidence.status).toBe("ready");
    expect(evidence.poseGap).toBeCloseTo(0.4);
    expect(evidence.nearTieCount).toBe(2);
    expect(evidence.physicalValidity.status).toBe("not_evaluated");
    expect(evidence.nextAction.status).toBe("review");
    expect(evidence.dimensions.find((item) => item.id === "sampling")?.statusLabel).toBe("Ambiguo");
  });

  it("exige revisión cuando el modelo está fuera de dominio", () => {
    const evidence = deriveEvaluationEvidence(
      { ...baseResult, in_applicability_domain: false } as EvaluationResult,
      readyTarget,
    );
    expect(evidence.status).toBe("review");
  });

  it("marca como incompleta una corrida sin poses", () => {
    const evidence = deriveEvaluationEvidence(
      { ...baseResult, docking_poses: [] } as unknown as EvaluationResult,
      readyTarget,
    );
    expect(evidence.status).toBe("incomplete");
    expect(evidence.nextAction.status).toBe("abstain");
  });

  it("solo permite continuar cuando la validación física supera sus controles", () => {
    // El contrato REAL es `structural_evidence`, el que persiste P0-A. Esta
    // prueba alimentaba `pose_validation`, un campo que el backend no ha
    // emitido nunca: pasaba en verde mientras la interfaz declaraba «no
    // evaluada» en cada corrida de producción.
    const evidence = deriveEvaluationEvidence(
      {
        ...baseResult,
        docking_poses: [
          { rank: 1, affinity: -7.6, rmsd_lb: 0, rmsd_ub: 0 },
          { rank: 2, affinity: -6.2, rmsd_lb: 1.1, rmsd_ub: 1.4 },
        ],
        structural_evidence: {
          version_schema: 1,
          stage_status: "passed",
          reason_code: null,
          poses_produced: 2,
          poses_evaluated: 2,
          poses: [
            { rank: 1, status: "passed", observed_vina_affinity_kcal_mol: -7.6 },
            { rank: 2, status: "passed", observed_vina_affinity_kcal_mol: -6.2 },
          ],
        },
      } as unknown as EvaluationResult,
      readyTarget,
    );
    expect(evidence.physicalValidity.status).toBe("passed");
    expect(evidence.nextAction.status).toBe("proceed");
  });

  it("una etapa `review` NO se presenta como pose superada", () => {
    const evidence = deriveEvaluationEvidence(
      {
        ...baseResult,
        structural_evidence: {
          version_schema: 1,
          stage_status: "review",
          poses_produced: 3,
          poses_evaluated: 2,
          poses: [],
        },
      } as unknown as EvaluationResult,
      readyTarget,
    );

    expect(evidence.physicalValidity.status).toBe("review");
    expect(evidence.physicalValidity.label).toBe("Requiere revisión");
    expect(evidence.nextAction.status).toBe("review");
  });

  it("sin el contrato, la corrida es anterior a la etapa y se dice así", () => {
    const evidence = deriveEvaluationEvidence(baseResult, readyTarget);

    expect(evidence.physicalValidity.status).toBe("not_evaluated");
    // Y ya no se afirma que el producto no ejecute un validador: lo ejecuta.
    expect(evidence.physicalValidity.detail).not.toContain("no ejecuta");
    expect(evidence.physicalValidity.detail).toContain("anterior a la etapa");
  });
});
