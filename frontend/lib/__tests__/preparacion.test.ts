// =====================================================================
// Preparación — qué corrida se audita y cómo se lee la auditoría
// =====================================================================
//
// TRES COSAS QUE ESTE ARCHIVO PROTEGE:
//
// 1. **Se audita la corrida ACTIVA del caso, terminada y con su molécula.**
//    Nunca «el último resultado de la molécula»: el backend contrasta el
//    `task_id`, y auditar otra corrida sería documentar algo que no se pidió.
// 2. **La relación corrida↔inputs es la misma que la del informe del caso.**
//    Las dos pantallas describen la misma corrida y no pueden discrepar.
// 3. **Una respuesta con forma desconocida no se pinta.** Si el contrato
//    cambiara, la interfaz lo diría en vez de enseñar bloques vacíos como si
//    fueran una auditoría.

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { DossierError, buildCaseProjection, requestPreparacion } from "../dossier";
import {
  BLOQUES_PREPARACION,
  corridaDelCaso,
  esAuditoriaPreparacion,
  valorVisible,
  type AuditoriaPreparacion,
  type RequisitoPreparacion,
} from "../preparacion";
import { relacionDeLaCorridaActiva, type ActiveRun, type CaseRecord } from "../cases/types";
import { resetApiUrl, setApiUrlFromPort } from "../config";
import { mockFetch } from "../../vitest.setup";

const MOLECULA = "11111111-2222-3333-4444-555555555555";

function caso(overrides: Partial<CaseRecord> = {}): CaseRecord {
  return {
    schemaVersion: 3,
    id: "case-0001",
    name: "Serie de anilinas",
    createdAt: "2026-08-01T09:00:00.000Z",
    updatedAt: "2026-08-01T09:30:00.000Z",
    lastOpenedAt: "2026-08-01T09:30:00.000Z",
    status: "review",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    runs: [],
    activeView: "evaluation",
    context: {},
    archived: false,
    ...overrides,
  };
}

function corrida(overrides: Partial<ActiveRun> = {}): ActiveRun {
  return {
    taskId: "task-abcdef123456",
    moleculeId: MOLECULA,
    executionState: "completed",
    startedAt: "2026-08-01T09:10:00.000Z",
    inputFingerprint: "huella-1",
    ...overrides,
  } as ActiveRun;
}

function auditoria(overrides: Partial<AuditoriaPreparacion> = {}): AuditoriaPreparacion {
  return {
    schema: "preparacion/v1",
    alcance: "Auditor de readiness para FEP en desarrollo",
    transferencia_fep_demostrada: false,
    estado: "BLOQUEADO",
    razon: "Falta evidencia imprescindible o hay una abstención declarada.",
    bloqueantes: ["entorno.metales_cofactores"],
    en_revision: [],
    bloques: BLOQUES_PREPARACION.map((id) => ({ id, estado: "REGISTRADO" as const, requisitos: [] })),
    corrida: { case_id: "case-0001", molecule_id: MOLECULA, task_id: "task-abcdef123456", target: "1C3R" },
    generated_at: "2026-09-27T12:00:00+00:00",
    paquete: { rotulo: "Paquete de la corrida", aviso: "No es un paquete FEP." },
    ...overrides,
  };
}

describe("corridaDelCaso", () => {
  it("audita la corrida activa terminada, con su molécula", () => {
    const resultado = corridaDelCaso(
      caso({ activeRun: corrida(), preflight: { fingerprint: "huella-1" } as CaseRecord["preflight"] }),
    );
    expect(resultado).toEqual({
      kind: "auditable",
      run: corrida(),
      reportable: { taskId: "task-abcdef123456", moleculeId: MOLECULA, certified: false },
      relation: "corresponde",
    });
  });

  it("sin corrida, sin terminar o sin molécula, lo dice y no audita", () => {
    expect(corridaDelCaso(caso()).kind).toBe("sin_corrida");
    expect(corridaDelCaso(caso({ activeRun: corrida({ executionState: "running" }) })).kind).toBe(
      "sin_terminar",
    );
    expect(corridaDelCaso(caso({ activeRun: corrida({ moleculeId: undefined }) })).kind).toBe(
      "sin_molecula",
    );
  });

  it("una corrida cancelada o fallida terminó: no se dice que no ha terminado", () => {
    for (const executionState of ["cancelled", "failed"] as const) {
      expect(corridaDelCaso(caso({ activeRun: corrida({ executionState }) })).kind).toBe(
        "sin_completar",
      );
    }
  });

  it("una corrida de inputs anteriores se audita, pero con su relación", () => {
    const resultado = corridaDelCaso(
      caso({ activeRun: corrida(), preflight: { fingerprint: "huella-2" } as CaseRecord["preflight"] }),
    );
    expect(resultado.kind === "auditable" && resultado.relation).toBe("corrida_anterior");
  });
});

