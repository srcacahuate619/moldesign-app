// =====================================================================
// Tests de clasificación dual de receptores (lib/targetGrouping.ts)
// =====================================================================
//
// El modal "Elige Receptor" agrupa los targets por DOS ejes intercambiables:
//   - quimica    → structural_family  ("gpcr", "kinase", ...)
//   - terapeutica → therapeutic_family ("cardiovascular", "oncologia", ...)
//
// groupTargets es una función pura: NUNCA filtra (la misma lista completa se
// redistribuye), key del grupo = display name (mapa de slugs → nombre humano,
// fallback al valor crudo), bucket "Otra / No Clasificada" para campos
// null/missing, y orden: COUNT DESC + "Otra" SIEMPRE al final.
//
// La preferencia del usuario se persiste en localStorage bajo la key
// "moldesign_receptor_mode" (D6 del plan): default "quimica" (D5), valores
// basura → "quimica".
//
// Tests cubren:
// - agrupación por eje (quimica vs terapeutica) con fixtures duales
// - fallback "Otra / No Clasificada" en AMBOS ejes (null / campo ausente)
// - orden por count desc + "Otra" pinned al final (aún con más ítems)
// - display names (senescencia___aging → "Senescencia & Aging")
// - fallback al valor crudo para familias desconocidas
// - invariante: cada target aparece exactamente una vez en ambos modos
// - input vacío → resultado vacío
// - caché localStorage: default, round-trip, valores basura

import { beforeEach, describe, it, expect } from "vitest";

import type { Target } from "../api";
import {
  groupTargets,
  readClassificationMode,
  writeClassificationMode,
  THERAPEUTIC_DISPLAY_NAMES,
} from "../targetGrouping";

const UNCLASSIFIED = "Otra / No Clasificada";

// Factory de fixtures: campos por defecto + overrides. Los campos de familia
// son null por defecto → ejercitan el fallback sin escribirlos.
function mkTarget(partial: Partial<Target> & { pdb_id: string }): Target {
  return {
    ...partial,
    pdb_id: partial.pdb_id,
    name: partial.name ?? `Target ${partial.pdb_id}`,
    organism: partial.organism ?? "Homo sapiens",
    resolution: partial.resolution ?? 2.0,
    chain: partial.chain ?? "A",
    requires_cns: partial.requires_cns ?? false,
    structural_family: partial.structural_family ?? null,
    therapeutic_family: partial.therapeutic_family ?? null,
    is_hot: partial.is_hot ?? false,
    spearman_rho: partial.spearman_rho ?? null,
    calibration_date: partial.calibration_date ?? null,
  };
}

