import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const read = (name: string) =>
  readFileSync(resolve(process.cwd(), "components/interfaces/pro", name), "utf8");

describe("contrato de etiquetas de los visores", () => {
  const web3d = read("Web3DViewer.tsx");
  const molstar = read("AdvancedMolstarViewer.tsx");
  const shared = read("viewerOverlayStyles.ts");

  it("mantiene el cambio de visor arriba a la izquierda, fuera del alcance de la burbuja de MolChat", () => {
    // Vivía abajo a la derecha, que es donde se queda fija la burbuja de MolChat: la tapaba («Ver MolStar»,
    // «Ver Web3D» y «Reintentar 3D»). Medido en una captura a 1440×900 (2026-11-10).
    const sinWebgl = read("VisorSinWebGL.tsx");
    expect(shared).toContain("h-8");
    expect(shared).toContain("w-[124px]");
    expect(web3d).toContain('className="absolute left-3 top-3 z-10 flex');
    expect(molstar).toContain('className="pointer-events-auto absolute left-3 top-3 z-10 flex items-center gap-2"');
    for (const fuente of [web3d, molstar, sinWebgl]) {
      expect(fuente).toContain("className={VIEWER_SWITCH_BUTTON_CLASS}");
      expect(fuente).not.toContain("absolute bottom-3 right-3");
    }
  });

  it("deja a Mol* dibujar por software, como promete comprobarWebGL", () => {
    expect(molstar).toContain("allowMajorPerformanceCaveat: true");
  });

  it("Web3D sólo dibuja cuando algo cambia", () => {
    // Con el bucle por defecto repintaba 60 veces por segundo una escena quieta.
    // Medido en el export (2026-11-09), en reposo: 46 % de un núcleo con tarjeta
    // gráfica y entre 9 y 11 núcleos enteros sin ella, los mismos que usa Vina.
    expect(web3d).toContain('frameloop="demand"');
    // Informar la cámara en cada fotograma era lo que obligaba a tener el bucle.
    expect(web3d).not.toMatch(/useFrame\(\(\) => \{\s*const now = performance\.now\(\)/);
    expect(web3d).toContain("onChange={alMoverLaCamara.current}");
  });

  it("los dos motores vigilan que el equipo no les quite el contexto", () => {
    for (const fuente of [web3d, molstar]) {
      expect(fuente).toContain('addEventListener("webglcontextlost"');
      expect(fuente).toContain('addEventListener("webglcontextrestored"');
      expect(fuente).toContain('removeEventListener("webglcontextlost"');
    }
  });

  it("Web3D crea él mismo su renderizador para enterarse si three no consigue contexto", () => {
    // R3F lo construye dentro de una promesa: la excepción de three no pasa por
    // React y ninguna frontera la ve. Sin esto el visor quedaba en un lienzo vacío.
    const inicio = web3d.indexOf("gl={(porDefecto) =>");
    expect(inicio).toBeGreaterThan(-1);
    const creacion = web3d.slice(inicio, web3d.indexOf('frameloop="demand"', inicio));
    expect(creacion).toContain("new THREE.WebGLRenderer(");
    expect(creacion).toMatch(/catch \(fallo\) \{[\s\S]*avisarNoDisponible\.current\?\.\(\)[\s\S]*throw fallo;/);
  });

  it("Mol* no se da por listo sin su lienzo 3D", () => {
    // Su mensaje «WebGL does not seem to be available» llega un render después de
    // que `create` resuelva: mirar sólo el texto dejaba pasar el fallo.
    expect(molstar).toContain("const sinLienzo3D = !viewer?.plugin?.canvas3d;");
    expect(molstar).toContain("if (seQuejoDeWebGL || sinLienzo3D) {");
  });

  it("reserva la esquina superior derecha de Web3D para Opciones y la pantalla completa", () => {
    expect(web3d).toContain('className="absolute right-3 top-3 z-10 flex items-start gap-2"');
    expect(web3d).toContain('t(pantalla.activa ? "pn_w3d_salir_pantalla_completa" : "pn_w3d_pantalla_completa")');
    expect(web3d).toContain('t("ev_opciones")');
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
