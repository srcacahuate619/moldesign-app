// =====================================================================
// MolChat en blanco cuando la pregunta nombra una molécula
// =====================================================================
//
// EL FALLO (medido en la cápsula 5 el 2026-10-10 y reproducido con el backend real
// el 2026-10-11). «calcula las propiedades de la aspirina» salía EN BLANCO. El
// backend escribía `compute_properties (aspirina): …` sin `[clase · fuente]`, y la
// respuesta determinista llegaba pegada a esa línea («…Rings: 1Propiedades de
// aspirina:»). `separarEvidencia` tomaba todo lo posterior a la cabecera por
// evidencia, no reconocía la primera línea y descartaba el resto: ni prosa ni
// evidencia. Igual con «compara la aspirina con el ibuprofeno» y con las propuestas
// de docking pedidas por nombre.
//
// Los textos de abajo son los que emitió `chat_service` con el backend real (ver
// `backend/tests/test_molchat_bloque_de_evidencia.py`), antes y después del arreglo.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/context/AIContext", () => ({
  useAI: () => ({ sendMessage: vi.fn(), state: { providers: [], activeProviderId: "local" } }),
}));

import { separarEvidencia } from "../BloqueDeEvidencia";
import { ChatMessage } from "../ChatMessage";

const CABECERA =
  "[Sistema: resultados de herramientas ejecutadas. Cada bloque declara QUÉ es y DE DÓNDE sale; conserva esa distinción al responder y cita la fuente cuando des un número:]";
const FIN = "<!--__FIN_DE_EVIDENCIA__-->";

/** «calcula las propiedades de la aspirina», tal como sale ahora del backend. */
const PROPIEDADES = [
  "",
  "",
  "",
  CABECERA,
  "[cálculo · RDKit (descriptores sobre el SMILES dado)] compute_properties (aspirina): MW: 180.2 Da, LogP: 1.31, TPSA: 63.6 A^2, H-Bond Donors: 1, H-Bond Acceptors: 3, Rotatable Bonds: 2, Heavy Atoms: 13, Rings: 1",
  FIN,
  "Propiedades de aspirina:",
  "- MW: 180.2",
  "- LogP: 1.31",
  "- TPSA: 63.6",
  "- H-Bond Donors: 1",
].join("\n");

/** «compara la aspirina con el ibuprofeno», tal como sale ahora del backend. */
const COMPARACION = [
  "",
  "",
  "",
  CABECERA,
  "[cálculo · RDKit (descriptores de ambos SMILES)] compare_molecules (A=aspirina | B=ibuprofeno): Comparación:",
  "  MW: A=180.2 | B=206.3 (Δ=+26.1)",
  "  LogP: A=1.31 | B=3.07 (Δ=+1.76)",
  FIN,
  "Comparación entre aspirina y ibuprofeno:",
  "- MW: mayor en ibuprofeno (206.3 vs 180.2)",
].join("\n");

/** El mismo turno con el backend de antes: así queda en las conversaciones ya guardadas. */
const PROPIEDADES_ANTES =
  "\n\n\n[Sistema: resultados de herramientas ejecutadas:]\n" +
  "compute_properties (aspirina): MW: 180.2 Da, LogP: 1.31, TPSA: 63.6 A^2, H-Bond Donors: 1, H-Bond Acceptors: 3, Rotatable Bonds: 2, Heavy Atoms: 13, Rings: 1" +
  "Propiedades de aspirina:\n- MW: 180.2\n- LogP: 1.31";

