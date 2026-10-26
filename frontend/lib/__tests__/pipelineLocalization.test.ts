import { describe, expect, it } from "vitest";
import { pro } from "../../context/traducciones/pro";
import { FAMILY_LABELS, localizePipelineText, PIPELINES_BY_FAMILY } from "../pipelineDefinitions";

describe("localizePipelineText", () => {
  it("traduce la procedencia persistida sin cambiar el valor científico", () => {
    expect(localizePipelineText("de esta corrida", key => pro.en[key])).toBe("from this run");
    expect(localizePipelineText("de esta corrida", key => pro.es[key])).toBe("de esta corrida");
    expect(localizePipelineText("-6.95 kcal/mol", key => pro.en[key])).toBe("-6.95 kcal/mol");
  });
  it("localizes every fixed pipeline note, stage note, label, and family label", () => {
    const values = new Set<string>();
    for (const [family, pipeline] of Object.entries(PIPELINES_BY_FAMILY)) {
      values.add(pipeline.label);
      values.add(pipeline.note);
      values.add(FAMILY_LABELS[family]);
      for (const stage of pipeline.stages) {
        values.add(stage.label);
        values.add(stage.value);
        values.add(stage.sub);
        if (stage.note) values.add(stage.note);
      }
    }

    const english = (key: string) => pro.en[key as keyof typeof pro.en] as string;
    const localized = [...values].map((value) => localizePipelineText(value, english));
    expect(localized).not.toContain(undefined);
    expect(localized).not.toContain("Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.");
    expect(localized).toContain("Provisional contract: Vina 1.00; XGBoost 0.00; CL-GNN runs and is reported as an experimental signal with zero weight until the exact checkpoint is validated externally.");
    expect(localized).toContain("M4 Protease · default weights");
  });

  it("keeps the Spanish UI wording byte for byte", () => {
    const spanish = (key: string) => pro.es[key as keyof typeof pro.es] as string;
    const value = PIPELINES_BY_FAMILY.gpcr.note;
    expect(localizePipelineText(value, spanish)).toBe(value);
  });
});
