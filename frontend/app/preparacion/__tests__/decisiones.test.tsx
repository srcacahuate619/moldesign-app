// =====================================================================
// Preparación registra la decisión del investigador en el caso
// =====================================================================
//
// Lo que se decide no es un estado nuevo: es una justificación escrita junto al
// requisito, sobre una corrida concreta. Aquí se fija:
//
//   1. se puede decidir sobre lo que está abierto, no sobre lo que ya tiene dato;
//   2. la justificación va al caso con el código y la huella que dice el backend,
//      y el caso vuelve a auditarse con ella;
//   3. sin justificación no se guarda nada;
//   4. una decisión ya registrada se enseña, y sobre un bloqueo dice que no lo levanta;
//   5. si Evaluación tiene el caso abierto, escribe ella (lib/decisionesDeCaso.ts):
//      escrito por fuera, su autoguardado lo borraría.

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";
import {
  olvidarEscritorDeDecisiones,
  registrarEscritorDeDecisiones,
} from "@/lib/decisionesDeCaso";

const mocks = vi.hoisted(() => ({
  locale: "es" as "es" | "en",
  read: vi.fn(),
  update: vi.fn(),
  request: vi.fn(),
  list: vi.fn(),
}));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
const repository = { listCases: mocks.list, readCase: mocks.read, updateCase: mocks.update };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t: (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key }) };
});
import PreparacionPage from "../page";

const HUELLA = "tarea:exact";

function auditoria(extra: Partial<AuditoriaPreparacion> = {}, decision?: unknown): AuditoriaPreparacion {
  return {
    schema: "preparacion/v1", estado: "REVISION", razon: "cause", alcance: "scope",
    transferencia_fep_demostrada: false, bloqueantes: [], en_revision: ["ligando.covalente"],
    huella_de_decision: HUELLA, corrida: { task_id: "exact" },
    bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({
      id, estado: id === "ligando" ? "REVISION" : "REGISTRADO",
      requisitos: id === "ligando" ? [
        {
          clave: "ligando.covalente", estado: "REVISAR", imprescindible: false, etiqueta: "Unión covalente",
          valor: "Ojiva: acrilamida (aceptor de Michael).", valor_es_clasificacion: true,
          razon: "Vina acopla el complejo no covalente.", fuente: "f",
          ...(decision ? { decision } : {}),
        },
        {
          clave: "ligando.identidad", estado: "REGISTRADO", imprescindible: true, etiqueta: "Ligando acoplado",
          valor: "CC(=O)O", valor_es_clasificacion: false, razon: null, fuente: "f",
        },
      ] : [],
    })),
    paquete: { rotulo: "package", aviso: "limit" },
    ...extra,
  } as unknown as AuditoriaPreparacion;
}

const CASO = {
  id: "case", name: "Caso", context: {}, runs: [],
  activeRun: { taskId: "exact", moleculeId: "molecule", executionState: "completed" },
} as unknown as CaseRecord;

async function abrir(a: AuditoriaPreparacion = auditoria()) {
  mocks.locale = "es";
  mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
  mocks.read.mockResolvedValue(CASO);
  mocks.update.mockImplementation(async (record: CaseRecord) => record);
  mocks.request.mockResolvedValue(a);
  render(<PreparacionPage />);
  fireEvent.change(await screen.findByRole("combobox"), { target: { value: "case" } });
  fireEvent.click(await screen.findByRole("button", { name: /Estado químico/ }));
  return screen.findByText("Ojiva: acrilamida (aceptor de Michael).");
}

/** El <li> del requisito, para no confundir sus controles con los de otro. */
function fila(valor: string) {
  const texto = screen.getByText(valor);
  const item = texto.closest("li");
  if (!item) throw new Error("sin fila");
  return within(item);
}

afterEach(() => {
  olvidarEscritorDeDecisiones();
  vi.clearAllMocks();
});

