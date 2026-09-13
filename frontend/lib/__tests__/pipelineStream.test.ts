// =====================================================================
// Tests del mapeo SSE → orbs (lib/pipelineStream.ts)
// =====================================================================
//
// El backend emite eventos de stage por SSE (registry.py) y el frontend los
// traduce a orbs del PipelineTimeline vía SSE_TO_ORB + stageEventToOrbUpdate.
//
// Tests cubren:
// - cada stage_id conocido mapea a un orb válido del timeline
// - stage_skipped → estado "skipped" con reason (o fallback "no se calculó")
// - stage_error → "error" con mensaje (o fallback "Error en la etapa")
// - stage_start / stage_done → "running" / "done" sin mensaje
// - stages desconocidos o sin orb → null (degradación suave, no crash)
// - pipeline_done/error → null (los maneja el consumidor, no el mapper)
// - los 8 orbs del timeline son todos alcanzables desde el mapa

import { waitFor } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";

import {
  NON_ORB_STAGE_IDS,
  SSE_TO_ORB,
  stageEventToOrbUpdate,
  subscribeToPipelineEvents,
  type PipelineEvent,
} from "../pipelineStream";

vi.mock("../config", () => ({ getApiUrl: async () => "http://127.0.0.1:8123" }));

function event(partial: Partial<PipelineEvent>): PipelineEvent {
  return { timestamp: "2026-08-01T00:00:00Z", ...partial } as PipelineEvent;
}

// Los 8 orbs del PipelineTimeline (DEFAULT_STAGES): validar que el mapa los
// cubre a todos y no produce orbs huérfanos.
const TIMELINE_ORBS = [
  "validation", "properties", "conformer", "vina", "xgb", "clgnn", "openmm", "mmgbsa",
];

describe("SSE_TO_ORB — mapa stage_id → orb", () => {
  it("mapea cada stage_id del pipeline a su orb del DOT", () => {
    expect(SSE_TO_ORB).toEqual({
      validation: "validation",
      properties: "properties",
      conformer: "conformer",
      docking: "vina",
      xgb: "xgb",
      clgnn: "clgnn",
      openmm: "openmm",
      mmgbsa: "mmgbsa",
    });
  });

  it("cubre los 8 orbs del timeline sin orbs huérfanos", () => {
    const mappedOrbs = Object.values(SSE_TO_ORB);
    for (const orb of TIMELINE_ORBS) {
      expect(mappedOrbs).toContain(orb);
    }
    // Cada orb mapeado existe en el timeline (no hay orbs fantasma)
    for (const orb of mappedOrbs) {
      expect(TIMELINE_ORBS).toContain(orb);
    }
  });

  it("docking (stage del backend) apunta al orb vina (DOT)", () => {
    expect(SSE_TO_ORB["docking"]).toBe("vina");
  });

  it("declara los stages válidos sin orb", () => {
    expect(NON_ORB_STAGE_IDS).toEqual(["sa_filter", "selectivity"]);
    expect(SSE_TO_ORB["sa_filter"]).toBeUndefined();
    expect(SSE_TO_ORB["selectivity"]).toBeUndefined();
  });

  // `properties` es la etapa donde corre ADMET-AI (runner.py). Sin orb, sus
  // minutos transcurrían con la línea temporal quieta y el usuario se los
  // atribuía al conformero, que en realidad ya se había generado dentro de
  // esta misma etapa. El orb existe para que ese tiempo tenga dueño.
  it("properties tiene orb propio: su tiempo no se le carga a otra etapa", () => {
    expect(SSE_TO_ORB["properties"]).toBe("properties");
    expect(SSE_TO_ORB["properties"]).not.toBe(SSE_TO_ORB["conformer"]);
    expect(NON_ORB_STAGE_IDS).not.toContain("properties");
  });

  it("un stage_start de properties enciende el orb de properties, no el de 3D ETKDG", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_start", stage_id: "properties" }))).toEqual({
      orb: "properties",
      state: "running",
    });
  });
});

