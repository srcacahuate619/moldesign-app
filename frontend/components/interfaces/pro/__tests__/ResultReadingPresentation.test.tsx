import React, { useState } from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { TRADUCCIONES_POR_SUPERFICIE } from "@/context/traducciones";
import { ResultReadingPresentation, ReadingReservations, ReadingHelp } from "../ResultReadingPresentation";
import { EvaluationEvidencePanel } from "../EvaluationEvidencePanel";
import { RunDataExplorer } from "../RunDataExplorer";
import type { EvaluationResult } from "@/lib/types";
import real from "../../../../app/laboratorio/evaluacion/lectura-qa.json";

vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ locale: "es", t: (key: string, values: Record<string, string | number> = {}) => {
  let message = TRADUCCIONES_POR_SUPERFICIE.es[key] ?? key;
  for (const [name, value] of Object.entries(values)) message = message.replace("{" + name + "}", String(value));
  return message;
} }) }));

function Selection() { const [pose, setPose] = useState("2"); return <label>Pose en revisión<input value={pose} onChange={e => setPose(e.target.value)}/></label>; }

describe("Lectura equilibrada de la evidencia", () => {
  it("conserva selección y datos sin mostrar controles de otras presentaciones ni ejecutar acciones", () => {
    const calculate = vi.fn();
    const result = { task_id: "RUN-A", is_pains: false, zero: 0, missing: null, nested: { evidence: [false, 0, null] } };
    const before = JSON.stringify(result);
    const { container } = render(<ResultReadingPresentation><Selection/><RunDataExplorer result={result}/><button onClick={calculate}>Calcular</button></ResultReadingPresentation>);
    const input = screen.getByLabelText("Pose en revisión");
    fireEvent.change(input, { target: { value: "7" } });
    const search = screen.getByRole("searchbox"); fireEvent.change(search, { target: { value: "nested" } });
    expect(container.querySelector("[data-reading]")).toHaveAttribute("data-reading", "balanced");
    expect(screen.getByLabelText("Pose en revisión")).toBe(input);
    expect(input).toHaveValue("7"); expect(search).toHaveValue("nested");
    expect(screen.getByText("nested", { exact: true })).toBeVisible();
    expect(screen.queryByText(/Presentación|Guiada|Compacta|organizaciones anteriores/i)).not.toBeInTheDocument();
    expect(calculate).not.toHaveBeenCalled(); expect(JSON.stringify(result)).toBe(before);
  });

  it("conserva un aviso crítico desconocido y su texto íntegro", () => {
    const text = "Primera condición. Segunda condición que limita el resultado; conservar false, 0 y null.";
    const items = [{ id: "notice-0", label: "Aviso crítico", code: "CODIGO_FUTURO", status: "missing" as const, detail: text }];
    const { container } = render(<ResultReadingPresentation><ReadingReservations items={items} legacy={[]}/></ResultReadingPresentation>);
    expect(screen.getByText(/Aviso crítico · CODIGO_FUTURO/)).toBeVisible();
    expect(screen.getByText(/Importante/)).toBeVisible();
    const details = container.querySelector("details")!; expect(details.open).toBe(false);
    fireEvent.click(details.querySelector("summary")!);
    expect(details.textContent).toContain(text);
    expect(items[0].detail).toBe(text);
  });

  it("usa el código y conserva la severidad declarada al cambiar la redacción", () => {
    const { rerender } = render(<ResultReadingPresentation><ReadingReservations items={[{ id:"notice-0", label:"Precaución", code:"CAJA_BUSQUEDA_AMPLIA", status:"review", detail:"Texto uno" }]} legacy={[]}/></ResultReadingPresentation>);
    expect(screen.getByText("Caja de búsqueda amplia; convergencia sin demostrar")).toBeVisible();
    rerender(<ResultReadingPresentation><ReadingReservations items={[{ id:"notice-0", label:"Precaución", code:"CAJA_BUSQUEDA_AMPLIA", status:"review", detail:"Texto dos, sin clasificar por palabras" }]} legacy={[]}/></ResultReadingPresentation>);
    expect(screen.getByText("Caja de búsqueda amplia; convergencia sin demostrar")).toBeVisible();
    expect(screen.queryByText(/Importante/)).not.toBeInTheDocument();
  });

  it("mantiene heredados contados sin reclasificarlos como críticos", () => {
    render(<ResultReadingPresentation><ReadingReservations items={[]} legacy={[{ id:"notice-1", label:"Heredado", detail:"Sin motor: revisión manual", status:"not_evaluated" }]}/></ResultReadingPresentation>);
    expect(screen.getByText("1 aviso heredado sin severidad declarada")).toBeVisible();
    expect(screen.queryByText(/Importante/)).not.toBeInTheDocument();
  });

  it("conserva la ausencia y el cero como estados distintos", () => {
    const empty = { ...real, docking_poses: null, affinity_kcal: null, structural_evidence: null } as unknown as EvaluationResult;
    const { rerender } = render(<ResultReadingPresentation><EvaluationEvidencePanel result={empty} target={null} compact/></ResultReadingPresentation>);
    expect(screen.getAllByText("Sin dato registrado", { exact: true })).toHaveLength(3);
    expect(screen.queryByText("0 / 0", { exact: true })).not.toBeInTheDocument();
    rerender(<ResultReadingPresentation><EvaluationEvidencePanel result={{ ...empty, affinity_kcal:0, docking_poses:[] }} target={null} compact/></ResultReadingPresentation>);
    expect(screen.getByText("0.00 kcal/mol", { exact:true })).toBeVisible();
    expect(screen.getByText("0", { exact:true })).toBeVisible();
  });

  it("muestra la explicación breve y mantiene el detalle a un clic", () => {
    const { container } = render(<ResultReadingPresentation><ReadingHelp area="properties"/></ResultReadingPresentation>);
    expect(screen.getByText(/Revisa primero el estado químico/)).toBeVisible();
    const details = container.querySelector("details")!;
    expect(details.open).toBe(false);
    fireEvent.click(details.querySelector("summary")!);
    expect(details.open).toBe(true);
    expect(details.textContent).toContain("La entrada y la especie acoplada pueden diferir");
  });
});