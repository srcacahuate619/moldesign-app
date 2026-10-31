import { describe, expect, it } from "vitest";
import { FrontendError, frontendMessage, presentError } from "../frontendError";
import { TRANSLATIONS, interpolar } from "../../context/LanguageContext";
describe.each(["es", "en"] as const)("errores locales en %s", locale => {
  const t = (key: string, values?: Readonly<Record<string, string | number>>) => interpolar(TRANSLATIONS[locale][key] ?? key, values);
  it("presenta la clave local, preservando el mensaje base y la serialización", () => {
    const error = new FrontendError(frontendMessage("ca_receptor_label_single", { pdbId: "8T69", chain: "A" }));
    const bytes = JSON.stringify(error);
    expect(error.message).toBe("8T69 · cadena A");
    expect(presentError(error,t)).toBe(locale === "es" ? "8T69 · cadena A" : "8T69 · chain A");
    expect(JSON.stringify(error)).toBe(bytes);
  });
  it("no traduce ni reconoce cadenas externas, aunque se parezcan a una frase local", () => {
    for (const external of ["8T69 · cadena A", "Error backend: no disponible", "Rust: permiso denegado"]) {
      expect(presentError(new Error(external),t)).toBe(external);
    }
  });
});
