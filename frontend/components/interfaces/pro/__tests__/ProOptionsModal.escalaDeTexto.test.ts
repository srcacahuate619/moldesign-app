/**
 * Escala de texto del diálogo de «Parámetros de la evaluación» (aprobada el 2026-10-07). Tres niveles:
 *
 *   16 px (`text-base`)  título del diálogo y de la ayuda
 *   14 px (`text-sm`)   encabezados de columna y de sección, nombres de opción, valores de entrada, botones
 *   12 px (`text-xs`)   descripciones, etiquetas de campo, insignias, chips, estados y avisos
 *
 * Antes había 10, 11, 12 y 14 px, y tres recetas distintas para el mismo nivel de encabezado. Esta
 * prueba fija la escala en el código: un tamaño nuevo fuera de ella es una decisión de diseño y tiene
 * que venir con un cambio aquí, no colarse en un componente.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const CARPETA = path.join(__dirname, "..");
const leer = (fichero: string) => readFileSync(path.join(CARPETA, fichero), "utf8");
const FUENTES = ["ProOptionsModal.tsx", "AyudaDelParametro.tsx"];
const ESCALA = new Set(["text-base", "text-sm", "text-xs"]);

describe("escala de texto del diálogo de parámetros", () => {
  it.each(FUENTES)("%s no usa tamaños arbitrarios (10 px, 11 px…)", (fichero) => {
    expect(leer(fichero)).not.toMatch(/text-\[\d+(?:\.\d+)?px\]/);
  });

  it.each(FUENTES)("%s sólo usa los tres niveles de la escala", (fichero) => {
    const usados = new Set(leer(fichero).match(/\btext-(?:xs|sm|base|lg|xl|2xl)\b/g) ?? []);
    for (const clase of usados) {
      expect(ESCALA.has(clase), `${clase} fuera de la escala`).toBe(true);
    }
  });

  it("el título del diálogo es el nivel 1 (16 px)", () => {
    expect(leer("ProOptionsModal.tsx")).toMatch(
      /<h2 id="pro-options-title" className="text-base /,
    );
  });

  it("los encabezados de sección tienen una sola receta", () => {
    const fuente = leer("ProOptionsModal.tsx");
    // Las dos recetas antiguas (sans-serif semibold y mono widest) y la variante `font-black`
    // ya no aparecen: los encabezados de columna y de sección comparten la misma.
    expect(fuente).not.toMatch(/font-semibold uppercase tracking-wider/);
    expect(fuente).not.toMatch(/tracking-widest/);
    expect(fuente).not.toMatch(/font-black/);
  });
});
