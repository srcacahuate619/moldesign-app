import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Moldex guarda EVALUACIONES, no moléculas. Una molécula (receptor + ligando) se
// evalúa varias veces en el mismo caso, y cada evaluación guardada es una ficha
// propia: se selecciona, se compara y carga sus archivos POR CORRIDA. Antes la
// lista se identificaba por `id` de molécula y la última evaluación pisaba a las
// guardadas.

const state = vi.hoisted(() => ({
  locale: "es" as "es" | "en",
  user: { user_id: "qa", email: "qa@local" },
}));
vi.mock("../../context/LanguageContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../context/LanguageContext")>();
  const t = (key: string) => actual.TRANSLATIONS[state.locale][key] ?? key;
  return { ...actual, useLanguage: () => ({ locale: state.locale, t }) };
});
vi.mock("../../lib/auth", () => ({ useAuth: () => ({ user: state.user, isLoading: false }) }));
vi.mock("../../context/KeepAliveContext", () => ({ useKeepAliveActive: () => true }));
vi.mock("../../hooks/useApiUrl", () => ({ useApiUrl: () => "http://qa.local" }));
vi.mock("../../hooks/useDownload", () => ({
  useDownload: () => ({ initialized: true, engine: { state: "ready" }, retryEngine: vi.fn() }),
}));
vi.mock("../../lib/tauri", () => ({ isDesktopRuntime: () => false }));
vi.mock("../../lib/api", () => ({
  getMoldex: vi.fn(),
  checkBlockchainHealth: vi.fn(async () => ({ available: false })),
  getProteinFile: vi.fn(async () => "PDB"),
  getPoseFile: vi.fn(async () => "SDF"),
  downloadCertificate: vi.fn(async () => undefined),
  downloadComplexFile: vi.fn(async () => undefined),
}));
vi.mock("react-virtuoso", () => ({
  Virtuoso: ({ data, itemContent }: { data: unknown[]; itemContent: (i: number, d: unknown) => React.ReactNode }) => (
    <div>{data.map((d, i) => <div key={i}>{itemContent(i, d)}</div>)}</div>
  ),
}));
vi.mock("../MoleculeViewer3D", () => ({ MoleculeViewer3D: () => null }));
vi.mock("../MolecularComparison", () => ({ default: () => null }));
vi.mock("../PDFReportViewer", () => ({ PDFReportViewer: () => null }));
vi.mock("../CertificationModal", () => ({ CertificationModal: () => null }));
// La tarjeta se sustituye por un botón por ficha: lo que se prueba es la identidad
// que la página le da y espera de vuelta, no el pintado de la tarjeta.
vi.mock("../MoldexCard", () => ({
  default: ({ molecule, onClick, isSelected }: {
    molecule: { entry_id: string; provenance: { task_id: string | null } };
    onClick: (id: string) => void;
    isSelected: boolean;
  }) => (
    <button
      type="button"
      data-testid={`ficha-${molecule.provenance.task_id}`}
      aria-pressed={isSelected}
      onClick={() => onClick(molecule.entry_id)}
    />
  ),
}));

import { getMoldex, getPoseFile, getProteinFile } from "../../lib/api";
import type { MoldexMolecule } from "../../lib/moldex";
import MoldexPage from "../../app/moldex/page";

function ficha(taskId: string, score: number): MoldexMolecule {
  return {
    id: "mol-1",
    entry_id: `mol-1:${taskId}`,
    saved_name: null,
    name: "Ligando",
    smiles: "CCO",
    smiles_hash: "abcd".repeat(16),
    created_at: "2026-10-05T01:00:00Z",
    evaluated_at: "2026-10-05T02:00:00Z",
    target: { pdb_id: "1HSG", name: "Protease", family: "protease", hotspots: [], spearman_rho: null },
    metrics: {
      affinity: -6, log_p: null, mw: null, tpsa: null, score, gnn_score: null,
      lipinski_pass: null, veber_pass: null,
    },
    provenance: { task_id: taskId, receptor_sha256: null, engine_version: null, random_seed: null, docking_protocol: null },
    scientific_warnings: [],
    hotspots_hit: [],
    blockchain: { certified: false, tx_signature: null, certified_task_id: null, certified_total_score: null, matches_current_run: null },
  };
}

function catalogo(...fichas: MoldexMolecule[]) {
  return { count: fichas.length, total: fichas.length, limit: 100, offset: 0, has_next: false, results: fichas };
}

describe("Moldex: una ficha por evaluación guardada", () => {
  beforeEach(() => {
    vi.mocked(getMoldex).mockReset();
    vi.mocked(getPoseFile).mockClear();
    vi.mocked(getProteinFile).mockClear();
    state.locale = "es";
  });

  it("muestra una ficha por evaluación aunque compartan molécula", async () => {
    vi.mocked(getMoldex).mockResolvedValue(catalogo(ficha("run-B", 55), ficha("run-A", 40)));

    render(<MoldexPage />);

    expect(await screen.findByTestId("ficha-run-A")).toBeInTheDocument();
    expect(screen.getByTestId("ficha-run-B")).toBeInTheDocument();
  });

  it("carga la pose de la CORRIDA de la ficha seleccionada, no la de la última evaluación", async () => {
    vi.mocked(getMoldex).mockResolvedValue(catalogo(ficha("run-B", 55), ficha("run-A", 40)));

    render(<MoldexPage />);
    await screen.findByTestId("ficha-run-A");
    await waitFor(() => expect(getPoseFile).toHaveBeenCalledWith("mol-1", "run-B"));

    fireEvent.click(screen.getByTestId("ficha-run-A"));

    await waitFor(() => expect(getPoseFile).toHaveBeenLastCalledWith("mol-1", "run-A"));
    // El receptor también pertenece a la corrida de la ficha.
    expect(getProteinFile).toHaveBeenLastCalledWith("mol-1", "run-A");
    expect(screen.getByTestId("ficha-run-A")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("ficha-run-B")).toHaveAttribute("aria-pressed", "false");
  });

  it("una ficha sin task_id no pide archivos de la proyección vigente", async () => {
    const legacy = ficha("sin-id", 40);
    legacy.provenance.task_id = null;
    vi.mocked(getMoldex).mockResolvedValue(catalogo(legacy));
    render(<MoldexPage />);
    await screen.findByTestId("ficha-null");
    expect(getProteinFile).not.toHaveBeenCalled();
    expect(getPoseFile).not.toHaveBeenCalled();
    expect(await screen.findByText(/La ficha no identifica una corrida/)).toBeInTheDocument();
  });

  it("al guardar una evaluación selecciona ESA ficha y no la primera de su molécula", async () => {
    vi.mocked(getMoldex).mockResolvedValue(catalogo(ficha("run-B", 55), ficha("run-A", 40)));

    render(<MoldexPage />);
    await screen.findByTestId("ficha-run-A");

    await act(async () => {
      window.dispatchEvent(new CustomEvent("moldex:invalidated", {
        detail: { moleculeId: "mol-1", taskId: "run-A" },
      }));
    });

    await waitFor(() =>
      expect(screen.getByTestId("ficha-run-A")).toHaveAttribute("aria-pressed", "true"),
    );
    expect(screen.getByTestId("ficha-run-B")).toHaveAttribute("aria-pressed", "false");
  });
});
