// =====================================================================
// Tests del contexto de casos — el drenaje que BLOQUEA y la corrida viva
// =====================================================================
//
// El escenario que da nombre al sprint: editar A, que la escritura falle, e
// intentar crear B. Antes B se creaba igual y el borrador de A se quedaba en
// una cola que ya nadie miraba: el texto seguía en memoria pero fuera de
// pantalla, o sea perdido de hecho.
//
// Ahora `drain` devuelve fallo y TODA transición aborta.

import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { CaseProvider, useCases } from "../CaseContext";
import { createBrowserCaseRepository } from "../../lib/cases/browserCaseRepository";
import type { CaseRepository } from "../../lib/cases/repository";
import { structuralSystemIsSealed, type CaseRecord } from "../../lib/cases/types";

/** Repositorio real de navegador con la escritura bajo control del test. */
function controllableRepository(): {
  repository: CaseRepository;
  failNextWrites: (fail: boolean) => void;
  writes: number;
} {
  const inner = createBrowserCaseRepository("test-owner");
  const state = { fail: false, writes: 0 };
  const repository: CaseRepository = {
    ...inner,
    async updateCase(record: CaseRecord) {
      state.writes += 1;
      if (state.fail) throw new Error("disco lleno");
      return inner.updateCase(record);
    },
  };
  return {
    repository,
    failNextWrites: (fail: boolean) => {
      state.fail = fail;
    },
    get writes() {
      return state.writes;
    },
  };
}

function wrapper(repository: CaseRepository) {
  return function Wrapper({ children }: { children: ReactNode }) {
    // Debounce 0: el guardado es observable sin esperar al reloj real.
    return (
      <CaseProvider repository={repository} autosaveDelayMs={0}>
        {children}
      </CaseProvider>
    );
  };
}

describe("el drenaje bloquea la transición", () => {
  it("si el guardado falla, NO se crea otro caso y el original sigue activo", async () => {
    window.localStorage.clear();
    const { repository, failNextWrites } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Caso A", "explore-hypothesis");
    });
    const idA = result.current.activeCase?.id;
    expect(idA).toBeTruthy();

    // El usuario escribe y el disco falla.
    failNextWrites(true);
    act(() => result.current.updateContext({ question: "texto valioso" }));
    await waitFor(() => expect(result.current.saveState).toBe("error"));

    // Ahora intenta crear otro caso.
    let created: CaseRecord | null = null;
    await act(async () => {
      created = await result.current.createCase("Caso B", "explore-hypothesis");
    });

    // B NO se crea.
    expect(created).toBeNull();
    // A sigue activo, con su texto intacto.
    expect(result.current.activeCase?.id).toBe(idA);
    expect(result.current.activeCase?.context.question).toBe("texto valioso");
    // Y el error sigue a la vista: no se limpia al intentar una transición que
    // no pudo guardar.
    expect(result.current.error).toBeTruthy();
    expect(result.current.saveState).toBe("error");
  });

  it("tras reintentar con éxito, la transición sí funciona", async () => {
    window.localStorage.clear();
    const { repository, failNextWrites } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Caso A", "explore-hypothesis");
    });
    failNextWrites(true);
    act(() => result.current.updateContext({ question: "se recupera" }));
    await waitFor(() => expect(result.current.saveState).toBe("error"));

    // El disco vuelve. Reintentar escribe lo que estaba pendiente.
    failNextWrites(false);
    await act(async () => {
      await result.current.retrySave();
    });
    await waitFor(() => expect(result.current.saveState).toBe("saved"));

    // Y ahora sí se puede crear otro caso.
    let created: CaseRecord | null = null;
    await act(async () => {
      created = await result.current.createCase("Caso B", "explore-hypothesis");
    });
    expect(created).not.toBeNull();
    expect(result.current.activeCase?.name).toBe("Caso B");

    // El texto de A llegó a disco antes del cambio.
    const a = (await repository.listCases()).find((c) => c.name === "Caso A");
    expect(a).toBeTruthy();
    const reread = await repository.readCase(a!.id);
    expect(reread.context.question).toBe("se recupera");
  });

  it("`setArchived` tampoco archiva si el drenaje falla", async () => {
    window.localStorage.clear();
    const { repository, failNextWrites } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Archivable", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;

    failNextWrites(true);
    act(() => result.current.updateContext({ question: "sin guardar" }));
    await waitFor(() => expect(result.current.saveState).toBe("error"));

    await act(async () => {
      await result.current.setArchived(id, true);
    });
    // Archivar antes de drenar habría perdido la edición pendiente.
    expect(result.current.activeCase?.archived).toBe(false);
    expect(result.current.error).toMatch(/no se ha archivado/i);
  });
});

