// =====================================================================
// Tests de `activeRun` — la corrida sobrevive al cierre de la ventana
// =====================================================================
//
// POR QUÉ ESTÁ EN EL MANIFIESTO Y NO EN MEMORIA. Su propósito es sobrevivir
// exactamente a lo que mata la memoria: cerrar la ventana, recargar, o cambiar
// de caso y volver. Sin esto, una corrida lanzada seguía viva en el backend y
// el usuario no tenía forma de volver a encontrarla: trabajo huérfano.
//
// Y ES ESTADO COMPUTACIONAL. `completed` aquí no completa el caso.

import { describe, expect, it } from "vitest";

import {
  createCaseRecord,
  parseCaseManifest,
  parseCaseManifestText,
  serializeCaseManifest,
} from "../schema";
import { CaseError, isRunBlocking, isTerminalRunState, type CaseRecord } from "../types";

const NOW = "2026-08-23T12:00:00.000Z";

function base(): CaseRecord {
  return createCaseRecord({
    ownerUserId: "test-owner",
    name: "Con corrida",
    studyKind: "explore-hypothesis",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    id: "caso-1",
    now: NOW,
  });

  it("una interrupción conserva el seguimiento pero no bloquea la navegación", () => {
    expect(isRunBlocking("submitted")).toBe(true);
    expect(isRunBlocking("running")).toBe(true);
    expect(isRunBlocking("interrupted")).toBe(false);
    expect(isRunBlocking("completed")).toBe(false);
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
});

describe("persistencia de la corrida", () => {
  it("sobrevive al round-trip del manifiesto", () => {
    const record: CaseRecord = {
      ...base(),
      status: "running",
      activeRun: {
        taskId: "task-abc",
        moleculeId: "4b67aeb2-e1a8-4ea2-9c3a-001a8ecbf106",
        executionState: "running",
        startedAt: NOW,
        lastKnownProgress: 42,
      },
    };
    const parsed = parseCaseManifestText(serializeCaseManifest(record));
    expect(parsed.activeRun).toEqual(record.activeRun);
    expect(parsed.status).toBe("running");
  });

  it("un caso sin corrida no escribe la clave: `null` sería ambiguo", () => {
    const text = serializeCaseManifest(base());
    expect(JSON.parse(text)).not.toHaveProperty("activeRun");
    expect(parseCaseManifestText(text).activeRun).toBeUndefined();
  });

  it("conserva el error de la última interrupción", () => {
    const record: CaseRecord = {
      ...base(),
      activeRun: {
        taskId: "task-int",
        executionState: "interrupted",
        startedAt: NOW,
        lastError: "Se perdió la conexión.",
      },
    };
    const parsed = parseCaseManifestText(serializeCaseManifest(record));
    expect(parsed.activeRun?.executionState).toBe("interrupted");
    expect(parsed.activeRun?.lastError).toBe("Se perdió la conexión.");
  });
});

describe("una corrida corrupta NO se descarta en silencio", () => {
  const withRun = (run: unknown) => {
    const manifest = JSON.parse(serializeCaseManifest(base())) as Record<string, unknown>;
    manifest.activeRun = run;
    return manifest;
  };

  it("rechaza si falta el `taskId`", () => {
    expect(() =>
      parseCaseManifest(withRun({ executionState: "running", startedAt: NOW })),
    ).toThrowError(CaseError);
  });

  it("rechaza un `executionState` desconocido", () => {
    expect(() =>
      parseCaseManifest(withRun({ taskId: "t", executionState: "corriendo", startedAt: NOW })),
    ).toThrowError(CaseError);
  });

  it("rechaza una fecha de inicio que no es una fecha", () => {
    expect(() =>
      parseCaseManifest(withRun({ taskId: "t", executionState: "running", startedAt: "ayer" })),
    ).toThrowError(CaseError);
  });

  it("rechaza un progreso que no es un número", () => {
    expect(() =>
      parseCaseManifest(
        withRun({ taskId: "t", executionState: "running", startedAt: NOW, lastKnownProgress: "medio" }),
      ),
    ).toThrowError(CaseError);
  });

  it("rechaza `activeRun` que no es un objeto", () => {
    for (const bad of ["task-1", 42, [1]]) {
      expect(() => parseCaseManifest(withRun(bad))).toThrowError(CaseError);
    }
  });

  it("acepta la ausencia: no hay corrida es un estado legítimo", () => {
    const manifest = JSON.parse(serializeCaseManifest(base())) as Record<string, unknown>;
    delete manifest.activeRun;
    expect(parseCaseManifest(manifest).activeRun).toBeUndefined();
    manifest.activeRun = null;
    expect(parseCaseManifest(manifest).activeRun).toBeUndefined();
  });
});
