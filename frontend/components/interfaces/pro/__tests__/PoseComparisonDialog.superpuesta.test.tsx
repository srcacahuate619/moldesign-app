// =====================================================================
// Comparador 3D: superponer las dos poses en un mismo visor
// =====================================================================
//
// 1. Sólo se superpone cuando se sabe que las dos poses comparten receptor preparado: misma corrida, o el backend
//    declara `frame: "same"`. Con otro receptor, con receptor no declarado o si la medida falla, el botón queda
//    apagado y dice por qué. Nunca se dibuja una superposición sin haberlo comprobado.
// 2. En la superposición hay UN visor con el receptor de la izquierda y los dos ligandos; la distancia sigue debajo.
// 3. Cambiar de pose no hace parpadear la vista (el receptor depende de las corridas, no de las poses); cambiar a
//    una corrida con otro receptor devuelve a lado a lado y no vuelve sola.
// 4. Cada ligando se puede ocultar sin tocar el otro.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  poses: vi.fn(), protein: vi.fn(), resultado: vi.fn(), same: vi.fn(), run: vi.fn(), analog: vi.fn(),
}));
vi.mock("../../../../lib/api", () => ({
  getPoseFile: api.poses, getProteinFile: api.protein, getEvaluationResult: api.resultado,
}));
vi.mock("../../../../lib/proApi", () => ({
  getSameRunPoseComparison: api.same, getRunPoseComparison: api.run, getAnalogPoseComparison: api.analog,
}));
vi.mock("../../../MoleculeViewer3D", () => ({
  MoleculeViewer3D: (props: {
    poseData: string; overlayPoseData?: string; proteinData?: string; showPrimaryLigand?: boolean; showOverlayLigand?: boolean;
  }) => (
    <pre
      data-testid="pose-input"
      data-overlay={props.overlayPoseData ?? ""}
      data-protein={props.proteinData ?? ""}
      data-primario={String(props.showPrimaryLigand ?? true)}
      data-superpuesto={String(props.showOverlayLigand ?? true)}
    >
      {props.poseData}
    </pre>
  ),
}));

import { PoseComparisonDialog } from "../PoseComparisonDialog";

const sdf = (id: string, n = 9) => Array.from({ length: n }, (_, i) => `${id}-${i + 1}\nAudit\n\nM  END\n$$$$\n`).join("");
const fuente = (taskId: string, moleculeId = "mol") => ({ taskId, moleculeId, etiqueta: `Corrida ${taskId}` });
const visores = () => screen.getAllByTestId("pose-input");

const medida = (frame: "same" | "different" | "undeclared") => ({
  frame,
  a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 },
  b: { rank: 1, found: true, vina_affinity_kcal_mol: -6 },
  difference: {
    b_minus_a_vina_kcal_mol: 1,
    pose_rmsd_between_runs: frame === "same"
      ? { available: true, reason_code: null, rmsd_angstrom: 0.42, heavy_atoms: 10 }
      : { available: false, reason_code: "DIFFERENT_RECEPTOR", rmsd_angstrom: null, heavy_atoms: null },
  },
  protocol_differences: [],
});

beforeEach(() => {
  api.poses.mockReset().mockImplementation(async (_m: string, taskId: string) => sdf(taskId));
  api.protein.mockReset().mockImplementation(async (_m: string, taskId: string) => `PROTEIN ${taskId}\nEND\n`);
  api.resultado.mockReset().mockResolvedValue({ docking_poses: Array.from({ length: 9 }, (_, i) => ({ rank: i + 1, affinity: -7 + i * 0.1 })) });
  api.same.mockReset();
  api.run.mockReset().mockResolvedValue(medida("same"));
  api.analog.mockReset();
});
afterEach(cleanup);

const abrir = (extra: Record<string, unknown> = {}) => render(
  <PoseComparisonDialog
    moleculeId="mol" taskId="run-A" leftRank={1} rightRank={1}
    rightSource={fuente("run-B")} runs={[fuente("run-B"), fuente("run-C")]} onClose={() => {}} {...extra}
  />,
);
const botonSuperponer = () => screen.getByRole("button", { name: "Superpuestas" });
const superponer = async () => {
  await waitFor(() => expect(botonSuperponer()).toBeEnabled());
  fireEvent.click(botonSuperponer());
};

