import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const sourcePath = resolve(process.cwd(), "components/interfaces/pro/ProEvaluation.tsx");
const source = readFileSync(sourcePath, "utf8");

describe("layout de los controles estructurales de Evaluación", () => {
  it("mantiene receptor y SMILES simétricos y extiende el sistema a las dos columnas", () => {
    expect(source).toContain("h-14 w-full border border-zinc-800");
    expect(source).toContain("lg:col-span-2");

    const receptorIndex = source.indexOf("h-14 w-full border border-zinc-800");
    const systemIndex = source.indexOf("lg:col-span-2");
    expect(receptorIndex).toBeGreaterThan(-1);
    expect(systemIndex).toBeGreaterThan(receptorIndex);
  });
  it("no monta Molstar ni Web3D cuando WebGL no esta disponible", () => {
    const gateIndex = source.indexOf('webglDisponible === false ?');
    const fallbackIndex = source.indexOf('<AvisoSinWebGL />', gateIndex);
    const molstarIndex = source.indexOf('<AdvancedMolstarViewer', gateIndex);
    const web3dIndex = source.indexOf('<Web3DViewer', gateIndex);

    expect(source).toContain('setWebglDisponible(comprobarWebGL().disponible)');
    expect(gateIndex).toBeGreaterThan(-1);
    expect(fallbackIndex).toBeGreaterThan(gateIndex);
    expect(molstarIndex).toBeGreaterThan(fallbackIndex);
    expect(web3dIndex).toBeGreaterThan(molstarIndex);
  });
});
