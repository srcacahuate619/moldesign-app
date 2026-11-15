// =====================================================================
// Comparador 3D entre corridas: cada lado elige su evaluación y su pose
// =====================================================================
//
// 1. Cada lado carga las poses y el receptor de SU corrida (task_id), no los de la actual.
// 2. Las poses de cada evaluación se desglosan una a una y elegir una cambia lo que se ve de ese lado.
// 3. Cambiar de evaluación en un lado vuelve a su primera pose y no toca el otro lado.
// 4. La distancia se pide al backend con las corridas y los rangos elegidos, y si se abstiene se dice por qué.
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
  MoleculeViewer3D: ({ poseData }: { poseData: string }) => <pre data-testid="pose-input">{poseData}</pre>,
}));

import { PoseComparisonDialog } from "../PoseComparisonDialog";

const sdf = (id: string, n = 9) => Array.from({ length: n }, (_, i) => `${id}-${i + 1}\nAudit\n\nM  END\n$$$$\n`).join("");
const resultado = (base: number) => ({
  docking_poses: Array.from({ length: 9 }, (_, i) => ({ rank: i + 1, affinity: base + i * 0.1 })),
});
const fuente = (taskId: string, moleculeId = "mol") => ({ taskId, moleculeId, etiqueta: `Corrida ${taskId}` });
const visores = () => screen.getAllByTestId("pose-input");

beforeEach(() => {
  api.poses.mockReset().mockImplementation(async (_m: string, taskId: string) => sdf(taskId));
  api.protein.mockReset().mockImplementation(async (_m: string, taskId: string) => `PROTEIN ${taskId}\nEND\n`);
  api.resultado.mockReset().mockImplementation(async (_m: string, taskId: string) => resultado(taskId === "run-A" ? -7 : -6));
  api.same.mockReset();
  api.run.mockReset().mockResolvedValue({
    frame: "same", a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -6 },
    difference: { b_minus_a_vina_kcal_mol: 1, pose_rmsd_between_runs: { available: true, reason_code: null, rmsd_angstrom: 0.42, heavy_atoms: 10 } },
    protocol_differences: [{ field: "seed", a: 42, b: 7 }],
  });
  api.analog.mockReset();
});
afterEach(cleanup);

const abrir = (extra: Record<string, unknown> = {}) => render(
  <PoseComparisonDialog
    moleculeId="mol" taskId="run-A" leftRank={1} rightRank={1}
    rightSource={fuente("run-B")} runs={[fuente("run-B"), fuente("run-C")]} onClose={() => {}} {...extra}
  />,
);

describe("cada lado enseña lo de su corrida", () => {
  it("izquierda es la actual y derecha la elegida, con su receptor y sus poses", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    expect(visores()[0]).toHaveTextContent("run-A-1");
    expect(visores()[1]).toHaveTextContent("run-B-1");
    expect(api.poses).toHaveBeenCalledWith("mol", "run-A");
    expect(api.poses).toHaveBeenCalledWith("mol", "run-B");
    expect(api.protein).toHaveBeenCalledWith("mol", "run-B");
  });

  it("desglosa las 9 poses de cada evaluación con su energía", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    const grupos = screen.getAllByRole("group", { name: "Poses de esta evaluación" });
    expect(grupos).toHaveLength(2);
    expect(within(grupos[0]).getAllByRole("button")).toHaveLength(9);
    expect(within(grupos[0]).getByRole("button", { name: "Pose n.º 1: -7.00 kcal/mol" })).toBeInTheDocument();
    expect(within(grupos[1]).getByRole("button", { name: "Pose n.º 9: -5.20 kcal/mol" })).toBeInTheDocument();
  });

  it("elegir una pose cambia sólo ese lado y vuelve a medir con esos rangos", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    const derecha = screen.getAllByRole("group", { name: "Poses de esta evaluación" })[1];
    fireEvent.click(within(derecha).getByRole("button", { name: /Pose n\.º 4/ }));
    await waitFor(() => expect(visores()[1]).toHaveTextContent("run-B-4"));
    expect(visores()[0]).toHaveTextContent("run-A-1");
    await waitFor(() => expect(api.run).toHaveBeenLastCalledWith("run-A", "run-B", 1, 4));
  });

  it("cambiar de evaluación en un lado reinicia su pose y no toca el otro", async () => {
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    const derecha = screen.getAllByRole("group", { name: "Poses de esta evaluación" })[1];
    fireEvent.click(within(derecha).getByRole("button", { name: /Pose n\.º 4/ }));
    await waitFor(() => expect(visores()[1]).toHaveTextContent("run-B-4"));

    fireEvent.change(screen.getAllByRole("combobox", { name: "Evaluación" })[1], { target: { value: "run-C" } });
    await waitFor(() => expect(visores()[1]).toHaveTextContent("run-C-1"));
    expect(visores()[0]).toHaveTextContent("run-A-1");
    expect(api.protein).toHaveBeenCalledWith("mol", "run-C");
  });
});