describe("cuándo se puede superponer", () => {
  it("por defecto es lado a lado, con dos visores, y superponer se habilita al confirmar el receptor", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    expect(screen.getByRole("button", { name: "Lado a lado" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(botonSuperponer()).toBeEnabled());
  });

  it("mientras no se ha comprobado el receptor no se puede superponer, y se dice", () => {
    api.run.mockReturnValue(new Promise(() => {}));
    abrir();
    expect(botonSuperponer()).toBeDisabled();
    expect(screen.getByText(/Comprobando que las dos poses comparten el mismo receptor preparado/)).toBeInTheDocument();
  });

  it("con receptores preparados distintos no se superpone y se explica", async () => {
    api.run.mockResolvedValue(medida("different"));
    abrir();
    expect(await screen.findByText(/No se pueden superponer: cada evaluación usó un receptor preparado distinto/)).toBeInTheDocument();
    expect(botonSuperponer()).toBeDisabled();
    expect(botonSuperponer()).toHaveAccessibleDescription(/receptor preparado distinto/);
  });

  it("si una evaluación no declara su receptor, tampoco", async () => {
    api.run.mockResolvedValue(medida("undeclared"));
    abrir();
    expect(await screen.findByText(/no se pudo comprobar que las dos poses se calcularon contra el mismo receptor/)).toBeInTheDocument();
    expect(botonSuperponer()).toBeDisabled();
  });

  it("si falla la medida no se superpone a ciegas", async () => {
    api.run.mockRejectedValue(new Error("boom"));
    abrir();
    expect(await screen.findByText(/no se pudo comprobar que las dos poses se calcularon contra el mismo receptor/)).toBeInTheDocument();
    expect(botonSuperponer()).toBeDisabled();
  });

  it("dos poses de la misma corrida comparten receptor por construcción", async () => {
    api.same.mockResolvedValue({
      task_id: "run-A", left: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, right: { rank: 2, found: true, vina_affinity_kcal_mol: -6.9 },
      difference: { right_minus_left_vina_kcal_mol: 0.1, pose_rmsd_between_poses: { available: true, reason_code: null, rmsd_angstrom: 1.5 } },
    });
    render(<PoseComparisonDialog moleculeId="mol" taskId="run-A" leftRank={1} rightRank={2} onClose={() => {}} />);
    await superponer();
    expect(visores()).toHaveLength(1);
    expect(visores()[0]).toHaveTextContent("run-A-1");
    expect(visores()[0]).toHaveAttribute("data-overlay", expect.stringContaining("run-A-2"));
  });

  it("ligandos distintos en el mismo receptor sí se superponen (el núcleo común se mide aparte)", async () => {
    api.analog.mockResolvedValue({
      frame: "same", a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -7.4 },
      difference: { b_minus_a_vina_kcal_mol: -0.4, affinity_delta_comparable: true, core_rmsd: { available: true, reason_code: null, rmsd_angstrom: 1.1, core_heavy_atoms: 12, core_fraction_of_smaller: 0.9 } },
      protocol_differences: [],
    });
    abrir({ rightSource: fuente("run-X", "otra-molecula") });
    await superponer();
    expect(visores()[0]).toHaveAttribute("data-overlay", expect.stringContaining("run-X-1"));
  });
});

