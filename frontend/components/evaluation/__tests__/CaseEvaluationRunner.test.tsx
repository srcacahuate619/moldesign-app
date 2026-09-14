// =====================================================================
// Tests del runner — reanudar una corrida que sobrevivió al cierre
// =====================================================================
//
// EL ESCENARIO. El usuario lanza una evaluación y cierra la ventana. La tarea
// sigue viva en el backend. Al volver, este componente se monta con el
// `activeRun` que estaba en el manifiesto y tiene que: preguntar de inmediato,
// y seguir preguntando si la tarea no ha terminado. Sin eso, la corrida quedaba
// huérfana y el usuario no volvía a verla nunca.
//
// Y LA DISTINCIÓN QUE FALTABA: un fallo de conexión NO es un `FAILURE` del
// backend. Antes, cinco reintentos fallidos escribían `FAILURE`, que es una
// afirmación sobre el backend que nadie había comprobado.
//
// `ProEvaluation` se mockea: aquí se prueba el ciclo de vida de la corrida, no
// la interfaz de evaluación, y montarla de verdad arrastra Ketcher y Molstar.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import type { ActiveRun, CasePipelineConfig, PreflightSummary } from "../../../lib/cases/types";

const getJobStatus = vi.fn();
const getEvaluationResult = vi.fn();
const getTargets = vi.fn(async () => []);
const submitEvaluation = vi.fn();
const MockApiError = vi.hoisted(() =>
  class MockApiError extends Error {
    readonly status: number;
    constructor(status: number, message = `HTTP ${status}`) {
      super(message);
      this.status = status;
    }
  },
);
const authState = vi.hoisted(() => ({
  isLoading: false,
  token: "token-prueba",
  user: { user_id: "usuario-prueba" },
  logout: vi.fn(),
}));

vi.mock("../../../lib/auth", () => ({
  useAuth: () => authState,
}));

vi.mock("../../../lib/api", () => ({
  ApiError: MockApiError,
  getJobStatus: (id: string) => getJobStatus(id),
  getEvaluationResult: (id: string, taskId?: string) => getEvaluationResult(id, taskId),
  getTargets: () => getTargets(),
  submitEvaluation: (...args: unknown[]) => submitEvaluation(...args),
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
    target,
    structuralSystem,
    resultRecovery,
    onRetryResultRecovery,
    handleSubmit,
  }: {
    status?: { status?: string; result?: { molecule_id?: string } | null } | null;
    target?: string;
    structuralSystem?: { sourceRunTaskId?: string };
    resultRecovery?: { state: string; message?: string; requiresLogin?: boolean } | null;
    onRetryResultRecovery?: () => void;
    handleSubmit?: (
      gridCenter?: [number, number, number],
      gridSize?: [number, number, number],
      customHotspots?: string[],
      peptideDockingEngine?: "esmfold" | "esmfold-pro" | "esmfold-experimental" | "colabfold",
      pipelineConfig?: unknown,
    ) => void;
  }) => (
    <div data-testid="pro" data-target={target} data-structural-system={structuralSystem?.sourceRunTaskId} data-recovery={resultRecovery?.state ?? "none"}>
      estado:{status?.status ?? "sin-estado"};resultado:{status?.result?.molecule_id ?? "sin-resultado"}
      {resultRecovery?.message && <span>{resultRecovery.message}</span>}
      {resultRecovery?.state === "blocked" && (
        <button onClick={onRetryResultRecovery}>
          {resultRecovery.requiresLogin ? "Iniciar sesión" : "Reintentar recuperación"}
        </button>
      )}
      <button
        onClick={() =>
          handleSubmit?.(
            [99, 99, 99],
            [99, 99, 99],
            ["Z:ALA1"],
            undefined,
            { enabled_stages: ["validation"], stage_params: {}, docking_engine: "vina" },
          )
        }
      >
        Ejecutar prueba
      </button>
    </div>
  ),
}));

