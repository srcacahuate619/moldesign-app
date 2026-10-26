// =====================================================================
// MOLDEX-UX-008 — qué afirma la ficha, y sobre qué red
// =====================================================================
//
// El lenguaje del producto era disciplinado donde se firma y mudo donde se
// muestra. `CertificationModal` declara que el registro «prueba integridad y
// precedencia […] No demuestra que la pose sea válida ni que la conclusión
// científica sea correcta», y el PDF dice que «acredita integridad y fecha, no
// descubrimiento ni validez científica». La ficha —la superficie que el
// investigador ve todo el tiempo— no decía ninguna de las dos cosas: una
// insignia, un encabezado «Evidencia Digital» y un enlace con `cluster=devnet`
// escrito a mano.

import { describe, expect, it } from "vitest";

import {
  ALCANCE_DEL_SELLO,
  esRedDePruebas,
  urlDelExplorador,
} from "../moldex";

describe("la red del sello se declara, no se codifica a mano", () => {
  it("reconoce devnet como red de pruebas", () => {
    expect(esRedDePruebas("devnet")).toBe(true);
    expect(esRedDePruebas("DEVNET")).toBe(true);
    expect(esRedDePruebas("testnet")).toBe(true);
  });

  it("no marca mainnet como red de pruebas", () => {
    expect(esRedDePruebas("mainnet")).toBe(false);
  });

  it("ante una red desconocida no afirma que sea de producción", () => {
    // No saber en qué red se selló no puede leerse como «red buena».
    expect(esRedDePruebas("unknown")).toBe(true);
    expect(esRedDePruebas("")).toBe(true);
    expect(esRedDePruebas(null)).toBe(true);
  });

  it("construye el enlace del explorador con la red real", () => {
    expect(urlDelExplorador("firma-xyz", "devnet")).toBe(
      "https://explorer.solana.com/tx/firma-xyz?cluster=devnet",
    );
    // En mainnet el explorador no lleva parámetro de cluster.
    expect(urlDelExplorador("firma-xyz", "mainnet")).toBe(
      "https://explorer.solana.com/tx/firma-xyz",
    );
  });

  it("escapa la firma en la URL", () => {
    expect(urlDelExplorador("a/b?c", "mainnet")).toBe(
      "https://explorer.solana.com/tx/a%2Fb%3Fc",
    );
  });
});

describe("el alcance del sello se dice en la ficha", () => {
  it("declara integridad y fecha, y niega validez científica", () => {
    expect(ALCANCE_DEL_SELLO).toMatch(/integridad/i);
    expect(ALCANCE_DEL_SELLO).toMatch(/fecha|precedencia/i);
    expect(ALCANCE_DEL_SELLO).toMatch(/no demuestra|no acredita|no valida/i);
  });

  it("nombra sólo los campos que el memo registra (SCI-A-006)", () => {
    expect(ALCANCE_DEL_SELLO).not.toMatch(/acredita integridad/i);
    expect(ALCANCE_DEL_SELLO).toMatch(/hash del SMILES/);
    expect(ALCANCE_DEL_SELLO).toMatch(/no identifica la revisión/i);
  });

  it("es el texto que la ficha muestra en castellano", async () => {
    const { moldex } = await import("../../context/traducciones/moldex");
    expect(ALCANCE_DEL_SELLO).toBe(moldex.es.mx_alcance_registro);
  });

  it("no promete validación experimental", () => {
    expect(ALCANCE_DEL_SELLO).not.toMatch(/valida(do|ción) experimental(?!\w)/i);
  });
});

describe("la ficha no presenta un ρ suelto como calibración (SCI-A-005)", () => {
  it("sin estado de calibración, o con los ceros por defecto, dice «sin calibrar»", async () => {
    const { calibracionDeLaFicha } = await import("../moldex");
    expect(calibracionDeLaFicha(null)).toEqual({ medida: false });
    expect(calibracionDeLaFicha({})).toEqual({ medida: false });
    expect(calibracionDeLaFicha({ calibracion: { nivel: "curado_estructural", respaldo: null } })).toEqual({ medida: false });
  });

  it("un «calibrado» sin n o con IC ilegible tampoco es una medida", async () => {
    const { calibracionDeLaFicha } = await import("../moldex");
    expect(calibracionDeLaFicha({ calibracion: { nivel: "calibrado", respaldo: null } })).toEqual({ medida: false });
    expect(calibracionDeLaFicha({ calibracion: { nivel: "calibrado", respaldo: { rho: 0.6, ic95: [0.3, NaN], n: 40, panel: "P" } } })).toEqual({ medida: false });
    expect(calibracionDeLaFicha({ calibracion: { nivel: "calibrado", respaldo: { rho: 0.6, ic95: [0.3, 0.8], n: 0, panel: "P" } } })).toEqual({ medida: false });
  });

  it("con la medida, da ρ, IC y n", async () => {
    const { calibracionDeLaFicha } = await import("../moldex");
    expect(calibracionDeLaFicha({ calibracion: { nivel: "calibrado", respaldo: { rho: 0.62, ic95: [0.31, 0.8], n: 48, panel: "P" } } }))
      .toEqual({ medida: true, rho: "0.62", a: "0.31", b: "0.80", n: 48 });
  });

  it("las dos frases tienen castellano e inglés", async () => {
    const { moldex } = await import("../../context/traducciones/moldex");
    for (const idioma of ["es", "en"] as const) {
      expect(moldex[idioma].mx_calibracion_medida).toContain("{n}");
      expect(moldex[idioma].mx_calibracion_sin_medida).toBeTruthy();
      expect(moldex[idioma].mx_correlacion_benchmark).not.toMatch(/benchmark/i);
    }
  });
});

describe("hotspots y origen de la afinidad (SCI-A-010, SCI-A-011)", () => {
  it("no evaluado no se convierte en cero; una lista vacía sí es un cero", async () => {
    const { hotspotsTocados } = await import("../moldex");
    expect(hotspotsTocados(null)).toBeNull();
    expect(hotspotsTocados(undefined)).toBeNull();
    expect(hotspotsTocados("no-json")).toBeNull();
    expect(hotspotsTocados([])).toEqual([]);
    expect(hotspotsTocados("[]")).toEqual([]);
    expect(hotspotsTocados('["A:1"]')).toEqual(["A:1"]);
  });

  it("las etiquetas nuevas existen en los dos idiomas", async () => {
    const { moldex } = await import("../../context/traducciones/moldex");
    for (const idioma of ["es", "en"] as const) {
      expect(moldex[idioma].mx_hits_no_evaluado).toBeTruthy();
      expect(moldex[idioma].mx_afinidad_heredada).toMatch(/no acreditado|not attested/);
      expect(moldex[idioma].mx_afinidad_heredada).not.toMatch(/Vina/);
    }
  });
});
