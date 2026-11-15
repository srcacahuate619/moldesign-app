/**
 * Un solo visor de Mol* que pasa de un caso al siguiente sin enseñarle a nadie lo del caso anterior.
 *
 * El visor es falso: un plugin que guarda qué estructuras tiene y cuándo dibuja. Lo que se comprueba es el reparto —
 * quién lo tiene, en qué orden se vacía y se carga, cuándo se ve—, que es lo que puede filtrar un caso a otro.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { cuentaDeVisores, olvidarResidente, pedirMolstar } from "../molstarResidente";

type Falso = ReturnType<typeof visorFalso>;

function visorFalso() {
  const estructuras: string[] = [];
  const dibujos = new Set<() => void>();
  const visor = {
    estructuras,
    plugin: {
      canvas3d: {
        didDraw: { subscribe: (f: () => void) => { f(); dibujos.add(f); return { unsubscribe: () => dibujos.delete(f) }; } },
        requestDraw: () => { queueMicrotask(() => dibujos.forEach((f) => f())); },
        handleResize: vi.fn(),
      },
      animationLoop: { isAnimating: true, start: vi.fn(function (this: { isAnimating: boolean }) { this.isAnimating = true; }), stop: vi.fn(function (this: { isAnimating: boolean }) { this.isAnimating = false; }) },
      clear: vi.fn(async () => { await Promise.resolve(); estructuras.length = 0; }),
    },
    handleResize: vi.fn(),
    dispose: vi.fn(),
    async cargar(nombre: string) { await Promise.resolve(); estructuras.push(nombre); },
  };
  return visor;
}

let creados: Falso[] = [];
const crear = async () => { const v = visorFalso(); creados.push(v); return v; };
const destino = () => { const d = document.createElement("div"); document.body.appendChild(d); return d; };
const caja = () => document.querySelector<HTMLElement>("[data-molstar-residente]");
const asentar = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); await new Promise((r) => setTimeout(r, 0)); for (let i = 0; i < 20; i++) await Promise.resolve(); };

beforeEach(() => { olvidarResidente(); creados = []; document.body.innerHTML = ""; });
afterEach(() => { vi.useRealTimers(); });

describe("un visor para toda la sesión", () => {
  it("el segundo caso recibe el mismo visor: no se crea otro ni se destruye el primero", async () => {
    const a = await pedirMolstar(destino(), crear);
    a.devolver();
    const b = await pedirMolstar(destino(), crear);
    expect(creados).toHaveLength(1);
    expect(b.visor).toBe(a.visor);
    expect(a.visor.dispose).not.toHaveBeenCalled();
    expect(cuentaDeVisores).toEqual({ creados: 1, descartados: 0 });
  });

  it("al devolverlo sale del documento y deja de dibujar", async () => {
    const d = destino();
    const a = await pedirMolstar(d, crear);
    expect(d.contains(caja())).toBe(true);
    a.devolver();
    expect(caja()).toBeNull();
    await asentar();
    expect(a.visor.plugin.animationLoop.stop).toHaveBeenCalled();
    const b = await pedirMolstar(destino(), crear);
    expect(b.visor.plugin.animationLoop.isAnimating).toBe(true);
  });

  it("el caso siguiente nunca ve las estructuras del anterior", async () => {
    const a = await pedirMolstar(destino(), crear);
    await a.cargar(async (v) => { await v.cargar("receptor de A"); });
    expect(a.visor.estructuras).toEqual(["receptor de A"]);
    a.devolver();
    const b = await pedirMolstar(destino(), crear);
    // Mientras el vaciado no ha dibujado, el visor está oculto.
    expect(caja()?.style.visibility).toBe("hidden");
    await asentar();
    expect(b.visor.estructuras).toEqual([]);
    expect(caja()?.style.visibility).toBe("");
    await b.cargar(async (v) => { await v.cargar("receptor de B"); });
    expect(b.visor.estructuras).toEqual(["receptor de B"]);
  });

  it("una carga que se queda atrás no sigue añadiendo estructuras al caso siguiente", async () => {
    const a = await pedirMolstar(destino(), crear);
    let soltar!: () => void;
    const bloqueo = new Promise<void>((r) => { soltar = r; });
    const lenta = a.cargar(async (v, vigente) => {
      await v.cargar("receptor de A");
      await bloqueo; // Mol* tarda en leer el PDB grande
      if (!vigente()) return;
      await v.cargar("ligando de A");
    });
    await asentar();
    a.devolver();
    const b = await pedirMolstar(destino(), crear);
    const deB = b.cargar(async (v) => { await v.cargar("receptor de B"); });
    soltar();
    await lenta;
    await deB;
    expect(b.visor.estructuras).toEqual(["receptor de B"]);
  });

  it("dos cargas seguidas del mismo caso no se cruzan: queda sólo la última", async () => {
    const a = await pedirMolstar(destino(), crear);
    const primera = a.cargar(async (v, vigente) => { await v.cargar("receptor 1"); if (vigente()) await v.cargar("ligando 1"); });
    const segunda = a.cargar(async (v) => { await v.cargar("receptor 2"); });
    await Promise.all([primera, segunda]);
    expect(a.visor.estructuras).toEqual(["receptor 2"]);
  });

  it("devolver dos veces, o devolver un préstamo viejo, no le quita el visor a quien lo tiene ahora", async () => {
    const a = await pedirMolstar(destino(), crear);
    a.devolver();
    const d = destino();
    const b = await pedirMolstar(d, crear);
    a.devolver();
    expect(d.contains(caja())).toBe(true);
    await b.cargar(async (v) => { await v.cargar("receptor de B"); });
    expect(b.visor.estructuras).toEqual(["receptor de B"]);
  });

  it("un visor descartado (sin contexto 3D) se destruye y el siguiente recibe uno nuevo", async () => {
    const a = await pedirMolstar(destino(), crear);
    a.descartar();
    expect(a.visor.dispose).toHaveBeenCalledTimes(1);
    expect(caja()).toBeNull();
    const b = await pedirMolstar(destino(), crear);
    expect(b.visor).not.toBe(a.visor);
    expect(cuentaDeVisores).toEqual({ creados: 2, descartados: 1 });
  });

  it("si crearlo falla no queda nada a medias, y el siguiente intento lo crea", async () => {
    const d = destino();
    await expect(pedirMolstar(d, async () => { throw new Error("WebGL"); })).rejects.toThrow("WebGL");
    expect(d.childElementCount).toBe(0);
    const b = await pedirMolstar(destino(), crear);
    expect(b.visor).toBe(creados[0]);
  });

  it("dos peticiones mientras se crea comparten el mismo visor", async () => {
    const [a, b] = await Promise.all([pedirMolstar(destino(), crear), pedirMolstar(destino(), crear)]);
    expect(creados).toHaveLength(1);
    expect(a.visor).toBe(b.visor);
  });
});
