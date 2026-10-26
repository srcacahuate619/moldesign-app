// =====================================================================
// Una decisión de Preparación no la pisa el autoguardado de Evaluación
// =====================================================================
//
// Preparación lee los casos en sólo lectura con su propio repositorio, y
// Evaluación tiene el caso activo EN MEMORIA y lo autoguarda entero. Escribir la
// decisión por fuera del caso que Evaluación tiene abierto la perdía en el
// siguiente autoguardado, sin aviso: el modo de fallo que `lib/decisionesDeCaso.ts`
// existe para impedir.
//
// Aquí se fija que el `CaseProvider` se registra como escritor, que sólo acepta SU
// caso activo, y que la decisión queda en disco.

import { describe, expect, it, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

import { CaseProvider, useCases } from "../CaseContext";
import { createBrowserCaseRepository } from "../../lib/cases/browserCaseRepository";
import type { CaseRepository } from "../../lib/cases/repository";
import { anotarDecision, conDecision } from "../../lib/decisionesDeCaso";
import type { CaseRecord } from "../../lib/cases/types";

function wrapper(repository: CaseRepository) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <CaseProvider repository={repository} autosaveDelayMs={0}>
        {children}
      </CaseProvider>
    );
  };
}

const DECISION = {
  controlCode: "preparacion:ligando.covalente",
  fingerprint: "tarea:task-1",
  note: "Se calcula el complejo no covalente previo.",
};

async function montarConCaso(repository: CaseRepository, nombre: string) {
  const { result } = renderHook(() => useCases(), { wrapper: wrapper(repository) });
  await waitFor(() => expect(result.current.loading).toBe(false));
  await act(async () => {
    await result.current.createCase(nombre, "explore-hypothesis");
  });
  return { result, id: result.current.activeCase!.id };
}

describe("decisiones de Preparación sobre el caso", () => {
  beforeEach(() => window.localStorage.clear());

  it("una decisión por control y huella: repetirla sustituye la nota", () => {
    const base = { id: "c", decisions: [] } as unknown as CaseRecord;
    const una = conDecision(base, DECISION, "2026-10-10T20:00:00.000Z");
    const otra = conDecision(una, { ...DECISION, note: "Mejor dicho." }, "2026-10-10T21:00:00.000Z");
    expect(otra.decisions).toHaveLength(1);
    expect(otra.decisions?.[0].note).toBe("Mejor dicho.");
    const distinta = conDecision(otra, { ...DECISION, fingerprint: "tarea:task-2" });
    expect(distinta.decisions).toHaveLength(2);
  });

  it("con el caso abierto en Evaluación, escribe el proveedor y queda en disco", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const { result, id } = await montarConCaso(repository, "Abierto");

    await act(async () => {
      await anotarDecision(repository, id, DECISION);
    });

    // En la copia en memoria de Evaluación…
    expect(result.current.activeCase?.decisions?.[0].note).toBe(DECISION.note);
    expect(result.current.saveState).toBe("saved");
    // …y en disco, que es lo que vuelve a leer Preparación.
    expect((await repository.readCase(id)).decisions?.[0].controlCode).toBe(DECISION.controlCode);
  });

  it("un cambio posterior de Evaluación no borra la decisión", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const { result, id } = await montarConCaso(repository, "Con corrida");

    await act(async () => {
      await anotarDecision(repository, id, DECISION);
    });
    act(() => result.current.setInputs({ ligand: { inputSmiles: "CCO" } }));
    await waitFor(() => expect(result.current.saveState).toBe("saved"));

    const guardado = await repository.readCase(id);
    expect(guardado.decisions?.[0].note).toBe(DECISION.note);
    expect(guardado.inputs?.ligand?.inputSmiles).toBe("CCO");
  });

  it("si el caso no es el activo, se escribe por el repositorio", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const { result, id } = await montarConCaso(repository, "Primero");
    // Evaluación pasa a otro caso: el primero ya no está en memoria.
    await act(async () => {
      await result.current.createCase("Segundo", "explore-hypothesis");
    });

    await act(async () => {
      await anotarDecision(repository, id, DECISION);
    });

    expect((await repository.readCase(id)).decisions?.[0].note).toBe(DECISION.note);
    // El caso activo no se contamina con la decisión del otro.
    expect(result.current.activeCase?.decisions ?? []).toEqual([]);
  });

  it("sin ningún proveedor montado, también se escribe", async () => {
    const repository = createBrowserCaseRepository("test-owner");
    const creado = await repository.createCase({ name: "Suelto", studyKind: "explore-hypothesis" });

    await anotarDecision(repository, creado.id, DECISION);

    expect((await repository.readCase(creado.id)).decisions?.[0].note).toBe(DECISION.note);
  });
});
