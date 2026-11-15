/**
 * Mol* cuando el equipo no puede —o deja de poder— dibujar en 3D.
 *
 * Tres caminos, y ninguno puede acabar en un recuadro sin salida:
 *   · no consigue contexto al arrancar;
 *   · lo tenía y el equipo se lo quita a media sesión (el proceso de GPU se cae);
 *   · lo pierde y el navegador se lo devuelve: ahí no hay que hacer nada.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import AdvancedMolstarViewer, { ESPERA_DE_CONTEXTO_MS } from "../AdvancedMolstarViewer";
import { reiniciarComprobacionWebGL } from "../../../../lib/webgl";

const getContextOriginal = HTMLCanvasElement.prototype.getContext;
// Con la tanda entera en paralelo, el arranque asíncrono del visor puede pasar
// del segundo que `waitFor` espera por defecto.
const ESPERA = { timeout: 8000 };

/** Un visor de Mol* de mentira: crea su lienzo, como el de verdad. */
function molstarFalso(crear?: (contenedor: HTMLElement) => void, conLienzo3D = true) {
  const visor = {
    plugin: {
      // Mol* deja aquí su lienzo 3D cuando consigue contexto; sin contexto, no existe.
      ...(conLienzo3D ? { canvas3d: {} } : {}),
      layout: { events: { updated: { subscribe: () => ({ unsubscribe: () => {} }) } }, state: { isExpanded: false } },
      clear: async () => {},
      managers: { structure: { hierarchy: { current: { structures: [] } } }, camera: {} },
    },
    loadStructureFromData: async () => {},
    dispose: vi.fn(),
  };
  return {
    visor,
    molstar: {
      Viewer: {
        create: vi.fn(async (contenedor: HTMLElement) => {
          if (crear) crear(contenedor);
          else contenedor.appendChild(document.createElement("canvas"));
          return visor;
        }),
      },
    },
  };
}

beforeEach(() => {
  reiniciarComprobacionWebGL();
  // La hoja y el script de Mol* «ya están cargados»: el visor no los vuelve a pedir.
  for (const id of ["molstar-css", "molstar-js"]) {
    const marca = document.createElement("meta");
    marca.id = id;
    document.head.appendChild(marca);
  }
  // El equipo dice que tiene contexto (con tarjeta): lo que falla es Mol*, no la sonda.
  HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
    getExtension: (nombre: string) => (nombre === "WEBGL_debug_renderer_info" ? { UNMASKED_RENDERER_WEBGL: 1 } : nombre === "WEBGL_lose_context" ? { loseContext: () => {} } : null),
    getParameter: () => "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0, D3D11)",
  })) as never;
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  document.getElementById("molstar-css")?.remove();
  document.getElementById("molstar-js")?.remove();
  delete (window as { molstar?: unknown }).molstar;
  HTMLCanvasElement.prototype.getContext = getContextOriginal;
  reiniciarComprobacionWebGL();
});

