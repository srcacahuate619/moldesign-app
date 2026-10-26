import { beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("../backendFetch", () => ({ fetchBackend: (...args: unknown[]) => request(...args) }));
const request = vi.hoisted(() => vi.fn());
import { getInteractions, getProteinFile } from "../api";
import { dockSingleAntiTarget, runAdmet, saveSelectivityResults } from "../proApi";

beforeEach(() => {
  request.mockReset().mockImplementation(async () => new Response(JSON.stringify({ task_id: "run A/1", success: true }), { status: 200 }));
});
const url = (index: number) => new URL(request.mock.calls[index][0], "http://localhost");

describe("recursos y acciones usan la identidad seleccionada", () => {
  it("receptor y contactos codifican la corrida y conservan la pose pedida", async () => {
    await getProteinFile("mol", "run A/1");
    await getInteractions("mol", 3, "run A/1");
    expect(url(0).pathname).toBe("/evaluation/files/protein/mol");
    expect(url(0).searchParams.get("task_id")).toBe("run A/1");
    expect(url(1).searchParams.get("task_id")).toBe("run A/1");
    expect(url(1).searchParams.get("pose_rank")).toBe("3");
  });

  it("las firmas previas mantienen las peticiones sin task_id", async () => {
    await getProteinFile("mol"); await getInteractions("mol");
    expect(url(0).searchParams.has("task_id")).toBe(false);
    expect(url(1).searchParams.has("task_id")).toBe(false);
    expect(url(1).searchParams.get("pose_rank")).toBe("1");
  });

  it("calcular y guardar selectividad envían la misma identidad", async () => {
    await dockSingleAntiTarget("mol", "5VA1", "run A/1");
    await saveSelectivityResults("mol", { task_id: "run A/1", off_targets: [] });
    expect(url(0).searchParams.get("task_id")).toBe("run A/1");
    expect(url(0).searchParams.get("target_pdb_id")).toBe("5VA1");
    expect(JSON.parse(request.mock.calls[1][1].body)).toEqual({ task_id: "run A/1", off_targets: [] });
  });

  it("ADMET incluye corrida y opción de recalcular sin cambiar clientes anteriores", async () => {
    await runAdmet("mol", { taskId: "run A/1", recalcular: true });
    await runAdmet("mol");
    expect(url(0).searchParams.get("task_id")).toBe("run A/1");
    expect(url(0).searchParams.get("recalcular")).toBe("true");
    expect(url(1).search).toBe("");
  });
});
