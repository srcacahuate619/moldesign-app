import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { EvaluationResult } from "../../../../lib/types";
import { EvaluationEvidencePanel } from "../EvaluationEvidencePanel";

function resultWithProvenance(overrides: Partial<EvaluationResult> = {}): EvaluationResult {
  return {
    id: "result-1",
    molecule_id: "molecule-1",
    receptor_sha256: "a".repeat(64),
    receptor_path: "C:/Users/Alice/experimentos/privado/receptor.pdbqt",
    docking_protocol: {
      contract: "docking_protocol/v1",
      conformers_requested: 5,
      conformers_generated: 3,
      engine: "AutoDock Vina 1.2.5",
      exhaustiveness: 16,
      num_poses: 9,
      seed: 42,
      conformer_warnings: ["2 conformaciones no convergieron"],
    },
    scientific_warnings: [],
    ...overrides,
  } as EvaluationResult;
}

describe("procedencia reproducible de la evaluación", () => {
  it("muestra hash y protocolo sin filtrar la ruta local", () => {
    render(<EvaluationEvidencePanel result={resultWithProvenance()} target={null} />);

    expect(screen.getByRole("heading", { name: /procedencia reproducible/i })).toBeInTheDocument();
    expect(screen.getByText("a".repeat(64))).toBeInTheDocument();
    expect(screen.getByText(/3 de 5 conformaciones/i)).toBeInTheDocument();
    expect(screen.getByText(/AutoDock Vina 1\.2\.5/i)).toBeInTheDocument();
    expect(screen.queryByText(/Users\/Alice|experimentos\/privado/i)).not.toBeInTheDocument();
  });

  it("declara la ausencia en corridas anteriores sin inventar procedencia", () => {
    render(
      <EvaluationEvidencePanel
        result={resultWithProvenance({
          receptor_sha256: null,
          receptor_path: null,
          docking_protocol: null,
        })}
        target={null}
      />,
    );

    expect(screen.getAllByText(/no registrado en esta corrida/i).length).toBeGreaterThanOrEqual(2);
  });
});
