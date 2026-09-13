import { describe, it, expect } from "vitest";
import { describirEtapa, etapasAusentes, tieneSalidaUms, SIN_SERIALIZAR, SIN_DESCRIPCION } from "../procedenciaDeSenales";

// Doc 71, defectos A3 y A7. El informe de la VM los listó por separado y son el
// mismo renglón: el pie caía a «sin salida serializada» aunque el valor viniera
// de la corrida.

describe("describirEtapa", () => {
  it("no dice «sin salida serializada» cuando SÍ hay valor (A7)", () => {
    const r = describirEtapa({ id: "vina" }, { value: "-7.0 kcal/mol" });
    expect(r.value).toBe("-7.0 kcal/mol");
    expect(r.sub).not.toBe(SIN_SERIALIZAR);
    expect(r.sub).toBe(SIN_DESCRIPCION);
  });

  it("no contradice al dossier, que contaba nueve poses serializadas (A3)", () => {
    // El dossier decía «9 poses serializadas» con su hash y el DOT decía lo
    // contrario para la misma corrida. El dossier tenía razón.
    const r = describirEtapa({ id: "vina" }, { value: "-9.4 kcal/mol", weight: 0.2 });
    expect(r.sub).not.toContain("sin salida");
    expect(r.reportedWeight).toBe(0.2);
  });

  it("sí lo dice cuando la etapa no reportó nada", () => {
    const r = describirEtapa({ id: "clgnn" }, undefined);
    expect(r.value).toBe("no reportado");
    expect(r.sub).toBe(SIN_SERIALIZAR);
  });

  it("distingue una etapa opcional no calculada de una que falló en reportar", () => {
    const r = describirEtapa({ id: "mmgbsa", post_hoc: true }, undefined);
    expect(r.value).toBe("no calculado");
    expect(r.sub).toBe("cálculo opcional");
  });

  it("respeta el pie que el backend sí sabe describir", () => {
    const r = describirEtapa({ id: "mmgbsa", post_hoc: true },
      { value: "-8.2 kcal/mol", sub: "OpenMM" });
    expect(r.sub).toBe("OpenMM");
  });

  it("nunca hereda los literales de ejemplo de pipelineDefinitions", () => {
    // «v1.2.7» y «500 trees» describen la familia, no esta corrida. Usarlos de
    // respaldo seria la misma invencion que el fix UI-8 quito de MM-GBSA.
    const r = describirEtapa({ id: "xgb" }, { value: "salida 0.05" });
    expect(r.sub).not.toContain("trees");
    expect(r.sub).not.toContain("v1.2.7");
  });
});

// La VM del 2026-09-03, 2BQV: la tarjeta de CL-GNN decia «no reportado · sin
// salida serializada · w=0.00» y justo debajo «Δ AUC +0.086 (HIV-1) · CL-GNN
// solo AUC 0.95». Lo segundo es la validacion del modelo en OTRO estudio, y
// puesto ahi se lee como la calidad de este numero.

describe("la nota de validacion no sobrevive a una etapa que no corrio", () => {
  const clgnn = {
    id: "clgnn",
    weight: 0.6,
    label: "CL-GNN",
    note: "Δ AUC +0.086 (HIV-P) · CL-GNN solo AUC 0.95",
  };

  it("retira la nota cuando la etapa no reporto valor", () => {
    const r = describirEtapa(clgnn, undefined);
    expect(r.value).toBe("no reportado");
    expect(r.note).toBeUndefined();
    expect(r.aporto).toBe(false);
  });

  it("conserva la nota cuando la etapa si corrio", () => {
    const r = describirEtapa(clgnn, { value: "0.74", weight: 0.6 });
    expect(r.note).toBe(clgnn.note);
    expect(r.aporto).toBe(true);
  });

  it("un peso reportado de cero no basta: lo que cuenta es si hubo salida", () => {
    // El backend renormaliza y puede mandar w=0 para una etapa que SI opino.
    const r = describirEtapa(clgnn, { value: "0.51", weight: 0 });
    expect(r.aporto).toBe(true);
    expect(r.note).toBe(clgnn.note);
  });
});

describe("etapasAusentes", () => {
  it("nombra la señal que el diseño pondera y la corrida no produjo", () => {
    const etapas = [
      { id: "vina", weight: 0.1, label: "Docking Vina", aporto: true },
      { id: "xgb", weight: 0.3, label: "XGBoost", aporto: true },
      { id: "clgnn", weight: 0.6, label: "CL-GNN", aporto: false },
    ];
    expect(etapasAusentes(etapas)).toEqual([
      { id: "clgnn", label: "CL-GNN", pesoDeDiseno: 0.6 },
    ]);
  });

  it("no delata a una etapa post-hoc: no calcularla es lo normal", () => {
    const etapas = [
      { id: "mmgbsa", weight: 0, label: "MM-GBSA", post_hoc: true, aporto: false },
      { id: "quantum", weight: 0, label: "Quantum", post_hoc: true, aporto: false },
    ];
    expect(etapasAusentes(etapas)).toEqual([]);
  });

  it("no delata a una etapa que el diseño ya apagaba (w=0)", () => {
    // En nuclear_receptor, CL-GNN esta desactivado a proposito (Δ AUC -0.003).
    const etapas = [{ id: "clgnn", weight: 0, label: "CL-GNN", aporto: false }];
    expect(etapasAusentes(etapas)).toEqual([]);
  });

  it("no dice nada cuando todo el pipeline opino", () => {
    const etapas = [
      { id: "vina", weight: 0.2, label: "Docking Vina", aporto: true },
      { id: "xgb", weight: 0.8, label: "XGBoost", aporto: true },
    ];
    expect(etapasAusentes(etapas)).toEqual([]);
  });
});

describe("presencia de UMS en el resultado persistido", () => {
  it("reconoce ums_warhead como la señal actual aunque ums_score falte", () => {
    expect(tieneSalidaUms({ ums_warhead: 0.42, ums_score: null })).toBe(true);
  });

  it("conserva la compatibilidad con el campo histórico", () => {
    expect(tieneSalidaUms({ ums_warhead: null, ums_score: 0.31 })).toBe(true);
  });

  it("no confunde la ausencia de ambas señales con un cero", () => {
    expect(tieneSalidaUms({ ums_warhead: null, ums_score: null })).toBe(false);
  });
});