import CaseEvaluationRunner from "../CaseEvaluationRunner";
import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";

beforeEach(() => {
  // El catálogo se cachea entre montajes: cada prueba parte sin nada.
  invalidarCatalogo();
  authState.isLoading = false;
  authState.token = "token-prueba";
  authState.user = { user_id: "usuario-prueba" };
  authState.logout.mockClear();
  submitEvaluation.mockReset();
});

const RUN: ActiveRun = {
  taskId: "task-viva",
  executionState: "running",
  startedAt: "2026-08-23T12:00:00.000Z",
};

function statusOf(state: string, extra: Record<string, unknown> = {}) {
  return {
    task_id: "task-viva",
    status: state,
    progress: 50,
    result: null,
    error: null,
    started_at: RUN.startedAt,
    finished_at: null,
    ...extra,
  };
}

describe("reanudación al montar", () => {
  beforeEach(() => {
    getJobStatus.mockReset();
    getEvaluationResult.mockReset();
    getTargets.mockClear();
  });

  it("con una tarea VIVA, pregunta de inmediato y sigue con la corrida abierta", async () => {
    getJobStatus.mockResolvedValue(statusOf("STARTED"));
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={RUN}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    // Consulta inmediata: no espera al primer tick del polling.
    await waitFor(() => expect(getJobStatus).toHaveBeenCalledWith("task-viva"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("STARTED"));

    // La corrida se mantiene abierta con su `taskId`.
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task-viva", executionState: "running" }),
      ),
    );
  });

  it("con una tarea ya TERMINADA, conserva el taskId y deja de bloquear", async () => {
    getJobStatus.mockResolvedValue(statusOf("SUCCESS", { result: { molecule_id: "mol-1" } }));
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={RUN}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("SUCCESS"));
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task-viva", executionState: "completed" }),
      ),
    );
    expect(onActiveRunChange).not.toHaveBeenCalledWith(null);
    expect(screen.getByTestId("pro")).toHaveTextContent("resultado:mol-1");
  });

  it("recupera una corrida terminal persistida con una sola lectura puntual", async () => {
    getJobStatus.mockResolvedValue(statusOf("SUCCESS", { result: { molecule_id: "mol-recuperada" } }));

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{ ...RUN, executionState: "completed" }}
      />,
    );

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("mol-recuperada"));
    await new Promise((resolve) => setTimeout(resolve, 30));
    expect(getJobStatus).toHaveBeenCalledTimes(1);
  });

  it("espera a que la sesión desktop esté resuelta antes de recuperar", async () => {
    authState.isLoading = true;
    getJobStatus.mockResolvedValue(
      statusOf("SUCCESS", { result: { molecule_id: "mol-con-sesion" } }),
    );

    const props = {
      caseId: "caso-1",
      activeRun: { ...RUN, executionState: "completed" as const },
    };
    const { rerender } = render(<CaseEvaluationRunner {...props} />);

    expect(getJobStatus).not.toHaveBeenCalled();
    expect(screen.getByTestId("pro")).not.toHaveTextContent("La evaluación terminó sin resultados");

    authState.isLoading = false;
    rerender(<CaseEvaluationRunner {...props} />);

    await waitFor(() => expect(getJobStatus).toHaveBeenCalledWith("task-viva"));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("mol-con-sesion"));
  });

  it("reabre el resultado durable sin depender del cache de tareas", async () => {
    getJobStatus.mockRejectedValue(new Error("job cache expired"));
    getEvaluationResult.mockResolvedValue({ molecule_id: "mol-durable" });
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{
          ...RUN,
          executionState: "completed",
          moleculeId: "mol-durable",
        }}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    await waitFor(() =>
      expect(getEvaluationResult).toHaveBeenCalledWith("mol-durable", "task-viva"),
    );
    expect(getJobStatus).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(screen.getByTestId("pro")).toHaveTextContent("resultado:mol-durable"),
    );
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ moleculeId: "mol-durable", executionState: "completed" }),
      ),
    );
  });

  it("un 403 de recuperación pide la cuenta correcta sin marcar la corrida como fallida", async () => {
    getJobStatus.mockRejectedValue(new MockApiError(403));
    getEvaluationResult.mockRejectedValue(new MockApiError(403));
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{
          ...RUN,
          executionState: "completed",
          moleculeId: "mol-privada",
        }}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    expect(await screen.findByText(/pertenece a otra sesión/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /iniciar sesión/i })).toBeInTheDocument();
    expect(
      onActiveRunChange.mock.calls.some(([run]) => run?.executionState === "failed"),
    ).toBe(false);
  });

  it("reintenta automáticamente al cambiar a la cuenta propietaria", async () => {
    getJobStatus
      .mockRejectedValueOnce(new MockApiError(403))
      .mockResolvedValueOnce(
        statusOf("SUCCESS", { result: { molecule_id: "mol-recuperada-cuenta" } }),
      );
    getEvaluationResult.mockRejectedValueOnce(new MockApiError(403));

    const props = {
      caseId: "caso-1",
      activeRun: {
        ...RUN,
        executionState: "completed" as const,
        moleculeId: "mol-recuperada-cuenta",
      },
    };
    const { rerender } = render(<CaseEvaluationRunner {...props} />);
    expect(await screen.findByText(/pertenece a otra sesión/i)).toBeInTheDocument();

    authState.user = { user_id: "usuario-propietario" };
    authState.token = "token-propietario";
    rerender(<CaseEvaluationRunner {...props} />);

    await waitFor(() => expect(getJobStatus).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByTestId("pro")).toHaveTextContent("mol-recuperada-cuenta"),
    );
  });

  it("si la conexión falla, declara INTERRUMPIDO y NO inventa un fallo del backend", async () => {
    getJobStatus.mockRejectedValue(new Error("ECONNREFUSED"));
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={RUN}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    await waitFor(() => expect(getJobStatus).toHaveBeenCalled());
    // Aviso visible, con su reintento.
    expect(await screen.findByText(/No se sabe cómo terminó/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reintentar seguimiento/i })).toBeInTheDocument();

    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task-viva", executionState: "interrupted" }),
      ),
    );
    // Y NUNCA se cierra con un `failed` que nadie ha comprobado.
    const cerrada = onActiveRunChange.mock.calls.some(([run]) => run === null);
    expect(cerrada).toBe(false);
    expect(screen.getByTestId("pro")).not.toHaveTextContent("FAILURE");
  });

  it("«Reintentar seguimiento» vuelve a preguntar y recupera la corrida", async () => {
    getJobStatus.mockRejectedValueOnce(new Error("ECONNREFUSED"));
    render(<CaseEvaluationRunner caseId="caso-1" activeRun={RUN} />);

    const retry = await screen.findByRole("button", { name: /reintentar seguimiento/i });
    getJobStatus.mockResolvedValue(statusOf("SUCCESS"));
    retry.click();

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("SUCCESS"));
    expect(screen.queryByText(/No se sabe cómo terminó/i)).not.toBeInTheDocument();
  });

  it("sin corrida persistida no pregunta nada al montar", async () => {
    render(<CaseEvaluationRunner caseId="caso-1" />);
    await waitFor(() => expect(getTargets).toHaveBeenCalled());
    expect(getJobStatus).not.toHaveBeenCalled();
    expect(screen.getByTestId("pro")).toHaveTextContent("sin-estado");
  });

  it("un caso fijado vuelve a abrir el mismo receptor, no el catálogo por defecto", async () => {
    render(
      <CaseEvaluationRunner
        caseId="caso-sistema"
        inputs={{ receptor: { pdbId: "1ABC", origin: "curado" } }}
        structuralSystem={{
          lockedAt: "2026-08-26T12:00:00.000Z",
          sourceRunTaskId: "task-ancla",
          inputFingerprint: "sha256:ancla",
          receptor: { pdbId: "6HSK", chain: "A", origin: "curado" },
          grid: { center: [-15, 2, -14], size: [22, 22, 22] },
          customHotspots: [],
          dockingEngine: "vina",
          exhaustiveness: 8,
          numPoses: 9,
          conformers: 1,
        }}
      />,
    );

    await waitFor(() => expect(getTargets).toHaveBeenCalled());
    expect(screen.getByTestId("pro")).toHaveAttribute("data-target", "6HSK");
    expect(screen.getByTestId("pro")).toHaveAttribute("data-structural-system", "task-ancla");
  });

  it("una corrida INTERRUMPIDA en el manifiesto se reintenta al montar", async () => {
    getJobStatus.mockRejectedValue(new Error("sigue caído"));
    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{ ...RUN, executionState: "interrupted", lastError: "Se perdió la conexión." }}
      />,
    );
    // Interrumpido NO es terminal, así que al montar se vuelve a preguntar: es
    // la diferencia entre "no sabemos" y "se acabó".
    await waitFor(() => expect(getJobStatus).toHaveBeenCalledWith("task-viva"));
    // Y como sigue sin haber conexión, el aviso vuelve.
    expect(await screen.findByText(/No se sabe cómo terminó/i)).toBeInTheDocument();
  });
});

