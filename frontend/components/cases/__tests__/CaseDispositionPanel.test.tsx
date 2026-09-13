import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CaseDispositionPanel } from "../CaseDispositionPanel";

describe("CaseDispositionPanel", () => {
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
