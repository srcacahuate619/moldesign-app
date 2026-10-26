import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { TRANSLATIONS } from "../../context/LanguageContext";

/**
 * «Opciones» nombraba tres cosas distintas, y la raíz era UNA clave compartida (`ev_opciones`): el
 * botón de la corrida, el desplegable de visualización del visor 3D y el título del menú de la cabecera.
 *
 * Decisión del propietario (2026-10-04): el diálogo de la corrida pasó a «Parámetros de la corrida»
 * («Run settings»). Decisión del propietario (2026-10-07): ahora se llama «Parámetros de la evaluación»
 * («Evaluation parameters»). «Opciones» queda para el menú de la cabecera. El desplegable del visor sigue
 * con `ev_opciones` (lo fija ViewerOverlayContract); es una cuestión aparte.
 */
const leer = (ruta: string) => readFileSync(resolve(process.cwd(), ruta), "utf8");

describe("«Opciones» ya no nombra el diálogo de la evaluación", () => {
  it("el botón de la evaluación y su diálogo dicen «Parámetros de la evaluación» / «Evaluation parameters»", () => {
    expect(TRANSLATIONS.es.ev_parametros_corrida).toBe("Parámetros de la evaluación");
    expect(TRANSLATIONS.en.ev_parametros_corrida).toBe("Evaluation parameters");
    expect(TRANSLATIONS.es.op_titulo).toBe(TRANSLATIONS.es.ev_parametros_corrida);
    expect(TRANSLATIONS.en.op_titulo).toBe(TRANSLATIONS.en.ev_parametros_corrida);
    expect(TRANSLATIONS.es.op_opciones_avanzadas).toBe("Parámetros avanzados");
    expect(TRANSLATIONS.en.op_opciones_avanzadas).toBe("Advanced parameters");
  });

  it("el botón de ProEvaluation usa la clave nueva y no la compartida", () => {
    const codigo = leer("components/interfaces/pro/ProEvaluation.tsx");
    expect(codigo).toContain('t("ev_parametros_corrida")');
    expect(codigo).not.toContain('t("ev_opciones")');
  });

  it("control positivo: el menú de la cabecera conserva «Opciones»", () => {
    expect(leer("components/ui/OptionsMenu.tsx")).toContain('t("ev_opciones")');
    expect(TRANSLATIONS.es.ev_opciones).toBe("Opciones");
    expect(TRANSLATIONS.en.ev_opciones).toBe("Options");
  });

  it("el título del diálogo y el de la cabecera ya no coinciden en ningún idioma", () => {
    for (const idioma of ["es", "en"] as const) {
      expect(TRANSLATIONS[idioma].op_titulo).not.toBe(TRANSLATIONS[idioma].ev_opciones);
      expect(TRANSLATIONS[idioma].op_titulo).not.toMatch(/opciones|options/i);
    }
  });
});
