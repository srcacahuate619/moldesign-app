// =====================================================================
// MOLCHAT-AUD-01, higiene del §8 — sanear el Markdown del modelo
// =====================================================================
//
// EL FALLO QUE VIGILA. `MarkdownRenderer` escapaba `<`, `>` y `&` a entidades
// HTML antes de construir los nodos. Pero no usa `dangerouslySetInnerHTML`:
// devuelve elementos de React, que ya escapan el texto. El escape era doble, y
// una desigualdad química —`MW < 500`, `logP > 3`— llegaba a la pantalla como
// `MW &lt; 500`. Una defensa que sobraba deformaba el dato.
//
// Lo que sí hay que sanear es lo activo: esquemas ejecutables y caracteres de
// control, que pueden venir del modelo o de una recuperación externa (texto de
// terceros que MolChat inyecta en el turno).

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { MarkdownRenderer, sanearMarkdown } from "../MarkdownRenderer";

describe("el texto científico llega intacto", () => {
  it("una desigualdad se lee como se escribió", () => {
    render(<MarkdownRenderer content="La regla pide MW < 500 y logP > 3." />);

    expect(screen.getByText(/MW < 500/)).toBeInTheDocument();
    expect(screen.queryByText(/&lt;/)).toBeNull();
  });

  it("un ampersand no se convierte en entidad", () => {
    render(<MarkdownRenderer content="Lipinski & Veber aprobados." />);

    expect(screen.getByText(/Lipinski & Veber/)).toBeInTheDocument();
  });
});

describe("lo activo se neutraliza", () => {
  it("un esquema ejecutable deja de serlo", () => {
    const salida = sanearMarkdown("mira javascript:alert(1)");

    expect(salida).not.toContain("javascript:");
    expect(salida).toContain("bloqueado");
  });

  it("un `data:` incrustado tampoco pasa", () => {
    expect(sanearMarkdown("data:text/html;base64,AAA")).not.toContain("data:");
  });

  it("los caracteres de control se quitan", () => {
    const nulo = String.fromCharCode(0);
    const campana = String.fromCharCode(7);
    const conControl = `texto${nulo}con${campana}control`;

    expect(sanearMarkdown(conControl)).toBe("textoconcontrol");
  });

  it("los saltos de línea y tabulaciones se conservan", () => {
    const texto = ["linea uno", "linea\tdos"].join("\n");

    expect(sanearMarkdown(texto)).toBe(texto);
  });
});

describe("los bloques se adaptan al tema", () => {
  it("renderiza citas con tokens de superficie y texto", () => {
    render(<MarkdownRenderer content="> La evidencia requiere revisión." />);

    const cita = screen.getByText("La evidencia requiere revisión.").closest("blockquote");
    expect(cita).toHaveStyle({
      background: "var(--bg-secondary)",
      color: "var(--text-secondary)",
    });
  });

  it("renderiza tablas sin colores exclusivos del tema oscuro", () => {
    const { container } = render(
      <MarkdownRenderer content={"| Métrica | Valor |\n| --- | --- |\n| RMSD | 1.2 Å |"} />,
    );

    expect(container.querySelector("table")?.getAttribute("style")).toContain(
      "border: 1px solid var(--border)",
    );
    expect(screen.getByText("RMSD")).toHaveStyle({ color: "var(--text-secondary)" });
  });
});
