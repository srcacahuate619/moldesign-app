import { describe, expect, it } from "vitest";
import { sameMolcyAjustes } from "../molcyPresentation";
import { AUTO_PRESENTATION } from "@/components/molcy/PresentationControls";
describe("immutable photo presentation", () => {
  const requested = { presentacion: { ...AUTO_PRESENTATION, titulo: " Alias ", color_receptor: "#abcdef" }, ensamble_fluido: { variante: "lenta" as const } };
  const saved = { presentacion: { ...AUTO_PRESENTATION, titulo: "Alias", color_receptor: "#ABCDEF" }, ensamble_fluido: { variante: "lenta" as const, conformero: 7 } };
  it("matches normalized cosmetic values and the effective conformer when not explicitly requested", () => {
    expect(sameMolcyAjustes(requested, saved)).toBe(true);
    expect(sameMolcyAjustes({ ...requested, ensamble_fluido: {variante:"lenta", conformero: 8} }, saved)).toBe(false);
  });
  it("requires a new photo scene after visibility or motion choices change", () => {
    expect(sameMolcyAjustes({...requested,presentacion:{...requested.presentacion,contactos:false}},saved)).toBe(false);
    expect(sameMolcyAjustes({...requested,ensamble_fluido:{variante:"detallada"}},saved)).toBe(false);
    expect(sameMolcyAjustes(requested,undefined)).toBe(false);
  });
});
