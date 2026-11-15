// =====================================================================
// SAR: la molécula de referencia no es un análogo de sí misma
// =====================================================================
//
// Desde S1-3.3 el backend entrega siempre la referencia primera, con `is_base`, y detrás las comparaciones. Medido en la
// pantalla real (cápsula de QA, 6 evaluaciones de Vina contra 8HFI), la tabla tenía dos defectos:
// 1. el Δ de la referencia («0.0») salía en rosa, el color de «peor que la base»;
// 2. el contador decía «6 análogos» y contaba la propia referencia y dos moléculas que la misma pantalla plegaba como
//    «no son análogos».
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const getSarData = vi.fn();
vi.mock("../../../../lib/proApi", () => ({
  getSarData: (...args: unknown[]) => getSarData(...args),
  getRunPoseComparison: vi.fn(),
  getAnalogPoseComparison: vi.fn(),
}));

import { ProSarTab, claseDelta, mapSarAnalog } from "../ProSarTab";
import type { CaseRun } from "../../../../lib/cases/types";

const CAMBIO = { core_heavy_atoms: 20, base_heavy_atoms: 20, analog_heavy_atoms: 21, formula_delta: [], core_complete: true };

const fila = (id: string, similarity: number, delta: number | null, extra: Record<string, unknown> = {}) => ({
  molecule_id: id, task_id: `run-${id}`, name: `Mol ${id}`, smiles: `C${id}`, similarity, delta_score: null, delta_affinity: delta,
  comparison_state: "descriptive", highlight: "", structural_change: CAMBIO, qed: 0.9, lipinski_pass: true, ...extra,
});
// La referencia, tal como la entrega el backend: Tanimoto 1 contra sí misma, Δ 0 y la propia corrida.
const referencia = (extra: Record<string, unknown> = {}) =>
  fila("base", 1, 0, { is_base: true, task_id: "t1", name: "Mol base", ...extra });

const corrida = (taskId: string): CaseRun => ({
  taskId, moleculeId: "mol-base", executionState: "completed", startedAt: "2026-11-01T10:00:00.000Z",
  protocol: { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 },
});

const montar = () => render(<ProSarTab moleculeId="mol-base" taskId="t1" caseRuns={[corrida("t1")]} />);

beforeEach(() => {
  getSarData.mockReset().mockResolvedValue({
    results: [
      referencia(),
      fila("cercano", 0.611, 0.6),
      fila("medio", 0.489, 0.3),
      fila("lejano", 0.261, -0.1),
      fila("ajeno", 0.128, 1.2),
    ],
    cohort: { source: "latest_projection", base_task_id: null, task_ids: null },
  });
});
afterEach(cleanup);

describe("la fila de referencia", () => {
  it("sale primera y dice que es la referencia, no un «0.0» frente a sí misma", async () => {
    montar();
    await screen.findByText("Mol base");
    const nombres = screen.getAllByText(/^Mol (base|cercano|medio)$/).map((n) => n.textContent);
    expect(nombres).toEqual(["Mol base", "Mol cercano", "Mol medio"]);
    const filaBase = screen.getByText("Mol base").closest("div.cursor-pointer") as HTMLElement;
    expect(within(filaBase).getByText("Referencia")).toBeInTheDocument();
    expect(within(filaBase).queryByText("0.0")).toBeNull();
    expect(within(filaBase).queryByText("Δ afinidad vs. base")).toBeNull();
  });

  it("va primera aunque el backend la entregue en otra posición", async () => {
    getSarData.mockResolvedValue({ results: [fila("cercano", 0.611, 0.6), referencia(), fila("medio", 0.489, 0.3)] });
    montar();
    await screen.findByText("Mol base");
    const nombres = screen.getAllByText(/^Mol (base|cercano|medio)$/).map((n) => n.textContent);
    expect(nombres).toEqual(["Mol base", "Mol cercano", "Mol medio"]);
  });

  it("no se pliega entre «las otras» aunque no tenga similitud medible", async () => {
    getSarData.mockResolvedValue({ results: [referencia({ similarity: null }), fila("cercano", 0.611, 0.6)] });
    montar();
    await screen.findByText("Mol base");
    expect(screen.queryByText(/similitud menor de/)).toBeNull();
    expect(screen.getByText("Mol base").closest("details")).toBeNull();
  });

  it("su ficha dice «Referencia» y no inventa un delta contra sí misma", async () => {
    montar();
    fireEvent.click(await screen.findByText("Mol base"));
    expect(screen.queryByText(/kcal\/mol/)).toBeNull();
    const ficha = screen.getByRole("heading", { name: "Mol base" }).closest("div.space-y-4") as HTMLElement;
    const celda = within(ficha).getByText("Referencia");
    expect(celda.className).toContain("text-zinc-400");
    expect(celda.className).not.toContain("text-rose-400");
  });

  it("el adaptador la marca solo cuando el backend dice is_base: true", () => {
    expect(mapSarAnalog({ is_base: true, smiles: "C" }, 0).isBase).toBe(true);
    expect(mapSarAnalog({ is_base: false, smiles: "C" }, 0).isBase).toBe(false);
    expect(mapSarAnalog({ smiles: "C" }, 0).isBase).toBe(false);
    expect(mapSarAnalog({ is_base: "true", smiles: "C" }, 0).isBase).toBe(false);
  });
});

