import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { EvaluationResult } from "../../../lib/types";
import { PipelineDeLaCorrida } from "../PipelineDeLaCorrida";

function resultado(parcial: Partial<EvaluationResult> = {}): EvaluationResult {
  return {
    stacking_effective_weights: { vina: 1, xgb: 0, gnn: 0, clgnn: 0 },
    m5_protocol_id: null, m5_score: null, m5_scientific_status: null,
    ...parcial,
  } as EvaluationResult;
}

describe("un solo protocolo utilizado", () => {
  it.each(["default", "gpcr", "protease", "kinase", "nuclear_receptor", "soluble_enzyme", "metaloenzyme"])(
    "aplica la misma regla a cualquier familia: %s", (familia) => {
      const { container } = render(<PipelineDeLaCorrida resultado={resultado({
        target_family: familia, m5_scientific_status: "REVIEW_OUT_OF_VALIDATED_TARGET",
      })} />);
      expect(screen.getByRole("heading", { name: "Protocolo utilizado: M4" })).toBeVisible();
      expect(screen.getByText(/Protocolo general de evaluación: reúne los resultados del docking/)).toBeVisible();
      expect(container.textContent).not.toMatch(/M5/);
    },
  );
  it.each([null, "REVIEW_OUT_OF_VALIDATED_TARGET", "REVIEW_OUT_OF_VALIDATED_STRUCTURE",
    "NOT_EVALUATED_MISSING_COMPONENT", "NOT_EVALUATED_PROTOCOL_NOT_EXECUTED", "BLOCKED_PROTOCOL_NOT_AVAILABLE"])(
    "identifica M4 sin mencionar M5 cuando su estado es %s", (estado) => {
      const { container } = render(<PipelineDeLaCorrida resultado={resultado({
        m5_scientific_status: estado, ums_warhead: 0.8833,
      })} />);
      expect(screen.getByRole("heading", { name: "Protocolo utilizado: M4" })).toBeVisible();
      expect(container.textContent).not.toMatch(/M5/);
      expect(screen.queryByText("Detalles del protocolo")).not.toBeInTheDocument();
    },
  );

  it("no identifica un protocolo a partir de la familia o de un aviso", () => {
    const { container } = render(<PipelineDeLaCorrida resultado={resultado({
      stacking_effective_weights: null, target_family: "protease",
      m5_scientific_status: "REVIEW_OUT_OF_VALIDATED_TARGET",
    })} />);
    expect(screen.getByRole("heading", { name: "Protocolo utilizado: no registrado" })).toBeVisible();
    expect(container.textContent).not.toMatch(/M4|M5/);
  });

  it("identifica únicamente M5-Zn cuando un perfil produjo un resultado", () => {
    const { container } = render(<PipelineDeLaCorrida resultado={resultado({
      m5_scientific_status: "VALIDATED", m5_protocol_id: "M5_ZN_MMP9_1GKC_V2", m5_score: 0,
    })} />);
    expect(screen.getByRole("heading", { name: "Protocolo utilizado: M5-Zn" })).toBeVisible();
    expect(screen.getByText(/Protocolo para dianas de zinc:/)).toBeVisible();
    expect(screen.queryByText(/Protocolo general de evaluación:/)).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/M4/);
    const detalle = screen.getByText("Detalles del protocolo").closest("details")!;
    expect(detalle.open).toBe(false);
    fireEvent.click(screen.getByText("Detalles del protocolo"));
    expect(screen.getByText("0.0000")).toBeVisible();
  });

  it("conserva la reserva visible de un resultado M5 de auditoría", () => {
    const { container } = render(<PipelineDeLaCorrida resultado={resultado({
      m5_scientific_status: "REVIEW_INVALID_BENCHMARK_SITE",
      m5_protocol_id: "M5_ZN_MMP9_1GKC_V2", m5_score: 0.9,
    })} />);
    expect(screen.getByRole("heading", { name: "Protocolo utilizado: M5-Zn" })).toBeVisible();
    expect(screen.getByText("Resultado de auditoría: requiere revisión.")).toBeVisible();
    expect(container.textContent).not.toMatch(/M4/);
  });

  it("no deduce M5 de un estado VALIDATED sin perfil y resultado", () => {
    const { container } = render(<PipelineDeLaCorrida resultado={resultado({ m5_scientific_status: "VALIDATED" })} />);
    expect(screen.getByRole("heading", { name: "Protocolo utilizado: M4" })).toBeVisible();
    expect(container.textContent).not.toMatch(/M5/);
  });

  it("identifica también el registro histórico de M4", () => {
    render(<PipelineDeLaCorrida resultado={resultado({
      stacking_effective_weights: null, stacking_vina_weight: 1,
    })} />);
    expect(screen.getByRole("heading", { name: "Protocolo utilizado: M4" })).toBeVisible();
  });

  it("no usa un estado desconocido con un número para declarar M5", () => {
    const { container } = render(<PipelineDeLaCorrida resultado={resultado({
      m5_scientific_status: "ESTADO_DESCONOCIDO", m5_protocol_id: "M5_ZN_MMP9_1GKC_V2", m5_score: 0.99,
    })} />);
    expect(screen.getByRole("heading", { name: "Protocolo utilizado: M4" })).toBeVisible();
    expect(container.textContent).not.toMatch(/M5/);
  });
});
