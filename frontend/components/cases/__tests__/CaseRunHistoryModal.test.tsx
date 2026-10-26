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
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import CaseRunHistoryModal, { whyRunCannotOpen } from "../CaseRunHistoryModal";
import type { CaseRun, CaseStructuralSystem } from "../../../lib/cases/types";

const getEvaluationResult = vi.fn();
const downloadCertificate = vi.fn();
const downloadComplexFile = vi.fn();

vi.mock("../../../lib/api", () => ({
  getEvaluationResult: (...args: unknown[]) => getEvaluationResult(...args),
  downloadCertificate: (...args: unknown[]) => downloadCertificate(...args),
  downloadComplexFile: (...args: unknown[]) => downloadComplexFile(...args),
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
  downloadCertificate.mockReset();
  downloadComplexFile.mockReset();
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

// ── CAS-06: el fallo de una descarga se ve, no se traga ──────────────
//
// La auditoría lo midió en vivo: pedir el PDF de una corrida de ensemble
// desde el historial devolvía HTTP 500 y el botón hacía `void` sobre la
// promesa — el rechazo quedaba en consola y al usuario no le pasaba nada al
// pulsar. Un botón silencioso no es honesto: la descarga falló y hay que
// decirlo junto al botón, sin destruir el resultado que ya está abierto.

async function abrirResultado() {
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
  expect(await screen.findByText("1.2.5")).toBeInTheDocument();
}

describe("las descargas son las de la corrida abierta", () => {
  // Una molécula se reevalúa varias veces en el caso. El informe y el complejo de
  // una corrida anterior son los de ESA corrida: sin su `task_id` el backend
  // respondía con la última evaluación de la molécula.
  it("el informe y el complejo piden la corrida abierta, no la última de la molécula", async () => {
    await abrirResultado();
    downloadCertificate.mockResolvedValue(undefined);
    downloadComplexFile.mockResolvedValue(undefined);

    fireEvent.click(screen.getByRole("button", { name: /descargar informe/i }));
    fireEvent.click(screen.getByRole("button", { name: /complejo 3d/i }));

    expect(downloadCertificate).toHaveBeenCalledWith(COMPLETED.moleculeId, "general", COMPLETED.taskId);
    expect(downloadComplexFile).toHaveBeenCalledWith(COMPLETED.moleculeId, "general", COMPLETED.taskId);
  });
});

describe("CAS-06: el fallo de una descarga se ve", () => {
  it("un PDF que el servidor no puede componer dice por qué, junto al botón", async () => {
    await abrirResultado();
    downloadCertificate.mockRejectedValue(
      new Error("No se pudo generar el PDF de esta corrida (HTTP 500)."),
    );

    fireEvent.click(screen.getByRole("button", { name: /descargar informe/i }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(/HTTP 500/i);
    // El resultado abierto NO se pierde por un fallo de descarga.
    expect(screen.getByText("1.2.5")).toBeInTheDocument();
  });

  it("reintentar limpia el error anterior", async () => {
    await abrirResultado();
    downloadCertificate
      .mockRejectedValueOnce(new Error("No se pudo generar el PDF (HTTP 500)."))
      .mockResolvedValueOnce(undefined);

    fireEvent.click(screen.getByRole("button", { name: /descargar informe/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/HTTP 500/i);

    fireEvent.click(screen.getByRole("button", { name: /descargar informe/i }));
    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
  });

  it("el complejo 3D fallido también se declara", async () => {
    await abrirResultado();
    downloadComplexFile.mockRejectedValue(
      new Error("El complejo no está disponible (HTTP 404)."),
    );

    fireEvent.click(screen.getByRole("button", { name: /complejo 3d/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/HTTP 404/i);
  });
});

// CAS-01 / CAS-03. Con 40 corridas de la misma molécula (20 únicas y 20
// ensemble) la fila no decía K, «Otro protocolo» no decía qué cambió y no había
// forma de aislar una serie. Nada de esto toca el libro: sólo lo que se muestra.
describe("K y diferencias de protocolo en la fila (CAS-01)", () => {
  const ENSEMBLE: CaseRun = {
    ...COMPLETED,
    taskId: "task-ens-abcdef",
    startedAt: "2026-08-23T15:00:00.000Z",
    protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 30 },
  };

  it("cada fila dice si fue única o ensemble y con qué K", () => {
    renderModal([COMPLETED, ENSEMBLE]);
    const filas = screen.getAllByRole("listitem");
    expect(filas[1]).toHaveTextContent("Único K=1");
    expect(filas[0]).toHaveTextContent("Ensemble K=30");
  });

  it("«Otro protocolo» nombra qué cambió y el valor del sistema inicial", () => {
    renderModal([COMPLETED, ENSEMBLE]);
    const filaEnsemble = screen.getAllByRole("listitem")[0];
    expect(filaEnsemble).toHaveTextContent(/Otro protocolo/i);
    expect(filaEnsemble).toHaveTextContent("Difiere del sistema inicial: K=30 (sistema: K=1).");
  });

  it("varios campos distintos se enumeran", () => {
    renderModal([COMPLETED, RERUN_DEEPER]);
    const fila = screen.getAllByRole("listitem")[0];
    expect(fila).toHaveTextContent("exhaustividad 32 (sistema: 8)");
    expect(fila).toHaveTextContent("20 poses (sistema: 9)");
  });

  it("una fila igual al sistema no inventa diferencias", () => {
    renderModal([COMPLETED, ENSEMBLE]);
    expect(screen.getAllByRole("listitem")[1]).not.toHaveTextContent(/Difiere del sistema/);
  });

  it("una fila sin protocolo registrado no muestra K ni diferencias", () => {
    renderModal([{ taskId: "legado", executionState: "completed", startedAt: COMPLETED.startedAt, moleculeId: "m" }, COMPLETED]);
    const fila = screen.getAllByRole("listitem")[1];
    expect(fila).toHaveTextContent("Protocolo no registrado");
    expect(fila).not.toHaveTextContent(/K=/);
  });
});

describe("filtros del libro (CAS-03)", () => {
  const ENS = (n: number): CaseRun => ({
    ...COMPLETED,
    taskId: `task-ens-${n}-abcdef`,
    ligandSmiles: `CC${"N".repeat(n)}`,
    startedAt: `2026-08-24T1${n}:00:00.000Z`,
    protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 30 },
  });
  const LIBRO = [COMPLETED, RERUN_DEEPER, FAILED, ENS(1), ENS(2)];

  it("con una sola corrida no hay barra de filtros que estorbe", () => {
    renderModal([COMPLETED]);
    expect(screen.queryByRole("search")).not.toBeInTheDocument();
  });

  it("cuenta cada modo y dice cuántas muestra de cuántas", () => {
    renderModal(LIBRO);
    expect(screen.getByRole("button", { name: "Todas (5)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Únicas (2)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ensembles (2)" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Mostrando 5 de 5");
  });

  it("el modo ensemble deja sólo los ensembles y lo dice", () => {
    renderModal(LIBRO);
    fireEvent.click(screen.getByRole("button", { name: "Ensembles (2)" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Ensembles (2)" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Mostrando 2 de 5");
  });

  it("por estado, sólo con los estados que existen en el libro", () => {
    renderModal(LIBRO);
    const selector = screen.getByLabelText(/Estado/i) as HTMLSelectElement;
    const opciones = Array.from(selector.options).map((o) => o.textContent);
    expect(opciones).toEqual(["Todos", "Terminada", "Fallida"]);
    fireEvent.change(selector, { target: { value: "failed" } });
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent("CCC");
  });

  it("por texto en el SMILES", () => {
    renderModal(LIBRO);
    fireEvent.change(screen.getByRole("searchbox", { name: /Buscar por SMILES o corrida/i }), { target: { value: "ccnn" } });
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getAllByRole("listitem")[0]).toHaveTextContent("CCNN");
  });

  it("sin coincidencias lo dice y ofrece quitar los filtros, que devuelve todo", () => {
    renderModal(LIBRO);
    fireEvent.change(screen.getByRole("searchbox"), { target: { value: "zzz" } });
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    expect(screen.getByText("Ninguna evaluación coincide con este filtro.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Quitar filtros" }));
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
  });

  it("filtrar no reabre ni pide nada al backend", () => {
    renderModal(LIBRO);
    fireEvent.click(screen.getByRole("button", { name: "Únicas (2)" }));
    expect(getEvaluationResult).not.toHaveBeenCalled();
  });
});


describe("destino de Actividad sin cambiar el libro", () => {
  it("abre y enfoca la corrida histórica solicitada por su task exacta", async () => {
    getEvaluationResult.mockResolvedValue({ molecule_id: COMPLETED.moleculeId, affinity_kcal: -7.42,
      docking_poses: [], target_name: "6HSK", vina_version: "1.2.7" });
    const selected = vi.fn();
    const book = [COMPLETED, RERUN_DEEPER];
    render(<CaseRunHistoryModal runs={book} currentFingerprint="fp-1" activeTaskId={RERUN_DEEPER.taskId}
      requestedTaskId={COMPLETED.taskId} onRequestedRunSelected={selected} onClose={vi.fn()} />);
    await waitFor(() => expect(selected).toHaveBeenCalledWith(COMPLETED.taskId));
    expect(getEvaluationResult).toHaveBeenCalledWith(COMPLETED.moleculeId, COMPLETED.taskId);
    expect(getEvaluationResult).not.toHaveBeenCalledWith(RERUN_DEEPER.moleculeId, RERUN_DEEPER.taskId);
    const row = document.querySelector(`[data-case-run-task="${COMPLETED.taskId}"]`);
    expect(row).toHaveFocus();
    expect(book.map(r => r.taskId)).toEqual([COMPLETED.taskId, RERUN_DEEPER.taskId]);
  });

  it("una referencia ajena no selecciona otra fila ni consulta su resultado", () => {
    const selected = vi.fn();
    render(<CaseRunHistoryModal runs={[COMPLETED]} currentFingerprint="fp-1" requestedTaskId="otra-corrida"
      onRequestedRunSelected={selected} onClose={vi.fn()} />);
    expect(selected).not.toHaveBeenCalled();
    expect(getEvaluationResult).not.toHaveBeenCalled();
  });
});


it("la solicitud de Actividad se consume una vez y no deshace una selección manual posterior", async () => {
  getEvaluationResult.mockResolvedValue({ molecule_id: COMPLETED.moleculeId, docking_poses: [], vina_version: "1.2.7" });
  const props = { currentFingerprint: "fp-1", requestedTaskId: COMPLETED.taskId, onClose: vi.fn() };
  const { rerender } = render(<CaseRunHistoryModal {...props} runs={[COMPLETED, RERUN_DEEPER]} />);
  await waitFor(() => expect(document.querySelector(`[data-case-run-task="${COMPLETED.taskId}"]`)).toHaveFocus());
  fireEvent.click(screen.getAllByRole("button", { name: /ver resultado/i })[0]);
  await waitFor(() => expect(getEvaluationResult).toHaveBeenCalledWith(RERUN_DEEPER.moleculeId, RERUN_DEEPER.taskId));
  rerender(<CaseRunHistoryModal {...props} runs={[{ ...COMPLETED }, { ...RERUN_DEEPER }]} />);
  const row = document.querySelector(`[data-case-run-task="${RERUN_DEEPER.taskId}"]`) as HTMLElement;
  expect(within(row).getByRole("button", { name: /ocultar/i })).toHaveAttribute("aria-expanded", "true");
});
