// =====================================================================
// R3 — persistencia crítica del taskId, trabajo vivo y salud del índice
// =====================================================================
//
// Tres regresiones que R2 dejó abiertas:
//
//  1. El `taskId` recién nacido dependía del autosave de 600 ms. Cerrar la
//     ventana en esa franja dejaba la tarea viva en el backend sin que nada la
//     registrara: trabajo huérfano por una carrera de temporizador.
//  2. `hasLiveWork` sólo contaba lo que el runner declaraba, así que un caso
//     reabierto con una corrida persistida se podía abandonar antes de visitar
//     Evaluar.
//  3. Un índice corrupto producía la misma lista vacía que un primer arranque,
//     y esa lista vacía se presentaba como estado sano.

import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { CaseProvider, useCases } from "../CaseContext";
import { createBrowserCaseRepository } from "../../lib/cases/browserCaseRepository";
import type { CaseRepository, RegistryHealth } from "../../lib/cases/repository";
import type { ActiveRun, CaseRecord } from "../../lib/cases/types";

function controllable(extra?: Partial<CaseRepository>) {
  const inner = createBrowserCaseRepository("test-owner");
  const state = { fail: false, writes: [] as CaseRecord[] };
  const repository: CaseRepository = {
    ...inner,
    async updateCase(record: CaseRecord) {
      if (state.fail) throw new Error("disco lleno");
      state.writes.push(record);
      return inner.updateCase(record);
    },
    ...extra,
  };
  return { repository, state };
}

function wrapper(repository: CaseRepository) {
  return function Wrapper({ children }: { children: ReactNode }) {
    // Debounce LARGO a propósito: si el registro dependiera del autosave, este
    // test no vería la escritura y fallaría. Es justamente lo que comprueba.
    return (
      <CaseProvider repository={repository} autosaveDelayMs={5000}>
        {children}
      </CaseProvider>
    );
  };
}

const RUN: ActiveRun = {
  taskId: "task-critica",
  executionState: "submitted",
  startedAt: "2026-08-23T12:00:00.000Z",
};

describe("registro crítico del taskId", () => {
  it("llega al repositorio ANTES de completar el flujo, sin esperar al debounce", async () => {
    window.localStorage.clear();
    const { repository, state } = controllable();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Con corrida", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;
    state.writes.length = 0;

    let ok: boolean | null = null;
    await act(async () => {
      ok = await result.current.registerRun(RUN);
    });

    // La promesa NO resuelve hasta que la escritura confirma.
    expect(ok).toBe(true);
    // Y la corrida ya está en el repositorio, con un debounce de 5 s por medio.
    const persisted = await repository.readCase(id);
    expect(persisted.activeRun?.taskId).toBe("task-critica");
    expect(state.writes.some((w) => w.activeRun?.taskId === "task-critica")).toBe(true);
    expect(result.current.unregisteredRun).toBeNull();
  });

  it("si la escritura falla, CONSERVA el taskId y bloquea el cambio de caso", async () => {
    window.localStorage.clear();
    const { repository, state } = controllable();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Fallo al registrar", "explore-hypothesis");
    });

    state.fail = true;
    let ok: boolean | null = null;
    await act(async () => {
      ok = await result.current.registerRun(RUN);
    });

    expect(ok).toBe(false);
    // El identificador NO se pierde: es lo único que permite volver a
    // encontrar la tarea, que sigue corriendo en el backend.
    expect(result.current.unregisteredRun?.taskId).toBe("task-critica");
    // Y bloquea: cerrar o cambiar de caso ahora lo perdería.
    expect(result.current.hasLiveWork).toBe(true);
    expect(result.current.error).toMatch(/no se pudo guardar/i);

    // Crear otro caso queda vetado.
    let created: CaseRecord | null = null;
    await act(async () => {
      created = await result.current.createCase("Otro", "explore-hypothesis");
    });
    expect(created).toBeNull();
  });

  it("reintentar el registro lo persiste y desbloquea", async () => {
    window.localStorage.clear();
    const { repository, state } = controllable();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Reintenta", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;

    state.fail = true;
    await act(async () => {
      await result.current.registerRun(RUN);
    });
    expect(result.current.unregisteredRun).not.toBeNull();

    state.fail = false;
    let ok: boolean | null = null;
    await act(async () => {
      ok = await result.current.retryRegisterRun();
    });

    expect(ok).toBe(true);
    expect(result.current.unregisteredRun).toBeNull();
    const persisted = await repository.readCase(id);
    expect(persisted.activeRun?.taskId).toBe("task-critica");
  });
});

