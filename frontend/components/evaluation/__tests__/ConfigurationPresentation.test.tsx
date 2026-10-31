import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ConfigurationInputs, ConfigurationPresentation, ConfigurationSystem } from "../ConfigurationPresentation";
import { PreparationPanel } from "../PreparationPanel";
import { EstimacionDeCorrida } from "../EstimacionDeCorrida";
import type { PreflightSummary, CaseStructuralSystem } from "../../../lib/cases/types";
import type { PreflightReport } from "../../../lib/preflight";
import { resultados } from "../../../context/traducciones/resultados";
import { pro } from "../../../context/traducciones/pro";
import { casos } from "../../../context/traducciones/casos";
import { comun } from "../../../context/traducciones/comun";
import { evaluacion } from "../../../context/traducciones/evaluacion";

const mocks = vi.hoisted(() => ({ locale: "es" as "es" | "en", estimate: vi.fn() }));
vi.mock("../../../lib/api", () => ({ estimarCorrida: mocks.estimate, getAuthHeaders: () => ({}) }));
vi.mock("../../../context/LanguageContext", () => ({ useLanguage: () => ({
  locale: mocks.locale,
  t: (key: string, params: Record<string, string | number> = {}) => {
    const words: Record<string, string> = { ...pro[mocks.locale], ...casos[mocks.locale], ...comun[mocks.locale], ...evaluacion[mocks.locale], ...resultados[mocks.locale], se_gen_protocol: mocks.locale === "es" ? "Protocolo" : "Protocol", se_phys_count_skip: mocks.locale === "es" ? "sin evaluar" : "not evaluated" };
    return (words[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`));
  },
}) }));

const smiles = "CC(C)Cc1ccc([C@H](C)C(=O)O)cc1";
const fingerprint = `sha256:${"a".repeat(64)}`;
const summary: PreflightSummary = {
  fingerprint, inputDocument: JSON.stringify({ target_pdb_id: "1CX2", chain: "A" }), generatedAt: "2026-10-24T12:00:00Z", schemaVersion: 3,
  executionRoute: "docking_vina", blockers: [], warnings: ["REVISAR"], notEvaluated: ["NO_MEDIDO"],
  receptorLabel: "1CX2 · cadena A", ligandLabel: smiles, gridLabel: "descripción antigua de la caja",
  executionConfig: { gridCenter: [-24.664125, 0, 16.451], gridSize: [31.1, 24.5, 18.25], customHotspots: ["A:TYR385", "A:ARG120"], dockingEngine: "vina", exhaustiveness: 4, numPoses: 9, seed: 0, conformers: 5 },
};
const system: CaseStructuralSystem = {
  lockedAt: "2026-10-24T12:00:00Z", sourceRunTaskId: "66e26595-6f90-492e-8eeb-ec6a9d057fb1", inputFingerprint: fingerprint,
  receptor: { pdbId: "1CX2", chain: "A", origin: "curado" },
  grid: { center: [-24.664125, 0, 16.451], size: [31.1, 24.5, 18.25] }, customHotspots: [], dockingEngine: "vina", exhaustiveness: 4, numPoses: 9, conformers: 5,
};
afterEach(() => { cleanup(); mocks.locale = "es"; mocks.estimate.mockReset(); });

describe("Configuración completa y legible", () => {
  it.each(["es", "en"] as const)("conserva SMILES, caja no cúbica, cero y protocolo completos en %s", locale => {
    mocks.locale = locale;
    render(<ConfigurationPresentation><ConfigurationInputs summary={summary} /></ConfigurationPresentation>);
    expect(screen.getByText(smiles, { exact: true })).toBeVisible();
    expect(screen.queryByText(summary.gridLabel, { exact: false })).not.toBeInTheDocument();
    expect(screen.getByRole("table", { name: pro[locale].pr_preflight_effective_box })).toBeVisible();
    for (const number of ["-24.664125", "16.451", "31.1", "24.5", "18.25"]) expect(screen.getByRole("cell", { name: number })).toBeVisible();
    expect(screen.getAllByText("0", { exact: true })).toHaveLength(2); // centro Y y semilla, ambos válidos
    expect(screen.getByText(resultados[locale].cf_requested_poses)).toBeVisible();
    for (const number of ["4", "9", "5"]) expect(screen.getByText(number, { exact: true })).toBeVisible();
    expect(screen.getByText("A:TYR385, A:ARG120", { exact: true })).toBeVisible();
  });

  it("mantiene el identificador de origen íntegro y las dimensiones distintas", () => {
    render(<ConfigurationSystem system={system} provisional={false} chains={null} />);
    expect(screen.getByText(system.sourceRunTaskId, { exact: true })).toBeVisible();
    expect(screen.getByText("31.1 × 24.5 × 18.25 Å", { exact: true })).toBeVisible();
    expect(screen.queryByText(/66e26595…/)).toBeNull();
  });

  it("muestra la huella entera y conserva las reservas del resumen guardado", () => {
    render(<ConfigurationPresentation><PreparationPanel report={null} summary={summary} loading={false} error={null} stale={false} conformers={5} decisions={[]} onAcknowledge={vi.fn()} /></ConfigurationPresentation>);
    expect(screen.getByText(fingerprint, { exact: true })).toBeVisible();
    expect(screen.getByText(/1 advertencia/)).toBeVisible();
    expect(screen.getByText(/1 sin evaluar/i)).toBeVisible();
  });

  it("no reutiliza el resumen cuando los inputs han cambiado", () => {
    render(<ConfigurationPresentation><PreparationPanel report={null} summary={summary} loading={false} error={null} stale conformers={5} decisions={[]} onAcknowledge={vi.fn()} /></ConfigurationPresentation>);
    expect(screen.queryByText(smiles, { exact: true })).toBeNull();
    expect(screen.queryByText(fingerprint, { exact: true })).toBeNull();
  });

  it("un resumen antiguo sin configuración no inventa coordenadas ni protocolo", () => {
    render(<ConfigurationInputs summary={{ ...summary, executionConfig: undefined }} />);
    expect(screen.getByText(comun.es.c_no_definido, { exact: true })).toBeVisible();
    expect(screen.getByText(resultados.es.cf_legacy_box)).toBeVisible();
    expect(screen.getByText(resultados.es.cf_missing_protocol)).toBeVisible();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("identifica el SMILES de entrada cuando no hay uno canónico y declara todas las cadenas", () => {
    const report = { receptor: { pdb_id: "1CX2", chain: "A", site_chains: ["B", "A"] }, ligand: { canonical_smiles: null, input_smiles: smiles }, effective_config: { grid_center: [1, 2, 3], grid_size: [20, 25, 30], docking_engine: "vina", exhaustiveness: 8, num_poses: 6, seed: 42, hotspots: [] } } as unknown as PreflightReport;
    render(<ConfigurationInputs report={report} />);
    expect(screen.getByText("1CX2 · cadenas A+B", { exact: true })).toBeVisible();
    expect(screen.getByText(smiles, { exact: true })).toBeVisible();
    expect(screen.getByText(resultados.es.cf_input_smiles)).toBeVisible();
  });

  it("deja las etapas de duración abiertas y conserva apoyo, reservas y coste inicial", async () => {
    mocks.estimate.mockResolvedValue({ segundos_min: 60, segundos_max: 180, apoyo: "modelo", detalle_apoyo: "Modelo de otro equipo.", etapas: [{ etapa: "Preparación", segundos_min: 2, segundos_max: 5, nota: "Una vez por ligando." }, { etapa: "Acoplamiento", segundos_min: 58, segundos_max: 175, nota: "Cinco confórmeros." }], una_vez: { etapa: "Receptor", segundos_min: 9, segundos_max: 26, nota: "Se prepara una sola vez." }, avisos: ["Podría superar el plazo."], ligandos: 1 });
    const view = render(<ConfigurationPresentation><EstimacionDeCorrida exhaustiveness={4} conformers={5} /></ConfigurationPresentation>);
    expect(await screen.findByText("1 min – 3 min", { exact: true })).toBeVisible();
    for (const text of ["Preparación", "Acoplamiento", "Cinco confórmeros."]) expect(screen.getByText(text, { exact: true })).toBeVisible();
    expect(screen.getByText(/Modelo de otro equipo/)).toBeVisible();
    expect(screen.getByText(/9 s – 26 s/)).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Podría superar el plazo.");
    expect(view.container.querySelector("details")).toBeNull();
    expect(screen.queryByRole("button", { name: /de qué se compone/i })).toBeNull();
  });
});
