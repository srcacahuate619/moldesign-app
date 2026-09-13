// =====================================================================
// La divulgación de IA generativa y su canal de reporte
// =====================================================================
//
// Microsoft pide las dos cosas juntas en cualquier aplicación que entregue
// texto escrito por un modelo: que el usuario sepa que lo es, y que pueda
// reportar una respuesta dañina o inapropiada. MolChat viaja en la 1.0.0 y no
// tenía ninguna de las dos.
//
// LO QUE VIGILA ESTA PRUEBA es que la divulgación no se pueda apagar. Este
// panel ya tiene tres avisos que se cierran —el del modelo local, el banner de
// advertencia, el de arranque— y todos con razón: describen estados que pasan.
// Éste describe lo que el panel ES. Un aviso que desaparece al segundo turno no
// divulga nada, y convertirlo en «uno más de los que se cierran» sería la forma
// natural de que dejara de cumplir sin que nadie lo notara.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { AvisoDeIAGenerativa } from "../AvisoDeIAGenerativa";
import { TRANSLATIONS } from "../../../context/LanguageContext";

const aqui = dirname(fileURLToPath(import.meta.url));
const panel = readFileSync(resolve(aqui, "..", "ChatPanel.tsx"), "utf8");
const mensaje = readFileSync(resolve(aqui, "..", "ChatMessage.tsx"), "utf8");
const aviso = readFileSync(resolve(aqui, "..", "AvisoDeIAGenerativa.tsx"), "utf8");

describe("el aviso dice las tres cosas que tiene que decir", () => {
  it("se muestra", () => {
    render(<AvisoDeIAGenerativa />);
    expect(screen.getByRole("note")).toBeTruthy();
  });

  it("nombra al modelo de lenguaje, admite el error y se deslinda del cálculo", () => {
    // La tercera es la que importa en este producto: MolChat habla de moléculas
    // a un centímetro de una pantalla que sí calcula.
    for (const idioma of ["es", "en"] as const) {
      const texto = TRANSLATIONS[idioma].ia_aviso_generativa;
      expect(texto, `falta en ${idioma}`).toBeTruthy();
      expect(texto).toMatch(/modelo de lenguaje|language model/i);
      expect(texto).toMatch(/incorrect|wrong/i);
      expect(texto).toMatch(/científico|scientific/i);
    }
  });
});

describe("la divulgación no se puede apagar", () => {
  it("el componente no tiene estado de cerrado ni botón de cerrar", () => {
    expect(aviso).not.toMatch(/setCerrado|avisoCerrado|onClose|dismiss/i);
  });

  it("el panel lo monta sin condición", () => {
    // Sin `&&` delante: los otros avisos del panel se renderizan condicionados
    // a un estado, y basta con que ese estado no se dé para que no aparezcan.
    expect(panel).toContain("<AvisoDeIAGenerativa />");
    expect(panel).not.toMatch(/\{[^}]*&&\s*<AvisoDeIAGenerativa/);
  });

  it("va pegado al campo de escritura, no arriba con los que se cierran", () => {
    const posicionAviso = panel.indexOf("<AvisoDeIAGenerativa />");
    const posicionInput = panel.indexOf("<ChatInput");

    expect(posicionAviso).toBeGreaterThan(-1);
    expect(posicionInput).toBeGreaterThan(posicionAviso);
  });
});

describe("el canal de reporte", () => {
  it("cuelga de cada respuesta del modelo", () => {
    expect(mensaje).toContain("<BotonDeReporte");
    expect(mensaje).toContain("!isUser");
  });

  it("no aparece mientras se escribe la respuesta", () => {
    // Todavía no hay respuesta que reportar.
    expect(mensaje).toMatch(/!isUser && !isStreaming/);
  });

  it("sale por la frontera de enlaces externos, no por fetch", () => {
    // Reportar no puede convertirse en una cuarta salida a la red: el correo lo
    // manda la persona desde su programa, con todo a la vista.
    expect(aviso).toContain("openExternal");
    expect(aviso).not.toContain("fetch(");
  });

  it("dice que no se envía nada hasta que la persona lo mande", () => {
    for (const idioma of ["es", "en"] as const) {
      expect(TRANSLATIONS[idioma].ia_reportar_aviso).toMatch(/no se envía|nothing is sent/i);
    }
  });
});
