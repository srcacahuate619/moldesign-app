// =====================================================================
// Moldex → Preparación: auditar una corrida guardada
// =====================================================================
//
// Moldex guarda CORRIDAS; Preparación audita el CASO que las produjo, porque la
// auditoría necesita su proyección (inputs, comprobación previa y decisiones). El
// enlace de Moldex manda el `task_id` y aquí se busca cuál de los casos lo tiene.
//
// Lo que se fija: que se abra ese caso con ESA corrida —no la última—, que se
// encuentre también cuando no es la última del caso, y que si ningún caso la tiene
// se diga en vez de auditar otra cosa.

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";
import { olvidarPeticionesDePreparacion, pedirPreparacion } from "@/lib/peticionDePreparacion";

const mocks = vi.hoisted(() => ({
  locale: "es" as "es" | "en",
  read: vi.fn(),
  request: vi.fn(),
  list: vi.fn(),
}));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
const repository = { listCases: mocks.list, readCase: mocks.read, updateCase: vi.fn() };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  const t = (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key;
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t }) };
});
import PreparacionPage from "../page";

function auditoria(): AuditoriaPreparacion {
  return {
    schema: "preparacion/v1", estado: "REVISION", razon: "cause", alcance: "scope",
    transferencia_fep_demostrada: false, bloqueantes: [], en_revision: [],
    corrida: { task_id: "run-vieja" },
    bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({
      id, estado: "REGISTRADO", requisitos: [],
    })),
    paquete: { rotulo: "package", aviso: "limit" },
  } as unknown as AuditoriaPreparacion;
}

/** Un caso con dos corridas completadas: la pedida por Moldex no es la última. */
function caso(id: string, tasks: readonly string[]): CaseRecord {
  const runs = tasks.map((taskId) => ({
    taskId, moleculeId: `mol-${taskId}`, executionState: "completed",
    startedAt: "2026-10-10T10:00:00.000Z",
  }));
  return {
    id, name: `Caso ${id}`, context: {}, runs,
    activeRun: runs[runs.length - 1],
  } as unknown as CaseRecord;
}

afterEach(() => {
  olvidarPeticionesDePreparacion();
  vi.clearAllMocks();
});

