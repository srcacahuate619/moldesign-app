import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { TRANSLATIONS } from "../../context/LanguageContext";

/**
 * El inglés de la interfaz es AMERICANO (decisión del propietario, 2026-10-04).
 *
 * Medido: el mismo diccionario mezclaba «centre» (Opciones) y «center» (otros paneles), «Catalogue (380)» en la
 * cabecera del catálogo, «Licences», «cancelled», «Minimisation»… y dos textos llegaron con una «đ»
 * donde debía ir «π» («cation-π», «S-π»).
 *
 * La lista cubre lo que ya apareció y las formas británicas más comunes; ampliarla es añadir una palabra.
 */
const BRITANICAS = [
  "centre", "centres", "catalogue", "catalogues", "licence", "licences", "authorised", "initialise", "analyse",
  "minimise", "minimises", "minimised", "minimisation", "optimise", "optimised", "optimisation", "recognised",
  "summarise", "summarises", "judgement", "labelled", "cancelled", "sulphur", "towards", "artefact", "artefacts",
  "favour", "colour", "colours", "behaviour", "normalise", "normalised", "organise", "visualise", "customise",
  "quantise", "quantisation", "serialise", "serialised", "serialisation", "prioritise", "prioritises", "prioritisation",
  "grey", "whilst", "dialogue", "programme", "modelling", "analysed", "neighbour", "neighbours", "metre",
];
const RE_BRITANICA = new RegExp(`\\b(${BRITANICAS.join("|")})\\b`, "i");
const RE_PREFIJO = /\bhaemat/i;
const MALA_TRADUCCION = /\b(earrings|healing)\b|^it['’]s$/i;
const ESPANOL = /[¿¡ñáéíóúÁÉÍÓÚÑđð]/;

describe("inglés americano en los diccionarios", () => {
  it("rechaza los falsos amigos medidos, con controles positivos y negativos", () => {
    expect(Object.entries(TRANSLATIONS.en).filter(([, value]) => MALA_TRADUCCION.test(value.trim()))).toEqual([]);
    for (const value of ["Earrings:", "Healing", "It's", "It’s"]) expect(MALA_TRADUCCION.test(value)).toBe(true);
    for (const value of ["Pending:", "Curation", "en", "Is", "It's downloading...", "It's because"]) expect(MALA_TRADUCCION.test(value)).toBe(false);
    expect(TRANSLATIONS.en.auto_711741f4bb14).toBe("Pending:");
    expect(TRANSLATIONS.en.auto_e8ce83629e9c).toBe("Curation");
    expect(TRANSLATIONS.en.auto_09cd68a2a77b).toBe("en");
    expect(TRANSLATIONS.en.auto_c4bbdea3891b).toBe("Is");
    expect(TRANSLATIONS.es.auto_711741f4bb14).toBe("Pendientes:");
    expect(TRANSLATIONS.es.auto_e8ce83629e9c).toBe("Curación");
    expect(TRANSLATIONS.es.auto_09cd68a2a77b).toBe("es");
    expect(TRANSLATIONS.es.auto_c4bbdea3891b).toBe("Es");
  });
  it("ningún texto inglés usa una grafía británica", () => {
    const infractores = Object.entries(TRANSLATIONS.en)
      .filter(([, valor]) => RE_BRITANICA.test(valor) || RE_PREFIJO.test(valor))
      .map(([clave, valor]) => `${clave}: ${valor}`);
    expect(infractores, infractores.join("\n")).toEqual([]);
  });

  it("ningún texto inglés lleva caracteres propios del español ni corruptos", () => {
    const infractores = Object.entries(TRANSLATIONS.en)
      .filter(([, valor]) => ESPANOL.test(valor))
      .map(([clave, valor]) => `${clave}: ${valor}`);
    expect(infractores, infractores.join("\n")).toEqual([]);
  });

  it("el inglés escrito dentro de la página de Preparación (fuera de los diccionarios) tampoco", () => {
    // Los identificadores del contrato de la API entre comillas («"cancelled"») no son texto de interfaz.
    const codigo = readFileSync(resolve(process.cwd(), "app/preparacion/page.tsx"), "utf8").replace(/(["'])cancelled\1/g, "");
    expect(RE_BRITANICA.test(codigo) || RE_PREFIJO.test(codigo)).toBe(false);
  });

  it("control positivo: las dos claves corruptas dicen «π» y las nuevas grafías están", () => {
    expect(TRANSLATIONS.en.auto_20974a2a67a6).toContain("cation-π");
    expect(TRANSLATIONS.en.auto_84d405785c17).toContain("S-π");
    expect(TRANSLATIONS.en.auto_84d405785c17).toMatch(/^Sulfur/);
    expect(TRANSLATIONS.en.lo_estado_cancelada).toBe("Canceled");
  });

  it("el guardián demuestra que ve: caza cada forma británica y no se queja de la americana", () => {
    for (const malo of ["Grid centre", "the Catalogue", "Licences", "Haemato-brain", "was cancelled", "Sulphur bond", "Quantisation", "quantise", "serialise", "serialised", "serialisation", "prioritise", "prioritises", "prioritisation"]) {
      expect(RE_BRITANICA.test(malo) || RE_PREFIJO.test(malo), malo).toBe(true);
    }
    for (const bueno of ["Grid center", "the Catalog", "Licenses", "Hemato-brain", "was canceled", "cancellation", "Sulfur bond", "Quantization", "quantize", "serialize", "serialized", "serialization", "prioritize", "prioritizes", "prioritization"]) {
      expect(RE_BRITANICA.test(bueno) || RE_PREFIJO.test(bueno), bueno).toBe(false);
    }
    expect(ESPANOL.test("cation-đ")).toBe(true);
    expect(ESPANOL.test("cation-π")).toBe(false);
  });
});
