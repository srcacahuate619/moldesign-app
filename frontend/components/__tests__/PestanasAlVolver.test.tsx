import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

/**
 * Moldex e Historial no se desmontan al cambiar de pestaña. Al VOLVER refrescan en silencio (decisión del propietario,
 * 2026-10-10: nada de «recargas» visibles): lo que había se queda en pantalla, sin «cargando», hasta que llega lo nuevo,
 * y la ficha elegida en Moldex sigue elegida. Ocultas, no piden nada.
 */
const estado = vi.hoisted(() => ({ activa: true, user: { user_id: "qa", email: "qa@local" } }));
vi.mock("../../context/KeepAliveContext", () => ({ useKeepAliveActive: () => estado.activa }));
vi.mock("../../context/LanguageContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../context/LanguageContext")>();
  const t = (key: string) => actual.TRANSLATIONS.es[key] ?? key;
  return { ...actual, useLanguage: () => ({ locale: "es", t }) };
});
vi.mock("../../lib/auth", () => ({ useAuth: () => ({ user: estado.user, isLoading: false }) }));
vi.mock("../../hooks/useApiUrl", () => ({ useApiUrl: () => "http://qa.local" }));
vi.mock("../../hooks/useDownload", () => ({
  useDownload: () => ({ initialized: true, engine: { state: "ready" }, retryEngine: vi.fn() }),
}));
vi.mock("../../lib/tauri", () => ({ isDesktopRuntime: () => false }));
vi.mock("../../lib/api", () => ({
  getMoldex: vi.fn(),
  getEvaluationHistory: vi.fn(),
  getUserStats: vi.fn(async () => ({ total_evaluations: 1, completed_evaluations: 1, failed_evaluations: 0,
    best_score: null, avg_score: null, unique_targets: 1 })),
  checkBlockchainHealth: vi.fn(async () => ({ available: false })),
  getProteinFile: vi.fn(async () => "PDB"),
  getPoseFile: vi.fn(async () => "SDF"),
  downloadCertificate: vi.fn(async () => undefined),
  downloadComplexFile: vi.fn(async () => undefined),
  mensajeDelError: (e: unknown) => String(e),
}));
vi.mock("../../lib/history", () => ({ downloadRunReceipt: vi.fn(async () => {}) }));
vi.mock("react-virtuoso", () => ({
  Virtuoso: ({ data, itemContent }: { data: unknown[]; itemContent: (i: number, d: unknown) => React.ReactNode }) => (
    <div>{data.map((d, i) => <div key={i}>{itemContent(i, d)}</div>)}</div>
  ),
}));
vi.mock("../MoleculeViewer3D", () => ({ MoleculeViewer3D: () => null }));
vi.mock("../MolecularComparison", () => ({ default: () => null }));
vi.mock("../PDFReportViewer", () => ({ PDFReportViewer: () => null }));
vi.mock("../CertificationModal", () => ({ CertificationModal: () => null }));
vi.mock("../MoldexCard", () => ({
  default: ({ molecule, onClick, isSelected }: {
    molecule: { entry_id: string; provenance: { task_id: string | null } };
    onClick: (id: string) => void;
    isSelected: boolean;
  }) => (
    <button type="button" data-testid={`ficha-${molecule.provenance.task_id}`} aria-pressed={isSelected}
      onClick={() => onClick(molecule.entry_id)} />
  ),
}));

import { getEvaluationHistory, getMoldex } from "../../lib/api";
import type { MoldexMolecule } from "../../lib/moldex";
import type { HistoryResponse } from "../../lib/types";
import MoldexPage from "../../app/moldex/page";
import HistoryPage from "../../app/history/page";

function ficha(taskId: string): MoldexMolecule {
  return {
    id: `mol-${taskId}`, entry_id: `mol:${taskId}`, saved_name: null, name: "Ligando", smiles: "CCO",
    smiles_hash: "abcd".repeat(16), created_at: "2026-10-05T01:00:00Z", evaluated_at: "2026-10-05T02:00:00Z",
    target: { pdb_id: "1HSG", name: "Protease", family: "protease", hotspots: [], spearman_rho: null },
    metrics: { affinity: -6, log_p: null, mw: null, tpsa: null, score: 40, gnn_score: null, lipinski_pass: null, veber_pass: null },
    provenance: { task_id: taskId, receptor_sha256: null, engine_version: null, random_seed: null, docking_protocol: null },
    scientific_warnings: [], hotspots_hit: [],
    blockchain: { certified: false, tx_signature: null, certified_task_id: null, certified_total_score: null, matches_current_run: null },
  };
}
const catalogo = (...fichas: MoldexMolecule[]) => ({ count: fichas.length, total: fichas.length, limit: 100, offset: 0, has_next: false, results: fichas });

