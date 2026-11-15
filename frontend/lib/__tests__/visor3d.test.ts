import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";
import { liberarVisor3D, pdbDelBolsillo, pintarVisor3D, visorSinContexto } from "../visor3d";

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

// ─────────────────────────────────────────────────────────────────────────
// La estructura REAL de 3Dmol (medida sobre `public/3Dmol-min.js` en un navegador, 2026-11-07).
//
// El contexto WebGL de un visor vive en `visor.renderer.getContext()`, un `OffscreenCanvas`; el `<canvas>` que se ve en
// la página sólo tiene un contexto `bitmaprenderer`, así que `lienzo.getContext("webgl")` devuelve `null` aunque el
// visor esté dibujando. La prueba de arriba («pierde el contexto WebGL explicitamente») simula un lienzo que SÍ lo tiene,
// y por eso pasó durante meses con una limpieza que en la práctica no soltaba nada.
// ─────────────────────────────────────────────────────────────────────────
describe("liberarVisor3D con la estructura real de 3Dmol", () => {
  function visor3DmolReal() {
    const loseContext = vi.fn();
    const gl = { getExtension: vi.fn(() => ({ loseContext })) };
    const visor = {
      renderer: { getContext: vi.fn(() => gl), isLost: vi.fn(() => false) },
      divwatcher: { disconnect: vi.fn() },
      intwatcher: { disconnect: vi.fn() },
      container: undefined as unknown,
      removeAllModels: vi.fn(),
    };
    return { visor, gl, loseContext };
  }

  it("pierde el contexto del renderizador aunque el lienzo visible no tenga ninguno", () => {
    const { visor, gl, loseContext } = visor3DmolReal();
    const contenedor = contenedorConLienzo(null); // `getContext("webgl")` -> null, como el <canvas> de 3Dmol
    liberarVisor3D(contenedor, visor);
    expect(gl.getExtension).toHaveBeenCalledWith("WEBGL_lose_context");
    expect(loseContext).toHaveBeenCalledTimes(1);
  });

  it("desconecta los observadores que 3Dmol no desconecta nunca", () => {
    const { visor } = visor3DmolReal();
    liberarVisor3D(contenedorConLienzo(null), visor);
    expect(visor.divwatcher.disconnect).toHaveBeenCalled();
    expect(visor.intwatcher.disconnect).toHaveBeenCalled();
  });

  it("deja el visor mirando a un contenedor suelto y sin tamaño, para que su listener de `resize` no lo reviva", () => {
    // 3Dmol no quita su listener de `window`: con el contexto perdido y un contenedor con tamaño, `resize()`
    // reconstruye el renderizador, y si otro visor tomó ese contenedor, sobre SU lienzo.
    const { visor } = visor3DmolReal();
    const real = document.createElement("div");
    visor.container = real;
    liberarVisor3D(contenedorConLienzo(null), visor);
    expect(visor.container).not.toBe(real);
    expect((visor.container as HTMLElement).isConnected).toBe(false);
    expect((visor.container as HTMLElement).offsetWidth).toBe(0);
  });

  it("si el renderizador no da contexto, sigue probando con el lienzo (otras builds de 3Dmol)", () => {
    const loseContext = vi.fn();
    const gl = { getExtension: vi.fn(() => ({ loseContext })) };
    const visor = { renderer: { getContext: vi.fn(() => null) }, removeAllModels: vi.fn() };
    liberarVisor3D(contenedorConLienzo(gl), visor);
    expect(loseContext).toHaveBeenCalled();
  });

  it("un renderizador que lanza no impide vaciar el contenedor", () => {
    const contenedor = contenedorConLienzo(null);
    const visor = { renderer: { getContext: vi.fn(() => { throw new Error("sin contexto"); }) } };
    expect(() => liberarVisor3D(contenedor, visor)).not.toThrow();
    expect(contenedor.innerHTML).toBe("");
  });
});

