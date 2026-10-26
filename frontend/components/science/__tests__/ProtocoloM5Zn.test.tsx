// =====================================================================
// La interfaz pinta el estado persistido. No lo recalcula ni lo mejora.
// =====================================================================
//
// La regla del backend, aplicada al cliente:
//
//   Sólo un resultado con estado explícito VALIDATED puede alimentar una
//   decisión derivada. Cualquier otro estado queda excluido.
//
// Aquí eso se traduce en dos comprobaciones que no pueden fallar:
//
//   1. si llega un REVIEW_*, se pinta EXACTAMENTE ese estado, aunque venga
//      acompañado de un score numérico alto;
//   2. un estado que este cliente no conoce se trata como no habilitante —
//      cerrado por defecto, igual que en el servidor.

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProtocoloM5Zn } from "../ProtocoloM5Zn";
import type { EvaluationResult } from "../../../lib/types";

function resultado(parcial: Partial<EvaluationResult>): EvaluationResult {
  return {
    m5_protocol_id: "M5_ZN_MMP9_1GKC_V1",
    m5_score: 0.99,
    m5_scientific_status: null,
    m5_missing_components: null,
    // V2: una sulfonamida primaria es UN grupo químico, así que n=1 y el
    // componente vale 0.85 + 0.10·(1/3). Con n=2 —el doble conteo de V1— daba
    // 0.9167, que es lo que este fixture traía.
    ums_warhead: 0.8833,
    ...parcial,
  } as unknown as EvaluationResult;
}

const NO_VALIDADOS = [
  "NOT_EVALUATED_MISSING_COMPONENT",
  "NOT_EVALUATED_PROTOCOL_NOT_EXECUTED",
  "REVIEW_OUT_OF_VALIDATED_TARGET",
  "REVIEW_OUT_OF_VALIDATED_STRUCTURE",
  "REVIEW_INVALID_BENCHMARK_SITE",
  "REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE",
  "REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING",
  "BLOCKED_PROTOCOL_NOT_AVAILABLE",
  "UN_ESTADO_QUE_TODAVIA_NO_EXISTE",
];

describe("ProtocoloM5Zn — el estado persistido se pinta tal cual", () => {
  it.each(NO_VALIDADOS)(
    "con %s declara que el número no habilita ninguna conclusión",
    (estado) => {
      render(
        <ProtocoloM5Zn
          resultado={resultado({ m5_scientific_status: estado })}
        />,
      );
      // El número SE VE: ocultarlo impediría auditarlo.
      expect(screen.getByText("0.9900")).toBeInTheDocument();
      // Y nunca solo.
      expect(screen.getByText(/Evidencia de auditoría/i)).toBeInTheDocument();
      expect(
        screen.getByText(/no entra en el score total/i),
      ).toBeInTheDocument();
      expect(screen.queryByText(/^Puntuación compuesta$/)).not.toBeInTheDocument();
    },
  );

  it("un estado desconocido NO se presenta como bueno (cerrado por defecto)", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({
          m5_scientific_status: "UN_ESTADO_QUE_TODAVIA_NO_EXISTE",
        })}
      />,
    );
    expect(
      screen.getByText(/Este cliente no conoce este estado/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/no habilita ninguna conclusión/i),
    ).toBeInTheDocument();
  });

  it("sólo VALIDATED presenta el número como score compuesto", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({ m5_scientific_status: "VALIDATED" })}
      />,
    );
    expect(screen.getByText("Puntuación compuesta")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Perfil M5-Zn aplicado" })).toBeInTheDocument();
    expect(
      screen.queryByText(/no entra en el score total/i),
    ).not.toBeInTheDocument();
  });

  it("sin estado no se pinta nada: la corrida no ejecutó M5-Zn", () => {
    const { container } = render(
      <ProtocoloM5Zn resultado={resultado({ m5_scientific_status: null })} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("el UMS se declara informativo, con peso 0 en el ranking", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({
          m5_scientific_status: "REVIEW_INVALID_BENCHMARK_SITE",
        })}
      />,
    );
    expect(screen.getByText(/peso 0 en el ranking/i)).toBeInTheDocument();
  });

  it("no inventa un score cuando el backend no lo manda", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({
          m5_scientific_status: "NOT_EVALUATED_MISSING_COMPONENT",
          m5_score: null,
        })}
      />,
    );
    expect(screen.queryByText("0.9900")).not.toBeInTheDocument();
    expect(screen.queryByText(/Evidencia de auditoría/i)).not.toBeInTheDocument();
  });

  it("pinta el componente ausente que llega persistido", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({
          m5_scientific_status: "NOT_EVALUATED_MISSING_COMPONENT",
          m5_missing_components: ["gnn_d"],
          m5_score: null,
        })}
      />,
    );
    expect(screen.getByText(/Componentes ausentes: gnn_d/i)).toBeInTheDocument();
  });
});

// QA1-009. Medido sobre los 380 receptores: 134 reciben este bloque sólo porque la
// estructura trae un ion (Mg, Na, K, Ca, Fe…) y 90 de ellos no contienen zinc.
// El texto afirmaba «Es una metaloenzima de zinc» en BACE1, cuyo único metal es un
// Na⁺ del tampón de cristalización. El estado no dice QUÉ ion hay (no viaja en el
// resultado), así que la explicación sólo puede decir lo que es cierto en todos los
// casos que lo disparan: hay un ion o una etiqueta de metaloenzima, y el PDB no es
// ninguno de los tres perfiles de M5-Zn.
describe("ProtocoloM5Zn — REVIEW_OUT_OF_VALIDATED_TARGET no afirma zinc (QA1-009)", () => {
  it("no dice que la diana sea una metaloenzima de zinc", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({ m5_scientific_status: "REVIEW_OUT_OF_VALIDATED_TARGET" })}
      />,
    );
    expect(screen.queryByText(/Es una metaloenzima de zinc/i)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/es una metaloenzima de zinc/i);
  });

  it("dice lo que sí es cierto: hay un ion y el PDB no es un perfil de M5-Zn", () => {
    render(
      <ProtocoloM5Zn
        resultado={resultado({ m5_scientific_status: "REVIEW_OUT_OF_VALIDATED_TARGET" })}
      />,
    );
    const texto = document.body.textContent ?? "";
    expect(texto).toMatch(/ion metálico/i);
    expect(texto).toMatch(/ninguno de los tres perfiles de M5-Zn/i);
    expect(texto).toMatch(/no implica un sitio de unión metálico/i);
    expect(texto).toMatch(/No se heredan los pesos de otra diana/i);
    expect(screen.getByRole("heading", { name: "Comprobación de aplicabilidad · M5-Zn" })).toBeInTheDocument();
    expect(texto).toMatch(/No se aplicó ningún perfil de M5-Zn a esta diana/i);
    expect(screen.queryByText("Perfil M5-Zn aplicado")).not.toBeInTheDocument();
  });
});
