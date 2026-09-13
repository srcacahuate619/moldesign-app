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

  it("no promete validación experimental", () => {
    expect(ALCANCE_DEL_SELLO).not.toMatch(/valida(do|ción) experimental(?!\w)/i);
  });
});
