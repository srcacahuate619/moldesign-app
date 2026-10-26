import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  locale: "es" as "es" | "en",
  user: { user_id: "qa2", email: "qa2@local" },
}));
vi.mock("../../context/LanguageContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../context/LanguageContext")>();
  const t = (key: string) => actual.TRANSLATIONS[state.locale][key] ?? key;
  return { ...actual, useLanguage: () => ({ locale: state.locale, t }) };
});
vi.mock("../../lib/auth", () => ({ useAuth: () => ({ user: state.user, isLoading: false }) }));
vi.mock("../../context/KeepAliveContext", () => ({ useKeepAliveActive: () => true }));
vi.mock("../../hooks/useApiUrl", () => ({ useApiUrl: () => "http://qa2.local" }));
vi.mock("../../hooks/useDownload", () => ({ useDownload: () => ({ initialized: true, engine: { state: "ready" }, retryEngine: vi.fn() }) }));
vi.mock("../../lib/tauri", () => ({ isDesktopRuntime: () => false }));
vi.mock("../../lib/api", () => ({
  getEvaluationHistory: vi.fn(async () => ({ items: [], total: 0, page: 1, page_size: 20 })),
  getUserStats: vi.fn(async () => null),
  getMoldex: vi.fn(async () => ({ results: [], total: 0 })),
  checkBlockchainHealth: vi.fn(async () => ({ available: false })),
  getProteinFile: vi.fn(), getPoseFile: vi.fn(), downloadCertificate: vi.fn(), downloadComplexFile: vi.fn(),
}));
vi.mock("../MoleculeViewer3D", () => ({ MoleculeViewer3D: () => null }));
vi.mock("../MoldexCard", () => ({ default: () => null }));
vi.mock("../MolecularComparison", () => ({ default: () => null }));
vi.mock("../PDFReportViewer", () => ({ PDFReportViewer: () => null }));
vi.mock("../CertificationModal", () => ({ CertificationModal: () => null }));
import { getMoldex } from "../../lib/api";
import HistoryPage from "../../app/history/page";
import MoldexPage from "../../app/moldex/page";

// QA2-001: se renderizan las dos pantallas reales con biblioteca vacía y los
// diccionarios del producto. Un texto de ranking heredado vuelve a fallar aquí.
describe.each(["es", "en"] as const)("origen del docking en %s", (locale) => {
  it.each([HistoryPage, MoldexPage])("identifica Vina sin atribuir el ranking a XGBoost (%#)", async (Page) => {
    state.locale = locale;
    render(<Page />);
    expect(await screen.findByText(locale === "es" ? "con AutoDock Vina" : "with AutoDock Vina")).toBeInTheDocument();
    expect(screen.queryByText(/XGBoost.*(?:reordena|re-ranks)/i)).not.toBeInTheDocument();
  });
});
it.each(["es", "en"] as const)("QA2-011: el filtro global de Moldex se traduce (%s)", async (locale) => {
  state.locale = locale;
  vi.mocked(getMoldex).mockResolvedValueOnce({ count: 1, total: 1, limit: 20, offset: 0, has_next: false, results: [{
    id: "mol-qa2", entry_id: "mol-qa2:run-qa2", name: "Ligando QA2", smiles: "CCO", smiles_hash: "abc", created_at: "2026-10-04T01:00:00Z", evaluated_at: null,
    target: { pdb_id: "1HSG", name: "Protease", family: "protease", hotspots: [], spearman_rho: null },
    metrics: { affinity: null, log_p: null, mw: null, tpsa: null, score: null, gnn_score: null, lipinski_pass: null, veber_pass: null },
    provenance: { task_id: "run-qa2", receptor_sha256: null, engine_version: null, random_seed: null, docking_protocol: null },
    scientific_warnings: [], hotspots_hit: [],
    blockchain: { certified: false, tx_signature: null, certified_task_id: null, certified_total_score: null, matches_current_run: null },
  }] });
  render(<MoldexPage />);
  expect(await screen.findByRole("button", { name: locale === "es" ? /^Todos$/ : /^All$/i })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "1HSG" })).toBeInTheDocument();
});
it.each(["es", "en"] as const)("QA2-014: el alcance del registro se presenta en el idioma elegido (%s)", async (locale) => {
  state.locale = locale;
  vi.mocked(getMoldex).mockResolvedValueOnce({ count: 1, total: 1, limit: 20, offset: 0, has_next: false, results: [{
    id: "mol-qa14", entry_id: "mol-qa14:run-qa14", name: "Ligando QA14", smiles: "CCO", smiles_hash: "abc", created_at: "2026-10-04T01:00:00Z", evaluated_at: null,
    target: { pdb_id: "1HSG", name: "Protease", family: "protease", hotspots: [], spearman_rho: null },
    metrics: { affinity: null, log_p: null, mw: null, tpsa: null, score: null, gnn_score: null, lipinski_pass: null, veber_pass: null },
    provenance: { task_id: "run-qa14", receptor_sha256: null, engine_version: null, random_seed: null, docking_protocol: null },
    scientific_warnings: [], hotspots_hit: [],
    blockchain: { certified: false, tx_signature: null, certified_task_id: null, certified_total_score: null, matches_current_run: null },
  }] });
  render(<MoldexPage />);
  expect(await screen.findByText(locale === "es"
    ? "El registro de devnet guarda un memo con el hash del SMILES, el score redondeado, el PDB, la fecha y la wallet. No acredita la integridad del informe, del receptor ni de las poses, no identifica la revisión del documento, no demuestra que la pose sea válida ni que la conclusión científica sea correcta, y no sustituye evidencia experimental."
    : "The devnet record stores a memo with the SMILES hash, the rounded score, the PDB, the date and the wallet. It does not attest to the integrity of the report, the receptor or the poses, does not identify the document's revision, does not establish that the pose is valid or the scientific conclusion is correct, and does not replace experimental evidence."
  )).toBeInTheDocument();
});