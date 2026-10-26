// =====================================================================
// Configuración efectiva del pipeline del caso: el K vigente gobierna (CAS-05)
// =====================================================================
//
// EL ESCENARIO DE LA AUDITORÍA (2026-09-30, 40 corridas reales): un caso
// corre primero con K=1 y queda con el sistema estructural sellado. El
// investigador pasa a Ensemble K=30, corre, abre Opciones y aplica SIN
// cambiar nada. El `onApply` reconstruía `conformer.conformers` desde
// `initialRunConfiguration` —que prioriza el pipelineConfig CONGELADO de la
// primera corrida (K=1)—, así que el caso quedaba con conformers=30 arriba y
// conformers=1 anidado: el siguiente preflight declaraba 30, la
// revalidación del submit firmaba 1, y la corrida moría con 409
// («La hipótesis o la preparación cambió») sin que nadie hubiera cambiado
// nada.
//
// LO QUE ESTE ARCHIVO FIJA:
//
// 1. `configuracionDelPipeline` fusiona POR ETAPA y CLAVE: un guardado
//    parcial (`conformer: {ph}` sin `conformers`) no puede borrar el
//    protocolo del caso.
// 2. El `onApply` del modal Opciones lee el K VIGENTE del caso (prop
//    `activeConformers`), no el congelado de la primera corrida.
// 3. Con el sistema sellado, aplicar Opciones sin cambios conserva K=30
//    de extremo a extremo.
//
// `ProEvaluation` se mockea por las mismas razones que en
// `CaseEvaluationRunner.test.tsx`: montarla de verdad arrastra Ketcher y
// Molstar. Las decisiones de cableado se leen del origen — el mismo
// enfoque que `AdmetOptIn.test.ts`.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type {
  CaseInputs,
  CasePipelineConfig,
  CaseStructuralSystem,
} from "../../../lib/cases/types";

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
  ApiError: class extends Error {
    readonly status: number;
    constructor(status: number, message = `HTTP ${status}`) {
      super(message);
      this.status = status;
    }
  },
  getJobStatus: vi.fn(),
  getEvaluationResult: vi.fn(),
  getTargets: vi.fn(async () => []),
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
    activeConformers,
    ejemploEnEditor,
    initialRunConfiguration,
    onRunConfigurationChange,
  }: {
    activeConformers?: number;
    ejemploEnEditor?: boolean;
    initialRunConfiguration?: {
      pipelineConfig?: CasePipelineConfig;
    };
    onRunConfigurationChange?: (config: {
      center: [number, number, number];
      size: [number, number, number];
      customHotspots: string[];
      dockingEngine: string;
      exhaustiveness: number;
      numPoses: number;
      conformers: number;
      pipelineConfig: CasePipelineConfig;
    }) => void;
  }) => (
    <div>
      <span data-testid="k-activo">{activeConformers ?? "ausente"}</span>
      <span data-testid="ejemplo-editor">
        {ejemploEnEditor === undefined ? "prop-ausente" : String(ejemploEnEditor)}
      </span>
      <span data-testid="k-congelado">
        {Number(
          initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.conformers ?? 1,
        )}
      </span>
      <button
        type="button"
        data-testid="aplicar-opciones"
        // El payload que el onApply REAL construye tras la corrección: el
        // anidado sale del K que el componente recibió como vigente.
        onClick={() =>
          onRunConfigurationChange?.({
            center: [43.21, 2.19, 46.19],
            size: [25.4, 25.4, 25.4],
            customHotspots: [],
            dockingEngine: "vina",
            exhaustiveness: 8,
            numPoses: 9,
            conformers: activeConformers ?? 1,
            pipelineConfig: {
              enabled_stages: [
                "validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn",
              ],
              stage_params: {
                docking: { exhaustiveness: 8, num_poses: 9 },
                properties: { run_admet_ai: false },
                conformer: { conformers: activeConformers ?? 1, ph: 7.4 },
              },
              docking_engine: "vina",
            },
          })
        }
      >
        aplicar
      </button>
    </div>
  ),
}));

import CaseEvaluationRunner, {
  configuracionDelPipeline,
} from "../CaseEvaluationRunner";
import { invalidarCatalogo } from "../../../lib/catalogoDeReceptores";

beforeEach(() => {
  invalidarCatalogo();
});

// ── 1. El merge de la configuración es por etapa y clave ───────────────