describe("la distancia que acompaña a lo que se ve", () => {
  it("misma molécula: enseña el RMSD y lo que difiere entre las corridas", async () => {
    abrir();
    expect(await screen.findByText("0.42 Å")).toBeInTheDocument();
    expect(api.run).toHaveBeenCalledWith("run-A", "run-B", 1, 1);
    expect(screen.getByText("Semilla")).toBeInTheDocument();
    expect(screen.getByText("42 → 7")).toBeInTheDocument();
  });

  it("con otro receptor no hay distancia y se dice por qué", async () => {
    api.run.mockResolvedValue({
      frame: "different", a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -6 },
      difference: { b_minus_a_vina_kcal_mol: 1, pose_rmsd_between_runs: { available: false, reason_code: "DIFFERENT_RECEPTOR", rmsd_angstrom: null, heavy_atoms: null } },
      protocol_differences: [],
    });
    abrir();
    expect(await screen.findByText(/receptores preparados distintos/)).toBeInTheDocument();
    expect(screen.queryByText(/ Å$/)).toBeNull();
  });

  it("ligandos distintos: pide el núcleo común y dice que no es la molécula entera", async () => {
    api.analog.mockResolvedValue({
      frame: "same", a: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, b: { rank: 1, found: true, vina_affinity_kcal_mol: -7.4 },
      difference: { b_minus_a_vina_kcal_mol: -0.4, affinity_delta_comparable: true, core_rmsd: { available: true, reason_code: null, rmsd_angstrom: 7.3, core_heavy_atoms: 12, core_fraction_of_smaller: 0.92 } },
      protocol_differences: [],
    });
    abrir({ rightSource: fuente("run-X", "otra-molecula") });
    expect(await screen.findByText("7.30 Å")).toBeInTheDocument();
    expect(api.analog).toHaveBeenCalledWith("run-A", "run-X", 1, 1);
    expect(screen.getByText(/núcleo común, no la de la molécula entera/)).toBeInTheDocument();
    expect(screen.getByText(/Núcleo: 12 átomos pesados \(92 % de la molécula menor\)/)).toBeInTheDocument();
  });

  it("misma corrida (el uso de siempre): pide las dos poses de esa corrida", async () => {
    api.same.mockResolvedValue({
      task_id: "run-A", left: { rank: 1, found: true, vina_affinity_kcal_mol: -7 }, right: { rank: 2, found: true, vina_affinity_kcal_mol: -6.9 },
      difference: { right_minus_left_vina_kcal_mol: 0.1, pose_rmsd_between_poses: { available: true, reason_code: null, rmsd_angstrom: 1.5 } },
    });
    render(<PoseComparisonDialog moleculeId="mol" taskId="run-A" leftRank={1} rightRank={2} onClose={() => {}} />);
    expect(await screen.findByText("1.50 Å")).toBeInTheDocument();
    expect(api.same).toHaveBeenCalledWith("run-A", 1, 2);
    expect(screen.queryByRole("combobox", { name: "Evaluación" })).toBeNull();
  });

  it("si el backend falla la medida, el comparador sigue enseñando las poses", async () => {
    api.run.mockRejectedValue(new Error("boom"));
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    await waitFor(() => expect(api.run).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("cuando una evaluación no conserva lo necesario", () => {
  it("dice que falta, sólo en su lado", async () => {
    api.poses.mockImplementation(async (_m: string, taskId: string) => (taskId === "run-B" ? null : sdf(taskId)));
    abrir();
    expect(await screen.findByRole("alert")).toHaveTextContent(/no devolvió un receptor o un archivo de poses/);
    expect(visores()).toHaveLength(1);
  });

  it("sin resultado de la corrida las poses salen igual, sin energía", async () => {
    api.resultado.mockRejectedValue(new Error("no hay"));
    abrir();
    await waitFor(() => expect(visores()).toHaveLength(2));
    const grupos = screen.getAllByRole("group", { name: "Poses de esta evaluación" });
    expect(within(grupos[0]).getAllByRole("button")).toHaveLength(9);
    expect(within(grupos[0]).getByRole("button", { name: "Pose n.º 1" })).toBeInTheDocument();
  });
});
