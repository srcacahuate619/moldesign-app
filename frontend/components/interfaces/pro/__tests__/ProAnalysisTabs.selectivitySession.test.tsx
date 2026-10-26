import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { KeepAliveContext } from "../../../../context/KeepAliveContext";

// El panel REAL se prueba dentro de las pestañas reales: desmontarlo perdía
// selección y progreso aunque una prueba del panel aislado siguiera verde.
vi.mock("../ProDockingTab", () => ({ ProDockingTab: () => <p>Estructura</p> }));
vi.mock("../ProParametersTab", () => ({ ProParametersTab: () => <p>Propiedades</p> }));
vi.mock("../EstadoDelLigando", () => ({ EstadoDelLigando: () => null }));
vi.mock("../ProAlertsTab", () => ({ ProAlertsTab: () => null }));
vi.mock("../ProXaiTab", () => ({ ProXaiTab: () => null }));
vi.mock("../ProSarTab", () => ({ ProSarTab: () => <p>SAR</p> }));
vi.mock("../StructuralEvidencePanel", () => ({ PosePhysicalDetails: () => null, StructuralEvidencePanel: () => null }));
const api = vi.hoisted(() => ({ dock: vi.fn(), save: vi.fn(), result: vi.fn() }));
vi.mock("../../../../lib/proApi", () => ({ dockSingleAntiTarget: api.dock, saveSelectivityResults: api.save }));
vi.mock("../../../../lib/api", () => ({ getEvaluationResult: api.result }));

import { ProAnalysisTabs } from "../ProAnalysisTabs";

const targets = [
  { pdb_id: "5VA1", name: "hERG", category: "Cardiac", por_defecto: true },
  { pdb_id: "7SRQ", name: "5-HT2B", category: "CNS", por_defecto: true },
  { pdb_id: "X7", name: "Diana adicional", category: "GPCR", por_defecto: false },
];
const status = { status: "SUCCESS", result: { affinity_kcal: -6.6 } } as any;
const completed = (pdb_id: string, affinity: number) => ({ pdb_id, affinity, status: "ok", threshold: -7, task_id: "run-A" });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
function view(taskId = "run-A", selectivityResult: any = null, visible = true, work = vi.fn()) {
  return <KeepAliveContext.Provider value={visible}>
    <ProAnalysisTabs status={status} moleculeId="mol-A" taskId={taskId} selectivityResult={selectivityResult} onSelectivityWorkChange={work} />
  </KeepAliveContext.Provider>;
}
const openAdvanced = () => fireEvent.click(screen.getByRole("tab", { name: /^Análisis$/ }));
const myPanel = () => screen.getByRole("region", { name: "Mi panel" });

beforeEach(() => {
  api.dock.mockReset();
  api.save.mockReset().mockResolvedValue({ success: true });
  api.result.mockReset().mockImplementation(async (_mid: string, task_id: string) => ({ task_id, anti_target_results: [], selectivity_ran: false }));
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ anti_targets: targets }) })));
});
afterEach(() => vi.unstubAllGlobals());

