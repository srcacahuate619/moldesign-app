// Traducciones automáticas que se fueron de la mano.
//
// EL FALLO. Dos claves heredadas de la traducción automática: el «?» que se
// enseña cuando falta un dato salía en inglés como una línea de «♪ Oh, oh,
// oh…» (en MolChat y en tres paneles de Evaluación), y «llama-cpp-python» como
// «cpp-python flame». Ninguna prueba lo veía porque las dos cadenas eran
// distintas del castellano, que es lo único que se comprobaba.
import { describe, expect, it } from "vitest";

import { TRANSLATIONS } from "../../context/LanguageContext";

const es = TRANSLATIONS.es as Record<string, string>;
const en = TRANSLATIONS.en as Record<string, string>;

describe("el inglés no tiene disparates de la traducción automática", () => {
  it("ningún texto lleva notas musicales", () => {
    const conNotas = Object.entries(en).filter(([, v]) => typeof v === "string" && /[♪♫]/.test(v));
    expect(conNotas.map(([k]) => k)).toEqual([]);
  });

  it("un signo suelto se queda como está", () => {
    const cambiados = Object.keys(es).filter(
      (k) => typeof es[k] === "string" && /^[?¿!¡…·—–-]+$/.test(es[k].trim()) && en[k] !== undefined && en[k].trim() !== es[k].trim(),
    );
    expect(cambiados).toEqual([]);
  });

  it("llama (el programa) no se traduce", () => {
    const traducida = Object.keys(es).filter(
      (k) => typeof es[k] === "string" && /\bllama[.-]/i.test(es[k]) && en[k] !== undefined && !/llama/i.test(en[k]),
    );
    expect(traducida).toEqual([]);
  });
});