describe("una pregunta que nombra la molécula no sale en blanco", () => {
  it("la respuesta determinista es prosa y no evidencia", () => {
    const { prosa, evidencias } = separarEvidencia(PROPIEDADES);

    expect(prosa).toMatch(/^Propiedades de aspirina:/);
    expect(prosa).toContain("- MW: 180.2");
    expect(evidencias).toHaveLength(1);
    expect(evidencias[0].texto).not.toContain("Propiedades de");
  });

  it("la evidencia conserva su clase, su fuente y de qué molécula es", () => {
    const [e] = separarEvidencia(PROPIEDADES).evidencias;

    expect(e.verificada).toBe(true);
    expect(e.clase).toMatch(/cálculo/);
    expect(e.fuente).toMatch(/RDKit/);
    expect(e.herramienta).toBe("compute_properties");
    expect(e.etiqueta).toBe("aspirina");
    expect(e.texto).toContain("MW: 180.2 Da");
  });

  it("una comparación lleva las dos moléculas y sus líneas siguen juntas", () => {
    const { prosa, evidencias } = separarEvidencia(COMPARACION);

    expect(prosa).toMatch(/^Comparación entre aspirina y ibuprofeno:/);
    expect(evidencias).toHaveLength(1);
    expect(evidencias[0].etiqueta).toBe("A=aspirina | B=ibuprofeno");
    expect(evidencias[0].texto).toContain("MW: A=180.2 | B=206.3");
    expect(evidencias[0].texto).toContain("LogP: A=1.31 | B=3.07");
  });

  it("el marcador de cierre no se enseña", () => {
    const { prosa, evidencias } = separarEvidencia(PROPIEDADES);

    expect(prosa).not.toContain("FIN_DE_EVIDENCIA");
    expect(evidencias.map((e) => e.texto).join("\n")).not.toContain("FIN_DE_EVIDENCIA");
  });

  it("en pantalla salen la respuesta y la evidencia con el nombre", () => {
    render(
      <ChatMessage message={{ id: "1", role: "assistant", content: PROPIEDADES } as never} isStreaming={false} />,
    );

    expect(screen.getByText(/Propiedades de aspirina/)).toBeInTheDocument();
    const bloque = screen.getByTestId("evidencia");
    expect(bloque).toHaveTextContent("compute_properties (aspirina)");
    expect(bloque).toHaveTextContent(/RDKit/);
  });
});

describe("ninguna línea se pierde", () => {
  it("un mensaje guardado con el formato de antes enseña todo lo que traía", () => {
    const { prosa, evidencias } = separarEvidencia(PROPIEDADES_ANTES);
    const visible = [prosa, ...evidencias.map((e) => e.texto)].join("\n");

    expect(visible).toContain("compute_properties (aspirina): MW: 180.2 Da");
    expect(visible).toContain("Propiedades de aspirina:");
    expect(visible).toContain("- LogP: 1.31");
    // Sin `[clase · fuente]` no se le supone una: se enseña como no verificada.
    expect(evidencias.every((e) => !e.verificada)).toBe(true);
  });

  it("varios bloques en un turno: la prosa entre ellos y la del final se conservan", () => {
    const { prosa, evidencias } = separarEvidencia(
      [
        "Primero calculo.",
        CABECERA,
        "[cálculo · RDKit (descriptores sobre el SMILES dado)] compute_properties: MW: 46.1 Da",
        FIN,
        "Ahora comparo.",
        CABECERA,
        "[cálculo · RDKit (descriptores de ambos SMILES)] compare_molecules: Comparación:",
        FIN,
        "Conclusión.",
      ].join("\n"),
    );

    expect(prosa.split("\n")).toEqual(["Primero calculo.", "Ahora comparo.", "Conclusión."]);
    expect(evidencias.map((e) => e.herramienta)).toEqual(["compute_properties", "compare_molecules"]);
  });

  it("una etiqueta con paréntesis (un SMILES sin nombre conocido) no rompe la línea", () => {
    const { evidencias } = separarEvidencia(
      `${CABECERA}\n[cálculo · RDKit (descriptores de ambos SMILES)] compare_molecules (A=CC(C)Cc1ccc(C(C)C(=O | B=aspirina): Comparación:\n${FIN}`,
    );

    expect(evidencias[0].verificada).toBe(true);
    expect(evidencias[0].etiqueta).toBe("A=CC(C)Cc1ccc(C(C)C(=O | B=aspirina");
    expect(evidencias[0].texto).toBe("Comparación:");
  });

  it("un bloque que aún no se ha cerrado (se está escribiendo) es evidencia hasta el final", () => {
    const { prosa, evidencias } = separarEvidencia(
      `Texto.\n${CABECERA}\n[cálculo · RDKit (descriptores sobre el SMILES dado)] compute_properties: MW: 4`,
    );

    expect(prosa).toBe("Texto.");
    expect(evidencias).toHaveLength(1);
  });
});
