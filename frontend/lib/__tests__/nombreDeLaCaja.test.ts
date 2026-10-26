import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { TRANSLATIONS } from "../../context/LanguageContext";

/**
 * La caja donde Vina busca tiene UN nombre en la interfaz: «Caja de búsqueda» / «Search box».
 *
 * Medido el 2026-10-03: en una misma pantalla se llamaba «Caja de acoplamiento» (visor), «Caja de
 * búsqueda» (preflight), «Caja de trabajo» (Preparación) y «grid box» (Opciones). Decisión del propietario
 * (2026-10-04): «Caja de búsqueda» en toda la interfaz, y traducida al inglés (no «grid box»).
 *
 * La Fase 6 del plan unifica también los textos del backend que genera el dossier y el preflight, incluidos
 * los rótulos «caja de búsqueda efectiva»; la instantánea española y los goldens se regeneran una sola vez.
 */
const VIEJOS = /grid box|caja de acoplamiento|docking box|caja de trabajo|caja de docking|caja efectiva/i;

describe("nombre de la caja de búsqueda en la interfaz", () => {
  it("ningún texto de los diccionarios, en español ni en inglés, usa un nombre antiguo", () => {
    const infractores: string[] = [];
    for (const idioma of ["es", "en"] as const) {
      for (const [clave, valor] of Object.entries(TRANSLATIONS[idioma])) {
        if (VIEJOS.test(valor)) infractores.push(`${idioma}.${clave}: ${valor}`);
      }
    }
    expect(infractores, infractores.join("\n")).toEqual([]);
  });

  it("control positivo: el nombre nuevo sí está, y distinto en cada idioma", () => {
    expect(TRANSLATIONS.es.pr_viewer_grid_box).toBe("Caja de búsqueda");
    expect(TRANSLATIONS.en.pr_viewer_grid_box).toBe("Search box");
    expect(TRANSLATIONS.es.op_centro_grid).toMatch(/caja de búsqueda/i);
    expect(TRANSLATIONS.en.op_centro_grid).toMatch(/search box/i);
  });

  it("los textos escritos en el código, sin diccionario, tampoco lo usan", () => {
    for (const ruta of ["lib/sitioDelReceptor.ts", "app/preparacion/page.tsx"]) {
      const codigo = readFileSync(resolve(process.cwd(), ruta), "utf8");
      expect(VIEJOS.test(codigo), `${ruta} dice un nombre antiguo de la caja`).toBe(false);
    }
  });

  it("el guardián demuestra que ve: caza cada nombre antiguo y no se queja del nuevo", () => {
    for (const viejo of ["Grid box", "grid box center", "Caja de acoplamiento", "Docking box", "Caja de trabajo", "la caja de docking", "caja efectiva"]) {
      expect(VIEJOS.test(viejo), viejo).toBe(true);
    }
    for (const bueno of ["Caja de búsqueda", "Search box", "caja de búsqueda efectiva"]) {
      expect(VIEJOS.test(bueno), bueno).toBe(false);
    }
  });
});
