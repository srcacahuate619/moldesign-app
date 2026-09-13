import { describe, expect, it } from "vitest";
import { etiquetaPPB } from "../admetEtiquetas";

// ─────────────────────────────────────────────────────────────────────────
// `blood_ppb_category` vale "extreme" | "high" | "low": son codigos, no texto
// para leer, y la interfaz los imprimia tal cual. En una pantalla integramente
// en espanol aparecia «PPB: high», y la ayuda contextual llegaba a explicarlo
// diciendo «Si es 'High' (Alta)…»: la propia ayuda traducia a mano lo que la
// celda no traducia.
//
// El codigo sigue viajando en el resultado y en el dossier; solo cambia lo que
// se ensena. Y vive en UN sitio para que las dos pantallas que muestran PPB
// —`PropertiesPanel` y `ProParametersTab`— no puedan discrepar, que es como
// empezo esto.
// ─────────────────────────────────────────────────────────────────────────

describe("etiquetaPPB", () => {
  it("traduce los tres codigos que emite el backend", () => {
    expect(etiquetaPPB("extreme")).toBe("Extrema (>99 %)");
    expect(etiquetaPPB("high")).toBe("Alta (>90 %)");
    expect(etiquetaPPB("low")).toBe("Baja (≤90 %)");
  });

  it("lleva el umbral, no solo el adjetivo", () => {
    // «Alta» sin el >90 % obliga a saberse la escala de memoria.
    for (const codigo of ["extreme", "high", "low"]) {
      expect(etiquetaPPB(codigo)).toMatch(/%/);
    }
  });

  it("no distingue mayusculas: el backend podria cambiar de estilo", () => {
    expect(etiquetaPPB("HIGH")).toBe(etiquetaPPB("high"));
    expect(etiquetaPPB("Low")).toBe(etiquetaPPB("low"));
  });

  it("ausencia es null, no una categoria inventada", () => {
    // Es la distincion que costo la aspirina: sin dato NO es «baja».
    expect(etiquetaPPB(null)).toBeNull();
    expect(etiquetaPPB(undefined)).toBeNull();
  });

  it("un codigo nuevo se ensena crudo antes que desaparecer", () => {
    // Preferimos que se vea algo raro a que la fila quede en blanco sin
    // explicacion: asi el codigo nuevo se nota y se traduce.
    expect(etiquetaPPB("moderate-plus")).toBe("moderate-plus");
  });

  it("nunca devuelve el codigo en ingles para los que si conoce", () => {
    for (const codigo of ["extreme", "high", "low", "medium"]) {
      expect(etiquetaPPB(codigo)).not.toBe(codigo);
    }
  });
});
