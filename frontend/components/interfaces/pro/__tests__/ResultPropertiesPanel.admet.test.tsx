import { beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { ProParametersTab, type EvaluationProperties } from "../ProParametersTab";
import { ResultReadingPresentation } from "../ResultReadingPresentation";

beforeAll(() => {
  vi.stubGlobal("IntersectionObserver", class {
    observe() {} unobserve() {} disconnect() {} takeRecords() { return []; }
  });
});

const missing: EvaluationProperties = {
  sa_score: 2.4,
  blood_viability_score: null, blood_solubility_logs: null,
  blood_ppb_category: null, blood_hia_permeable: null, blood_bbb_permeable: null,
  blood_cns_mpo: null, blood_bbb_motivo: null,
  blood_systemic_reactivity: [], blood_tabpfn_estado: "no_evaluado",
};
const populated: EvaluationProperties = {
  ...missing, blood_viability_score: 76, blood_solubility_logs: -2.75,
  blood_ppb_category: "high", blood_hia_permeable: true, blood_bbb_permeable: false,
  blood_cns_mpo: 3.21, blood_bbb_motivo: "Decisión registrada: polaridad elevada.",
  blood_systemic_reactivity: ["Inhibidor CYP2C9", "Sustrato CYP3A4"],
};
function view(result: EvaluationProperties) {
  return <ResultReadingPresentation><ProParametersTab result={result}/></ResultReadingPresentation>;
}
function openAdmet() {
  const disclosure = screen.getByText("Predicciones ADMET · experimental").closest("details")!;
  expect(disclosure.open).toBe(false);
  fireEvent.click(disclosure.querySelector("summary")!);
  expect(disclosure.open).toBe(true);
  return within(disclosure);
}

describe("ADMET en la presentación equilibrada · contrato anterior y procedencia", () => {
  it("conserva todos los valores, fuentes, motivo BBB y alertas guardadas", () => {
    render(view(populated));
    const panel = openAdmet();
    for (const text of ["76 / 100", "-2.75 logS", "Alta (>90 %)", "✓ Alta", "✗ No permeable", "3.21 / 6", "2.4 / 10", populated.blood_bbb_motivo!, ...populated.blood_systemic_reactivity!]) {
      expect(panel.getByText(text)).toBeVisible();
    }
    expect(panel.getByText("ADMET-AI · heurístico")).toBeVisible();
    expect(panel.getByText("ADMET-AI", { exact: true })).toBeVisible();
    expect(panel.getByText(/no equivalen a toxicidad clínica/)).toBeVisible();
    expect(panel.queryByText("TabPFN · no_evaluado")).not.toBeInTheDocument();
  });

  it("mantiene cero y false como resultados en lugar de tratarlos como ausencia", () => {
    render(view({ ...populated, sa_score: 0, blood_viability_score: 0,
      blood_solubility_logs: 0, blood_cns_mpo: 0, blood_hia_permeable: false }));
    const panel = openAdmet();
    for (const text of ["0 / 100", "0.00 logS", "0.00 / 6", "0.0 / 10", "✗ Baja", "✗ No permeable"]) {
      expect(panel.getByText(text)).toBeVisible();
    }
    expect(panel.queryByRole("status")).not.toBeInTheDocument();
  });

  it("explica la ausencia sin convertir los nulos en negativos ni ocultar descriptores", () => {
    render(view(missing));
    const panel = openAdmet();
    expect(panel.getByText("ADMET-AI no disponible")).toBeVisible();
    expect(panel.getByRole("status")).toHaveTextContent(/desactivado/);
    expect(panel.getByRole("status")).toHaveTextContent(/cargar el modelo/);
    expect(panel.getByRole("status")).toHaveTextContent(/no es un resultado desfavorable/);
    expect(panel.getByText("2.4 / 10")).toBeVisible();
    expect(panel.getAllByText("ADMET-AI no se ejecutó en esta corrida")).toHaveLength(2);
    expect(panel.queryByText("✗ Baja")).not.toBeInTheDocument();
    expect(panel.queryByText("✗ No permeable")).not.toBeInTheDocument();
    expect(panel.getAllByText("No registrado").length).toBeGreaterThanOrEqual(3);
  });

  it("distingue un registro parcial de la disponibilidad de ADMET-AI", () => {
    render(view({ ...missing, blood_cns_mpo: 2.75, blood_bbb_motivo: "Motivo conservado de una corrida anterior." }));
    const panel = openAdmet();
    expect(panel.getByText("Resultados parciales")).toBeVisible();
    expect(panel.getByText("ADMET-AI no disponible")).toBeVisible();
    expect(panel.getByText("2.75 / 6")).toBeVisible();
    expect(panel.getByText("Motivo conservado de una corrida anterior.")).toBeVisible();
    expect(panel.queryByText("Con resultado", { exact: true })).not.toBeInTheDocument();
  });

  it("un parámetro ausente no implica que ADMET-AI no se ejecutara si hay otras predicciones", () => {
    render(view({ ...populated, blood_viability_score: null, blood_hia_permeable: null }));
    const panel = openAdmet();
    expect(panel.getByText("Resultados parciales")).toBeVisible();
    expect(panel.getByText("Este parámetro no tiene un valor guardado.")).toBeVisible();
    expect(panel.getByText("-2.75 logS")).toBeVisible();
    expect(panel.queryByText("ADMET-AI no se ejecutó en esta corrida")).not.toBeInTheDocument();
    expect(panel.queryByText("ADMET-AI no disponible")).not.toBeInTheDocument();
  });

  it("no confunde una lista vacía de señales con el estado del clasificador histórico", () => {
    render(view({ ...populated, blood_systemic_reactivity: [] }));
    const panel = openAdmet();
    expect(panel.getByText(/No hay señales de reactividad guardadas/)).toBeVisible();
    expect(panel.getByText("TabPFN · estado histórico").closest("div")).toHaveTextContent("Sin evaluar");
    expect(panel.queryByText(/Sin señales CYP identificadas/)).not.toBeInTheDocument();
  });

  it("conserva los estados históricos y distingue una lista sin registrar", () => {
    const { rerender } = render(view({ ...missing, blood_systemic_reactivity: null, blood_tabpfn_estado: "fallo" }));
    const panel = openAdmet();
    expect(panel.getByText(/No se guardó el detalle de reactividad sistémica/)).toBeVisible();
    expect(panel.getByText("TabPFN · estado histórico").closest("div")).toHaveTextContent("Falló");
    rerender(view({ ...populated, blood_tabpfn_estado: "evaluado" }));
    expect(panel.getByText("Inhibidor CYP2C9")).toBeVisible();
    expect(panel.getByText("TabPFN · estado histórico").closest("div")).toHaveTextContent("Evaluado");
  });

  it("actualiza la vista al recibir un perfil sin volver a cerrar el desplegable", () => {
    const { rerender } = render(view(missing));
    const panel = openAdmet();
    rerender(view(populated));
    expect(panel.getByText("76 / 100")).toBeVisible();
    expect(panel.getByText("-2.75 logS")).toBeVisible();
    expect(panel.queryByText("ADMET-AI no disponible")).not.toBeInTheDocument();
    expect(panel.queryByRole("status")).not.toBeInTheDocument();
  });
});
