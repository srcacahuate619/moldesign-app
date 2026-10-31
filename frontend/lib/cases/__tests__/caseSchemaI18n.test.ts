import { describe, expect, it } from "vitest";
import { TRADUCCIONES_POR_SUPERFICIE } from "@/context/traducciones";
import { caseSchema } from "@/context/traducciones/caseSchema";
import { presentError, type Translate } from "@/lib/frontendError";
import { CaseError, presentCaseErrorDetail } from "../types";
import { parseCaseManifest, sanitizeFolderName } from "../schema";

const traducir = (idioma: "es" | "en"): Translate => (key, values) =>
  (TRADUCCIONES_POR_SUPERFICIE[idioma][key] ?? key).replace(/\{(\w+)\}/g,
    (original, name: string) => values && name in values ? String(values[name]) : original);

function capturar(run: () => unknown): CaseError {
  try { run(); } catch (error) {
    if (error instanceof CaseError) return error;
    throw error;
  }
  throw new Error("La prueba esperaba un CaseError");
}

describe("diagnósticos del esquema de casos", () => {
  it("conserva en inglés los parámetros de todos los diagnósticos", () => {
    const parametros = (texto: string) => [...texto.matchAll(/\{(v\d+)\}/g)].map((m) => m[1]).sort();
    expect(Object.keys(caseSchema.en).sort()).toEqual(Object.keys(caseSchema.es).sort());
    for (const clave of Object.keys(caseSchema.es)) {
      expect(parametros(caseSchema.en[clave]), clave).toEqual(parametros(caseSchema.es[clave]));
    }
  });

  it("traduce el mensaje y el detalle sin perder el campo ni el valor recibido", () => {
    const error = capturar(() => parseCaseManifest({ schemaVersion: 7, name: 42 }, "ruta/hipótesis"));
    expect(presentError(error, traducir("en"))).toContain("id");
    expect(presentError(error, traducir("en"))).toMatch(/manifest|case/i);
    expect(presentCaseErrorDetail(error, traducir("en"))).toContain("id");
    expect(presentCaseErrorDetail(error, traducir("en"))).toContain("ruta/hipótesis");
    expect(presentCaseErrorDetail(error, traducir("en"))).toMatch(/received|must/i);
    expect(error.message).toMatch(/manifiesto|caso/i);
  });

  it("conserva la descripción del valor y los identificadores en el detalle", () => {
    const error = capturar(() => parseCaseManifest([]));
    expect(presentCaseErrorDetail(error, traducir("en"))).toMatch(/array/i);
    expect(presentError(error, traducir("en"))).toContain("case.json");
  });

  it("traduce los nombres reservados sin modificar el nombre recibido", () => {
    const error = capturar(() => sanitizeFolderName("CON"));
    expect(presentError(error, traducir("en"))).toContain("CON");
    expect(presentError(error, traducir("en"))).toMatch(/reserved/i);
    expect(presentCaseErrorDetail(error, traducir("en"))).toContain("PRN");
  });

  it("no modifica mensajes externos ni detalles que no estén estructurados", () => {
    const error = new CaseError("IO_ERROR", "Fallo de Rust ajeno", "Detalle externo: dato del usuario");
    expect(presentError(error, traducir("en"))).toBe("Fallo de Rust ajeno");
    expect(presentCaseErrorDetail(error, traducir("en"))).toBe("Detalle externo: dato del usuario");
  });
});
