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


// Superponer dos ligandos en la misma escena (el comparador 3D entre corridas).
//   · el segundo se carga detrás del primero, con un carbono de otro color;
//   · ocultar uno cambia su estilo, no recarga la escena ni mueve la cámara;
//   · el bolsillo y las líneas polares se miden contra los ligandos que se ven;
//   · sin primer ligando no hay a qué superponer.
describe("superposición de dos ligandos", () => {
  const OTRA_POSE = POSE_SDF.replace("ligando", "otro-ligando");

  /** Un doble donde cada modelo (proteína, ligando 1, ligando 2) tiene sus átomos y se pueden contar sus lecturas. */
  function escenaConDosLigandos() {
    const { visor } = dobleDe3Dmol();
    const atomos = {
      proteina: vi.fn(() => [{ x: 0, y: 0, z: 0, chain: "A", resi: 1, resn: "SER", atom: "OG", elem: "O" }]),
      primero: vi.fn(() => [{ x: 0, y: 0, z: 3, elem: "N" }]),
      segundo: vi.fn(() => [{ x: 0, y: 0, z: 2.5, elem: "N" }]),
    };
    visor.getModel.mockImplementation((index: number) => ({
      selectedAtoms: index === 0 ? atomos.proteina : index === 1 ? atomos.primero : atomos.segundo,
    }));
    return { visor, atomos };
  }

  it("carga proteína, primer ligando y segundo ligando, en ese orden", () => {
    equipoConWebGL(true);
    const { visor } = escenaConDosLigandos();

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={OTRA_POSE} />);

    expect(visor.addModel).toHaveBeenCalledTimes(3);
    expect(visor.addModel.mock.calls.map((llamada: unknown[]) => llamada[1])).toEqual(["pdb", "sdf", "sdf"]);
    expect(visor.addModel.mock.calls[2][0]).toContain("otro-ligando");
  });

  it("dibuja cada ligando con su carbono y encuadra los dos", () => {
    equipoConWebGL(true);
    const { visor } = escenaConDosLigandos();

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={OTRA_POSE} />);

    expect(visor.setStyle).toHaveBeenCalledWith({ model: 1 }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
    expect(visor.setStyle).toHaveBeenCalledWith({ model: 2 }, { stick: { colorscheme: "magentaCarbon", radius: 0.22 } });
    expect(visor.zoomTo).toHaveBeenCalledWith({ model: [1, 2] });
  });

  it("sin segundo ligando todo queda como antes: un modelo de ligando y la cámara sobre él", () => {
    equipoConWebGL(true);
    const { visor } = escenaConDosLigandos();

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} />);

    expect(visor.addModel).toHaveBeenCalledTimes(2);
    expect(visor.zoomTo).toHaveBeenCalledWith({ model: 1 });
    expect(visor.setStyle).not.toHaveBeenCalledWith({ model: 2 }, expect.anything());
  });

  it("sin primer ligando no hay a qué superponer: el segundo no se carga", () => {
    equipoConWebGL(true);
    const { visor } = escenaConDosLigandos();

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" overlayPoseData={OTRA_POSE} />);

    expect(visor.addModel).toHaveBeenCalledTimes(1);
  });

  it("ocultar un ligando cambia su estilo sin recargar la escena ni mover la cámara", () => {
    equipoConWebGL(true);
    const { visor } = escenaConDosLigandos();

    const { rerender } = render(
      <MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={OTRA_POSE} />,
    );
    expect(visor.addModel).toHaveBeenCalledTimes(3);
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);

    rerender(
      <MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={OTRA_POSE} showOverlayLigand={false} />,
    );

    expect(visor.setStyle).toHaveBeenLastCalledWith({ model: 2 }, { stick: { hidden: true } });
    expect(visor.addModel).toHaveBeenCalledTimes(3);
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
  });

  it("el bolsillo se mide contra los ligandos visibles, y se recalcula al ocultar uno", () => {
    equipoConWebGL(true);
    const { atomos } = escenaConDosLigandos();

    const { rerender } = render(
      <MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={OTRA_POSE} />,
    );
    expect(atomos.primero).toHaveBeenCalledTimes(1);
    expect(atomos.segundo).toHaveBeenCalledTimes(1);

    // Alternar vistas no recalcula: los mismos ligandos visibles, la misma geometría.
    fireEvent.click(screen.getByRole("button", { name: /superficie/i }));
    expect(atomos.primero).toHaveBeenCalledTimes(1);
    expect(atomos.segundo).toHaveBeenCalledTimes(1);

    // Ocultar el segundo deja de contar sus átomos.
    rerender(
      <MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={OTRA_POSE} showOverlayLigand={false} />,
    );
    expect(atomos.primero).toHaveBeenCalledTimes(2);
    expect(atomos.segundo).toHaveBeenCalledTimes(1);
  });
});

