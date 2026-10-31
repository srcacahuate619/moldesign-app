import { render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const producto = vi.hoisted(() => ({ version: "1.0.1" }));
vi.mock("@/lib/softwareCatalog", () => ({ PRODUCT: producto }));
vi.mock("@/lib/registro", () => ({ cargarIndice: vi.fn(async () => ({ total: 167 })) }));

import { LanguageProvider } from "../../context/LanguageContext";
import { AuthProvider } from "../../lib/auth";
import { SITE } from "../../lib/inicio";
import HomePage from "../page";

function montar(idioma: "es-ES" | "en-US") {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue(idioma);
  return render(
    <AuthProvider>
      <LanguageProvider>
        <HomePage />
      </LanguageProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  producto.version = "1.0.1";
});
afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

/**
 * El inicio (decisión del propietario, 2026-10-04): explica la app, trae las notas de la versión y lleva a la web.
 *
 * Antes decía que Molcy y Preparación «no ejecutan nuevos análisis todavía» (falso desde 1.0.2), sus notas
 * eran las de una versión que ya había cambiado, y sus enlaces apuntaban a un dominio y a dos rutas que no existen.
 */
describe("menú de inicio", () => {
  it("explica qué es la aplicación y qué no es", () => {
    montar("es-ES");
    expect(screen.getByTestId("que-es-la-app")).toHaveTextContent(/aplicación de escritorio/);
    expect(screen.getByTestId("que-es-la-app")).toHaveTextContent(/funciona sin conexión/);
    const limites = screen.getByTestId("que-es-y-que-no-es");
    expect(limites).toHaveTextContent("No predice actividad biológica");
    expect(limites).toHaveTextContent("No ejecuta dinámica molecular ni cálculos de energía libre (FEP)");
    expect(limites).toHaveTextContent("no certifica compatibilidad con ningún proveedor");
  });

  it("dice qué incluye: las seis herramientas, con Molcy marcada Beta", () => {
    montar("es-ES");
    const incluye = screen.getByTestId("que-incluye");
    expect(within(incluye).getAllByRole("listitem")).toHaveLength(6);
    for (const nombre of ["Evaluación", "Batch", "Preparación", "Moldex", "Historial", "Molcy (Beta)"]) {
      expect(within(incluye).getByText(nombre)).toBeTruthy();
    }
  });

  it("con la versión anterior instalada, las notas dicen que están en preparación", () => {
    montar("es-ES");
    expect(screen.getByTestId("estado-de-las-notas")).toHaveTextContent("En preparación · aún no publicado");
    expect(screen.getByTestId("notas-de-la-version")).toHaveTextContent("Lo que viene en la versión 1.0.4");
  });

  it.each(["1.0.4", "1.0.5", "1.1.0"])("con la versión %s instalada, las notas pasan a publicadas solas", (version) => {
    producto.version = version;
    montar("es-ES");
    expect(screen.getByTestId("estado-de-las-notas")).toHaveTextContent("Publicada");
    expect(screen.getByTestId("notas-de-la-version")).toHaveTextContent("Novedades de la versión 1.0.4");
  });

  it("las notas cuentan lo que de verdad cambió, incluidas las decisiones de esta versión", () => {
    montar("es-ES");
    const notas = screen.getByTestId("notas-de-la-version");
    expect(within(notas).getAllByRole("listitem").length).toBeGreaterThanOrEqual(9);
    // Lo que destacamos en 1.0.4 (2026-10-26): la vista 3D del dibujo va primera, como Molcy iba en 1.0.2.
    expect(notas).toHaveTextContent("tu dibujo 2D se ve en 3D para comprobar que es la molécula que quieres");
    expect(notas).toHaveTextContent("Molcy, que hace vídeos y fotos de tus evaluaciones");
    expect(notas).toHaveTextContent("la proteína VMAT2 (8T69) es el primer receptor verificado");
    expect(notas).toHaveTextContent("en Preparación, una segunda copia de la molécula de referencia");
  });

  it("todos los enlaces externos llevan a la portada de la web, y hay una llamada a la acción", () => {
    montar("es-ES");
    const externos = screen.getAllByRole("link").filter((a) => /^https?:/.test(a.getAttribute("href") ?? ""));
    expect(externos.length).toBeGreaterThanOrEqual(3); // notas, llamada a la acción y pie
    for (const enlace of externos) expect(enlace).toHaveAttribute("href", SITE);
    const llamada = screen.getByTestId("llamada-a-la-accion");
    expect(within(llamada).getByRole("link", { name: /Visitar la web de MolDesign/ })).toHaveAttribute("href", SITE);
  });

  it("ya no afirma que Molcy y Preparación están por diseñar (control de las afirmaciones falsas)", () => {
    montar("es-ES");
    const texto = document.body.textContent ?? "";
    expect(texto).not.toMatch(/no ejecutan nuevos análisis todavía|se están diseñando/);
  });

  it("en inglés dice lo mismo, con ortografía americana", async () => {
    montar("en-US");
    expect(await screen.findByText("WHAT IT IS NOT")).toBeTruthy();
    expect(screen.getByTestId("que-es-la-app")).toHaveTextContent(/desktop application/);
    expect(screen.getByTestId("notas-de-la-version")).toHaveTextContent("Coming in version 1.0.4");
    const enlaces = screen.getAllByRole("link", { name: /Visit the MolDesign website/ });
    expect(enlaces.length).toBeGreaterThanOrEqual(2); // notas y llamada a la acción
    for (const enlace of enlaces) expect(enlace).toHaveAttribute("href", SITE);
    expect(document.body.textContent ?? "").not.toMatch(/are being designed/);
  });
});
