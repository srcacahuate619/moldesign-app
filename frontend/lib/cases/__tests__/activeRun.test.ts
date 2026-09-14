// =====================================================================
// Tests del LIBRO de corridas — el caso no pierde lo que produjo
// =====================================================================
//
// POR QUÉ ESTÁ EN EL MANIFIESTO Y NO EN MEMORIA. Su propósito es sobrevivir
// exactamente a lo que mata la memoria: cerrar la ventana, recargar, o cambiar
// de caso y volver. Sin esto, una corrida lanzada seguía viva en el backend y
// el usuario no tenía forma de volver a encontrarla: trabajo huérfano.
//
// POR QUÉ ES UNA LISTA. Hasta v6 el manifiesto guardaba `activeRun`, singular,
// y cada corrida nueva pisaba el puntero a la anterior. El informe seguía
// intacto en el backend y desde el caso ya no se llegaba a él. `activeRun`
// pasa a DERIVARSE de la última fila: en disco hay una sola fuente de verdad.
//
// Y ES ESTADO COMPUTACIONAL. `completed` aquí no completa el caso.

import { describe, expect, it } from "vitest";

import {
  caseWithRun,
  createCaseRecord,
  parseCaseManifest,
  parseCaseManifestText,
  serializeCaseManifest,
} from "../schema";
import {
  CaseError,
  hasCompletedRun,
  isRunBlocking,
  isTerminalRunState,
  latestRun,
  structuralSystemIsSealed,
  upsertRun,
  type CaseRecord,
  type CaseRun,
} from "../types";

const NOW = "2026-08-23T12:00:00.000Z";
const LATER = "2026-08-23T13:00:00.000Z";

function base(): CaseRecord {
  return createCaseRecord({
    ownerUserId: "test-owner",
    name: "Con corrida",
    studyKind: "explore-hypothesis",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    id: "caso-1",
    now: NOW,
  });
}

describe("estados de ejecución", () => {
  it("distingue terminal de no terminal", () => {
    expect(isTerminalRunState("completed")).toBe(true);
    expect(isTerminalRunState("failed")).toBe(true);
    expect(isTerminalRunState("cancelled")).toBe(true);
    expect(isTerminalRunState("running")).toBe(false);
    expect(isTerminalRunState("submitted")).toBe(false);
    // INTERRUMPIDO no es terminal: no se sabe cómo acabó, así que hay que
    // seguir preguntando.
    expect(isTerminalRunState("interrupted")).toBe(false);
  });

  // Esta comprobación vivía DENTRO del cuerpo de `base()`, después de su
  // `return`: estaba escrita y no la ejecutaba nadie.
  it("una interrupción conserva el seguimiento pero no bloquea la navegación", () => {
    expect(isRunBlocking("submitted")).toBe(true);
    expect(isRunBlocking("running")).toBe(true);
    expect(isRunBlocking("interrupted")).toBe(false);
    expect(isRunBlocking("completed")).toBe(false);
  });
});

