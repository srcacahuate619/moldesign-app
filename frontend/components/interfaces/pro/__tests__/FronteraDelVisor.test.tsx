/**
 * Un visor que lanza no se lleva la pestaña por delante.
 *
 * La única frontera de errores era la de toda la aplicación: una excepción al
 * crear el contexto de three.js sustituía Evaluación entera —editor, opciones y
 * la línea de etapas de una corrida en marcha— por «Algo salió mal».
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

import { FronteraDelVisor } from "../FronteraDelVisor";

function VisorRoto(): never {
  throw new Error("Error creating WebGL context.");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("FronteraDelVisor", () => {
  it("contiene el fallo, avisa una vez y lo de alrededor sigue en pie", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const alFallar = vi.fn();
    render(
      <div>
        <p>Línea de etapas de la corrida</p>
        <FronteraDelVisor onFallo={alFallar} respaldo={<p>otro visor</p>}>
          <VisorRoto />
        </FronteraDelVisor>
      </div>,
    );
    expect(alFallar).toHaveBeenCalledTimes(1);
    expect((alFallar.mock.calls[0][0] as Error).message).toContain("WebGL context");
    expect(screen.getByText("Línea de etapas de la corrida")).toBeTruthy();
    expect(screen.getByText("otro visor")).toBeTruthy();
  });

  it("sin fallo no estorba", () => {
    const alFallar = vi.fn();
    render(<FronteraDelVisor onFallo={alFallar}><p>visor sano</p></FronteraDelVisor>);
    expect(screen.getByText("visor sano")).toBeTruthy();
    expect(alFallar).not.toHaveBeenCalled();
  });
});
