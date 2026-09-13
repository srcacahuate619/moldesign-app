// =====================================================================
// Tests del DOT por familia (lib/pipelineDefinitions.ts)
// =====================================================================
//
// El DOT de resultados reales cae a PIPELINES_BY_FAMILY cuando el backend
// no serializa un métrico (registros legacy → null). Estas constantes son
// la fuente única de verdad del DOT (family-gated stacking).
//
// Tests cubren:
// - las 6 familias definidas con sus nodos esperados
//   (validation/conformer/docking son etapas de RUN del backend → se validan
//   contra el orden canónico del timeline en el test de "8 orbs")
// - nodo Quantum en TODAS las familias: weight 0.0 y value 0.55 (post_hoc)
// - convención de pesos: suman 1.0 en las familias M4
// - metaloenzyme: HOY es M4 con pesos por defecto. M5-Zn esta implementado
//   y NO conectado, y UMS/MolChamb son senales informativas con peso 0
// - fallback de familia desconocida → default (stacking neutro, no gpcr)
// - orden del timeline de 8 orbs vs. orden canónico de etapas del backend

import { describe, it, expect } from "vitest";

import { PIPELINES_BY_FAMILY, FAMILY_LABELS } from "../pipelineDefinitions";
import { SSE_TO_ORB } from "../pipelineStream";

// Nodos que TODO pipeline del DOT debe exponer (fallback por métrico null)
const REQUIRED_DOT_NODES = ["vina", "xgb", "clgnn", "quantum", "mmgbsa"];
// Familias M4 clásicas: incluyen el nodo GNN-v3 (degradado)
const M4_REQUIRED_NODES = [...REQUIRED_DOT_NODES, "gnn"];
// Metaloenzyme anade UMS y MolChamb como senales INFORMATIVAS, ademas de los
// nodos M4 — porque hoy se puntua con M4.
const METALOENZYME_NODES = [...M4_REQUIRED_NODES, "ums", "molchamb"];

// TODAS las familias son M4 hoy: los pesos suman 1.0 en las cuatro etapas del
// stacking. La entrada de metaloenzimas se retiro de stacking_weights.json el
// 2026-09-04 (ADR 75) y M5-Zn no esta conectado al pipeline, asi que esas
// dianas caen a los pesos por defecto como cualquier otra familia sin
// calibracion propia.
const M4_FAMILIES = [
  "gpcr",
  "protease",
  "kinase",
  "nuclear_receptor",
  "soluble_enzyme",
  "metaloenzyme",
];