describe("Preparación atiende la petición de Moldex", () => {
  it("vuelve a cargar la corrida solicitada cuando el caso ya estaba abierto", async () => {
    mocks.locale = "es";
    mocks.list.mockResolvedValue([{ id: "case", name: "Caso", activeRun: { taskId: "run-nueva" } }]);
    mocks.read.mockResolvedValue(caso("case", ["run-vieja", "run-nueva"]));
    mocks.request.mockImplementation(async (moleculeId: string) => ({
      ...auditoria(), corrida: { task_id: moleculeId.replace("mol-", "") },
    }));
    render(<PreparacionPage />);
    fireEvent.change(await screen.findByLabelText("Caso"), { target: { value: "case" } });
    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("mol-run-nueva", expect.anything(), expect.anything()));

    pedirPreparacion({ taskId: "run-vieja" });

    await waitFor(() => expect(mocks.request).toHaveBeenCalledWith("mol-run-vieja", expect.anything(), expect.anything()));
    expect(screen.getByLabelText("Caso")).toHaveValue("case");
    expect(screen.getByRole("button", { name: "Descargar paquete de la corrida" })).toBeEnabled();
  });

  it("abre el caso que tiene esa corrida, y audita ESA corrida", async () => {
    mocks.locale = "es";
    mocks.list.mockResolvedValue([
      { id: "otro", name: "Otro", activeRun: { taskId: "run-ajena" } },
      { id: "case", name: "Caso", activeRun: { taskId: "run-nueva" } },
    ]);
    mocks.read.mockImplementation(async (id: string) =>
      id === "case" ? caso("case", ["run-vieja", "run-nueva"]) : caso("otro", ["run-ajena"]));
    mocks.request.mockResolvedValue(auditoria());
    render(<PreparacionPage />);
    await screen.findByRole("combobox");

    pedirPreparacion({ taskId: "run-vieja", etiqueta: "aspirina" });

    // Se audita la corrida que pidió Moldex, no la última del caso.
    await waitFor(() => expect(mocks.request).toHaveBeenCalled());
    const [moleculeId] = mocks.request.mock.calls[0];
    expect(moleculeId).toBe("mol-run-vieja");
    // Con el caso abierto hay dos selectores (caso y evaluación): el del caso es el etiquetado «Caso».
    expect(screen.getByLabelText("Caso")).toHaveValue("case");
  });

  it("si ningún caso tiene esa corrida, lo dice y no audita otra", async () => {
    mocks.locale = "es";
    mocks.list.mockResolvedValue([{ id: "case", name: "Caso", activeRun: { taskId: "run-nueva" } }]);
    mocks.read.mockResolvedValue(caso("case", ["run-nueva"]));
    render(<PreparacionPage />);
    await waitFor(() => expect(mocks.list).toHaveBeenCalled());

    pedirPreparacion({ taskId: "run-de-otra-parte" });

    expect(await screen.findByText(/Ningún caso tuyo contiene esa corrida guardada/)).toBeInTheDocument();
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("no mira los casos que no se pueden abrir", async () => {
    mocks.locale = "es";
    mocks.list.mockResolvedValue([
      { id: "roto", name: "Roto", unavailable: { code: "not_found" }, activeRun: { taskId: "run-vieja" } },
    ]);
    mocks.read.mockResolvedValue(caso("roto", ["run-vieja"]));
    render(<PreparacionPage />);
    await waitFor(() => expect(mocks.list).toHaveBeenCalled());

    pedirPreparacion({ taskId: "run-vieja" });

    expect(await screen.findByText(/Ningún caso tuyo contiene esa corrida guardada/)).toBeInTheDocument();
    expect(mocks.read).not.toHaveBeenCalled();
  });
});

describe("el canal de Moldex a Preparación", () => {
  it("una petición sin oyente espera y la toma el primero que escucha", async () => {
    const { escucharPeticionesDePreparacion } = await import("@/lib/peticionDePreparacion");
    pedirPreparacion({ taskId: "t-1" });
    const recibidas: string[] = [];
    const dejar = escucharPeticionesDePreparacion((p) => recibidas.push(p.taskId));
    expect(recibidas).toEqual(["t-1"]);
    // Ya consumida: un segundo oyente no la recibe otra vez.
    const otras: string[] = [];
    escucharPeticionesDePreparacion((p) => otras.push(p.taskId));
    expect(otras).toEqual([]);
    dejar();
  });

  it("dos peticiones iguales son dos, y al dejar de escuchar no llega nada", async () => {
    const { escucharPeticionesDePreparacion } = await import("@/lib/peticionDePreparacion");
    const nonces: number[] = [];
    const dejar = escucharPeticionesDePreparacion((p) => nonces.push(p.nonce));
    pedirPreparacion({ taskId: "t-1" });
    pedirPreparacion({ taskId: "t-1" });
    expect(new Set(nonces).size).toBe(2);
    dejar();
    pedirPreparacion({ taskId: "t-2" });
    expect(nonces).toHaveLength(2);
  });
});

describe("Moldex ofrece el acceso", () => {
  it("la ficha manda el task_id de la corrida y no inventa uno", async () => {
    const { readFileSync } = await import("node:fs");
    const { resolve } = await import("node:path");
    const fuente = readFileSync(resolve(process.cwd(), "app/moldex/page.tsx"), "utf8");
    expect(fuente).toContain("pedirPreparacion({ taskId: selectedTaskId");
    // Sin corrida exacta no hay enlace: se dice por qué.
    expect(fuente).toContain('t("pg_mx_preparacion_sin_corrida")');
  });
});
