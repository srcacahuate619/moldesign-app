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
  inventarioDeMotores: vi.fn(async () => ({
    docking: [
      { id: "vina", etiqueta: "AutoDock Vina 1.2.7", estado: "listo", disponible: true, requiere: "binario_empaquetado", motivo: null, accion: null },
    ],
    peptido: [],
  })),
}));

import ProOptionsModal, { type AdvancedConfig } from "../ProOptionsModal";

beforeAll(() => {
  if (typeof Element.prototype.animate !== "function") {
    Element.prototype.animate = (() => ({
      cancel: () => {},
      finish: () => {},
      finished: Promise.resolve(),
    })) as unknown as Element["animate"];
  }
});

async function abrir(props: Partial<React.ComponentProps<typeof ProOptionsModal>> = {}) {
  const onClose = vi.fn();
  render(<ProOptionsModal isOpen onClose={onClose} onApply={() => {}} {...props} />);
  // Hasta que llega el inventario no se puede asegurar nada del menú de motores.
  await waitFor(() => expect(screen.getByRole("radio", { name: /AutoDock Vina/ })).not.toBeDisabled());
  return { onClose };
}

const botonAyuda = (parametro: string) =>
  screen.getByRole("button", { name: `Más información sobre ${parametro}` });

/**
 * El diálogo de «Parámetros de la evaluación» tenía párrafos explicativos permanentes bajo cada
 * parámetro. Decisión del propietario (2026-10-07): se leen con un «?». Estas pruebas fijan que el
 * texto sigue existiendo —no se perdió ninguna explicación— pero no ocupa sitio hasta pedirlo.
 */
describe("ayuda de cada parámetro (el «?»)", () => {
  const temas: Array<[string, string, RegExp]> = [
    ["pH de protonación", "pH de protonación", /especie química/],
    ["tautómero", "Tautómero del ligando", /Por defecto se acopla el tautómero escrito/],
    ["selectividad", "Selectividad anti-diana", /hERG, 5-HT2B/],
    ["ADMET", "Perfil ADMET", /Módulo experimental/],
    ["caja de búsqueda", "Parámetros del bolsillo", /región del espacio donde Vina buscará poses/],
    ["confórmeros", "Generación conformacional", /Compra amplitud de búsqueda, no precisión/],
  ];

  it.each(temas)("%s: el texto no está a la vista y aparece al pulsar el «?»", async (_n, parametro, texto) => {
    await abrir();
    expect(screen.queryByText(texto)).toBeNull();

    fireEvent.click(botonAyuda(parametro));
    const ayuda = screen.getByRole("dialog", { name: parametro });
    expect(ayuda).toHaveTextContent(texto);
  });

  it("cada «?» tiene nombre accesible y no sobra ni falta ninguno", async () => {
    await abrir();
    // pH, tautómero, selectividad, ADMET, caja, ESMFold y confórmeros.
    expect(screen.getAllByRole("button", { name: /^Más información sobre / })).toHaveLength(7);
  });

  it("los residuos de referencia y la caja fijada también se explican con «?»", async () => {
    await abrir({
      systemSealed: true,
      targetHotspots: [{ name: "HIS41", importance: 1 }],
    });

    fireEvent.click(botonAyuda("Residuos del sitio activo (hotspots)"));
    const residuos = screen.getByRole("dialog", { name: "Residuos del sitio activo (hotspots)" });
    // SOL-09: la advertencia científica sigue ahí, y con el sistema fijado se añade el motivo.
    expect(residuos).toHaveTextContent(/No guían la búsqueda de Vina/);
    expect(residuos).toHaveTextContent(/Fijados por la primera corrida/);

    fireEvent.click(screen.getByRole("button", { name: "Cerrar ayuda" }));
    // El título de la caja fijada se queda a la vista; el detalle, no.
    expect(screen.getByText("Caja y residuos fijados")).toBeInTheDocument();
    expect(screen.queryByText(/Una corrida de este caso ya terminó/)).toBeNull();
    fireEvent.click(botonAyuda("Caja y residuos fijados"));
    expect(screen.getByRole("dialog", { name: "Caja y residuos fijados" })).toHaveTextContent(
      /Una corrida de este caso ya terminó/,
    );
  });

  it("lo que cambia con el estado sigue a la vista: un pH fuera de 7.4 avisa sin abrir nada", async () => {
    const base: AdvancedConfig = {
      protonationPh: 6.5,
      numWorkers: 4,
      parallelDocks: 2,
      enableSelectivity: false,
      selectedAntiTargets: [],
      enableMMGBSA: false,
      mmgbsaSteps: 1000,
      enableADMET: false,
    };
    await abrir({ initialAdvanced: base });
    expect(screen.getByText(/Fuera del pH fisiológico/)).toBeInTheDocument();
  });
});

