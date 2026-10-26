import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

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

    fireEvent.click(screen.getByText("Evidencia y procedencia"));
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

describe("la vía de péptidos se marca experimental (decisión del 2026-10-04)", () => {
  it("un resultado con transferencia peptídica lleva el aviso de que ESMFold no está validado", () => {
    render(
      <EvaluationEvidencePanel
        result={resultWithProvenance({
          ligand_state: {
            peptide_transfer: { status: "completed", coordinates_transferred: 15, coordinates_completed: 1 },
          },
        } as Partial<EvaluationResult>)}
        target={null}
      />,
    );
    expect(screen.getByTestId("peptido-experimental")).toHaveTextContent(/Experimental: ESMFold predice la estructura/);
    expect(screen.getByTestId("peptido-experimental")).toHaveTextContent(/no está validada/);
    expect(screen.getByTestId("peptido-experimental").closest("details")).toBeNull();
  });

  it("una molécula pequeña no lleva ese aviso (control)", () => {
    render(<EvaluationEvidencePanel result={resultWithProvenance()} target={null} />);
    expect(screen.queryByTestId("peptido-experimental")).toBeNull();
  });
});

describe("resumen inicial de la evaluación", () => {
  it("mantiene las reservas y límites visibles con la procedencia cerrada", () => {
    const fallback = "Familia 'protease' sin modelo validado — modelo universal usado.";
    render(<EvaluationEvidencePanel result={resultWithProvenance({
      affinity_kcal: -6.02,
      docking_poses: [
        { rank: 1, affinity: -6.02, rmsd_lb: 0, rmsd_ub: 0 },
        { rank: 2, affinity: -5.79, rmsd_lb: 1, rmsd_ub: 2 },
      ],
      in_applicability_domain: true,
      model_used: "universal",
      fallback_reason: fallback,
      structural_evidence: {
        version_schema: 1, stage_status: "passed", poses_produced: 2, poses_evaluated: 2, poses: [],
      },
      scientific_warnings: [
        { codigo: "MOTOR", severidad: "critica", mensaje: "El motor ejecutado difiere del solicitado." },
        { codigo: "NOTA", severidad: "info", mensaje: "Las afinidades se leyeron del registro." },
      ],
    } as Partial<EvaluationResult>)} target={null} />);

    expect(screen.getByRole("heading", { name: "Resumen de la evaluación" })).toBeInTheDocument();
    expect(screen.getByText("Revisión necesaria")).toBeVisible();
    expect(screen.getByText("Muestreo ambiguo")).toBeVisible();
    expect(screen.getByText(fallback)).toBeVisible();
    expect(screen.getAllByText("El motor ejecutado difiere del solicitado.")[0]).toBeVisible();
    expect(screen.getByText("Controles físicos superados: 2/2")).toBeVisible();
    expect(screen.getByText("Selectividad no evaluada")).toBeVisible();
    expect(screen.getByText("Reconstrucción por un tercero no demostrada")).toBeVisible();
    const record = screen.getByText("Evidencia y procedencia").closest("details")!;
    expect(record).not.toHaveAttribute("open");
    expect(within(record).getByText("Las afinidades se leyeron del registro.")).toBeInTheDocument();
    expect(within(record).getByText("Señal de docking").closest("details")).not.toHaveAttribute("open");
    expect(screen.queryByText("Trazas técnicas registradas")).toBeNull();
    expect(screen.queryByText("Pregunta del dossier")).toBeNull();
  });

  it("conserva el acceso a controles fallidos sin presentar aprobación física", () => {
    const openControls = vi.fn();
    render(<EvaluationEvidencePanel result={resultWithProvenance({
      affinity_kcal: -6,
      docking_poses: [{ rank: 1, affinity: -6, rmsd_lb: 0, rmsd_ub: 0 }],
      structural_evidence: {
        version_schema: 1, stage_status: "failed", poses_produced: 1, poses_evaluated: 1, poses: [],
      },
    } as Partial<EvaluationResult>)} target={null} onOpenPhysicalControls={openControls} />);

    expect(screen.getByText(/No priorizar el ligando ni iniciar cálculos posteriores/)).toBeVisible();
    expect(screen.getAllByText(/Al menos la pose principal falla/)[0]).toBeVisible();
    expect(screen.queryByText(/Controles físicos superados:/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /revisar controles/i }));
    expect(openControls).toHaveBeenCalledOnce();
  });
});

describe("compact summary chosen by the owner", () => {
  it("groups only unclassified legacy notices, preserving visible critical messages and access to every text", () => {
    render(<EvaluationEvidencePanel compact target={null} result={resultWithProvenance({ scientific_warnings: [
      "Legacy notice with an extensive explanation.",
      {codigo:"QA_CRITICAL",severidad:"critica",mensaje:"Critical warning must remain visible."},
    ] })}/>);
    const legacy = screen.getByText("Legacy notice with an extensive explanation.");
    const details = legacy.closest("details");
    expect(details).not.toHaveAttribute("open");
    expect(screen.getByText("1 aviso heredado sin severidad declarada")).toBeVisible();
    expect(screen.getByText("Critical warning must remain visible.")).toBeVisible();
    expect(screen.getByText("Critical warning must remain visible.").closest("details")).toBeNull();
    fireEvent.click(screen.getByText("1 aviso heredado sin severidad declarada"));
    expect(legacy).toBeVisible();
  });
});
