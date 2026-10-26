// =====================================================================
// CAS-02 — el SAR puede reconstruir la cohorte histórica de un caso
// =====================================================================
//
// Con 20 moléculas evaluadas como únicas (K=1) y luego reevaluadas en ensemble
// (K=30), la tabla SAR de la corrida única tomaba a los análogos de la
// proyección MÁS RECIENTE de cada molécula —ya ensemble—: K distinto, la API se
// abstenía (correctamente) y quedaban 0 comparables entre 20 filas. El caso sí
// conserva las 20 corridas únicas; faltaba poder pedirlas. El valor por defecto
// no cambia: la cohorte histórica es una alternativa que se elige y se declara.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const getSarData = vi.fn();
vi.mock("../../../../lib/proApi", () => ({
  getSarData: (...args: unknown[]) => getSarData(...args),
}));

import { ProSarTab, cohorteDelProtocolo } from "../ProSarTab";
import type { CaseRun } from "../../../../lib/cases/types";

const UNICA = { dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1 };
const ENSEMBLE = { ...UNICA, conformers: 30 };

function corrida(id: string, protocolo = UNICA, extra: Partial<CaseRun> = {}): CaseRun {
  return {
    taskId: id,
    moleculeId: `mol-${id}`,
    executionState: "completed",
    startedAt: "2026-09-30T10:00:00.000Z",
    ligandSmiles: "CCO",
    protocol: protocolo,
    ...extra,
  };
}

const LIBRO: CaseRun[] = [
  corrida("unica-0"),
  corrida("unica-1"),
  corrida("unica-2"),
  corrida("ens-0", ENSEMBLE),
  corrida("ens-1", ENSEMBLE),
];

const RESPUESTA_RECIENTE = { results: [], cohort: { source: "latest_projection", base_task_id: null, task_ids: null } };

beforeEach(() => {
  getSarData.mockReset().mockResolvedValue(RESPUESTA_RECIENTE);
});
afterEach(cleanup);

describe("cohorteDelProtocolo", () => {
  it("reúne las corridas terminadas del caso con el MISMO protocolo que la de pantalla", () => {
    expect(cohorteDelProtocolo("unica-1", LIBRO)).toEqual({
      taskIds: ["unica-0", "unica-1", "unica-2"],
      k: 1,
    });
    expect(cohorteDelProtocolo("ens-0", LIBRO)).toEqual({ taskIds: ["ens-0", "ens-1"], k: 30 });
  });

  it("no mezcla protocolos distintos aunque sea la misma molécula", () => {
    const resultado = cohorteDelProtocolo("unica-0", LIBRO)!;
    expect(resultado.taskIds.some((id) => id.startsWith("ens"))).toBe(false);
  });

  it("excluye corridas sin terminar, sin resultado guardado o sin protocolo", () => {
    const libro = [
      corrida("a"),
      corrida("b"),
      corrida("fallida", UNICA, { executionState: "failed" }),
      corrida("sin-mol", UNICA, { moleculeId: undefined }),
      { ...corrida("sin-proto"), protocol: undefined },
    ];
    expect(cohorteDelProtocolo("a", libro)?.taskIds).toEqual(["a", "b"]);
  });

  it("con menos de dos no hay alternativa que ofrecer", () => {
    expect(cohorteDelProtocolo("solo", [corrida("solo")])).toBeNull();
  });

  it("sin protocolo registrado en la de referencia no adivina cuál sería «el mismo»", () => {
    const libro = [{ ...corrida("ref"), protocol: undefined }, corrida("x"), corrida("y")];
    expect(cohorteDelProtocolo("ref", libro)).toBeNull();
  });

  it("sin corrida en pantalla o sin libro: nada", () => {
    expect(cohorteDelProtocolo(null, LIBRO)).toBeNull();
    expect(cohorteDelProtocolo("unica-0", undefined)).toBeNull();
    expect(cohorteDelProtocolo("no-esta", LIBRO)).toBeNull();
  });
});

