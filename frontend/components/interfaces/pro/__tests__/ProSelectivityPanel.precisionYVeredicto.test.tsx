import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../../../../lib/api", () => ({ getEvaluationResult: vi.fn(async () => null) }));
vi.mock("../../../../lib/proApi", () => ({ dockSingleAntiTarget: vi.fn(), saveSelectivityResults: vi.fn() }));
import { ProSelectivityPanel } from "../ProSelectivityPanel";
import { decimalesParaDistinguir, valorYCorte } from "../../../../lib/decimalesDeAlerta";
import { VEREDICTO_SIN_ALERTA, VEREDICTO_UMBRAL_REBASADO } from "../../../../lib/selectividadMargen";
import { pro } from "../../../../context/traducciones/pro";

// Revisión final de 1.0.4 (hERG): con la desigualdad estricta, −7,004 frente a −7,0 se escribía «−7,0 … −7,0».
// La desigualdad no cambia; se escribe con los decimales que dejan ver por qué se cumple. Y la ausencia de alerta
// no descarta un bloqueo: sólo dice que ninguna anti-diana evaluada cruzó el umbral.
const VINETA = /^\s*•\s*ALERTA /;

describe("decimales que distinguen el valor de su corte", () => {
  it("con un valor lejos del corte son los de siempre", () => {
    expect(decimalesParaDistinguir(-8.2, -7)).toBe(1);
    expect(valorYCorte(-8.2, -7)).toEqual({ valor: "-8.2", corte: "-7.0" });
  });

  it("aumentan hasta que dejan de escribirse igual", () => {
    expect(valorYCorte(-7.004, -7)).toEqual({ valor: "-7.004", corte: "-7.000" });
    expect(valorYCorte(-7.04, -7)).toEqual({ valor: "-7.04", corte: "-7.00" });
  });

  it("tienen tope: un empate exacto no los dispara", () => {
    expect(decimalesParaDistinguir(-7, -7)).toBe(6);
  });

  it("control negativo: un decimal fijo los escribiría iguales", () => {
    expect((-7.004).toFixed(1)).toBe((-7).toFixed(1));
  });
});

describe("panel de selectividad: precisión de la alerta y alcance del veredicto", () => {
  it("la alerta de −7,004 frente a −7,0 enseña los dos números distintos", async () => {
    render(<ProSelectivityPanel moleculeId={null} initialResult={{ off_targets: [
      { pdb_id: "5VA1", name: "hERG", threshold: -7, affinity: -7.004, status: "ok", sitio_adjudicado: true },
    ] }} />);
    await screen.findAllByText(VINETA);
    const texto = screen.getAllByText(VINETA)[0].textContent ?? "";
    expect(texto).toContain("-7.004 kcal/mol");
    expect(texto).toContain("-7.000 kcal/mol");
    expect(texto).not.toMatch(/\(-7\.0 kcal\/mol\) rebasó el umbral crítico \(-7\.0 kcal\/mol\)/);
  });

  it("lo que se guarda (y el informe PDF imprime) dice lo mismo que la pantalla", () => {
    // `selectivity_verdict` viaja con la corrida y el PDF lo escribe tal cual: si sólo la pantalla dijera que la
    // ausencia de alerta no descarta un bloqueo, el informe seguiría sin decirlo.
    expect(VEREDICTO_SIN_ALERTA).toBe(pro.es.pr_sel_threshold_clear);
    expect(VEREDICTO_UMBRAL_REBASADO).toBe(pro.es.pr_sel_threshold_review);
    expect(VEREDICTO_SIN_ALERTA).toContain("no descarta que el compuesto bloquee una diana");
    // Control negativo: la frase guardada antes no lo decía.
    expect("SIN ALERTA EN ESTE PANEL — Ningún anti-target rebasó el umbral definido").not.toContain("no descarta");
  });

  it("la ausencia de alerta dice que no descarta un bloqueo", async () => {
    render(<ProSelectivityPanel moleculeId={null} initialResult={{ off_targets: [
      { pdb_id: "7UL2", name: "OPRK1", category: "GPCR", threshold: -7, affinity: -6, status: "ok", sitio_adjudicado: false },
    ] }} />);
    await screen.findAllByText("OPRK1");
    const veredicto = await screen.findByText(/SIN ALERTA EN ESTE PANEL/);
    expect(veredicto.textContent).toContain("no descarta que el compuesto bloquee una diana");
    expect(veredicto.textContent).toContain("evaluado");
  });
});
