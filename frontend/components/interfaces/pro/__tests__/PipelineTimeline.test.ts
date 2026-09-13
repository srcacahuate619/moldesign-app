import { describe, expect, it } from "vitest";

import {
  PROPERTIES_ADMET_LABEL,
  PROPERTIES_LABEL,
  stagesForPipeline,
} from "../PipelineTimeline";

describe("stagesForPipeline", () => {
  it("oculta OpenMM y MM-GBSA cuando el usuario no los activó", () => {
    const ids = stagesForPipeline({
      enabled_stages: ["validation", "properties", "conformer", "docking", "xgb", "clgnn"],
      pro_mmgbsa: false,
    }).map((stage) => stage.id);

    expect(ids).toEqual(["validation", "properties", "conformer", "vina", "xgb", "clgnn"]);
  });

  it("muestra las etapas opcionales sólo cuando forman parte del protocolo", () => {
    const ids = stagesForPipeline({
      enabled_stages: ["validation", "conformer", "docking", "xgb", "clgnn", "openmm"],
      pro_mmgbsa: true,
    }).map((stage) => stage.id);

    expect(ids).toContain("openmm");
    expect(ids).toContain("mmgbsa");
  });
});

// ─────────────────────────────────────────────────────────────────────────
// El tiempo de ADMET tiene dueño
//
// ADMET-AI corre DENTRO de la etapa `properties` del backend (`runner.py`,
// rama `stage_id == "properties"`), y en su primera carga se lleva la mayor
// parte del reloj —en una VM, minutos—. Mientras tanto, `properties` no tenía
// orb: la línea temporal se quedaba quieta entre «Curación» y «3D ETKDG» y el
// usuario le apuntaba esos minutos al conformero. Que además es falso por
// partida doble: el conformero se genera EN PARALELO dentro de esa misma
// etapa y llega hecho a su propio orb.
//
// La regla que fijan estas pruebas: **la etapa que gasta el tiempo es la que
// lo enseña, y sólo se nombra ADMET cuando la corrida lo pidió.**
// ─────────────────────────────────────────────────────────────────────────

const BASE = {
  enabled_stages: ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
  pro_mmgbsa: false,
} as const;

describe("etapa Propiedades / ADMET en la línea temporal", () => {
  it("con ADMET activo muestra una etapa propia, y va antes del conformero", () => {
    const stages = stagesForPipeline({
      ...BASE,
      stage_params: { properties: { run_admet_ai: true } },
    });
    const ids = stages.map((s) => s.id);
    const properties = stages.find((s) => s.id === "properties");

    expect(properties?.label).toBe(PROPERTIES_ADMET_LABEL);
    expect(ids.indexOf("properties")).toBeGreaterThan(-1);
    expect(ids.indexOf("properties")).toBeLessThan(ids.indexOf("conformer"));
  });

  it("con ADMET activo, «3D ETKDG» sigue siendo sólo el conformero", () => {
    const stages = stagesForPipeline({
      ...BASE,
      stage_params: { properties: { run_admet_ai: true } },
    });

    // El conformero conserva su etiqueta y NO absorbe la de ADMET: el tiempo
    // del modelo se ve en su propio nodo o no se ve en ninguno honesto.
    expect(stages.find((s) => s.id === "conformer")?.label).toBe("3D ETKDG");
    expect(stages.filter((s) => s.label.includes("ADMET"))).toHaveLength(1);
  });

  it("con ADMET desactivado la etapa existe pero NO afirma ADMET", () => {
    const stages = stagesForPipeline({
      ...BASE,
      stage_params: { properties: { run_admet_ai: false } },
    });

    expect(stages.find((s) => s.id === "properties")?.label).toBe(PROPERTIES_LABEL);
    expect(stages.some((s) => s.label.includes("ADMET"))).toBe(false);
  });

  it("sin configuración de propiedades no se nombra ADMET (opt-in, no opt-out)", () => {
    // El tipo se declara: si no, TS unifica los miembros del array y acaba
    // inventando un `stage_params` con claves opcionales que la firma real
    // no acepta.
    const configuraciones: Array<Parameters<typeof stagesForPipeline>[0]> = [
      { ...BASE },
      { ...BASE, stage_params: {} },
      { ...BASE, stage_params: { properties: {} } },
      { ...BASE, stage_params: { docking: { exhaustiveness: 8 } } },
      // Un manifiesto viejo con un valor que no es un booleano tampoco
      // enciende nada: sólo un `true` explícito cuenta.
      { ...BASE, stage_params: { properties: { run_admet_ai: "true" } } },
      { ...BASE, stage_params: { properties: { run_admet_ai: 1 } } },
      undefined,
    ];

    for (const config of configuraciones) {
      const stages = stagesForPipeline(config);
      expect(stages.some((s) => s.label.includes("ADMET"))).toBe(false);
      expect(stages.find((s) => s.id === "properties")?.label).toBe(PROPERTIES_LABEL);
    }
  });

  it("el orden de la línea temporal respeta el del pipeline real", () => {
    const ids = stagesForPipeline({
      enabled_stages: [
        "validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn", "openmm",
      ],
      pro_mmgbsa: true,
      stage_params: { properties: { run_admet_ai: true } },
    }).map((s) => s.id);

    expect(ids).toEqual([
      "validation", "properties", "conformer", "vina", "xgb", "clgnn", "openmm", "mmgbsa",
    ]);
  });
});