describe("ProSarTab: la cohorte es una alternativa declarada", () => {
  it("por defecto pide la tabla de siempre, sin cohorte, y no ofrece nada si no hay libro", async () => {
    render(<ProSarTab moleculeId="mol-unica-0" taskId="unica-0" />);
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(1));
    expect(getSarData).toHaveBeenCalledWith("mol-unica-0", undefined);
    expect(screen.queryByRole("group", { name: /Qué moléculas entran/i })).not.toBeInTheDocument();
  });

  it("con un libro que ofrece cohorte histórica, muestra la elección y arranca en lo de siempre", async () => {
    render(<ProSarTab moleculeId="mol-unica-0" taskId="unica-0" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenCalled());
    expect(screen.getByRole("group", { name: /Qué moléculas entran/i })).toBeInTheDocument();
    expect(getSarData).toHaveBeenLastCalledWith("mol-unica-0", undefined);
    const reciente = screen.getByRole("radio", { name: /evaluación más reciente de cada molécula/i });
    expect(reciente).toBeChecked();
    expect(screen.getByRole("radio", { name: /3 corridas de este caso con el mismo protocolo.*K=1/i })).not.toBeChecked();
  });

  it("elegir la cohorte histórica pide la base y las corridas EXPLÍCITAS, y lo declara", async () => {
    getSarData.mockResolvedValueOnce(RESPUESTA_RECIENTE).mockResolvedValueOnce({
      results: [],
      cohort: { source: "explicit_runs", base_task_id: "unica-0", task_ids: ["unica-0", "unica-1", "unica-2"] },
    });
    render(<ProSarTab moleculeId="mol-unica-0" taskId="unica-0" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole("radio", { name: /3 corridas de este caso/i }));

    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(2));
    expect(getSarData).toHaveBeenLastCalledWith("mol-unica-0", {
      taskId: "unica-0",
      cohortTaskIds: ["unica-0", "unica-1", "unica-2"],
    });
    expect(await screen.findByText(/Tabla construida sobre 3 corridas concretas/)).toBeInTheDocument();
  });

  it("volver a «más reciente» deja la tabla de siempre", async () => {
    render(<ProSarTab moleculeId="mol-unica-0" taskId="unica-0" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("radio", { name: /3 corridas de este caso/i }));
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("radio", { name: /evaluación más reciente/i }));
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(3));
    expect(getSarData).toHaveBeenLastCalledWith("mol-unica-0", undefined);
  });

  it("si el servidor rechaza la cohorte, el motivo se DICE; no cae a una tabla vacía muda", async () => {
    getSarData
      .mockResolvedValueOnce(RESPUESTA_RECIENTE)
      .mockRejectedValueOnce(new Error("La corrida unica-2 no terminó con éxito (FAILURE)."));
    render(<ProSarTab moleculeId="mol-unica-0" taskId="unica-0" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("radio", { name: /3 corridas de este caso/i }));
    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("No se pudo construir la tabla con esa cohorte");
    expect(aviso).toHaveTextContent("unica-2 no terminó con éxito");
  });

  it("un rechazo de la tabla por defecto NO inventa un aviso de cohorte", async () => {
    getSarData.mockRejectedValue(new Error("Molecule not found"));
    render(<ProSarTab moleculeId="mol-x" taskId="unica-0" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("si la corrida en pantalla cambia y la cohorte deja de existir, vuelve al valor por defecto", async () => {
    const { rerender } = render(<ProSarTab moleculeId="mol-unica-0" taskId="unica-0" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("radio", { name: /3 corridas de este caso/i }));
    await waitFor(() => expect(getSarData).toHaveBeenCalledTimes(2));
    rerender(<ProSarTab moleculeId="mol-nueva" taskId="otra" caseRuns={LIBRO} />);
    await waitFor(() => expect(getSarData).toHaveBeenLastCalledWith("mol-nueva", undefined));
    expect(screen.queryByRole("group", { name: /Qué moléculas entran/i })).not.toBeInTheDocument();
  });
});