describe("el libro de corridas", () => {
  const first: CaseRun = {
    taskId: "task-1",
    moleculeId: "4b67aeb2-e1a8-4ea2-9c3a-001a8ecbf106",
    executionState: "completed",
    startedAt: NOW,
    ligandSmiles: "CCO",
    affinityKcal: -7.4,
    protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 },
  };
  const second: CaseRun = {
    taskId: "task-2",
    executionState: "running",
    startedAt: LATER,
    ligandSmiles: "CCN",
  };

  it("una corrida nueva NO borra la anterior", () => {
    const withTwo = caseWithRun(caseWithRun(base(), first), second);
    expect(withTwo.runs.map((run) => run.taskId)).toEqual(["task-1", "task-2"]);
    // Ésta es la regresión que motivó la v7: antes, la segunda corrida dejaba
    // la primera sin ningún puntero desde el caso.
    expect(withTwo.runs[0]).toEqual(first);
  });

  it("`activeRun` es SIEMPRE la última fila", () => {
    const withTwo = caseWithRun(caseWithRun(base(), first), second);
    expect(withTwo.activeRun?.taskId).toBe("task-2");
    expect(latestRun(withTwo.runs)?.taskId).toBe("task-2");
  });

  it("actualizar una corrida viva no la duplica ni la mueve de sitio", () => {
    const book = upsertRun(upsertRun([], first), second);
    const advanced = upsertRun(book, { ...second, lastKnownProgress: 60 });
    expect(advanced).toHaveLength(2);
    expect(advanced[1].lastKnownProgress).toBe(60);
    expect(advanced[0].taskId).toBe("task-1");
  });

  it("una actualización de progreso no borra lo que ya sabía la fila", () => {
    // El progreso llega sin `ligandSmiles` ni `protocol`: si la fila se
    // reemplazara en vez de fusionarse, el libro perdería con qué se corrió.
    const advanced = upsertRun([first], {
      taskId: "task-1",
      executionState: "completed",
      startedAt: NOW,
      lastKnownProgress: 100,
    });
    expect(advanced[0].ligandSmiles).toBe("CCO");
    expect(advanced[0].protocol?.exhaustiveness).toBe(8);
  });

  it("sobrevive al round-trip del manifiesto", () => {
    const record = caseWithRun(caseWithRun(base(), first), second);
    const parsed = parseCaseManifestText(serializeCaseManifest(record));
    expect(parsed.runs).toEqual(record.runs);
    expect(parsed.activeRun).toEqual(second);
  });

  it("no escribe `activeRun` en disco: se deriva al leer", () => {
    const record = caseWithRun(base(), first);
    const written = JSON.parse(serializeCaseManifest(record)) as Record<string, unknown>;
    expect(written).not.toHaveProperty("activeRun");
    expect(written).toHaveProperty("runs");
    expect(parseCaseManifest(written).activeRun).toEqual(first);
  });

  it("un caso sin corridas no escribe la clave: `null` sería ambiguo", () => {
    const text = serializeCaseManifest(base());
    expect(JSON.parse(text)).not.toHaveProperty("runs");
    const parsed = parseCaseManifestText(text);
    expect(parsed.runs).toEqual([]);
    expect(parsed.activeRun).toBeUndefined();
  });

  it("conserva el error de la última interrupción", () => {
    const record = caseWithRun(base(), {
      taskId: "task-int",
      executionState: "interrupted",
      startedAt: NOW,
      lastError: "Se perdió la conexión.",
    });
    const parsed = parseCaseManifestText(serializeCaseManifest(record));
    expect(parsed.activeRun?.executionState).toBe("interrupted");
    expect(parsed.activeRun?.lastError).toBe("Se perdió la conexión.");
  });
});

describe("el sistema no queda sellado por una corrida que no produjo nada", () => {
  const system = {
    lockedAt: NOW,
    sourceRunTaskId: "task-1",
    inputFingerprint: "fp-1",
    receptor: { pdbId: "1ABC", origin: "curado" as const },
    grid: { center: [1, 2, 3] as [number, number, number], size: [20, 20, 20] as [number, number, number] },
    customHotspots: [],
    dockingEngine: "vina",
    exhaustiveness: 8,
    numPoses: 9,
    conformers: 1,
  };

  it("una corrida FALLIDA deja el sistema provisional", () => {
    const record = caseWithRun({ ...base(), structuralSystem: system }, {
      taskId: "task-1",
      executionState: "failed",
      startedAt: NOW,
      lastError: "Vina reventó en la preparación.",
    });
    expect(structuralSystemIsSealed(record)).toBe(false);
    expect(hasCompletedRun(record.runs)).toBe(false);
  });

  it("una corrida TERMINADA lo sella", () => {
    const record = caseWithRun({ ...base(), structuralSystem: system }, {
      taskId: "task-1",
      executionState: "completed",
      startedAt: NOW,
    });
    expect(structuralSystemIsSealed(record)).toBe(true);
  });

  it("sin sistema escrito no hay nada que sellar", () => {
    const record = caseWithRun(base(), {
      taskId: "task-1",
      executionState: "completed",
      startedAt: NOW,
    });
    expect(structuralSystemIsSealed(record)).toBe(false);
  });
});

