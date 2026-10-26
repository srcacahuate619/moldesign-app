import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en", read: vi.fn(), request: vi.fn(), list: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
const repository = { listCases: mocks.list, readCase: mocks.read };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => null }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t: (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key }) };
});
import PreparacionPage from "../page";

describe("Preparación: nombre del requisito de catálogo", () => {
  it.each(["es", "en"] as const)("traduce la clave del requisito sin cambiar su estado en %s", async (locale) => {
    mocks.locale = locale;
    mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
    mocks.read.mockResolvedValue({ id: "case", name: "Caso", context: {}, runs: [], activeRun: { taskId: "exact", moleculeId: "molecule", executionState: "completed" } } as unknown as CaseRecord);
    mocks.request.mockResolvedValue({ schema: "preparacion/v1", estado: "REVISION", alcance: "scope", razon: "cause",
      transferencia_fep_demostrada: false, bloqueantes: [], en_revision: ["receptor.seccion_catalogo"],
      corrida: { case_id: "case", molecule_id: "molecule", task_id: "exact", target: "8HFI", pdb_id: "8HFI" },
      bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map(id => ({ id, estado: "REVISION", requisitos: id === "receptor" ? [{
        clave: "receptor.seccion_catalogo", etiqueta: "Etiqueta cruda del backend", valor: null, estado: "REVISAR", razon: null,
        valor_es_clasificacion: false, fuente: "run.catalogo", imprescindible: false,
      }] : [] })), paquete: { rotulo: "package", aviso: "limit" },
    } as unknown as AuditoriaPreparacion);
    render(<PreparacionPage />);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "case" } });
    expect(await screen.findByText(locale === "es" ? "Sección del catálogo" : "Catalog section")).toBeVisible();
    expect(screen.queryByText("Etiqueta cruda del backend")).toBeNull();
    expect(screen.getByRole("heading", { name: locale === "es" ? "Revisión" : "Review" })).toBeVisible();
  });
});