describe("trabajo vivo de una corrida recuperada", () => {
  it("bloquea desde que se abre el caso, sin visitar Evaluar", async () => {
    window.localStorage.clear();
    const { repository } = controllable();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Un caso que YA traía una corrida viva del disco.
    await act(async () => {
      await result.current.createCase("Reabierto", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;
    await act(async () => {
      await repository.updateCase({
        ...(await repository.readCase(id)),
        status: "running",
        activeRun: { taskId: "task-vieja", executionState: "running", startedAt: RUN.startedAt },
      });
    });
    // Se cierra y se vuelve a abrir, como haría un reinicio.
    await act(async () => {
      await result.current.closeCase();
    });
    await act(async () => {
      await result.current.selectCase(id);
    });

    // El caso está bloqueado por la corrida PERSISTIDA, sin depender de que
    // ningún componente se haya montado: el guard vive en el manifiesto.
    expect(result.current.hasLiveWork).toBe(true);

    let created: CaseRecord | null = null;
    await act(async () => {
      created = await result.current.createCase("Nuevo", "explore-hypothesis");
    });
    expect(created).toBeNull();
    expect(result.current.activeCase?.id).toBe(id);
  });

  it("una corrida TERMINAL no bloquea nada", async () => {
    window.localStorage.clear();
    const { repository } = controllable();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.createCase("Terminada", "explore-hypothesis");
    });
    const id = result.current.activeCase!.id;
    await act(async () => {
      await repository.updateCase({
        ...(await repository.readCase(id)),
        activeRun: { taskId: "t", executionState: "completed", startedAt: RUN.startedAt },
      });
    });
    await act(async () => {
      await result.current.closeCase();
    });
    await act(async () => {
      await result.current.selectCase(id);
    });
    expect(result.current.hasLiveWork).toBe(false);
    expect(result.current.activeCase?.activeRun).toEqual(
      expect.objectContaining({ taskId: "t", executionState: "completed" }),
    );
  });
});

describe("salud del índice", () => {
  async function healthOf(health: RegistryHealth) {
    window.localStorage.clear();
    const { repository } = controllable({ registryHealth: async () => health });
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.registryHealth).not.toBeNull());
    return result;
  }

  it("un primer arranque no dice nada: la lista vacía es correcta", async () => {
    const result = await healthOf({ state: "first_run" });
    expect(result.current.registryHealth?.state).toBe("first_run");
    expect(result.current.error).toBeNull();
  });

  it("un índice CORRUPTO no se presenta como estado sano", async () => {
    const result = await healthOf({ state: "corrupted", detail: "JSON roto" });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    // La lista vacía de un índice ilegible tiene que decir que lo es.
    expect(result.current.error).toMatch(/no se pudo leer/i);
    expect(result.current.error).toMatch(/incompleta/i);
  });

  it("un índice recuperado del backup avisa de que puede faltar algo", async () => {
    const result = await healthOf({ state: "recovered_from_backup", detail: "x" });
    await waitFor(() => expect(result.current.error).toBeTruthy());
    expect(result.current.error).toMatch(/copia de seguridad/i);
  });

  it("un repositorio sin salud declarada se considera sano", async () => {
    window.localStorage.clear();
    // El repositorio de navegador no tiene índice de autorizaciones.
    const { repository } = controllable();
    const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
    await waitFor(() => expect(result.current.registryHealth?.state).toBe("ok"));
    expect(result.current.error).toBeNull();
  });
});
