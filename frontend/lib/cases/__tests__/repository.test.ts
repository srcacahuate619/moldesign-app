import { describe, expect, it } from "vitest";

import { sortCaseEntries } from "../repository";
import type { CaseIndexEntry } from "../types";

function entry(
  id: string,
  createdAt: string,
  overrides: Partial<CaseIndexEntry> = {},
): CaseIndexEntry {
  return {
    id,
    name: id,
    status: "review",
    createdAt,
    updatedAt: createdAt,
    lastOpenedAt: createdAt,
    archived: false,
    storageMode: "browser",
    ...overrides,
  };
}

describe("sortCaseEntries", () => {
  it("mantiene el orden de creacion aunque se abra o evalúe un caso antiguo", () => {
    const antiguo = entry("antiguo", "2026-08-01T10:00:00.000Z", {
      lastOpenedAt: "2026-08-26T12:00:00.000Z",
      updatedAt: "2026-08-26T12:00:00.000Z",
      activeRun: {
        taskId: "run-nueva",
        executionState: "completed",
        startedAt: "2026-08-26T11:59:00.000Z",
      },
    });
    const nuevo = entry("nuevo", "2026-08-20T10:00:00.000Z", {
      lastOpenedAt: "2026-08-20T10:00:00.000Z",
    });

    expect(sortCaseEntries([antiguo, nuevo]).map((item) => item.id)).toEqual([
      "nuevo",
      "antiguo",
    ]);
  });

  it("separa archivados sin alterar el orden de nacimiento de cada grupo", () => {
    const entries = [
      entry("activo-antiguo", "2026-08-01T10:00:00.000Z"),
      entry("archivado-nuevo", "2026-08-25T10:00:00.000Z", { archived: true }),
      entry("activo-nuevo", "2026-08-20T10:00:00.000Z"),
    ];

    expect(sortCaseEntries(entries).map((item) => item.id)).toEqual([
      "activo-nuevo",
      "activo-antiguo",
      "archivado-nuevo",
    ]);
  });
});
