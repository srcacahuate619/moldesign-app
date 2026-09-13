import { describe, expect, it } from "vitest";
import {
  ESCALA_DE_MARGEN,
  KCAL_POR_DECADA,
  VEREDICTO_INVERTIDO,
  VEREDICTO_SIN_DATOS,
  bandaDeFactor,
  colorDeMargen,
  factorDeSelectividad,
  formatearFactor,
  margenDeSelectividad,
  veredictoDeMargen,
} from "../selectividadMargen";

// ─────────────────────────────────────────────────────────────────────────
// El panel dividia dos energias libres.
//
//     ratio = ΔG_on / ΔG_off
//
// Como ΔG = −RT·ln K_d, eso es ln K_on / ln K_off: el logaritmo de una
// constante de disociacion en la base de la otra. No describe nada.
//
// Y ademas la escala de veredictos estaba DUPLICADA y no coincidia:
//
//     backend  (selectivity_verdict)   > 10   > 3    > 1.5  > 1.0
//     frontend (ProSelectivityPanel)   > 1.8  > 1.2  > 0.9
//
// Un cociente de 2.0 se guardaba en el dossier como «MODERADAMENTE SELECTIVO»
// mientras la pantalla decia «ALTAMENTE SELECTIVO» para la MISMA corrida.
// ─────────────────────────────────────────────────────────────────────────

describe("ΔΔG en vez del cociente", () => {
  it("separa margenes que el cociente confundia", () => {
    // Los dos casos que daban 2.00 y por tanto el mismo veredicto.
    expect(margenDeSelectividad(-10.0, -5.0)).toBe(5.0);
    expect(margenDeSelectividad(-6.0, -3.0)).toBe(3.0);
    expect(-10.0 / -5.0).toBeCloseTo(-6.0 / -3.0, 10);
  });

  it("no depende de la potencia absoluta", () => {
    // El cociente daba 1.5 y 1.2 para el mismo margen de 2 kcal/mol.
    expect(margenDeSelectividad(-6.0, -4.0)).toBe(2.0);
    expect(margenDeSelectividad(-12.0, -10.0)).toBe(2.0);
  });

  it("no unirse a la anti-diana es el mejor caso, no un hueco", () => {
    // Con ΔG_off ≥ 0 el cociente se indefinia.
    expect(margenDeSelectividad(-9.0, 0.5)).toBe(9.5);
    expect(veredictoDeMargen(9.5)).toBe(ESCALA_DE_MARGEN[0][1]);
  });

  it("el signo dice quien une mas fuerte", () => {
    expect(veredictoDeMargen(-4.0)).toBe(VEREDICTO_INVERTIDO);
    expect(colorDeMargen(-4.0)).toBe("#ef4444");
  });

  it("sin afinidades no hay margen", () => {
    expect(margenDeSelectividad(null, -6)).toBeNull();
    expect(margenDeSelectividad(-6, undefined)).toBeNull();
    expect(veredictoDeMargen(null)).toBe(VEREDICTO_SIN_DATOS);
    expect(colorDeMargen(null)).toBe("#64748b");
  });
});

describe("el factor implicado", () => {
  it("una decada por cada 1.3633 kcal/mol", () => {
    expect(factorDeSelectividad(0)).toBeCloseTo(1, 10);
    expect(factorDeSelectividad(KCAL_POR_DECADA)).toBeCloseTo(10, 8);
    expect(factorDeSelectividad(2 * KCAL_POR_DECADA)).toBeCloseTo(100, 6);
  });

  it("se reporta como banda, no como punto", () => {
    // ±2 kcal/mol son casi tres ordenes de magnitud: «4.680x» seria la misma
    // pseudoprecision que ya se quito de la columna de Ki.
    const banda = bandaDeFactor(4.0);
    expect(banda.min).toBeLessThan(banda.max);
    expect(Math.log10(banda.max / banda.min)).toBeCloseTo(4 / KCAL_POR_DECADA, 6);
  });

  it("formatea sin decimales que no sostiene", () => {
    expect(formatearFactor(1234.6)).toBe(`${Math.round(1234.6).toLocaleString("es")}x`);
    expect(formatearFactor(42.7)).toBe("43x");
    expect(formatearFactor(3.14)).toBe("3.1x");
  });
});

describe("la escala", () => {
  it("los cortes estan en ordenes de magnitud redondos", () => {
    // Tolerancia relativa: 2.73 y 1.36 son los umbrales redondeados a dos
    // decimales, no los exactos, asi que el factor cae cerca de 100 y de 10.
    expect(factorDeSelectividad(ESCALA_DE_MARGEN[0][0]) / 100).toBeCloseTo(1, 1);
    expect(factorDeSelectividad(ESCALA_DE_MARGEN[1][0]) / 10).toBeCloseTo(1, 1);
  });

  it("ninguna etiqueta promete seguridad", () => {
    // Un margen in silico con ±2 kcal/mol no autoriza esa palabra, y menos en
    // el panel de anti-dianas.
    for (const [, veredicto] of ESCALA_DE_MARGEN) {
      expect(veredicto.toLowerCase()).not.toContain("seguro");
      expect(veredicto.toLowerCase()).not.toContain("seguridad");
    }
  });

  it("el color sale de la misma escala que el veredicto", () => {
    expect(colorDeMargen(3.0)).toBe("#10b981");
    expect(colorDeMargen(2.0)).toBe("#34d399");
    expect(colorDeMargen(0.5)).toBe("#f59e0b");
    expect(colorDeMargen(0.1)).toBe("#ef4444");
  });

  it("es monotona", () => {
    const umbrales = ESCALA_DE_MARGEN.map(([u]) => u);
    expect([...umbrales].sort((a, b) => b - a)).toEqual(umbrales);
  });
});
