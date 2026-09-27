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
