// =====================================================================
// SAR: la tabla enseña lo que se midió, y la pose se compara entre evaluaciones
// =====================================================================
//
// (El backend envía la similitud como Tanimoto 0-1; el adaptador la pasa a %.)
// 1. No se llama «análogo» a lo que no se parece: por debajo del umbral de Tanimoto, plegado aparte.
// 2. ΔScore no existe (siempre vacío desde SOL-04/AMP-02; SUP-02 NO_GO): ni columna ni cuadro en el detalle.
// 3. «Cambio clave» describe el grafo (núcleo común y fórmula), no repite que la comparación es legítima.
// 4. La comparación de pose entre evaluaciones se abstiene del RMSD cuando no hay marco común, y lo dice.
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const getSarData = vi.fn();
const getRunPoseComparison = vi.fn();
const getAnalogPoseComparison = vi.fn();
vi.mock("../../../../lib/proApi", () => ({
  getSarData: (...args: unknown[]) => getSarData(...args),
  getRunPoseComparison: (...args: unknown[]) => getRunPoseComparison(...args),
  getAnalogPoseComparison: (...args: unknown[]) => getAnalogPoseComparison(...args),
}));

// El diálogo real tiene su propia batería. Aquí importa qué recibe: sus props (en JSON) y la ficha, que se pinta aparte.
vi.mock("../PoseComparisonDialog", () => ({
  PoseComparisonDialog: ({ ficha, onClose, ...props }: { ficha?: ReactNode; onClose: () => void } & Record<string, unknown>) => (
    <div>
      <pre data-testid="dialogo-3d">{JSON.stringify(props)}</pre>
      <div data-testid="ficha-en-el-dialogo">{ficha}</div>
      <button type="button" onClick={onClose}>cerrar-dialogo</button>
    </div>
  ),
}));

import { ProSarTab, UMBRAL_ANALOGO_PCT } from "../ProSarTab";
import type { CaseRun } from "../../../../lib/cases/types";

const fila = (id: string, similarity: number, extra: Record<string, unknown> = {}) => ({
  molecule_id: id, task_id: `run-${id}`, name: `Mol ${id}`, smiles: `C${id}`, similarity, delta_score: null, delta_affinity: -1.2,
  comparison_state: "descriptive", highlight: "Protocolo estructural y condiciones químicas coincidentes; sin actividad experimental",
  structural_change: { core_heavy_atoms: 7, base_heavy_atoms: 7, analog_heavy_atoms: 8, formula_delta: [{ element: "C", delta: 1 }, { element: "H", delta: 2 }], core_complete: true },
  qed: 0.9, lipinski_pass: true, ...extra,
});

const corrida = (taskId: string, extra: Partial<CaseRun> = {}): CaseRun => ({
  taskId, moleculeId: "mol-base", executionState: "completed", startedAt: "2026-11-01T10:00:00.000Z",
  protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 }, ...extra,
});

beforeEach(() => {
  getSarData.mockReset().mockResolvedValue({
    results: [fila("alto", 0.72), fila("bajo", 0.117)],
    cohort: { source: "latest_projection", base_task_id: null, task_ids: null },
  });
  getRunPoseComparison.mockReset();
  getAnalogPoseComparison.mockReset();
});
afterEach(cleanup);

describe("la tabla", () => {
  it("separa los análogos reales de lo que no se parece, y pliega lo segundo", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    expect(await screen.findByText("Mol alto")).toBeInTheDocument();
    const plegado = screen.getByText(new RegExp(`similitud menor de ${UMBRAL_ANALOGO_PCT} %`)).closest("details")!;
    expect(plegado).not.toHaveAttribute("open");
    expect(within(plegado).getByText("Mol bajo")).toBeInTheDocument();
    expect(screen.getAllByText("Mol alto")).toHaveLength(1);
  });

  it("no enseña ΔScore, y la columna de afinidad dice contra qué se mide", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    await screen.findByText("Mol alto");
    expect(screen.queryByText("ΔScore")).toBeNull();
    expect(screen.getAllByText("Δ afinidad vs. base").length).toBeGreaterThan(0);
  });

  it("el cambio clave describe el grafo y no repite que la comparación es legítima", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    await screen.findByText("Mol alto");
    expect(screen.getAllByText(/Núcleo común: 7 de los 7 átomos pesados de la base · cambia \+1 C, \+2 H/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Protocolo estructural y condiciones químicas coincidentes/)).toBeNull();
  });

  it("en abstención sigue enseñando el motivo que da el backend", async () => {
    getSarData.mockResolvedValue({
      results: [fila("alto", 0.72, { comparison_state: "abstained", delta_affinity: null, highlight: "pH distinto: 7.4 frente a 2.0" })],
    });
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    expect(await screen.findByText(/pH distinto: 7.4 frente a 2.0/)).toBeInTheDocument();
  });
});

