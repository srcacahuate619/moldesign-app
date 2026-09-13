// =====================================================================
// SC-9 — la interfaz no puede presentar igual un receptor calibrado y uno que no
// =====================================================================
//
// EL FALLO QUE VIGILA. El catálogo tiene 387 receptores curados
// estructuralmente y **cero** calibrados: `spearman_rho` existe en 2 de 387 y
// los dos valen `0.0`, que es el valor por defecto y que, de ser real,
// significaría ausencia de correlación. Aun así la interfaz mostraba scores,
// tiers y rankings con el mismo aspecto profesional para todos.
//
// El backend calcula el nivel en un solo sitio y lo manda en el contrato. Lo
// que estas pruebas fijan es la otra mitad: que la pantalla lo **muestre**, que
// no lo deduzca por su cuenta, y que no llame «validado» a estar en el catálogo.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  RespaldoDelReceptor,
  nivelLegible,
  necesitaAdvertencia,
  type Calibracion,
} from "../RespaldoDelReceptor";

function calibracion(parcial: Partial<Calibracion> = {}): Calibracion {
  return {
    nivel: "curado_estructural",
    spearman_rho: null,
    structural_family: "polymerase",
    tiene_pipeline_de_familia: false,
    resumen: "Curado estructuralmente; sin calibrar y sin pipeline de familia",
    advertencia:
      "Este receptor no tiene Spearman ρ medido y su familia estructural no tiene stacking calibrado.",
    motivo: "faltan Spearman ρ del receptor y stacking calibrado para su familia",
    requiere_advertencia: true,
    ...parcial,
  };
}

describe("los cuatro niveles se distinguen a la vista", () => {
  it("un receptor calibrado lo dice y muestra su ρ", () => {
    render(
      <RespaldoDelReceptor
        calibracion={calibracion({
          nivel: "calibrado",
          spearman_rho: 0.62,
          requiere_advertencia: false,
          resumen: "Calibrado para este receptor (Spearman ρ medido)",
          advertencia: "",
        })}
      />,
    );

    expect(screen.getByTestId("respaldo-receptor")).toHaveTextContent(/calibrado/i);
    expect(screen.getByTestId("respaldo-receptor")).toHaveTextContent("0.62");
  });

  it("un receptor con pipeline de familia no se presenta como calibrado", () => {
    render(
      <RespaldoDelReceptor
        calibracion={calibracion({
          nivel: "pipeline_de_familia",
          structural_family: "gpcr",
          tiene_pipeline_de_familia: true,
          resumen:
            "Pipeline calibrado por familia; este receptor no está calibrado individualmente",
        })}
      />,
    );

    const insignia = screen.getByTestId("respaldo-receptor");
    expect(insignia).toHaveTextContent(/familia/i);
    expect(insignia).toHaveTextContent(/no está calibrado/i);
  });

  it("un receptor sólo curado lo dice sin adornos", () => {
    render(<RespaldoDelReceptor calibracion={calibracion()} />);

    expect(screen.getByTestId("respaldo-receptor")).toHaveTextContent(/curado/i);
  });

  it("un receptor sin curar es el nivel más bajo y se ve", () => {
    render(
      <RespaldoDelReceptor
        calibracion={calibracion({
          nivel: "sin_curar",
          structural_family: null,
          resumen: "Sin curar: sin familia estructural conocida",
        })}
      />,
    );

    expect(screen.getByTestId("respaldo-receptor")).toHaveTextContent(/sin curar/i);
  });
});

describe("la advertencia no se pierde", () => {
  it("todo lo que no está calibrado la muestra", () => {
    render(<RespaldoDelReceptor calibracion={calibracion()} mostrarAdvertencia />);

    expect(screen.getByTestId("advertencia-calibracion")).toHaveTextContent(
      /spearman/i,
    );
  });

  it("un receptor calibrado no muestra advertencia", () => {
    render(
      <RespaldoDelReceptor
        calibracion={calibracion({
          nivel: "calibrado",
          spearman_rho: 0.62,
          requiere_advertencia: false,
          advertencia: "",
        })}
        mostrarAdvertencia
      />,
    );

    expect(screen.queryByTestId("advertencia-calibracion")).toBeNull();
  });

  it("sin dato del backend no se afirma que esté calibrado", () => {
    // El caso peligroso: una respuesta anterior al campo, o un fallo al
    // resolverlo. Presentarla como buena es exactamente el fallo de SC-9.
    render(<RespaldoDelReceptor calibracion={null} mostrarAdvertencia />);

    const insignia = screen.getByTestId("respaldo-receptor");
    expect(insignia).toHaveTextContent(/sin comprobar/i);
    expect(insignia).not.toHaveTextContent(/^calibrado/i);
    expect(screen.getByTestId("advertencia-calibracion")).toBeInTheDocument();
  });
});

describe("la interfaz no vuelve a decidir por su cuenta", () => {
  it("`requiere_advertencia` lo manda el backend, no se recalcula del ρ", () => {
    // Un backend que dijera «calibrado» con ρ nulo sería un bug del backend, y
    // la interfaz tiene que reflejarlo, no taparlo con una regla propia.
    expect(necesitaAdvertencia(calibracion({ requiere_advertencia: false }))).toBe(
      false,
    );
    expect(necesitaAdvertencia(null)).toBe(true);
  });

  it("un nivel desconocido no se presenta como bueno", () => {
    expect(nivelLegible("algo_que_no_existe" as Calibracion["nivel"])).toMatch(
      /sin comprobar/i,
    );
  });
});

describe("la palabra validado", () => {
  it("no aparece para ningún nivel que no esté calibrado", () => {
    for (const nivel of [
      "pipeline_de_familia",
      "curado_estructural",
      "sin_curar",
    ] as const) {
      const { unmount } = render(
        <RespaldoDelReceptor calibracion={calibracion({ nivel })} mostrarAdvertencia />,
      );
      expect(document.body.textContent?.toLowerCase()).not.toContain("validad");
      unmount();
    }
  });
});
