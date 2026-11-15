/**
 * El visor de respaldo: lo que se ve en Evaluación cuando el equipo no da WebGL.
 *
 * Antes era un recuadro negro con un aviso. Aquí se comprueba que dice por qué
 * está ahí, que dibuja, que responde al ratón y al teclado, y que no gasta nada
 * mientras no se toca.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import VisorSinWebGL from "../VisorSinWebGL";

const atomo = (serie: number, nombre: string, residuo: string, numero: number, x: number, y: number, z: number, elemento: string) =>
  `ATOM  ${String(serie).padStart(5)}  ${nombre.padEnd(3)} ${residuo} A${String(numero).padStart(4)}    `
  + `${x.toFixed(3).padStart(8)}${y.toFixed(3).padStart(8)}${z.toFixed(3).padStart(8)}  1.00 20.00          ${elemento.padStart(2)}`;

const RECEPTOR = [
  atomo(1, "CA", "ALA", 1, 0, 0, 0, "C"),
  atomo(2, "CA", "ASP", 2, 3.8, 0, 0, "C"),
  atomo(3, "CG", "ASP", 2, 3.8, -1.5, 0, "C"),
  atomo(4, "OD1", "ASP", 2, 3.8, -2.7, 0, "O"),
  atomo(5, "CA", "GLY", 3, 7.6, 0, 0, "C"),
].join("\n");

const POSE = [
  "ligando", "  prueba", "",
  "  2  1  0  0  0  0  0  0  0  0999 V2000",
  "    3.8000   -5.5000    0.0000 N   0  0  0  0  0  0  0  0  0  0  0  0",
  "    3.8000   -7.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0",
  "  1  2  1  0", "M  END", "$$$$", "",
].join("\n");

/** Un contexto 2D que apunta lo que se le pide, para saber si se pintó y cuánto. */
function lienzoFalso() {
  const llamadas = { stroke: 0, arc: 0, fillText: 0, clearRect: 0 };
  const ctx = {
    setTransform: () => {}, clearRect: () => { llamadas.clearRect += 1; }, beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
    stroke: () => { llamadas.stroke += 1; }, arc: () => { llamadas.arc += 1; }, fill: () => {},
    strokeText: () => {}, fillText: () => { llamadas.fillText += 1; },
    lineCap: "", lineJoin: "", font: "", textAlign: "", textBaseline: "", globalAlpha: 1, strokeStyle: "", fillStyle: "", lineWidth: 1,
  };
  return { ctx, llamadas };
}

const getContextOriginal = HTMLCanvasElement.prototype.getContext;
const anchoOriginal = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
const altoOriginal = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientHeight");
let pendientes: FrameRequestCallback[] = [];

/** Corre los fotogramas pedidos, como haría el navegador en el siguiente refresco. */
function pasarFotograma(): number {
  const ahora = pendientes;
  pendientes = [];
  ahora.forEach((dibujar) => dibujar(0));
  return ahora.length;
}

function conTamano(ancho: number, alto: number): void {
  Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => ancho });
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, get: () => alto });
}

beforeEach(() => {
  pendientes = [];
  vi.stubGlobal("requestAnimationFrame", (dibujar: FrameRequestCallback) => { pendientes.push(dibujar); return pendientes.length; });
  vi.stubGlobal("cancelAnimationFrame", () => {});
  conTamano(640, 480);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  HTMLCanvasElement.prototype.getContext = getContextOriginal;
  if (anchoOriginal) Object.defineProperty(HTMLElement.prototype, "clientWidth", anchoOriginal);
  if (altoOriginal) Object.defineProperty(HTMLElement.prototype, "clientHeight", altoOriginal);
});