describe("borrador de generación conformacional", () => {
  it("parte de un confórmero y sólo guarda el número elegido al aplicar", async () => {
    const onApply = vi.fn();
    await abrir({ onApply });
    expect(screen.queryByText(/Precisión GNN|FP32|FP16/)).toBeNull();
    expect(screen.getByRole("button", { name: "Confórmero único" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("spinbutton", { name: "Número de confórmeros" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Varios confórmeros" }));
    const numero = screen.getByRole("spinbutton", { name: "Número de confórmeros" });
    expect(numero).toHaveValue(30);
    fireEvent.change(numero, { target: { value: "12" } });
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Aplicar configuración" }));
    expect(onApply.mock.calls[0][4]).toBe(12);
  });

  it("cancelar descarta el borrador y reabrir restaura el K vigente del caso", async () => {
    const onApply = vi.fn();
    const onClose = vi.fn();
    const props = { isOpen: true, onApply, onClose, initialConformers: 12 };
    const { rerender } = render(<ProOptionsModal {...props} />);
    fireEvent.change(screen.getByRole("spinbutton", { name: "Número de confórmeros" }), { target: { value: "18" } });
    fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onApply).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledOnce();
    rerender(<ProOptionsModal {...props} isOpen={false} />);
    rerender(<ProOptionsModal {...props} initialConformers={24} />);
    expect(screen.getByRole("spinbutton", { name: "Número de confórmeros" })).toHaveValue(24);
    fireEvent.click(screen.getByRole("button", { name: "Aplicar configuración" }));
    expect(onApply.mock.calls[0][4]).toBe(24);
  });

  it("volver a confórmero único aplica 1 y oculta el contador", async () => {
    const onApply = vi.fn();
    await abrir({ onApply, initialConformers: 30, systemSealed: true });
    fireEvent.click(screen.getByRole("button", { name: "Confórmero único" }));
    expect(screen.queryByRole("spinbutton", { name: "Número de confórmeros" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Aplicar configuración" }));
    expect(onApply.mock.calls[0][4]).toBe(1);
  });

  it.each(["1", "65", "2.5"])("rechaza %s sin cambiar el número que se aplicará", async (value) => {
    const onApply = vi.fn();
    await abrir({ onApply, initialConformers: 30 });
    const numero = screen.getByRole("spinbutton", { name: "Número de confórmeros" });
    fireEvent.change(numero, { target: { value } });
    expect(numero).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent(/Se conserva 30/);
    fireEvent.click(screen.getByRole("button", { name: "Aplicar configuración" }));
    expect(onApply.mock.calls[0][4]).toBe(30);
  });
});

describe("cerrar la ayuda", () => {
  it("Escape cierra la ayuda y no el diálogo de parámetros; el segundo Escape sí lo cierra", async () => {
    const { onClose } = await abrir();
    fireEvent.click(botonAyuda("pH de protonación"));
    expect(screen.getByRole("dialog", { name: "pH de protonación" })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "pH de protonación" })).toBeNull();
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("al cerrar, el foco vuelve al «?» que la abrió", async () => {
    await abrir();
    const boton = botonAyuda("pH de protonación");
    fireEvent.click(boton);
    expect(screen.getByRole("button", { name: "Cerrar ayuda" })).toHaveFocus();

    fireEvent.click(screen.getByRole("button", { name: "Cerrar ayuda" }));
    expect(screen.queryByRole("dialog", { name: "pH de protonación" })).toBeNull();
    expect(boton).toHaveFocus();
  });

  it("al cerrar el diálogo de parámetros no queda una ayuda huérfana", async () => {
    const onClose = vi.fn();
    const { rerender } = render(<ProOptionsModal isOpen onClose={onClose} onApply={() => {}} />);
    await waitFor(() => expect(screen.getByRole("radio", { name: /AutoDock Vina/ })).not.toBeDisabled());
    fireEvent.click(botonAyuda("pH de protonación"));

    rerender(<ProOptionsModal isOpen={false} onClose={onClose} onApply={() => {}} />);
    rerender(<ProOptionsModal isOpen onClose={onClose} onApply={() => {}} />);
    expect(screen.queryByRole("dialog", { name: "pH de protonación" })).toBeNull();
  });
});