describe("Mol* sin contexto 3D", () => {
  it("si no consigue contexto al arrancar, avisa a quien lo montó", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { molstar } = molstarFalso(() => { throw new Error("Could not create a WebGL rendering context"); });
    (window as { molstar?: unknown }).molstar = molstar;
    const alNoPoder = vi.fn();
    render(<AdvancedMolstarViewer proteinData="ATOM" onNoDisponible={alNoPoder} />);
    await waitFor(() => expect(alNoPoder).toHaveBeenCalledWith("sin-contexto"), ESPERA);
  });

  it("si Mol* se pinta su propio «WebGL does not seem to be available», también cuenta", async () => {
    const { molstar, visor } = molstarFalso((contenedor) => { contenedor.textContent = "WebGL does not seem to be available."; });
    (window as { molstar?: unknown }).molstar = molstar;
    const alNoPoder = vi.fn();
    render(<AdvancedMolstarViewer proteinData="ATOM" onNoDisponible={alNoPoder} />);
    await waitFor(() => expect(alNoPoder).toHaveBeenCalledWith("sin-contexto"), ESPERA);
    expect(visor.dispose).toHaveBeenCalled();
    // El texto de la librería no llega al usuario.
    expect(screen.queryByText(/does not seem to be available/)).toBeNull();
  });

  it("si Mol* vuelve sin lienzo 3D y AÚN no ha pintado su mensaje, no se da por listo", async () => {
    // El caso que la guarda del texto no veía: `create` resuelve, el contenedor
    // está vacío y el «WebGL does not seem to be available» llega un render
    // después. Reproducido en el export con un equipo que da contexto a la sonda
    // y se lo niega a Mol*: el usuario acababa viendo el mensaje de la librería.
    const { molstar, visor } = molstarFalso(() => {}, false);
    (window as { molstar?: unknown }).molstar = molstar;
    const alNoPoder = vi.fn();
    const cargar = vi.spyOn(visor, "loadStructureFromData");
    render(<AdvancedMolstarViewer proteinData={"ATOM  ".padEnd(80, " ")} onNoDisponible={alNoPoder} />);
    await waitFor(() => expect(alNoPoder).toHaveBeenCalledWith("sin-contexto"), ESPERA);
    expect(visor.dispose).toHaveBeenCalled();
    // Y no se le pide cargar estructuras a un visor que no puede dibujarlas.
    expect(cargar).not.toHaveBeenCalled();
  });

  it("si el fallo no es del 3D, también avisa: un recuadro de error no es una salida", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    (window as { molstar?: unknown }).molstar = {};
    const alNoPoder = vi.fn();
    render(<AdvancedMolstarViewer proteinData="ATOM" onNoDisponible={alNoPoder} />);
    await waitFor(() => expect(alNoPoder).toHaveBeenCalledWith("no-cargo"), ESPERA);
  });

  it("el aviso manda al visor ligero y el botón para abrirlo está en el propio aviso", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const { molstar } = molstarFalso(() => { throw new Error("Could not create a WebGL rendering context"); });
    (window as { molstar?: unknown }).molstar = molstar;
    const cambiar = vi.fn();
    render(<AdvancedMolstarViewer proteinData="ATOM" onSwitchViewer={cambiar} viewerLabel="Web3D" />);
    const boton = await screen.findByRole("button", { name: "Abrir el visor ligero" }, ESPERA);
    fireEvent.click(boton);
    expect(cambiar).toHaveBeenCalledTimes(1);
  });
});

describe("Mol* pierde el contexto con el visor abierto", () => {
  async function montar(alNoPoder: () => void) {
    const falso = molstarFalso();
    (window as { molstar?: unknown }).molstar = falso.molstar;
    const vista = render(<AdvancedMolstarViewer proteinData="ATOM" onNoDisponible={alNoPoder} onSwitchViewer={() => {}} />);
    await waitFor(() => expect(vista.container.querySelector("canvas")).not.toBeNull(), ESPERA);
    // Un respiro para que termine de quedar listo antes de congelar el reloj.
    await act(async () => { await Promise.resolve(); });
    return { ...falso, lienzo: vista.container.querySelector("canvas") as HTMLCanvasElement };
  }

  it("si el navegador no lo devuelve, lo dice y avisa", async () => {
    const alNoPoder = vi.fn();
    const { lienzo } = await montar(alNoPoder);
    vi.useFakeTimers();
    act(() => { lienzo.dispatchEvent(new Event("webglcontextlost")); });
    act(() => { vi.advanceTimersByTime(ESPERA_DE_CONTEXTO_MS - 1); });
    expect(alNoPoder).not.toHaveBeenCalled();
    act(() => { vi.advanceTimersByTime(1); });
    expect(alNoPoder).toHaveBeenCalledWith("contexto-perdido");
    expect(screen.getByRole("button", { name: "Abrir el visor ligero" })).toBeTruthy();
  });

  it("si lo devuelve a tiempo, no pasa nada: Mol* se reconstruye solo", async () => {
    const alNoPoder = vi.fn();
    const { lienzo } = await montar(alNoPoder);
    vi.useFakeTimers();
    act(() => { lienzo.dispatchEvent(new Event("webglcontextlost")); });
    act(() => { vi.advanceTimersByTime(1500); });
    act(() => { lienzo.dispatchEvent(new Event("webglcontextrestored")); });
    act(() => { vi.advanceTimersByTime(ESPERA_DE_CONTEXTO_MS * 3); });
    expect(alNoPoder).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Abrir el visor ligero" })).toBeNull();
  });

  it("al desmontar deja de vigilar: un aviso tardío no llega a un visor que ya no existe", async () => {
    const alNoPoder = vi.fn();
    const { lienzo } = await montar(alNoPoder);
    vi.useFakeTimers();
    act(() => { lienzo.dispatchEvent(new Event("webglcontextlost")); });
    cleanup();
    act(() => { vi.advanceTimersByTime(ESPERA_DE_CONTEXTO_MS * 2); });
    expect(alNoPoder).not.toHaveBeenCalled();
  });
});