describe("VisorSinWebGL", () => {
  it("dice por qué se está viendo y que la evaluación no depende de él", () => {
    const { ctx } = lienzoFalso();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    expect(screen.getByText("Vista simplificada")).toBeTruthy();
    expect(screen.getByText(/no ofrece 3D ni por tarjeta gráfica ni por software/)).toBeTruthy();
    expect(screen.getByText("Tu evaluación no se ve afectada.")).toBeTruthy();
    // El criterio del sitio se dice con su distancia: no se presenta como otra cosa.
    // (El separador decimal lo pone el idioma: «4.5» en es-MX, «4,5» en es-ES.)
    expect(screen.getByText(/residuos con algún átomo a 4[.,]5 Å o menos/)).toBeTruthy();
  });

  it("cuando lo que falló fueron los visores, no le echa la culpa al equipo", () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => lienzoFalso().ctx) as never;
    render(<VisorSinWebGL motivo="visor-fallo" proteinData={RECEPTOR} poseData={POSE} />);
    expect(screen.getByText(/Los visores 3D no pudieron dibujar en este equipo/)).toBeTruthy();
    expect(screen.queryByText(/no ofrece 3D ni por tarjeta/)).toBeNull();
  });

  it("pinta la pose, el sitio y las etiquetas en un lienzo 2D", () => {
    const { ctx, llamadas } = lienzoFalso();
    const getContext = vi.fn((_tipo: string) => ctx);
    HTMLCanvasElement.prototype.getContext = getContext as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    pasarFotograma();
    // Nunca pide WebGL: es justo lo que no hay.
    expect(getContext.mock.calls.length).toBeGreaterThan(0);
    expect(getContext.mock.calls.every(([tipo]) => tipo === "2d")).toBe(true);
    expect(llamadas.clearRect).toBeGreaterThan(0);
    expect(llamadas.stroke).toBeGreaterThan(0);
    expect(llamadas.arc).toBe(3); // dos átomos del ligando y el oxígeno del ASP
    expect(llamadas.fillText).toBe(1); // «ASP2»
    expect(screen.getByText("Ligando acoplado")).toBeTruthy();
    expect(screen.getByText("Residuos del sitio (1)")).toBeTruthy();
    expect(screen.getByText("Esqueleto del receptor")).toBeTruthy();
  });

  it("en reposo no pide ningún fotograma: no hay bucle de dibujo", () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => lienzoFalso().ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    pasarFotograma();
    expect(pasarFotograma()).toBe(0);
    expect(pasarFotograma()).toBe(0);
  });

  it("arrastrar gira, y por muchos movimientos que lleguen se pinta una vez por fotograma", () => {
    const { ctx, llamadas } = lienzoFalso();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    pasarFotograma();
    const antes = llamadas.clearRect;
    const lienzo = screen.getByRole("img");
    fireEvent.pointerDown(lienzo, { clientX: 100, clientY: 100, pointerId: 1 });
    for (let i = 1; i <= 10; i++) fireEvent.pointerMove(lienzo, { clientX: 100 + i * 5, clientY: 100, pointerId: 1 });
    fireEvent.pointerUp(lienzo, { pointerId: 1 });
    expect(pasarFotograma()).toBe(1);
    expect(llamadas.clearRect).toBe(antes + 1);
  });

  it("la explicación se recoge al empezar a mirar la estructura y vuelve con un clic", () => {
    // Abierta tapaba un tercio de la escena, justo donde queda la pose.
    HTMLCanvasElement.prototype.getContext = vi.fn(() => lienzoFalso().ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    expect(screen.getByText("Tu evaluación no se ve afectada.")).toBeTruthy();
    fireEvent.pointerDown(screen.getByRole("img"), { clientX: 10, clientY: 10, pointerId: 1 });
    expect(screen.queryByText("Tu evaluación no se ve afectada.")).toBeNull();
    // El rótulo sigue ahí: lo que se está viendo no deja de ser la vista simplificada.
    fireEvent.click(screen.getByRole("button", { name: /Vista simplificada/ }));
    expect(screen.getByText("Tu evaluación no se ve afectada.")).toBeTruthy();
  });

  it("sin pose dice que enseña el centro de la caja, con su distancia", () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => lienzoFalso().ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR}
      gridInfo={{ centerX: 3.8, centerY: 0, centerZ: 0, sizeX: 22.5, sizeY: 22.5, sizeZ: 22.5 }} />);
    expect(screen.getByText(/Todavía no hay pose: muestra los residuos a 8 Å o menos del centro de la caja/)).toBeTruthy();
    expect(screen.getByText("Residuos del sitio (3)")).toBeTruthy();
    expect(screen.getByText("Caja de búsqueda")).toBeTruthy();
  });

  it("se maneja con el teclado", () => {
    const { ctx, llamadas } = lienzoFalso();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    pasarFotograma();
    const antes = llamadas.clearRect;
    const lienzo = screen.getByRole("img");
    expect(lienzo.getAttribute("tabindex")).toBe("0");
    fireEvent.keyDown(lienzo, { key: "ArrowLeft" });
    pasarFotograma();
    fireEvent.keyDown(lienzo, { key: "+" });
    pasarFotograma();
    expect(llamadas.clearRect).toBe(antes + 2);
    // Una tecla que no es suya no repinta ni se la queda.
    fireEvent.keyDown(lienzo, { key: "a" });
    expect(pasarFotograma()).toBe(0);
  });

  it("quitar las etiquetas las quita del dibujo", () => {
    const { ctx, llamadas } = lienzoFalso();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    pasarFotograma();
    expect(llamadas.fillText).toBe(1);
    fireEvent.click(screen.getByRole("button", { name: "Etiquetas" }));
    pasarFotograma();
    expect(llamadas.fillText).toBe(1);
  });

  it("con la pestaña oculta (tamaño cero) no intenta pintar", () => {
    const { ctx, llamadas } = lienzoFalso();
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx) as never;
    conTamano(0, 0);
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    pasarFotograma();
    expect(llamadas.clearRect).toBe(0);
  });

  it("sin estructura lo dice, y no deja un lienzo vacío", () => {
    render(<VisorSinWebGL motivo="sin-webgl" />);
    expect(screen.getByText("Sin estructura para visualizar")).toBeTruthy();
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("si ni siquiera hay lienzo 2D, no lanza", () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => null) as never;
    render(<VisorSinWebGL motivo="sin-webgl" proteinData={RECEPTOR} poseData={POSE} />);
    expect(() => pasarFotograma()).not.toThrow();
  });

  it("ofrece volver a intentar el 3D sólo si alguien puede atenderlo", () => {
    HTMLCanvasElement.prototype.getContext = vi.fn(() => lienzoFalso().ctx) as never;
    const reintentar = vi.fn();
    const { unmount } = render(<VisorSinWebGL motivo="visor-fallo" proteinData={RECEPTOR} onReintentar3D={reintentar} />);
    fireEvent.click(screen.getByRole("button", { name: "Reintentar 3D" }));
    expect(reintentar).toHaveBeenCalledTimes(1);
    unmount();
    render(<VisorSinWebGL motivo="visor-fallo" proteinData={RECEPTOR} />);
    expect(screen.queryByRole("button", { name: "Reintentar 3D" })).toBeNull();
  });
});
