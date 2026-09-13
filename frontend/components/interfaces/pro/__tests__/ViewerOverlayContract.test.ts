import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const read = (name: string) =>
  readFileSync(resolve(process.cwd(), "components/interfaces/pro", name), "utf8");

describe("contrato de etiquetas de los visores", () => {
  const web3d = read("Web3DViewer.tsx");
  const molstar = read("AdvancedMolstarViewer.tsx");
  const shared = read("viewerOverlayStyles.ts");

  it("mantiene el cambio de visor estable en la esquina inferior derecha", () => {
    expect(shared).toContain("h-8");
    expect(shared).toContain("w-[124px]");
    expect(web3d).toContain('className="absolute bottom-3 right-3 z-10"');
    expect(molstar).toContain('className="pointer-events-auto absolute bottom-3 right-3 z-10"');
    expect(web3d).toContain("className={VIEWER_SWITCH_BUTTON_CLASS}");
    expect(molstar).toContain("className={VIEWER_SWITCH_BUTTON_CLASS}");
  });

  it("reserva la esquina superior derecha de Web3D para Opciones", () => {
    expect(web3d).toContain('className="absolute right-3 top-3 z-10"');
    expect(web3d).toContain("Opciones");
  });

  it("no monta el panel inferior izquierdo de MolStar cuando no hay información", () => {
    expect(molstar).toContain("(gridInfo || hotspots.length > 0)");
    expect(molstar).toContain("VIEWER_LABEL_PANEL_CLASS");
  });

  it("aísla nuestras etiquetas para que no atraviesen MolChat", () => {
    expect(web3d).toContain("relative isolate h-full");
    expect(molstar).toContain("relative isolate overflow-hidden");
    expect(web3d).not.toContain("z-[110]");
    expect(molstar).not.toContain("z-[100]");
  });
});