// Núcleo común y contactos que el comparador pide dibujar.
//   · con la lista de átomos del núcleo, lo que cambia va grueso y el núcleo fino y tenue; sin ella, como siempre;
//   · la lista es de índices del registro SDF (`atom.index` de 3Dmol): el predicado elige por ese índice;
//   · los contactos pedidos son cilindros punteados del color que se les dio, sólo con receptor y ligando.
describe("núcleo común y líneas de contacto", () => {
  it("dibuja grueso lo que cambia y fino el núcleo, eligiendo por el índice del átomo", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} primaryCoreAtoms={[0, 1, 2]} />);

    expect(visor.setStyle).toHaveBeenCalledWith({ model: 1 }, { stick: { colorscheme: "greenCarbon", radius: 0.3 } });
    const [seleccion, estilo] = visor.setStyle.mock.calls.find(
      (llamada: any[]) => llamada[0]?.model === 1 && typeof llamada[0]?.predicate === "function",
    )!;
    expect(estilo).toEqual({ stick: { colorscheme: "greenCarbon", radius: 0.13, opacity: 0.7 } });
    expect([0, 1, 2, 3].map((index) => seleccion.predicate({ index }))).toEqual([true, true, true, false]);
  });

  it("cada ligando se afina con su propio núcleo", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();

    render(
      <MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} overlayPoseData={POSE_SDF.replace("ligando", "otro")}
        primaryCoreAtoms={[0]} overlayCoreAtoms={[5]} />,
    );

    const afinados = visor.setStyle.mock.calls.filter((llamada: any[]) => typeof llamada[0]?.predicate === "function");
    expect(afinados.map((llamada: any[]) => llamada[0].model)).toEqual([1, 2]);
    expect(afinados[0][0].predicate({ index: 0 })).toBe(true);
    expect(afinados[0][0].predicate({ index: 5 })).toBe(false);
    expect(afinados[1][0].predicate({ index: 5 })).toBe(true);
    expect(afinados[1][1]).toEqual({ stick: { colorscheme: "magentaCarbon", radius: 0.13, opacity: 0.7 } });
  });

  it("sin núcleo el ligando se dibuja como siempre, y oculto no se afina nada", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();

    const { rerender } = render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} />);
    expect(visor.setStyle.mock.calls.some((llamada: any[]) => typeof llamada[0]?.predicate === "function")).toBe(false);

    visor.setStyle.mockClear();
    rerender(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} primaryCoreAtoms={[0]} showPrimaryLigand={false} />);
    expect(visor.setStyle).toHaveBeenCalledWith({ model: 1 }, { stick: { hidden: true } });
    expect(visor.setStyle.mock.calls.some((llamada: any[]) => typeof llamada[0]?.predicate === "function")).toBe(false);
  });

  it("las líneas de contacto son cilindros punteados del color pedido", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();
    const lineas = [
      { start: { x: 0, y: 0, z: 0 }, end: { x: 0, y: 0, z: 3 }, color: "#00ff00" },
      { start: { x: 1, y: 0, z: 0 }, end: { x: 1, y: 0, z: 3 }, color: "#a1a1aa" },
    ];

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} contactLines={lineas} />);

    expect(visor.addCylinder).toHaveBeenCalledTimes(2);
    expect(visor.addCylinder).toHaveBeenCalledWith(expect.objectContaining({ start: lineas[0].start, end: lineas[0].end, color: "#00ff00", dashed: true }));
  });

  it("sin receptor no hay a qué unir las líneas", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();

    render(<MoleculeViewer3D poseData={POSE_SDF} contactLines={[{ start: { x: 0, y: 0, z: 0 }, end: { x: 0, y: 0, z: 3 }, color: "#fff" }]} />);

    expect(visor.addCylinder).not.toHaveBeenCalled();
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


// =====================================================================
// Cambiar de pose no es volver a construir el receptor
// =====================================================================
//
// Medido en el comparador 3D con una evaluación real (8T69, 2 900 átomos): cada cambio de pose hacía `clear()`, volvía a
// leer la proteína entera, la volvía a estilar y reencuadraba la cámara, así que quien comparaba poses perdía su punto
// de vista a cada clic. Con la misma proteína, sólo se reemplazan los modelos de ligando.
describe("cambiar de pose con la misma proteína", () => {
  const POSE_2 = POSE_SDF.replace("ligando", "pose-2");
  const POSE_3 = POSE_SDF.replace("ligando", "pose-3");
  const OVERLAY = POSE_SDF.replace("ligando", "otro-ligando");
  const PROTEINA = "PROTEIN-MODEL-DATA";
  const estilosDeProteina = (visor: { setStyle: { mock: { calls: any[][] } } }) =>
    visor.setStyle.mock.calls.filter((llamada) => llamada[0]?.model === 0 && llamada[1]?.cartoon).length;

  /** 3Dmol devuelve el modelo que añade; `removeModel` lo quita. Cada modelo lleva el orden en que se creó. */
  function visorConModelos() {
    const { visor, createViewer } = dobleDe3Dmol();
    let creados = 0;
    visor.addModel.mockImplementation(() => ({ orden: ++creados }) as never);
    const removeModel = vi.fn();
    (visor as unknown as { removeModel: typeof removeModel }).removeModel = removeModel;
    return { visor, createViewer, removeModel };
  }

  it("no vuelve a leer la proteína, no la descarta, y deja la cámara donde está", () => {
    equipoConWebGL(true);
    const { visor, removeModel } = visorConModelos();

    const { rerender } = render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    expect(visor.clear).toHaveBeenCalledTimes(1);
    expect(visor.addModel.mock.calls.map((c: unknown[]) => c[1])).toEqual(["pdb", "sdf"]);
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
    const dibujosAntes = visor.render.mock.calls.length;

    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_2} />);

    expect(visor.clear).toHaveBeenCalledTimes(1);
    expect(visor.addModel).toHaveBeenCalledTimes(3);
    expect(visor.addModel.mock.calls[2][1]).toBe("sdf");
    expect(visor.addModel.mock.calls[2][0]).toContain("pose-2");
    expect(removeModel).toHaveBeenCalledTimes(1);
    expect((removeModel.mock.calls[0][0] as { orden: number }).orden).toBe(2); // el ligando; la proteína (1) sigue
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
    expect(visor.render.mock.calls.length).toBeGreaterThan(dibujosAntes);
  });

  it("varios cambios seguidos siguen siendo sólo del ligando", () => {
    equipoConWebGL(true);
    const { visor, removeModel } = visorConModelos();

    const { rerender } = render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_2} />);
    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_3} />);

    expect(visor.clear).toHaveBeenCalledTimes(1);
    expect(visor.addModel.mock.calls.filter((c: unknown[]) => c[1] === "pdb")).toHaveLength(1);
    expect(removeModel).toHaveBeenCalledTimes(2);
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
  });

  it("con dos ligandos quita primero el segundo y vuelve a añadir en el mismo orden: 1 = ligando, 2 = superpuesto", () => {
    // 3Dmol numera cada modelo nuevo con el largo de su lista y sólo recorta el final al quitar uno.
    equipoConWebGL(true);
    const { visor, removeModel } = visorConModelos();

    const { rerender } = render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} overlayPoseData={OVERLAY} />);
    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_2} overlayPoseData={OVERLAY} />);

    expect(removeModel.mock.calls.map((c) => (c[0] as { orden: number }).orden)).toEqual([3, 2]);
    expect(visor.addModel.mock.calls.slice(3).map((c: unknown[]) => c[1])).toEqual(["sdf", "sdf"]);
    expect(visor.addModel.mock.calls[3][0]).toContain("pose-2");
    expect(visor.addModel.mock.calls[4][0]).toContain("otro-ligando");
    expect(visor.clear).toHaveBeenCalledTimes(1);
    expect(visor.zoomTo).toHaveBeenCalledTimes(1);
  });

  it("al aparecer o desaparecer el segundo ligando tampoco se vuelve a cargar la proteína", () => {
    equipoConWebGL(true);
    const { visor, removeModel } = visorConModelos();

    const { rerender } = render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} overlayPoseData={OVERLAY} />);
    expect(visor.clear).toHaveBeenCalledTimes(1);
    expect(visor.addModel.mock.calls.filter((c: unknown[]) => c[1] === "pdb")).toHaveLength(1);
    expect(visor.addModel.mock.calls.at(-1)![0]).toContain("otro-ligando");

    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    expect(removeModel.mock.calls.at(-1)).toBeDefined();
    expect(visor.clear).toHaveBeenCalledTimes(1);
  });

  it("otra proteína sí es una escena nueva: se vacía, se vuelve a cargar y se reencuadra", () => {
    equipoConWebGL(true);
    const { visor } = visorConModelos();

    const { rerender } = render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    rerender(<MoleculeViewer3D proteinData="OTRO-RECEPTOR-DISTINTO" poseData={POSE_SDF} />);

    expect(visor.clear).toHaveBeenCalledTimes(2);
    expect(visor.addModel.mock.calls.filter((c: unknown[]) => c[1] === "pdb")).toHaveLength(2);
    expect(visor.zoomTo).toHaveBeenCalledTimes(2);
    expect(estilosDeProteina(visor)).toBe(2);
  });

  it("si 3Dmol no devuelve los modelos no se pueden quitar uno a uno: se recarga todo, como antes", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol(); // `addModel` devuelve undefined

    const { rerender } = render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    rerender(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_2} />);

    expect(visor.clear).toHaveBeenCalledTimes(2);
    expect(visor.addModel.mock.calls.filter((c: unknown[]) => c[1] === "pdb")).toHaveLength(2);
  });

  it("sin proteína no hay receptor que conservar: el ligando nuevo se carga y se encuadra", () => {
    equipoConWebGL(true);
    const { visor } = visorConModelos();

    const { rerender } = render(<MoleculeViewer3D poseData={POSE_SDF} />);
    rerender(<MoleculeViewer3D poseData={POSE_2} />);

    expect(visor.clear).toHaveBeenCalledTimes(2);
    expect(visor.zoomTo).toHaveBeenCalledTimes(2);
  });

  // Una proteína con forma de PDB (las líneas ATOM que lee `pdbDelBolsillo`): dos serinas lejos una de otra.
  const PDB = [
    "ATOM      1  OG  SER A   1       0.000   0.000   0.000  1.00  0.00           O",
    "ATOM      2  OG  SER A   2      30.000   0.000   0.000  1.00  0.00           O",
    "HETATM    3  O   HOH A   1       0.500   0.500   0.500  1.00  0.00           O",
  ].join("\n");
  const ATOMOS_DEL_PDB = [
    { x: 0, y: 0, z: 0, chain: "A", resi: 1, resn: "SER", atom: "OG", elem: "O" },
    { x: 30, y: 0, z: 0, chain: "A", resi: 2, resn: "SER", atom: "OG", elem: "O" },
  ];
  /** Tres poses: la 2.ª toca los mismos residuos que la 1.ª; la 3.ª, otros. */
  function escenaDeTresPoses() {
    const ctx = visorConModelos();
    const ligando = vi.fn();
    ligando
      .mockReturnValueOnce([{ x: 0, y: 0, z: 3, elem: "N" }])   // pose 1: junto al residuo 1
      .mockReturnValueOnce([{ x: 0, y: 0, z: 2.8, elem: "N" }]) // pose 2: otra posición, mismo residuo
      .mockReturnValueOnce([{ x: 30, y: 0, z: 3, elem: "N" }]); // pose 3: junto al residuo 2
    ctx.visor.getModel.mockImplementation((index: number) => ({ selectedAtoms: index === 0 ? () => ATOMOS_DEL_PDB : ligando }));
    return ctx;
  }
  const modelosPdb = (visor: { addModel: { mock: { calls: any[][] } } }) =>
    visor.addModel.mock.calls.filter((llamada) => llamada[1] === "pdb").map((llamada) => String(llamada[0]));

  it("el bolsillo es un modelo aparte: cambiar de pose no vuelve a estilar la proteína, aunque cambie el bolsillo", () => {
    // Estilar un modelo hace que 3Dmol reconstruya toda su geometría —el cartoon del receptor, que crece con él—. Las
    // varillas del bolsillo cambian con cada pose, así que son un modelo pequeño que se reemplaza junto al ligando.
    equipoConWebGL(true);
    const { visor } = escenaDeTresPoses();

    const { rerender } = render(<MoleculeViewer3D proteinData={PDB} poseData={POSE_SDF} />);
    expect(estilosDeProteina(visor)).toBe(1);
    // Proteína, ligando y bolsillo (sólo el residuo 1, sólo ATOM: el agua HETATM con el mismo número no entra).
    expect(visor.addModel.mock.calls.map((c: unknown[]) => c[1])).toEqual(["pdb", "sdf", "pdb"]);
    expect(modelosPdb(visor)[1]).toContain("SER A   1");
    expect(modelosPdb(visor)[1]).not.toContain("SER A   2");
    expect(modelosPdb(visor)[1]).not.toContain("HETATM");
    expect(visor.setStyle).toHaveBeenCalledWith({ model: 2 }, { stick: { colorscheme: "lightgreyCarbon", radius: 0.14, opacity: 0.99 } });

    rerender(<MoleculeViewer3D proteinData={PDB} poseData={POSE_2} />);
    expect(estilosDeProteina(visor)).toBe(1);
    expect(visor.clear).toHaveBeenCalledTimes(1);

    rerender(<MoleculeViewer3D proteinData={PDB} poseData={POSE_3} />);
    expect(estilosDeProteina(visor)).toBe(1);
    expect(visor.clear).toHaveBeenCalledTimes(1);
    // El bolsillo de la pose 3 es el otro residuo.
    const ultimoBolsillo = modelosPdb(visor).at(-1)!;
    expect(ultimoBolsillo).toContain("SER A   2");
    expect(ultimoBolsillo).not.toContain("SER A   1");
    // La proteína se leyó una sola vez; los demás modelos de proteína son bolsillos.
    expect(modelosPdb(visor)[0]).toContain("HETATM");
    // El ligando sí se estila siempre.
    expect(visor.setStyle).toHaveBeenCalledWith({ model: 1 }, { stick: { colorscheme: "greenCarbon", radius: 0.22 } });
  });

  it("el bolsillo se quita antes que los ligandos, para que los ids de 3Dmol no se muevan", () => {
    equipoConWebGL(true);
    const { visor, removeModel } = escenaDeTresPoses();

    const { rerender } = render(<MoleculeViewer3D proteinData={PDB} poseData={POSE_SDF} />);
    rerender(<MoleculeViewer3D proteinData={PDB} poseData={POSE_2} />);

    // Creados en este orden: 1 = proteína, 2 = ligando, 3 = bolsillo. Se quitan 3 (bolsillo) y 2 (ligando).
    expect(removeModel.mock.calls.map((c) => (c[0] as { orden: number }).orden)).toEqual([3, 2]);
    // Y vuelven a añadirse en el orden que fija los ids: ligando (1) y bolsillo (2).
    expect(visor.addModel.mock.calls.slice(3).map((c: unknown[]) => c[1])).toEqual(["sdf", "pdb"]);
  });

  it("con dos ligandos el bolsillo es el modelo 3", () => {
    equipoConWebGL(true);
    const { visor } = visorConModelos();
    visor.getModel.mockImplementation((index: number) => ({
      selectedAtoms: index === 0 ? () => ATOMOS_DEL_PDB : index === 1 ? () => [{ x: 0, y: 0, z: 3, elem: "N" }] : () => [{ x: 0, y: 0, z: 2.5, elem: "N" }],
    }));

    render(<MoleculeViewer3D proteinData={PDB} poseData={POSE_SDF} overlayPoseData={OVERLAY} />);

    expect(visor.addModel.mock.calls.map((c: unknown[]) => c[1])).toEqual(["pdb", "sdf", "sdf", "pdb"]);
    expect(visor.setStyle).toHaveBeenCalledWith({ model: 3 }, { stick: { colorscheme: "lightgreyCarbon", radius: 0.14, opacity: 0.99 } });
  });

  it("ocultar el único ligando visible quita el bolsillo; volver a mostrarlo lo levanta", () => {
    equipoConWebGL(true);
    const { visor, removeModel } = escenaDeTresPoses();

    const { rerender } = render(<MoleculeViewer3D proteinData={PDB} poseData={POSE_SDF} />);
    expect(modelosPdb(visor)).toHaveLength(2);

    rerender(<MoleculeViewer3D proteinData={PDB} poseData={POSE_SDF} showPrimaryLigand={false} />);
    // Sin ligando visible no se mide ningún bolsillo: el modelo se retira y no se levanta otro.
    expect(removeModel).toHaveBeenCalledTimes(1);
    expect(modelosPdb(visor)).toHaveLength(2);
  });

  it("un visor sin `removeModel` pinta el bolsillo como estilo de la proteína, como antes", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol(); // sin removeModel
    visor.getModel.mockImplementation((index: number) => ({ selectedAtoms: index === 0 ? () => ATOMOS_DEL_PDB : () => [{ x: 0, y: 0, z: 3, elem: "N" }] }));

    render(<MoleculeViewer3D proteinData={PDB} poseData={POSE_SDF} />);

    expect(visor.addModel.mock.calls.map((c: unknown[]) => c[1])).toEqual(["pdb", "sdf"]);
    expect(visor.addStyle).toHaveBeenCalledWith({ model: 0, chain: "A", resi: 1 }, { stick: { colorscheme: "lightgreyCarbon", radius: 0.14, opacity: 0.99 } });
  });

  it("alternar la vista no vuelve a estilar la proteína, y la superficie se rehace sólo al cambiar de vista", () => {
    equipoConWebGL(true);
    const { visor } = visorConModelos();
    visor.getModel.mockImplementation((index: number) => ({
      selectedAtoms: index === 0
        ? () => [{ x: 0, y: 0, z: 0, chain: "A", resi: 1, resn: "SER", atom: "OG", elem: "O" }]
        : () => [{ x: 0, y: 0, z: 3, elem: "N" }],
    }));

    render(<MoleculeViewer3D proteinData={PROTEINA} poseData={POSE_SDF} />);
    expect(estilosDeProteina(visor)).toBe(1);
    expect(visor.addSurface).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /^proximidad polar$/i }));
    expect(estilosDeProteina(visor)).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: /superficie/i }));
    expect(visor.addSurface).toHaveBeenCalledTimes(1);
    expect(estilosDeProteina(visor)).toBe(1);

    // Volver a alternar la proximidad polar no rehace la superficie de toda la proteína.
    fireEvent.click(screen.getByRole("button", { name: /^proximidad polar$/i }));
    expect(visor.addSurface).toHaveBeenCalledTimes(1);
  });
});