describe("groupTargets — agrupación por eje de clasificación", () => {
  it("quimica: agrupa por structural_family con display name", () => {
    const targets = [
      mkTarget({ pdb_id: "1ABC", structural_family: "kinase" }),
      mkTarget({ pdb_id: "2ABC", structural_family: "kinase" }),
      mkTarget({ pdb_id: "3ABC", structural_family: "protease" }),
    ];

    expect(groupTargets(targets, "quimica")).toEqual([
      ["Kinasa", [targets[0], targets[1]]],
      ["Proteasa", [targets[2]]],
    ]);
  });

  it("terapeutica: agrupa por therapeutic_family con display name", () => {
    const targets = [
      mkTarget({ pdb_id: "1ABC", therapeutic_family: "cardiovascular" }),
      mkTarget({ pdb_id: "2ABC", therapeutic_family: "cardiovascular" }),
      mkTarget({ pdb_id: "3ABC", therapeutic_family: "oncologia" }),
    ];

    expect(groupTargets(targets, "terapeutica")).toEqual([
      ["Cardiovascular", [targets[0], targets[1]]],
      ["Oncología", [targets[2]]],
    ]);
  });

  it("null / campo ausente → 'Otra / No Clasificada' en AMBOS ejes", () => {
    const targets = [
      mkTarget({ pdb_id: "1ABC" }), // ambos ejes null
      mkTarget({ pdb_id: "2ABC", structural_family: "kinase" }), // sin terapéutica
      mkTarget({ pdb_id: "3ABC", therapeutic_family: "oncologia" }), // sin química
    ];

    // Eje químico: Kinasa (1) primero; 1ABC y 3ABC sin structural_family
    // → Otra (2) al FINAL aunque tenga más ítems (pinned last).
    expect(groupTargets(targets, "quimica")).toEqual([
      ["Kinasa", [targets[1]]],
      [UNCLASSIFIED, [targets[0], targets[2]]],
    ]);

    // Eje terapéutico: Oncología (1) primero; 1ABC y 2ABC → Otra al final.
    expect(groupTargets(targets, "terapeutica")).toEqual([
      ["Oncología", [targets[2]]],
      [UNCLASSIFIED, [targets[0], targets[1]]],
    ]);
  });

  it("ordena por COUNT DESC y 'Otra' pinned al final (aún con más ítems)", () => {
    const targets = [
      mkTarget({ pdb_id: "1ABC" }),
      mkTarget({ pdb_id: "2ABC" }),
      mkTarget({ pdb_id: "3ABC" }),
      mkTarget({ pdb_id: "4ABC", structural_family: "kinase" }),
      mkTarget({ pdb_id: "5ABC", structural_family: "kinase" }),
      mkTarget({ pdb_id: "6ABC", structural_family: "gpcr" }),
    ];

    const groups = groupTargets(targets, "quimica");

    // Kinasa (2) > GPCR (1) > Otra (3, la más grande, pero SIEMPRE al final)
    expect(groups.map(([key]) => key)).toEqual(["Kinasa", "GPCR", UNCLASSIFIED]);
    expect(groups[0][1]).toHaveLength(2);
    expect(groups[1][1]).toHaveLength(1);
    expect(groups[2][1]).toHaveLength(3);
  });

  it("aplica display names de slugs feos (senescencia___aging → 'Senescencia & Aging')", () => {
    const targets = [
      mkTarget({ pdb_id: "1ABC", therapeutic_family: "senescencia___aging" }),
      mkTarget({ pdb_id: "2ABC", therapeutic_family: "inflamacion___dolor" }),
    ];

    const groups = groupTargets(targets, "terapeutica");
    expect(groups[0][0]).toBe("Senescencia & Aging");
    expect(groups[1][0]).toBe("Inflamación & Dolor");

    // El mapa cubre familias químicas y terapéuticas (slugs canónicos)
    expect(THERAPEUTIC_DISPLAY_NAMES["ubiquitina-proteasoma"]).toBe("Ubiquitina-Proteasoma");
    expect(THERAPEUTIC_DISPLAY_NAMES["coagulacion___hemostasia"]).toBe("Coagulación & Hemostasia");
  });

  it("familia desconocida → fallback al valor crudo como key", () => {
    const targets = [mkTarget({ pdb_id: "1ABC", structural_family: "familia_aleatoria" })];

    expect(groupTargets(targets, "quimica")[0][0]).toBe("familia_aleatoria");
  });

  it("invariante: cada target aparece exactamente una vez en ambos modos", () => {
    const targets = [
      mkTarget({ pdb_id: "1ABC", structural_family: "kinase", therapeutic_family: "oncologia" }),
      mkTarget({ pdb_id: "2ABC", structural_family: "kinase" }),
      mkTarget({ pdb_id: "3ABC", therapeutic_family: "cardiovascular" }),
      mkTarget({ pdb_id: "4ABC" }),
      mkTarget({ pdb_id: "5ABC", structural_family: "gpcr", therapeutic_family: "psiquiatria" }),
      mkTarget({ pdb_id: "6ABC", structural_family: "protease", therapeutic_family: "antiparasitarios" }),
    ];

    for (const mode of ["quimica", "terapeutica"] as const) {
      const flat = groupTargets(targets, mode).flatMap(([, items]) => items);
      expect(flat).toHaveLength(targets.length);
      expect(new Set(flat.map((t) => t.pdb_id)).size).toBe(targets.length);
    }
  });

  it("input vacío → resultado vacío", () => {
    expect(groupTargets([], "quimica")).toEqual([]);
    expect(groupTargets([], "terapeutica")).toEqual([]);
  });
});

describe("caché de modo de clasificación (localStorage moldesign_receptor_mode)", () => {
  beforeEach(() => {
    window.localStorage.setItem(
      "moldesign_auth",
      JSON.stringify({ user: { user_id: "test-user" } }),
    );
  });

  it("sin valor guardado → default 'quimica'", () => {
    expect(readClassificationMode()).toBe("quimica");
  });

  it("round-trip: write 'terapeutica' persiste y read la devuelve", () => {
    writeClassificationMode("terapeutica");
    expect(window.localStorage.getItem("moldesign_receptor_mode:user:test-user")).toBe("terapeutica");
    expect(readClassificationMode()).toBe("terapeutica");
  });

  it("valores basura → 'quimica'", () => {
    window.localStorage.setItem("moldesign_receptor_mode:user:test-user", "modo-inexistente");
    expect(readClassificationMode()).toBe("quimica");
  });
});