describe("pintarVisor3D", () => {
  it("dibuja un visor con contexto, y uno sin renderizador conocido", () => {
    const conContexto = { renderer: { isLost: () => false }, render: vi.fn(), resize: vi.fn() };
    expect(pintarVisor3D(conContexto)).toBe(true);
    expect(conContexto.render).toHaveBeenCalledTimes(1);
    expect(conContexto.resize).not.toHaveBeenCalled();

    const sinRenderer = { render: vi.fn() };
    expect(pintarVisor3D(sinRenderer)).toBe(true);
    expect(sinRenderer.render).toHaveBeenCalled();
  });

  it("con el contexto perdido intenta la reconstrucción propia de 3Dmol y, si no vuelve, NO dibuja", () => {
    // Dibujar sobre un contexto perdido hace que 3Dmol escriba «could not initialize shader» en cada fotograma.
    const visor = { renderer: { isLost: () => true }, render: vi.fn(), resize: vi.fn() };
    expect(pintarVisor3D(visor)).toBe(false);
    expect(visor.resize).toHaveBeenCalledTimes(1);
    expect(visor.render).not.toHaveBeenCalled();
  });

  it("si `resize()` devuelve el contexto, dibuja", () => {
    let perdido = true;
    const visor = {
      renderer: { isLost: () => perdido },
      resize: vi.fn(() => { perdido = false; }),
      render: vi.fn(),
    };
    expect(pintarVisor3D(visor)).toBe(true);
    expect(visor.render).toHaveBeenCalledTimes(1);
  });

  it("un fallo con el contexto perdido es consecuencia de eso; con contexto, es un defecto y se propaga", () => {
    let perdido = false;
    const visor = { renderer: { isLost: () => perdido }, render: vi.fn(() => { throw new Error("escena rota"); }), resize: vi.fn() };
    expect(() => pintarVisor3D(visor)).toThrow("escena rota");
    visor.render.mockImplementation(() => { perdido = true; throw new Error("contexto perdido a medias"); });
    expect(pintarVisor3D(visor)).toBe(false);
  });

  it("sin visor no hay nada que dibujar", () => {
    expect(pintarVisor3D(null)).toBe(false);
  });
});

describe("visorSinContexto", () => {
  it("sólo dice que sí cuando el renderizador lo afirma", () => {
    expect(visorSinContexto({ renderer: { isLost: () => true } })).toBe(true);
    expect(visorSinContexto({ renderer: { isLost: () => false } })).toBe(false);
    expect(visorSinContexto({})).toBe(false);
    expect(visorSinContexto(null)).toBe(false);
    expect(visorSinContexto({ renderer: { isLost: () => { throw new Error("x"); } } })).toBe(false);
  });
});

describe("pdbDelBolsillo", () => {
  const PDB = [
    "ATOM      1  N   SER A   1       0.000   0.000   0.000  1.00  0.00           N",
    "ATOM      2  OG  SER A   1       1.000   0.000   0.000  1.00  0.00           O",
    "ATOM      3  N   GLY A   2       5.000   0.000   0.000  1.00  0.00           N",
    "ATOM      4  N   SER B   1      10.000   0.000   0.000  1.00  0.00           N",
    "HETATM    5  O   HOH A   1      20.000   0.000   0.000  1.00  0.00           O",
    "TER",
  ].join("\n");

  it("deja sólo los átomos ATOM de los residuos pedidos y cierra el modelo", () => {
    const texto = pdbDelBolsillo(PDB, new Set(["A:1"]));
    expect(texto.split("\n").filter((l) => l.startsWith("ATOM"))).toHaveLength(2);
    expect(texto).toContain("OG  SER A   1");
    expect(texto).not.toContain("GLY A   2");
    expect(texto.endsWith("\nEND\n")).toBe(true);
  });

  it("no mezcla cadenas ni cuenta los hetero-átomos que comparten número de residuo", () => {
    expect(pdbDelBolsillo(PDB, new Set(["B:1"]))).toContain("SER B   1");
    expect(pdbDelBolsillo(PDB, new Set(["B:1"]))).not.toContain("SER A   1");
    expect(pdbDelBolsillo(PDB, new Set(["A:1"]))).not.toContain("HOH");
  });

  it("si ningún residuo pedido está en la proteína, no hay modelo que añadir", () => {
    expect(pdbDelBolsillo(PDB, new Set(["C:9"]))).toBe("");
    expect(pdbDelBolsillo(PDB, new Set())).toBe("");
    expect(pdbDelBolsillo("no es un PDB", new Set(["A:1"]))).toBe("");
  });

  it("al cambiar la proteína lee la nueva, no la anterior", () => {
    const otra = "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N";
    expect(pdbDelBolsillo(PDB, new Set(["A:1"]))).toContain("SER A   1");
    expect(pdbDelBolsillo(otra, new Set(["A:1"]))).toContain("ALA A   1");
    expect(pdbDelBolsillo(otra, new Set(["A:1"]))).not.toContain("SER");
    expect(pdbDelBolsillo(PDB, new Set(["A:1"]))).toContain("SER A   1");
  });
});

