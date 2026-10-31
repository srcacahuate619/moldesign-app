import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** El efecto de la evaluación pedida desde el chat pulsa `ejecutarRef`: tiene que ser el botón que ejecuta. */
const fuente = readFileSync(join(__dirname, "../../components/interfaces/pro/ProEvaluation.tsx"), "utf8");

function cuerpoDelBoton(ref: string): string {
  const inicio = fuente.indexOf(`ref={${ref}}`);
  expect(inicio, `no hay un botón con ref={${ref}}`).toBeGreaterThan(-1);
  return fuente.slice(inicio, fuente.indexOf("</button>", inicio));
}

describe("botón que la evaluación del chat pulsa", () => {
  it("ejecutarRef es el botón que llama a handleSubmit", () => {
    const cuerpo = cuerpoDelBoton("ejecutarRef");
    expect(cuerpo).toContain("handleSubmit?.(");
    expect(cuerpo).not.toContain("setShowResults");
  });
  it("control negativo: el de «Ver resultados» alterna resultados y no ejecuta", () => {
    const cuerpo = cuerpoDelBoton("evaluarRef");
    expect(cuerpo).toContain("setShowResults");
    expect(cuerpo).not.toContain("handleSubmit");
  });
  it("el efecto del chat pulsa ejecutarRef y no evaluarRef", () => {
    const efecto = fuente.slice(fuente.indexOf("const request = evaluacionDesdeChat;"), fuente.indexOf("latidoEvaluacionChat]);"));
    expect(efecto).toContain("ejecutarRef");
    expect(efecto).not.toContain("evaluarRef");
  });
});
