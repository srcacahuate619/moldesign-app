/**
 * Lo que enseña el visor ligero: qué átomos dibuja, cómo identifica los residuos y qué dice cuando no lo dibuja todo.
 *
 * Cuatro defectos leídos en el código el 2026-11-10, cada uno con su prueba:
 *   · sólo dibujaba registros ATOM: un Zn o un cofactor conservados, que Vina sí ve, no aparecían;
 *   · identificaba los residuos del sitio sin cadena: en un homodímero se mezclaban los de las dos cadenas;
 *   · cortaba en 50 000 átomos por el orden del archivo, sin avisar, y seguía diciendo «receptor completo»;
 *   · la leyenda y el resumen abrían a la vez y se pisaban.
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

vi.mock("@react-three/fiber", () => ({
  Canvas: () => null,
  useFrame: () => {},
  useThree: () => ({}),
}));
vi.mock("@react-three/drei", () => ({
  OrbitControls: () => null,
}));

import Web3DViewer, { parsePdbAtoms, parsePdbHetero, recortarAlrededor } from "../Web3DViewer";

function linea(registro: "ATOM  " | "HETATM", serial: number, nombre: string, resName: string, cadena: string, resSeq: number,
  x: number, y: number, z: number, elemento: string): string {
  return (
    registro + String(serial).padStart(5) + " " + nombre.padEnd(4).slice(0, 4) + " " + resName.padStart(3) + " " + cadena +
    String(resSeq).padStart(4) + " " + "   " + x.toFixed(3).padStart(8) + y.toFixed(3).padStart(8) + z.toFixed(3).padStart(8) +
    "  1.00" + " 20.00" + "          " + elemento.padStart(2)
  );
}

describe("qué átomos dibuja", () => {
  const pdb = [
    linea("ATOM  ", 1, " CA ", "HIS", "A", 94, 0, 0, 0, "C"),
    linea("HETATM", 2, " SE ", "MSE", "A", 95, 1, 0, 0, "SE"),     // selenometionina: es de la proteína
    linea("ATOM  ", 3, "ZN  ", " ZN", "A", 301, 2, 0, 0, "ZN"),     // Meeko escribe los iones como ATOM
    linea("HETATM", 4, " FE ", "HEM", "A", 500, 3, 0, 0, "FE"),     // cofactor
    linea("HETATM", 5, " C1 ", "HEM", "A", 500, 4, 0, 0, "C"),
    linea("HETATM", 6, " O  ", "HOH", "A", 601, 5, 0, 0, "O"),
    linea("HETATM", 7, " O  ", "HOH", "A", 602, 6, 0, 0, "O"),
  ].join("\n");

  it("la proteína incluye los residuos modificados aunque vengan como HETATM, y no los heteroátomos", () => {
    expect(parsePdbAtoms(pdb, new Map()).map((a) => a.resId)).toEqual(["HIS94", "MSE95"]);
  });

  it("los metales salen aunque vengan como ATOM, y el cofactor como un grupo", () => {
    const { atomos, grupos } = parsePdbHetero(pdb, { conAguas: false });
    expect(grupos.map((g) => [g.clave, g.tipo, g.atomos])).toEqual([
      ["A:ZN301", "metal", 1], ["A:HEM500", "grupo", 2], ["A:HOH601", "agua", 1], ["A:HOH602", "agua", 1],
    ]);
    // Las aguas del depósito se cuentan, pero no se dibujan: son cientos y la preparación las retira.
    expect(atomos.map((a) => a.element)).toEqual(["ZN", "FE", "C"]);
  });

  it("con el receptor que acopló Vina, las aguas que conserva sí se dibujan", () => {
    expect(parsePdbHetero(pdb, { conAguas: true }).atomos.filter((a) => a.tipo === "agua")).toHaveLength(2);
  });

  it("si hay que recortar, se queda el sitio entero y lo más cercano al centro, no lo primero del archivo", () => {
    const atomos = [
      { x: 100, y: 0, z: 0, id: "lejos" },
      { x: 50, y: 0, z: 0, id: "medio" },
      { x: 90, y: 0, z: 0, id: "sitio", isHotspot: true },
      { x: 1, y: 0, z: 0, id: "cerca" },
    ];
    expect(recortarAlrededor(atomos, [0, 0, 0], 3).map((a) => a.id)).toEqual(["sitio", "cerca", "medio"]);
    expect(recortarAlrededor(atomos, [0, 0, 0], 10)).toBe(atomos);
  });
});

describe("el visor", () => {
  // Un homodímero: el mismo ASP25 en las cadenas A y B, anotado sin cadena (como el catálogo en la proteasa del VIH).
  const dimero = [
    linea("ATOM  ", 1, " CA ", "ASP", "A", 25, 0, 0, 0, "C"),
    linea("ATOM  ", 2, " CB ", "ASP", "A", 25, 0.5, 0, 0, "C"),
    linea("ATOM  ", 3, " CA ", "ASP", "B", 25, 6, 0, 0, "C"),
    linea("ATOM  ", 4, " CB ", "ASP", "B", 25, 6.5, 0, 0, "C"),
    linea("ATOM  ", 5, " CA ", "GLY", "A", 27, 2, 2, 0, "C"),
    linea("HETATM", 6, "ZN  ", " ZN", "A", 401, 3, 3, 3, "ZN"),
  ].join("\n");

  it("en un homodímero, el residuo de cada cadena es una entrada propia de la leyenda", () => {
    render(<Web3DViewer proteinData={dimero} hotspots={[{ name: "ASP25", importance: 0.9 }]} />);
    fireEvent.click(screen.getByRole("button", { name: /leyenda/i }));
    expect(screen.getByText("A:ASP25")).toBeTruthy();
    expect(screen.getByText("B:ASP25")).toBeTruthy();
  });

  it("enseña los metales en la leyenda y dice de dónde salen", () => {
    const { unmount } = render(<Web3DViewer proteinData={dimero} origenDelReceptor="deposito" />);
    fireEvent.click(screen.getByRole("button", { name: /leyenda/i }));
    expect(screen.getByText("A:ZN401")).toBeTruthy();
    expect(screen.getAllByText("Son los del depósito; la preparación decide cuáles conserva.").length).toBeGreaterThan(0);
    unmount();
    render(<Web3DViewer proteinData={dimero} origenDelReceptor="corrida" />);
    fireEvent.click(screen.getByRole("button", { name: /leyenda/i }));
    expect(screen.getAllByText("Son los del receptor que acopló Vina.").length).toBeGreaterThan(0);
  });

  it("el resumen y la leyenda no se abren a la vez", () => {
    render(<Web3DViewer proteinData={dimero} hotspots={[{ name: "ASP25" }]} />);
    const leyenda = screen.getByRole("button", { name: /leyenda/i });
    const resumen = screen.getByRole("button", { name: /Web3D/ });
    expect(leyenda.getAttribute("aria-expanded")).toBe("false");
    expect(resumen.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(leyenda);
    fireEvent.click(resumen);
    expect(leyenda.getAttribute("aria-expanded")).toBe("false");
    expect(resumen.getAttribute("aria-expanded")).toBe("true");
  });

  it("si recorta el receptor lo dice, en el resumen y en la leyenda", () => {
    const grande = Array.from({ length: 50_010 }, (_, i) => linea("ATOM  ", i + 1, " CA ", "ALA", "A", i + 1, i % 97, (i * 7) % 89, (i * 13) % 83, "C")).join("\n");
    render(<Web3DViewer proteinData={grande} gridInfo={{ centerX: 0, centerY: 0, centerZ: 0, sizeX: 20, sizeY: 20, sizeZ: 20 }} />);
    fireEvent.click(screen.getByRole("button", { name: /Web3D/ }));
    expect(screen.getByRole("status").textContent).toMatch(/50\D?000 de 50\D?010/);
    fireEvent.click(screen.getByRole("button", { name: /leyenda/i }));
    expect(screen.getByText(/Receptor \(parte cercana a la caja\)/)).toBeTruthy();
  });

  it("pantalla completa: sin la del sistema, el visor ocupa la ventana, y Escape lo devuelve", () => {
    const { container } = render(<Web3DViewer proteinData={dimero} />);
    const raiz = container.firstElementChild as HTMLElement;
    // jsdom no tiene `requestFullscreen`: es el camino de respaldo.
    fireEvent.click(screen.getByRole("button", { name: "Pantalla completa" }));
    expect(raiz.className).toContain("fixed inset-0");
    fireEvent.keyDown(window, { key: "Escape" });
    expect(raiz.className).not.toContain("fixed inset-0");
  });
});
