// =====================================================================
// Tests de la cola de guardado — el orden importa y nada se pierde
// =====================================================================
//
// Todo aquí usa un repositorio ARTIFICIALMENTE LENTO y controlado a mano. Sin
// poder decidir cuándo resuelve cada escritura no se puede provocar el caso que
// importa: dos respuestas que llegan fuera de orden.
//
// Cubre los cinco escenarios pedidos:
//   · editar A → cambiar a B antes del debounce (drain)
//   · dos guardados que terminan fuera de orden
//   · crear un caso durante un guardado
//   · fallo de escritura y reintento
//   · archivar mientras existe un cambio pendiente

import { describe, expect, it, vi } from "vitest";

import { CaseSaveQueue, type SaveOutcome } from "../saveQueue";
import { createCaseRecord } from "../schema";
import type { CaseRecord } from "../types";

function record(id: string, question?: string): CaseRecord {
  const base = createCaseRecord({
    ownerUserId: "test-owner",
    name: `Caso ${id}`,
    studyKind: "explore-hypothesis",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    id,
    now: "2026-08-23T12:00:00.000Z",
  });
  return question ? { ...base, context: { ...base.context, question } } : base;
}

/** Escritor controlado: cada llamada queda pendiente hasta que se la resuelve. */
function controlledWriter() {
  const calls: Array<{
    record: CaseRecord;
    resolve: (value: CaseRecord) => void;
    reject: (error: unknown) => void;
  }> = [];
  const write = vi.fn(
    (r: CaseRecord) =>
      new Promise<CaseRecord>((resolve, reject) => {
        calls.push({ record: r, resolve, reject });
      }),
  );
  return { write, calls };
}

function makeQueue(write: (r: CaseRecord) => Promise<CaseRecord>) {
  const outcomes: Array<{ caseId: string; outcome: SaveOutcome }> = [];
  const queue = new CaseSaveQueue({
    write,
    // Debounce 0: los tests controlan el tiempo con el escritor, no con timers.
    delayMs: 0,
    onOutcome: (caseId, outcome) => outcomes.push({ caseId, outcome }),
  });
  return { queue, outcomes };
}

describe("cola serializada por caso", () => {
  it("no mezcla las colas de dos casos distintos", async () => {
    const { write, calls } = controlledWriter();
    const { queue } = makeQueue(write);

    queue.enqueue(record("a", "de A"));
    queue.enqueue(record("b", "de B"));
    await vi.waitFor(() => expect(calls).toHaveLength(2));

    // Cada escritura lleva el registro de SU caso.
    expect(calls.map((c) => c.record.id).sort()).toEqual(["a", "b"]);
  });

  it("editar A y cambiar a B antes del debounce: el drenaje escribe A primero", async () => {
    const { write, calls } = controlledWriter();
    const { queue } = makeQueue(write);

    queue.enqueue(record("a", "borrador de A"));
    // `drain` es lo que llama el contexto ANTES de cambiar de caso.
    const drained = queue.drain("a");
    await vi.waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0].record.context.question).toBe("borrador de A");

    calls[0].resolve(calls[0].record);
    await drained;
    // Y ya no queda nada pendiente de A: el borrador no se perdió ni quedó
    // colgando para escribirse después de haber cambiado de caso.
    expect(queue.hasPending("a")).toBe(false);
  });
});

describe("respuestas fuera de orden", () => {
  it("una respuesta vieja NO reemplaza estado más reciente", async () => {
    const { write, calls } = controlledWriter();
    const { queue, outcomes } = makeQueue(write);

    // Primera edición: entra en vuelo.
    queue.enqueue(record("a", "primera"));
    await vi.waitFor(() => expect(calls).toHaveLength(1));

    // El usuario SIGUE ESCRIBIENDO mientras la primera escritura está en vuelo.
    queue.enqueue(record("a", "segunda"));

    // Ahora responde la PRIMERA, que ya está obsoleta.
    calls[0].resolve(calls[0].record);
    await vi.waitFor(() => expect(outcomes).toHaveLength(1));
    // Se descarta. Aplicarla habría devuelto la pantalla a "primera" después de
    // que el usuario ya había escrito "segunda".
    expect(outcomes[0].outcome.kind).toBe("superseded");

    // Y la segunda sí se aplica cuando termina.
    await vi.waitFor(() => expect(calls).toHaveLength(2));
    calls[1].resolve(calls[1].record);
    await vi.waitFor(() => expect(outcomes).toHaveLength(2));
    const saved = outcomes[1].outcome;
    expect(saved.kind).toBe("saved");
    expect(saved.kind === "saved" ? saved.record.context.question : null).toBe("segunda");
  });

  it("las escrituras de un mismo caso NO se solapan: la cola las serializa", async () => {
    const { write, calls } = controlledWriter();
    const { queue } = makeQueue(write);

    queue.enqueue(record("a", "1"));
    await vi.waitFor(() => expect(calls).toHaveLength(1));
    queue.enqueue(record("a", "2"));

    // La segunda no arranca hasta que la primera termina: dos escrituras
    // concurrentes sobre el mismo `case.json` podrían intercalarse en disco.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(calls).toHaveLength(1);

    calls[0].resolve(calls[0].record);
    await vi.waitFor(() => expect(calls).toHaveLength(2));
  });

  it("la revisión es monótona y creciente por caso", () => {
    const { write } = controlledWriter();
    const { queue } = makeQueue(write);
    const r1 = queue.enqueue(record("a", "1"));
    const r2 = queue.enqueue(record("a", "2"));
    const r3 = queue.enqueue(record("a", "3"));
    expect(r2).toBeGreaterThan(r1);
    expect(r3).toBeGreaterThan(r2);
    // Otro caso lleva su propio contador.
    expect(queue.enqueue(record("b", "1"))).toBe(1);
  });
});

