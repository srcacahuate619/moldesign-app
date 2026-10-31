import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import type { CaseRecord } from "@/lib/cases/types";
import type { AuditoriaPreparacion } from "@/lib/preparacion";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en", read: vi.fn(), request: vi.fn(), list: vi.fn() }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: "owner" }, isLoading: false }) }));
const repository = { listCases: mocks.list, readCase: mocks.read };
vi.mock("@/lib/cases/factory", () => ({ crearRepositorioDeCasos: () => repository }));
vi.mock("@/lib/dossier", async (load) => ({ ...await load<object>(), requestPreparacion: mocks.request }));
vi.mock("@/context/LanguageContext", async (load) => {
  const real = await load<typeof import("@/context/LanguageContext")>();
  const t = (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key;
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t }) };
});
import PreparacionPage from "../page";

describe("Preparación: acción sobre el corte físico", () => {
  it.each(["es", "en"] as const)("muestra ubicación, acción y causa global en %s", async (locale) => {
    mocks.locale = locale;
    mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
    mocks.read.mockResolvedValue({ id: "case", name: "Caso", context: {}, runs: [], activeRun: { taskId: "exact", moleculeId: "molecule", executionState: "completed" } } as unknown as CaseRecord);
    const action = locale === "es" ? "Modela o repara el esqueleto." : "Model or repair the backbone.";
    mocks.request.mockResolvedValue({ schema: "preparacion/v1", estado: "BLOQUEADO", razon: "cause", alcance: "scope", transferencia_fep_demostrada: false,
      bloqueantes: ["receptor.huecos"], en_revision: [], corrida: { task_id: "exact" },
      bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({ id, estado: id === "receptor" ? "BLOQUEADO" : "REVISION", requisitos: id === "receptor" ? [{ clave: "receptor.huecos", estado: "ABSTENCION", imprescindible: true, etiqueta: "Gap", valor: "A: THR 197 → VAL 199 (C–N 4.79 Å; 1.25 Å)", valor_es_clasificacion: true, razon: "cavity", accion_recomendada: action, fuente: "receptor_prep.backbone_gaps" }] : [] })),
      paquete: { rotulo: "package", aviso: "limit" },
    } as unknown as AuditoriaPreparacion);
    const view = render(<PreparacionPage />);
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "case" } });
    expect(await screen.findByText(action)).toBeVisible();
    expect(screen.getByText(/THR 197.*VAL 199/)).toBeVisible();
    expect(screen.getByText(locale === "es" ? /sistema está bloqueado hasta reparar/ : /system is blocked until/)).toBeVisible();
    expect(screen.getByText(locale === "es" ? "Acción recomendada" : "Recommended action")).toBeVisible();
    if (locale === "es") {
      const data = await mocks.request.mock.results.at(-1)!.value as AuditoriaPreparacion;
      const english = "Model or repair the backbone.";
      mocks.request.mockResolvedValue({ ...data, bloques: data.bloques.map((block) => ({ ...block, requisitos: block.requisitos.map((r) => ({ ...r, accion_recomendada: english })) })) });
      mocks.locale = "en";
      view.rerender(<PreparacionPage />);
      expect(await screen.findByText(english)).toBeVisible();
      expect(screen.queryByText(action)).not.toBeInTheDocument();
    }
  });
});
