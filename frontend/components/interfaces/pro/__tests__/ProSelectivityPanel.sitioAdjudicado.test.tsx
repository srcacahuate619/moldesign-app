import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../../../../lib/api", () => ({ getEvaluationResult: vi.fn(async () => null) }));
vi.mock("../../../../lib/proApi", () => ({ dockSingleAntiTarget: vi.fn(), saveSelectivityResults: vi.fn() }));
import { ProSelectivityPanel } from "../ProSelectivityPanel";

// D-09 de la investigación de 1.0.4: la alerta sale igual, y si el panel declara el sitio sin adjudicar, se dice que
// mide sólo la afinidad a esa caja. Un resultado sin el campo (anterior, o de una anti-diana propia) no se afirma.
const VINETA = /^\s*•\s*ALERTA /;
const alertas = () => screen.getAllByText(VINETA).map((nodo) => nodo.textContent ?? "");

describe("alertas de anti-dianas y sitio adjudicado", () => {
  it("añade el aviso sólo a la alerta cuyo sitio no está adjudicado", async () => {
    render(<ProSelectivityPanel moleculeId={null} initialResult={{ off_targets: [
      { pdb_id: "5VA1", name: "hERG", threshold: -7, affinity: -8, status: "ok", sitio_adjudicado: true },
      { pdb_id: "7UL2", name: "OPRK1", category: "GPCR", threshold: -7, affinity: -8, status: "ok", sitio_adjudicado: false },
      { pdb_id: "PROPIA", name: "Propia", category: "Custom", threshold: -7, affinity: -8, status: "ok" },
    ] }} />);
    await screen.findAllByText(VINETA);

    const textos = alertas();
    expect(textos).toHaveLength(3);
    const de = (nombre: string) => textos.find((t) => t.includes(`ALERTA ${nombre}:`)) ?? "";
    expect(de("OPRK1")).toContain("Sitio no adjudicado: no se ha comprobado que la caja corresponda al sitio del mecanismo");
    expect(de("OPRK1")).toContain("refleja sólo el score de Vina en esa caja");
    expect(de("hERG")).not.toContain("Sitio no adjudicado");
    expect(de("Propia")).not.toContain("Sitio no adjudicado");
  });

  it("el empate exacto con el umbral no alerta, como en el backend y el PDF", async () => {
    render(<ProSelectivityPanel moleculeId={null} initialResult={{ off_targets: [
      { pdb_id: "7UL2", name: "OPRK1", category: "GPCR", threshold: -7, affinity: -7, status: "ok", sitio_adjudicado: false },
      { pdb_id: "5VA1", name: "hERG", threshold: -7, affinity: -7.01, status: "ok", sitio_adjudicado: true },
    ] }} />);
    await screen.findAllByText(VINETA);
    const textos = alertas();
    expect(textos).toHaveLength(1);
    expect(textos[0]).toContain("ALERTA hERG:");
  });

  it("sin rebasar el umbral no hay alerta ni aviso", async () => {
    render(<ProSelectivityPanel moleculeId={null} initialResult={{ off_targets: [
      { pdb_id: "7UL2", name: "OPRK1", category: "GPCR", threshold: -7, affinity: -6, status: "ok", sitio_adjudicado: false },
    ] }} />);
    await screen.findAllByText("OPRK1");
    expect(screen.queryByText(VINETA)).toBeNull();
    expect(screen.queryByText(/Sitio no adjudicado/)).toBeNull();
  });
});
