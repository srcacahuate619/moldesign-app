// =====================================================================
// R3 — un cambio de sesión NO borra la identidad de la tarea
// =====================================================================
//
// LA REGRESIÓN. `auth_expired` ponía `taskId` a null y limpiaba el estado
// entero. Pero un cambio de sesión no dice absolutamente nada sobre cómo va la
// tarea: puede estar terminando perfectamente en el backend. Borrar su
// identificador convertía una corrida viva en trabajo huérfano por un motivo
// que no tiene que ver con ella.
//
// LO QUE SÍ HAY QUE LIMPIAR son los RESULTADOS: el `molecule_id` pertenece a la
// cuenta anterior y guardarlo con la sesión nueva daría un 404. La distinción
// es entre «resultados de otra cuenta» e «identidad de la tarea».

import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";

import type { ActiveRun } from "../../../lib/cases/types";

const getJobStatus = vi.fn();

vi.mock("../../../lib/auth", () => ({
  useAuth: () => ({
    isLoading: false,
    logout: vi.fn(),
    token: "test-token",
    user: { user_id: "test-user" },
  }),
}));

vi.mock("../../../lib/api", () => ({
  getJobStatus: (id: string) => getJobStatus(id),
  getTargets: async () => [],
  submitEvaluation: vi.fn(),
  validateSmiles: vi.fn(),
  cancelEvaluation: vi.fn(),
  certifyMolecule: vi.fn(),
  downloadCertificate: vi.fn(),
  getComplexFile: vi.fn(),
  saveMolecule: vi.fn(),
}));
vi.mock("../../../lib/sounds", () => ({ playSound: vi.fn() }));
vi.mock("../../interfaces/pro/ProEvaluation", () => ({
  default: ({
    status,
    error,
  }: {
    status?: { status?: string; task_id?: string; result?: { molecule_id?: string } | null } | null;
    error?: string | null;
  }) => (
    <div>
      <span data-testid="estado">{status?.status ?? "sin-estado"}</span>
      <span data-testid="task">{status?.task_id ?? "sin-task"}</span>
      <span data-testid="result">{status?.result?.molecule_id ?? "sin-resultado"}</span>
      <span data-testid="error">{error ?? ""}</span>
    </div>
  ),
}));

import CaseEvaluationRunner from "../CaseEvaluationRunner";

const RUN: ActiveRun = {
  taskId: "task-sesion",
  executionState: "running",
  startedAt: "2026-08-23T12:00:00.000Z",
};

describe("auth_expired durante una corrida", () => {
  beforeEach(() => {
    getJobStatus.mockReset();
  });

  it("conserva el taskId y marca INTERRUMPIDO en vez de borrar la tarea", async () => {
    getJobStatus.mockResolvedValue({
      task_id: "task-sesion",
      status: "STARTED",
      progress: 30,
      result: { molecule_id: "mol-de-la-cuenta-vieja" },
      error: null,
      started_at: RUN.startedAt,
      finished_at: null,
    });
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={RUN}
        onActiveRunChange={onActiveRunChange}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("STARTED"));

    act(() => {
      window.dispatchEvent(new Event("auth_expired"));
    });

    // La identidad de la tarea SIGUE ahí.
    await waitFor(() => expect(screen.getByTestId("task")).toHaveTextContent("task-sesion"));
    // Y se declara interrumpida, con su explicación y su reintento.
    expect(await screen.findByText(/No se sabe cómo terminó/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reintentar seguimiento/i })).toBeInTheDocument();
    expect(screen.getByTestId("error")).toHaveTextContent(/recupera la sesión/i);

    // Nunca se cierra la corrida: cerrarla sería afirmar que terminó.
    expect(onActiveRunChange.mock.calls.some(([run]) => run === null)).toBe(false);
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task-sesion", executionState: "interrupted" }),
      ),
    );
  });

  it("limpia los RESULTADOS, que sí pertenecen a la otra cuenta", async () => {
    getJobStatus.mockResolvedValue({
      task_id: "task-sesion",
      status: "STARTED",
      progress: 30,
      result: { molecule_id: "mol-vieja" },
      error: null,
      started_at: RUN.startedAt,
      finished_at: null,
    });
    render(<CaseEvaluationRunner caseId="caso-1" activeRun={RUN} />);
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("STARTED"));

    act(() => {
      window.dispatchEvent(new Event("auth_expired"));
    });

    // El identificador de la tarea se conserva; el resultado de la cuenta
    // anterior no.
    await waitFor(() => expect(screen.getByTestId("task")).toHaveTextContent("task-sesion"));
    expect(screen.getByTestId("result")).toHaveTextContent("sin-resultado");
    expect(screen.getByTestId("error")).toHaveTextContent(/sesión cambió/i);
  });

  it("sin corrida viva sí limpia todo: no hay identidad que conservar", async () => {
    render(<CaseEvaluationRunner caseId="caso-1" />);
    act(() => {
      window.dispatchEvent(new Event("auth_expired"));
    });
    await waitFor(() => expect(screen.getByTestId("task")).toHaveTextContent("sin-task"));
    expect(screen.getByTestId("error")).toHaveTextContent(/sesión cambió/i);
    // Y no aparece el aviso de interrupción: no había nada que interrumpir.
    expect(screen.queryByText(/No se sabe cómo terminó/i)).not.toBeInTheDocument();
  });

  it("con una corrida ya TERMINADA limpia el resultado pero conserva su taskId", async () => {
    getJobStatus.mockResolvedValue({
      task_id: "task-sesion",
      status: "SUCCESS",
      progress: 100,
      result: { molecule_id: "mol" },
      error: null,
      started_at: RUN.startedAt,
      finished_at: RUN.startedAt,
    });
    render(<CaseEvaluationRunner caseId="caso-1" activeRun={RUN} />);
    await waitFor(() => expect(screen.getByTestId("estado")).toHaveTextContent("SUCCESS"));

    act(() => {
      window.dispatchEvent(new Event("auth_expired"));
    });
    await waitFor(() => expect(screen.getByTestId("task")).toHaveTextContent("task-sesion"));
    expect(screen.getByTestId("result")).toHaveTextContent("sin-resultado");
    expect(screen.queryByText(/No se sabe cómo terminó/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("error")).toHaveTextContent(/corrida terminada conserva/i);
  });

  it("ignora una respuesta de la sesión anterior que llega después del evento", async () => {
    let resolveStatus!: (value: Record<string, unknown>) => void;
    getJobStatus.mockReturnValue(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }),
    );
    const onActiveRunChange = vi.fn();
    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={RUN}
        onActiveRunChange={onActiveRunChange}
      />,
    );
    await waitFor(() => expect(getJobStatus).toHaveBeenCalledTimes(1));

    act(() => {
      window.dispatchEvent(new Event("auth_expired"));
    });
    await waitFor(() => expect(screen.getByTestId("error")).toHaveTextContent(/recupera la sesión/i));

    await act(async () => {
      resolveStatus({
        task_id: "task-sesion",
        status: "SUCCESS",
        progress: 100,
        result: { molecule_id: "mol-que-llegó-tarde" },
        error: null,
        started_at: RUN.startedAt,
        finished_at: RUN.startedAt,
      });
      await Promise.resolve();
    });

    expect(screen.getByTestId("result")).toHaveTextContent("sin-resultado");
    expect(screen.getByTestId("estado")).not.toHaveTextContent("SUCCESS");
    expect(
      onActiveRunChange.mock.calls.some(([run]) => run?.executionState === "completed"),
    ).toBe(false);
  });
});
