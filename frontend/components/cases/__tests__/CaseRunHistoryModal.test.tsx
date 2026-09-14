// =====================================================================
// CaseRunHistoryModal — el caso recupera lo que produjo, sin repetirlo
// =====================================================================
//
// LO QUE ESTE ARCHIVO PROTEGE, en orden de gravedad:
//
// 1. **Atribución.** El detalle se pide SIEMPRE con el `task_id` de la fila.
//    Sin él, el backend devuelve la proyección más reciente de esa molécula
//    —que puede ser la de otra corrida posterior— y «ver la evaluación
//    anterior» pasaría a enseñar otra cosa con la misma cara.
//
// 2. **Comparabilidad visible.** Una corrida que se ejecutó con otro protocolo
//    se marca. El producto no prohíbe cambiar el muestreo; lo que no puede
//    permitir es que dos corridas incomparables se lean como comparables.
//
// 3. **Honestidad del fallo.** Una corrida que falló, que se canceló o que
//    perdió la referencia a su resultado dice POR QUÉ no se puede abrir, en vez
//    de esconder el botón y dejar al usuario buscando.
//
// 4. **Legibilidad sin backend.** La lista se pinta con lo que guarda el propio
//    `case.json`: el libro se lee con el motor apagado.

import { describe, expect, it, beforeEach, afterEach, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

import CaseRunHistoryModal, { whyRunCannotOpen } from "../CaseRunHistoryModal";
import type { CaseRun, CaseStructuralSystem } from "../../../lib/cases/types";

const getEvaluationResult = vi.fn();

vi.mock("../../../lib/api", () => ({
  getEvaluationResult: (...args: unknown[]) => getEvaluationResult(...args),
  downloadCertificate: vi.fn(),
  downloadComplexFile: vi.fn(),
}));

vi.mock("@/hooks/useScrollLock", () => ({ useScrollLock: () => {} }));

const SYSTEM: CaseStructuralSystem = {
  lockedAt: "2026-08-23T12:00:00.000Z",
  sourceRunTaskId: "task-1",
  inputFingerprint: "fp-1",
  receptor: { pdbId: "6HSK", chain: "A", origin: "curado" },
  grid: { center: [1, 2, 3], size: [22, 22, 22] },
  customHotspots: [],
  dockingEngine: "vina",
  exhaustiveness: 8,
  numPoses: 9,
  conformers: 1,
};

const COMPLETED: CaseRun = {
  taskId: "task-1-abcdef",
  moleculeId: "4b67aeb2-e1a8-4ea2-9c3a-001a8ecbf106",
  executionState: "completed",
  startedAt: "2026-08-23T12:00:00.000Z",
  ligandSmiles: "CCO",
  affinityKcal: -7.42,
  inputFingerprint: "fp-1",
  protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 },
};

const RERUN_DEEPER: CaseRun = {
  taskId: "task-2-abcdef",
  moleculeId: "9c3a0001-e1a8-4ea2-9c3a-001a8ecbf107",
  executionState: "completed",
  startedAt: "2026-08-23T14:00:00.000Z",
  ligandSmiles: "CCN",
  affinityKcal: -8.1,
  inputFingerprint: "fp-1",
  protocol: { dockingEngine: "vina", exhaustiveness: 32, numPoses: 20, conformers: 1 },
};

const FAILED: CaseRun = {
  taskId: "task-3-abcdef",
  executionState: "failed",
  startedAt: "2026-08-23T16:00:00.000Z",
  ligandSmiles: "CCC",
  lastError: "Vina no pudo preparar el receptor.",
};

function renderModal(runs: readonly CaseRun[], onClose = vi.fn()) {
  return render(
    <CaseRunHistoryModal
      runs={runs}
      structuralSystem={SYSTEM}
      currentFingerprint="fp-1"
      activeTaskId={runs[runs.length - 1]?.taskId}
      onClose={onClose}
    />,
  );
}

beforeEach(() => {
  getEvaluationResult.mockReset();
});

afterEach(() => {
  cleanup();
});

describe("el libro se lee sin backend", () => {
  it("lista todas las corridas, la más reciente arriba", () => {
    renderModal([COMPLETED, RERUN_DEEPER, FAILED]);
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    // La regresión que motivó todo esto: la corrida vieja seguía existiendo y
    // el caso había perdido el puntero.
    expect(rows[2]).toHaveTextContent("CCO");
    expect(rows[0]).toHaveTextContent("CCC");
    expect(getEvaluationResult).not.toHaveBeenCalled();
  });

  it("enseña afinidad y protocolo de cada fila sin pedir nada", () => {
    renderModal([COMPLETED]);
    expect(screen.getByText(/-7\.42 kcal\/mol/)).toBeInTheDocument();
    expect(screen.getByText(/vina · exh 8 · 9 poses/)).toBeInTheDocument();
  });

  it("una fila migrada de v6 dice que no sabe, no inventa", () => {
    renderModal([
      { taskId: "task-legacy", executionState: "completed", startedAt: COMPLETED.startedAt, moleculeId: "m" },
    ]);
    expect(screen.getByText(/Ligando no registrado/i)).toBeInTheDocument();
    expect(screen.getByText(/Protocolo no registrado/i)).toBeInTheDocument();
    // Sin afinidad guardada se muestra el guion, nunca un cero.
    expect(screen.queryByText(/0\.00 kcal\/mol/)).not.toBeInTheDocument();
  });
});

