// =====================================================================
// La leyenda del Web3D tenía barra de desplazamiento y no se podía usar
// =====================================================================
//
// EL FALLO. El panel de «Leyenda» pedía `overflow-y-auto` con `max-h-[55vh]`
// —así que en un sitio activo grande la lista de residuos se corta y aparece la
// barra— pero al mismo tiempo llevaba `pointer-events-none`. Con el puntero
// desactivado el gesto no lo recibe el panel: lo recibe lo que hay DEBAJO, que
// es el canvas del visor. El resultado era una barra decorativa: la rueda sobre
// la leyenda le hacía zoom a la cámara y arrastrar la barra rotaba la molécula,
// mientras la mitad de los residuos quedaba fuera de la vista sin ninguna forma
// de llegar a ella.
//
// Por qué la prueba monta el componente y no lee el archivo: el defecto es la
// combinación de dos clases que por separado son correctas, y eso sólo se ve
// sobre el nodo real. `@react-three/fiber` sí se dobla —jsdom no tiene WebGL y
// el `<Canvas>` no arrancaría—, pero lo que se comprueba es el chrome de
// MolDesign alrededor del canvas, que es DOM normal.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

// El canvas no se monta: `Canvas` devuelve null y sus hijos —los que usan
// `useFrame`/`useThree`— nunca llegan a renderizarse.
vi.mock("@react-three/fiber", () => ({
  Canvas: () => null,
  useFrame: () => {},
  useThree: () => ({}),
}));
vi.mock("@react-three/drei", () => ({
  OrbitControls: () => null,
}));

import Web3DViewer from "../Web3DViewer";

/** Una línea ATOM con las columnas en su sitio (el parser lee por posición). */
function lineaAtom(
  serial: number,
  nombre: string,
  resName: string,
  cadena: string,
  resSeq: number,
  x: number,
  y: number,
  z: number,
  elemento: string,
): string {
  return (
    "ATOM  " +                       // 0-5
    String(serial).padStart(5) +     // 6-10
    " " +                            // 11
    nombre.padEnd(4).slice(0, 4) +   // 12-15
    " " +                            // 16 altLoc
    resName.padStart(3) +            // 17-19
    " " +                            // 20
    cadena +                         // 21
    String(resSeq).padStart(4) +     // 22-25
    " " +                            // 26 iCode
    "   " +                          // 27-29
    x.toFixed(3).padStart(8) +       // 30-37
    y.toFixed(3).padStart(8) +       // 38-45
    z.toFixed(3).padStart(8) +       // 46-53
    "  1.00" +                       // 54-59
    " 20.00" +                       // 60-65
    "          " +                   // 66-75
    elemento.padStart(2)             // 76-77
  );
}

const PDB = [
  lineaAtom(1, " N  ", "LEU", "A", 10, 10.0, 10.0, 10.0, "N"),
  lineaAtom(2, " CA ", "LEU", "A", 10, 11.0, 10.0, 10.0, "C"),
  lineaAtom(3, " N  ", "ASP", "A", 11, 13.0, 11.0, 10.0, "N"),
  lineaAtom(4, " CA ", "ASP", "A", 11, 14.0, 11.0, 10.0, "C"),
  "END",
].join("\n");

const HOTSPOTS = [
  { name: "A:LEU10", importance: 0.9 },
  { name: "A:ASP11", importance: 0.6 },
];

/** El panel desplegable es el hermano inmediato del botón que lo abre. */
function panelDeLeyenda(): HTMLElement {
  const boton = screen.getByRole("button", { name: /leyenda/i });
  const panel = boton.nextElementSibling;
  if (!(panel instanceof HTMLElement)) throw new Error("la leyenda no desplegó su panel");
  return panel;
}

function montar() {
  return render(<Web3DViewer proteinData={PDB} hotspots={HOTSPOTS} chain="A" />);
}

describe("panel de Leyenda del Web3D", () => {
  it("es el panel de la leyenda y está desplegado", () => {
    montar();
    // Ancla de contenido: si esto deja de cumplirse, las clases que se afirman
    // abajo estarían describiendo otro elemento.
    expect(panelDeLeyenda()).toHaveTextContent(/Caja de acoplamiento/i);
  });

  it("acepta el puntero: sin `pointer-events-none`", () => {
    // Es la causa exacta. Con el puntero desactivado la barra existe pero el
    // gesto atraviesa el panel y lo recibe el canvas.
    montar();
    const panel = panelDeLeyenda();

    expect(panel.className).not.toContain("pointer-events-none");
    expect(panel.className).toContain("pointer-events-auto");
  });

  it("se desplaza por sí mismo y contiene el desbordamiento", () => {
    montar();
    const panel = panelDeLeyenda();

    expect(panel.className).toContain("overflow-y-auto");
    // Sin esto, al llegar al final del panel el gesto se encadena hacia el
    // contenedor del visor y vuelve a mover la escena.
    expect(panel.className).toContain("overscroll-contain");
  });

  it("la rueda no llega al canvas, pero tampoco se cancela", () => {
    montar();
    const panel = panelDeLeyenda();

    // El oyente va en `document`: React registra los suyos en el contenedor
    // raíz, así que si el manejador del panel corta la propagación el evento
    // no sigue subiendo desde ahí.
    const espia = vi.fn();
    document.addEventListener("wheel", espia);
    const rueda = new WheelEvent("wheel", { bubbles: true, cancelable: true, deltaY: 120 });
    panel.dispatchEvent(rueda);
    document.removeEventListener("wheel", espia);

    expect(espia).not.toHaveBeenCalled();
    // `preventDefault` es el error clásico al arreglar esto: cortaría también
    // el desplazamiento nativo del propio panel, que es lo que se quería.
    expect(rueda.defaultPrevented).toBe(false);
  });
});