describe("stageEventToOrbUpdate — traducción de eventos", () => {
  it("stage_start → running sin mensaje", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_start", stage_id: "docking" }))).toEqual({
      orb: "vina",
      state: "running",
    });
  });

  it("stage_done → done sin mensaje", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_done", stage_id: "clgnn" }))).toEqual({
      orb: "clgnn",
      state: "done",
    });
  });

  it("stage_error → error con el mensaje del backend", () => {
    expect(
      stageEventToOrbUpdate(event({ type: "stage_error", stage_id: "xgb", error: "Modelo caído" })),
    ).toEqual({ orb: "xgb", state: "error", message: "Modelo caído" });
  });

  it("stage_error sin error → mensaje fallback 'Error en la etapa'", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_error", stage_id: "xgb" }))).toEqual({
      orb: "xgb",
      state: "error",
      message: "Error en la etapa",
    });
  });

  it("stage_skipped → skipped con el reason del backend", () => {
    expect(
      stageEventToOrbUpdate(event({ type: "stage_skipped", stage_id: "openmm", reason: "Etapa no habilitada en la configuración" })),
    ).toEqual({ orb: "openmm", state: "skipped", message: "Etapa no habilitada en la configuración" });
  });

  it("stage_skipped sin reason → mensaje fallback 'no se calculó'", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_skipped", stage_id: "clgnn" }))).toEqual({
      orb: "clgnn",
      state: "skipped",
      message: "no se calculó",
    });
  });

  it("stage_skipped de openmm (default disabled) → orb openmm en skipped", () => {
    const update = stageEventToOrbUpdate(event({ type: "stage_skipped", stage_id: "openmm" }));
    expect(update?.orb).toBe("openmm");
    expect(update?.state).toBe("skipped");
  });

  it("stage desconocido → null (degradación suave, sin crash)", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_start", stage_id: "stage_fantasma" }))).toBeNull();
    expect(stageEventToOrbUpdate(event({ type: "stage_skipped", stage_id: "foo" }))).toBeNull();
  });

  it("stages sin orb (pre-score/Safety Panel) → null", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_done", stage_id: "sa_filter" }))).toBeNull();
    expect(stageEventToOrbUpdate(event({ type: "stage_skipped", stage_id: "selectivity" }))).toBeNull();
  });

  it("evento sin stage_id → null", () => {
    expect(stageEventToOrbUpdate(event({ type: "stage_start" }))).toBeNull();
  });

  it("pipeline_done / pipeline_error → null (los maneja el consumidor)", () => {
    expect(stageEventToOrbUpdate(event({ type: "pipeline_done" }))).toBeNull();
    expect(stageEventToOrbUpdate(event({ type: "pipeline_error", error: "boom" }))).toBeNull();
  });
});

// ── Progreso real de etapa (ensemble conformacional) ─────────────────

describe("stage_progress", () => {
  it("publica el avance CONTADO, no una animación", () => {
    const update = stageEventToOrbUpdate({
      type: "stage_progress",
      stage_id: "docking",
      done: 7,
      total: 30,
      timestamp: "2026-08-25T10:00:00Z",
    });

    expect(update).toEqual({
      orb: SSE_TO_ORB.docking,
      state: "running",
      progress: { done: 7, total: 30 },
    });
  });

  it("sin cifras utilizables se queda en «running» a secas", () => {
    // Una barra que no corresponde a nada es peor que ninguna barra: sugiere
    // que el producto sabe cuánto falta cuando no lo sabe.
    for (const parcial of [
      { done: undefined, total: 30 },
      { done: 7, total: undefined },
      { done: 7, total: 0 },
    ]) {
      const update = stageEventToOrbUpdate({
        type: "stage_progress",
        stage_id: "docking",
        timestamp: "2026-08-25T10:00:00Z",
        ...parcial,
      } as never);
      expect(update).toEqual({ orb: SSE_TO_ORB.docking, state: "running" });
    }
  });

  it("un avance fuera de rango se acota en vez de desbordar la barra", () => {
    const update = stageEventToOrbUpdate({
      type: "stage_progress",
      stage_id: "docking",
      done: 99,
      total: 30,
      timestamp: "2026-08-25T10:00:00Z",
    });
    expect(update?.progress).toEqual({ done: 30, total: 30 });
  });

  it("una etapa sin orbe sigue devolviendo null", () => {
    expect(
      stageEventToOrbUpdate({
        type: "stage_progress",
        stage_id: "sa_filter",
        done: 1,
        total: 2,
        timestamp: "2026-08-25T10:00:00Z",
      }),
    ).toBeNull();
  });
});

describe("transporte SSE autenticado", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("envía el Bearer de la sesión y procesa frames partidos entre chunks", async () => {
    localStorage.setItem("moldesign_auth", JSON.stringify({ token: "token-alice" }));
    const encoder = new TextEncoder();
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"stage_start","stage_id":"dock'));
        controller.enqueue(encoder.encode('ing","timestamp":"t"}\n\ndata: {"type":"pipeline_done","timestamp":"t"}\n\n'));
        controller.close();
      },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
    );
    const events: PipelineEvent[] = [];
    const onClose = vi.fn();

    await subscribeToPipelineEvents("task con espacios", (item) => events.push(item), onClose);

    await waitFor(() => expect(events).toHaveLength(2));
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://127.0.0.1:8123/evaluation/stream/task%20con%20espacios",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer token-alice" }),
      }),
    );
    expect(events[0]).toMatchObject({ type: "stage_start", stage_id: "docking" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("abortar una suscripción desmontada no se reporta como error", async () => {
    let capturedSignal: AbortSignal | undefined;
    vi.spyOn(globalThis, "fetch").mockImplementation(async (_url, init) => {
      capturedSignal = init?.signal ?? undefined;
      return await new Promise<Response>((_resolve, reject) => {
        capturedSignal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    });
    const onClose = vi.fn();
    const unsubscribe = await subscribeToPipelineEvents("task-1", vi.fn(), onClose);

    unsubscribe();

    await waitFor(() => expect(capturedSignal?.aborted).toBe(true));
    expect(onClose).not.toHaveBeenCalled();
  });
});