describe("la vista superpuesta", () => {
  it("es un solo visor: receptor y pose de la izquierda, y la de la derecha encima", async () => {
    abrir();
    await superponer();
    await waitFor(() => expect(visores()).toHaveLength(1));
    const visor = visores()[0];
    expect(visor).toHaveTextContent("run-A-1");
    expect(visor).toHaveAttribute("data-overlay", expect.stringContaining("run-B-1"));
    expect(visor).toHaveAttribute("data-protein", expect.stringContaining("PROTEIN run-A"));
    expect(botonSuperponer()).toHaveAttribute("aria-pressed", "true");
  });

  it("conserva a la vista la distancia y avisa de que parecerse no valida", async () => {
    abrir();
    await superponer();
    expect(await screen.findByText("0.42 Å")).toBeInTheDocument();
    expect(screen.getByText(/Que se parezcan a simple vista no valida ninguna de las dos/)).toBeInTheDocument();
  });

  it("sigue eligiendo evaluación y pose de cada lado, y el visor las enseña", async () => {
    abrir();
    await superponer();
    const grupos = screen.getAllByRole("group", { name: "Poses de esta evaluación" });
    expect(grupos).toHaveLength(2);
    fireEvent.click(within(grupos[1]).getByRole("button", { name: /Pose n\.º 4/ }));
    await waitFor(() => expect(visores()[0]).toHaveAttribute("data-overlay", expect.stringContaining("run-B-4")));
    // Cambiar de pose repite la medida pero no tira la vista superpuesta.
    await waitFor(() => expect(api.run).toHaveBeenLastCalledWith("run-A", "run-B", 1, 4));
    expect(botonSuperponer()).toHaveAttribute("aria-pressed", "true");
    expect(visores()).toHaveLength(1);
  });

  it("cada ligando se oculta sin tocar el otro", async () => {
    abrir();
    await superponer();
    fireEvent.click(screen.getByRole("checkbox", { name: "Mostrar la pose: Derecha" }));
    expect(visores()[0]).toHaveAttribute("data-superpuesto", "false");
    expect(visores()[0]).toHaveAttribute("data-primario", "true");
    fireEvent.click(screen.getByRole("checkbox", { name: "Mostrar la pose: Izquierda" }));
    expect(visores()[0]).toHaveAttribute("data-primario", "false");
  });

  it("cambiar a una evaluación con otro receptor vuelve a lado a lado y no regresa sola", async () => {
    api.run.mockImplementation(async (_a: string, b: string) => medida(b === "run-C" ? "different" : "same"));
    abrir();
    await superponer();
    await waitFor(() => expect(visores()).toHaveLength(1));

    const selector = screen.getAllByRole("combobox", { name: "Evaluación" })[1];
    fireEvent.change(selector, { target: { value: "run-C" } });
    expect(await screen.findByText(/No se pueden superponer: cada evaluación usó un receptor preparado distinto/)).toBeInTheDocument();
    await waitFor(() => expect(visores()).toHaveLength(2));
    expect(screen.getByRole("button", { name: "Lado a lado" })).toHaveAttribute("aria-pressed", "true");

    // Al volver a una evaluación compatible se puede superponer otra vez, pero hay que pedirlo.
    fireEvent.change(screen.getAllByRole("combobox", { name: "Evaluación" })[1], { target: { value: "run-B" } });
    await waitFor(() => expect(botonSuperponer()).toBeEnabled());
    expect(visores()).toHaveLength(2);
  });

  it("si una evaluación no conserva sus archivos lo dice en su tarjeta y no dibuja la mitad", async () => {
    api.poses.mockImplementation(async (_m: string, taskId: string) => (taskId === "run-B" ? null : sdf(taskId)));
    abrir();
    expect(await screen.findByRole("alert")).toHaveTextContent(/no devolvió un receptor o un archivo de poses/);
    await waitFor(() => expect(botonSuperponer()).toBeEnabled());
    fireEvent.click(botonSuperponer());
    expect(screen.queryByTestId("pose-input")).toBeNull();
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });
});

describe("la ficha de quien abre el comparador (el SAR: lo que antes era un modal)", () => {
  const conFicha = () => abrir({ ficha: <section data-testid="ficha-del-analogo">SMILES del análogo</section> });

  it("se pinta dentro del diálogo, debajo de los visores", async () => {
    conFicha();
    await waitFor(() => expect(visores()).toHaveLength(2));
    const ficha = screen.getByTestId("ficha-del-analogo");
    expect(within(screen.getByRole("dialog")).getByTestId("ficha-del-analogo")).toBe(ficha);
    const ultimoVisor = visores()[1];
    expect(ultimoVisor.compareDocumentPosition(ficha) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("sigue ahí al superponer las poses", async () => {
    conFicha();
    await superponer();
    await waitFor(() => expect(visores()).toHaveLength(1));
    expect(screen.getByTestId("ficha-del-analogo")).toBeInTheDocument();
  });

  it("sin ficha el diálogo es el de siempre", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    expect(screen.queryByTestId("ficha-del-analogo")).toBeNull();
  });
});