describe("el contador", () => {
  it("cuenta los análogos que la tabla presenta como tales: ni la referencia ni lo que pliega como «no son análogos»", async () => {
    montar();
    await screen.findByText("Mol base");
    // Referencia + 2 por encima del umbral + 2 plegadas = 5 filas; análogos presentados: 2.
    expect(screen.getByText("2 análogos")).toBeInTheDocument();
    const plegado = screen.getByText(/similitud menor de 40 %/).closest("details")!;
    expect(within(plegado).getByText("Mol lejano")).toBeInTheDocument();
    expect(within(plegado).getByText("Mol ajeno")).toBeInTheDocument();
    expect(within(plegado).queryByText("Mol base")).toBeNull();
  });

  it("con la referencia sola no hay análogos: lo dice, en vez de una tabla de una fila que se cuenta a sí misma", async () => {
    getSarData.mockResolvedValue({ results: [referencia()] });
    montar();
    expect(await screen.findByText(/Sin análogos disponibles aún/)).toBeInTheDocument();
    expect(screen.getByText("0 análogos")).toBeInTheDocument();
    expect(screen.queryByText("Mol base")).toBeNull();
  });

  it("sin la marca is_base (cohorte antigua o respuesta vieja) cuenta como antes", async () => {
    getSarData.mockResolvedValue({ results: [fila("cercano", 0.611, 0.6), fila("medio", 0.489, 0.3)] });
    montar();
    await screen.findByText("Mol cercano");
    expect(screen.getByText("2 análogos")).toBeInTheDocument();
  });
});

describe("el color del Δ de afinidad", () => {
  it("un cero no es «peor que la base»: va en neutro", () => {
    expect(claseDelta(0)).toBe("text-zinc-300");
    expect(claseDelta(-0)).toBe("text-zinc-300");
  });

  it("negativo en verde, positivo en rosa y sin delta en gris", () => {
    expect(claseDelta(-0.5)).toBe("text-emerald-400");
    expect(claseDelta(0.6)).toBe("text-rose-400");
    expect(claseDelta(null)).toBe("text-zinc-400");
  });

  it("una comparación real con delta exactamente cero se pinta en neutro, no en rosa", async () => {
    getSarData.mockResolvedValue({ results: [referencia(), fila("gemelo", 0.7, 0)] });
    montar();
    await screen.findByText("Mol gemelo");
    const delta = within(screen.getByText("Mol gemelo").closest("div.cursor-pointer") as HTMLElement).getByText("0.0");
    expect(delta.className).toContain("text-zinc-300");
    expect(delta.className).not.toContain("text-rose-400");
  });

  it("las comparaciones con delta siguen igual: +0.6 rosa, −0.5 verde", async () => {
    getSarData.mockResolvedValue({ results: [referencia(), fila("peor", 0.7, 0.6), fila("mejor", 0.6, -0.5)] });
    montar();
    await screen.findByText("Mol peor");
    expect(screen.getByText("+0.6").className).toContain("text-rose-400");
    expect(screen.getByText("-0.5").className).toContain("text-emerald-400");
  });
});