// =====================================================================
// Referencia al resultado publicable
// =====================================================================
//
// El workspace revela «Informe» sólo si este componente le pasa un
// `molecule_id` REAL. Es la pieza que evita las dos alternativas malas: copiar
// el payload científico dentro de `case.json` —una segunda verdad que
// envejece— o enseñar un informe que después no se puede abrir.

describe("referencia al resultado publicable", () => {
  beforeEach(() => {
    getJobStatus.mockReset();
    getEvaluationResult.mockReset();
    getTargets.mockClear();
  });

  it("publica el `molecule_id` cuando la corrida termina con resultado", async () => {
    getJobStatus.mockResolvedValue(
      statusOf("SUCCESS", { result: { molecule_id: "mol-publicable" } }),
    );
    const onReportableChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{ ...RUN, executionState: "completed" }}
        onReportableChange={onReportableChange}
      />,
    );

    await waitFor(() =>
      expect(onReportableChange).toHaveBeenCalledWith({
        taskId: "task-viva",
        moleculeId: "mol-publicable",
        certified: false,
      }),
    );
  });

  it("un SUCCESS sin resultado NO publica nada", async () => {
    // Pérdida silenciosa: el pipeline dijo que terminó pero no llegó el
    // resultado. Publicarlo revelaría un «Informe» que no se puede abrir.
    getJobStatus.mockResolvedValue(statusOf("SUCCESS", { result: null }));
    const onReportableChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{ ...RUN, executionState: "completed" }}
        onReportableChange={onReportableChange}
      />,
    );

    await waitFor(() => expect(getJobStatus).toHaveBeenCalled());
    expect(onReportableChange).not.toHaveBeenCalledWith(
      expect.objectContaining({ moleculeId: expect.any(String) }),
    );
  });

  it("declara la recuperación cuando el caso guardaba una corrida completada", async () => {
    getJobStatus.mockResolvedValue(
      statusOf("SUCCESS", { result: { molecule_id: "mol-recuperada" } }),
    );
    const onReportRecoveryChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{ ...RUN, executionState: "completed" }}
        onReportRecoveryChange={onReportRecoveryChange}
      />,
    );

    await waitFor(() => expect(onReportRecoveryChange).toHaveBeenCalledWith("recovered"));
    expect(onReportRecoveryChange).toHaveBeenCalledWith("recovering");
  });

  it("si la tarea completada ya no se puede consultar, lo dice en vez de callarlo", async () => {
    getJobStatus.mockRejectedValue(new Error("404 task not found"));
    const onReportRecoveryChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{ ...RUN, executionState: "completed" }}
        onReportRecoveryChange={onReportRecoveryChange}
      />,
    );

    await waitFor(() => expect(onReportRecoveryChange).toHaveBeenCalledWith("unrecoverable"));
  });

  it("una corrida VIVA no anuncia recuperación de informe", async () => {
    // No se esperaba evidencia todavía: anunciar una recuperación fallida
    // sería inventar un problema que nadie tiene.
    getJobStatus.mockResolvedValue(statusOf("STARTED"));
    const onReportRecoveryChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={RUN}
        onReportRecoveryChange={onReportRecoveryChange}
      />,
    );

    await waitFor(() => expect(getJobStatus).toHaveBeenCalled());
    expect(onReportRecoveryChange).not.toHaveBeenCalled();
  });
});

