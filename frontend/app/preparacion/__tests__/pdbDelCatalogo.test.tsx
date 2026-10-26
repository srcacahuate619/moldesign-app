import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Target } from "@/lib/api";
import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";
import { verificacionDePrueba } from "@/lib/__tests__/fixtures/verificacionReceptor";

const mocks = vi.hoisted(() => ({ read: vi.fn(), request: vi.fn(), list: vi.fn(), getResult: vi.fn() }));
vi.mock("@/lib/api", async load => ({ ...await load<object>(), getEvaluationResult: mocks.getResult }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
const repository = { listCases: mocks.list, readCase: mocks.read };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  return { ...real, useLanguage: () => ({ locale: "es", t: (key: string, params: Record<string, string | number> = {}) =>
    Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), real.TRANSLATIONS.es[key] ?? key) }) };
});
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => [
  { pdb_id: "8HFI", seccion_catalogo: "verificado", verificacion: verificacionDePrueba },
  { pdb_id: "LOCAL", is_private: true },
] as Target[] }));
import PreparacionPage from "../page";

describe("Preparación: identidad del receptor del sello", () => {
  it.each([
    { nombre: "el PDB explícito gana al rótulo", pdb_id: "8HFI", target: "LOCAL · Otro receptor" },
    { nombre: "una auditoría antigua usa el rótulo", target: "8HFI · Transportador" },
  ])("$nombre", async (corrida) => {
    mocks.getResult.mockReset().mockResolvedValue({ receptor_sha256: "receptor-de-esta-corrida", docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } });
    mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
    mocks.read.mockResolvedValue({ id: "case", name: "Caso", context: {}, inputs: { receptor: { pdbId: "LOCAL" } },
      runs: [], activeRun: { taskId: "exact", moleculeId: "molecule", executionState: "completed" },
    } as unknown as CaseRecord);
    mocks.request.mockResolvedValue({ schema: "preparacion/v1", estado: "BLOQUEADO", razon: "Causa del backend", alcance: "scope",
      transferencia_fep_demostrada: false, bloqueantes: [], en_revision: [],
      corrida: { case_id: "case", molecule_id: "molecule", task_id: "exact", ...corrida },
      bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({ id, estado: "REVISION", requisitos: [] })),
      paquete: { rotulo: "package", aviso: "limit" },
    } as unknown as AuditoriaPreparacion);
    render(<PreparacionPage />);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "case" } });
    expect(await screen.findByText("Verificado")).toBeVisible();
    expect(screen.getByText(/ρ = 0.41.*n = 57/)).toBeVisible();
    expect(screen.getByText(/Medido con exhaustividad 8, 9 poses y semilla 42/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Bloqueado" })).toBeVisible();
    expect(await screen.findByText("Esta corrida usó otro receptor preparado: la calibración no la describe.")).toBeVisible();
    expect(mocks.getResult).toHaveBeenCalledExactlyOnceWith("molecule", "exact");
    expect(screen.queryByText(/no declara todos sus parámetros/)).toBeNull();
  });
});