describe("configuracionDelPipeline: un guardado parcial no borra el protocolo", () => {
  it("un `conformer: {ph}` sin `conformers` hereda el K vigente, no lo pierde", () => {
    const config = configuracionDelPipeline({
      conformers: 30,
      pipelineConfig: { stage_params: { conformer: { ph: 7.4 } } },
    });
    expect(config.stage_params?.conformer?.conformers).toBe(30);
    expect(config.stage_params?.conformer?.ph).toBe(7.4);
  });

  it("un `docking` guardado a medias conserva las claves que no trae", () => {
    const config = configuracionDelPipeline({
      exhaustiveness: 16,
      pipelineConfig: { stage_params: { docking: { exhaustiveness: 16 } } },
    });
    expect(config.stage_params?.docking).toEqual({ exhaustiveness: 16, num_poses: 9 });
  });

  it("sin guardado, el defecto declara K=1, poses 9 y ADMET apagado", () => {
    const config = configuracionDelPipeline(undefined);
    expect(config.stage_params?.conformer).toEqual({ conformers: 1 });
    expect(config.stage_params?.docking).toEqual({ exhaustiveness: 8, num_poses: 9 });
    expect(config.stage_params?.properties).toEqual({ run_admet_ai: false });
  });

  it("un guardado completo pasa limpio: el merge no inventa ni pisa claves", () => {
    const guardado: CasePipelineConfig = {
      stage_params: {
        docking: { exhaustiveness: 16, num_poses: 5 },
        conformer: { conformers: 30, ph: 6.5 },
        properties: { run_admet_ai: true },
      },
      docking_engine: "vina",
    };
    const config = configuracionDelPipeline({ pipelineConfig: guardado });
    expect(config.stage_params).toEqual(guardado.stage_params);
  });
});

// ── 2. El cableado: el K vigente llega al modal de Opciones ──────────
//
// ProEvaluation tiene ~1800 líneas con visores 3D y SSE: montarlo probaría
// el visor, no la decisión. El origen del defecto era una expresión concreta
// — leer el K desde el sistema congelado— y eso se lee del fuente.

const proSource = readFileSync(
  resolve(process.cwd(), "components/interfaces/pro/ProEvaluation.tsx"),
  "utf8",
);

const runnerSource = readFileSync(
  resolve(process.cwd(), "components/evaluation/CaseEvaluationRunner.tsx"),
  "utf8",
);

describe("ProEvaluation: el onApply no puede reconstruir K desde el sistema congelado", () => {
  it("declara la prop del K vigente como parte de su contrato", () => {
    expect(proSource).toContain("activeConformers: number;");
  });

  it("el anidado del modal sale del K vigente del caso, no de initialRunConfiguration", () => {
    expect(proSource).toContain("initialConformers={activeConformers}");
    // `aplicarOpciones` (el onApply del modal) toma por defecto el K vigente.
    expect(proSource).toContain("conformers: number = activeConformers");
    expect(proSource).toContain("onApply={aplicarOpciones}");
    // La expresión del defecto: era el pipelineConfig congelado de la
    // primera corrida el que pisaba el K=30 del caso.
    expect(proSource).not.toContain(
      "conformers: initialRunConfiguration?.pipelineConfig?.stage_params?.conformer?.conformers",
    );
  });

  it("el runner pasa el K vigente de los inputs del caso", () => {
    expect(runnerSource).toContain("activeConformers={inputs?.conformers ?? 1}");
  });
});

// ── 3. El recorrido completo, con el sistema sellado ──────────────────

const INPUTS_K30: CaseInputs = {
  receptor: { pdbId: "3F75", origin: "curado", chain: "A" },
  ligand: { inputSmiles: "CC(=O)Oc1ccccc1C(=O)O" },
  grid: { center: [43.21, 2.19, 46.19], size: [25.4, 25.4, 25.4] },
  dockingEngine: "vina",
  exhaustiveness: 8,
  numPoses: 9,
  conformers: 30,
  pipelineConfig: {
    stage_params: { conformer: { conformers: 30 } },
  },
};

