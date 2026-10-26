// =====================================================================
// Guardar en Moldex es un hecho de la EVALUACIÓN que se está viendo
// =====================================================================
//
// Una molécula (receptor + ligando) se reevalúa varias veces en el mismo caso y
// cada evaluación se guarda por separado. Antes `isSaved` era un booleano suelto
// del runner: tras guardar la primera quedaba en `true` para el resultado
// siguiente (que se veía «Guardado» sin estarlo), y `saveMolecule` no decía CUÁL
// evaluación guardaba, así que el backend guardaba la última de la molécula.
//
// `ProEvaluation` se mockea, como en el resto de pruebas del runner: aquí se
// prueba qué evaluación guarda el runner y cuándo la da por guardada.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

const getJobStatus = vi.fn();
const saveMolecule = vi.fn(async () => undefined);
const authState = vi.hoisted(() => ({
  isLoading: false,
  token: "token-prueba",
  user: { user_id: "usuario-prueba" },
  logout: vi.fn(),
}));

vi.mock("../../../lib/auth", () => ({ useAuth: () => authState }));
vi.mock("../../../lib/api", () => ({
  ApiError: class extends Error {},
  getJobStatus: (id: string) => getJobStatus(id),
  getEvaluationResult: vi.fn(),
  getTargets: vi.fn(async () => []),
  submitEvaluation: vi.fn(),
  validateSmiles: vi.fn(),
  cancelEvaluation: vi.fn(),
  certifyMolecule: vi.fn(),
  downloadCertificate: vi.fn(),
  downloadComplexFile: vi.fn(),
  getComplexFile: vi.fn(),
  saveMolecule: (...args: unknown[]) => saveMolecule(...(args as [])),
}));
vi.mock("../../../lib/sounds", () => ({ playSound: vi.fn() }));

vi.mock("../../interfaces/pro/ProEvaluation", () => ({
  default: ({
    status,
    isSaved,
    handleSave,
    setStatus,
  }: {
    status?: { result?: { molecule_id?: string; task_id?: string | null } | null } | null;
    isSaved?: boolean;
    handleSave?: (name?: string) => Promise<void>;
    setStatus: (next: unknown) => void;
  }) => (
    <div data-testid="pro">
      viendo:{status?.result?.task_id ?? "nada"};guardado:{String(Boolean(isSaved))}
      <button onClick={() => void handleSave?.("mi ficha")}>Guardar</button>
      {["run-A", "run-B"].map((tarea) => (
        <button
          key={tarea}
          onClick={() =>
            setStatus({
              task_id: tarea, status: "SUCCESS", progress: 100, error: null,
              started_at: null, finished_at: null,
              result: { molecule_id: "mol-1", task_id: tarea },
            })
          }
        >
          ver {tarea}
        </button>
      ))}
    </div>
  ),
}));

import CaseEvaluationRunner from "../CaseEvaluationRunner";
import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";

const RUN = {
  taskId: "run-A",
  executionState: "completed" as const,
  startedAt: "2026-10-05T12:00:00.000Z",
};

async function montar() {
  getJobStatus.mockResolvedValue({
    task_id: "run-A", status: "SUCCESS", progress: 100, error: null,
    started_at: RUN.startedAt, finished_at: RUN.startedAt,
    result: { molecule_id: "mol-1", task_id: "run-A" },
  });
  render(<CaseEvaluationRunner caseId="caso-1" activeRun={RUN} onActiveRunChange={vi.fn()} />);
  await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("viendo:run-A"));
}

describe("guardar una evaluación en Moldex", () => {
  beforeEach(() => {
    invalidarCatalogo();
    saveMolecule.mockClear();
    getJobStatus.mockReset();
    window.localStorage.setItem("moldesign_auth", JSON.stringify({ token: "t" }));
  });

  it("guarda la evaluación que se está viendo, identificada por su corrida", async () => {
    await montar();

    fireEvent.click(screen.getByText("Guardar"));

    await waitFor(() => expect(saveMolecule).toHaveBeenCalledWith("mol-1", "mi ficha", "run-A"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("guardado:true"));
  });

  it("avisa a Moldex de QUÉ evaluación se guardó", async () => {
    await montar();
    const oyente = vi.fn();
    window.addEventListener("moldex:invalidated", oyente);

    fireEvent.click(screen.getByText("Guardar"));

    await waitFor(() => expect(oyente).toHaveBeenCalled());
    expect((oyente.mock.calls[0][0] as CustomEvent).detail).toEqual({
      moleculeId: "mol-1", taskId: "run-A",
    });
    window.removeEventListener("moldex:invalidated", oyente);
  });

  it("la evaluación siguiente de la misma molécula NO nace «guardada» y se puede guardar", async () => {
    await montar();
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("guardado:true"));

    fireEvent.click(screen.getByText("ver run-B"));

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("viendo:run-B;guardado:false"));
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(saveMolecule).toHaveBeenLastCalledWith("mol-1", "mi ficha", "run-B"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("guardado:true"));
  });

  it("guardar la segunda no «des-guarda» la primera al volver a verla", async () => {
    await montar();
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("guardado:true"));
    fireEvent.click(screen.getByText("ver run-B"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("viendo:run-B"));
    fireEvent.click(screen.getByText("Guardar"));
    await waitFor(() => expect(saveMolecule).toHaveBeenCalledTimes(2));

    await act(async () => { fireEvent.click(screen.getByText("ver run-A")); });

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("viendo:run-A;guardado:true"));
  });
});
