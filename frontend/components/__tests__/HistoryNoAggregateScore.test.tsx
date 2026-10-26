import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ locale: "es" as "es" | "en", user: { user_id: "qa2", email: "qa2@local" } }));
vi.mock("../../context/LanguageContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../context/LanguageContext")>();
  const t = (key: string) => actual.TRANSLATIONS[state.locale][key] ?? key;
  return { ...actual, useLanguage: () => ({ locale: state.locale, t }) };
});
vi.mock("../../lib/auth", () => ({ useAuth: () => ({ user: state.user, isLoading: false }) }));
vi.mock("../../context/KeepAliveContext", () => ({ useKeepAliveActive: () => true }));
vi.mock("../../lib/api", () => ({
  getEvaluationHistory: vi.fn(async () => ({ total: 1, page: 1, page_size: 20, items: [{
    molecule_id: "m1", task_id: "run-qa2", smiles: "CCO", target_pdb_id: "1HSG", status: "completed",
    total_score: 35.7, affinity_kcal: -6.57, molecular_weight: 46, qed: 0.82, lipinski_pass: true,
    created_at: "2026-10-04T01:32:00Z", protocolo_vigente: false, is_saved: true,
  }] })),
  getUserStats: vi.fn(async () => ({ total_evaluations: 1, completed_evaluations: 1, failed_evaluations: 0,
    best_score: 35.7, avg_score: 35.7, unique_targets: 1 })),
  downloadCertificate: vi.fn(),
}));
import { getEvaluationHistory } from "../../lib/api";
vi.mock("../../lib/history", () => ({ downloadRunReceipt: vi.fn(async () => {}) }));
import { downloadRunReceipt } from "../../lib/history";
import HistoryPage from "../../app/history/page";
import { TRANSLATIONS } from "../../context/LanguageContext";

describe.each(["es", "en"] as const)("QA2-007: historial sin score agregado (%s)", (locale) => {
  it("retira score y agregados, conservando afinidad, corrida y condición del protocolo", async () => {
    state.locale = locale;
    render(<HistoryPage />);
    await screen.findByText("-6.6 kcal/mol");
    expect(screen.getByText(/run-qa2…/)).toBeInTheDocument();
    expect(screen.getByText(locale === "es" ? "Protocolo anterior" : "Earlier protocol")).toBeInTheDocument();
    expect(screen.queryAllByText("35.7")).toHaveLength(0);
    expect(screen.queryByRole("columnheader", { name: /score/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /score/i })).toBeNull();
    expect(screen.queryByText(locale === "es" ? "Mejor score" : "Best score")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: locale === "es" ? "Afinidad" : "Affinity" }));
    await waitFor(() => expect(getEvaluationHistory).toHaveBeenLastCalledWith(1, 20, "affinity_kcal", "desc"));
  });
});

it("QA2-010: muestra las dos corridas y descarga el recibo de la fila elegida", async () => {
  state.locale = "es";
  const source = await getEvaluationHistory(1);
  const item = source.items[0];
  vi.mocked(getEvaluationHistory).mockResolvedValueOnce({ ...source, total: 2, items: [
    { ...item, task_id: "old-run-001", affinity_kcal: -6.1, blockchain_tx_id: "receipt-old" },
    { ...item, task_id: "new-run-002", affinity_kcal: -8.2, blockchain_tx_id: null },
  ] });
  render(<HistoryPage />);
  await screen.findByText("-6.1 kcal/mol");
  expect(screen.getByText("-8.2 kcal/mol")).toBeInTheDocument();
  expect(screen.getAllByRole("row")).toHaveLength(3);
  fireEvent.click(screen.getByRole("button", { name: /descargar recibo/i }));
  await waitFor(() => expect(downloadRunReceipt).toHaveBeenCalledWith("old-run-001"));
});
it("las corridas de una misma molécula se distinguen por hora y sólo la guardada lleva «Moldex»", async () => {
  // Moldex guarda EVALUACIONES: la insignia es de la corrida, no de la molécula. Y dos
  // corridas de la misma molécula el mismo día no pueden verse como una fila repetida.
  state.locale = "es";
  const source = await getEvaluationHistory(1);
  const item = source.items[0];
  vi.mocked(getEvaluationHistory).mockResolvedValueOnce({ ...source, total: 2, items: [
    { ...item, task_id: "run-guardada", is_saved: true, created_at: "2026-10-04T01:32:00Z" },
    { ...item, task_id: "run-sin-guardar", is_saved: false, created_at: "2026-10-04T05:47:00Z" },
  ] });
  render(<HistoryPage />);
  await screen.findByText(/run-guar…/);

  const filas = screen.getAllByRole("row").slice(1);
  expect(filas).toHaveLength(2);
  const insignia = TRANSLATIONS.es.pg_hist_promovida_moldex;
  expect(within(filas[0]).queryByTitle(insignia)).not.toBeNull();
  expect(within(filas[1]).queryByTitle(insignia)).toBeNull();
  const fecha = (fila: HTMLElement) => within(fila).getAllByRole("cell").at(-1)?.textContent ?? "";
  expect(fecha(filas[0])).toMatch(/\d{1,2}:\d{2}/);
  expect(fecha(filas[0])).not.toBe(fecha(filas[1]));
});
it.each(["es", "en"] as const)("QA2-016: el error de conexión usa el idioma de Historial (%s)", async (locale) => {
  state.locale = locale;
  vi.mocked(getEvaluationHistory).mockRejectedValueOnce(new Error("Error de conexión: no se pudo establecer contacto con el motor local de MolDesign. Revisa su estado en la aplicación y vuelve a intentarlo."));
  render(<HistoryPage />);
  expect(await screen.findByText(locale === "es"
    ? "Error de conexión: no se pudo establecer contacto con el motor local de MolDesign. Revisa su estado en la aplicación y vuelve a intentarlo."
    : "Connection error: the local MolDesign engine could not be reached. Check its status in the application and try again."
  )).toBeInTheDocument();
});