const SISTEMA_K1: CaseStructuralSystem = {
  lockedAt: "2026-09-30T12:00:00.000Z",
  sourceRunTaskId: "11111111-1111-1111-1111-111111111111",
  inputFingerprint: `sha256:${"a".repeat(64)}`,
  receptor: { pdbId: "3F75", origin: "curado", chain: "A" },
  grid: { center: [43.21, 2.19, 46.19], size: [25.4, 25.4, 25.4] },
  customHotspots: [],
  dockingEngine: "vina",
  exhaustiveness: 8,
  numPoses: 9,
  // El sistema se congeló con la primera corrida del caso: K=1. Es el origen
  // exacto del defecto — no un detalle del fixture.
  conformers: 1,
  pipelineConfig: {
    stage_params: { conformer: { conformers: 1 } },
  },
};

describe("CAS-05: aplicar Opciones tras pasar a ensemble, con sistema sellado", () => {
  it("el modal recibe el K vigente (30) aunque el congelado diga 1", async () => {
    render(
      <CaseEvaluationRunner
        caseId="caso-40"
        inputs={INPUTS_K30}
        structuralSystem={SISTEMA_K1}
        structuralSystemSealed
      />,
    );
    // El catálogo carga async: el panel aparece cuando resuelve.
    await waitFor(() => expect(screen.getByTestId("k-activo").textContent).toBe("30"));
    // El congelado sigue siendo 1: el sistema no se reescribe; simplemente
    // deja de ser la fuente del K del protocolo.
    expect(screen.getByTestId("k-congelado").textContent).toBe("1");
  });

  it("aplicar sin cambios conserva K=30 en el anidado y no degrada el caso", async () => {
    const onInputsChange = vi.fn();
    render(
      <CaseEvaluationRunner
        caseId="caso-40"
        inputs={INPUTS_K30}
        structuralSystem={SISTEMA_K1}
        structuralSystemSealed
        onInputsChange={onInputsChange}
      />,
    );

    await waitFor(() => expect(screen.getByTestId("aplicar-opciones")).toBeTruthy());
    fireEvent.click(screen.getByTestId("aplicar-opciones"));

    expect(onInputsChange).toHaveBeenCalledTimes(1);
    const patch = onInputsChange.mock.calls[0][0] as Partial<CaseInputs>;
    const anidado = (patch.pipelineConfig as CasePipelineConfig | undefined)?.stage_params
      ?.conformer as { conformers?: number; ph?: number } | undefined;
    expect(anidado?.conformers).toBe(30);
    // El K aplicado viaja en ambos niveles, también con el sistema sellado.
    expect(patch.conformers).toBe(30);
  });
});

// ── CAS-04: la estimación describe el protocolo VIGENTE ───────────────
//
// La auditoría lo midió: con Ensemble K=30 la pantalla estimaba 7–14 s
// (K=1) mientras la corrida real tardó ~209 s. La estimación leía el K del
// sistema estructural CONGELADO en la primera corrida en vez del K que el
// panel de preparación acaba de elegir — el mismo K que firmará el
// preflight.

describe("CAS-04: la estimación usa el K vigente del caso", () => {
  it("el estimador recibe el K activo, no el congelado del sistema", () => {
    expect(proSource).toContain("conformers={activeConformers}");
    expect(proSource).not.toContain("conformers={conformerosConfigurados}");
  });
});

// ── SOL-10: el editor declara que su contenido es un ejemplo ──────────
//
// Un caso nuevo muestra aspirina en el editor aunque el caso no tiene
// ligando: estructura y SMILES parecían válidos mientras «Comprobar
// preparación» pedía un ligando. La decisión de producto (documentada en
// el propio código) es NO persistir la aspirina de muestra como si fuera
// la hipótesis del usuario — así que lo honesto es DECIR que es ejemplo.

describe("SOL-10: el editor comunica su ejemplo", () => {
  it("ProEvaluation pinta la nota de ejemplo con la clave de diccionario", () => {
    expect(proSource).toContain('t("ev_editor_ejemplo")');
  });

  it("el runner marca ejemplo cuando el caso no tiene ligando guardado", async () => {
    render(
      <CaseEvaluationRunner
        caseId="caso-nuevo"
        inputs={{ receptor: { pdbId: "3F75", origin: "curado", chain: "A" } }}
      />,
    );
    await waitFor(() => expect(screen.getByTestId("ejemplo-editor").textContent).toBe("true"));
  });

  it("con ligando guardado, el editor ya no es un ejemplo", async () => {
    render(
      <CaseEvaluationRunner caseId="caso-40" inputs={INPUTS_K30} />,
    );
    await waitFor(() => expect(screen.getByTestId("ejemplo-editor").textContent).toBe("false"));
  });
});
