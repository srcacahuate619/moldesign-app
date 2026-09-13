// =====================================================================
// Ayuda — el "?" tiene que alcanzarse, leerse y cerrarse
// =====================================================================
//
// LO QUE PROTEGEN:
//
// 1. **Se opera con teclado.** Es la razón de no usar `title=`: el tooltip
//    nativo no se alcanza sin ratón, no lo anuncia un lector de pantalla y en
//    el WebView2 tarda cientos de milisegundos. Una explicación que sólo ve
//    quien ya sabe dónde poner el ratón no explica nada.
//
// 2. **Escape cierra y DEVUELVE EL FOCO.** Sin eso, cerrar con teclado deja al
//    usuario al principio del documento.
//
// 3. **Cada "?" se llama distinto.** Siete botones llamados «Ayuda» son siete
//    botones indistinguibles en la lista de controles.
//
// 4. **Los siete textos existen en los dos idiomas** y dicen lo que tienen que
//    desactivar. Un texto que no corrige un malentendido real no merece un "?".

import { describe, expect, it, afterEach } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import { Ayuda } from "../Ayuda";
import { TRANSLATIONS } from "../../../context/LanguageContext";

afterEach(cleanup);

const es = TRANSLATIONS.es;
const en = TRANSLATIONS.en;

describe("comportamiento del componente", () => {
  it("empieza cerrado y se abre al pulsar", () => {
    render(<Ayuda titulo="Margen del selector">No es una probabilidad.</Ayuda>);

    const boton = screen.getByRole("button", { name: /Margen del selector/ });
    expect(boton).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(boton);
    expect(boton).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("dialog", { name: "Margen del selector" })).toBeInTheDocument();
    expect(screen.getByText("No es una probabilidad.")).toBeInTheDocument();
  });

  it("se opera con teclado: es un botón nativo, enfocable y con `aria-controls`", () => {
    render(<Ayuda titulo="Cobertura">El denominador importa.</Ayuda>);

    const boton = screen.getByRole("button", { name: /Cobertura/ });
    expect(boton).toHaveAttribute("type", "button");
    expect(boton).toHaveAttribute("aria-controls");

    boton.focus();
    expect(document.activeElement).toBe(boton);
    // Un `<button>` nativo convierte Enter y Espacio en `click`; jsdom no lo
    // simula, así que se comprueba lo que el navegador acabará disparando.
    fireEvent.click(boton);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("Escape cierra y devuelve el foco al botón", () => {
    render(<Ayuda titulo="Checksums">Integridad, no validez.</Ayuda>);

    const boton = screen.getByRole("button", { name: /Checksums/ });
    boton.focus();
    fireEvent.click(boton);
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    // Lo esencial: no deja al usuario de teclado en el limbo.
    expect(document.activeElement).toBe(boton);
  });

  it("se cierra al pulsar fuera", () => {
    render(
      <div>
        <Ayuda titulo="Afinidad">No es energía libre.</Ayuda>
        <p data-testid="fuera">otro sitio</p>
      </div>,
    );

    fireEvent.click(screen.getByRole("button", { name: /Afinidad/ }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.mouseDown(screen.getByTestId("fuera"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("cada ayuda se llama por lo que explica, no «Ayuda»", () => {
    render(
      <div>
        <Ayuda titulo="Margen del selector">a</Ayuda>
        <Ayuda titulo="Cobertura evaluada">b</Ayuda>
        <Ayuda titulo="Checksums del paquete">c</Ayuda>
      </div>,
    );

    const nombres = screen
      .getAllByRole("button")
      .map((b) => b.getAttribute("aria-label"));
    expect(new Set(nombres).size).toBe(nombres.length);
    expect(nombres.every((n) => n && n !== "Ayuda")).toBe(true);
  });
});

// ── Los siete textos ─────────────────────────────────────────────────

const PUNTOS = [
  "ensemble",
  "exhaustividad",
  "afinidad",
  "margen",
  "estados",
  "cobertura",
  "checksums",
] as const;

describe("los siete textos de ayuda", () => {
  it("existen en español y en inglés, con su título", () => {
    for (const punto of PUNTOS) {
      for (const dict of [es, en]) {
        expect(dict[`ayuda_${punto}_titulo`], `título de ${punto}`).toBeTruthy();
        expect(dict[`ayuda_${punto}`], `texto de ${punto}`).toBeTruthy();
        // Dos frases mínimo: un "?" que dice menos que la etiqueta no aporta.
        expect(dict[`ayuda_${punto}`].length).toBeGreaterThan(80);
      }
    }
  });

  it("ninguna clave `ayuda_` existe en un solo idioma", () => {
    const clavesEs = Object.keys(es).filter((k) => k.startsWith("ayuda_")).sort();
    const clavesEn = Object.keys(en).filter((k) => k.startsWith("ayuda_")).sort();
    expect(clavesEs).toEqual(clavesEn);
    expect(clavesEs.length).toBe(PUNTOS.length * 2);
  });

  it("cada texto desactiva la lectura equivocada que le toca", () => {
    // El ensemble no se vende como «mejor».
    expect(es.ayuda_ensemble).toContain("COBERTURA");
    expect(es.ayuda_ensemble).toContain("NO mejoró");
    expect(en.ayuda_ensemble).toContain("did NOT improve");

    // La afinidad no es energía libre.
    expect(es.ayuda_afinidad).toContain("NO es una energía libre");
    expect(es.ayuda_afinidad.toLowerCase()).toContain("ic50");

    // El margen no es probabilidad.
    expect(es.ayuda_margen).toContain("NO es una probabilidad");

    // «Revisión» no es aprobado, «no evaluada» habla del validador.
    expect(es.ayuda_estados).toContain("no que la pose sea buena");
    expect(es.ayuda_estados).toContain("VALIDADOR");

    // La cobertura sin denominador no dice nada.
    expect(es.ayuda_cobertura).toContain("denominador");

    // Un checksum no es validez científica.
    expect(es.ayuda_checksums).toContain("INTEGRIDAD");
    expect(es.ayuda_checksums).toContain("no sobre la ciencia");
  });

  it("ningún texto promete actividad, eficacia ni éxito", () => {
    for (const punto of PUNTOS) {
      for (const dict of [es, en]) {
        const texto = dict[`ayuda_${punto}`].toLowerCase();
        for (const prohibido of ["es activo", "eficaz", "probabilidad de éxito", "garantiza"]) {
          expect(texto, `${punto}: «${prohibido}»`).not.toContain(prohibido);
        }
      }
    }
  });
});
