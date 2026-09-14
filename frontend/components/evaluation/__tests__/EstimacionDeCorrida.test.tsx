// =====================================================================
// La estimación que se lee justo antes de pulsar «Evaluar»
// =====================================================================
//
// LO QUE PROTEGE, en orden de importancia:
//
//   1. Que un acoplamiento que va a superar el límite de 600 s se ANUNCIE. No
//      es una corrida lenta: es una que falla, y enterarse después de diez
//      minutos de espera es el peor resultado posible.
//   2. Que el coste de UNA vez —preparar el receptor— se presente como tal y no
//      como «la aplicación es lenta». Es la diferencia que hizo que una primera
//      corrida pareciera rota al lado de la segunda.
//   3. Que nunca se muestre un número solo: siempre un rango y siempre diciendo
//      en qué se apoya. Un tiempo exacto sería una promesa que esto no puede
//      hacer.
//   4. Que un motor que no contesta NO impida evaluar: el panel desaparece.

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";

import { EstimacionDeCorrida, formatearDuracion } from "../EstimacionDeCorrida";

const estimarCorrida = vi.fn();

vi.mock("../../../lib/api", () => ({
  estimarCorrida: (...args: unknown[]) => estimarCorrida(...args),
}));

const BASE = {
  segundos_min: 60,
  segundos_max: 180,
  apoyo: "modelo" as const,
  detalle_apoyo: "Todavía no hay corridas terminadas en este equipo.",
  etapas: [
    { etapa: "Acoplamiento", segundos_min: 54, segundos_max: 170, nota: "1 acoplamiento" },
  ],
  una_vez: null,
  avisos: [],
  ligandos: 1,
};

afterEach(() => {
  cleanup();
  estimarCorrida.mockReset();
});

describe("el formato del tiempo", () => {
  it("no enseña cuatro cifras de segundos a nadie", () => {
    expect(formatearDuracion(45)).toBe("45 s");
    expect(formatearDuracion(95)).toBe("1 min 35 s");
    expect(formatearDuracion(120)).toBe("2 min");
    expect(formatearDuracion(3600)).toBe("1 h");
    expect(formatearDuracion(5400)).toBe("1 h 30 min");
  });
});

describe("siempre un rango, y siempre con su apoyo", () => {
  it("muestra los dos extremos, no un número solo", async () => {
    estimarCorrida.mockResolvedValue(BASE);
    render(<EstimacionDeCorrida exhaustiveness={8} />);
    expect(await screen.findByText(/1 min – 3 min/)).toBeInTheDocument();
  });

  it("dice cuando NO está calibrado con este equipo", async () => {
    estimarCorrida.mockResolvedValue(BASE);
    render(<EstimacionDeCorrida exhaustiveness={8} />);
    expect(await screen.findByText(/sin historial todavía/i)).toBeInTheDocument();
  });

  it("y lo dice distinto cuando sí lo está", async () => {
    estimarCorrida.mockResolvedValue({
      ...BASE,
      apoyo: "historial",
      detalle_apoyo: "Calibrado con 7 acoplamientos que ya se ejecutaron en este equipo.",
    });
    render(<EstimacionDeCorrida exhaustiveness={8} />);
    expect(await screen.findByText(/calibrado con tu equipo/i)).toBeInTheDocument();
    expect(screen.getByText(/7 acoplamientos/)).toBeInTheDocument();
  });
});

describe("el coste de una sola vez", () => {
  it("se presenta como tal, no como lentitud del producto", async () => {
    estimarCorrida.mockResolvedValue({
      ...BASE,
      una_vez: {
        etapa: "Preparar el receptor",
        segundos_min: 9,
        segundos_max: 26,
        nota: "Este receptor aún no está preparado en este equipo. Se hace una sola vez.",
      },
    });
    render(<EstimacionDeCorrida exhaustiveness={8} />);
    expect(await screen.findByText(/sólo esta primera vez/i)).toBeInTheDocument();
    expect(screen.getByText(/se hace una sola vez/i)).toBeInTheDocument();
  });

  it("no aparece si el receptor ya está preparado", async () => {
    estimarCorrida.mockResolvedValue(BASE);
    render(<EstimacionDeCorrida exhaustiveness={8} />);
    await screen.findByText(/1 min – 3 min/);
    expect(screen.queryByText(/sólo esta primera vez/i)).not.toBeInTheDocument();
  });
});

describe("los avisos mandan sobre el número", () => {
  it("anuncia la corrida que va a reventar contra el límite", async () => {
    estimarCorrida.mockResolvedValue({
      ...BASE,
      avisos: ["Con esta configuración un solo acoplamiento podría superar el límite de 600 segundos y la corrida fallaría."],
    });
    render(<EstimacionDeCorrida exhaustiveness={64} />);
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(/fallaría/);
  });

  it("sin avisos no pinta ninguna alerta", async () => {
    estimarCorrida.mockResolvedValue(BASE);
    render(<EstimacionDeCorrida exhaustiveness={8} />);
    await screen.findByText(/1 min – 3 min/);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("no estorba", () => {
  it("un motor que no contesta NO impide evaluar: el panel no aparece", async () => {
    estimarCorrida.mockRejectedValue(new Error("Error de conexión"));
    const { container } = render(<EstimacionDeCorrida exhaustiveness={8} />);
    await waitFor(() => expect(estimarCorrida).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("no pregunta nada mientras no haya qué evaluar", () => {
    render(<EstimacionDeCorrida exhaustiveness={8} visible={false} />);
    expect(estimarCorrida).not.toHaveBeenCalled();
  });

  it("una cohorte se anuncia como cohorte", async () => {
    estimarCorrida.mockResolvedValue({ ...BASE, ligandos: 50 });
    render(<EstimacionDeCorrida exhaustiveness={8} ligandos={50} />);
    expect(await screen.findByText(/duración estimada de la cohorte/i)).toBeInTheDocument();
  });
});

describe("lo que se le pide al motor", () => {
  it("manda el receptor: sin él no se puede saber si hay que prepararlo", async () => {
    estimarCorrida.mockResolvedValue(BASE);
    render(
      <EstimacionDeCorrida
        exhaustiveness={16}
        targetPdbId="1WBM"
        gridSize={[30, 30, 30]}
        conformers={3}
      />,
    );
    await waitFor(() => expect(estimarCorrida).toHaveBeenCalled());
    expect(estimarCorrida).toHaveBeenCalledWith(
      expect.objectContaining({
        exhaustiveness: 16,
        targetPdbId: "1WBM",
        conformers: 3,
        gridSize: [30, 30, 30],
      }),
    );
  });

  it("no vuelve a preguntar si nada cambió, aunque el padre repinte", async () => {
    estimarCorrida.mockResolvedValue(BASE);
    const { rerender } = render(
      <EstimacionDeCorrida exhaustiveness={8} gridSize={[30, 30, 30]} />,
    );
    await waitFor(() => expect(estimarCorrida).toHaveBeenCalledTimes(1));
    // Array NUEVO con los mismos valores: es lo que hace el padre en cada
    // tecla. Sin serializar la clave, esto dispararía una petición por render.
    rerender(<EstimacionDeCorrida exhaustiveness={8} gridSize={[30, 30, 30]} />);
    await waitFor(() => expect(estimarCorrida).toHaveBeenCalledTimes(1));
  });
});
