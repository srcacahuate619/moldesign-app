import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:9999" }));

import { getSarData } from "../proApi";

// CAS-02. La consulta SAR por defecto no cambia; con cohorte lleva la corrida
// base y CADA corrida de la cohorte como parámetro repetido.
describe("getSarData: la consulta SAR", () => {
  const respuesta = () =>
    new Response(JSON.stringify({ results: [] }), { status: 200, headers: { "Content-Type": "application/json" } });

  beforeEach(() => {
    window.localStorage.clear();
    vi.restoreAllMocks();
  });

  it("sin cohorte pide exactamente /sar/{id}, como siempre", async () => {
    const fetchSpy = vi.fn(async (..._args: unknown[]) => respuesta());
    global.fetch = fetchSpy as typeof fetch;
    await getSarData("mol-1");
    expect(fetchSpy.mock.calls[0][0]).toBe("http://127.0.0.1:9999/sar/mol-1");
  });

  it("con cohorte lleva task_id y un cohort_task_ids por corrida", async () => {
    const fetchSpy = vi.fn(async (..._args: unknown[]) => respuesta());
    global.fetch = fetchSpy as typeof fetch;
    await getSarData("mol-1", { taskId: "unica-0", cohortTaskIds: ["unica-0", "unica-1"] });
    const url = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(url.pathname).toBe("/sar/mol-1");
    expect(url.searchParams.get("task_id")).toBe("unica-0");
    expect(url.searchParams.getAll("cohort_task_ids")).toEqual(["unica-0", "unica-1"]);
  });

  it("los identificadores se codifican: un task_id con caracteres especiales no rompe la consulta", async () => {
    const fetchSpy = vi.fn(async (..._args: unknown[]) => respuesta());
    global.fetch = fetchSpy as typeof fetch;
    await getSarData("mol-1", { taskId: "a&b=c", cohortTaskIds: ["a&b=c"] });
    const url = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(url.searchParams.get("task_id")).toBe("a&b=c");
    expect(url.searchParams.getAll("cohort_task_ids")).toEqual(["a&b=c"]);
  });
});
