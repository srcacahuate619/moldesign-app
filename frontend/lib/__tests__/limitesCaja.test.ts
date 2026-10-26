// SOL-13. Los límites de la caja que la interfaz permite escribir tienen que
// ser los que el backend ejecuta. La interfaz recortaba el centro a ±100 Å y el
// lado a 50 Å mientras `preflight.py` admite ±10000 Å y 5–80 Å.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { CAJA_CENTRO_MAX_A, CAJA_LADO_MAX_A, CAJA_LADO_MIN_A } from "../limitesCaja";

const PREFLIGHT = resolve(__dirname, "..", "..", "..", "backend", "services", "docking", "preflight.py");

function constanteDelBackend(nombre: string): number {
  const fuente = readFileSync(PREFLIGHT, "utf-8");
  const m = new RegExp(`^${nombre}\\s*=\\s*([0-9.]+)\\s*$`, "m").exec(fuente);
  if (!m) throw new Error(`preflight.py ya no define ${nombre}`);
  return Number(m[1]);
}

describe("límites de la caja: interfaz = ejecución", () => {
  it.each([
    ["CAJA_LADO_MIN_A", CAJA_LADO_MIN_A],
    ["CAJA_LADO_MAX_A", CAJA_LADO_MAX_A],
    ["CAJA_CENTRO_MAX_A", CAJA_CENTRO_MAX_A],
  ])("%s coincide con preflight.py", (nombre, valor) => {
    expect(constanteDelBackend(nombre)).toBe(valor);
  });

  it("el guardián ve: una constante inexistente se declara, no se lee como 0", () => {
    expect(() => constanteDelBackend("CAJA_INEXISTENTE_A")).toThrow(/ya no define/);
  });

  it("el preflight usa las constantes y no literales sueltos", () => {
    const fuente = readFileSync(PREFLIGHT, "utf-8");
    expect(fuente).toContain("CAJA_LADO_MIN_A <= v <= CAJA_LADO_MAX_A");
    expect(fuente).toContain("abs(v) > CAJA_CENTRO_MAX_A");
    expect(fuente).not.toMatch(/abs\(v\) > 10000/);
  });
});
