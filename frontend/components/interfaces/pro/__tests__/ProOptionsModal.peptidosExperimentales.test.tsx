import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

// Mismo andamiaje que AdmetOptIn.test.tsx: el modal monta un Canvas de three.js que jsdom no tiene.
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
  encenderMotor: vi.fn(async () => ({})),
  // Por defecto: Vina listo y ESMFold instalado y apagado (la corrida lo enciende al empezar).
  inventarioDeMotores: vi.fn(async () => ({
    docking: [
      { id: "vina", etiqueta: "AutoDock Vina 1.2.7", estado: "listo", disponible: true, requiere: "binario_empaquetado", motivo: null, accion: null },
    ],
    peptido: [
      {
        id: "esmfold",
        etiqueta: "ESMFold",
        estado: "instalado_apagado",
        disponible: false,
        requiere: "descarga_bajo_demanda",
        motivo: "ESMFold está instalado y apagado.",
        accion: "encender",
      },
    ],
  })),
}));

import { inventarioDeMotores } from "../../../../lib/api";
import ProOptionsModal from "../ProOptionsModal";

beforeAll(() => {
  if (typeof Element.prototype.animate !== "function") {
    Element.prototype.animate = (() => ({
      cancel: () => {},
      finish: () => {},
      finished: Promise.resolve(),
    })) as unknown as Element["animate"];
  }
});

type Inventario = Awaited<ReturnType<typeof inventarioDeMotores>>;

const VINA = {
  id: "vina",
  etiqueta: "AutoDock Vina 1.2.7",
  estado: "listo",
  disponible: true,
  requiere: "binario_empaquetado",
  motivo: null,
  accion: null,
  bytes_descarga: 0,
  archivos_faltantes: [],
  dependencias_faltantes: [],
  modulo_launcher: null,
};

/** Abre el modal con un inventario concreto y espera a que el backend responda. */
async function abrir(peptido?: Inventario["peptido"]) {
  if (peptido) {
    vi.mocked(inventarioDeMotores).mockResolvedValueOnce({ docking: [VINA], peptido });
  }
  const onApply = vi.fn();
  render(<ProOptionsModal isOpen onClose={() => {}} onApply={onApply} />);
  await waitFor(() => expect(radio(/AutoDock Vina/)).not.toBeDisabled());
  return { onApply };
}

const radio = (nombre: RegExp) => screen.getByRole("radio", { name: nombre });

/**
 * La vía de péptidos se marca EXPERIMENTAL en el selector de motores (decisión del 2026-10-04).
 * AGENTS.md: está probado que ESMFold carga y sirve poses, no que las poses sean buenas.
 */
describe("selector de motores: péptidos experimentales", () => {
  it("la tarjeta de ESMFold se marca EXPERIMENTAL a la vista", async () => {
    await abrir();
    expect(radio(/ESMFold/)).toHaveAccessibleName(/experimental/i);
  });

  it("el aviso completo se lee en la ayuda de ESMFold, también con una molécula pequeña", async () => {
    await abrir();
    expect(screen.queryByText(/su calidad no está validada en MolDesign/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Más información sobre ESMFold" }));
    const ayuda = screen.getByRole("dialog", { name: "ESMFold" });
    expect(ayuda).toHaveTextContent(
      /Experimental: ESMFold predice la estructura del péptido y su calidad no está validada en MolDesign/,
    );
    // La decisión sigue siendo del investigador: la ayuda lo dice y nada se deshabilita.
    expect(ayuda).toHaveTextContent(/La decisión es tuya/);
  });
});

describe("ESMFold se usa como cualquier motor, sin depender de la molécula", () => {
  it("instalado y apagado se puede elegir: no hay bloqueo por «auto-detecta»", async () => {
    await abrir();
    await waitFor(() => expect(radio(/ESMFold/)).not.toBeDisabled());
    expect(screen.queryByText(/auto-detecta/i)).toBeNull();
  });

  it("no hay botón «Encender»: la corrida lo enciende al empezar", async () => {
    await abrir();
    expect(screen.queryByRole("button", { name: /encender/i })).toBeNull();
  });

  it("sin descargar, ESMFold queda deshabilitado y enlaza el gestor de modelos", async () => {
    await abrir([
      {
        id: "esmfold",
        etiqueta: "ESMFold",
        estado: "no_instalado",
        disponible: false,
        requiere: "descarga_bajo_demanda",
        motivo: "ESMFold no está instalado en este equipo.",
        accion: "descargar",
        bytes_descarga: 8442062570,
        archivos_faltantes: ["esmfold/models/pytorch_model.bin"],
        dependencias_faltantes: [],
        modulo_launcher: "esmfold-weights",
      },
    ]);
    await waitFor(() => expect(screen.getByRole("link", { name: /Abrir gestor/ })).toBeInTheDocument());
    expect(radio(/ESMFold/)).toBeDisabled();
  });

  it("Vina y ESMFold se intercambian: se aplica lo último que se eligió", async () => {
    const { onApply } = await abrir();
    await waitFor(() => expect(radio(/ESMFold/)).not.toBeDisabled());

    fireEvent.click(radio(/ESMFold/));
    fireEvent.click(screen.getByRole("button", { name: /Aplicar configuración/ }));
    expect(onApply.mock.calls[0][0]).toMatchObject({ engine: "vina", peptideEngine: "esmfold" });
  });

  it("volver a Vina quita el plegado previo", async () => {
    const { onApply } = await abrir();
    await waitFor(() => expect(radio(/ESMFold/)).not.toBeDisabled());

    fireEvent.click(radio(/ESMFold/));
    fireEvent.click(radio(/AutoDock Vina/));
    fireEvent.click(screen.getByRole("button", { name: /Aplicar configuración/ }));
    expect(onApply.mock.calls[0][0]).toMatchObject({ engine: "vina", peptideEngine: null });
  });

  it("el muestreo sigue visible al cambiar de ruta y no ofrece la precisión GNN legacy", async () => {
    await abrir();
    await waitFor(() => expect(radio(/ESMFold/)).not.toBeDisabled());
    expect(screen.queryByText("Precisión GNN")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Varios confórmeros" }));

    fireEvent.click(radio(/ESMFold/));
    expect(screen.queryByText("Precisión GNN")).toBeNull();
    expect(screen.getByRole("spinbutton", { name: "Número de confórmeros" })).toHaveValue(30);
  });

  it("la plaza del motor externo está a la vista y no se puede elegir sin conexión", async () => {
    await abrir();
    expect(screen.getByTestId("plaza-motor-api")).toHaveTextContent(/Vía API/);
    expect(screen.getByTestId("plaza-motor-api")).toHaveTextContent(/Sin conectar/);
    expect(screen.queryByRole("radio", { name: /Vía API/ })).toBeNull();
  });

  it("no aparecen motores que esta versión no ejecuta", async () => {
    await abrir();
    expect(screen.queryByText(/QuickVina|DiffDock|ColabFold|RFdiffusion|ESMFold Pro/)).toBeNull();
  });
});
