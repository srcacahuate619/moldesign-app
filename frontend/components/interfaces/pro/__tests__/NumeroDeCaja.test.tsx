// =====================================================================
// SOL-13 / SOL-14 — los controles numéricos de Opciones
// =====================================================================
//
// SOL-13. Teclear 150 en el centro X producía 100 al instante, sin explicación:
// el valor pedido se perdía y la búsqueda se desplazaba sin que nadie lo
// decidiera. El criterio de cierre exige «conservar la entrada válida o
// informar explícitamente su rechazo».
//
// SOL-14. `NumberInput` dibujaba un <label> suelto: el campo no tenía nombre
// accesible y los pasos se anunciaban sólo como «+» y «−».
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

vi.mock("@react-three/fiber", () => ({
  Canvas: () => <div data-testid="canvas" />,
  useThree: () => ({
    camera: { position: { set: () => {} }, lookAt: () => {}, updateProjectionMatrix: () => {} },
    invalidate: () => {},
    gl: {},
    scene: {},
  }),
}));
vi.mock("@react-three/drei", () => ({ OrbitControls: () => null, Edges: () => null, Sphere: () => null }));
vi.mock("../../../../lib/api", () => ({
  encenderMotor: vi.fn(async () => {}),
  inventarioDeMotores: vi.fn(async () => ({ motores: [] })),
}));

import ProOptionsModal, { type GridBoxConfig } from "../ProOptionsModal";

beforeAll(() => {
  if (typeof Element.prototype.animate !== "function") {
    Element.prototype.animate = (() => ({
      cancel: () => {},
      finish: () => {},
      finished: Promise.resolve(),
    })) as unknown as Element["animate"];
  }
});

const caja: GridBoxConfig = {
  centerX: 12, centerY: -3.5, centerZ: 40, sizeX: 20, sizeY: 20, sizeZ: 20, exhaustiveness: 8, numModes: 9,
};

function abrir() {
  const alAplicar = vi.fn();
  render(<ProOptionsModal isOpen onClose={() => {}} onApply={alAplicar} initialGridBox={caja} />);
  return alAplicar;
}

const centroX = () => screen.getByRole("spinbutton", { name: /Centro de la caja de búsqueda.*X/i }) as HTMLInputElement;

describe("SOL-13: la entrada fuera de rango no se recorta en silencio", () => {
  it("150 en el centro X se conserva: el backend admite hasta ±10000 Å", () => {
    abrir();
    fireEvent.change(centroX(), { target: { value: "150" } });
    expect(centroX().value).toBe("150");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("un centro sobre el límite de ejecución se RECHAZA con mensaje, sin cambiar el valor vigente", () => {
    abrir();
    fireEvent.change(centroX(), { target: { value: "20000" } });
    const aviso = screen.getByRole("alert");
    expect(aviso).toHaveTextContent("20000");
    expect(aviso).toHaveTextContent("-10000 a 10000");
    expect(aviso).toHaveTextContent("Se conserva 12");
    expect(centroX()).toHaveAttribute("aria-invalid", "true");
    expect(centroX()).toHaveAttribute("aria-describedby", aviso.id);
    // Al salir del campo vuelve el valor vigente, y el rechazo sigue visible.
    fireEvent.blur(centroX());
    expect(centroX().value).toBe("12");
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("una entrada válida posterior limpia el rechazo y se acepta", () => {
    abrir();
    fireEvent.change(centroX(), { target: { value: "20000" } });
    fireEvent.change(centroX(), { target: { value: "-250.5" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(centroX().value).toBe("-250.5");
    expect(centroX()).not.toHaveAttribute("aria-invalid");
  });

  it("la edición a medias (vacío) no es un rechazo", () => {
    abrir();
    fireEvent.change(centroX(), { target: { value: "" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("el lado de la caja admite hasta 80 Å (antes 50) y rechaza más", () => {
    abrir();
    const lado = screen.getByRole("spinbutton", { name: /Dimensiones de la caja de búsqueda.*X/i }) as HTMLInputElement;
    fireEvent.change(lado, { target: { value: "70" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    fireEvent.change(lado, { target: { value: "81" } });
    expect(screen.getByRole("alert")).toHaveTextContent("5 a 80");
  });
});

describe("SOL-14: nombre accesible de los controles numéricos", () => {
  it("cada eje del centro y del tamaño tiene nombre que dice eje y dimensión", () => {
    abrir();
    for (const eje of ["X", "Y", "Z"]) {
      expect(
        screen.getByRole("spinbutton", { name: new RegExp(`Centro de la caja de búsqueda.*${eje}`, "i") }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("spinbutton", { name: new RegExp(`Dimensiones de la caja de búsqueda.*${eje}`, "i") }),
      ).toBeInTheDocument();
    }
  });

  it("los pasos se anuncian con el campo al que afectan, no como «+» y «−»", () => {
    abrir();
    expect(screen.getByRole("button", { name: /Aumentar Centro de la caja de búsqueda.*X/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Disminuir Centro de la caja de búsqueda.*X/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "+" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "−" })).not.toBeInTheDocument();
  });

  it("el paso suma sin ruido de coma flotante", () => {
    abrir();
    fireEvent.click(screen.getByRole("button", { name: /Aumentar Centro de la caja de búsqueda.*Y/i }));
    const y = screen.getByRole("spinbutton", { name: /Centro de la caja de búsqueda.*Y/i }) as HTMLInputElement;
    expect(y.value).toBe("-3");
  });

  it("los selectores de exhaustividad y poses tienen nombre accesible", () => {
    abrir();
    expect(screen.getByRole("combobox", { name: /exhaustividad/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /modos|poses/i })).toBeInTheDocument();
  });

  it("el pH y los procesos también tienen nombre accesible", () => {
    abrir();
    expect(screen.getByRole("spinbutton", { name: /pH de protonación/i })).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: /proces/i })).toBeInTheDocument();
  });
});
