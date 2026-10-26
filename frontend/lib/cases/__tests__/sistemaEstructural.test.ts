import { describe, expect, it } from "vitest";
import { inputsForStructuralSystem, mismoSistemaEstructural, pideOtroSistema, type CaseInputs } from "../types";

// El aviso «este caso ya está fijado a su sistema estructural» saltaba al cambiar sólo el ligando.
const receptor = { pdbId: "8T69", chain: "A", name: "VMAT2" } as unknown as CaseInputs["receptor"];
const grid = { center: [127.862, 123.474, 104.225], size: [30, 30, 30] } as unknown as CaseInputs["grid"];
const residuos = ["A:ALA337", "A:TYR433"];
const sistema = { receptor, grid, customHotspots: residuos } as never;

describe("mismoSistemaEstructural", () => {
  it("no depende del orden de las claves", () => {
    const reordenado = { chain: "A", name: "VMAT2", pdbId: "8T69" } as unknown as CaseInputs["receptor"];
    const a = { receptor, grid, customHotspots: residuos } as unknown as CaseInputs;
    expect(mismoSistemaEstructural(a, { ...a, receptor: reordenado })).toBe(true);
  });

  it("ve un cambio real del receptor, de la caja o de los residuos (control negativo)", () => {
    const base = { receptor, grid, customHotspots: [] } as unknown as CaseInputs;
    expect(mismoSistemaEstructural(base, { ...base, receptor: { ...(receptor as object), chain: "B" } } as CaseInputs)).toBe(false);
    expect(mismoSistemaEstructural(base, { ...base, grid: { center: [0, 0, 0], size: [30, 30, 30] } } as unknown as CaseInputs)).toBe(false);
    expect(mismoSistemaEstructural(base, { ...base, customHotspots: ["A:TYR433"] })).toBe(false);
  });
});

describe("pideOtroSistema", () => {
  it("cambiar sólo el ligando no pide otro sistema, aunque los inputs no traigan los residuos (lo medido al grabar)", () => {
    const actuales = { receptor, grid, ligand: { smiles: "CCO" } } as unknown as CaseInputs;
    const patch = { ligand: { smiles: "CCN" } } as unknown as Partial<CaseInputs>;
    const restituidos = inputsForStructuralSystem(sistema, { ...actuales, ...patch });
    expect(restituidos.customHotspots).toEqual(residuos);
    expect(pideOtroSistema(patch, restituidos)).toBe(false);
  });

  it("pedir otro receptor, otra caja u otros residuos sí lo pide (control negativo)", () => {
    const restituidos = inputsForStructuralSystem(sistema, { receptor, grid } as unknown as CaseInputs);
    expect(pideOtroSistema({ receptor: { ...(receptor as object), chain: "B" } } as Partial<CaseInputs>, restituidos)).toBe(true);
    expect(pideOtroSistema({ grid: { center: [0, 0, 0], size: [30, 30, 30] } } as unknown as Partial<CaseInputs>, restituidos)).toBe(true);
    expect(pideOtroSistema({ customHotspots: [] }, restituidos)).toBe(true);
  });
});
