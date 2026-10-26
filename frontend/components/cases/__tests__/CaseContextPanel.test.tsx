// =====================================================================
// AMP-06 — el formulario del contexto avisa ANTES del rechazo del dossier
// =====================================================================
//
// La pregunta del caso aceptó y persistió 4 366 caracteres sin límite visible;
// al actualizar el dossier, HTTP 422 con una explicación técnica en inglés. El
// formulario no recorta (ni al teclear ni al pegar: cortar en silencio perdería
// texto del investigador): cuenta, avisa cerca del límite y dice cuánto sobra.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { CaseContextPanel } from "../CaseContextPanel";

afterEach(cleanup);

function abrir(context = {}) {
  const alCambiar = vi.fn();
  render(<CaseContextPanel context={context} saveState="idle" onChange={alCambiar} embedded />);
  return alCambiar;
}

const pregunta = () => screen.getByLabelText("¿Qué intenta responder este caso?") as HTMLTextAreaElement;

describe("contador y límite del contexto (AMP-06)", () => {
  it("lejos del límite no hay contador que estorbe", () => {
    abrir({ question: "a".repeat(100) });
    expect(screen.queryByText(/caracteres/)).not.toBeInTheDocument();
    expect(pregunta()).not.toHaveAttribute("aria-invalid");
  });

  it("cerca del límite (90 %) cuenta, sin alarma", () => {
    abrir({ question: "a".repeat(3759) });
    expect(screen.getByText("3759 / 4000 caracteres")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(pregunta()).not.toHaveAttribute("aria-invalid");
  });

  it("sobre el límite avisa con el exceso y marca el campo; NO recorta el texto", () => {
    const alCambiar = abrir({ question: "a".repeat(4366) });
    const aviso = screen.getByRole("alert");
    expect(aviso).toHaveTextContent("366 caracteres");
    expect(aviso).toHaveTextContent("4000");
    expect(aviso).toHaveTextContent("tu texto no se ha modificado");
    expect(pregunta()).toHaveAttribute("aria-invalid", "true");
    expect(pregunta()).toHaveAttribute("aria-describedby", aviso.id);
    expect(pregunta().value).toHaveLength(4366);
    expect(alCambiar).not.toHaveBeenCalled();
  });

  it("no impone maxLength: un pegado de más de 4000 caracteres llega completo al caso", () => {
    const alCambiar = abrir();
    expect(pregunta()).not.toHaveAttribute("maxLength");
    fireEvent.change(pregunta(), { target: { value: "b".repeat(4366) } });
    expect(pregunta().value).toHaveLength(4366);
    expect(alCambiar).toHaveBeenCalledWith({ question: "b".repeat(4366) });
    expect(screen.getByRole("alert")).toHaveTextContent("366 caracteres");
  });

  it("al acortar por debajo del límite el aviso desaparece", () => {
    abrir({ question: "a".repeat(4366) });
    fireEvent.change(pregunta(), { target: { value: "a".repeat(100) } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(pregunta()).not.toHaveAttribute("aria-invalid");
  });

  it("cada texto cuenta por separado", () => {
    abrir({ question: "a".repeat(4500), decision: "corta" });
    expect(screen.getAllByRole("alert")).toHaveLength(1);
  });
});

describe("las notas declaran su destino (AMP-05)", () => {
  it("el campo de notas dice que aparece en el dossier", () => {
    abrir();
    expect(screen.getByText(/Aparece en el dossier; no entra en ningún cálculo/)).toBeInTheDocument();
  });
});
