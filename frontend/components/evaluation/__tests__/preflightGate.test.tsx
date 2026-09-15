// =====================================================================
// La corrida sólo ejecuta lo que el preflight inspeccionó
// =====================================================================
//
// EL FALLO QUE ESTE ARCHIVO IMPIDE: que la interfaz muestre una comprobación
// de unos inputs y el submit envíe otros. Si eso pudiera pasar, el informe de
// preparación sería decorativo y el fingerprint no demostraría nada.
//
// `ProEvaluation` se mockea a lo mínimo —un botón que dispara `handleSubmit` y
// la razón de bloqueo— porque lo que se prueba aquí es el CONTRATO del runner,
// no la pantalla de presentación.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";

import { LanguageProvider } from "../../../context/LanguageContext";

// El componente avisa —con razón— cuando se monta fuera del proveedor de
// idioma y cae al diccionario en castellano. Montarlo como lo monta la
// aplicacion quita ese aviso Y prueba el arbol real, no uno degradado.
function montar(elemento: React.ReactElement) {
  // `LanguageProvider` lee la sesión para recordar el idioma por cuenta, así
  // que el árbol real lleva los dos. Montar sólo uno era lo que producía el
  // aviso «useLanguage fuera de LanguageProvider» en la salida de la suite.
  return render(<LanguageProvider>{elemento}</LanguageProvider>);
}

import type { CaseInputs, PreflightSummary } from "../../../lib/cases/types";
import type { Target } from "../../../lib/api";

const getJobStatus = vi.fn();
const getTargets = vi.fn<() => Promise<Target[]>>(async () => []);
const submitEvaluation = vi.fn();

vi.mock("../../../lib/auth", () => ({
  // `LanguageProvider` monta dentro del árbol de sesión para recordar el
  // idioma por cuenta. El mock lo expone como paso a través: la sesión ya la
  // fija `useAuth` de aquí arriba.
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({
    isLoading: false,
    logout: vi.fn(),
    token: "test-token",
    user: { user_id: "test-user" },
  }),
}));

