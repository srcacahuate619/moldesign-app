import { describe, expect, it } from "vitest";
import type { Target } from "../api";
import type { EvaluationResult } from "../types";
import { deriveEvaluationEvidence, deriveEvaluationReadiness } from "../evaluationEvidence";
import { pro } from "../../context/traducciones/pro";

const translateEnglish = (key: string, values: Record<string, string | number> = {}) => {
  let text = pro.en[key] ?? key;
  for (const [name, value] of Object.entries(values)) {
    text = text.replaceAll(`{${name}}`, String(value));
  }
  return text;
};

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

// Lo que una corrida reciente registra de sí misma (`vina_service.py`). Sin
// esto la fila de reproducibilidad ya no dice «Registrada» (SOL-06).
const procedenciaCompleta = {
  box_center: [1, 2, 3],
  box_size: [20, 20, 20],
  receptor_sha256: "a".repeat(64),
  ligand_input_sha256: "b".repeat(64),
  ligand_pdbqt_sha256: "c".repeat(64),
  poses_sha256: "d".repeat(64),
  log_sha256: "e".repeat(64),
  app_version: "1.0.2",
};

const baseResult = {
  docking_protocol: {
    engine: "vina",
    exhaustiveness: 8,
    num_poses: 9,
    seed: 42,
    execution_provenance: procedenciaCompleta,
  },
  ligand_state: { smiles_acoplado: "CCO", protonacion: { aplicada: false } },
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

  it("localiza en inglés la matriz, sus reservas y la acción siguiente", () => {
    const evidence = deriveEvaluationEvidence(
      {
        ...baseResult,
        model_used: "universal",
        fallback_reason: "Family 'protease' has no validated model — the universal model was used.",
        structural_evidence: {
          version_schema: 1,
          stage_status: "passed",
          reason_code: null,
          poses_produced: 3,
          poses_evaluated: 3,
          poses: [],
        },
      } as unknown as EvaluationResult,
      readyTarget,
      translateEnglish,
    );

    expect(evidence.label).toBe("Review needed");
    expect(evidence.summary).toContain("produced useful evidence");
    expect(evidence.dimensions.find((item) => item.id === "sampling")?.detail).toContain(
      "2 poses are within 1 kcal/mol",
    );
    expect(evidence.dimensions.find((item) => item.id === "model")?.detail).toContain(
      "universal model; fallback reason: Family 'protease'",
    );
    expect(evidence.dimensions.find((item) => item.id === "model")?.detail).toBe(
      "universal model; fallback reason: Family 'protease' has no validated model — the universal model was used. The docking engine and its version are listed in the reproducibility trace.",
    );
    expect(evidence.assumptions[0]).toContain("not experimental free-energy measurements");
    expect(evidence.uncertainties[0]).toContain("2 poses are within 1 kcal/mol");
    expect(evidence.nextAction.label).toBe("Resolve reservations before comparison");
  });

  it("preserves the Spanish model fallback detail exactly", () => {
    const evidence = deriveEvaluationEvidence(
      {
        ...baseResult,
        model_used: "universal",
        fallback_reason: "Familia 'protease' sin modelo validado — modelo universal usado.",
      } as unknown as EvaluationResult,
      readyTarget,
    );

    expect(evidence.dimensions.find((item) => item.id === "model")?.detail).toBe(
      "modelo universal; fallback: Familia 'protease' sin modelo validado — modelo universal usado.. El motor de acoplamiento y su versión se declaran en la traza de reproducibilidad.",
    );
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

  // ── SOL-05: cabecera, reservas y acción siguiente cuentan lo mismo ──
  //
  // La auditoría lo midió con datos sintéticos: con todo lo demás en orden,
  // cambiar `stage_status` a `failed` o `review` mantenía el estado global
  // en `ready` («Evidencia disponible») y dejaba la lista de incertidumbres
  // VACÍA — la pantalla se contradecía con su propia acción siguiente, que
  // sí se abstener/pedir revisión. El criterio de cierre: fallo/revisión
  // físicos se reflejan consistentemente en el estado resumido y las
  // reservas, conservando la evidencia producida.
  //
  // `not_evaluated` NO entra: una corrida anterior a la etapa de validación
  // muestra su reserva en la lista desde siempre, y «Evidencia disponible»
  // con la reserva a la vista y una acción conservadora no se contradice.
  // (Ver el test de arriba: ese contrato es deliberado.)

  describe("SOL-05: el estado global refleja los controles físicos", () => {
    const CON_CONTROLES = (stage_status: string) =>
      ({
        ...baseResult,
        structural_evidence: {
          version_schema: 1,
          stage_status,
          reason_code: null,
          poses_produced: 3,
          poses_evaluated: 3,
          poses: [],
        },
      }) as unknown as EvaluationResult;

    it.each(["failed", "review"])(
      "con %s la cabecera NO dice ready y la reserva se ve en la lista",
      (stage) => {
        const evidence = deriveEvaluationEvidence(CON_CONTROLES(stage), readyTarget);

        // La cabecera deja de decir «Evidencia disponible»: la evidencia se
        // produjo (no es incomplete), pero contiene una reserva que se ve.
        expect(evidence.status).toBe("review");
        expect(evidence.label).toBe("Revisión necesaria");
        // La reserva física aparece en la lista — antes quedaba VACÍA.
        expect(evidence.uncertainties).toContain(evidence.physicalValidity.detail);
        // Y la acción siguiente sigue siendo la conservadora de siempre.
        expect(evidence.nextAction.status).toBe(
          stage === "failed" ? "abstain" : "review",
        );
      },
    );

    it("con passed sigue pudiendo ser ready, sin reserva física en la lista", () => {
      const evidence = deriveEvaluationEvidence(CON_CONTROLES("passed"), readyTarget);

      expect(evidence.status).toBe("ready");
      expect(evidence.nextAction.status).toBe("proceed");
      expect(evidence.uncertainties).not.toContain(evidence.physicalValidity.detail);
    });
  });

  // SOL-06. «Completa» salía de tres metadatos. Tres escalones que no se
  // confunden: trazas mínimas, elementos de reconstrucción registrados y
  // reconstrucción demostrada (que esta fila no puede afirmar nunca).
  describe("reproducibilidad por escalones (SOL-06)", () => {
    const fila = (resultado: EvaluationResult) =>
      deriveEvaluationEvidence(resultado, readyTarget).dimensions.find((d) => d.id === "reproducibility")!;
    const SOLO_TRES_TRAZAS = {
      ...baseResult,
      docking_protocol: null,
      ligand_state: null,
    } as unknown as EvaluationResult;

    it("tres trazas sin caja, hashes ni preparación NO se rotulan completas", () => {
      const reproducibilidad = fila(SOLO_TRES_TRAZAS);
      expect(reproducibilidad.statusLabel).toBe("Parcial");
      expect(reproducibilidad.status).toBe("review");
      expect(reproducibilidad.detail).toContain("Trazas mínimas 3/3");
      expect(reproducibilidad.detail).toContain("elementos de reconstrucción 0/7");
      expect(reproducibilidad.detail).toContain("caja de búsqueda efectiva");
      expect(reproducibilidad.detail).toContain("hash del receptor");
    });

    it("el resumen ya no promete reproducción técnica si faltan elementos", () => {
      const evidencia = deriveEvaluationEvidence(SOLO_TRES_TRAZAS, readyTarget);
      expect(evidencia.status).toBe("review");
      expect(evidencia.summary).not.toMatch(/suficientes para/);
      expect(evidencia.uncertainties.some((u) => u.startsWith("Faltan elementos para reconstruir"))).toBe(true);
      expect(evidencia.reproducibility.reconstruction.missing).toContain("caja de búsqueda efectiva");
    });

    it("con todo registrado dice «Registrada» y aun así declara la reconstrucción no demostrada", () => {
      const reproducibilidad = fila(baseResult);
      expect(reproducibilidad.statusLabel).toBe("Registrada");
      expect(reproducibilidad.status).toBe("available");
      expect(reproducibilidad.detail).toContain("no demostrada");
      expect(reproducibilidad.statusLabel).not.toMatch(/complet/i);
      const evidencia = deriveEvaluationEvidence(baseResult, readyTarget);
      expect(evidencia.status).toBe("ready");
      expect(evidencia.summary).toContain("no está demostrada");
      expect(evidencia.reproducibility.reconstruction.demonstrated).toBe(false);
    });

    it.each([
      ["caja de búsqueda efectiva", { box_size: undefined }],
      ["hash del receptor", { receptor_sha256: undefined }],
      ["hashes de entrada del ligando", { ligand_pdbqt_sha256: undefined }],
      ["hashes de salida (poses y registro)", { log_sha256: "" }],
      ["versión de la aplicación", { app_version: null }],
    ])("sin %s la fila es Parcial y lo nombra", (faltante, cambio) => {
      const resultado = {
        ...baseResult,
        docking_protocol: {
          ...(baseResult.docking_protocol as object),
          execution_provenance: { ...procedenciaCompleta, ...cambio },
        },
      } as unknown as EvaluationResult;
      const reproducibilidad = fila(resultado);
      expect(reproducibilidad.statusLabel).toBe("Parcial");
      expect(reproducibilidad.detail).toContain(`faltan: ${faltante}`);
    });

    it("sin protocolo de búsqueda o sin preparación del ligando también es Parcial", () => {
      const sinProtocolo = {
        ...baseResult,
        docking_protocol: { engine: "vina", execution_provenance: procedenciaCompleta },
      } as unknown as EvaluationResult;
      expect(fila(sinProtocolo).detail).toContain("faltan: protocolo de búsqueda");
      const sinPreparacion = { ...baseResult, ligand_state: { smiles_acoplado: "CCO" } } as unknown as EvaluationResult;
      expect(fila(sinPreparacion).detail).toContain("faltan: preparación del ligando");
    });

    it("sin ninguna traza ni elemento es Insuficiente", () => {
      const vacio = {
        ...SOLO_TRES_TRAZAS,
        vina_version: null,
        vina_random_seed: null,
        parsing_source: null,
      } as unknown as EvaluationResult;
      expect(fila(vacio).statusLabel).toBe("Insuficiente");
      expect(fila(vacio).status).toBe("missing");
    });
  });
});