describe("relacionDeLaCorridaActiva", () => {
  it("hereda la huella del sistema estructural sellado desde esa corrida", () => {
    const record = caso({
      activeRun: corrida({ inputFingerprint: undefined }),
      preflight: { fingerprint: "huella-sellada" } as CaseRecord["preflight"],
      structuralSystem: {
        sourceRunTaskId: "task-abcdef123456",
        inputFingerprint: "huella-sellada",
      } as CaseRecord["structuralSystem"],
    });
    expect(relacionDeLaCorridaActiva(record)).toBe("corresponde");
  });

  it("sin corrida es desconocida", () => {
    expect(relacionDeLaCorridaActiva(caso())).toBe("desconocida");
  });
});

describe("esAuditoriaPreparacion", () => {
  it("acepta el contrato preparacion/v1", () => {
    expect(esAuditoriaPreparacion(auditoria())).toBe(true);
  });

  it.each([{ accion_recomendada: 42 }, { ubicacion: "A:197" }, { ubicacion: [{}] }, { ubicacion: [{ chain: "A", after: "THR 197", before: "VAL 199", c_n_distance_A: 4.79, distance_to_box_A: -1, missing_declared: null, site_critical: true }] }])("rechaza metadatos de reparación malformados: %j", (metadata) => {
    const value = auditoria();
    (value.bloques[0] as { requisitos: unknown }).requisitos = [{ clave: "receptor.huecos", estado: "ABSTENCION", ...metadata }] as unknown as RequisitoPreparacion[];
    expect(esAuditoriaPreparacion(value)).toBe(false);
  });

  describe("contexto de ensayo (C-GAP-02)", () => {
    const comparacion = {
      contrato: "moldesign.contexto_ensayo/1", campo: "ph", ensayo: 5.5, corrida: 7.4,
      estado: "discrepancia", fuente_ensayo: "case.context.assay.ph", fuente_corrida: "receptor.ph",
    };
    const resumen = {
      contrato: "moldesign.contexto_ensayo/1",
      declarados_sin_contraparte: { temperature_c: 25, endpoint: "Ki", source: "CHEMBL853189" },
    };
    const con = (ensayo: unknown) => {
      const value = auditoria();
      (value.bloques[0] as { requisitos: unknown }).requisitos =
        [{ clave: "entorno.ensayo", estado: "REGISTRADO", ensayo }] as unknown as RequisitoPreparacion[];
      return value;
    };

    it("acepta la comparación de un campo y el resumen de lo declarado, que no son huecos", () => {
      expect(esAuditoriaPreparacion(con(comparacion))).toBe(true);
      expect(esAuditoriaPreparacion(con(resumen))).toBe(true);
    });

    it("sigue rechazando esas formas dentro de `ubicacion`: era el defecto que impedía abrir Preparación", () => {
      for (const forma of [comparacion, resumen]) {
        const value = auditoria();
        (value.bloques[0] as { requisitos: unknown }).requisitos =
          [{ clave: "entorno.ensayo", estado: "REGISTRADO", ubicacion: [forma] }] as unknown as RequisitoPreparacion[];
        expect(esAuditoriaPreparacion(value)).toBe(false);
      }
    });

    it.each([
      null, [], "ph", {}, { contrato: "" },
      { ...comparacion, estado: "similar" }, { ...comparacion, campo: undefined },
      { ...comparacion, fuente_corrida: 3 },
      { contrato: "moldesign.contexto_ensayo/1", declarados_sin_contraparte: [] },
      { contrato: "moldesign.contexto_ensayo/1", declarados_sin_contraparte: { temperature_c: { x: 1 } } },
    ])("rechaza un `ensayo` malformado: %j", (ensayo) => {
      expect(esAuditoriaPreparacion(con(ensayo))).toBe(false);
    });
  });

  it("rechaza otro esquema, otro estado o bloques fuera de orden", () => {
    expect(esAuditoriaPreparacion({ ...auditoria(), schema: "preparacion/v2" })).toBe(false);
    expect(esAuditoriaPreparacion({ ...auditoria(), estado: "LISTO" })).toBe(false);
    const alReves = [...auditoria().bloques].reverse();
    expect(esAuditoriaPreparacion({ ...auditoria(), bloques: alReves })).toBe(false);
    expect(esAuditoriaPreparacion(null)).toBe(false);
  });
});