describe("matriz de recuperación durable", () => {
  beforeEach(() => {
    getJobStatus.mockReset();
    getEvaluationResult.mockReset();
    getTargets.mockClear();
  });

  const completedRun: ActiveRun = {
    ...RUN,
    executionState: "completed",
    moleculeId: "mol-durable",
  };

  it("un 401 explica que la sesión caducó y conserva la corrida completada", async () => {
    getJobStatus.mockRejectedValue(new MockApiError(401));
    getEvaluationResult.mockRejectedValue(new MockApiError(401));
    const onActiveRunChange = vi.fn();

    render(<CaseEvaluationRunner caseId="caso-1" activeRun={completedRun} onActiveRunChange={onActiveRunChange} />);

    expect(await screen.findByText(/sesión caducó/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /iniciar sesión/i })).toBeInTheDocument();
    expect(onActiveRunChange.mock.calls.some(([run]) => run?.executionState === "failed")).toBe(false);
  });

  it("lee primero SQLite cuando el caso conserva un moleculeId durable", async () => {
    getEvaluationResult.mockResolvedValue({ molecule_id: "mol-durable", total_score: 81 });

    render(<CaseEvaluationRunner caseId="caso-1" activeRun={completedRun} />);

    await waitFor(() =>
      expect(getEvaluationResult).toHaveBeenCalledWith("mol-durable", "task-viva"),
    );
    expect(screen.getByTestId("pro")).toHaveTextContent("resultado:mol-durable");
    expect(getJobStatus).not.toHaveBeenCalled();
  });

  it("si SQLite falla temporalmente, usa el estado de la tarea como respaldo", async () => {
    getEvaluationResult.mockRejectedValue(new Error("SQLite ocupado"));
    getJobStatus.mockResolvedValue(
      statusOf("SUCCESS", { result: { molecule_id: "mol-status" } }),
    );

    render(<CaseEvaluationRunner caseId="caso-1" activeRun={completedRun} />);

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("resultado:mol-status"));
    expect(getEvaluationResult).toHaveBeenCalledWith("mol-durable", "task-viva");
    expect(getJobStatus).toHaveBeenCalledWith("task-viva");
  });

  it("registrar la corrida recién completada no superpone el aviso de recuperación", async () => {
    getJobStatus.mockResolvedValue(
      statusOf("SUCCESS", { result: { molecule_id: "mol-actual" } }),
    );
    const { rerender } = render(
      <CaseEvaluationRunner caseId="caso-1" activeRun={RUN} />,
    );

    await waitFor(() =>
      expect(screen.getByTestId("pro")).toHaveTextContent("resultado:mol-actual"),
    );

    rerender(
      <CaseEvaluationRunner
        caseId="caso-1"
        activeRun={{
          ...RUN,
          executionState: "completed",
          moleculeId: "mol-actual",
        }}
      />,
    );

    await waitFor(() => expect(screen.getByTestId("pro")).toHaveAttribute("data-recovery", "none"));
    expect(getJobStatus).toHaveBeenCalledTimes(1);
  });

  it("un arranque tardío del motor se recupera automáticamente sin intervención", async () => {
    getJobStatus.mockRejectedValueOnce(new Error("Error de conexión: motor apagado"));
    getEvaluationResult
      .mockRejectedValueOnce(new Error("Error de conexión: motor apagado"))
      .mockResolvedValueOnce({ molecule_id: "mol-reintentada" });

    render(<CaseEvaluationRunner caseId="caso-1" activeRun={completedRun} />);

    expect(await screen.findByText(/reintentando automáticamente/i)).toBeInTheDocument();
    await waitFor(() => expect(getEvaluationResult).toHaveBeenCalledTimes(2), { timeout: 2_000 });
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("mol-reintentada"));
    expect(getJobStatus).toHaveBeenCalledTimes(1);
  });

  it("un error no transitorio conserva el reintento manual sin relanzar la evaluación", async () => {
    getJobStatus.mockRejectedValueOnce(new MockApiError(422));
    getEvaluationResult
      .mockRejectedValueOnce(new MockApiError(422))
      .mockResolvedValueOnce({ molecule_id: "mol-reintentada-manual" });

    render(<CaseEvaluationRunner caseId="caso-1" activeRun={completedRun} />);

    const retry = await screen.findByRole("button", { name: /reintentar recuperación/i });
    retry.click();
    await waitFor(() => expect(getEvaluationResult).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByTestId("pro")).toHaveTextContent("mol-reintentada-manual"));
  });
});