vi.mock("../../../lib/api", () => ({
  getJobStatus: (id: string) => getJobStatus(id),
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

const requestPreflight = vi.fn();
vi.mock("../../../lib/preflight", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/preflight")>(
    "../../../lib/preflight",
  );
  return { ...actual, requestPreflight: (...args: unknown[]) => requestPreflight(...args) };
});

// Mock mínimo de la pantalla: expone el submit y la razón de bloqueo.
let latestProProps: Record<string, any> = {};
vi.mock("../../interfaces/pro/ProEvaluation", () => ({
  default: (props: Record<string, any>) => {
    latestProProps = props;
    const { handleSubmit, runBlockedReason, preparationSlot, setTarget } = props;
    return (
      <div>
      <button
        type="button"
        data-testid="run"
        disabled={Boolean(runBlockedReason)}
        onClick={() =>
          handleSubmit?.(
            [0, 0, 0],
            [22.5, 22.5, 22.5],
            undefined,
            undefined,
            { enabled_stages: [] },
          )
        }
      >
        Ejecutar
      </button>
      <button type="button" data-testid="select-other-target" onClick={() => setTarget?.("2XYZ")}>
        Otro receptor
      </button>
      <p data-testid="blocked">{runBlockedReason ?? ""}</p>
      {preparationSlot}
      </div>
    );
  },
}));

import CaseEvaluationRunner from "../CaseEvaluationRunner";

const INPUTS: CaseInputs = {
  receptor: { pdbId: "7E2Y", chain: "A", origin: "curado" },
  ligand: { inputSmiles: "CC(=O)Oc1ccccc1C(=O)O" },
  grid: { center: [1, 2, 3], size: [20, 20, 20] },
};

const PREFLIGHT: PreflightSummary = {
  fingerprint: "sha256:huella-inspeccionada",
  inputDocument: '{"chain":"A"}',
  generatedAt: "2026-08-24T10:00:00.000Z",
  schemaVersion: 1,
  executionRoute: "docking_vina",
  blockers: [],
  warnings: ["METALES_ELIMINADOS"],
  notEvaluated: [],
  receptorLabel: "7E2Y · cadena A",
  ligandLabel: "CC(=O)Oc1ccccc1C(=O)O",
  gridLabel: "(1.00, 2.00, 3.00)",
  executionConfig: {
    gridCenter: [1, 2, 3],
    gridSize: [20, 20, 20],
    customHotspots: [],
    dockingEngine: "vina",
    exhaustiveness: 8,
    numPoses: 9,
    seed: 42,
  },
};

describe("puerta de ejecución", () => {
  beforeEach(() => {
    vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-ES");
    // El catálogo se cachea entre montajes: cada prueba parte sin nada.
    invalidarCatalogo();
    getJobStatus.mockReset();
    getTargets.mockReset();
    getTargets.mockResolvedValue([]);
    submitEvaluation.mockReset();
    requestPreflight.mockReset();
    latestProProps = {};
    submitEvaluation.mockResolvedValue({ task_id: "task-nueva" });
  });

  it("sin preflight no se ejecuta, y se explica por qué", async () => {
    montar(<CaseEvaluationRunner caseId="c1" inputs={INPUTS} />);

    await waitFor(() => expect(screen.getByTestId("run")).toBeDisabled());
    expect(screen.getByTestId("blocked")).toHaveTextContent(/comprobar preparación/i);
    expect(submitEvaluation).not.toHaveBeenCalled();
  });

  it("una advertencia científica NO bloquea", async () => {
    montar(<CaseEvaluationRunner caseId="c1" inputs={INPUTS} preflight={PREFLIGHT} />);

    await waitFor(() => expect(screen.getByTestId("run")).toBeEnabled());
    expect(screen.getByTestId("blocked")).toHaveTextContent("");
  });

  it("al reabrir enseña el resumen persistido aunque el detalle ya no esté en memoria", async () => {
    montar(<CaseEvaluationRunner caseId="c1" inputs={INPUTS} preflight={PREFLIGHT} />);

    expect(await screen.findByText("7E2Y · cadena A")).toBeInTheDocument();
    // Mismo motivo que en `PreparationPanel.test.tsx`: el texto vive en el módulo
    // de traducción y jsdom resuelve `en-US`.
    const { pro } = await import("../../../context/traducciones/pro");
    expect(screen.getByText(pro.es.pr_resumen_guardado)).toBeInTheDocument();
    expect(screen.getByText(/vina · ex 8 · 9 poses/i)).toBeInTheDocument();
  });

  it("al reabrir restaura en los controles la configuración efectiva, no el sentinel crudo", async () => {
    montar(
      <CaseEvaluationRunner
        caseId="c1"
        inputs={{ ...INPUTS, grid: { center: [0, 0, 0], size: [22.5, 22.5, 22.5] } }}
        preflight={PREFLIGHT}
      />,
    );

    await waitFor(() => expect(latestProProps.initialRunConfiguration).toBeDefined());
    expect(latestProProps.initialRunConfiguration).toMatchObject({
      center: [1, 2, 3],
      size: [20, 20, 20],
      dockingEngine: "vina",
      exhaustiveness: 8,
      numPoses: 9,
    });
  });

  it("cambiar receptor reemplaza la caja y no arrastra hotspots del anterior", async () => {
    getTargets.mockResolvedValue([
      {
        id: "22",
        pdb_id: "2XYZ",
        name: "Receptor nuevo",
        organism: "Homo sapiens",
        resolution: 2.1,
        chain: "B",
        requires_cns: false,
        is_hot: false,
        spearman_rho: null,
        calibration_date: null,
        grid_center_x: 11,
        grid_center_y: 12,
        grid_center_z: 13,
        grid_size_x: 24,
        grid_size_y: 25,
        grid_size_z: 26,
        hotspots: [],
      },
    ]);
    const onInputsChange = vi.fn();
    montar(
      <CaseEvaluationRunner
        caseId="c1"
        inputs={{ ...INPUTS, customHotspots: ["A:OLD1"] }}
        onInputsChange={onInputsChange}
      />,
    );

    await waitFor(() => expect(latestProProps.targets).toHaveLength(1));
    fireEvent.click(screen.getByTestId("select-other-target"));

    expect(onInputsChange).toHaveBeenCalledWith(
      expect.objectContaining({
        receptor: expect.objectContaining({ pdbId: "2XYZ", chain: "B" }),
        grid: { center: [11, 12, 13], size: [24, 25, 26] },
        customHotspots: [],
      }),
    );
  });

  it("un bloqueante técnico sí bloquea y nombra la causa", async () => {
    montar(
      <CaseEvaluationRunner
        caseId="c1"
        inputs={INPUTS}
        preflight={{ ...PREFLIGHT, blockers: ["RECEPTOR_CADENA_PRESENTE"] }}
      />,
    );

    await waitFor(() => expect(screen.getByTestId("run")).toBeDisabled());
    expect(screen.getByTestId("blocked")).toHaveTextContent("RECEPTOR_CADENA_PRESENTE");
  });

  it("ejecuta con los inputs INSPECCIONADOS, no con los de la pantalla", async () => {
    // El mock de la pantalla envía una caja (0,0,0)/22.5 —la que tendría por
    // defecto— mientras el caso guarda (1,2,3)/20. Debe ganar el caso: es lo
    // que el preflight inspeccionó.
    montar(<CaseEvaluationRunner caseId="c1" inputs={INPUTS} preflight={PREFLIGHT} />);
    await waitFor(() => expect(screen.getByTestId("run")).toBeEnabled());

    fireEvent.click(screen.getByTestId("run"));

    await waitFor(() => expect(submitEvaluation).toHaveBeenCalled());
    const [smiles, target, , center, size] = submitEvaluation.mock
      .calls[0] as unknown as unknown[];
    expect(smiles).toBe("CC(=O)Oc1ccccc1C(=O)O");
    expect(target).toBe("7E2Y");
    expect(center).toEqual([1, 2, 3]);
    expect(size).toEqual([20, 20, 20]);
    expect(submitEvaluation.mock.calls[0]?.[8]).toBe(PREFLIGHT.fingerprint);
    expect(submitEvaluation.mock.calls[0]?.[9]).toBe("A");
  });

  it("registra en la corrida la huella de lo inspeccionado", async () => {
    const onRunRegistered = vi.fn(async () => true);
    montar(
      <CaseEvaluationRunner
        caseId="c1"
        inputs={INPUTS}
        preflight={PREFLIGHT}
        onRunRegistered={onRunRegistered}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("run")).toBeEnabled());

    fireEvent.click(screen.getByTestId("run"));

    await waitFor(() => expect(onRunRegistered).toHaveBeenCalled());
    expect((onRunRegistered.mock.calls[0] as unknown as unknown[])[0]).toMatchObject({
      taskId: "task-nueva",
      inputFingerprint: "sha256:huella-inspeccionada",
    });
  });

  it("el fingerprint sobrevive a las actualizaciones de progreso", async () => {
    // Sin esto, el primer `poll` reescribía `activeRun` sin huella y la
    // corrida perdía la única prueba de a qué hipótesis pertenece.
    getJobStatus.mockResolvedValue({
      task_id: "task-viva",
      status: "SUCCESS",
      progress: 100,
      result: { molecule_id: "mol-1" },
      error: null,
      started_at: "2026-08-24T09:00:00.000Z",
      finished_at: null,
    });
    const onActiveRunChange = vi.fn();

    montar(
      <CaseEvaluationRunner
        caseId="c1"
        inputs={INPUTS}
        preflight={PREFLIGHT}
        activeRun={{
          taskId: "task-viva",
          executionState: "running",
          startedAt: "2026-08-24T09:00:00.000Z",
          inputFingerprint: "sha256:huella-de-la-corrida",
        }}
        onActiveRunChange={onActiveRunChange}
      />,
    );

    await waitFor(() => expect(onActiveRunChange).toHaveBeenCalled());
    const calls = onActiveRunChange.mock.calls as unknown as unknown[][];
    const last = calls[calls.length - 1][0] as { inputFingerprint?: string };
    expect(last.inputFingerprint).toBe("sha256:huella-de-la-corrida");
  });

  it("el panel pide lo que falta en vez de ofrecer un botón inerte", async () => {
    montar(<CaseEvaluationRunner caseId="c1" inputs={{ ligand: { inputSmiles: "CCO" } }} />);

    expect(
      await screen.findByRole("button", { name: /comprobar preparación/i }),
    ).toBeDisabled();
    expect(screen.getByText(/elige un receptor para poder comprobar/i)).toBeInTheDocument();
  });

  it("comprobar la preparación guarda el resumen y el canónico", async () => {
    requestPreflight.mockResolvedValue({
      schema_version: 1,
      generated_at: "2026-08-24T10:00:00.000Z",
      execution_route: "docking_vina",
      input_fingerprint: "sha256:nueva-huella",
      input_document: "{}",
      receptor: {
        reference: null,
        pdb_id: "7E2Y",
        chain: "A",
        origin: "curado",
        source_available: true,
        source_sha256: "sha256:f",
        prepared_available: false,
        prepared_sha256: null,
        prepared_compatible: null,
        prepared_chains: [],
      },
      ligand: {
        input_smiles: "O=C(C)Oc1ccccc1C(=O)O",
        canonical_smiles: "CC(=O)Oc1ccccc1C(=O)O",
        smiles_hash: "h",
        molecular_formula: "C9H8O4",
        heavy_atom_count: 13,
        error: null,
        vina_atom_compatibility: { evaluated: true, supported: true, unsupported_elements: [] },
      },
      effective_config: {
        grid_center: [1, 2, 3],
        grid_size: [20, 20, 20],
        grid_center_origin: "override_usuario",
        grid_size_origin: "override_usuario",
        derived_box: null,
        hotspots: [],
        hotspots_origin: "ninguno",
        docking_engine: "vina",
        exhaustiveness: 8,
        num_poses: 9,
        seed: 42,
        heteroatom_policy: {
          route: "docking_vina",
          waters: "eliminadas",
          metals: "eliminados",
          organic_cofactors: "conservados_lista_producto",
          organic_cofactors_kept: ["NAD"],
          cofactors_whitelist_declared: [],
          cofactors_whitelist_applied: false,
          source: "preparer",
        },
      },
      preparation_diff: { state: "no_evaluado", reason: "sin fuente", source: null, route_input: null, removed: null, preserved: null },
      controls: [],
      technical_blockers: [],
      warnings: [],
      not_evaluated: [],
    });
    const onPreflightChange = vi.fn();
    const onInputsChange = vi.fn();

    montar(
      <CaseEvaluationRunner
        caseId="c1"
        inputs={INPUTS}
        onPreflightChange={onPreflightChange}
        onInputsChange={onInputsChange}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: /comprobar preparación/i }));

    await waitFor(() => expect(onPreflightChange).toHaveBeenCalled());
    expect((onPreflightChange.mock.calls[0] as unknown as unknown[])[0]).toMatchObject({
      fingerprint: "sha256:nueva-huella",
    });
    // El canónico se guarda JUNTO al texto introducido, sin sustituirlo.
    expect(onInputsChange).toHaveBeenCalledWith({
      ligand: {
        inputSmiles: "CC(=O)Oc1ccccc1C(=O)O",
        canonicalSmiles: "CC(=O)Oc1ccccc1C(=O)O",
      },
    });
  });

  it("un fallo del motor no se confunde con un problema del ligando", async () => {
    requestPreflight.mockRejectedValue(new Error("La comprobación previa no se pudo completar (HTTP 503)."));

    montar(<CaseEvaluationRunner caseId="c1" inputs={INPUTS} />);
    fireEvent.click(await screen.findByRole("button", { name: /comprobar preparación/i }));

    expect(await screen.findByText(/no se pudo completar/i)).toBeInTheDocument();
  });
});
