import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LanguageProvider } from "../../../context/LanguageContext";
import { AuthProvider } from "../../../lib/auth";
import { PASOS_DEL_TUTORIAL, TutorialMolcy, capturaDelPaso } from "../TutorialMolcy";

const PUBLICO = resolve(process.cwd(), "public");
const MARCAS = JSON.parse(readFileSync(resolve(process.cwd(), "lib/tutorial/molcy-marcas.json"), "utf8"));

function montar(idioma: "es-ES" | "en-US") {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue(idioma);
  return render(<AuthProvider><LanguageProvider><TutorialMolcy /></LanguageProvider></AuthProvider>);
}

afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

/**
 * Inicio · «Del caso al vídeo» (decisión del propietario, 2026-10-10): cómo se hace un vídeo con Molcy, en seis
 * capturas reales con el control de cada paso señalado. Las capturas y las cajas las genera
 * `scripts/capturas-tutorial-molcy.mjs` contra la aplicación de verdad.
 */
describe("tutorial de Molcy en el inicio", () => {
  it("cada paso tiene su captura, en los dos idiomas, y la caja del botón cae dentro", () => {
    for (const idioma of ["es", "en"] as const) {
      for (const paso of PASOS_DEL_TUTORIAL) {
        const { src, marca } = capturaDelPaso(paso, idioma);
        expect(existsSync(resolve(PUBLICO, `.${src}`)), `${idioma}/${paso}`).toBe(true);
        expect(marca, `${idioma}/${paso}`).toEqual(MARCAS[idioma][paso]);
        const [x, y, w, h] = marca.caja;
        expect(w > 0 && h > 0 && x >= 0 && y >= 0 && x + w <= marca.ancho && y + h <= marca.alto, `${idioma}/${paso}`).toBe(true);
      }
    }
  });

  it("recorre los seis pasos en castellano y cambia la captura y el texto", () => {
    montar("es-ES");
    const seccion = screen.getByTestId("tutorial-molcy");
    expect(within(seccion).getByRole("heading", { name: "Del caso al vídeo, en seis pasos." })).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/molcy/es/caso.webp");
    expect(within(seccion).getByText("Paso 1 de 6")).toBeInTheDocument();
    expect(within(seccion).getByRole("button", { name: "Paso anterior" })).toBeDisabled();

    // Paso 2: elegir el receptor, entre crear el caso y ejecutar (decisión del propietario, 2026-10-10).
    fireEvent.click(within(seccion).getByRole("button", { name: "Paso siguiente" }));
    expect(within(seccion).getByText("Paso 2 de 6")).toBeInTheDocument();
    expect(within(seccion).getByRole("button", { name: /Selecciona un receptor/ })).toHaveAttribute("aria-current", "step");
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/molcy/es/receptor.webp");
    expect(within(seccion).getByRole("img")).toHaveAccessibleName("Un caso recién creado en Evaluación, con el botón «Elige receptor» señalado.");
    expect(within(seccion).getByText(/Pulsa «Elige receptor»/)).toBeInTheDocument();
    expect(PASOS_DEL_TUTORIAL.slice(0, 3)).toEqual(["caso", "receptor", "evaluar"]);

    fireEvent.click(within(seccion).getByRole("button", { name: /Guárdala en Moldex/ }));
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/molcy/es/guardar.webp");
    expect(within(seccion).getByRole("img")).toHaveAccessibleName("El resultado de una evaluación, con el botón «Guardar en MolDex» señalado.");
    expect(within(seccion).getByRole("button", { name: /Guárdala en Moldex/ })).toHaveAttribute("aria-current", "step");
    expect(within(seccion).getByText(/pulsa «Guardar en MolDex»/)).toBeInTheDocument();

    fireEvent.click(within(seccion).getByRole("button", { name: "Paso siguiente" }));
    expect(within(seccion).getByText("Paso 5 de 6")).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/molcy/es/corrida.webp");
    expect(within(seccion).getByText(/elige la corrida guardada/)).toBeInTheDocument();
    fireEvent.click(within(seccion).getByRole("button", { name: "Paso siguiente" }));
    expect(within(seccion).getByText("Paso 6 de 6")).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/molcy/es/molcy.webp");
    expect(within(seccion).getByRole("button", { name: "Paso siguiente" })).toBeDisabled();
  });

  it("en inglés usa las capturas inglesas", () => {
    montar("en-US");
    const seccion = screen.getByTestId("tutorial-molcy");
    expect(within(seccion).getByRole("heading", { name: "From case to video in six steps." })).toBeInTheDocument();
    expect(within(seccion).getByRole("img")).toHaveAttribute("src", "/tutorial/molcy/en/caso.webp");
    expect(within(seccion).getByRole("img")).toHaveAccessibleName("The Evaluation tab with no cases, with the “Create a case” button highlighted.");
  });

  it("el recuadro y la flecha señalan la caja del botón, no un sitio fijo", () => {
    montar("es-ES");
    const { marca } = capturaDelPaso("caso", "es");
    const [x, y, w] = marca.caja;
    const recuadro = screen.getByTestId("tutorial-recuadro");
    const flecha = screen.getByTestId("tutorial-flecha");
    expect(recuadro.style.left).toBe(`${(((x - 4) / marca.ancho) * 100).toFixed(2)}%`);
    expect(recuadro.style.top).toBe(`${(((y - 4) / marca.alto) * 100).toFixed(2)}%`);
    expect(flecha.style.left).toBe(`${(((x + w / 2) / marca.ancho) * 100).toFixed(2)}%`);
    // Son decoración: el texto del paso ya dice qué botón pulsar.
    expect(recuadro).toHaveAttribute("aria-hidden", "true");
    expect(flecha).toHaveAttribute("aria-hidden", "true");
  });
});
