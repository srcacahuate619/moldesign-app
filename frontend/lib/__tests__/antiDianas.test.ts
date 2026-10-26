import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { antiDianasParaEnviar } from "../antiDianas";
describe("selección efectiva de anti-dianas", () => {
  it("no envía una guardada no disponible, no seleccionable o desconocida y no duplica ids", () => {
    const targets = [ { pdb_id: "OK", name: "A", category: "F" }, { pdb_id: "NO", name: "B", category: "F", disponible: false }, { pdb_id: "DIS", name: "C", category: "F", seleccionable: false } ];
    expect(antiDianasParaEnviar(targets, ["OK", "NO", "DIS", "UNKNOWN", "OK"])).toEqual(["OK"]);
    expect(antiDianasParaEnviar(targets, [])).toEqual([]);
    expect(antiDianasParaEnviar(null, ["OK"])).toEqual([]);
  });
  it("la estimación y el envío usan el mismo recuento efectivo y ambos paneles comparten selector", () => {
    const source = readFileSync(resolve(process.cwd(), "components/interfaces/pro/ProEvaluation.tsx"), "utf8");
    expect(source).toContain("antiTargets={advancedOpts.enableSelectivity ? effectiveAntiTargets.length : 0}");
    expect(source).toContain("pro_anti_targets: effectiveAntiTargets");
    for (const name of ["ProOptionsModal", "ProConfigPanel"]) expect(readFileSync(resolve(process.cwd(), `components/interfaces/pro/${name}.tsx`), "utf8")).toContain("<AntiDianasSelector");
  });
});
