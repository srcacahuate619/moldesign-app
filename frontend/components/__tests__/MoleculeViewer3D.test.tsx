// =====================================================================
// El visor secundario tampoco debe pedir un contexto que no existe
// =====================================================================
//
// EL FALLO. Evaluación ya no monta Mol* ni Web3D sin comprobar antes que el
// equipo puede crear un contexto WebGL, pero `MoleculeViewer3D` —el visor de
// 3Dmol que usan Moldex, la comparación de moléculas y el diálogo de poses—
// llamaba a `$3Dmol.createViewer` sin preguntar nada.
//
// En la máquina virtual sin GPU virtualizada eso no da un error legible: 3Dmol
// falla al construir su renderizador, `modelsLoaded` nunca pasa a true, y lo que
// queda en pantalla es el spinner girando indefinidamente sobre un recuadro
// vacío con los controles «Surface», «Charges», «Interactions» y «Hotspots»
// encima. El investigador ve una aplicación colgada y no tiene forma de saber lo
// único que importa: que el docking, las métricas y las descargas ya están
// hechos y no dependen del visor.
//
// La prueba es conductual: se fuerza `getContext` a devolver `null` —que es lo
// que hace de verdad un WebView sin aceleración— y se comprueba sobre el
// componente montado que `createViewer` no llega a llamarse. `window.$3Dmol` es
// un doble, así que la librería real nunca se carga.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { MoleculeViewer3D } from "../MoleculeViewer3D";
import { reiniciarComprobacionWebGL } from "../../lib/webgl";

// Una pose mínima pero por encima del umbral de 10 caracteres que el componente
// usa para decidir que hay algo que dibujar.
const POSE_SDF = [
  "ligando",
  "  MolDesign",
  "",
  "  1  0  0  0  0  0            999 V2000",
  "    0.0000    0.0000    0.0000 C   0  0",
  "M  END",
  "$$$$",
].join("\n");

const original = HTMLCanvasElement.prototype.getContext;

/** Deja el equipo con o sin aceleración 3D, como lo ve `comprobarWebGL`. */
function equipoConWebGL(disponible: boolean): void {
  HTMLCanvasElement.prototype.getContext = ((): unknown =>
    disponible ? { getExtension: () => null } : null) as typeof original;
  // La comprobación se memoriza por sesión: sin esto, el primer test fijaría
  // el resultado para todos los demás.
  reiniciarComprobacionWebGL();
}

function dobleDe3Dmol() {
  const visor = {
    clear: vi.fn(),
    addModel: vi.fn(),
    removeAllSurfaces: vi.fn(),
    removeAllShapes: vi.fn(),
    removeAllModels: vi.fn(),
    removeAllLabels: vi.fn(),
    setStyle: vi.fn(),
    addStyle: vi.fn(),
    addCylinder: vi.fn(),
    addSurface: vi.fn(),
    setClickable: vi.fn(),
    getModel: vi.fn((_index: number): { selectedAtoms: () => any[] } | null => null),
    zoomTo: vi.fn(),
    zoom: vi.fn(),
    render: vi.fn(),
    resize: vi.fn(),
    spin: vi.fn(),
  };
  const createViewer = vi.fn(() => visor);
  (window as unknown as { $3Dmol?: unknown }).$3Dmol = {
    createViewer,
    SurfaceType: { VDW: 1 },
  };
  return { visor, createViewer };
}

// jsdom no implementa `matchMedia`, y el componente la consulta para decidir si
// está en un dispositivo táctil. Se repone aquí —no en el setup global— porque
// esto es una carencia del entorno de prueba, no del producto: en el WebView
// existe siempre. Escritorio, que es el caso que interesa.
const matchMediaOriginal = (window as unknown as { matchMedia?: unknown }).matchMedia;

beforeEach(() => {
  (window as unknown as { matchMedia: unknown }).matchMedia = (consulta: string) => ({
    matches: false,
    media: consulta,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    onchange: null,
    dispatchEvent: () => false,
  });
  reiniciarComprobacionWebGL();
});

afterEach(() => {
  (window as unknown as { matchMedia?: unknown }).matchMedia = matchMediaOriginal;
  HTMLCanvasElement.prototype.getContext = original;
  delete (window as unknown as { $3Dmol?: unknown }).$3Dmol;
  reiniciarComprobacionWebGL();
});

