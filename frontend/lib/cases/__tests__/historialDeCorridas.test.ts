// CAS-01 / CAS-03. Con 40 corridas de la misma molécula (20 únicas y 20
// ensemble), «Otro protocolo» decía que algo era distinto sin decir qué, y no
// había forma de aislar las únicas de los ensembles. Funciones puras del libro.
import { describe, expect, it } from "vitest";

import {
  NO_RUN_FILTER,
  filterRuns,
  runMode,
  runProtocolDifferences,
  type CaseRun,
  type CaseStructuralSystem,
} from "../types";

const SISTEMA: CaseStructuralSystem = {
  lockedAt: "2026-08-23T12:00:00.000Z",
  sourceRunTaskId: "t-0",
  inputFingerprint: "fp",
  receptor: { pdbId: "3F75", chain: "A", origin: "curado" },
  grid: { center: [1, 2, 3], size: [22, 22, 22] },
  customHotspots: [],
  dockingEngine: "vina",
  exhaustiveness: 8,
  numPoses: 9,
  conformers: 1,
};

function corrida(id: string, smiles: string, k: number | null, estado: CaseRun["executionState"] = "completed"): CaseRun {
  return {
    taskId: id,
    executionState: estado,
    startedAt: "2026-09-30T10:00:00.000Z",
    ligandSmiles: smiles,
    ...(k === null
      ? {}
      : { protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: k } }),
  };
}

describe("runMode: único o ensemble, con su K", () => {
  it("K=1 es único; K>1 es ensemble, y K viaja", () => {
    expect(runMode({ dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 })).toEqual({ mode: "single", k: 1 });
    expect(runMode({ dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 30 })).toEqual({ mode: "ensemble", k: 30 });
  });
});

describe("runProtocolDifferences: qué cambió frente al sistema inicial", () => {
  it("K distinto se nombra con los dos valores", () => {
    expect(runProtocolDifferences(corrida("a", "CCO", 30), SISTEMA)).toEqual([
      { field: "conformers", run: 30, system: 1 },
    ]);
  });

  it("varios campos distintos se listan todos, en un orden estable", () => {
    const run = {
      ...corrida("a", "CCO", 12),
      protocol: { dockingEngine: "qvina2", exhaustiveness: 32, numPoses: 20, conformers: 12 },
    } as CaseRun;
    expect(runProtocolDifferences(run, SISTEMA).map((d) => d.field)).toEqual([
      "dockingEngine", "exhaustiveness", "numPoses", "conformers",
    ]);
  });

  it("igual al sistema: sin diferencias", () => {
    expect(runProtocolDifferences(corrida("a", "CCO", 1), SISTEMA)).toEqual([]);
  });

  it("sin protocolo registrado o sin sistema NO se inventa ni diferencia ni igualdad", () => {
    expect(runProtocolDifferences(corrida("a", "CCO", null), SISTEMA)).toEqual([]);
    expect(runProtocolDifferences(corrida("a", "CCO", 30), undefined)).toEqual([]);
  });
});

describe("filterRuns: aislar una serie repetida", () => {
  const LIBRO: CaseRun[] = [
    ...Array.from({ length: 20 }, (_, i) => corrida(`unica-${i}`, `C${"C".repeat(i)}O`, 1)),
    ...Array.from({ length: 20 }, (_, i) => corrida(`ens-${i}`, `C${"C".repeat(i)}O`, 30)),
    corrida("fallo-0", "CCN", 1, "failed"),
    corrida("legado-0", "CCCl", null),
  ];

  it("sin filtro devuelve todo, en el mismo orden", () => {
    expect(filterRuns(LIBRO, NO_RUN_FILTER)).toEqual(LIBRO);
  });

  it("modo único: sólo K=1 (incluida la fallida, que también fue K=1)", () => {
    const unicas = filterRuns(LIBRO, { ...NO_RUN_FILTER, mode: "single" });
    expect(unicas).toHaveLength(21);
    expect(unicas.every((r) => r.protocol?.conformers === 1)).toBe(true);
  });

  it("modo ensemble: sólo K>1", () => {
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, mode: "ensemble" })).toHaveLength(20);
  });

  it("una corrida migrada SIN protocolo no se afirma única ni ensemble: sólo aparece en «todas»", () => {
    const legado = LIBRO.find((r) => r.taskId === "legado-0")!;
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, mode: "single" })).not.toContain(legado);
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, mode: "ensemble" })).not.toContain(legado);
    expect(filterRuns(LIBRO, NO_RUN_FILTER)).toContain(legado);
  });

  it("por estado", () => {
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, state: "failed" }).map((r) => r.taskId)).toEqual(["fallo-0"]);
  });

  it("por texto: SMILES o identificador de la corrida, sin distinguir mayúsculas", () => {
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, query: "ccn" }).map((r) => r.taskId)).toEqual(["fallo-0"]);
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, query: "ENS-1" }).length).toBe(11); // ens-1, ens-10..ens-19
    expect(filterRuns(LIBRO, { ...NO_RUN_FILTER, query: "   " })).toHaveLength(LIBRO.length);
  });

  it("los filtros se combinan (y)", () => {
    const resultado = filterRuns(LIBRO, { mode: "ensemble", state: "completed", query: "ens-0" });
    expect(resultado.map((r) => r.taskId)).toEqual(["ens-0"]);
  });

  it("filtrar no cambia el libro", () => {
    const copia = [...LIBRO];
    filterRuns(LIBRO, { ...NO_RUN_FILTER, mode: "single" });
    expect(LIBRO).toEqual(copia);
  });
});