describe("comparabilidad visible", () => {
  it("marca la corrida que usó otro protocolo", () => {
    renderModal([COMPLETED, RERUN_DEEPER]);
    const rows = screen.getAllByRole("listitem");
    // La de exhaustiveness 32 se salió del protocolo del caso: se dice.
    expect(rows[0]).toHaveTextContent(/Otro protocolo/i);
    expect(rows[1]).not.toHaveTextContent(/Otro protocolo/i);
  });

  it("no marca nada cuando el protocolo coincide", () => {
    renderModal([COMPLETED]);
    expect(screen.queryByText(/Otro protocolo/i)).not.toBeInTheDocument();
  });

  it("marca una corrida lanzada con otra hipótesis", () => {
    render(
      <CaseRunHistoryModal
        runs={[{ ...COMPLETED, inputFingerprint: "fp-vieja" }]}
        structuralSystem={SYSTEM}
        currentFingerprint="fp-1"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText(/Otra hipótesis/i)).toBeInTheDocument();
  });
});

describe("atribución: el detalle es el de ESTA corrida", () => {
  it("pide el resultado con el task_id de la fila, no sólo con la molécula", async () => {
    getEvaluationResult.mockResolvedValue({
      molecule_id: COMPLETED.moleculeId,
      affinity_kcal: -7.42,
      docking_poses: [{}, {}],
      target_name: "6HSK",
      vina_version: "1.2.5",
      ml_pki: null,
      ml_pki_aplicada: null,
    });
    renderModal([COMPLETED]);
    fireEvent.click(screen.getByRole("button", { name: /ver resultado/i }));
    await waitFor(() =>
      expect(getEvaluationResult).toHaveBeenCalledWith(COMPLETED.moleculeId, COMPLETED.taskId),
    );
    expect(await screen.findByText("1.2.5")).toBeInTheDocument();
  });

  it("un fallo de lectura no se disfraza de resultado vacío", async () => {
    getEvaluationResult.mockRejectedValue(new Error("El motor local no está disponible."));
    renderModal([COMPLETED]);
    fireEvent.click(screen.getByRole("button", { name: /ver resultado/i }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/motor local no está disponible/i);
    // Y no se afirma que el resultado se haya perdido: sólo que no se ha leído.
    expect(alert).toHaveTextContent(/no se ha podido leer, no que se haya perdido/i);
  });
});

describe("una corrida que no se puede abrir dice por qué", () => {
  it("la fallida no ofrece informe y explica el motivo", () => {
    renderModal([FAILED]);
    expect(screen.getByRole("button", { name: /ver resultado/i })).toBeDisabled();
    expect(screen.getByText(/no produjo ningún informe/i)).toBeInTheDocument();
    // El error del backend se conserva, no se resume a «falló».
    expect(screen.getByText(/Vina no pudo preparar el receptor/)).toBeInTheDocument();
  });

  it("distingue cada causa en vez de esconder el botón", () => {
    expect(whyRunCannotOpen(FAILED)).toMatch(/falló/i);
    expect(whyRunCannotOpen({ ...FAILED, executionState: "cancelled" })).toMatch(/canceló/i);
    expect(whyRunCannotOpen({ ...FAILED, executionState: "running" })).toMatch(/ejecutando/i);
    expect(whyRunCannotOpen({ ...FAILED, executionState: "interrupted" })).toMatch(/seguimiento/i);
    // Terminada pero SIN referencia durable: el caso no guardó con qué reabrir.
    expect(
      whyRunCannotOpen({ ...FAILED, executionState: "completed", moleculeId: undefined }),
    ).toMatch(/referencia a su resultado/i);
    expect(whyRunCannotOpen(COMPLETED)).toBeNull();
  });
});

describe("el panel no toca el caso", () => {
  it("un libro vacío lo dice sin fingir", () => {
    renderModal([]);
    expect(screen.getByText(/todavía no ha lanzado ninguna evaluación/i)).toBeInTheDocument();
  });

  it("señala cuál es la corrida que está en pantalla", () => {
    renderModal([COMPLETED, RERUN_DEEPER]);
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent(/En pantalla/i);
    expect(rows[1]).not.toHaveTextContent(/En pantalla/i);
  });

  it("cierra con Escape", () => {
    const onClose = vi.fn();
    renderModal([COMPLETED], onClose);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
