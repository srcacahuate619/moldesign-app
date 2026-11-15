import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const sourcePath = resolve(process.cwd(), "components/interfaces/pro/ProEvaluation.tsx");
const source = readFileSync(sourcePath, "utf8");
const configurationCss = readFileSync(
  resolve(process.cwd(), "components/evaluation/ConfigurationPresentation.module.css"),
  "utf8",
);

describe("layout de los controles estructurales de Evaluación", () => {
  it("mantiene receptor y SMILES simétricos y extiende el sistema a las dos columnas", () => {
    expect(source).toContain("h-14 w-full border border-zinc-800");
    // El sistema completo (ConfigurationSystem) va dentro de la rejilla de dos columnas,
    // después del receptor, y su CSS lo extiende a todas las columnas.
    const receptorIndex = source.indexOf("h-14 w-full border border-zinc-800");
    const systemIndex = source.indexOf("{!reviewingResult && systemPanel}");
    expect(receptorIndex).toBeGreaterThan(-1);
    expect(systemIndex).toBeGreaterThan(receptorIndex);
    expect(configurationCss).toMatch(/\.system\s*\{[^}]*grid-column:\s*1\s*\/\s*-1/);
  });
  it("no monta Molstar ni Web3D cuando WebGL no esta disponible", () => {
    // Sin WebGL la primera rama es el visor de lienzo 2D; ningún motor 3D va antes.
    // Antes esa rama era sólo un aviso: se podía evaluar, pero no mirar la pose.
    const gateIndex = source.indexOf('webglDisponible === false ?');
    const fallbackIndex = source.indexOf('<VisorSinWebGL', gateIndex);
    const molstarIndex = source.indexOf('<AdvancedMolstarViewer', gateIndex);
    const web3dIndex = source.indexOf('<Web3DViewer', gateIndex);

    expect(source).toContain('setWebglDisponible(comprobarWebGL().disponible)');
    expect(gateIndex).toBeGreaterThan(-1);
    expect(fallbackIndex).toBeGreaterThan(gateIndex);
    expect(molstarIndex).toBeGreaterThan(fallbackIndex);
    expect(web3dIndex).toBeGreaterThan(molstarIndex);
    expect(source.slice(gateIndex, molstarIndex)).toContain('motivo="sin-webgl"');
  });

  it("el visor de respaldo no depende de descargar otro trozo de la aplicación", () => {
    // Es a lo que se cae cuando lo demás falla: si fuera `dynamic(...)`, un fallo
    // al cargar ese trozo dejaría la columna vacía justo cuando hace falta.
    expect(source).toContain('import VisorSinWebGL from "./VisorSinWebGL";');
    expect(source).not.toMatch(/VisorSinWebGL\s*=\s*dynamic/);
  });

  it("cada motor 3D va dentro de su frontera, y un fallo abre el siguiente visor", () => {
    for (const motor of ["molstar", "web3d"]) {
      expect(source).toContain(`<FronteraDelVisor key="${motor}" onFallo={() => alFallarElVisor("${motor}")}>`);
      expect(source).toContain(`onNoDisponible={() => alFallarElVisor("${motor}")}`);
    }
    // Antes de elegir sustituto se vuelve a medir el equipo: lo memorizado al
    // abrir la pestaña puede no valer si el proceso de GPU se ha caído.
    const fallo = source.slice(source.indexOf("const alFallarElVisor"), source.indexOf("const reintentarVisor3D"));
    expect(fallo.indexOf("reiniciarComprobacionWebGL()")).toBeGreaterThan(-1);
    expect(fallo.indexOf("reiniciarComprobacionWebGL()")).toBeLessThan(fallo.indexOf("siguienteVisor("));
  });
});