describe("PIPELINES_BY_FAMILY — fallbacks del DOT por familia", () => {
  it("define exactamente las 7 familias del family-gating (6 curadas + default)", () => {
    expect(Object.keys(PIPELINES_BY_FAMILY)).toEqual([
      "default",
      "gpcr",
      "protease",
      "kinase",
      "nuclear_receptor",
      "soluble_enzyme",
      "metaloenzyme",
    ]);
  });

  it("FAMILY_LABELS cubre todas las familias (y default)", () => {
    for (const fam of Object.keys(PIPELINES_BY_FAMILY)) {
      expect(FAMILY_LABELS[fam]).toBeTruthy();
    }
    expect(FAMILY_LABELS.default).toBe("Default");
  });

  it("cada familia expone los nodos DOT requeridos (fallback null-safe)", () => {
    for (const fam of M4_FAMILIES) {
      const ids = PIPELINES_BY_FAMILY[fam].stages.map((s) => s.id);
      for (const node of M4_REQUIRED_NODES) {
        expect(ids).toContain(node);
      }
    }
    const metalIds = PIPELINES_BY_FAMILY.metaloenzyme.stages.map((s) => s.id);
    for (const node of METALOENZYME_NODES) {
      expect(metalIds).toContain(node);
    }
  });

  it("metaloenzyme agrega los orbes ortogonales UMS y MolChamb", () => {
    const ids = PIPELINES_BY_FAMILY.metaloenzyme.stages.map((s) => s.id);
    for (const node of ["ums", "molchamb"]) {
      expect(ids).toContain(node);
    }
    // Y conserva los del stack M4, porque hoy se puntua con M4.
    expect(ids).toContain("gnn");
  });

  it("Quantum existe en TODAS las familias con weight 0.0 y value 0.55", () => {
    for (const pipeline of Object.values(PIPELINES_BY_FAMILY)) {
      const quantum = pipeline.stages.find((s) => s.id === "quantum");
      expect(quantum, `${pipeline.id} debería tener nodo quantum`).toBeDefined();
      expect(quantum!.weight).toBe(0.0);
      expect(quantum!.value).toBe("0.55");
      expect(quantum!.post_hoc).toBe(true);
    }
  });

  it("familias M4: los pesos de stacking suman 1.0 (post_hoc no cuenta)", () => {
    for (const fam of M4_FAMILIES) {
      const pipeline = PIPELINES_BY_FAMILY[fam];
      const total = pipeline.stages.reduce((acc, s) => acc + s.weight, 0);
      expect(total).toBeCloseTo(1.0, 5);
    }
  });

  it("metaloenzyme: UMS y MolChamb son informativos, con peso 0 en el ranking", () => {
    // Llegaron a mostrarse con peso 1.00 bajo la etiqueta «M5 Gated · UMS +
    // MolChamb + CL-GNN (sin Vina)». Nada de eso se ejecuta: el ADR 75 retiro
    // el empujon aditivo de UMS al stacking y M5-Zn no esta conectado al
    // pipeline. Un peso distinto de cero aqui afirma una contribucion al
    // ranking que el engine no hace.
    const pipeline = PIPELINES_BY_FAMILY.metaloenzyme;
    for (const id of ["ums", "molchamb"]) {
      const etapa = pipeline.stages.find((s) => s.id === id);
      expect(etapa?.weight).toBe(0.0);
      expect(etapa?.post_hoc).toBe(true);
    }
    // Y Vina y XGBoost SI puntuan: son los pesos por defecto de M4.
    expect(pipeline.stages.find((s) => s.id === "vina")?.weight).toBe(0.25);
    expect(pipeline.stages.find((s) => s.id === "xgb")?.weight).toBe(0.75);
  });

  it("ninguna familia atribuye a CL-GNN el peso de la GNN legacy", () => {
    // En GPCR el artefacto vigente da 0.40 a la GNN legacy de RTMScore y 0.00 a
    // CL-GNN. La interfaz mostraba ese 0.40 sobre CL-GNN: atribuia la
    // influencia al modelo equivocado.
    const gpcr = PIPELINES_BY_FAMILY.gpcr;
    expect(gpcr.stages.find((s) => s.id === "gnn")?.weight).toBe(0.0);
    expect(gpcr.stages.find((s) => s.id === "clgnn")?.weight).toBe(0.0);
  });

  it("cada familia tiene al menos una etapa activa (weight > 0)", () => {
    for (const pipeline of Object.values(PIPELINES_BY_FAMILY)) {
      expect(pipeline.stages.some((s) => s.weight > 0)).toBe(true);
    }
  });

  it("ids de etapas únicos dentro de cada familia", () => {
    for (const pipeline of Object.values(PIPELINES_BY_FAMILY)) {
      const ids = pipeline.stages.map((s) => s.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it("ids de pipeline únicos entre familias", () => {
    const ids = Object.values(PIPELINES_BY_FAMILY).map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("familia desconocida → cae al pipeline 'default' (target no curado)", () => {
    // FIX UI-8 (2026-08-04): antes el fallback era `?? PIPELINES_BY_FAMILY.gpcr`
    // → un target no curado mostraba "M4 GPCR" con pesos que no aplican.
    // Ahora existe key "default" (stacking neutro, marcado no-curado) y el
    // lookup de familia desconocida cae a él.
    expect(PIPELINES_BY_FAMILY.default).toBeDefined();
    expect(PIPELINES_BY_FAMILY.default.id).toBe("m4_default_uncured");
    expect(PIPELINES_BY_FAMILY.gpcr).toBeDefined();
    // Familia no definida → lookup undefined → el ?? default resuelve
    expect(PIPELINES_BY_FAMILY["no_existe"]).toBeUndefined();
  });
});

describe("Timeline de 8 orbs vs. orden canónico de etapas", () => {
  // Orden de los orbs del PipelineTimeline (DEFAULT_STAGES)
  const TIMELINE_ORBS = [
    "validation", "properties", "conformer", "vina", "xgb", "clgnn", "openmm", "mmgbsa",
  ];

  // Orden canónico de etapas del backend (registry.py STAGE_REGISTRY)
  const CANONICAL_STAGE_ORDER = [
    "validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn", "openmm",
  ];

  it("el timeline respeta el orden canónico de las etapas del backend", () => {
    // Cada orb del timeline se traduce a su stage_id SSE (inversa de SSE_TO_ORB)
    const orbToStage: Record<string, string> = {};
    for (const [stageId, orb] of Object.entries(SSE_TO_ORB)) {
      orbToStage[orb] = stageId;
    }

    const timelineStages = TIMELINE_ORBS.map((orb) => orbToStage[orb]);
    expect(timelineStages).toEqual([
      "validation", "properties", "conformer", "docking", "xgb", "clgnn", "openmm", "mmgbsa",
    ]);

    // `properties` precede al conformero, igual que en el registro del
    // backend (conformer depende de properties). Ése es el orden en el que
    // ADMET-AI ocurre, y por tanto el orden en el que se puede mirar.
    expect(timelineStages.indexOf("properties")).toBeLessThan(
      timelineStages.indexOf("conformer"),
    );

    // Las etapas del registro deben aparecer en orden relativo canónico
    const registryStages = timelineStages.filter((s) => CANONICAL_STAGE_ORDER.includes(s));
    const indices = registryStages.map((s) => CANONICAL_STAGE_ORDER.indexOf(s));
    const sorted = [...indices].sort((a, b) => a - b);
    expect(indices).toEqual(sorted);

    // mmgbsa es post-hoc del frontend: va última, tras openmm
    expect(timelineStages.indexOf("mmgbsa")).toBe(timelineStages.length - 1);
  });

  it("todo stage SSE con orb existe en el orden canónico (o es mmgbsa)", () => {
    const known = new Set([...CANONICAL_STAGE_ORDER, "mmgbsa"]);
    for (const stageId of Object.keys(SSE_TO_ORB)) {
      expect(known.has(stageId)).toBe(true);
    }
  });
});
