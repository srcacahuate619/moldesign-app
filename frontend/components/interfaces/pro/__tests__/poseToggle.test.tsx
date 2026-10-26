import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ProAnalysisTabs } from "../ProAnalysisTabs";
import type { EvaluationResult } from "@/lib/types";
import real from "../../../../app/laboratorio/evaluacion/lectura-qa.json";

// The decorative orb requires IntersectionObserver; it is outside this interaction contract.
vi.mock("../LiquidOrb", () => ({ LiquidOrb: () => null }));

describe("Divulgación de controles de pose", () => {
  it("abre, cierra y vuelve a abrir conservando la pose elegida", () => {
    render(<ProAnalysisTabs status={null} structuralEvidenceResult={real as unknown as EvaluationResult} selectivityResult={null} moleculeId={null} taskId={real.task_id}/>);
    const pose=screen.getByRole("button", { name:"Ver controles físicos de la pose #2" });
    fireEvent.click(pose);
    expect(pose).toHaveAttribute("aria-pressed","true");
    expect(pose).toHaveAttribute("aria-expanded","true");
    const region=document.getElementById(pose.getAttribute("aria-controls")!)!;
    expect(region).toBeVisible();
    fireEvent.click(pose);
    expect(pose).toHaveAttribute("aria-expanded","false");
    expect(pose).toHaveAttribute("aria-pressed","true");
    expect(region).not.toBeVisible();
    fireEvent.click(pose);
    expect(region).toBeVisible();
    fireEvent.click(screen.getByRole("button",{name:"Ver controles físicos de la pose #3"}));
    expect(pose).toHaveAttribute("aria-pressed","false");
    expect(pose).toHaveAttribute("aria-expanded","false");
    expect(screen.getByRole("button",{name:"Ver controles físicos de la pose #3"})).toHaveAttribute("aria-expanded","true");
  });

  it("conserva el cierre al volver al área y empieza una nueva corrida con filas compactas", () => {
    const props={ status:null,structuralEvidenceResult:real as unknown as EvaluationResult,selectivityResult:null,moleculeId:null,taskId:real.task_id };
    const {rerender}=render(<ProAnalysisTabs {...props}/>);
    const first=screen.getByRole("button",{name:"Ver controles físicos de la pose #1"});
    expect(first).toHaveAttribute("aria-expanded","false");
    fireEvent.click(first);expect(first).toHaveAttribute("aria-expanded","true");
    fireEvent.click(first);expect(first).toHaveAttribute("aria-expanded","false");
    fireEvent.click(screen.getByRole("tab",{name:"Propiedades y estado químico"}));
    fireEvent.click(screen.getByRole("tab",{name:"Poses y controles"}));
    expect(screen.getByRole("button",{name:"Ver controles físicos de la pose #1"})).toHaveAttribute("aria-expanded","false");
    rerender(<ProAnalysisTabs {...props} taskId="another-run"/>);
    expect(screen.getByRole("button",{name:"Ver controles físicos de la pose #1"})).toHaveAttribute("aria-expanded","false");
  });
});
