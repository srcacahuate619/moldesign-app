// SCI-A-023: la interfaz no niega un ensemble que el protocolo de la corrida registra.
import { describe, expect, it } from "vitest";
import {
  conformacionesDelMuestreo,
  deriveEvaluationEvidence,
  fraseDeMuestreo,
  fraseDeMuestreoTraducida,
} from "../evaluationEvidence";
import { pro } from "../../context/traducciones/pro";
import { interpolar } from "../../context/LanguageContext";
import type { EvaluationResult } from "../types";

const t = (idioma: "es" | "en") => (clave: string, valores?: Record<string, string | number>) =>
  interpolar((pro[idioma] as Record<string, string>)[clave] ?? clave, valores);

function resultado(protocolo: Record<string, unknown> | null): EvaluationResult {
  return {
    docking_poses: [{ rank: 1, affinity: -8.0 }, { rank: 2, affinity: -7.6 }, { rank: 3, affinity: -6.0 }],
    docking_protocol: protocolo,
  } as unknown as EvaluationResult;
}

describe("muestreo declarado (SCI-A-023)", () => {
  it("un ensemble registrado se dice, no se niega", () => {
    const r = resultado({ conformers_requested: 3, conformers_generated: 3 });
    expect(conformacionesDelMuestreo(r)).toBe(3);
    const detalle = deriveEvaluationEvidence(r, null).dimensions.find((d) => d.id === "sampling")?.detail ?? "";
    expect(detalle).toContain("ensemble de 3 conformaciones");
    expect(detalle).not.toMatch(/ni ensemble/);
  });

  it("un confórmero único y un protocolo ausente se distinguen", () => {
    expect(fraseDeMuestreo(conformacionesDelMuestreo(resultado({ conformers_generated: 1 })))).toMatch(/^Confórmero único/);
    expect(fraseDeMuestreo(conformacionesDelMuestreo(resultado(null)))).toMatch(/no informa si hubo ensemble/);
  });

  it("las tres frases existen en castellano y en inglés, y el detalle localizado las usa", () => {
    for (const idioma of ["es", "en"] as const) {
      for (const g of [3, 1, null]) {
        const frase = fraseDeMuestreoTraducida(g, t(idioma));
        expect(frase).not.toMatch(/^pr_ev_/);
        expect(frase).not.toMatch(/\{count\}/);
      }
      const detalle = deriveEvaluationEvidence(resultado({ conformers_generated: 4 }), null, t(idioma))
        .dimensions.find((d) => d.id === "sampling")?.detail ?? "";
      expect(detalle).toContain(idioma === "en" ? "ensemble of 4 conformers" : "ensemble de 4 conformaciones");
      expect(detalle).not.toContain("{muestreo}");
    }
  });
});
