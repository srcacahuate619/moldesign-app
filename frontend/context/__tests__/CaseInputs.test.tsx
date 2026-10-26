// =====================================================================
// Inputs persistentes del caso — supervivencia, aislamiento e invalidación
// =====================================================================
//
// LO QUE ESTOS TESTS IMPIDEN, en orden de gravedad:
//
// 1. Que una corrida guardada quede sin la hipótesis que la explica. Antes de
//    v3, receptor y SMILES vivían en `useState`: cerrar el caso los perdía y
//    el manifiesto conservaba un `taskId` que ya nadie podía interpretar.
// 2. Que el preflight sobreviva a un cambio de inputs. Un informe que describe
//    otra hipótesis es peor que no tener informe: parece una comprobación.
// 3. Que los inputs de un caso aparezcan en otro.
// 4. Que una corrida anterior se presente como evidencia de la hipótesis nueva.

import { describe, expect, it, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { CaseProvider, useCases } from "../CaseContext";
import { createBrowserCaseRepository } from "../../lib/cases/browserCaseRepository";
import type { CaseRepository } from "../../lib/cases/repository";
import { runMatchesInputs, type PreflightSummary } from "../../lib/cases/types";

function wrapper(repository: CaseRepository) {
  return function Wrapper({ children }: { children: ReactNode }) {
    // Debounce a 0: el guardado se vuelve observable sin esperas artificiales.
    return (
      <CaseProvider repository={repository} autosaveDelayMs={0}>
        {children}
      </CaseProvider>
    );
  };
}

const PREFLIGHT: PreflightSummary = {
  fingerprint: "sha256:huella-uno",
  inputDocument: '{"chain":"A"}',
  generatedAt: "2026-08-24T10:00:00.000Z",
  schemaVersion: 1,
  executionRoute: "docking_vina",
  blockers: [],
  warnings: ["METALES_ELIMINADOS"],
  notEvaluated: ["ASSEMBLY_BIOLOGICA"],
  receptorLabel: "7E2Y · cadena A",
  ligandLabel: "CC(=O)Oc1ccccc1C(=O)O",
  gridLabel: "(1.00, 2.00, 3.00)",
};

async function newCase(result: { current: ReturnType<typeof useCases> }, name: string) {
  await act(async () => {
    await result.current.createCase(name, "explore-hypothesis");
  });
  return result.current.activeCase!.id;
}

describe("inputs persistentes del caso", () => {
  beforeEach(() => window.localStorage.clear());

  it("receptor y ligando sobreviven a cerrar y reabrir el caso", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    const id = await newCase(result, "Hipótesis");
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "7E2Y", chain: "A", origin: "curado", name: "5-HT2A" },
        ligand: { inputSmiles: "CC(=O)Oc1ccccc1C(=O)O" },
      });
    });
    await waitFor(() => expect(result.current.saveState).toBe("saved"));

    // Se cierra y se vuelve a abrir, como haría un reinicio.
    await act(async () => {
      await result.current.closeCase();
    });
    await act(async () => {
      await result.current.selectCase(id);
    });

    expect(result.current.activeCase?.inputs?.receptor?.pdbId).toBe("7E2Y");
    expect(result.current.activeCase?.inputs?.receptor?.chain).toBe("A");
    expect(result.current.activeCase?.inputs?.ligand?.inputSmiles).toBe(
      "CC(=O)Oc1ccccc1C(=O)O",
    );
  });

  it("el preflight sobrevive junto a sus inputs", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    const id = await newCase(result, "Con preflight");
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "7E2Y", origin: "curado" },
        ligand: { inputSmiles: "CCO" },
      });
    });
    act(() => result.current.setPreflight(PREFLIGHT));
    await waitFor(() => expect(result.current.saveState).toBe("saved"));

    await act(async () => {
      await result.current.closeCase();
    });
    await act(async () => {
      await result.current.selectCase(id);
    });

    expect(result.current.activeCase?.preflight?.fingerprint).toBe("sha256:huella-uno");
    expect(result.current.activeCase?.preflight?.warnings).toEqual(["METALES_ELIMINADOS"]);
  });

  it("no se filtran entre casos", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await newCase(result, "Primero");
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "7E2Y", origin: "curado" },
        ligand: { inputSmiles: "CCO" },
      });
    });
    await waitFor(() => expect(result.current.saveState).toBe("saved"));

    await newCase(result, "Segundo");

    expect(result.current.activeCase?.name).toBe("Segundo");
    expect(result.current.activeCase?.inputs).toBeUndefined();
    expect(result.current.activeCase?.preflight).toBeUndefined();
  });

  describe("invalidación del preflight", () => {
    async function caseWithPreflight() {
      const repository = createBrowserCaseRepository("test-owner");
      const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
      await waitFor(() => expect(result.current.loading).toBe(false));
      await newCase(result, "Invalidable");
      act(() => {
        result.current.setInputs({
          receptor: { pdbId: "7E2Y", chain: "A", origin: "curado" },
          ligand: { inputSmiles: "CCO" },
          grid: { center: [1, 2, 3], size: [20, 20, 20] },
        });
      });
      act(() => result.current.setPreflight(PREFLIGHT));
      await waitFor(() => expect(result.current.activeCase?.preflight).toBeDefined());
      return result;
    }

    it("cambiar el receptor retira el preflight anterior", async () => {
      const result = await caseWithPreflight();
      act(() => {
        result.current.setInputs({ receptor: { pdbId: "1ABC", origin: "curado" } });
      });
      expect(result.current.activeCase?.preflight).toBeUndefined();
    });

    it("cambiar el ligando retira el preflight anterior", async () => {
      const result = await caseWithPreflight();
      act(() => {
        result.current.setInputs({ ligand: { inputSmiles: "CCCC" } });
      });
      expect(result.current.activeCase?.preflight).toBeUndefined();
    });

    it("cambiar la caja retira el preflight anterior", async () => {
      const result = await caseWithPreflight();
      act(() => {
        result.current.setInputs({ grid: { center: [9, 9, 9], size: [20, 20, 20] } });
      });
      expect(result.current.activeCase?.preflight).toBeUndefined();
    });

    it("guardar el canónico del mismo ligando NO lo retira", async () => {
      // El preflight devuelve el canónico y el runner lo persiste. Si eso
      // invalidara, el informe se borraría justo al llegar y sería imposible
      // ejecutar nada.
      const result = await caseWithPreflight();
      act(() => {
        result.current.setInputs({
          ligand: { inputSmiles: "CCO", canonicalSmiles: "CCO" },
        });
      });
      expect(result.current.activeCase?.preflight?.fingerprint).toBe("sha256:huella-uno");
    });

    it("invalidar el preflight NO borra la corrida guardada", async () => {
      const result = await caseWithPreflight();
      act(() =>
        result.current.setActiveRun({
          taskId: "task-1",
          executionState: "completed",
          startedAt: "2026-08-24T09:00:00.000Z",
          inputFingerprint: "sha256:huella-uno",
        }),
      );
      await waitFor(() => expect(result.current.activeCase?.activeRun).toBeDefined());

      act(() => {
        result.current.setInputs({ receptor: { pdbId: "1ABC", origin: "curado" } });
      });

      // La corrida sigue ahí: es historia del caso. Lo que cambia es que ya no
      // corresponde a los inputs actuales.
      expect(result.current.activeCase?.activeRun?.taskId).toBe("task-1");
      expect(result.current.activeCase?.preflight).toBeUndefined();
    });
  });

  describe("atribución de una corrida a su hipótesis", () => {
    it("una corrida con otra huella se etiqueta como anterior", () => {
      const run = {
        taskId: "t",
        executionState: "completed" as const,
        startedAt: "2026-08-24T09:00:00.000Z",
        inputFingerprint: "sha256:vieja",
      };
      expect(runMatchesInputs(run, "sha256:nueva")).toBe("corrida_anterior");
      expect(runMatchesInputs(run, "sha256:vieja")).toBe("corresponde");
    });

    it("una corrida sin huella NO se da por correspondiente", () => {
      // Las corridas anteriores a v3 no guardaron fingerprint. Tratar ese
      // hueco como «corresponde» sería exactamente la atribución falsa que
      // este campo existe para impedir.
      const legacy = {
        taskId: "t",
        executionState: "completed" as const,
        startedAt: "2026-08-24T09:00:00.000Z",
      };
      expect(runMatchesInputs(legacy, "sha256:nueva")).toBe("desconocida");
    });
  });

  describe("decisiones humanas", () => {
    it("quedan atadas al fingerprint y no se duplican", async () => {
      const repository = createBrowserCaseRepository("test-owner");
      const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
      await waitFor(() => expect(result.current.loading).toBe(false));
      await newCase(result, "Con decisiones");

      act(() => result.current.recordDecision("METALES_ELIMINADOS", "sha256:uno"));
      act(() => result.current.recordDecision("METALES_ELIMINADOS", "sha256:uno"));
      act(() => result.current.recordDecision("METALES_ELIMINADOS", "sha256:dos"));

      const decisions = result.current.activeCase?.decisions ?? [];
      expect(decisions).toHaveLength(2);
      expect(decisions.map((d) => d.fingerprint).sort()).toEqual(["sha256:dos", "sha256:uno"]);
      expect(decisions.every((d) => d.decision === "reconocida")).toBe(true);
    });

    it("sobreviven a reabrir el caso", async () => {
      const repository = createBrowserCaseRepository("test-owner");
      const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
      await waitFor(() => expect(result.current.loading).toBe(false));
      const id = await newCase(result, "Persistentes");

      act(() => result.current.recordDecision("METALES_ELIMINADOS", "sha256:uno", "revisado"));
      await waitFor(() => expect(result.current.saveState).toBe("saved"));

      await act(async () => {
        await result.current.closeCase();
      });
      await act(async () => {
        await result.current.selectCase(id);
      });

      expect(result.current.activeCase?.decisions?.[0]?.note).toBe("revisado");
    });
  });

  // ── AMP-01: la disposición no se pierde al editar los inputs ────────
  //
  // La auditoría ampliada lo midió en vivo: guardar «Aceptar con límites»
  // con su justificación, exportar, editar el SMILES y restaurar el
  // original — y la disposición dejaba de existir en el caso persistido.
  // «La justificación queda guardada junto a la huella de inputs» no se
  // cumplía como historial durable: el PDF ya exportado la conservaba, el
  // caso no permitía reconstruirla.
  //
  // La regla: al invalidar, la disposición VIGENTE se retira (describiría
  // otra hipótesis y el caso pasa a review), pero la decisión con su
  // justificación y su huella queda en el HISTORIAL del caso — en disco,
  // no sólo en memoria.

  describe("AMP-01: la disposición no se pierde al editar los inputs", () => {
    beforeEach(() => window.localStorage.clear());

    async function casoConDisposicion(repository: CaseRepository) {
      const { result } = renderHook(() => useCases(), {
        wrapper: wrapper(repository),
      });
      await waitFor(() => expect(result.current.loading).toBe(false));
      const id = await newCase(result, "Con disposición");
      act(() => {
        result.current.setInputs({
          receptor: { pdbId: "7E2Y", chain: "A", origin: "curado" },
          ligand: { inputSmiles: "CCO" },
        });
      });
      act(() => result.current.setPreflight(PREFLIGHT));
      act(() =>
        result.current.setActiveRun({
          taskId: "task-1",
          executionState: "completed",
          startedAt: "2026-08-24T09:00:00.000Z",
          inputFingerprint: "sha256:huella-uno",
        }),
      );
      await waitFor(() =>
        expect(result.current.activeCase?.activeRun).toBeDefined(),
      );
      await act(async () => {
        expect(
          await result.current.setDisposition(
            "limit",
            "Acepto con límites: el receptor no está calibrado.",
          ),
        ).toBe(true);
      });
      await waitFor(() => expect(result.current.saveState).toBe("saved"));
      return { result, id };
    }

    it("editar el ligando retira la vigente y conserva decisión y justificación en el historial", async () => {
      const repository = createBrowserCaseRepository("test-owner");
      const { result, id } = await casoConDisposicion(repository);
      expect(result.current.activeCase?.disposition?.rationale).toContain(
        "no está calibrado",
      );

      // La reproducción de la auditoría: editar el SMILES (aunque se
      // restaure después) borraba la decisión del caso por completo.
      act(() => {
        result.current.setInputs({ ligand: { inputSmiles: "CCN" } });
      });
      await waitFor(() => expect(result.current.saveState).toBe("saved"));

      // La VIGENTE se retira: describiría otra hipótesis, y el caso a review.
      expect(result.current.activeCase?.disposition).toBeUndefined();
      expect(result.current.activeCase?.status).toBe("review");
      // La decisión con su justificación NO desaparece: queda en el historial.
      const historial = result.current.activeCase?.dispositions ?? [];
      expect(historial).toHaveLength(1);
      expect(historial[0].kind).toBe("limit");
      expect(historial[0].fingerprint).toBe("sha256:huella-uno");
      expect(historial[0].rationale).toContain("no está calibrado");
      // Y en disco, no sólo en memoria: el caso permite reconstruirla.
      const stored = await repository.readCase(id);
      expect(stored.dispositions?.[0]?.rationale).toContain("no está calibrado");
    });

    it("re-decidir añade al historial, no lo sobrescribe", async () => {
      const repository = createBrowserCaseRepository("test-owner");
      const { result } = await casoConDisposicion(repository);
      act(() => {
        result.current.setInputs({ ligand: { inputSmiles: "CCN" } });
      });
      await waitFor(() =>
        expect(result.current.activeCase?.disposition).toBeUndefined(),
      );

      // Con la evidencia desalineada de los inputs, sólo la abstención es
      // honesta — la propia guardia del contexto lo exige.
      await act(async () => {
        expect(
          await result.current.setDisposition(
            "abstain",
            "La evidencia actual no sostiene una conclusión.",
          ),
        ).toBe(true);
      });
      await waitFor(() => expect(result.current.saveState).toBe("saved"));

      const historial = result.current.activeCase?.dispositions ?? [];
      expect(historial).toHaveLength(2);
      expect(historial[0].rationale).toContain("no está calibrado");
      expect(historial[1].rationale).toContain("no sostiene una conclusión");
      // La vigente es la nueva.
      expect(result.current.activeCase?.disposition?.kind).toBe("abstain");
    });

    it("el historial sobrevive a cerrar y reabrir el caso", async () => {
      const repository = createBrowserCaseRepository("test-owner");
      const { result, id } = await casoConDisposicion(repository);
      act(() => {
        result.current.setInputs({ ligand: { inputSmiles: "CCN" } });
      });
      await waitFor(() => expect(result.current.saveState).toBe("saved"));

      await act(async () => {
        await result.current.closeCase();
      });
      await act(async () => {
        await result.current.selectCase(id);
      });

      expect(result.current.activeCase?.dispositions).toHaveLength(1);
      expect(result.current.activeCase?.dispositions?.[0]?.fingerprint).toBe(
        "sha256:huella-uno",
      );
      // El caso reabrido recuerda qué se decidió y sobre qué huella, aunque
      // la decisión ya no esté vigente.
      expect(result.current.activeCase?.disposition).toBeUndefined();
    });
  });
});