describe("Preparación: decisiones del investigador", () => {
  it("ofrece decidir sobre lo que está abierto y no sobre lo que ya tiene dato", async () => {
    await abrir();
    expect(fila("Ojiva: acrilamida (aceptor de Michael).").getByRole("button", { name: "Asumir esta incertidumbre" }))
      .toBeInTheDocument();
    expect(fila("CC(=O)O").queryByRole("button", { name: /Asumir|Dejar escrita/ })).toBeNull();
  });

  it("escribe la justificación en el caso con el código y la huella del backend", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Asumir esta incertidumbre" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Justificación/ }), {
      target: { value: "Se calcula el complejo no covalente previo." },
    });
    // La reauditoría del caso guardado: ahora con la decisión.
    mocks.request.mockResolvedValue(auditoria(
      { en_revision: [], decididos: ["ligando.covalente"] },
      { justificacion: "Se calcula el complejo no covalente previo.", registrada: "2026-10-10T21:00:00Z", resuelve: true },
    ));
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));

    await waitFor(() => expect(mocks.update).toHaveBeenCalledTimes(1));
    const guardado = mocks.update.mock.calls[0][0] as CaseRecord;
    expect(guardado.decisions).toEqual([{
      controlCode: "preparacion:ligando.covalente",
      fingerprint: HUELLA,
      decision: "reconocida",
      at: expect.any(String),
      note: "Se calcula el complejo no covalente previo.",
    }]);
    // Y el caso guardado se vuelve a auditar: la decisión viaja en la proyección.
    expect(await screen.findByText("Se calcula el complejo no covalente previo.")).toBeInTheDocument();
    expect(screen.getByText("Decisión del investigador", { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Asumir esta incertidumbre" })).toBeNull();
  });

  it("sin justificación no guarda nada y lo dice", async () => {
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Asumir esta incertidumbre" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Justificación/ }), { target: { value: " " } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Escribe una justificación breve.");
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("sobre un bloqueante se registra, y la pantalla dice que no lo levanta", async () => {
    await abrir(auditoria(
      { estado: "BLOQUEADO", bloqueantes: ["ligando.covalente"], en_revision: [] },
      { justificacion: "El aducto se calcula aparte.", registrada: null, resuelve: false },
    ));
    const item = fila("Ojiva: acrilamida (aceptor de Michael).");
    expect(item.getByText("El aducto se calcula aparte.")).toBeInTheDocument();
    expect(item.getByText("Queda registrada; el bloqueo sigue.")).toBeInTheDocument();
  });

  it("el botón dice que un bloqueo no se levanta antes de escribir nada", async () => {
    await abrir(auditoria({ estado: "BLOQUEADO", bloqueantes: ["ligando.covalente"], en_revision: [] }));
    expect(screen.getByRole("button", { name: "Dejar escrita una decisión (no levanta el bloqueo)" }))
      .toBeInTheDocument();
  });

  it("si Evaluación tiene el caso abierto, escribe ella y no se toca el repositorio", async () => {
    const escritas: unknown[] = [];
    registrarEscritorDeDecisiones(async (casoId, decision) => {
      if (casoId !== "case") return false;
      escritas.push(decision);
      return true;
    });
    await abrir();
    fireEvent.click(screen.getByRole("button", { name: "Asumir esta incertidumbre" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Justificación/ }), { target: { value: "Decidido." } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));

    await waitFor(() => expect(escritas).toHaveLength(1));
    expect(escritas[0]).toEqual({
      controlCode: "preparacion:ligando.covalente", fingerprint: HUELLA, note: "Decidido.",
    });
    expect(mocks.update).not.toHaveBeenCalled();
  });

  it("un fallo al guardar se dice y no se da por registrada", async () => {
    await abrir();
    mocks.update.mockRejectedValue(new Error("disco lleno"));
    fireEvent.click(screen.getByRole("button", { name: "Asumir esta incertidumbre" }));
    fireEvent.change(screen.getByRole("textbox", { name: /Justificación/ }), { target: { value: "Decidido." } });
    fireEvent.click(screen.getByRole("button", { name: "Registrar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("disco lleno");
    expect(screen.getByRole("textbox", { name: /Justificación/ })).toHaveValue("Decidido.");
  });

  it("las decisiones de otras corridas del caso se declaran, no se aplican", async () => {
    await abrir(auditoria({ decisiones_de_otras_corridas: 2 }));
    expect(screen.getByText("Hay 2 decisiones de otras corridas de este caso: no se aplican a ésta."))
      .toBeInTheDocument();
  });
});
