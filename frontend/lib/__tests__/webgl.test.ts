/**
 * La sonda de WebGL distingue TRES estados, no dos.
 *
 * El defecto que esto cierra: la versión anterior sólo preguntaba «¿se puede
 * crear un contexto?». Entre el sí y el no está el caso de una máquina virtual,
 * donde hay contexto pero lo dibuja el procesador. Medido en la misma máquina:
 *
 *     hardware   ANGLE (NVIDIA … D3D11)          Mol* listo en 1 072 ms
 *     software   ANGLE (… SwiftShader driver)    Mol* listo en 1 260 ms
 *
 * Las dos funcionan. Por eso el render por software NO se bloquea: se dice.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { comprobarWebGL, reiniciarComprobacionWebGL } from "../webgl";

const original = HTMLCanvasElement.prototype.getContext;

/** Un contexto de mentira que anuncia el renderer que se le pida. */
function contextoFalso(renderer: string | null) {
  return {
    getExtension: (nombre: string) => {
      if (nombre === "WEBGL_debug_renderer_info") {
        return renderer === null ? null : { UNMASKED_RENDERER_WEBGL: 37446 };
      }
      if (nombre === "WEBGL_lose_context") return { loseContext: () => {} };
      return null;
    },
    getParameter: () => renderer,
  };
}

function conRenderer(renderer: string | null): void {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => contextoFalso(renderer)) as never;
}

function sinContexto(): void {
  HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;
}

beforeEach(() => {
  reiniciarComprobacionWebGL();
});

afterEach(() => {
  HTMLCanvasElement.prototype.getContext = original;
  reiniciarComprobacionWebGL();
});

describe("comprobarWebGL", () => {
  it("sin contexto: no disponible y con un motivo que se puede leer", () => {
    sinContexto();
    const estado = comprobarWebGL();
    expect(estado.disponible).toBe(false);
    expect(estado.aceleracion).toBeNull();
    // El motivo es lo que sustituye al «bad weather» de la librería.
    expect(estado.motivo).toMatch(/máquina virtual/i);
  });

  it("reconoce el render por software SIN bloquearlo", () => {
    conRenderer("ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero)), SwiftShader driver)");
    const estado = comprobarWebGL();
    // Lo importante: disponible TRUE. Se avisa, no se impide.
    expect(estado.disponible).toBe(true);
    expect(estado.aceleracion).toBe("software");
    expect(estado.motivo).toBeNull();
  });

  it.each([
    ["llvmpipe (LLVM 15.0.7, 256 bits)", "llvmpipe de Mesa"],
    ["Microsoft Basic Render Driver", "el driver básico de Windows"],
    ["ANGLE (Software Adapter, Direct3D11)", "el adaptador por software de ANGLE"],
  ])("reconoce %s como software", (renderer) => {
    conRenderer(renderer);
    expect(comprobarWebGL().aceleracion).toBe("software");
  });

  it("una tarjeta de verdad se clasifica como hardware", () => {
    conRenderer("ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)");
    const estado = comprobarWebGL();
    expect(estado.disponible).toBe(true);
    expect(estado.aceleracion).toBe("hardware");
  });

  it("si el equipo no quiere identificarse, no se inventa una clasificación", () => {
    // Algunos equipos ocultan `WEBGL_debug_renderer_info` por privacidad. No
    // saber cómo se dibuja es un estado legítimo, no un fallo.
    conRenderer(null);
    const estado = comprobarWebGL();
    expect(estado.disponible).toBe(true);
    expect(estado.aceleracion).toBeNull();
    expect(estado.renderer).toBeNull();
  });

  it("un getContext que lanza no tumba la aplicación", () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => {
      throw new Error("contexto denegado");
    }) as never;
    const estado = comprobarWebGL();
    expect(estado.disponible).toBe(false);
    expect(estado.motivo).toContain("contexto denegado");
  });

  it("se memoriza: crear contextos de prueba consume GPU de verdad", () => {
    const espia = vi.fn(() => contextoFalso("NVIDIA"));
    HTMLCanvasElement.prototype.getContext = espia as never;
    comprobarWebGL();
    comprobarWebGL();
    comprobarWebGL();
    expect(espia).toHaveBeenCalledTimes(1);
  });
});
