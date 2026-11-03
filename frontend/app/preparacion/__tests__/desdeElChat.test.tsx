// =====================================================================
// MolChat → Preparación: «audita la corrida que acabas de evaluar»
// =====================================================================
//
// El asistente pide por el puente del host (`audit_case_preparation`) que Preparación audite una corrida de un caso
// por su nombre. Se atiende por el mismo camino que Moldex: se abre el caso que tiene esa corrida y la pestaña la
// audita a la vista. Al llegar la auditoría se devuelve la proyección que armó la pestaña.
//
// Lo que se fija: que se audite ESA corrida, que el estado que dictó el backend viaje tal cual (un REVISION no se
// vuelve «listo»), que no se invente ninguna decisión humana, y que lo que no se puede auditar se diga con su motivo.

import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";
import { olvidarPeticionesDePreparacion } from "@/lib/peticionDePreparacion";

const mocks = vi.hoisted(() => ({
  locale: "es" as "es" | "en",
  read: vi.fn(),
  request: vi.fn(),
  list: vi.fn(),
  user: { user_id: "owner" } as { user_id: string } | null,
}));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: mocks.user, isLoading: mocks.user === null }) }));
const repository = { listCases: mocks.list, readCase: mocks.read, updateCase: vi.fn() };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  const t = (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key;
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t }) };
});
import PreparacionPage from "../page";

function auditoria(estado: string, taskId: string): AuditoriaPreparacion {
  return {
    schema: "preparacion/v1", estado, razon: "cause", alcance: "scope",
    transferencia_fep_demostrada: false, bloqueantes: [], en_revision: [],
    corrida: { task_id: taskId },
    bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({
      id, estado: "REGISTRADO", requisitos: [],
    })),
    paquete: { rotulo: "package", aviso: "limit" },
  } as unknown as AuditoriaPreparacion;
}

function caso(id: string, tasks: readonly string[]): CaseRecord {
  const runs = tasks.map((taskId) => ({
    taskId, moleculeId: `mol-${taskId}`, executionState: "completed", startedAt: "2026-10-10T10:00:00.000Z",
  }));
  return { id, name: `Caso ${id}`, context: {}, runs, activeRun: runs[runs.length - 1] } as unknown as CaseRecord;
}

function pedir(over: Partial<{ caseName: string; taskId: string; owner: string; deadline: number }> = {}) {
  const respond = vi.fn();
  const detail = { caseName: "Caso case", taskId: "run-vieja", owner: "owner", deadline: Date.now() + 30000,
    handled: false, respond, ...over };
  window.dispatchEvent(new CustomEvent("molchat-audit-preparation", { detail }));
  return { respond, detail };
}

afterEach(() => {
  mocks.user = { user_id: "owner" };
  olvidarPeticionesDePreparacion();
  vi.clearAllMocks();
});

function preparar(estado = "REVISION") {
  mocks.locale = "es";
  mocks.list.mockResolvedValue([{ id: "case", name: "Caso case", activeRun: { taskId: "run-nueva" } }]);
  mocks.read.mockResolvedValue(caso("case", ["run-vieja", "run-nueva"]));
  mocks.request.mockImplementation(async (moleculeId: string) => auditoria(estado, moleculeId.replace("mol-", "")));
}

describe("Preparación atiende la petición del chat", () => {
  it("audita ESA corrida y devuelve la proyección con el estado que dictó el backend", async () => {
    preparar("REVISION");
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond, detail } = pedir();
    expect(detail.handled).toBe(true);

    await waitFor(() => expect(respond).toHaveBeenCalled());
    const [result] = respond.mock.calls[0];
    expect(result).toMatchObject({ status: "audited", molecule_id: "mol-run-vieja", estado: "REVISION" });
    expect(result.projection).toMatchObject({ case_id: "case", name: "Caso case" });
    expect(mocks.request.mock.calls[0][0]).toBe("mol-run-vieja");
    // la pestaña no inventa decisiones humanas para que el paquete salga «mejor»
    expect(result.projection.decisions).toBeUndefined();
    expect(respond).toHaveBeenCalledTimes(1);
  });

  it("un BLOQUEADO también se devuelve tal cual: la abstención es una salida válida", async () => {
    preparar("BLOQUEADO");
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond } = pedir();
    await waitFor(() => expect(respond).toHaveBeenCalled());
    expect(respond.mock.calls[0][0]).toMatchObject({ status: "audited", estado: "BLOQUEADO" });
  });

  it("si ningún caso tiene esa corrida, lo dice y no audita otra", async () => {
    preparar();
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond } = pedir({ taskId: "run-de-otra-parte" });
    await waitFor(() => expect(respond).toHaveBeenCalledWith({ status: "case_not_found" }));
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("si la corrida es de otro caso que el pedido por nombre, no la entrega", async () => {
    preparar();
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond } = pedir({ caseName: "Otro caso distinto" });
    await waitFor(() => expect(respond).toHaveBeenCalledWith({ status: "case_mismatch" }));
  });

  it("si la auditoría falla, devuelve el motivo y no una proyección", async () => {
    preparar();
    mocks.request.mockRejectedValue(new Error("el backend no respondió"));
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond } = pedir();
    await waitFor(() => expect(respond).toHaveBeenCalled());
    expect(respond.mock.calls[0][0]).toMatchObject({ status: "audit_failed" });
    expect(respond.mock.calls[0][0].projection).toBeUndefined();
  });

  it("rechaza al que no es el dueño de la sesión y no audita nada", async () => {
    preparar();
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond } = pedir({ owner: "otra-cuenta" });
    expect(respond).toHaveBeenCalledWith({ status: "failed", reason: "la petición es de otra cuenta" });
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("rechaza una petición que llegó ya vencida", async () => {
    preparar();
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const { respond } = pedir({ deadline: Date.now() - 1 });
    expect(respond).toHaveBeenCalledWith({ status: "failed", reason: "se venció el plazo antes de empezar" });
  });

  it("si la pestaña aún no conoce la cuenta, no contesta: deja que el anfitrión vuelva a preguntar", async () => {
    // Lo que hizo fallar el primer ensayo en la app: la pestaña recién montada contestaba «failed» al instante.
    preparar();
    mocks.user = null;
    render(<PreparacionPage />);
    const { respond, detail } = pedir();
    expect(detail.handled).toBe(false);
    expect(respond).not.toHaveBeenCalled();
  });

  it("atiende una petición a la vez: la segunda recibe «busy» sin pisar a la primera", async () => {
    preparar();
    mocks.request.mockImplementation(() => new Promise(() => {}));
    render(<PreparacionPage />);
    await screen.findByRole("combobox");
    const primera = pedir();
    const segunda = pedir({ taskId: "run-nueva" });
    expect(segunda.respond).toHaveBeenCalledWith({ status: "busy" });
    expect(primera.respond).not.toHaveBeenCalled();
  });
});
