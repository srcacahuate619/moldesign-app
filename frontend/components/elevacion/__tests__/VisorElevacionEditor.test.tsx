import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { fetchBackend } from "../../../lib/backendFetch";
import VisorElevacionEditor from "../VisorElevacionEditor";

vi.mock("../../../lib/backendFetch", () => ({ fetchBackend: vi.fn() }));
vi.mock("../../../lib/api", () => ({ getAuthHeaders: () => ({}) }));
vi.mock("../../../context/LanguageContext", () => {
  const t = (clave: string) => clave;
  return { useLanguage: () => ({ t }) };
});

const modelo = {
  contrato: "elevacion/v1",
  fuente: "conformador_calculado",
  lienzo: 300,
  svg: "<svg/>",
  atomos: [
    { elemento: "C", carga: 0, hidrogenos: 3, plano: [100, 160], xyz: [102, 158, -20] },
    { elemento: "O", carga: 0, hidrogenos: 1, plano: [150, 130], xyz: [149, 131, 15] },
  ],
  enlaces: [{ a: 0, b: 1, orden: 1 }],
  desajuste_px: 2,
  enlace_px: 30,
  razon_enlaces: 0.07,
  fiel: true,
};

function respuesta(): Response {
  return { ok: true, status: 200, json: async () => modelo } as unknown as Response;
}

function visor(smiles: string, activo: boolean) {
  return <VisorElevacionEditor smiles={smiles} activo={activo} onSwitchViewer={() => {}} />;
}

describe("VisorElevacionEditor: no recalcula lo ya visto", () => {
  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
    vi.mocked(fetchBackend).mockResolvedValue(respuesta());
    // jsdom no siempre trae el bucle de animación: se sustituye por temporizadores.
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16));
    vi.stubGlobal("cancelAnimationFrame", (id: number) => window.clearTimeout(id));
  });

  afterEach(() => {
    cleanup(); // antes de quitar los dobles: un fotograma pendiente no debe encontrarse sin requestAnimationFrame
    vi.unstubAllGlobals();
  });

  it("al volver a montarlo, la molécula ya levantada aparece sin pedirla ni mostrar el cálculo", async () => {
    const primera = render(visor("CCO-visor-remontar", true));
    expect(await screen.findByText("el_pausar")).toBeTruthy();
    // Una semilla primero y las tres después: dos peticiones, y sólo la completa se guarda.
    await vi.waitFor(() => expect(fetchBackend).toHaveBeenCalledTimes(2));
    primera.unmount();

    // Lo que hace el editor al volver de Ketcher cuando el visor se remontaba.
    render(visor("CCO-visor-remontar", true));

    expect(screen.getByText("el_pausar")).toBeTruthy();
    expect(screen.queryByText("el_cargando")).toBeNull();
    expect(fetchBackend).toHaveBeenCalledTimes(2);
  });

  it("oculto no pide nada aunque cambie la molécula: pide la nueva al mostrarse", async () => {
    const { rerender } = render(visor("CCO-visor-oculto", false));
    rerender(visor("CCN-visor-oculto", false));
    expect(fetchBackend).not.toHaveBeenCalled();

    rerender(visor("CCN-visor-oculto", true));
    expect(await screen.findByText("el_pausar")).toBeTruthy();
    await vi.waitFor(() => expect(fetchBackend).toHaveBeenCalledTimes(2));
    expect(vi.mocked(fetchBackend).mock.calls.every((c) => String(c[1]?.body).includes("CCN-visor-oculto"))).toBe(true);
  });
});