function historial(...corridas: [string, number][]): HistoryResponse {
  return { total: corridas.length, page: 1, page_size: 20, items: corridas.map(([taskId, afinidad]) => ({
    molecule_id: `m-${taskId}`, task_id: taskId, smiles: "CCO", target_pdb_id: "1HSG", status: "completed",
    total_score: null, affinity_kcal: afinidad, molecular_weight: 46, qed: 0.8, lipinski_pass: true,
    created_at: "2026-10-04T01:32:00Z", protocolo_vigente: true, is_saved: false,
  })) } as unknown as HistoryResponse;
}

/** Una promesa que se resuelve cuando la prueba quiere: así se ve qué hay en pantalla MIENTRAS llega lo nuevo. */
function diferida<T>() {
  let resolver!: (valor: T) => void;
  const promesa = new Promise<T>((r) => { resolver = r; });
  return { promesa, resolver };
}

beforeEach(() => {
  estado.activa = true;
  estado.user = { user_id: "qa", email: "qa@local" };
  vi.mocked(getMoldex).mockReset();
  vi.mocked(getEvaluationHistory).mockReset();
});

describe("Historial: cambiar el orden sin parpadeo", () => {
  it("conserva la tabla y sus filas mientras llega el nuevo orden", async () => {
    vi.mocked(getEvaluationHistory).mockResolvedValueOnce(historial(["run-A", -8.3], ["run-B", -6.6]));
    render(<HistoryPage />);
    const tabla = await screen.findByRole("table");
    const filas = () => [...tabla.querySelectorAll("tbody tr")].map((fila) => fila.textContent);
    const ordenInicial = filas();
    const nueva = diferida<HistoryResponse>();
    vi.mocked(getEvaluationHistory).mockReturnValueOnce(nueva.promesa);

    fireEvent.click(screen.getByRole("button", { name: "Afinidad" }));
    expect(getEvaluationHistory).toHaveBeenLastCalledWith(1, 20, "affinity_kcal", "desc");
    expect(screen.getByRole("table")).toBe(tabla);
    expect(filas()).toEqual(ordenInicial);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
    expect(tabla.closest("[aria-busy]")).toHaveAttribute("aria-busy", "true");

    await act(async () => { nueva.resolver(historial(["run-B", -6.6], ["run-A", -8.3])); });
    expect(screen.getByRole("table")).toBe(tabla);
    expect(filas()).toEqual([...ordenInicial].reverse());
    expect(tabla.closest("[aria-busy]")).toHaveAttribute("aria-busy", "false");
  });

  it("al alternar rápido ignora la respuesta del orden que ya se abandonó", async () => {
    vi.mocked(getEvaluationHistory).mockResolvedValueOnce(historial(["run-inicial", -6.6]));
    render(<HistoryPage />);
    await screen.findByText("-6.6 kcal/mol");
    const afinidad = diferida<HistoryResponse>();
    const fecha = diferida<HistoryResponse>();
    vi.mocked(getEvaluationHistory).mockReturnValueOnce(afinidad.promesa).mockReturnValueOnce(fecha.promesa);

    fireEvent.click(screen.getByRole("button", { name: "Afinidad" }));
    fireEvent.click(screen.getByRole("button", { name: "Fecha" }));
    await act(async () => { fecha.resolver(historial(["run-reciente", -7.2])); });
    await act(async () => { afinidad.resolver(historial(["run-antigua", -8.3])); });
    expect(screen.getByText("-7.2 kcal/mol")).toBeInTheDocument();
    expect(screen.queryByText("-8.3 kcal/mol")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fecha" })).toHaveAttribute("aria-pressed", "true");
  });

  it("si la consulta falla, conserva los datos disponibles y muestra el error", async () => {
    vi.mocked(getEvaluationHistory).mockResolvedValueOnce(historial(["run-A", -6.6]));
    render(<HistoryPage />);
    const tabla = await screen.findByRole("table");
    vi.mocked(getEvaluationHistory).mockRejectedValueOnce(new Error("Sin conexión"));
    fireEvent.click(screen.getByRole("button", { name: "Afinidad" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Sin conexión");
    expect(screen.getByRole("table")).toBe(tabla);
    expect(screen.getByText("-6.6 kcal/mol")).toBeInTheDocument();
    expect(tabla.closest("[aria-busy]")).toHaveAttribute("aria-busy", "false");
  });

  it("al cambiar de cuenta no conserva las filas del usuario anterior", async () => {
    vi.mocked(getEvaluationHistory).mockResolvedValueOnce(historial(["run-privada", -6.6]));
    const { rerender } = render(<HistoryPage />);
    await screen.findByText("-6.6 kcal/mol");
    const nueva = diferida<HistoryResponse>();
    vi.mocked(getEvaluationHistory).mockReturnValueOnce(nueva.promesa);
    estado.user = { user_id: "otra-cuenta", email: "otra@local" };
    rerender(<HistoryPage />);

    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("-6.6 kcal/mol")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
    await act(async () => { nueva.resolver(historial(["run-propia", -7.2])); });
    expect(screen.getByText("-7.2 kcal/mol")).toBeInTheDocument();
  });
});

describe("al volver a la pestaña", () => {
  it("Moldex: oculta no pide nada; al volver la lista se queda mientras llega la nueva y la ficha elegida sigue elegida", async () => {
    vi.mocked(getMoldex).mockResolvedValue(catalogo(ficha("run-A"), ficha("run-B")));
    const { rerender } = render(<MoldexPage />);
    fireEvent.click(await screen.findByTestId("ficha-run-B"));
    expect(screen.getByTestId("ficha-run-B")).toHaveAttribute("aria-pressed", "true");
    const llamadas = vi.mocked(getMoldex).mock.calls.length;

    estado.activa = false;
    await act(async () => { rerender(<MoldexPage />); });
    expect(vi.mocked(getMoldex).mock.calls.length).toBe(llamadas);

    const nueva = diferida<ReturnType<typeof catalogo>>();
    vi.mocked(getMoldex).mockReturnValueOnce(nueva.promesa as never);
    estado.activa = true;
    await act(async () => { rerender(<MoldexPage />); });
    expect(vi.mocked(getMoldex).mock.calls.length).toBe(llamadas + 1);
    // Mientras llega: la lista de antes, sin pantalla de carga.
    expect(screen.getByTestId("ficha-run-B")).toHaveAttribute("aria-pressed", "true");

    await act(async () => { nueva.resolver(catalogo(ficha("run-C"), ficha("run-A"), ficha("run-B"))); });
    expect(await screen.findByTestId("ficha-run-C")).toBeInTheDocument();
    expect(screen.getByTestId("ficha-run-B")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByTestId("ficha-run-C")).toHaveAttribute("aria-pressed", "false");
  });

  it("Historial: una evaluación hecha mientras tanto aparece al volver, sin «cargando» encima de la tabla", async () => {
    vi.mocked(getEvaluationHistory).mockResolvedValue(historial(["run-vieja", -6.57]));
    const { rerender } = render(<HistoryPage />);
    await screen.findByText("-6.6 kcal/mol");
    const llamadas = vi.mocked(getEvaluationHistory).mock.calls.length;

    estado.activa = false;
    await act(async () => { rerender(<HistoryPage />); });
    expect(vi.mocked(getEvaluationHistory).mock.calls.length).toBe(llamadas);

    const nueva = diferida<HistoryResponse>();
    vi.mocked(getEvaluationHistory).mockReturnValueOnce(nueva.promesa);
    estado.activa = true;
    await act(async () => { rerender(<HistoryPage />); });
    expect(vi.mocked(getEvaluationHistory).mock.calls.length).toBe(llamadas + 1);
    expect(screen.getByText("-6.6 kcal/mol")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();

    await act(async () => { nueva.resolver(historial(["run-nueva", -7.21], ["run-vieja", -6.57])); });
    await waitFor(() => expect(screen.getByText("-7.2 kcal/mol")).toBeInTheDocument());
  });
});
