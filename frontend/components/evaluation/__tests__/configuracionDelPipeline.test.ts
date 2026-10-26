import { describe, expect, it } from "vitest";

import { configuracionDelPipeline } from "../CaseEvaluationRunner";
import type { CaseInputs, CasePipelineConfig } from "../../../lib/cases/types";

// QA-036: cambiar a ensemble en un caso que nunca pasó por Opciones guardaba un
// pipelineConfig con sólo `stage_params.conformer`. El preflight lo firmaba con
// 9 poses y la ejecución lo enviaba sin `stage_params.docking`: el backend ponía
// 5 y respondía 409 siempre.
describe("configuracionDelPipeline", () => {
  it("sin configuración guardada devuelve la completa por defecto", () => {
    const config = configuracionDelPipeline({ conformers: 1 } as CaseInputs);
    expect(config.stage_params?.docking).toEqual({ exhaustiveness: 8, num_poses: 9 });
    expect(config.enabled_stages).toContain("docking");
    expect(config.docking_engine).toBe("vina");
  });

  it("un caso nuevo pide el panel vigente, mientras Ninguna queda explícita", () => {
    expect(configuracionDelPipeline(undefined).pro_anti_targets).toBeUndefined();
    expect(configuracionDelPipeline({ pipelineConfig: { pro_anti_targets: [] } } as CaseInputs).pro_anti_targets).toEqual([]);
  });

  it("completa una configuración a medias sin perder lo que sí tenía", () => {
    const aMedias = {
      conformers: 30,
      pipelineConfig: { stage_params: { conformer: { conformers: 30 } } },
    } as CaseInputs;
    const config = configuracionDelPipeline(aMedias);
    expect(config.stage_params?.docking).toEqual({ exhaustiveness: 8, num_poses: 9 });
    expect(config.stage_params?.conformer).toEqual({ conformers: 30 });
    expect(config.enabled_stages).toContain("docking");
    // Sin IDs guardados, el backend resuelve su panel vigente por defecto.
    expect(config.pro_anti_targets).toBeUndefined();
  });

  it("una configuración completa de Opciones no cambia", () => {
    const deOpciones: CasePipelineConfig = {
      enabled_stages: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
      stage_params: {
        docking: { exhaustiveness: 16, num_poses: 5 },
        properties: { run_admet_ai: true },
        conformer: { conformers: 1, ph: 6.5 },
      },
      docking_engine: "vina",
      pro_workers: 2,
      pro_parallel_docks: 1,
      pro_selectivity: true,
      pro_anti_targets: ["4NC3"],
      pro_mmgbsa: false,
      pro_mmgbsa_steps: 500,
      gnn_precision: "fp16",
    };
    expect(configuracionDelPipeline({ pipelineConfig: deOpciones } as CaseInputs)).toEqual(deOpciones);
  });
});
