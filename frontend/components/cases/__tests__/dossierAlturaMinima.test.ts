// =====================================================================
// Guardia: la vista previa del dossier no se colapsa con la altura de la ventana
// =====================================================================
//
// Medido en la cápsula de QA el 2026-11-11 con el export real: el <iframe> del dossier medía 504 px a 1440×900, 284 a 1280×800,
// 53 a 1024×768 y 16 a 1024×700, que es el mínimo que declara `tauri.conf.json`. Todo el cuerpo del visor es absoluto, así
// que su contenedor no tiene con qué crecer: tomaba la fracción de altura que le dejaba un reparto `minmax(0, 1.1fr)` y
// quedaba en nada.
//
// jsdom no calcula el layout, así que esta guardia es estática (como `reportViewerBoundary`): vigila las dos condiciones
// que lo impiden. La altura real la mide el export en la cápsula (`scripts/qa_sandbox`).

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

const COMPONENTS = join(__dirname, "..", "..");

function code(...parts: string[]): string {
  return readFileSync(join(COMPONENTS, ...parts), "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
}

/** El `className` del primer elemento cuyo className contiene `fragmento`. */
function claseQueContiene(fuente: string, fragmento: string): string | null {
  const m = new RegExp(`className="([^"]*${fragmento}[^"]*)"`).exec(fuente);
  return m ? m[1] : null;
}

/** `true` si la clase de la altura mínima del cuerpo está y no es cero. */
export function cuerpoTieneAlturaMinima(clase: string | null): boolean {
  return !!clase && /(^|\s)min-h-\[\d+(\.\d+)?(rem|px|vh|dvh)\]/.test(clase);
}

/** `true` si por debajo de `xl` el reparto de filas es por fracciones (lo que dejaba el visor en 16 px). */
export function repartePorFraccionesSinXl(clase: string | null): boolean {
  return !!clase && /(^|\s)grid-rows-\[[^\]]*fr[^\]]*\]/.test(clase);
}

describe("vista previa del dossier: altura mínima", () => {
  it("el cuerpo del visor tiene una altura mínima propia", () => {
    const visor = code("cases", "CaseDossierViewer.tsx");
    const clase = claseQueContiene(visor, "relative min-h-");
    expect(cuerpoTieneAlturaMinima(clase)).toBe(true);
  });

  it("por debajo de xl la página hace scroll y no reparte la altura por fracciones", () => {
    const vista = code("cases", "CaseReportView.tsx");
    const principal = claseQueContiene(vista, "flex h-full min-h-0 w-full flex-col");
    expect(principal).toMatch(/(^|\s)overflow-y-auto(\s|$)/);
    expect(principal).toMatch(/xl:overflow-hidden/);
    const rejilla = claseQueContiene(vista, "grid-cols-1");
    expect(repartePorFraccionesSinXl(rejilla)).toBe(false);
  });

  it("control negativo: el detector ve el reparto que dejaba el visor en 16 px", () => {
    const antes =
      "grid h-full min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1.1fr)_minmax(0,0.9fr)] gap-4 xl:grid-rows-1";
    expect(repartePorFraccionesSinXl(antes)).toBe(true);
    expect(cuerpoTieneAlturaMinima("relative min-h-0 flex-1 bg-surface-950")).toBe(false);
    expect(cuerpoTieneAlturaMinima("relative min-h-[28rem] flex-1 bg-surface-950")).toBe(true);
  });
});
