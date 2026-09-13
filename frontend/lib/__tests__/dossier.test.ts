// =====================================================================
// Cliente del dossier — proyección, transporte y nombres
// =====================================================================
//
// CUATRO COSAS QUE ESTE ARCHIVO PROTEGE:
//
// 1. **La traducción camelCase → snake_case es exacta.** Es la clase de código
//    que se rompe en silencio: una clave mal escrita no falla, simplemente
//    desaparece del documento, y el dossier sale sin la mitad de lo que el caso
//    declaró. Se comprueba campo a campo.
//
// 2. **Un hueco sigue siendo un hueco.** Un campo sin responder se OMITE. No
//    viaja como `null` ni como cadena vacía, que el PDF imprimiría como una
//    respuesta en blanco en vez de como «NO DEFINIDO».
//
// 3. **El dossier se pide por POST.** La ruta histórica del certificado es un
//    GET a `/blockchain/...` y sigue existiendo para otra cosa. Si alguien
//    devolviera el dossier del caso a esa ruta, el caso dejaría de viajar y el
//    documento describiría otra pregunta.
//
// 4. **El fallo del backend se transmite, no se traduce a optimismo.** El 409
//    dice que el resultado guardado es de otra corrida; convertirlo en un PDF
//    silencioso sería empaquetar evidencia ajena.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  DossierError,
  PROJECTION_VERSION,
  buildCaseProjection,
  dossierPackageFilename,
  dossierPdfFilename,
  requestDossierPackage,
  requestDossierPreview,
  sanitizeFilenamePart,
  saveBlobAs,
} from "../dossier";
import { resetApiUrl, setApiUrlFromPort } from "../config";
import { mockFetch } from "../../vitest.setup";
import type { CaseRecord, ReportableResult } from "../cases/types";

const REPORTABLE: ReportableResult = {
  taskId: "task-abcdef123456",
  moleculeId: "11111111-2222-3333-4444-555555555555",
  certified: false,
};

/** Caso MÍNIMO: sólo lo que el esquema exige. Todo lo demás está ausente. */
function minimalCase(overrides: Partial<CaseRecord> = {}): CaseRecord {
  return {
    schemaVersion: 3,
    id: "case-0001",
    name: "Serie de anilinas",
    createdAt: "2026-08-01T09:00:00.000Z",
    updatedAt: "2026-08-01T09:30:00.000Z",
    lastOpenedAt: "2026-08-01T09:30:00.000Z",
    status: "review",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    activeView: "report",
    context: {},
    archived: false,
    ...overrides,
  };
}

/** Caso COMPLETO: cada campo que el contrato v1 admite tiene valor. */
function fullCase(): CaseRecord {
  return minimalCase({
    context: {
      studyKind: "explore-hypothesis",
      question: "¿Tolera el andamio el sustituyente?",
      decision: "Sintetizar o descartar la serie",
      systemRationale: "Cristal con el cofactor presente",
      controls: "Redock del ligando cristalográfico",
      assumptions: "Receptor rígido, protonación a pH 7.4",
      uncertainties: "No cubre selectividad",
      notes: "Revisado con el equipo",
    },
    inputs: {
      receptor: {
        targetId: "target-77",
        pdbId: "7E2Y",
        chain: "A",
        origin: "curado",
        name: "Proteasa principal",
      },
      ligand: {
        inputSmiles: "CCO",
        canonicalSmiles: "CCO",
        name: "etanol",
      },
      grid: { center: [1, 2, 3], size: [20, 20, 20] },
      customHotspots: ["HIS41"],
      dockingEngine: "vina",
      exhaustiveness: 8,
      numPoses: 9,
    },
    preflight: {
      fingerprint: "sha256:0123456789abcdef",
      inputDocument: "{documento canónico}",
      generatedAt: "2026-08-01T09:10:00.000Z",
      schemaVersion: 2,
      executionRoute: "docking_vina",
      blockers: [],
      warnings: ["RECEPTOR_SIN_PREPARAR"],
      notEvaluated: ["TAUTOMERIA"],
      receptorLabel: "7E2Y · cadena A",
      ligandLabel: "CCO",
      gridLabel: "(1.00, 2.00, 3.00) · (20.00, 20.00, 20.00) Å",
      executionConfig: {
        gridCenter: [10, 11, 12],
        gridSize: [22, 22, 22],
        customHotspots: ["HIS41", "CYS145"],
        dockingEngine: "vina",
        exhaustiveness: 16,
        numPoses: 5,
        seed: 42,
      },
    },
    activeRun: {
      taskId: REPORTABLE.taskId,
      executionState: "completed",
      startedAt: "2026-08-01T09:12:00.000Z",
      inputFingerprint: "sha256:0123456789abcdef",
    },
    decisions: [
      {
        controlCode: "RECEPTOR_SIN_PREPARAR",
        fingerprint: "sha256:0123456789abcdef",
        decision: "reconocida",
        at: "2026-08-01T09:11:00.000Z",
        note: "Se asume la preparación por defecto",
      },
    ],
  });
}

