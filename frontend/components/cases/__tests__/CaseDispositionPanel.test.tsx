// =====================================================================
// CaseDispositionPanel — el contrato básico y el recuerdo (AMP-01)
// =====================================================================
//
// Dos cosas protege este archivo:
//
// 1. **El contrato básico del panel** (desde el MVP): sin relación
//    verificable sólo cabe la abstención; con la corrida correspondiendo,
//    las tres disposiciones.
// 2. **AMP-01**: el caso recuerda lo que se decidió. La auditoría ampliada
//    midió que editar el SMILES (y restaurarlo) borraba la decisión con su
//    justificación del caso persistido: «la justificación queda guardada
//    junto a la huella de inputs» no se cumplía como historial durable.
//    El panel enseña las disposiciones RETIRADAS — la conclusión vigente
//    la invalida el cambio de hipótesis, pero el derecho a recordar qué se
//    decidió y por qué no se borra.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { AuthProvider } from "../../../lib/auth";
import { LanguageProvider } from "../../../context/LanguageContext";
import { CaseDispositionPanel } from "../CaseDispositionPanel";
import type { CaseDisposition } from "../../../lib/cases/types";

const VIGENTE: CaseDisposition = {
  kind: "abstain",
  rationale: "La evidencia actual no sostiene una conclusión.",
  fingerprint: "sha256:dos",
  at: "2026-10-02T20:00:00.000Z",
};

const RETIRADA: CaseDisposition = {
  kind: "limit",
  rationale: "Acepto con límites: el receptor no está calibrado.",
  fingerprint: "sha256:uno",
  at: "2026-10-02T19:00:00.000Z",
};

afterEach(() => cleanup());

describe("CaseDispositionPanel", () => {
  it("traduce las tres opciones de disposición al inglés", async () => {
    vi.spyOn(window.navigator, "language", "get").mockReturnValue("en-US");
    render(
      <AuthProvider>
        <LanguageProvider>
          <CaseDispositionPanel runRelation="corresponde" onSubmit={() => true} />
        </LanguageProvider>
      </AuthProvider>,
    );

    expect(await screen.findByText("Accept the evidence")).toBeInTheDocument();
    expect(screen.getByText("Accept with limits")).toBeInTheDocument();
    expect(screen.getByText("Abstain")).toBeInTheDocument();
  });

  it("ofrece una sola acción cuando la evidencia no tiene relación verificable", () => {
    const onSubmit = vi.fn(() => true);
    render(
      <CaseDispositionPanel
        runRelation="desconocida"
        onSubmit={onSubmit}
      />,
    );

    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
    expect(screen.queryByText("Aceptar evidencia")).not.toBeInTheDocument();
    expect(screen.queryByText("Aceptar con límites")).not.toBeInTheDocument();
    expect(screen.getByText(/No se afirmará una conclusión/i)).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "La corrida no conserva una huella verificable." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar abstención" }));

    expect(onSubmit).toHaveBeenCalledWith(
      "abstain",
      "La corrida no conserva una huella verificable.",
    );
  });

  it("mantiene las tres disposiciones cuando la corrida corresponde", () => {
    render(
      <CaseDispositionPanel
        runRelation="corresponde"
        onSubmit={() => true}
      />,
    );

    expect(screen.getByRole("radiogroup", { name: "Disposición científica" })).toBeInTheDocument();
    expect(screen.getByText("Aceptar evidencia")).toBeInTheDocument();
    expect(screen.getByText("Aceptar con límites")).toBeInTheDocument();
    expect(screen.getByText("Abstenerse")).toBeInTheDocument();
  });
});

describe("AMP-01: el caso enseña sus disposiciones anteriores", () => {
  it("muestra la decisión retirada con su justificación, distinta de la vigente", () => {
    render(
      <CaseDispositionPanel
        disposition={VIGENTE}
        dispositions={[RETIRADA, VIGENTE]}
        runRelation="corresponde"
        onSubmit={() => true}
      />,
    );

    // La justificación retirada sigue legible en el caso…
    expect(screen.getByText(/no está calibrado/)).toBeInTheDocument();
    // …marcada como anterior, para no confundirse con la vigente.
    expect(screen.getByText(/Disposiciones anteriores/i)).toBeInTheDocument();
  });

  it("sin vigente, todo el historial es anterior", () => {
    render(
      <CaseDispositionPanel
        dispositions={[RETIRADA]}
        runRelation="corrida_anterior"
        onSubmit={() => true}
      />,
    );

    expect(screen.getByText(/no está calibrado/)).toBeInTheDocument();
  });

  it("sin historial, la sección no aparece", () => {
    render(
      <CaseDispositionPanel
        runRelation="corresponde"
        onSubmit={() => true}
      />,
    );

    expect(screen.queryByText(/Disposiciones anteriores/i)).not.toBeInTheDocument();
  });
});
