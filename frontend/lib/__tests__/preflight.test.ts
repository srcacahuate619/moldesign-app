// =====================================================================
// Cliente del preflight — invalidación, bloqueo y puerto dinámico
// =====================================================================
//
// Tres cosas que este archivo protege:
//
// 1. **La petición sale por `getApiUrl()`.** Un puerto fijo aquí rompería el
//    escritorio en cuanto 8000 esté ocupado, que es el caso normal.
// 2. **Ante la duda, se invalida.** `inputsAffectRun` decide si el preflight
//    anterior dejó de describir la corrida. El sesgo es deliberado: un
//    preflight de más cuesta una petición; uno de menos deja ejecutar algo que
//    nadie inspeccionó.
// 3. **El bloqueo se explica.** Un botón deshabilitado sin frase es un
//    callejón sin salida.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  describeRunBlock,
  inputsAffectRun,
  inputsAreComplete,
  requestPreflight,
  summarizePreflight,
  type PreflightReport,
} from "../preflight";
import { resetApiUrl, setApiUrlFromPort } from "../config";
import { mockFetch } from "../../vitest.setup";
import type { CaseInputs, PreflightSummary } from "../cases/types";

const BASE_INPUTS: CaseInputs = {
  receptor: { pdbId: "7E2Y", chain: "A", origin: "curado" },
  ligand: { inputSmiles: "CC(=O)Oc1ccccc1C(=O)O" },
  grid: { center: [1, 2, 3], size: [20, 20, 20] },
};