// ─────────────────────────────────────────────────────────────────────────
// Lo que el visor da por hecho de 3Dmol, comprobado sobre el archivo que SE EMPAQUETA (`public/3Dmol-min.js`).
//
// Nada de esto está en la API documentada de 3Dmol: son piezas internas que se midieron en un navegador el 2026-11-07.
// Si una actualización las cambia, estas pruebas fallan aquí y no en la GPU de un investigador.
// ─────────────────────────────────────────────────────────────────────────
describe("la build de 3Dmol que se empaqueta tiene lo que el visor da por hecho", () => {
  const fuente3Dmol = readFileSync(resolve(process.cwd(), "public/3Dmol-min.js"), "utf8");

  const piezas: Array<[string, RegExp]> = [
    // Cambiar de pose reemplaza modelos: `removeModel` quita por id y recorta SÓLO el final de la lista.
    ["removeModel quita por id y recorta sólo el final", /removeModel\(\w+\)\{.{0,200}delete this\.models\[\w+\.getID\(\)\].{0,120}this\.models\.pop\(\)/s],
    // El id de un modelo nuevo es el largo de la lista (por eso se quita en orden inverso).
    ["addModel numera con el largo de la lista", /new \w+\(this\.models\.length,/],
    // Liberar y vigilar el contexto: viven en el renderizador, no en el <canvas> visible.
    ["el renderizador expone getContext()", /getContext\(\)\{return this\._gl\}/],
    ["el renderizador expone isLost()", /isLost\(\)\{return null==this\._gl\|\|this\._gl\.isContextLost\(\)\}/],
    ["el contexto vive en un OffscreenCanvas", /OffscreenCanvas/],
    // 3Dmol se reconstruye solo al redimensionar con el contexto perdido: de eso depende `pintarVisor3D`.
    ["resize() reconstruye el renderizador si el contexto se perdió", /resize\(\)\{.{0,200}this\.renderer\.isLost\(\)&&this\.WIDTH>0&&this\.HEIGHT>0/s],
    // Los observadores que `liberarVisor3D` desconecta.
    ["deja un ResizeObserver en divwatcher", /this\.divwatcher=new window\.ResizeObserver/],
    ["deja un IntersectionObserver en intwatcher", /this\.intwatcher=new window\.IntersectionObserver/],
  ];

  it.each(piezas)("%s", (_nombre, patron) => {
    expect(fuente3Dmol).toMatch(patron);
  });

  it("el guardián distingue: los mismos patrones NO casan sobre un archivo que no los tiene", () => {
    const otro = "function removeModel(m){ return m }; class Renderer { getContext(){ return null } }";
    for (const [, patron] of piezas) expect(otro).not.toMatch(patron);
  });
});
