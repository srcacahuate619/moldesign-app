import { describe, expect, it } from "vitest";

import { siguienteVisor, type Motor3D } from "../cadenaDeVisores";

describe("qué visor se abre cuando uno no puede dibujar", () => {
  it("si Mol* falla se prueba el visor ligero, y al revés", () => {
    expect(siguienteVisor("molstar", new Set<Motor3D>(["molstar"]))).toBe("web3d");
    expect(siguienteVisor("web3d", new Set<Motor3D>(["web3d"]))).toBe("molstar");
  });

  it("si los dos han fallado se va a la vista simplificada: no se alterna entre dos visores rotos", () => {
    const fallidos = new Set<Motor3D>(["molstar", "web3d"]);
    expect(siguienteVisor("molstar", fallidos)).toBe("simple");
    expect(siguienteVisor("web3d", fallidos)).toBe("simple");
  });
});