describe("valorVisible", () => {
  const base: RequisitoPreparacion = {
    clave: "entorno.aguas",
    etiqueta: "Aguas junto al sitio",
    valor: "3 retirada(s)",
    estado: "REVISAR",
    razon: "No se ha decidido cuáles son estructurales.",
    valor_es_clasificacion: false,
    fuente: "receptor_prep.species_diff.near_site",
    imprescindible: false,
  };

  it("un valor en estado de reserva no se enseña, salvo que sea la clasificación", () => {
    expect(valorVisible(base)).toBeNull();
    expect(valorVisible({ ...base, valor_es_clasificacion: true })).toBe("3 retirada(s)");
    expect(valorVisible({ ...base, estado: "REGISTRADO" })).toBe("3 retirada(s)");
  });
});

describe("requestPreparacion", () => {
  beforeEach(() => {
    resetApiUrl();
    setApiUrlFromPort(8017);
  });

  afterEach(() => {
    resetApiUrl();
  });

  it("pide la auditoría por POST con la misma proyección que el dossier", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(auditoria()), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const reportable = { taskId: "task-abcdef123456", moleculeId: MOLECULA, certified: false };
    const projection = buildCaseProjection(caso({ activeRun: corrida() }), reportable, "corresponde");

    const respuesta = await requestPreparacion(MOLECULA, projection);

    const [url, init] = mockFetch.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`http://127.0.0.1:8017/evaluation/dossier/${MOLECULA}/preparacion`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual(projection);
    expect(respuesta.estado).toBe("BLOQUEADO");
  });

  it("una forma desconocida es un error, no una auditoría vacía", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ schema: "otra" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const reportable = { taskId: "t", moleculeId: MOLECULA, certified: false };
    await expect(
      requestPreparacion(MOLECULA, buildCaseProjection(caso(), reportable, "desconocida")),
    ).rejects.toBeInstanceOf(DossierError);
  });

  it("el 409 del backend llega tal cual", async () => {
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: "El resultado almacenado pertenece a otra corrida." }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
    );
    const reportable = { taskId: "t", moleculeId: MOLECULA, certified: false };
    const promesa = requestPreparacion(MOLECULA, buildCaseProjection(caso(), reportable, "desconocida"));
    await expect(promesa).rejects.toMatchObject({ status: 409 });
  });
});

describe("última corrida completada (QA-035)", () => {
  it("tres completas y una cancelada: audita la tercera y su huella", () => {
    const runs = [1, 2, 3].map((n) => corrida({ taskId: `completa-${n}`, inputFingerprint: `huella-${n}` }));
    const cancelled = corrida({ taskId: "cancelada", executionState: "cancelled", inputFingerprint: "huella-4" });
    const record = caso({ runs, activeRun: cancelled, preflight: { fingerprint: "huella-4" } as CaseRecord["preflight"] });
    const selected = corridaDelCaso(record);
    expect(selected.kind).toBe("auditable");
    if (selected.kind !== "auditable") return;
    expect(selected.reportable.taskId).toBe("completa-3");
    expect(selected.relation).toBe("corrida_anterior");
    const snapshot = { ...record, activeRun: (selected as typeof selected & { run: ActiveRun }).run };
    expect(buildCaseProjection(snapshot, selected.reportable, selected.relation).run?.task_id).toBe("completa-3");
    expect(record.activeRun?.taskId).toBe("cancelada");
  });
  it("una única completa en el libro se audita aun sin activeRun", () => {
    const result = corridaDelCaso(caso({ runs: [corrida()] }));
    expect(result.kind).toBe("auditable");
    if (result.kind === "auditable") expect(result.reportable.taskId).toBe("task-abcdef123456");
  });
  it("ninguna completa: una fallida y una cancelada se declaran sin completar", () => {
    expect(corridaDelCaso(caso({ runs: [corrida({ executionState: "failed" }), corrida({ executionState: "cancelled", taskId: "cancelada" })] })).kind).toBe("sin_completar");
  });
});
