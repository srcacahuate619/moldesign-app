import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { configuracionDelPipeline } from "../CaseEvaluationRunner";
const source = () => readFileSync(resolve("components/interfaces/pro/ProEvaluation.tsx"), "utf8");
describe("modo tautomérico guardado y firmado", () => {
  it("restaura el modo guardado; sin clave, una corrida anterior fue canónica y un caso nuevo usa la entrada", () => {
    expect(source()).toContain('if (guardado === "canonico" || guardado === "entrada") return guardado;');
    expect(source()).toContain('return initialRunConfiguration?.pipelineConfig ? "canonico" : "entrada";');
  });
  it("envía siempre el modo explícito: el defecto del backend ya no es el canónico", () => {
    expect(source()).toContain('tautomero: adv.tautomerMode ?? "entrada",');
  });
  it("la copia efectiva conserva el modo guardado y el K vigente", () => {
    const effective = configuracionDelPipeline({ conformers: 3, pipelineConfig: { stage_params: { conformer: { tautomero: "entrada", ph: 7.4 } } } });
    expect(effective.stage_params?.conformer).toMatchObject({ tautomero: "entrada", conformers: 3, ph: 7.4 });
  });
});
