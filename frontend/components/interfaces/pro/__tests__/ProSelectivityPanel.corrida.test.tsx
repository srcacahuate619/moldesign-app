import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ read: vi.fn(), dock: vi.fn(), save: vi.fn() }));
vi.mock("../../../../lib/api", () => ({ getEvaluationResult: api.read }));
vi.mock("../../../../lib/proApi", () => ({ dockSingleAntiTarget: api.dock, saveSelectivityResults: api.save }));
vi.mock("../../../../lib/antiDianas", async (importOriginal) => ({
  ...await importOriginal<Record<string, unknown>>(),
  useAntiDianas: () => ({
    targets: [{ pdb_id: "5VA1", name: "hERG", category: "Cardiac", threshold_kcal: -7, por_defecto: true, disponible: true }],
    error: null, loading: false, retry: () => {},
  }),
}));
import { ProSelectivityPanel } from "../ProSelectivityPanel";

const result = (taskId: string, affinity: number) => ({ task_id: taskId, selectivity_ran: true,
  anti_target_results: [{ pdb_id: "5VA1", affinity, status: "ok", threshold: -7 }],
});
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
beforeEach(() => {
  api.read.mockReset(); api.dock.mockReset(); api.save.mockReset().mockResolvedValue({ success: true });
});

describe("la selectividad se recupera para la corrida seleccionada", () => {
  it("una acción y su guardado conservan task_id", async () => {
    api.read.mockResolvedValue({ task_id: "run-A", anti_target_results: [] });
    api.dock.mockResolvedValue({ target: { ...result("run-A", -4).anti_target_results[0], task_id: "run-A" } });
    render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" onTargetAffinity={-6.6} />);
    fireEvent.click(screen.getByRole("button", { name: "Evaluar seleccionadas (1)" }));
    await waitFor(() => expect(api.save).toHaveBeenCalledOnce());
    expect(api.dock).toHaveBeenCalledWith("mol", "5VA1", "run-A");
    expect(api.save.mock.calls[0][1].task_id).toBe("run-A");
  });

  it("una respuesta de acción de otra corrida conserva la afinidad histórica", async () => {
    api.dock.mockResolvedValue({ target: { ...result("run-B", -11).anti_target_results[0], task_id: "run-B" } });
    render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" initialResult={{ off_targets: result("run-A", -4).anti_target_results }} />);
    fireEvent.click(screen.getByRole("button", { name: "Reevaluar" }));
    await screen.findByText(/No se puede ampliar esta evaluación/);
    expect(screen.getByText("-4.0 kcal/mol")).toBeInTheDocument();
    expect(screen.queryByText("-11.0 kcal/mol")).toBeNull();
    expect(api.save).not.toHaveBeenCalled();
  });

  it("una acción tardía de A no actualiza ni guarda la sesión B", async () => {
    const action = deferred<any>();
    api.read.mockImplementation(async (_mid: string, task_id: string) => ({ task_id, anti_target_results: [] }));
    api.dock.mockReturnValue(action.promise);
    const update = vi.fn();
    const view = render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" onUpdateResult={update} />);
    fireEvent.click(screen.getByRole("button", { name: "Evaluar seleccionadas (1)" }));
    view.rerender(<ProSelectivityPanel moleculeId="mol" taskId="run-B" onUpdateResult={update} />);
    await act(async () => { action.resolve({ target: { ...result("run-A", -4).anti_target_results[0], task_id: "run-A" } }); });
    expect(screen.queryByText("-4.0 kcal/mol")).toBeNull();
    expect(api.save).not.toHaveBeenCalled();
    expect(update).not.toHaveBeenCalled();
  });

  it("consulta A aunque la proyección de la molécula corresponda a B", async () => {
    api.read.mockImplementation(async (_mid: string, taskId?: string) => taskId === "run-A" ? result("run-A", -4) : result("run-B", -11));
    render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" onTargetAffinity={-6.6} />);
    await waitFor(() => expect(screen.getByText("-4.0 kcal/mol")).toBeInTheDocument());
    expect(api.read).toHaveBeenCalledWith("mol", "run-A");
    expect(screen.queryByText("-11.0 kcal/mol")).toBeNull();
  });

  it("rechaza una respuesta cuya task_id no coincide", async () => {
    api.read.mockResolvedValue(result("run-B", -11));
    render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.queryByText("-11.0 kcal/mol")).toBeNull();
    expect(api.dock).not.toHaveBeenCalled();
    expect(api.save).not.toHaveBeenCalled();
  });

  it("cambiar corrida de la misma molécula descarta la respuesta tardía anterior", async () => {
    const a = deferred<ReturnType<typeof result>>();
    api.read.mockImplementation((_mid: string, taskId: string) => taskId === "run-A" ? a.promise : Promise.resolve(result("run-B", -5)));
    const view = render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" />);
    view.rerender(<ProSelectivityPanel moleculeId="mol" taskId="run-B" />);
    await waitFor(() => expect(screen.getByText("-5.0 kcal/mol")).toBeInTheDocument());
    await act(async () => { a.resolve(result("run-A", -4)); });
    expect(screen.queryByText("-4.0 kcal/mol")).toBeNull();
    expect(screen.getByText("-5.0 kcal/mol")).toBeInTheDocument();
  });

  it("el seguimiento en background también pide y valida la corrida", async () => {
    api.read.mockResolvedValue(result("run-B", -11));
    render(<ProSelectivityPanel moleculeId="mol" taskId="run-A" autoPoll />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(api.read.mock.calls.every(args => args[0] === "mol" && args[1] === "run-A")).toBe(true);
    expect(screen.queryByText("-11.0 kcal/mol")).toBeNull();
  });
});