describe("VisorElevacionEditor: vista «Se acoplará»", () => {
  const acoplada = {
    ...modelo,
    fuente: "especie_acoplada",
    atomos: [modelo.atomos[0], { ...modelo.atomos[1], carga: -1, hidrogenos: 0 }],
    especie_acoplada: {
      smiles: "C[O-]",
      ph: 7.4,
      aviso_de_ph: null,
      protonacion: { aplicada: true, motor: "dimorphite-dl", alternativas: 2, motivo: null },
      tautomero: { modo: "entrada", aplicada: false, alternativas: 1, motivo: null },
      conformador: { semilla: 42, campo_de_fuerza: "MMFF94", convergio: true },
      sdf_sha256: null,
      cambios: { atomos: [{ atomo: 1, carga: [0, -1], hidrogenos: [1, 0] }], enlaces: [] },
      estereo: { declarados: 0, conservados: 0, invertidos: [], no_asignables: [], sin_declarar: [] },
      contraiones: [],
    },
  };

  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
    vi.mocked(fetchBackend).mockImplementation(async (_ruta, init) => {
      const cuerpo = JSON.parse(String(init?.body));
      return { ok: true, status: 200, json: async () => (cuerpo.vista === "acoplada" ? acoplada : modelo) } as unknown as Response;
    });
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16));
    vi.stubGlobal("cancelAnimationFrame", (id: number) => window.clearTimeout(id));
  });

  afterEach(() => {
    cleanup(); // antes de quitar los dobles: un fotograma pendiente no debe encontrarse sin requestAnimationFrame
    vi.unstubAllGlobals();
  });

  it("prepara con el pH y el tautómero de la corrida, lista lo que cambió y volver a «Escrita» no recalcula", async () => {
    render(
      <VisorElevacionEditor smiles="CO-visor-acoplada" activo onSwitchViewer={() => {}}
        preparacion={{ ph: 6.8, tautomero: "canonico" }} />,
    );
    expect(await screen.findByText("el_pausar")).toBeTruthy();
    await vi.waitFor(() => expect(fetchBackend).toHaveBeenCalledTimes(2));

    fireEvent.click(screen.getByText("el_vista_acoplada"));

    expect(await screen.findByTestId("cambios-de-la-preparacion")).toBeTruthy();
    expect(screen.getByText("el_cambio_atomo")).toBeTruthy();
    expect(screen.getByText("el_acoplada_titulo")).toBeTruthy();
    const cuerpos = vi.mocked(fetchBackend).mock.calls.map((c) => JSON.parse(String(c[1]?.body)));
    expect(cuerpos[2]).toEqual({ smiles: "CO-visor-acoplada", vista: "acoplada", ph: 6.8, tautomero: "canonico" });

    fireEvent.click(screen.getByText("el_vista_escrita"));
    expect(screen.queryByTestId("cambios-de-la-preparacion")).toBeNull();
    expect(fetchBackend).toHaveBeenCalledTimes(3);
  });
});

describe("VisorElevacionEditor: «Escrita» por etapas y dibujo de Ketcher", () => {
  beforeEach(() => {
    vi.mocked(fetchBackend).mockReset();
    vi.mocked(fetchBackend).mockImplementation(async (_ruta, init) => {
      const cuerpo = JSON.parse(String(init?.body));
      const respuesta = { ...modelo, abstencion_provisional: Boolean(cuerpo.rapida), geometria: { espesor_A: 0, plana: true, macrociclos: [], anillos_rigidos_grandes: [] } };
      return { ok: true, status: 200, json: async () => respuesta } as unknown as Response;
    });
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => window.setTimeout(() => cb(performance.now()), 16));
    vi.stubGlobal("cancelAnimationFrame", (id: number) => window.clearTimeout(id));
  });

  afterEach(() => {
    cleanup(); // antes de quitar los dobles: un fotograma pendiente no debe encontrarse sin requestAnimationFrame
    vi.unstubAllGlobals();
  });

  it("enseña primero una semilla, dice que es provisional y la sustituye por las tres", async () => {
    render(<VisorElevacionEditor smiles="CCO-etapas" activo onSwitchViewer={() => {}} molfile="dibujo" />);

    expect(await screen.findByText("el_pausar")).toBeTruthy();
    await vi.waitFor(() => expect(fetchBackend).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(screen.queryByText("el_provisional")).toBeNull());
    const cuerpos = vi.mocked(fetchBackend).mock.calls.map((c) => JSON.parse(String(c[1]?.body)));
    expect(cuerpos).toEqual([
      { smiles: "CCO-etapas", molfile: "dibujo", rapida: true },
      { smiles: "CCO-etapas", molfile: "dibujo" },
    ]);
    expect(screen.getByText("el_plana")).toBeTruthy();
  });
});
