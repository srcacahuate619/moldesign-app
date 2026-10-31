// =====================================================================
// Preparación separa la revisión rutinaria de la del caso
// =====================================================================
//
// Medido en el panel del 2026-10-10: la protonación por plantilla, la sección
// Demostración y el commit del instalador pedían revisión en las once corridas, y
// «Revisión» salía igual sin nada propio del caso que con un tautómero abierto.
// El backend marca lo rutinario (`rutinaria`, `en_revision_rutinaria`,
// `solo_rutinaria`) y la pantalla:
//
//   1. lo dice junto al estado global: «Sólo rutinaria» o «Del caso»;
//   2. con sólo rutina, explica que nada propio del caso pide revisión;
//   3. en cada requisito rutinario dice por qué, y sigue ofreciendo decidir: está abierto;
//   4. un bloque que sólo tiene rutina lo dice en su cabecera.

import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CaseRecord } from "@/lib/cases/types";
import { esAuditoriaPreparacion, type AuditoriaPreparacion } from "@/lib/preparacion";

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
  const t = (key: string) => real.TRANSLATIONS[mocks.locale][key] ?? key;
  return { ...real, useLanguage: () => ({ locale: mocks.locale, t }) };
});
import PreparacionPage from "../page";

const MOTIVO = "La pide toda corrida protonada por plantilla, y ninguna histidina tiene un nitrógeno del anillo a 3.5 Å o menos del ligando.";

const PROTONACION = {
  clave: "receptor.protonacion", estado: "REVISAR", imprescindible: false, etiqueta: "Protonación del receptor",
  valor: "Meeko 0.7.1; asignación por plantilla", valor_es_clasificacion: true,
  razon: "Asignación por plantilla, sin pH experimental.", fuente: "f",
  rutinaria: { motivo: MOTIVO },
};
const COVALENTE = {
  clave: "ligando.covalente", estado: "REVISAR", imprescindible: false, etiqueta: "Unión covalente",
  valor: "Ojiva: acrilamida (aceptor de Michael).", valor_es_clasificacion: true,
  razon: "Vina acopla el complejo no covalente.", fuente: "f",
};

/** Con `delCaso`, además de la protonación rutinaria hay una ojiva covalente que revisar. */
function auditoria(delCaso: boolean): AuditoriaPreparacion {
  return {
    schema: "preparacion/v1", estado: "REVISION", razon: "cause", alcance: "scope",
    transferencia_fep_demostrada: false, bloqueantes: [],
    en_revision: delCaso ? ["receptor.protonacion", "ligando.covalente"] : ["receptor.protonacion"],
    en_revision_rutinaria: ["receptor.protonacion"],
    solo_rutinaria: !delCaso,
    huella_de_decision: "tarea:exact", corrida: { task_id: "exact" },
    bloques: ["receptor", "ligando", "pose", "entorno", "procedencia"].map((id) => ({
      id,
      estado: id === "receptor" || (delCaso && id === "ligando") ? "REVISION" : "REGISTRADO",
      solo_rutinaria: id === "receptor",
      requisitos: id === "receptor" ? [PROTONACION] : id === "ligando" && delCaso ? [COVALENTE] : [],
    })),
    paquete: { rotulo: "package", aviso: "limit" },
  } as unknown as AuditoriaPreparacion;
}

const CASO = {
  id: "case", name: "Caso", context: {}, runs: [],
  activeRun: { taskId: "exact", moleculeId: "molecule", executionState: "completed" },
} as unknown as CaseRecord;

async function abrir(a: AuditoriaPreparacion, locale: "es" | "en" = "es") {
  mocks.locale = locale;
  mocks.list.mockResolvedValue([{ id: "case", name: "Caso" }]);
  mocks.read.mockResolvedValue(CASO);
  mocks.update.mockImplementation(async (record: CaseRecord) => record);
  mocks.request.mockResolvedValue(a);
  render(<PreparacionPage />);
  fireEvent.change(await screen.findByRole("combobox"), { target: { value: "case" } });
  await screen.findByText(locale === "es" ? "Revisión" : "Review", { selector: "h2" });
}

afterEach(() => vi.clearAllMocks());

describe("Preparación: revisión rutinaria y revisión del caso", () => {
  it("el contrato admite lo rutinario y rechaza un motivo vacío", () => {
    expect(esAuditoriaPreparacion(auditoria(true))).toBe(true);
    const mala = structuredClone(auditoria(false)) as unknown as { bloques: { requisitos: { rutinaria?: unknown }[] }[] };
    mala.bloques[0].requisitos[0].rutinaria = { motivo: "" };
    expect(esAuditoriaPreparacion(mala)).toBe(false);
  });

  it("con sólo rutina, el estado global lo dice y explica que nada del caso pide revisión", async () => {
    await abrir(auditoria(false));
    expect(screen.getByText("Sólo rutinaria")).toBeInTheDocument();
    expect(screen.getByText(/^Nada propio de este caso pide revisión/)).toBeInTheDocument();
    expect(screen.getByText("0 imprescindible(s) sin resolver · 1 para revisar (1 rutinaria)")).toBeInTheDocument();
  });

  it("con algo del caso, el estado global dice «Del caso» y la razón de siempre", async () => {
    await abrir(auditoria(true));
    expect(screen.getByText("Del caso")).toBeInTheDocument();
    expect(screen.queryByText("Sólo rutinaria")).toBeNull();
    expect(screen.getByText("Hay decisiones científicas abiertas que el cálculo siguiente heredaría.")).toBeInTheDocument();
    expect(screen.getByText("0 imprescindible(s) sin resolver · 2 para revisar (1 rutinaria)")).toBeInTheDocument();
  });

  it("el requisito rutinario dice por qué y se puede decidir igual: sigue abierto", async () => {
    await abrir(auditoria(true));
    const cabecera = screen.getByRole("button", { name: /Receptor y sitio/ });
    expect(within(cabecera).getByText("· RUTINARIA", { exact: false })).toBeInTheDocument();
    // El primer bloque abre ya desplegado: pulsarlo lo cerraría.
    if (cabecera.getAttribute("aria-expanded") !== "true") fireEvent.click(cabecera);
    const item = within(screen.getByText("Asignación por plantilla, sin pH experimental.").closest("li") as HTMLElement);
    expect(item.getByText((_, el) => el?.tagName === "P" && el.textContent === `Rutinaria. ${MOTIVO}`))
      .toBeInTheDocument();
    expect(item.getByRole("button", { name: "Asumir esta incertidumbre" })).toBeInTheDocument();
  });

  it("un requisito del caso no se marca como rutinario", async () => {
    await abrir(auditoria(true));
    const cabecera = screen.getByRole("button", { name: /Estado químico/ });
    expect(within(cabecera).queryByText("· RUTINARIA", { exact: false })).toBeNull();
    fireEvent.click(cabecera);
    const item = within(screen.getByText("Ojiva: acrilamida (aceptor de Michael).").closest("li") as HTMLElement);
    expect(item.queryByText("Rutinaria.")).toBeNull();
  });

  it("sale en inglés", async () => {
    await abrir(auditoria(false), "en");
    expect(screen.getByText("Routine only")).toBeInTheDocument();
    expect(screen.getByText(/^Nothing specific to this case needs review/)).toBeInTheDocument();
    expect(screen.getByText("0 essential item(s) unresolved · 1 to review (1 routine)")).toBeInTheDocument();
  });
});
