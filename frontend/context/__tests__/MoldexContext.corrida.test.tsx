import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
const api = vi.hoisted(() => ({ list: vi.fn(), protein: vi.fn(), pose: vi.fn() }));
vi.mock("../../lib/api", () => ({ getMoldex: api.list, getProteinFile: api.protein, getPoseFile: api.pose }));
import { MoldexProvider, useMoldex } from "../MoldexContext";
function Consumer() {
  const state = useMoldex();
  return <><button onClick={() => state.selectMolecule("mol:run-A")}>A</button><button onClick={() => state.selectMolecule("mol:run-B")}>B</button><pre>{state.proteinData}</pre><output>{state.error}</output></>;
}
beforeEach(() => {
  api.list.mockReset().mockResolvedValue({ results: [
    { id: "mol", entry_id: "mol:run-A", provenance: { task_id: "run-A" } },
    { id: "mol", entry_id: "mol:run-B", provenance: { task_id: "run-B" } },
  ] });
  api.protein.mockReset().mockImplementation(async (_mid: string, task: string) => `PROTEIN-${task}`);
  api.pose.mockReset().mockImplementation(async (_mid: string, task: string) => `POSE-${task}`);
});
describe("la caché de Moldex separa las corridas", () => {
  it("las dos fichas cargan recursos propios y volver a A recupera sólo su caché", async () => {
    render(<MoldexProvider><Consumer /></MoldexProvider>);
    await screen.findByText("PROTEIN-run-A");
    fireEvent.click(screen.getByRole("button", { name: "B" }));
    await screen.findByText("PROTEIN-run-B");
    expect(api.protein).toHaveBeenCalledWith("mol", "run-B");
    expect(api.pose).toHaveBeenCalledWith("mol", "run-B");
    fireEvent.click(screen.getByRole("button", { name: "A" }));
    await screen.findByText("PROTEIN-run-A");
    expect(api.protein).toHaveBeenCalledTimes(2);
  });
  it("sin task_id no descarga el receptor vigente", async () => {
    api.list.mockResolvedValue({ results: [{ id: "mol", entry_id: "legacy", provenance: {} }] });
    render(<MoldexProvider><Consumer /></MoldexProvider>);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/La ficha no identifica una corrida/));
    expect(api.protein).not.toHaveBeenCalled(); expect(api.pose).not.toHaveBeenCalled();
  });
});