function reportFixture(overrides: Partial<PreflightReport> = {}): PreflightReport {
  return {
    schema_version: 1,
    generated_at: "2026-08-24T10:00:00.000Z",
    execution_route: "docking_vina",
    input_fingerprint: "sha256:abc123def456",
    input_document: '{"chain":"A"}',
    receptor: {
      reference: "ref-1",
      pdb_id: "7E2Y",
      chain: "A",
      origin: "curado",
      source_available: true,
      source_sha256: "sha256:fuente",
      prepared_available: false,
      prepared_sha256: null,
      prepared_compatible: null,
      prepared_chains: [],
    },
    ligand: {
      input_smiles: "O=C(C)Oc1ccccc1C(=O)O",
      canonical_smiles: "CC(=O)Oc1ccccc1C(=O)O",
      smiles_hash: "hash",
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
    preparation_diff: {
      state: "no_evaluado",
      reason: "sin fuente",
      source: null,
      route_input: null,
      removed: null,
      preserved: null,
    },
    controls: [],
    technical_blockers: [],
    warnings: [],
    not_evaluated: [],
    ...overrides,
  } as PreflightReport;
}

describe("requestPreflight", () => {
  beforeEach(() => {
    resetApiUrl();
    mockFetch.mockReset();
  });
  afterEach(() => resetApiUrl());

  it("usa el puerto que resolvió el runtime, nunca uno fijo", async () => {
    setApiUrlFromPort(8007);
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(reportFixture()), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await requestPreflight({ smiles: "CCO", targetPdbId: "7E2Y" });

    const [url, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8007/evaluation/preflight");
    expect(init.method).toBe("POST");
  });

  it("envía exactamente los inputs que después irán a la corrida", async () => {
    setApiUrlFromPort(8000);
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify(reportFixture()), { status: 200 }),
    );

    await requestPreflight({
      smiles: "CCO",
      targetPdbId: "7e2y",
      chain: "B",
      gridCenter: [1, 2, 3],
      gridSize: [20, 20, 20],
      customHotspots: ["TYR1"],
      dockingEngine: "qvina2",
      exhaustiveness: 12,
      numPoses: 7,
    });

    const [, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({
      smiles: "CCO",
      target_pdb_id: "7e2y",
      chain: "B",
      grid_center: [1, 2, 3],
      grid_size: [20, 20, 20],
      custom_hotspots: ["TYR1"],
      docking_engine: "qvina2",
      exhaustiveness: 12,
      num_poses: 7,
      // El protocolo de generación 3D viaja con la comprobación: entra en la
      // huella, así que lo que se ejecuta es lo que se inspeccionó. `null`
      // cuando el caso no lo declara — el backend aplica el defecto de 1.
      conformers: null,
    });
  });

  it("un fallo del motor se reporta como fallo del motor, no del ligando", async () => {
    setApiUrlFromPort(8000);
    mockFetch.mockResolvedValue(new Response("boom", { status: 503 }));

    await expect(requestPreflight({ smiles: "CCO", targetPdbId: "7E2Y" })).rejects.toThrow(
      /no se pudo completar/i,
    );
  });
});

describe("summarizePreflight", () => {
  it("guarda lo justo para reabrir el caso y decidir si se puede ejecutar", () => {
    const summary = summarizePreflight(
      reportFixture({ technical_blockers: ["X"], warnings: ["Y", "Z"], not_evaluated: ["W"] }),
    );

    expect(summary.fingerprint).toBe("sha256:abc123def456");
    expect(summary.blockers).toEqual(["X"]);
    expect(summary.warnings).toEqual(["Y", "Z"]);
    expect(summary.notEvaluated).toEqual(["W"]);
    expect(summary.receptorLabel).toBe("7E2Y · cadena A");
    // El resumen enseña el CANÓNICO: es el que se acopla.
    expect(summary.ligandLabel).toBe("CC(=O)Oc1ccccc1C(=O)O");
  });

  it("no copia el payload científico dentro del caso", () => {
    const summary = summarizePreflight(reportFixture()) as unknown as Record<string, unknown>;
    // Ni controles, ni diff, ni hashes: eso pertenece al backend y envejecería
    // dentro de `case.json` sin que nada lo revalidara.
    expect(summary.controls).toBeUndefined();
    expect(summary.preparation_diff).toBeUndefined();
    expect(summary.receptor).toBeUndefined();
  });

  it("declara cuando la caja la derivará la corrida", () => {
    const summary = summarizePreflight(
      reportFixture({
        effective_config: {
          ...reportFixture().effective_config,
          grid_center: [10, 11, 12],
          grid_center_origin: "derivado_dinamico",
        },
      }),
    );
    expect(summary.gridLabel).toContain("derivada del PDB");
  });
});

describe("inputsAffectRun", () => {
  it("no invalida si nada cambió", () => {
    expect(inputsAffectRun(BASE_INPUTS, { ...BASE_INPUTS })).toBe(false);
  });

  it.each([
    ["receptor", { receptor: { pdbId: "1ABC", origin: "curado" as const } }],
    ["cadena", { receptor: { pdbId: "7E2Y", chain: "B", origin: "curado" as const } }],
    ["ligando", { ligand: { inputSmiles: "CCO" } }],
    ["centro de la caja", { grid: { center: [9, 9, 9] as const, size: [20, 20, 20] as const } }],
    ["tamaño de la caja", { grid: { center: [1, 2, 3] as const, size: [30, 30, 30] as const } }],
    ["hotspots", { customHotspots: ["TYR1"] }],
    ["motor", { dockingEngine: "qvina2" }],
    ["exhaustividad", { exhaustiveness: 16 }],
    ["número de poses", { numPoses: 12 }],
  ])("invalida al cambiar %s", (_label, patch) => {
    expect(inputsAffectRun(BASE_INPUTS, { ...BASE_INPUTS, ...patch } as CaseInputs)).toBe(true);
  });

  it("el ruido de coma flotante no invalida", () => {
    const noisy: CaseInputs = {
      ...BASE_INPUTS,
      grid: { center: [1.0000001, 2, 3], size: [20, 20, 20] },
    };
    expect(inputsAffectRun(BASE_INPUTS, noisy)).toBe(false);
  });

  it("reordenar hotspots no invalida", () => {
    const a: CaseInputs = { ...BASE_INPUTS, customHotspots: ["TYR1", "ASP2"] };
    const b: CaseInputs = { ...BASE_INPUTS, customHotspots: ["ASP2", "TYR1"] };
    expect(inputsAffectRun(a, b)).toBe(false);
  });

  it("pasar de nada a algo invalida", () => {
    expect(inputsAffectRun(undefined, BASE_INPUTS)).toBe(true);
  });
});

describe("describeRunBlock", () => {
  const preflight: PreflightSummary = {
    fingerprint: "sha256:abc",
    inputDocument: "{}",
    generatedAt: "2026-08-24T10:00:00.000Z",
    schemaVersion: 1,
    executionRoute: "docking_vina",
    blockers: [],
    warnings: ["METALES_ELIMINADOS"],
    notEvaluated: [],
    receptorLabel: "7E2Y · cadena A",
    ligandLabel: "CCO",
    gridLabel: "(1, 2, 3)",
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

  it("pide receptor y ligando antes que nada", () => {
    expect(describeRunBlock(undefined, undefined)).toMatch(/receptor/i);
    expect(describeRunBlock({ receptor: BASE_INPUTS.receptor }, undefined)).toMatch(/ligando/i);
  });

  it("exige un preflight vigente", () => {
    expect(describeRunBlock(BASE_INPUTS, undefined)).toMatch(/comprobar preparación/i);
  });

  it("las advertencias científicas NO bloquean", () => {
    expect(describeRunBlock(BASE_INPUTS, preflight)).toBeNull();
  });

  it("los bloqueantes técnicos bloquean y dicen cuáles", () => {
    const blocked = describeRunBlock(BASE_INPUTS, {
      ...preflight,
      blockers: ["RECEPTOR_CADENA_PRESENTE"],
    });
    expect(blocked).toContain("RECEPTOR_CADENA_PRESENTE");
    expect(blocked).toMatch(/bloqueante/i);
  });
});

describe("inputsAreComplete", () => {
  it("exige receptor y ligando no vacío", () => {
    expect(inputsAreComplete(undefined)).toBe(false);
    expect(inputsAreComplete({ receptor: BASE_INPUTS.receptor })).toBe(false);
    expect(inputsAreComplete({ ...BASE_INPUTS, ligand: { inputSmiles: "   " } })).toBe(false);
    expect(inputsAreComplete(BASE_INPUTS)).toBe(true);
  });
});