function pdfResponse(body = "%PDF-1.4", disposition?: string): Response {
  const headers = new Headers({ "content-type": "application/pdf" });
  if (disposition) headers.set("content-disposition", disposition);
  return new Response(body, { status: 200, headers });
}

function errorResponse(status: number, payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("buildCaseProjection", () => {
  it("traduce el caso COMPLETO a snake_case, campo a campo", () => {
    const projection = buildCaseProjection(fullCase(), REPORTABLE, "corresponde");

    expect(projection).toEqual({
      projection_version: PROJECTION_VERSION,
      case_id: "case-0001",
      case_schema_version: 3,
      name: "Serie de anilinas",
      created_at: "2026-08-01T09:00:00.000Z",
      context: {
        study_kind: "explore-hypothesis",
        question: "¿Tolera el andamio el sustituyente?",
        decision: "Sintetizar o descartar la serie",
        system_rationale: "Cristal con el cofactor presente",
        controls: "Redock del ligando cristalográfico",
        assumptions: "Receptor rígido, protonación a pH 7.4",
        uncertainties: "No cubre selectividad",
        notes: "Revisado con el equipo",
      },
      inputs: {
        receptor: {
          pdb_id: "7E2Y",
          chain: "A",
          origin: "curado",
          name: "Proteasa principal",
          target_id: "target-77",
        },
        ligand: {
          input_smiles: "CCO",
          canonical_smiles: "CCO",
          name: "etanol",
        },
        config: {
          grid_center: [10, 11, 12],
          grid_size: [22, 22, 22],
          custom_hotspots: ["HIS41", "CYS145"],
          docking_engine: "vina",
          exhaustiveness: 16,
          num_poses: 5,
          seed: 42,
        },
      },
      preflight: {
        fingerprint: "sha256:0123456789abcdef",
        generated_at: "2026-08-01T09:10:00.000Z",
        schema_version: 2,
        execution_route: "docking_vina",
        warnings: ["RECEPTOR_SIN_PREPARAR"],
        not_evaluated: ["TAUTOMERIA"],
        receptor_label: "7E2Y · cadena A",
        ligand_label: "CCO",
        grid_label: "(1.00, 2.00, 3.00) · (20.00, 20.00, 20.00) Å",
      },
      run: {
        task_id: REPORTABLE.taskId,
        input_fingerprint: "sha256:0123456789abcdef",
        execution_state: "completed",
        started_at: "2026-08-01T09:12:00.000Z",
      },
      decisions: [
        {
          control_code: "RECEPTOR_SIN_PREPARAR",
          fingerprint: "sha256:0123456789abcdef",
          decision: "reconocida",
          at: "2026-08-01T09:11:00.000Z",
          note: "Se asume la preparación por defecto",
        },
      ],
      run_inputs_relation: "corresponde",
    });
  });

  it("la configuración declarada es la EFECTIVA del preflight, no la pedida", () => {
    // Los inputs piden la caja (1,2,3)/20 y exhaustividad 8; el preflight
    // inspeccionó (10,11,12)/22 y exhaustividad 16. El dossier documenta lo que
    // se comprobó, no lo que se tecleó.
    const projection = buildCaseProjection(fullCase(), REPORTABLE, "corresponde");
    expect(projection.inputs.config?.grid_center).toEqual([10, 11, 12]);
    expect(projection.inputs.config?.exhaustiveness).toBe(16);
  });

  it("sin preflight, la configuración cae en los inputs y NO inventa una semilla", () => {
    const record = fullCase();
    const sinPreflight = minimalCase({ inputs: record.inputs, activeRun: record.activeRun });
    const projection = buildCaseProjection(sinPreflight, REPORTABLE, "desconocida");

    expect(projection.inputs.config).toEqual({
      grid_center: [1, 2, 3],
      grid_size: [20, 20, 20],
      custom_hotspots: ["HIS41"],
      docking_engine: "vina",
      exhaustiveness: 8,
      num_poses: 9,
    });
    expect(projection.inputs.config).not.toHaveProperty("seed");
    expect(projection).not.toHaveProperty("preflight");
  });

  it("los campos ausentes se OMITEN: no viajan como null ni como cadena vacía", () => {
    const projection = buildCaseProjection(minimalCase(), REPORTABLE, "desconocida");

    expect(projection.context).toEqual({});
    expect(projection.inputs).toEqual({});
    expect(projection).not.toHaveProperty("preflight");
    expect(projection).not.toHaveProperty("decisions");

    // Y lo que se serializa tampoco los lleva: `undefined` desaparece, pero un
    // `null` explícito habría sobrevivido y el backend lo habría rechazado.
    const wire = JSON.parse(JSON.stringify(projection));
    expect(Object.keys(wire)).not.toContain("preflight");
    expect(wire.context).toEqual({});
  });

  it("una respuesta en blanco no cuenta como respuesta", () => {
    const record = minimalCase({
      context: { question: "   ", notes: "" },
      inputs: { receptor: { pdbId: "  ", origin: "curado" }, ligand: { inputSmiles: "" } },
    });
    const projection = buildCaseProjection(record, REPORTABLE, "desconocida");

    expect(projection.context).toEqual({});
    // Un receptor sin PDB ID no es un receptor a medias: no se declara.
    expect(projection.inputs).toEqual({});
  });

  it("sin corrida guardada, declara la del resultado que se está documentando", () => {
    const projection = buildCaseProjection(minimalCase(), REPORTABLE, "desconocida");
    // Es un identificador REAL, observado por el cliente. Omitirlo dejaría al
    // backend sin poder contrastar que el resultado es de esta corrida.
    expect(projection.run).toEqual({ task_id: REPORTABLE.taskId });
  });

  it("sin corrida y sin resultado, `run` no se fabrica", () => {
    const projection = buildCaseProjection(minimalCase(), null, "desconocida");
    expect(projection).not.toHaveProperty("run");
  });

  it("no filtra la ruta del caso ni el documento canónico del preflight", () => {
    const record = fullCase();
    const enCarpeta = minimalCase({
      ...record,
      storage: { mode: "folder", path: "D:\\casos\\anilinas" },
    });
    const wire = JSON.stringify(buildCaseProjection(enCarpeta, REPORTABLE, "corresponde"));

    expect(wire).not.toContain("D:\\\\casos");
    expect(wire).not.toContain("storage");
    // `inputDocument` es procedencia local: el contrato no lo acepta.
    expect(wire).not.toContain("documento canónico");
    expect(wire).not.toContain("input_document");
  });

  it("transmite la relación con los inputs tal cual, incluidas las salvedades", () => {
    for (const relation of ["corresponde", "corrida_anterior", "desconocida"] as const) {
      expect(buildCaseProjection(minimalCase(), REPORTABLE, relation).run_inputs_relation).toBe(
        relation,
      );
    }
  });

  it("es pura: no toca el caso que recibe", () => {
    const record = fullCase();
    const snapshot = JSON.stringify(record);
    buildCaseProjection(record, REPORTABLE, "corresponde");
    expect(JSON.stringify(record)).toBe(snapshot);
  });
});

describe("transporte del dossier", () => {
  beforeEach(() => {
    resetApiUrl();
    setApiUrlFromPort(8017);
  });

  afterEach(() => {
    resetApiUrl();
  });

  it("pide la vista previa por POST a /evaluation/dossier, no por el GET histórico", async () => {
    mockFetch.mockResolvedValueOnce(pdfResponse());

    const projection = buildCaseProjection(fullCase(), REPORTABLE, "corresponde");
    await requestDossierPreview(REPORTABLE.moleculeId, projection);

    expect(mockFetch).toHaveBeenCalledTimes(1);
    const [url, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      `http://127.0.0.1:8017/evaluation/dossier/${REPORTABLE.moleculeId}/preview`,
    );
    expect(init.method).toBe("POST");
    expect(url).not.toContain("/blockchain/");
    // El caso viaja en el cuerpo: no cabe en una URL.
    expect(JSON.parse(init.body as string)).toEqual(projection);
  });

  it("pide el paquete por POST a /package", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response("PK", {
        status: 200,
        headers: { "content-type": "application/zip" },
      }),
    );

    await requestDossierPackage(
      REPORTABLE.moleculeId,
      buildCaseProjection(fullCase(), REPORTABLE, "corresponde"),
    );

    const [url, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(
      `http://127.0.0.1:8017/evaluation/dossier/${REPORTABLE.moleculeId}/package`,
    );
    expect(init.method).toBe("POST");
  });

  it("lleva la sesión: el dossier no es público", async () => {
    window.localStorage.setItem(
      "moldesign_auth",
      JSON.stringify({ token: "jwt-de-prueba", refreshToken: "r", user: {} }),
    );
    mockFetch.mockResolvedValueOnce(pdfResponse());

    await requestDossierPreview(
      REPORTABLE.moleculeId,
      buildCaseProjection(minimalCase(), REPORTABLE, "desconocida"),
    );

    const [, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer jwt-de-prueba");
  });

  it("usa el nombre que propone el backend cuando lo propone", async () => {
    mockFetch.mockResolvedValueOnce(
      pdfResponse("%PDF-1.4", 'inline; filename="dossier_Serie-de-anilinas.pdf"'),
    );

    const artifact = await requestDossierPreview(
      REPORTABLE.moleculeId,
      buildCaseProjection(fullCase(), REPORTABLE, "corresponde"),
    );

    expect(artifact.filename).toBe("dossier_Serie-de-anilinas.pdf");
  });

  it("el 409 llega con el mensaje del backend, y se puede reintentar", async () => {
    const detail =
      "El caso pide la corrida solicitada y el resultado almacenado pertenece a otra.";
    mockFetch.mockResolvedValueOnce(errorResponse(409, { detail }));

    const projection = buildCaseProjection(fullCase(), REPORTABLE, "corresponde");
    await expect(
      requestDossierPreview(REPORTABLE.moleculeId, projection),
    ).rejects.toMatchObject({ name: "DossierError", status: 409, message: detail });

    // Reintentar es una petición nueva, no un estado bloqueado.
    mockFetch.mockResolvedValueOnce(pdfResponse());
    const artifact = await requestDossierPreview(REPORTABLE.moleculeId, projection);
    expect(artifact.blob.size).toBeGreaterThan(0);
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it("aplana el 422 de pydantic en algo legible", async () => {
    mockFetch.mockResolvedValueOnce(
      errorResponse(422, {
        detail: [
          { loc: ["body", "preflight", "fingerprint"], msg: "String should have at least 8 characters" },
        ],
      }),
    );

    await expect(
      requestDossierPreview(
        REPORTABLE.moleculeId,
        buildCaseProjection(minimalCase(), REPORTABLE, "desconocida"),
      ),
    ).rejects.toMatchObject({
      status: 422,
      message: "preflight.fingerprint: String should have at least 8 characters",
    });
  });

  it("un 404 sin cuerpo útil se explica igualmente", async () => {
    mockFetch.mockResolvedValueOnce(new Response("", { status: 404 }));

    await expect(
      requestDossierPreview(
        REPORTABLE.moleculeId,
        buildCaseProjection(minimalCase(), REPORTABLE, "desconocida"),
      ),
    ).rejects.toMatchObject({ status: 404 });
  });

  it("un fallo de conexión NO se cuenta como un caso inválido", async () => {
    mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const failure = await requestDossierPreview(
      REPORTABLE.moleculeId,
      buildCaseProjection(minimalCase(), REPORTABLE, "desconocida"),
    ).catch((error: unknown) => error);

    expect(failure).toBeInstanceOf(DossierError);
    expect((failure as DossierError).status).toBeNull();
    expect((failure as DossierError).message).toMatch(/conexión/i);
  });

  it("la cancelación se propaga tal cual: no es un fallo del dossier", async () => {
    const abort = new DOMException("The user aborted a request.", "AbortError");
    mockFetch.mockRejectedValueOnce(abort);

    const failure = await requestDossierPreview(
      REPORTABLE.moleculeId,
      buildCaseProjection(minimalCase(), REPORTABLE, "desconocida"),
    ).catch((error: unknown) => error);

    expect(failure).toBe(abort);
    expect(failure).not.toBeInstanceOf(DossierError);
  });
});

describe("nombres de archivo", () => {
  it("saneado con la misma lista blanca que el backend", () => {
    expect(sanitizeFilenamePart("Serie de anilinas")).toBe("Serie-de-anilinas");
    expect(sanitizeFilenamePart("../escape")).toBe("escape");
    expect(sanitizeFilenamePart("   ")).toBe("sin-nombre");
    // Igual que el backend: los guiones de los extremos se recortan.
    expect(sanitizeFilenamePart("añil/β", 40)).toBe("a-il");
  });

  it("los nombres se derivan del caso y de la corrida", () => {
    expect(dossierPdfFilename("Serie de anilinas")).toBe("dossier_Serie-de-anilinas.pdf");
    expect(dossierPackageFilename("case-0001", "task-abcdef123456")).toBe(
      "moldesign_case_case-0001_run_task-abcdef1.zip",
    );
    expect(dossierPackageFilename("case-0001", undefined)).toBe(
      "moldesign_case_case-0001_run_sin-corrida.zip",
    );
  });
});

describe("saveBlobAs", () => {
  it("entrega el archivo y revoca el object URL", () => {
    // jsdom no implementa los object URL: se instalan para poder observarlos.
    const created: string[] = [];
    const revoked: string[] = [];
    const urlApi = window.URL as unknown as Record<string, unknown>;
    const previous = { create: urlApi.createObjectURL, revoke: urlApi.revokeObjectURL };
    urlApi.createObjectURL = () => {
      const url = `blob:mock/${created.length}`;
      created.push(url);
      return url;
    };
    urlApi.revokeObjectURL = (url: string) => {
      revoked.push(url);
    };
    const clicks: string[] = [];
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicks.push(this.download);
      });

    try {
      saveBlobAs(new Blob(["%PDF"], { type: "application/pdf" }), "dossier_Caso.pdf");
    } finally {
      urlApi.createObjectURL = previous.create;
      urlApi.revokeObjectURL = previous.revoke;
      clickSpy.mockRestore();
    }

    expect(clicks).toEqual(["dossier_Caso.pdf"]);
    expect(revoked).toEqual(created);
    // El ancla no se queda colgando del documento.
    expect(document.querySelectorAll("a[download]").length).toBe(0);
  });
});
