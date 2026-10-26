import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
vi.mock("../../../../lib/api", () => ({ getEvaluationResult: vi.fn(async () => null) }));
vi.mock("../../../../lib/proApi", () => ({ dockSingleAntiTarget: vi.fn(), saveSelectivityResults: vi.fn() }));
import { ProSelectivityPanel } from "../ProSelectivityPanel";
describe("cobertura de anti-dianas pedidas y acopladas", () => {
  it("muestra también una diana opcional acoplada y distingue una desconocida sin afinidad", async () => {
    render(<ProSelectivityPanel moleculeId={null} initialResult={{ off_targets: [
      { pdb_id: "5VA1", name: "hERG", affinity: -7, status: "ok" },
      { pdb_id: "EXTRA", name: "Opcional", category: "GPCR", threshold: -7, affinity: -6, status: "ok" },
      { pdb_id: "DESCONOCIDA", name: "DESCONOCIDA", affinity: null, status: "not_evaluated", reason: "No existe" },
    ] }} />);
    expect(await screen.findByText(/Anti-dianas solicitadas:/)).toHaveTextContent("5VA1, EXTRA, DESCONOCIDA");
    const actual = screen.getByText(/Anti-dianas acopladas:/);
    expect(actual).toHaveTextContent("5VA1, EXTRA");
    expect(actual).not.toHaveTextContent("DESCONOCIDA");
    expect(screen.getAllByText("Opcional").length).toBeGreaterThan(0);
  });
});
