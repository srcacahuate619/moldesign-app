import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { ReactElement } from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LanguageProvider } from "../../../context/LanguageContext";
import { AuthProvider } from "../../../lib/auth";
import { Tutoriales } from "../Tutoriales";
import { PASOS_DEL_TUTORIAL_PREPARACION, TutorialPreparacion, capturaDelPasoPreparacion } from "../TutorialPreparacion";

const PUBLICO = resolve(process.cwd(), "public");
const MARCAS = JSON.parse(readFileSync(resolve(process.cwd(), "lib/tutorial/preparacion-marcas.json"), "utf8"));

function montar(ui: ReactElement, idioma: "es-ES" | "en-US") {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue(idioma);
  return render(<AuthProvider><LanguageProvider>{ui}</LanguageProvider></AuthProvider>);
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

/**
 * Inicio · «Cómo preparar una evaluación para compartirla» (decisión del propietario, 2026-10-26): el primer tutorial de
 * la sección, con las capturas reales de la pestaña Preparación y el control de cada paso señalado. Las capturas y las
 * cajas las genera `scripts/capturas-tutorial-preparacion.mjs` contra la aplicación de verdad.
 */
describe("tutorial de Preparación en el inicio", () => {
  it("cada paso tiene su captura, en los dos idiomas, y la caja del control cae dentro", () => {
    for (const idioma of ["es", "en"] as const) {
      for (const paso of PASOS_DEL_TUTORIAL_PREPARACION) {
        const { src, marca } = capturaDelPasoPreparacion(paso, idioma);
        expect(existsSync(resolve(PUBLICO, `.${src}`)), `${idioma}/${paso}`).toBe(true);
        expect(marca, `${idioma}/${paso}`).toEqual(MARCAS[idioma][paso]);
        const [x, y, w, h] = marca.caja;
        expect(w > 0 && h > 0 && x >= 0 && y >= 0 && x + w <= marca.ancho && y + h <= marca.alto, `${idioma}/${paso}`).toBe(true);
      }
    }
  });

  it("recorre los seis pasos en castellano y cambia la captura y el texto", () => {
    montar(<TutorialPreparacion />, "es-ES");
    const seccion = screen.getByTestId("tutorial-preparacion");
    expect(within(seccion).getByRole("heading", { name: "Cómo preparar una evaluación para compartirla, en seis pasos." })).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/preparacion/es/pestana.webp");
    expect(within(seccion).getByText("Paso 1 de 6")).toBeInTheDocument();
    expect(within(seccion).getByRole("button", { name: "Paso anterior" })).toBeDisabled();

    fireEvent.click(within(seccion).getByRole("button", { name: "Paso siguiente" }));
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/preparacion/es/caso.webp");
    expect(within(seccion).getByText(/En «Elige un caso»/)).toBeInTheDocument();

    fireEvent.click(within(seccion).getByRole("button", { name: /Decide con una razón escrita/ }));
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/preparacion/es/decision.webp");
    expect(within(seccion).getByRole("button", { name: /Decide con una razón escrita/ })).toHaveAttribute("aria-current", "step");
    expect(within(seccion).getByText(/«Registrar»/)).toBeInTheDocument();

    fireEvent.click(within(seccion).getByRole("button", { name: "Paso siguiente" }));
    fireEvent.click(within(seccion).getByRole("button", { name: "Paso siguiente" }));
    expect(within(seccion).getByText("Paso 6 de 6")).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/preparacion/es/aviso.webp");
    expect(within(seccion).getByRole("button", { name: "Paso siguiente" })).toBeDisabled();
  });

  it("en inglés usa las capturas inglesas", () => {
    montar(<TutorialPreparacion />, "en-US");
    const seccion = screen.getByTestId("tutorial-preparacion");
    expect(within(seccion).getByRole("heading", { name: "How to prepare an evaluation to share it, in six steps." })).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/preparacion/en/pestana.webp");
  });
});

/** Las flechas entre tutoriales: Preparación primero, Molcy después. */
describe("sección de tutoriales del inicio", () => {
  it("abre con Preparación y la flecha pasa a Molcy", () => {
    montar(<Tutoriales />, "es-ES");
    expect(screen.getByText("TUTORIALES")).toBeInTheDocument();
    expect(screen.getByText("Tutorial 1 de 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tutorial anterior" })).toBeDisabled();
    expect(screen.getByTestId("tutorial-preparacion")).toBeInTheDocument();
    expect(screen.queryByTestId("tutorial-molcy")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Tutorial siguiente" }));
    expect(screen.getByText("Tutorial 2 de 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tutorial siguiente" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Tutorial anterior" })).toBeEnabled();
    expect(screen.getByTestId("tutorial-molcy")).toBeInTheDocument();
    expect(screen.queryByTestId("tutorial-preparacion")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Tutorial anterior" }));
    expect(screen.getByTestId("tutorial-preparacion")).toBeInTheDocument();
  });

  it("en inglés, las flechas se nombran en inglés", () => {
    montar(<Tutoriales />, "en-US");
    expect(screen.getByRole("button", { name: "Next tutorial" })).toBeInTheDocument();
    expect(screen.getByText("Tutorial 1 of 2")).toBeInTheDocument();
  });
});
