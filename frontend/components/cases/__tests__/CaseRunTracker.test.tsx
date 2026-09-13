// =====================================================================
// R3 — el tracker ligero sigue una corrida sin montar la evaluación
// =====================================================================
//
// EL HUECO. Una corrida persistida sólo se reanudaba al montar el runner, y el
// runner sólo se monta al visitar Evaluar. Un caso reabierto con una corrida
// viva, con el usuario en Contexto, no seguía a nadie: la tarea corría en el
// backend y la interfaz no se enteraba.
//
// Montar el runner automáticamente habría arrastrado Ketcher y Molstar sólo
// para hacer un GET cada dos segundos.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, waitFor } from "@testing-library/react";
import { useState } from "react";

import type { ActiveRun } from "../../../lib/cases/types";

const getJobStatus = vi.fn();
vi.mock("../../../lib/api", () => ({
  getJobStatus: (id: string) => getJobStatus(id),
}));

import { CaseRunTracker } from "../CaseRunTracker";

const RUN: ActiveRun = {
  taskId: "task-track",
  executionState: "running",
  startedAt: "2026-08-23T12:00:00.000Z",
};

function status(state: string, progress = 10) {
  return {
    task_id: "task-track",
    status: state,
    progress,
    result: null,
    error: null,
    started_at: RUN.startedAt,
    finished_at: null,
  };
}

function StatefulTracker({
  onChange,
  pollIntervalMs = 5,
}: {
  onChange: (run: ActiveRun | null) => void;
  pollIntervalMs?: number;
}) {
  const [run, setRun] = useState(RUN);
  return (
    <CaseRunTracker
      activeRun={run}
      pollIntervalMs={pollIntervalMs}
      onActiveRunChange={(next) => {
        onChange(next);
        if (next) setRun(next);
      }}
    />
  );
}

describe("CaseRunTracker", () => {
  // `mockReset` a secas deja el mock devolviendo `undefined`, y en ese estado
  // los tests de este archivo se contaminaban entre sí: el error de uno se
  // atribuía al siguiente. No he aislado el mecanismo exacto; lo que sí está
  // comprobado —con una prueba aislada— es que el componente hace 5 consultas y
  // declara `interrupted`. Se le da una implementación inocua por defecto para
  // que ninguna llamada rezagada devuelva `undefined`.
  beforeEach(() => {
    getJobStatus.mockReset();
    getJobStatus.mockResolvedValue(status("PENDING"));
  });

  it("no renderiza nada: es sólo seguimiento", async () => {
    getJobStatus.mockResolvedValue(status("STARTED"));
    const { container } = render(
      <CaseRunTracker activeRun={RUN} onActiveRunChange={vi.fn()} />,
    );
    await waitFor(() => expect(getJobStatus).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("pregunta de inmediato y refleja el progreso", async () => {
    getJobStatus.mockResolvedValue(status("STARTED", 42));
    const onActiveRunChange = vi.fn();
    render(<CaseRunTracker activeRun={RUN} onActiveRunChange={onActiveRunChange} />);

    // Sin esperar al primer tick: dos segundos con el estado viejo en pantalla
    // son dos segundos mintiendo.
    await waitFor(() => expect(getJobStatus).toHaveBeenCalledWith("task-track"));
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ taskId: "task-track", lastKnownProgress: 42 }),
      ),
    );
  });

  it("conserva la identidad de la corrida cuando la tarea termina", async () => {
    getJobStatus.mockResolvedValue(status("SUCCESS", 100));
    const onActiveRunChange = vi.fn();
    render(<CaseRunTracker activeRun={RUN} onActiveRunChange={onActiveRunChange} />);
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({
          taskId: "task-track",
          executionState: "completed",
          lastKnownProgress: 100,
        }),
      ),
    );
    expect(onActiveRunChange).not.toHaveBeenCalledWith(null);
  });

  it("no sigue una corrida ya terminal", async () => {
    render(
      <CaseRunTracker
        activeRun={{ ...RUN, executionState: "completed" }}
        onActiveRunChange={vi.fn()}
      />,
    );
    // Nada que seguir: preguntar por una tarea acabada es ruido.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(getJobStatus).not.toHaveBeenCalled();
  });

  it("tras varios fallos declara INTERRUMPIDO, no fallido", async () => {
    // Throw SÍNCRONO: basta para ejercitar el mismo `catch`.
    getJobStatus.mockImplementation(() => {
      throw new Error("ECONNREFUSED");
    });
    const onActiveRunChange = vi.fn();
    // Intervalo corto: el umbral son cinco fallos, y esperarlos a 2 s reales
    // haría el test lento y dependiente del reloj.
    render(<StatefulTracker onChange={onActiveRunChange} />);

    // Espera simple en vez de `waitFor`: el envoltorio de `waitFor` intercepta
    // los errores que jsdom emite desde los callbacks de temporizador y los
    // atribuye al test, aunque el componente los capture. Aquí se deja correr
    // el reloj y se comprueba el resultado.
    await new Promise((resolve) => setTimeout(resolve, 200));

    expect(getJobStatus).toHaveBeenCalledTimes(5);
    expect(onActiveRunChange).toHaveBeenCalledWith(
      expect.objectContaining({ executionState: "interrupted", taskId: "task-track" }),
    );
    // Y NUNCA cierra la corrida: cerrarla afirmaría que terminó.
    expect(onActiveRunChange.mock.calls.some(([run]) => run === null)).toBe(false);
  });

  it("una respuesta en vuelo no puede cerrar la corrida tras cambiar de sesión", async () => {
    let resolveStatus!: (value: ReturnType<typeof status>) => void;
    getJobStatus.mockReturnValue(
      new Promise((resolve) => {
        resolveStatus = resolve;
      }),
    );
    const onActiveRunChange = vi.fn();
    render(<StatefulTracker onChange={onActiveRunChange} />);
    await waitFor(() => expect(getJobStatus).toHaveBeenCalledTimes(1));

    act(() => {
      window.dispatchEvent(new Event("auth_expired"));
    });
    await waitFor(() =>
      expect(onActiveRunChange).toHaveBeenCalledWith(
        expect.objectContaining({ executionState: "interrupted", taskId: "task-track" }),
      ),
    );

    await act(async () => {
      resolveStatus(status("SUCCESS", 100));
      await Promise.resolve();
    });
    expect(
      onActiveRunChange.mock.calls.some(
        ([run]) => run?.executionState === "completed" || run?.executionState === "failed",
      ),
    ).toBe(false);
  });
});
