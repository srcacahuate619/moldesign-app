import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
vi.mock("@react-three/fiber", () => ({ Canvas: () => <div />, useThree: () => ({ camera: { position: { set() {} }, lookAt() {}, updateProjectionMatrix() {} }, invalidate() {}, gl: {}, scene: {} }) }));
vi.mock("@react-three/drei", () => ({ OrbitControls: () => null, Edges: () => null, Sphere: () => null }));
vi.mock("../../../../lib/api", () => ({ encenderMotor: vi.fn(), inventarioDeMotores: vi.fn(async () => ({ docking: [], peptido: [] })) }));
vi.mock("../../../../lib/config", () => ({ getApiUrl: async () => "http://localhost:18015" }));
const language = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("../../../../context/LanguageContext", async (original) => {
  const actual = await original<typeof import("../../../../context/LanguageContext")>();
  return { ...actual, useLanguage: () => ({ locale: language.locale, t: (key: string, params: Record<string, string | number> = {}) => Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, String(value)), actual.TRANSLATIONS[language.locale][key] ?? key) }) };
});
import ProOptionsModal, { type AdvancedConfig } from "../ProOptionsModal";
const rows = Array.from({ length: 44 }, (_, i) => ({
  pdb_id: i === 0 ? "5VA1" : i === 1 ? "4NC3" : i < 40 ? `X${i}` : null,
  name: i === 0 ? "hERG" : i === 1 ? "5-HT2B" : `Diana ${i}`,
  category: i < 2 ? "Cardiac" : "Bowes 2012 · GPCR", risk: "", threshold_kcal: -7,
  por_defecto: i < 2, disponible: i < 40, seleccionable: i < 40,
  motivo_no_disponible: i < 40 ? null : "Sin estructura humana",
  estructura: i === 2 ? { pose_reproducida: false, resolucion_A: 2.5 } : null,
}));
const initial: AdvancedConfig = { protonationPh: 7.4, numWorkers: 4, parallelDocks: 2, enableSelectivity: true, selectedAntiTargets: ["5VA1", "4NC3"], enableMMGBSA: false, mmgbsaSteps: 1000, enableADMET: false };
beforeEach(() => {
  language.locale = "es";
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ anti_targets: rows }) })));
  Element.prototype.animate = (() => ({ cancel() {}, finish() {}, finished: Promise.resolve() })) as unknown as Element["animate"];
});
afterEach(() => vi.unstubAllGlobals());
function open(advanced: AdvancedConfig | null = initial) {
  const apply = vi.fn();
  render(<ProOptionsModal isOpen onClose={() => {}} onApply={apply} initialAdvanced={advanced ?? undefined} />);
  return apply;
}
describe("anti-dianas en Parámetros de la evaluación", () => {
  it("resuelve el panel por defecto si se abre antes de terminar la carga del padre", async () => {
    const apply = open({ ...initial, selectedAntiTargets: [], antiTargetsPending: true } as AdvancedConfig);
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /hERG/ })).toBeChecked());
    expect(screen.getByRole("checkbox", { name: /5-HT2B/ })).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: /Aplicar/ }));
    expect(apply.mock.calls[0][2].selectedAntiTargets).toEqual(["5VA1", "4NC3"]);
  });

  it.each(["es", "en"] as const)("declara las cadenas laterales truncadas del nuevo receptor en %s", async (locale) => {
    language.locale = locale;
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ anti_targets: rows.map((r) => r.pdb_id === "4NC3" ? { ...r, pdb_id: "7SRQ", estructura: { resolucion_A: 2.7, pose_reproducida: true, truncadas_en_sitio: 4 } } : r) }) })));
    open();
    await screen.findByText(locale === "es" ? /4 cadenas laterales incompletas/ : /4 incomplete side chains/);
  });
  it("muestra 44 filas por familia, dos seleccionadas y los motivos no disponibles", async () => {
    open();
    const boxes = await screen.findAllByRole("checkbox");
    expect(boxes).toHaveLength(44);
    expect(boxes.filter((b) => (b as HTMLInputElement).checked)).toHaveLength(2);
    expect(within(screen.getByRole("group", { name: /GPCR/ })).getAllByRole("checkbox")).toHaveLength(42);
    expect(screen.getAllByText("Sin estructura humana")).toHaveLength(4);
    expect(boxes.filter((b) => (b as HTMLInputElement).disabled)).toHaveLength(4);
  });
  it("Todas excluye las no disponibles, advierte del coste y Ninguna envía cero", async () => {
    const apply = open();
    await screen.findAllByRole("checkbox");
    fireEvent.click(screen.getByRole("button", { name: "Todas las disponibles" }));
    expect(screen.getAllByRole("checkbox").filter((b) => (b as HTMLInputElement).checked)).toHaveLength(40);
    expect(screen.getByText(/Cada anti-diana añade un acoplamiento por confórmero/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Ninguna" }));
    expect(screen.getAllByRole("checkbox").filter((b) => (b as HTMLInputElement).checked)).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: /Aplicar/ }));
    expect(apply.mock.calls[0][2].selectedAntiTargets).toEqual([]);
  });
  it("conserva visible una id guardada desconocida, avisa y la excluye al aplicar", async () => {
    const apply = open({ ...initial, selectedAntiTargets: ["5VA1", "YA_NO_EXISTE"] });
    await screen.findByText("YA_NO_EXISTE");
    expect(screen.getByText(/se excluyen del envío/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Aplicar/ }));
    await waitFor(() => expect(apply).toHaveBeenCalled());
    expect(apply.mock.calls[0][2].selectedAntiTargets).toEqual(["5VA1"]);
  });
  it("declara la pose no reproducida con resolución y PDB y obtiene el defecto del API", async () => {
    open(null);
    fireEvent.click(screen.getByRole("switch", { name: /Selectividad/ }));
    await screen.findByText(/El redocking no reprodujo la pose cristalográfica/);
    expect(screen.getByText(/X2.*2\.5 Å/)).toHaveTextContent("X2");
    await waitFor(() => expect(screen.getAllByRole("checkbox").filter((b) => (b as HTMLInputElement).checked)).toHaveLength(2));
    fireEvent.click(screen.getByRole("button", { name: "Todas las disponibles" }));
    fireEvent.click(screen.getByRole("button", { name: "Panel por defecto" }));
    await waitFor(() => expect(screen.getAllByRole("checkbox").filter((b) => (b as HTMLInputElement).checked)).toHaveLength(2));
  });
  it("una id guardada ahora no disponible sigue visible y marcada pero se excluye del envío", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ anti_targets: rows.map((r) => r.pdb_id === "X2" ? { ...r, disponible: false, motivo_no_disponible: "Receptor retirado" } : r) }) })));
    const apply = open({ ...initial, selectedAntiTargets: ["5VA1", "X2"] });
    await screen.findByText("Receptor retirado");
    const box = screen.getByRole("checkbox", { name: /Diana 2.*X2$/ });
    expect(box).toBeDisabled();
    expect(box).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: /Aplicar/ }));
    expect(apply.mock.calls[0][2].selectedAntiTargets).toEqual(["5VA1"]);
  });
  it("los ids por defecto vienen del API también al sustituir una estructura", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({ ok: true, json: async () => ({ anti_targets: rows.map((r) => r.pdb_id === "4NC3" ? { ...r, pdb_id: "NUEVA" } : r) }) })));
    const apply = open(null);
    fireEvent.click(screen.getByRole("switch", { name: /Selectividad/ }));
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /5-HT2B/ })).toBeChecked());
    fireEvent.click(screen.getByRole("button", { name: /Aplicar/ }));
    expect(apply.mock.calls[0][2].selectedAntiTargets).toEqual(["5VA1", "NUEVA"]);
  });
  it("las advertencias y controles siguen el inglés de la interfaz", async () => {
    language.locale = "en";
    open();
    await screen.findByText(/Redocking did not reproduce the crystal pose/);
    expect(screen.getByRole("button", { name: "All available" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Anti-targets by family" })).toBeTruthy();
  });

});

describe("tautómero personalizado", () => {
  it.each(["es", "en"] as const)("elige y aplica el modo en %s", async (locale) => {
    language.locale = locale;
    const apply = open();
    const select = screen.getByRole("combobox", { name: locale === "es" ? "Tautómero del ligando" : "Ligand tautomer" });
    // Desde el 2026-10-10 el defecto es el tautómero escrito; el canónico de RDKit se elige.
    expect(select).toHaveValue("entrada");
    await screen.findAllByRole("checkbox");
    fireEvent.change(select, { target: { value: "canonico" } });
    fireEvent.click(screen.getByRole("button", { name: locale === "es" ? /Aplicar/ : /Apply/ }));
    expect(apply.mock.calls[0][2].tautomerMode).toBe("canonico");
  });
  it("reabre el modo guardado personalizado", () => {
    open({ ...initial, tautomerMode: "entrada" } as AdvancedConfig);
    expect(screen.getByRole("combobox", { name: "Tautómero del ligando" })).toHaveValue("entrada");
  });
});
