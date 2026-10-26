import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CaseRecord, CaseRun } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";

/**
 * Preparación no se desmonta al cambiar de pestaña (decisión del propietario, 2026-10-10). Antes, al volver, el caso
 * abierto se perdía y había que elegirlo y auditarlo otra vez. Ahora al volver se refresca en silencio: si el caso no
 * cambió no se repite la auditoría; si tiene una evaluación nueva y se veía la última por defecto, pasa a la nueva; si el
 * investigador había elegido otra, se respeta.
 */
const mocks = vi.hoisted(() => ({ activa: true, read: vi.fn(), request: vi.fn(), list: vi.fn() }));
vi.mock("@/context/KeepAliveContext", () => ({ useKeepAliveActive: () => mocks.activa }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => ({ listCases: mocks.list, readCase: mocks.read }) }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  return { ...real, useLanguage: () => ({ locale: "es", t: (key: string) => real.TRANSLATIONS.es[key] ?? key }) };
});
import PreparacionPage from "../page";

const corrida = (n: number): CaseRun => ({ taskId: `run-${n}`, moleculeId: `m${n}`, executionState: "completed",
  startedAt: `2026-10-0${n}T10:00:00Z` } as unknown as CaseRun);
function caso(updatedAt: string, ...runs: CaseRun[]): CaseRecord {
  return { id: "case", name: "Caso", context: {}, updatedAt, runs, activeRun: runs.at(-1) } as unknown as CaseRecord;
}
const auditoria = (taskId: string) => ({ schema: "preparacion/v1", estado: "REVISION", razon: "r", alcance: "a",
  transferencia_fep_demostrada: false, bloqueantes: [], en_revision: [], corrida: { task_id: taskId },
  bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({ id, estado: "REVISION", requisitos: [] })),
  paquete: { rotulo: "p", aviso: "l" } }) as unknown as AuditoriaPreparacion;
/** Moléculas auditadas, en orden: dicen qué evaluación se auditó. */
const auditadas = () => mocks.request.mock.calls.map((llamada) => llamada[0] as string);

/** El selector de casos es el `<select>` nativo; el de evaluaciones es un listbox propio. */
const selectorDeCasos = () => screen.getAllByRole("combobox").find((el) => el.tagName === "SELECT") as HTMLSelectElement;
async function abrirCaso() {
  const vista = render(<PreparacionPage />);
  await waitFor(() => expect(selectorDeCasos()).toBeTruthy());
  fireEvent.change(selectorDeCasos(), { target: { value: "case" } });
  return vista;
}
async function salirYVolver(rerender: (ui: React.ReactElement) => void) {
  mocks.activa = false;
  await act(async () => { rerender(<PreparacionPage />); });
  mocks.activa = true;
  await act(async () => { rerender(<PreparacionPage />); });
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  mocks.activa = true;
  vi.clearAllMocks();
  mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
  mocks.request.mockImplementation(async (moleculeId: string) => auditoria(`run-${moleculeId.slice(1)}`));
});

describe("Preparación al volver a la pestaña", () => {
  it("si el caso no cambió, sigue abierto y no repite la auditoría", async () => {
    mocks.read.mockResolvedValue(caso("t1", corrida(1)));
    const { rerender } = await abrirCaso();
    await waitFor(() => expect(auditadas()).toEqual(["m1"]));
    const lecturas = mocks.read.mock.calls.length;
    const listas = mocks.list.mock.calls.length;

    await salirYVolver(rerender);
    await waitFor(() => expect(mocks.read.mock.calls.length).toBe(lecturas + 1));
    expect(mocks.list.mock.calls.length).toBe(listas + 1);
    expect(auditadas()).toEqual(["m1"]);
    expect(selectorDeCasos().value).toBe("case");
  });

  it("una evaluación nueva del caso se abre si se veía la última por defecto", async () => {
    mocks.read.mockResolvedValue(caso("t1", corrida(1)));
    const { rerender } = await abrirCaso();
    await waitFor(() => expect(auditadas()).toEqual(["m1"]));

    mocks.read.mockResolvedValue(caso("t2", corrida(1), corrida(2)));
    await salirYVolver(rerender);
    await waitFor(() => expect(auditadas()).toEqual(["m1", "m2"]));
  });

  it("si el investigador eligió otra evaluación, se respeta aunque haya una nueva", async () => {
    mocks.read.mockResolvedValue(caso("t1", corrida(1), corrida(2)));
    const { rerender } = await abrirCaso();
    await waitFor(() => expect(auditadas()).toEqual(["m2"]));
    const selector = screen.getAllByRole("combobox").find((el) => el.tagName !== "SELECT")!;
    fireEvent.click(selector);
    const opciones = within(screen.getByRole("listbox")).getAllByRole("option");
    fireEvent.click(opciones.find((opcion) => opcion.getAttribute("aria-selected") === "false")!);
    await waitFor(() => expect(auditadas().at(-1)).toBe("m1"));

    mocks.read.mockResolvedValue(caso("t2", corrida(1), corrida(2), corrida(3)));
    await salirYVolver(rerender);
    await waitFor(() => expect(mocks.read.mock.calls.length).toBeGreaterThanOrEqual(2));
    await act(async () => { await Promise.resolve(); });
    expect(auditadas()).not.toContain("m3");
    expect(auditadas().at(-1)).toBe("m1");
  });

  it("un caso creado mientras tanto aparece en la lista al volver", async () => {
    mocks.read.mockResolvedValue(caso("t1", corrida(1)));
    const { rerender } = await abrirCaso();
    await waitFor(() => expect(auditadas()).toEqual(["m1"]));
    mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }, { id: "otro", name: "Caso nuevo" }]);
    await salirYVolver(rerender);
    expect(await screen.findByRole("option", { name: "Caso nuevo" })).toBeInTheDocument();
  });
});
