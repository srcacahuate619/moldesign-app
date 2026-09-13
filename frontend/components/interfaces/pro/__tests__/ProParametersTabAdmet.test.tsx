import { describe, it, expect, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { ProParametersTab } from "../ProParametersTab";

// `LiquidOrb` observa su propia visibilidad para animar el llenado. jsdom no
// trae `IntersectionObserver`; lo que se prueba aqui es el TEXTO del panel, no
// la animacion, asi que basta con un doble que nunca dispare.
beforeAll(() => {
  if (!("IntersectionObserver" in globalThis)) {
    (globalThis as unknown as { IntersectionObserver: unknown }).IntersectionObserver =
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
        takeRecords() {
          return [];
        }
      };
  }
});

// ─────────────────────────────────────────────────────────────────────────
// La aspirina en 2BQV, en la maquina limpia del 2026-09-03
//
// El panel mostraba, a la vez:
//
//     Viabilidad Sanguinea  orbe vacio y ROJO, «—»
//     Solubilidad           orbe vacio y ROJO, «—»
//     BBB                   «✗ No permeable», en rojo
//     HIA                   «✗ Baja», en rojo
//     Toxicologia           «✓ Sin alertas … identificadas por TabPFN», en verde
//
// Nada de eso se habia medido: ADMET-AI no corrio y el backend habia puesto
// los cinco campos a `null` justamente para no afirmar nada. El tipo de las
// props declaraba `boolean | undefined`, asi que la guarda estaba escrita
// `=== undefined` y `null` se colaba por la rama negativa.
//
// La regla que fijan estas pruebas: **ausencia no es negacion, y tampoco es
// aprobado**.
// ─────────────────────────────────────────────────────────────────────────

const SIN_ADMET = {
  qed: 0.55,
  sa_score: 1.9,
  molecular_weight: 180.16,
  log_p: 1.19,
  lipinski_pass: true,
  veber_pass: true,
  blood_viability_score: null,
  blood_solubility_logs: null,
  blood_ppb_category: null,
  blood_hia_permeable: null,
  blood_bbb_permeable: null,
  blood_systemic_reactivity: [],
};

const CON_ADMET = {
  ...SIN_ADMET,
  blood_viability_score: 100,
  blood_solubility_logs: -1.62,
  blood_ppb_category: "low",
  blood_hia_permeable: true,
  blood_bbb_permeable: false,
  blood_systemic_reactivity: ["Inhibidor CYP2C9"],
};

describe("ProParametersTab · ADMET ausente", () => {
  it("no afirma «No permeable» ni «Baja» cuando no hay prediccion", () => {
    render(<ProParametersTab result={SIN_ADMET} />);
    expect(screen.queryByText("✗ No permeable")).toBeNull();
    expect(screen.queryByText("✗ Baja")).toBeNull();
    expect(screen.getAllByText("sin dato").length).toBeGreaterThanOrEqual(3);
  });

  it("no da por buena la toxicologia que nadie evaluo", () => {
    render(<ProParametersTab result={SIN_ADMET} />);
    expect(screen.queryByText(/Sin alertas de reactividad sistémica/)).toBeNull();
    expect(screen.getByText(/no corrió en este equipo/)).toBeInTheDocument();
  });

  it("explica el hueco una vez, sin inventarle una causa", () => {
    render(<ProParametersTab result={SIN_ADMET} />);
    const aviso = screen.getByRole("status");
    expect(aviso).toHaveTextContent(/no llegó a ejecutarse/);
    // No se elige entre las dos causas posibles: se nombran las dos.
    expect(aviso).toHaveTextContent(/desactivado/);
    expect(aviso).toHaveTextContent(/no se pudo cargar/);
    expect(screen.getByText("ADMET-AI no disponible")).toBeInTheDocument();
  });

  it("los orbes se declaran vacios en vez de marcar cero", () => {
    render(<ProParametersTab result={SIN_ADMET} />);
    // «0 / 100» seria un resultado; «—» es un hueco.
    expect(screen.queryByText(/0 \/ 100/)).toBeNull();
    expect(screen.getAllByText("ADMET-AI no se ejecutó en esta corrida").length).toBe(2);
  });
});

describe("ProParametersTab · ADMET presente", () => {
  it("sigue diciendo lo que el modelo predijo, sin suavizarlo", () => {
    render(<ProParametersTab result={CON_ADMET} />);
    expect(screen.getByText("✓ Alta")).toBeInTheDocument();
    expect(screen.getByText("✗ No permeable")).toBeInTheDocument();
    expect(screen.getByText("Inhibidor CYP2C9")).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("traduce la categoria de PPB, que llegaba en ingles", () => {
    render(<ProParametersTab result={CON_ADMET} />);
    expect(screen.queryByText("low")).toBeNull();
    expect(screen.getByText("Baja (≤90 %)")).toBeInTheDocument();
  });
});