// =====================================================================
// Contrato entre la comprobación previa y el submit
// =====================================================================

describe("contrato preflight-submit", () => {
  it("reutiliza byte por byte la pipeline_config firmada y no agrega defaults", async () => {
    const signedPipelineConfig = {
      enabled_stages: ["validation", "properties", "conformer", "docking"],
      stage_params: {
        docking: { exhaustiveness: 8, num_poses: 9 },
        conformer: { conformers: 1 },
      },
      docking_engine: "vina",
      pro_workers: 4,
    } satisfies CasePipelineConfig;
    const preflight = {
      fingerprint: `sha256:${"a".repeat(64)}`,
      inputDocument: "{}",
      generatedAt: "2026-09-01T12:00:00.000Z",
      schemaVersion: 1,
      executionRoute: "docking_vina",
      blockers: [],
      warnings: [],
      notEvaluated: [],
      receptorLabel: "1RKP · cadena A",
      ligandLabel: "CCO",
      gridLabel: "(0, 0, 0) · (30, 30, 30) Å",
      executionConfig: {
        gridCenter: [0, 0, 0],
        gridSize: [30, 30, 30],
        customHotspots: ["A:PHE75"],
        dockingEngine: "vina",
        exhaustiveness: 8,
        numPoses: 9,
        seed: 42,
        conformers: 1,
        pipelineConfig: signedPipelineConfig,
      },
    } satisfies PreflightSummary;
    submitEvaluation.mockResolvedValue({ task_id: "task-sin-409" });
    const onActiveRunChange = vi.fn();

    render(
      <CaseEvaluationRunner
        caseId="caso-contrato"
        inputs={{
          receptor: { pdbId: "1RKP", chain: "A", origin: "curado" },
          ligand: { inputSmiles: "CCO" },
          grid: { center: [0, 0, 0], size: [30, 30, 30] },
          customHotspots: ["A:PHE75"],
          dockingEngine: "vina",
          exhaustiveness: 8,
          numPoses: 9,
          conformers: 1,
          pipelineConfig: signedPipelineConfig,
        }}
        preflight={preflight}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Ejecutar prueba" }));

    await waitFor(() => expect(submitEvaluation).toHaveBeenCalledTimes(1));
    const submittedPipelineConfig = submitEvaluation.mock.calls[0][7];
    expect(submittedPipelineConfig).toEqual(signedPipelineConfig);
    expect(submittedPipelineConfig).not.toHaveProperty("stage_params.docking.seed");
    expect(submitEvaluation.mock.calls[0][8]).toBe(preflight.fingerprint);
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task-sin-409",
          inputFingerprint: preflight.fingerprint,
        }),
      ),
    );
  });
});