describe("corrida persistida", () => {
  it("el sistema queda PROVISIONAL mientras ninguna corrida ha terminado", async () => {
    window.localStorage.clear();
    const { repository } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Sistema fijado", "compare-series");
    });

    const startedAt = "2026-08-26T12:00:00.000Z";
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "6HSK", chain: "A", origin: "curado" },
        ligand: { inputSmiles: "CCO", canonicalSmiles: "CCO" },
        // La interfaz puede partir de una caja provisional; el preflight es
        // quien declara la caja que se ejecutará realmente.
        grid: { center: [0, 0, 0], size: [20, 20, 20] },
        customHotspots: ["A:ASP101"],
        dockingEngine: "vina",
        exhaustiveness: 8,
        numPoses: 9,
        conformers: 1,
      });
      result.current.setPreflight({
        fingerprint: "sha256:sistema-fijado",
        inputDocument: "{}",
        generatedAt: startedAt,
        schemaVersion: 1,
        executionRoute: "docking_vina",
        blockers: [],
        warnings: [],
        notEvaluated: [],
        receptorLabel: "6HSK · cadena A",
        ligandLabel: "CCO",
        gridLabel: "(-15.02, 2.30, -14.27)",
        receptorSourceSha256: "source-hash",
        preparedReceptorSha256: "prepared-hash",
        executionConfig: {
          gridCenter: [-15.02, 2.3, -14.27],
          gridSize: [22, 22, 22],
          customHotspots: ["A:ASP101"],
          dockingEngine: "vina",
          exhaustiveness: 8,
          numPoses: 9,
          seed: 42,
          conformers: 1,
        },
      });
    });
    await waitFor(() => expect(result.current.activeCase?.preflight?.fingerprint).toBe("sha256:sistema-fijado"));

    let registered = false;
    await act(async () => {
      registered = await result.current.registerRun({
        taskId: "task-sistema-fijado",
        executionState: "running",
        startedAt,
        inputFingerprint: "sha256:sistema-fijado",
      });
    });
    expect(registered).toBe(true);
    await waitFor(() => expect(result.current.activeCase?.structuralSystem?.sourceRunTaskId).toBe("task-sistema-fijado"));
    expect(result.current.activeCase?.structuralSystem).toMatchObject({
      receptor: { pdbId: "6HSK", chain: "A" },
      grid: { center: [-15.02, 2.3, -14.27], size: [22, 22, 22] },
      dockingEngine: "vina",
      receptorSourceSha256: "source-hash",
      preparedReceptorSha256: "prepared-hash",
    });

    // PROVISIONAL: el sistema está escrito, pero ninguna corrida ha terminado
    // todavía en él. Sellarlo aquí era el defecto: una primera corrida que
    // fallaba casaba el caso para siempre con una configuración que nunca
    // produjo nada, y la única salida era crear otro caso y perder el nombre,
    // el contexto y las notas.
    expect(structuralSystemIsSealed(result.current.activeCase!)).toBe(false);
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "1ABC", chain: "B", origin: "curado" },
      });
    });
    await waitFor(() => expect(result.current.activeCase?.inputs?.receptor?.pdbId).toBe("1ABC"));
    expect(result.current.error).toBeNull();

    // La ancla llega a disco igual, que es lo que preserva la comparación
    // entre futuras moléculas tras reiniciar la aplicación.
    const stored = await repository.readCase(result.current.activeCase!.id);
    expect(stored.structuralSystem?.sourceRunTaskId).toBe("task-sistema-fijado");
    expect(stored.runs.map((run) => run.taskId)).toEqual(["task-sistema-fijado"]);
  });

  it("al TERMINAR la corrida se sella el sistema, pero el protocolo sigue libre", async () => {
    window.localStorage.clear();
    const { repository } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Sistema sellado", "compare-series");
    });

    const startedAt = "2026-08-26T12:00:00.000Z";
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "6HSK", chain: "A", origin: "curado" },
        ligand: { inputSmiles: "CCO", canonicalSmiles: "CCO" },
        grid: { center: [0, 0, 0], size: [20, 20, 20] },
        customHotspots: ["A:ASP101"],
        dockingEngine: "vina",
        exhaustiveness: 8,
        numPoses: 9,
        conformers: 1,
      });
      result.current.setPreflight({
        fingerprint: "sha256:sistema-sellado",
        inputDocument: "{}",
        generatedAt: startedAt,
        schemaVersion: 1,
        executionRoute: "docking_vina",
        blockers: [],
        warnings: [],
        notEvaluated: [],
        receptorLabel: "6HSK · cadena A",
        ligandLabel: "CCO",
        gridLabel: "(-15.02, 2.30, -14.27)",
        receptorSourceSha256: "source-hash",
        preparedReceptorSha256: "prepared-hash",
        executionConfig: {
          gridCenter: [-15.02, 2.3, -14.27],
          gridSize: [22, 22, 22],
          customHotspots: ["A:ASP101"],
          dockingEngine: "vina",
          exhaustiveness: 8,
          numPoses: 9,
          seed: 42,
          conformers: 1,
        },
      });
    });
    await waitFor(() => expect(result.current.activeCase?.preflight?.fingerprint).toBe("sha256:sistema-sellado"));

    await act(async () => {
      await result.current.registerRun({
        taskId: "task-sellada",
        executionState: "running",
        startedAt,
        inputFingerprint: "sha256:sistema-sellado",
      });
    });
    act(() =>
      result.current.setActiveRun({
        taskId: "task-sellada",
        executionState: "completed",
        startedAt,
        moleculeId: "4b67aeb2-e1a8-4ea2-9c3a-001a8ecbf106",
      }),
    );
    await waitFor(() =>
      expect(structuralSystemIsSealed(result.current.activeCase!)).toBe(true),
    );

    // Una llamada directa no puede desanclar el SISTEMA aunque una futura vista
    // olvidara deshabilitar sus controles.
    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "1ABC", chain: "B", origin: "curado" },
        grid: { center: [99, 99, 99], size: [10, 10, 10] },
        ligand: { inputSmiles: "CCN", canonicalSmiles: "CCN" },
      });
    });
    await waitFor(() => expect(result.current.activeCase?.inputs?.ligand?.canonicalSmiles).toBe("CCN"));
    expect(result.current.activeCase?.inputs).toMatchObject({
      receptor: { pdbId: "6HSK", chain: "A" },
      grid: { center: [-15.02, 2.3, -14.27], size: [22, 22, 22] },
    });
    expect(result.current.error).toMatch(/sistema estructural/i);
    // El ligando cambia la hipótesis, por tanto el preflight de CCO no se
    // puede reciclar como si describiera CCN.
    expect(result.current.activeCase?.preflight).toBeUndefined();

    // El PROTOCOLO sí pasa. Repetir un ligando con más muestreo es trabajo
    // normal de laboratorio: lo que no se puede es hacerlo sin que quede
    // dicho, y de eso se encarga el protocolo sellado en cada fila del libro.
    act(() => {
      result.current.setInputs({ exhaustiveness: 32, numPoses: 20 });
    });
    await waitFor(() => expect(result.current.activeCase?.inputs?.exhaustiveness).toBe(32));
    expect(result.current.activeCase?.inputs?.numPoses).toBe(20);
  });

  it("registrar una corrida pone el caso en `running` y la escribe", async () => {
    window.localStorage.clear();
    const { repository } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Con corrida", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;

    act(() =>
      result.current.setActiveRun({
        taskId: "task-1",
        executionState: "running",
        startedAt: new Date().toISOString(),
      }),
    );

    await waitFor(() => expect(result.current.activeCase?.status).toBe("running"));
    expect(result.current.activeCase?.activeRun?.taskId).toBe("task-1");
    // Y llega a disco: es lo que permite reanudar tras cerrar la ventana.
    await waitFor(async () => {
      const reread = await repository.readCase(id);
      expect(reread.activeRun?.taskId).toBe("task-1");
    });
  });

  it("libera el cambio de caso cuando una escritura posterior recupera una corrida", async () => {
    window.localStorage.clear();
    const { repository, failNextWrites } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Registro recuperable", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;

    failNextWrites(true);
    let registered = true;
    await act(async () => {
      registered = await result.current.registerRun({
        taskId: "task-recovered",
        executionState: "running",
        startedAt: new Date().toISOString(),
      });
    });
    expect(registered).toBe(false);
    expect(result.current.unregisteredRun?.taskId).toBe("task-recovered");
    expect(result.current.hasLiveWork).toBe(true);

    // A terminal mirror after storage recovers must persist the task and clear
    // the temporary guard. Otherwise a completed task keeps the sidebar locked.
    failNextWrites(false);
    act(() =>
      result.current.setActiveRun({
        taskId: "task-recovered",
        executionState: "completed",
        startedAt: new Date().toISOString(),
      }),
    );

    await waitFor(() => expect(result.current.unregisteredRun).toBeNull());
    expect(result.current.hasLiveWork).toBe(false);
    await waitFor(async () => {
      const stored = await repository.readCase(id);
      expect(stored.activeRun).toMatchObject({
        taskId: "task-recovered",
        executionState: "completed",
      });
    });
  });

  it("cerrar la corrida saca al caso de `running` sin declararlo completo", async () => {
    window.localStorage.clear();
    const { repository } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Termina", "explore-hypothesis");
    });
    act(() =>
      result.current.setActiveRun({
        taskId: "task-2",
        executionState: "running",
        startedAt: new Date().toISOString(),
      }),
    );
    await waitFor(() => expect(result.current.activeCase?.status).toBe("running"));

    act(() => result.current.setActiveRun(null));

    await waitFor(() => expect(result.current.activeCase?.status).toBe("review"));
    // NO `completed`: un cálculo que termina no completa un caso, lo deja
    // pendiente de que una persona lo mire.
    expect(result.current.activeCase?.status).not.toBe("completed");
    // Y el caso NO se queda atrapado en `running`.
    expect(result.current.hasLiveWork).toBe(false);
    // Pero la corrida NO desaparece del libro. Dejar de seguirla no es no
    // haberla hecho: su fila es el único puntero que queda a su informe.
    expect(result.current.activeCase?.runs.map((run) => run.taskId)).toEqual(["task-2"]);
  });

  it("una corrida INTERRUMPIDA conserva el taskId sin bloquear el workspace", async () => {
    window.localStorage.clear();
    const { repository } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Interrumpida", "explore-hypothesis");
    });
    act(() =>
      result.current.setActiveRun({
        taskId: "task-3",
        executionState: "interrupted",
        startedAt: new Date().toISOString(),
        lastError: "Se perdió la conexión.",
      }),
    );

    await waitFor(() => expect(result.current.activeCase?.activeRun?.taskId).toBe("task-3"));
    // Interrumpido no afirma que el backend fallo y conserva como reanudarlo,
    // pero ya no hay polling vivo que justifique secuestrar la navegacion.
    expect(result.current.activeCase?.status).not.toBe("running");
    expect(result.current.hasLiveWork).toBe(false);
  });
});

describe("persistencia de un ligando vacío", () => {
  it("omite el ligando incompleto y conserva el resto del caso en disco", async () => {
    window.localStorage.clear();
    const { repository } = controllableRepository();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Ligando editable", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;

    act(() => {
      result.current.setInputs({
        receptor: { pdbId: "4DQC", chain: "A", origin: "curado" },
        ligand: { inputSmiles: "CCO" },
      });
    });
    await waitFor(() => expect(result.current.activeCase?.inputs?.ligand?.inputSmiles).toBe("CCO"));

    act(() => {
      result.current.setInputs({ ligand: { inputSmiles: "" } });
    });
    await waitFor(() => expect(result.current.saveState).toBe("saved"));

    expect(result.current.activeCase?.inputs?.ligand).toBeUndefined();
    expect(result.current.activeCase?.inputs?.receptor?.pdbId).toBe("4DQC");
    const stored = await repository.readCase(id);
    expect(stored.inputs?.ligand).toBeUndefined();
    expect(stored.inputs?.receptor?.pdbId).toBe("4DQC");
  });
});