describe("la sesión de anti-dianas al cambiar de pestaña", () => {
  it("conserva selección y scroll tanto entre métodos avanzados como entre áreas de análisis", async () => {
    render(view());
    expect(api.result).not.toHaveBeenCalled();
    openAdvanced();
    fireEvent.click(await screen.findByRole("checkbox", { name: /Diana adicional/ }));
    const panel = myPanel();
    const list = within(panel).getByRole("group", { name: "Mi panel" });
    list.scrollTop = 150;

    fireEvent.click(screen.getByRole("tab", { name: /^SAR:/ }));
    expect(screen.queryByRole("region", { name: "Mi panel" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /^Selectividad:/ }));
    expect(myPanel()).toBe(panel);
    expect(screen.getByRole("checkbox", { name: /Diana adicional/ })).toBeChecked();
    expect(list.scrollTop).toBe(150);

    fireEvent.click(screen.getByRole("tab", { name: /^Propiedades/ }));
    openAdvanced();
    expect(myPanel()).toBe(panel);
    expect(screen.getByRole("checkbox", { name: /Diana adicional/ })).toBeChecked();
    expect(api.dock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Ninguna" }));
    fireEvent.click(screen.getByRole("tab", { name: /^Propiedades/ }));
    openAdvanced();
    expect(screen.getByRole("button", { name: "Evaluar seleccionadas (0)" })).toBeDisabled();
    expect(screen.getAllByRole("checkbox").every(input => !(input as HTMLInputElement).checked)).toBe(true);
  });

  it("conserva nodo, selección y scroll en el índice lateral", async () => {
    const { rerender } = render(view());
    openAdvanced();
    fireEvent.click(await screen.findByRole("checkbox", { name: /Diana adicional/ }));
    const panel = myPanel();
    const list = within(panel).getByRole("group", { name: "Mi panel" });
    list.scrollTop = 150;
    rerender(view());
    expect(myPanel()).toBe(panel);
    expect(list.scrollTop).toBe(150);
    expect(screen.getByRole("checkbox", { name: /Diana adicional/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "Evaluar seleccionadas (3)" })).toBeEnabled();
    expect(api.dock).not.toHaveBeenCalled();
  });

  it("la tanda sigue al salir, conserva los parciales y vuelve terminada sin duplicar cálculos", async () => {
    const first = deferred<any>();
    const second = deferred<any>();
    const third = deferred<any>();
    api.dock.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise).mockReturnValueOnce(third.promise);
    const work = vi.fn();
    render(view("run-A", null, true, work));
    openAdvanced();
    await screen.findByRole("checkbox", { name: /Diana adicional/ });
    fireEvent.click(screen.getByRole("button", { name: "Todas las disponibles" }));
    fireEvent.click(screen.getByRole("button", { name: "Evaluar seleccionadas (3)" }));
    await waitFor(() => expect(work).toHaveBeenLastCalledWith(true));

    fireEvent.click(screen.getByRole("tab", { name: /^SAR:/ }));
    await act(async () => { first.resolve({ target: completed("5VA1", -5.1) }); });
    await waitFor(() => expect(api.dock).toHaveBeenCalledTimes(2));
    expect(api.save.mock.calls[0][1].off_targets).toContainEqual(completed("5VA1", -5.1));
    expect(work).toHaveBeenLastCalledWith(true);

    fireEvent.click(screen.getByRole("tab", { name: /^Selectividad:/ }));
    expect(within(myPanel()).getByText("-5.1 kcal/mol")).toBeInTheDocument();
    expect(screen.getByText("1/3")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /Diana adicional/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("tab", { name: /^Propiedades/ }));
    await act(async () => { second.resolve({ target: completed("7SRQ", -5.2) }); });
    await waitFor(() => expect(api.dock).toHaveBeenCalledTimes(3));
    await act(async () => { third.resolve({ target: completed("X7", -5.3) }); });
    await waitFor(() => expect(work).toHaveBeenLastCalledWith(false));
    openAdvanced();

    expect(screen.getByText("3/3")).toBeInTheDocument();
    expect(within(myPanel()).getByText("-5.3 kcal/mol")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evaluar seleccionadas (3)" })).toBeEnabled();
    expect(api.dock.mock.calls.map(call => call[1])).toEqual(["5VA1", "7SRQ", "X7"]);
    expect(api.save.mock.calls.at(-1)?.[1].off_targets).toHaveLength(3);
    expect(api.save.mock.calls.every(call => call[1].task_id === "run-A")).toBe(true);
    expect(api.dock.mock.calls.every(call => call[2] === "run-A")).toBe(true);
  });

  it("ocultar toda Evaluación conserva la selección y cerrar un diálogo no lo reabre al volver", async () => {
    const { rerender } = render(view());
    openAdvanced();
    fireEvent.click(await screen.findByRole("checkbox", { name: /Diana adicional/ }));
    const panel = myPanel();
    fireEvent.click(within(panel).getAllByRole("button", { name: /Saber más/i })[0]);
    expect(await screen.findByText(/Canal de potasio dependiente/)).toBeInTheDocument();
    rerender(view("run-A", null, false));
    expect(screen.queryByText(/Canal de potasio dependiente/)).not.toBeInTheDocument();
    rerender(view());
    expect(myPanel()).toBe(panel);
    expect(screen.getByRole("checkbox", { name: /Diana adicional/ })).toBeChecked();
    expect(screen.queryByText(/Canal de potasio dependiente/)).not.toBeInTheDocument();
  });

  it("un snapshot anterior del padre no reemplaza una reevaluación recién obtenida", async () => {
    const old = { off_targets: [completed("5VA1", -5.1)] };
    api.dock.mockResolvedValueOnce({ target: completed("5VA1", -5.9) });
    const { rerender } = render(view("run-A", old));
    openAdvanced();
    await screen.findByRole("checkbox", { name: /hERG/ });
    fireEvent.click(within(myPanel()).getByRole("button", { name: "Reevaluar" }));
    await within(myPanel()).findByText("-5.9 kcal/mol");
    rerender(view("run-A", { off_targets: [completed("5VA1", -5.1)] }));
    expect(within(myPanel()).getByText("-5.9 kcal/mol")).toBeInTheDocument();
    expect(within(myPanel()).queryByText("-5.1 kcal/mol")).not.toBeInTheDocument();
  });

  it("una corrida nueva de la misma molécula recibe su propio panel", async () => {
    const { rerender } = render(view());
    openAdvanced();
    fireEvent.click(await screen.findByRole("checkbox", { name: /Diana adicional/ }));
    const previous = myPanel();
    rerender(view("run-B"));
    await screen.findByRole("checkbox", { name: /Diana adicional/ });
    expect(myPanel()).not.toBe(previous);
    expect(screen.getByRole("checkbox", { name: /Diana adicional/ })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Evaluar seleccionadas (2)" })).toBeEnabled();
  });

  it("incorpora datos nuevos del padre para las anti-dianas que no se han recalculado localmente", async () => {
    const { rerender } = render(view("run-A", { off_targets: [completed("5VA1", -5.1)] }));
    openAdvanced();
    await within(myPanel()).findByText("-5.1 kcal/mol");
    rerender(view("run-A", { off_targets: [completed("5VA1", -5.8)] }));
    expect(await within(myPanel()).findByText("-5.8 kcal/mol")).toBeInTheDocument();
    expect(within(myPanel()).queryByText("-5.1 kcal/mol")).not.toBeInTheDocument();
  });
});
