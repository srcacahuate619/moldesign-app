import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ poses: vi.fn(), protein: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ getPoseFile: api.poses, getProteinFile: api.protein }));
vi.mock("../../../MoleculeViewer3D", () => ({
  MoleculeViewer3D: ({ poseData }: { poseData: string }) => <pre data-testid="pose-input">{poseData}</pre>,
}));
import { PoseComparisonDialog } from "../PoseComparisonDialog";

const sdf = (id: string) => [1, 2].map(rank => `${id}-${rank}\nAudit\n\nM  END\n$$$$\n`).join("");
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}

beforeEach(() => {
  api.poses.mockReset().mockImplementation(async (_id: string, taskId: string) => sdf(taskId));
  api.protein.mockReset().mockResolvedValue("HEADER PROTEIN\nEND\n");
});

describe("coordenadas de la corrida elegida en el comparador", () => {
  it("pide las poses con task_id y actualiza al cambiar sólo de corrida", async () => {
    const view = render(<PoseComparisonDialog moleculeId="mol" taskId="run-A" leftRank={1} rightRank={2} onClose={() => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("pose-input")).toHaveLength(2));
    expect(api.poses).toHaveBeenCalledWith("mol", "run-A");
    expect(api.protein).toHaveBeenCalledWith("mol", "run-A");
    expect(screen.getAllByTestId("pose-input")[0]).toHaveTextContent("run-A-1");
    view.rerender(<PoseComparisonDialog moleculeId="mol" taskId="run-B" leftRank={1} rightRank={2} onClose={() => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("pose-input")[0]).toHaveTextContent("run-B-1"));
    expect(api.poses).toHaveBeenCalledWith("mol", "run-B");
    expect(api.protein).toHaveBeenCalledWith("mol", "run-B");
  });

  it("una respuesta tardía de A no sustituye las coordenadas de B", async () => {
    const a = deferred<string>();
    api.poses.mockImplementation((_id: string, taskId: string) => taskId === "run-A" ? a.promise : Promise.resolve(sdf("run-B")));
    const view = render(<PoseComparisonDialog moleculeId="mol" taskId="run-A" leftRank={1} rightRank={2} onClose={() => {}} />);
    view.rerender(<PoseComparisonDialog moleculeId="mol" taskId="run-B" leftRank={1} rightRank={2} onClose={() => {}} />);
    await waitFor(() => expect(screen.getAllByTestId("pose-input")[0]).toHaveTextContent("run-B-1"));
    await act(async () => { a.resolve(sdf("run-A")); });
    expect(screen.getAllByTestId("pose-input")[0]).toHaveTextContent("run-B-1");
    expect(screen.getAllByTestId("pose-input")[0]).not.toHaveTextContent("run-A");
  });
});
