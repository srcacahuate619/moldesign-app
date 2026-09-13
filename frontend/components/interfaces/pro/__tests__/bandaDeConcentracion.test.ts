import { describe, expect, it } from "vitest";
import { bandaDeConcentracion } from "../ProSelectivityPanel";

// ─────────────────────────────────────────────────────────────────────────
// El panel de anti-dianas imprimia, de un score de Vina:
//
//     Estimación Ki / IC50:   0.4 µM
//
// Dos afirmaciones falsas en la misma celda:
//
//  · «Ki / IC50» son dos observables experimentales distintos, y Vina no mide
//    ninguno: su score es una funcion empirica de puntuacion, no una energia
//    libre;
//  · UN DECIMAL. La dispersion del score de Vina frente a afinidad medida esta
//    en 1.5-2.5 kcal/mol. Como la relacion es exponencial, 1.4 kcal/mol ya son
//    diez veces la concentracion y 2.8 kcal/mol son cien.
//
// El resto del producto ya se cuida de no disfrazar la afinidad de Vina como
// una constante experimental; este panel —el de SEGURIDAD— era el que no.
// ─────────────────────────────────────────────────────────────────────────

describe("banda de concentracion implicada por el score", () => {
  it("no devuelve un punto: devuelve los dos extremos", () => {
    const banda = bandaDeConcentracion(-9.0);
    expect(banda.inferior).not.toBe(banda.superior);
  });

  it("la anchura son mas de dos ordenes de magnitud", () => {
    // +-2 kcal/mol a 310 K = multiplicar y dividir por ~26.
    const banda = bandaDeConcentracion(-9.0);
    expect(banda.ordenes).toBeGreaterThan(2.5);
    expect(banda.ordenes).toBeLessThan(3.5);
  });

  it("la anchura no depende del score: la incertidumbre es la misma", () => {
    const fuerte = bandaDeConcentracion(-12.0);
    const debil = bandaDeConcentracion(-5.0);
    expect(fuerte.ordenes).toBeCloseTo(debil.ordenes, 6);
  });

  it("un score mas negativo desplaza la banda a concentraciones menores", () => {
    // -12 kcal/mol debe implicar menos concentracion que -6.
    expect(bandaDeConcentracion(-12.0).inferior).toMatch(/pM|nM/);
    expect(bandaDeConcentracion(-4.0).superior).toMatch(/mM|M$/);
  });

  it("elige la unidad segun la magnitud, sin notacion cientifica", () => {
    for (const score of [-2, -4, -6, -8, -10, -14]) {
      const banda = bandaDeConcentracion(score);
      expect(banda.inferior).toMatch(/^[\d.]+ (pM|nM|µM|mM|M)$/);
      expect(banda.superior).toMatch(/^[\d.]+ (pM|nM|µM|mM|M)$/);
      expect(banda.inferior).not.toContain("e+");
      expect(banda.inferior).not.toContain("e-");
    }
  });
});