describe("crear un caso durante un guardado", () => {
  it("el guardado en vuelo termina y el caso nuevo tiene su propia cola", async () => {
    const { write, calls } = controlledWriter();
    const { queue, outcomes } = makeQueue(write);

    queue.enqueue(record("a", "en vuelo"));
    await vi.waitFor(() => expect(calls).toHaveLength(1));

    // Mientras A está escribiéndose, se crea B y se edita.
    queue.enqueue(record("b", "caso nuevo"));
    await vi.waitFor(() => expect(calls).toHaveLength(2));

    // Los dos terminan; ninguno pisa al otro.
    calls[0].resolve(calls[0].record);
    calls[1].resolve(calls[1].record);
    await vi.waitFor(() => expect(outcomes).toHaveLength(2));

    expect(outcomes.every((o) => o.outcome.kind === "saved")).toBe(true);
    expect(outcomes.map((o) => o.caseId).sort()).toEqual(["a", "b"]);
  });
});

describe("fallo de escritura", () => {
  it("conserva el cambio pendiente y permite reintentar", async () => {
    const { write, calls } = controlledWriter();
    const { queue, outcomes } = makeQueue(write);

    queue.enqueue(record("a", "texto valioso"));
    await vi.waitFor(() => expect(calls).toHaveLength(1));
    calls[0].reject(new Error("disco lleno"));

    await vi.waitFor(() =>
      expect(outcomes.some((o) => o.outcome.kind === "failed")).toBe(true),
    );
    // EL CAMBIO NO SE HA PERDIDO. Antes se descartaba y el usuario veía "Error"
    // con su texto ya inexistente.
    expect(queue.hasPending("a")).toBe(true);
    expect((queue.lastError("a") as Error).message).toBe("disco lleno");

    // Reintento: se vuelve a intentar EL MISMO registro.
    const retried = queue.retry("a");
    await vi.waitFor(() => expect(calls).toHaveLength(2));
    expect(calls[1].record.context.question).toBe("texto valioso");
    calls[1].resolve(calls[1].record);
    await retried;
    expect(queue.hasPending("a")).toBe(false);
  });

  it("un cambio más nuevo durante el fallo tiene prioridad sobre el reintento", async () => {
    const { write, calls } = controlledWriter();
    const { queue } = makeQueue(write);

    queue.enqueue(record("a", "viejo"));
    await vi.waitFor(() => expect(calls).toHaveLength(1));
    // El usuario sigue escribiendo mientras la escritura está en vuelo.
    queue.enqueue(record("a", "nuevo"));
    calls[0].reject(new Error("falló"));

    await vi.waitFor(() => expect(calls.length).toBeGreaterThanOrEqual(2));
    // Lo que se reintenta es lo NUEVO: restaurar lo viejo encima sería
    // retroceder el texto del usuario.
    const last = calls[calls.length - 1];
    expect(last.record.context.question).toBe("nuevo");
  });
});

describe("archivar con un cambio pendiente", () => {
  it("`drain` fuerza la escritura pendiente antes de continuar", async () => {
    const { write, calls } = controlledWriter();
    const { queue } = makeQueue(write);

    queue.enqueue(record("a", "sin guardar todavía"));
    // Esto es lo que hace `setArchived` en el contexto: drena ANTES de archivar.
    const drained = queue.drain("a");
    await vi.waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0].record.context.question).toBe("sin guardar todavía");

    calls[0].resolve(calls[0].record);
    await drained;
    // Si archivar no drenara, la lectura que hace `setArchived` traería el
    // registro SIN la edición y la sobrescribiría al escribir.
    expect(queue.hasPending("a")).toBe(false);
  });

  it("`drainAll` vacía todas las colas", async () => {
    const { write, calls } = controlledWriter();
    const { queue } = makeQueue(write);
    queue.enqueue(record("a", "A"));
    queue.enqueue(record("b", "B"));

    const drained = queue.drainAll();
    await vi.waitFor(() => expect(calls).toHaveLength(2));
    calls.forEach((c) => c.resolve(c.record));
    await drained;

    expect(queue.hasPending("a")).toBe(false);
    expect(queue.hasPending("b")).toBe(false);
  });
});
