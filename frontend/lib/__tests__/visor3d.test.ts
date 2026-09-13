import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";
import { liberarVisor3D } from "../visor3d";

// ─────────────────────────────────────────────────────────────────────────
// Ningun visor 3Dmol se destruia nunca.
//
// `MoleculeViewer3D` reutiliza a proposito la instancia entre cambios de datos,
// asi que su efecto de carga no puede destruirla; y no habia ningun otro que lo
// hiciera. `MoleculeTechViewer` tenia la limpieza SOLO en la rama del `else`
// —la que espera a que 3Dmol cargue—, asi que en el camino normal no devolvia
// nada, y encima dejaba `spin("y", 0.015)` pidiendo fotogramas para siempre.
//
// En la VM sin GPU, WebView2 cae al renderizador por software: el proceso subia
// de ~180 MB a mas de 600 MB. Y hay un limite que el tamano no deja ver:
// Chromium mantiene ~16 contextos WebGL vivos y al pasarse PIERDE el mas
// antiguo, dejando en negro un visor que el usuario estaba mirando.
// ─────────────────────────────────────────────────────────────────────────

function contenedorConLienzo(gl: unknown) {
  const lienzo = { getContext: vi.fn(() => gl) };
  return {
    querySelector: vi.fn(() => lienzo),
    innerHTML: "<canvas></canvas>",
  } as unknown as HTMLElement;
}

describe("liberarVisor3D", () => {
  it("para la animacion ANTES de tocar la escena", () => {
    const orden: string[] = [];
    const visor = {
      spin: vi.fn(() => void orden.push("spin")),
      removeAllModels: vi.fn(() => void orden.push("modelos")),
    };
    liberarVisor3D(contenedorConLienzo(null), visor);
    expect(visor.spin).toHaveBeenCalledWith(false);
    expect(orden[0]).toBe("spin");
  });

  it("suelta geometria, superficies, formas y etiquetas", () => {
    const visor = {
      removeAllModels: vi.fn(),
      removeAllSurfaces: vi.fn(),
      removeAllShapes: vi.fn(),
      removeAllLabels: vi.fn(),
    };
    liberarVisor3D(contenedorConLienzo(null), visor);
    expect(visor.removeAllModels).toHaveBeenCalled();
    expect(visor.removeAllSurfaces).toHaveBeenCalled();
    expect(visor.removeAllShapes).toHaveBeenCalled();
    expect(visor.removeAllLabels).toHaveBeenCalled();
  });

  it("pierde el contexto WebGL explicitamente", () => {
    // Es el recurso racionado: sin esto sobrevive hasta que el recolector de
    // Chromium se digna, y son solo ~16.
    const loseContext = vi.fn();
    const gl = { getExtension: vi.fn(() => ({ loseContext })) };
    liberarVisor3D(contenedorConLienzo(gl), { removeAllModels: vi.fn() });
    expect(gl.getExtension).toHaveBeenCalledWith("WEBGL_lose_context");
    expect(loseContext).toHaveBeenCalled();
  });

  it("vacia el contenedor para no retener el lienzo", () => {
    const contenedor = contenedorConLienzo(null);
    liberarVisor3D(contenedor, { removeAllModels: vi.fn() });
    expect(contenedor.innerHTML).toBe("");
  });

  it("no explota con un visor nulo ni a medio inicializar", () => {
    expect(() => liberarVisor3D(null, null)).not.toThrow();
    expect(() => liberarVisor3D(contenedorConLienzo(null), {})).not.toThrow();
  });

  it("un paso que falla no impide los siguientes", () => {
    // Abandonar a la primera excepcion dejaria vivo justo lo que se quiere soltar.
    const contenedor = contenedorConLienzo(null);
    const visor = {
      spin: vi.fn(() => {
        throw new Error("no giraba");
      }),
      removeAllModels: vi.fn(() => {
        throw new Error("escena rota");
      }),
    };
    expect(() => liberarVisor3D(contenedor, visor)).not.toThrow();
    expect(contenedor.innerHTML).toBe("");
  });
});

describe("los dos componentes que crean un visor lo liberan", () => {
  const componentes = [
    "components/MoleculeViewer3D.tsx",
    "components/MoleculeTechViewer.tsx",
  ];

  it.each(componentes)("%s llama a liberarVisor3D al desmontar", (ruta) => {
    const fuente = readFileSync(resolve(process.cwd(), ruta), "utf8");
    expect(fuente).toContain("createViewer");
    expect(fuente).toContain("liberarVisor3D");
  });

  it("MoleculeTechViewer devuelve limpieza en TODOS los caminos", () => {
    // El defecto exacto: el `return` vivia dentro del `else`, asi que con
    // 3Dmol ya cargado por `layout.tsx` el efecto no devolvia nada.
    const fuente = readFileSync(
      resolve(process.cwd(), "components/MoleculeTechViewer.tsx"),
      "utf8",
    );
    expect(fuente).not.toContain("return () => clearInterval(check);");
    expect(fuente).toContain("if (check) clearInterval(check);");
  });
});
