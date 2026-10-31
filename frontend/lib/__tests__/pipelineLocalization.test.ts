import { describe, expect, it } from "vitest";
import { pro } from "../../context/traducciones/pro";
import { FAMILY_LABEL_KEYS, localizePipeline, PIPELINES_BY_FAMILY } from "../pipelineDefinitions";
import { describirEtapa } from "../procedenciaDeSenales";
import { stageEventToOrbUpdate, type PipelineEvent } from "../pipelineStream";
describe.each(["es", "en"] as const)("procedencia por claves en %s", locale => {
  const t = (key: string) => pro[locale][key] ?? key;
  it("localiza las definiciones sin modificar pesos ni los originales", () => {
    const bytes = JSON.stringify(PIPELINES_BY_FAMILY);
    for (const pipeline of Object.values(PIPELINES_BY_FAMILY)) {
      const shown = localizePipeline(pipeline, t);
      expect(shown.stages.map(s => [s.id, s.weight, s.post_hoc])).toEqual(pipeline.stages.map(s => [s.id, s.weight, s.post_hoc]));
      if (locale === "es") expect(shown.note).toBe(pipeline.note);
      else expect(shown.note).not.toMatch(/Contrato provisional|Target sin curación/);
    }
    expect(JSON.stringify(PIPELINES_BY_FAMILY)).toBe(bytes);
    expect(t(FAMILY_LABEL_KEYS.protease)).toBe(locale === "es" ? "Proteasa" : "Protease");
  });
  it("traduce ausencias locales y conserva valores y texto del backend", () => {
    expect(describirEtapa({ id: "vina" }, { value: "-6.95 kcal/mol" }, t)).toMatchObject({ value: "-6.95 kcal/mol", sub: locale === "es" ? "de esta corrida" : "from this run" });
    expect(describirEtapa({ id: "xgb" }, undefined, t)).toMatchObject({ value: locale === "es" ? "no reportado" : "not reported", sub: locale === "es" ? "sin salida serializada" : "no serialized output" });
    expect(describirEtapa({ id: "mmgbsa", post_hoc: true }, undefined, t)).toMatchObject({ value: locale === "es" ? "no calculado" : "not calculated", sub: locale === "es" ? "cálculo opcional" : "optional calculation" });
    expect(describirEtapa({ id: "vina" }, { value: "dato externo", sub: "origen externo" }, t).sub).toBe("origen externo");
    const event = { type: "stage_error", stage_id: "xgb" } as PipelineEvent;
    expect(stageEventToOrbUpdate(event, t)?.message).toBe(locale === "es" ? "Error en la etapa" : "Stage error");
    expect(stageEventToOrbUpdate({ ...event, error: "fallo del backend" }, t)?.message).toBe("fallo del backend");
  });
});