// =====================================================================
// Un contexto WebGL perdido no inunda la consola
// =====================================================================
//
// 3Dmol no lanza cuando el navegador le quita el contexto: en cada dibujo intenta compilar sus shaders y escribe «could
// not initialize shader» con `console.error`, que el overlay de Next convierte en una pila de incidencias. Se detecta,
// se deja de dibujar y se ofrece reabrir la vista.
describe("contexto WebGL perdido", () => {
  it("no dibuja sobre un contexto perdido, lo dice y no esconde que los datos siguen ahí", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();
    (visor as unknown as { renderer: unknown }).renderer = { isLost: () => true };

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    expect(visor.render).not.toHaveBeenCalled();
    expect(screen.getByRole("status")).toHaveTextContent(/soltó la aceleración 3D de esta vista/i);
    expect(screen.getByRole("status")).toHaveTextContent(/datos y las descargas no dependen/i);
  });

  it("si 3Dmol recupera el contexto al redimensionar, dibuja y no muestra ningún aviso", () => {
    equipoConWebGL(true);
    const { visor } = dobleDe3Dmol();
    let perdido = true;
    visor.resize.mockImplementation(() => { perdido = false; });
    (visor as unknown as { renderer: unknown }).renderer = { isLost: () => perdido };

    render(<MoleculeViewer3D poseData={POSE_SDF} />);

    expect(visor.render).toHaveBeenCalled();
    expect(screen.queryByText(/soltó la aceleración 3D/i)).toBeNull();
  });

  it("«Volver a abrir la vista 3D» suelta el visor perdido y crea uno nuevo con los mismos datos", () => {
    equipoConWebGL(true);
    const { visor, createViewer } = dobleDe3Dmol();
    let perdido = true;
    (visor as unknown as { renderer: unknown }).renderer = { isLost: () => perdido };

    render(<MoleculeViewer3D proteinData="PROTEIN-MODEL-DATA" poseData={POSE_SDF} />);
    expect(createViewer).toHaveBeenCalledTimes(1);
    expect(visor.render).not.toHaveBeenCalled();

    perdido = false;
    fireEvent.click(screen.getByRole("button", { name: /volver a abrir la vista 3d/i }));

    expect(visor.removeAllModels).toHaveBeenCalled();
    expect(createViewer).toHaveBeenCalledTimes(2);
    expect(visor.addModel.mock.calls.filter((c: unknown[]) => c[1] === "pdb")).toHaveLength(2);
    expect(visor.render).toHaveBeenCalled();
    expect(screen.queryByText(/soltó la aceleración 3D/i)).toBeNull();
  });
});