describe("comparar la pose entre evaluaciones (lo visual manda)", () => {
  it("sin otra evaluación terminada de la misma molécula no aparece", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1"), corrida("x", { moleculeId: "otra" })]} />);
    await screen.findByText("Mol alto");
    expect(screen.queryByRole("region", { name: /Comparar la pose de esta molécula/ })).toBeNull();
  });

  it("con otra evaluación ofrece abrir el comparador 3D con esa corrida a la derecha y las del caso a elegir", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t0"), corrida("t1"), corrida("t2", { moleculeId: "otra" })]} />);
    await screen.findByText("Mol alto");
    const region = screen.getByRole("region", { name: /Comparar la pose de esta molécula/ });
    expect(within(region).queryByTestId("dialogo-3d")).toBeNull();
    fireEvent.click(within(region).getByRole("button", { name: "Comparar en 3D" }));
    const dialogo = await screen.findByTestId("dialogo-3d");
    expect(JSON.parse(dialogo.textContent!)).toMatchObject({
      moleculeId: "mol-base", taskId: "t1", leftRank: 1, rightRank: 1, rightSource: { taskId: "t0", moleculeId: "mol-base" },
    });
    expect(JSON.parse(dialogo.textContent!).runs.map((r: { taskId: string }) => r.taskId)).toEqual(["t2", "t0"]);
  });

  it("no se calcula nada en las letras: la tarjeta ya no pide distancias, las pide el comparador", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t0"), corrida("t1")]} />);
    await screen.findByText("Mol alto");
    expect(getRunPoseComparison).not.toHaveBeenCalled();
    expect(screen.queryByText(/Semilla/)).toBeNull();
  });
});

describe("pulsar un análogo abre directamente el comparador 3D", () => {
  const abrirAnalogo = async (caseRuns: CaseRun[] = [corrida("t1")]) => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={caseRuns} />);
    fireEvent.click(await screen.findByText("Mol alto"));
    return screen.findByTestId("dialogo-3d");
  };

  it("con la base a la izquierda y el análogo a la derecha, sin pasar por un botón ni por un modal", async () => {
    const dialogo = await abrirAnalogo();
    expect(JSON.parse(dialogo.textContent!)).toMatchObject({
      moleculeId: "mol-base", taskId: "t1", leftRank: 1, rightRank: 1,
      rightSource: { taskId: "run-alto", moleculeId: "alto", etiqueta: "Mol alto" },
    });
    expect(screen.queryByRole("button", { name: /Comparar en 3D con la base/ })).toBeNull();
    expect(screen.queryByText(/no hay una pose con la que compararla/)).toBeNull();
    expect(getAnalogPoseComparison).not.toHaveBeenCalled();
  });

  it("deja elegir, en cada lado, las demás corridas del caso", async () => {
    const dialogo = await abrirAnalogo([corrida("t0"), corrida("t1"), corrida("t2", { moleculeId: "otra" })]);
    expect(JSON.parse(dialogo.textContent!).runs.map((r: { taskId: string }) => r.taskId)).toEqual(["t2", "t0"]);
  });

  it("la información que era un modal viaja dentro del comparador: nombre, SMILES, cambio clave, Δ afinidad y QED", async () => {
    await abrirAnalogo();
    const ficha = within(screen.getByTestId("ficha-en-el-dialogo"));
    expect(ficha.getByRole("heading", { name: "Mol alto" })).toBeInTheDocument();
    expect(ficha.getByText("Calto")).toBeInTheDocument();
    expect(ficha.getByText(/Núcleo común: 7 de los 7 átomos pesados de la base · cambia \+1 C, \+2 H/)).toBeInTheDocument();
    expect(ficha.getByText("-1.2 kcal/mol")).toBeInTheDocument();
    expect(ficha.getByText("QED")).toBeInTheDocument();
    expect(ficha.getByText("0.90")).toBeInTheDocument();
    expect(ficha.getByText("72.0%")).toBeInTheDocument();
    expect(ficha.queryByText("ΔScore")).toBeNull();
    expect(ficha.queryByText("RMSD del núcleo común")).toBeNull();
  });

  it("si la fila se abstuvo, la ficha del comparador sigue diciendo el motivo y no inventa el delta", async () => {
    getSarData.mockResolvedValue({
      results: [fila("alto", 0.72, { comparison_state: "abstained", delta_affinity: null, highlight: "pH distinto: 7.4 frente a 2.0", comparison_reason: "pH distinto: 7.4 frente a 2.0" })],
    });
    await abrirAnalogo();
    const ficha = within(screen.getByTestId("ficha-en-el-dialogo"));
    expect(ficha.getAllByText(/pH distinto: 7.4 frente a 2.0/).length).toBeGreaterThan(0);
    expect(ficha.queryByText(/kcal\/mol/)).toBeNull();
  });

  it("cerrar el comparador vuelve a la tabla", async () => {
    await abrirAnalogo();
    fireEvent.click(screen.getByRole("button", { name: "cerrar-dialogo" }));
    await waitFor(() => expect(screen.queryByTestId("dialogo-3d")).toBeNull());
    expect(screen.getByText("Mol alto")).toBeInTheDocument();
  });
});

describe("una fila sin pose que comparar enseña su ficha sola, y dice por qué no hay 3D", () => {
  it("sin la corrida del análogo", async () => {
    getSarData.mockResolvedValue({ results: [fila("alto", 0.72, { task_id: null })] });
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    fireEvent.click(await screen.findByText("Mol alto"));
    expect(screen.queryByTestId("dialogo-3d")).toBeNull();
    expect(screen.getByRole("heading", { name: "Mol alto" })).toBeInTheDocument();
    expect(screen.getByText("QED")).toBeInTheDocument();
    expect(screen.getByText(/no hay una pose con la que compararla en 3D/)).toBeInTheDocument();
  });

  it("cuando la fila es la propia evaluación que se ve", async () => {
    getSarData.mockResolvedValue({ results: [fila("alto", 0.72, { task_id: "t1" })] });
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    fireEvent.click(await screen.findByText("Mol alto"));
    expect(screen.queryByTestId("dialogo-3d")).toBeNull();
    expect(screen.getByText(/no hay una pose con la que compararla en 3D/)).toBeInTheDocument();
  });

  it("sin ΔScore en ningún caso", async () => {
    render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);
    fireEvent.click(await screen.findByText("Mol alto"));
    expect(screen.queryByText("ΔScore")).toBeNull();
  });
});