describe("MoleculeViewer3D sin aceleración 3D", () => {
  it("no intenta crear el contexto: `createViewer` no llega a llamarse", () => {
    equipoConWebGL(false);
    const { createViewer } = dobleDe3Dmol();

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    expect(createViewer).not.toHaveBeenCalled();
  });

  it("dice que los datos y las descargas siguen disponibles", () => {
    equipoConWebGL(false);
    dobleDe3Dmol();

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    const aviso = screen.getByRole("status");
    expect(aviso).toHaveTextContent(/no se puede dibujar en este equipo/i);
    expect(aviso).toHaveTextContent(/descargas no dependen del visor/i);
    expect(aviso).toHaveTextContent(/siguen\s+disponibles/i);
    // El motivo viene de `lib/webgl.ts`, no de un texto duplicado aquí.
    expect(aviso).toHaveTextContent(/aceleración 3D por hardware/i);
  });

  it("no deja un spinner girando para siempre", () => {
    equipoConWebGL(false);
    dobleDe3Dmol();

    const { container } = render(<MoleculeViewer3D poseData={POSE_SDF} />);

    // El spinner es el único `animate-spin` del componente y sólo tiene sentido
    // mientras algo se está cargando. Sin contexto no se va a cargar nada.
    expect(container.querySelector(".animate-spin")).toBeNull();
  });

  it("no ofrece controles ni leyenda de una vista que no existe", () => {
    equipoConWebGL(false);
    dobleDe3Dmol();

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    for (const control of [/bolsillo/i, /superficie/i, /tipos de residuo/i, /proximidad polar/i, /hotspots/i]) {
      expect(screen.queryByRole("button", { name: control })).toBeNull();
    }
    // La leyenda educativa abre diálogos sobre lo que se ve en 3D.
    expect(screen.queryByText(/hit \(/i)).toBeNull();
    expect(screen.queryByText(/proximity \(/i)).toBeNull();
  });

  it("no muestra el mensaje interno de la librería", () => {
    equipoConWebGL(false);
    dobleDe3Dmol();

    const { container } = render(<MoleculeViewer3D poseData={POSE_SDF} />);

    expect(container.textContent).not.toMatch(/does not seem to be available/i);
    expect(container.textContent).not.toMatch(/error|fallo|no se pudo/i);
  });
});

describe("MoleculeViewer3D con WebGL disponible", () => {
  it("sigue creando el visor y cargando la pose", () => {
    equipoConWebGL(true);
    const { visor, createViewer } = dobleDe3Dmol();

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    expect(createViewer).toHaveBeenCalledTimes(1);
    expect(visor.addModel).toHaveBeenCalledWith(expect.stringContaining("MolDesign"), "sdf");
    expect(visor.render).toHaveBeenCalled();
  });

  it("sigue mostrando los controles del visor", () => {
    equipoConWebGL(true);
    dobleDe3Dmol();

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    expect(screen.getByRole("button", { name: /superficie/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^proximidad polar$/i })).toBeInTheDocument();
  });

  it("conserva la cámara al alternar vistas y calcula contactos una sola vez por pose", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();
    const proteinAtoms = vi.fn(() => [{ x: 0, y: 0, z: 0, chain: "A", resi: 1, resn: "SER", elem: "O" }]);
    const ligandAtoms = vi.fn(() => [{ x: 0, y: 0, z: 3, elem: "N" }]);
    visor.getModel.mockImplementation((index: number) => ({ selectedAtoms: index === 0 ? proteinAtoms : ligandAtoms }));

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} hotspots={["A:SER1"]} pocketFocus />);
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
    expect(visor.zoomTo).toHaveBeenCalledWith(expect.objectContaining({ model: 0, predicate: expect.any(Function) }));
    expect(proteinAtoms).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: /superficie/i }));
    fireEvent.click(screen.getByRole("button", { name: /^proximidad polar$/i }));
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
    expect(proteinAtoms).toHaveBeenCalledTimes(1);
    expect(ligandAtoms).toHaveBeenCalledTimes(1);
  });

  it("sigue liberando el visor al desmontar", () => {
    // La limpieza por `liberarVisor3D` es lo que impide acumular contextos
    // WebGL huérfanos; la guarda nueva no debe haberla dejado sin camino.
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();

    const { unmount } = render(<MoleculeViewer3D poseData={POSE_SDF} />);
    unmount();

    expect(visor.spin).toHaveBeenCalledWith(false);
    expect(visor.removeAllModels).toHaveBeenCalled();
  });
});


describe("SCI-A-015: proximidad de la cadena dibujada", () => {
  it("no transfiere una proximidad B a A, ni sin cadena, y conserva el gris de no alcanzado", () => {
    equipoConWebGL(true);
    for (const caso of [
      { hotspot: "A:ASP1", hit: true, cercaA: false, color: "#52525b", radio: 0.5 },
      { hotspot: "A:ASP1", hit: true, cercaA: true, color: "#10b981", radio: 0.65 },
      { hotspot: "ASP1", hit: true, cercaA: false, color: "#52525b", radio: 0.5 },
      { hotspot: "A:ASP1", hit: false, cercaA: false, color: "#71717a", radio: 0.5 },
      { hotspot: "A:ASP1", hit: false, cercaA: true, color: "#71717a", radio: 0.65 },
    ]) {
      const { visor } = dobleDe3Dmol();
      const atoms = [
        { x: 0, y: 0, z: caso.cercaA ? 3 : 4, chain: "A", resi: 1, resn: "ASP", atom: "OD1", elem: "O" },
        { x: 0, y: 0, z: 3, chain: "B", resi: 1, resn: "ASP", atom: "OD1", elem: "O" },
      ];
      visor.getModel.mockImplementation((index: number) => ({ selectedAtoms: () => index === 0 ? atoms : [{ x: 0, y: 0, z: 0, elem: "N" }] }));
      const { unmount } = render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF}
        hotspots={[caso.hotspot]} hotspotsHit={caso.hit ? [caso.hotspot] : []} />);
      const marcas = visor.addStyle.mock.calls.filter((args: any[]) => args[1]?.sphere);
      expect(marcas).toHaveLength(1);
      expect(marcas[0]).toEqual([
        expect.objectContaining({ chain: "A", resn: "ASP", resi: 1, atom: "OD1" }),
        { sphere: { color: caso.color, radius: caso.radio } },
      ]);
      unmount();
    }
  });
});