describe("migración v6 → v7", () => {
  const v6 = () => {
    const manifest = JSON.parse(serializeCaseManifest(base())) as Record<string, unknown>;
    manifest.schemaVersion = 6;
    manifest.activeRun = {
      taskId: "task-legacy",
      moleculeId: "4b67aeb2-e1a8-4ea2-9c3a-001a8ecbf106",
      executionState: "completed",
      startedAt: NOW,
    };
    return manifest;
  };

  it("la corrida que el caso tenía se convierte en la primera fila del libro", () => {
    const parsed = parseCaseManifest(v6());
    expect(parsed.schemaVersion).toBe(7);
    expect(parsed.runs).toHaveLength(1);
    expect(parsed.runs[0].taskId).toBe("task-legacy");
    expect(parsed.activeRun?.taskId).toBe("task-legacy");
  });

  it("NO se inventan las corridas anteriores que ese manifiesto nunca guardó", () => {
    const parsed = parseCaseManifest(v6());
    // Una fila migrada no declara ligando ni protocolo. Rellenarlos con los
    // valores de ahora sería atribuirle una hipótesis que no es la suya.
    expect(parsed.runs[0].ligandSmiles).toBeUndefined();
    expect(parsed.runs[0].protocol).toBeUndefined();
  });

  it("un v6 sin corrida migra a un libro vacío", () => {
    const manifest = JSON.parse(serializeCaseManifest(base())) as Record<string, unknown>;
    manifest.schemaVersion = 6;
    expect(parseCaseManifest(manifest).runs).toEqual([]);
  });
});

describe("una corrida corrupta NO se descarta en silencio", () => {
  const withRuns = (runs: unknown) => {
    const manifest = JSON.parse(serializeCaseManifest(base())) as Record<string, unknown>;
    manifest.runs = runs;
    return manifest;
  };

  it("rechaza si falta el `taskId`", () => {
    expect(() =>
      parseCaseManifest(withRuns([{ executionState: "running", startedAt: NOW }])),
    ).toThrowError(CaseError);
  });

  it("rechaza un `executionState` desconocido", () => {
    expect(() =>
      parseCaseManifest(withRuns([{ taskId: "t", executionState: "corriendo", startedAt: NOW }])),
    ).toThrowError(CaseError);
  });

  it("rechaza una fecha de inicio que no es una fecha", () => {
    expect(() =>
      parseCaseManifest(withRuns([{ taskId: "t", executionState: "running", startedAt: "ayer" }])),
    ).toThrowError(CaseError);
  });

  it("rechaza un progreso que no es un número", () => {
    expect(() =>
      parseCaseManifest(
        withRuns([
          { taskId: "t", executionState: "running", startedAt: NOW, lastKnownProgress: "medio" },
        ]),
      ),
    ).toThrowError(CaseError);
  });

  it("rechaza una afinidad que no es un número finito", () => {
    expect(() =>
      parseCaseManifest(
        withRuns([{ taskId: "t", executionState: "completed", startedAt: NOW, affinityKcal: "buena" }]),
      ),
    ).toThrowError(CaseError);
  });

  it("rechaza un protocolo sin motor", () => {
    expect(() =>
      parseCaseManifest(
        withRuns([
          {
            taskId: "t",
            executionState: "completed",
            startedAt: NOW,
            protocol: { exhaustiveness: 8, numPoses: 9, conformers: 1 },
          },
        ]),
      ),
    ).toThrowError(CaseError);
  });

  it("rechaza una fila que no es un objeto", () => {
    for (const bad of ["task-1", 42, [1]]) {
      expect(() => parseCaseManifest(withRuns([bad]))).toThrowError(CaseError);
    }
  });

  it("rechaza `runs` que no es una lista", () => {
    expect(() => parseCaseManifest(withRuns({ taskId: "t" }))).toThrowError(CaseError);
  });

  it("rechaza dos filas con el mismo `taskId`", () => {
    // Un libro con la misma corrida dos veces no permitiría decir cuál de las
    // dos es la buena.
    const run = { taskId: "t", executionState: "completed", startedAt: NOW };
    expect(() => parseCaseManifest(withRuns([run, run]))).toThrowError(CaseError);
  });

  it("acepta la ausencia: no haber corrido nada es un estado legítimo", () => {
    const manifest = JSON.parse(serializeCaseManifest(base())) as Record<string, unknown>;
    delete manifest.runs;
    expect(parseCaseManifest(manifest).runs).toEqual([]);
    manifest.runs = null;
    expect(parseCaseManifest(manifest).runs).toEqual([]);
    manifest.runs = [];
    expect(parseCaseManifest(manifest).activeRun).toBeUndefined();
  });
});
