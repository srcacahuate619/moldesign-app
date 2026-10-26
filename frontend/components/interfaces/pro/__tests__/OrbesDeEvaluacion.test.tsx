import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LanguageProvider } from "../../../../context/LanguageContext";
import { AuthProvider } from "../../../../lib/auth";
import { OrbeDeEvaluacion, angulosDeAnillo } from "../OrbeDeEvaluacion";
import { PipelineTimeline, DEFAULT_STAGES } from "../PipelineTimeline";

/**
 * Los orbes de la pantalla de carga de una evaluación (decisión del propietario, 2026-10-10: «más simétricos y
 * optimizados»). Simétricos: puntos a ángulos exactos y a la misma distancia del centro; lo que gira es el anillo entero.
 * Optimizados: animación CSS, ni un `requestAnimationFrame` (antes la pantalla gastaba 9,1 s de CPU cada 10 s).
 */

/** Ángulo y radio de cada punto, leídos de su `transform`. */
function geometria(contenedor: HTMLElement) {
  return within(contenedor).getAllByTestId("punto-de-anillo").map((punto) => {
    const m = /rotate\(([\d.]+)deg\) translateY\(-([\d.]+)px\)/.exec(punto.style.transform);
    if (!m) throw new Error(`transform inesperado: ${punto.style.transform}`);
    return { angulo: Number(m[1]), radio: Number(m[2]), tam: punto.style.width };
  });
}

function montarLinea(props: Parameters<typeof PipelineTimeline>[0]) {
  return render(<AuthProvider><LanguageProvider><PipelineTimeline {...props} /></LanguageProvider></AuthProvider>);
}

afterEach(() => { vi.restoreAllMocks(); });

describe("orbe de la evaluación", () => {
  it("los ángulos de un anillo se reparten por igual", () => {
    expect(angulosDeAnillo(12)).toEqual([0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]);
    expect(angulosDeAnillo(8)).toEqual([0, 45, 90, 135, 180, 225, 270, 315]);
  });

  it("es simétrico: 12 puntos cada 30° y 6 cada 60°, cada anillo a un solo radio y un solo tamaño", () => {
    render(<OrbeDeEvaluacion label="Procesando" />);
    const exterior = geometria(screen.getByTestId("anillo-exterior"));
    const interior = geometria(screen.getByTestId("anillo-interior"));
    expect(exterior.map((p) => p.angulo)).toEqual(angulosDeAnillo(12));
    expect(new Set(exterior.map((p) => p.radio))).toEqual(new Set([40]));
    expect(new Set(exterior.map((p) => p.tam)).size).toBe(1);
    expect(interior.map((p) => p.angulo)).toEqual(angulosDeAnillo(6));
    expect(new Set(interior.map((p) => p.radio))).toEqual(new Set([22]));
    expect(screen.getByText("Procesando")).toBeInTheDocument();
  });

  it("gira el anillo entero con CSS (y sólo si no se pidió reducir el movimiento), sin pedir fotogramas", () => {
    const raf = vi.spyOn(window, "requestAnimationFrame");
    render(<OrbeDeEvaluacion />);
    expect(screen.getByTestId("anillo-exterior").className).toContain("motion-safe:animate-giro");
    expect(screen.getByTestId("anillo-interior").className).toContain("motion-safe:animate-giro-inverso");
    expect(raf).not.toHaveBeenCalled();
  });
});

describe("línea de etapas de la evaluación", () => {
  const estados = { validation: "done", properties: "done", conformer: "done", vina: "running", xgb: "pending", clgnn: "pending" } as const;

  it("sólo gira el anillo de la etapa en curso; las pendientes lo enseñan quieto y las terminadas no lo tienen", () => {
    const { container } = montarLinea({ stages: DEFAULT_STAGES.slice(0, 6), stageStates: estados });
    const anillo = (id: string) => container.querySelector(`[data-etapa="${id}"] [data-testid="anillo-etapa"]`) as HTMLElement | null;
    expect(anillo("vina")!.dataset.girando).toBe("true");
    expect(anillo("vina")!.className).toContain("motion-safe:animate-giro");
    for (const id of ["xgb", "clgnn"]) {
      expect(anillo(id)!.dataset.girando, id).toBe("false");
      expect(anillo(id)!.className, id).not.toContain("animate-giro");
    }
    for (const id of ["validation", "properties", "conformer"]) expect(anillo(id), id).toBeNull();
    expect(container.querySelectorAll('[data-girando="true"]')).toHaveLength(1);
  });

  it("cada anillo es simétrico: 8 puntos cada 45° a 22 px", () => {
    const { container } = montarLinea({ stages: DEFAULT_STAGES.slice(0, 6), stageStates: estados });
    for (const anillo of container.querySelectorAll<HTMLElement>('[data-testid="anillo-etapa"]')) {
      const puntos = geometria(anillo);
      expect(puntos.map((p) => p.angulo)).toEqual(angulosDeAnillo(8));
      expect(new Set(puntos.map((p) => p.radio))).toEqual(new Set([22]));
    }
  });

  it("el brillo de la línea corre mientras hay trabajo y desaparece al terminar o fallar", () => {
    const vista = montarLinea({ stages: DEFAULT_STAGES.slice(0, 6), stageStates: estados });
    expect(screen.getByTestId("barrido")).toBeInTheDocument();
    vista.rerender(<AuthProvider><LanguageProvider><PipelineTimeline stages={DEFAULT_STAGES.slice(0, 6)} stageStates={estados} isDone /></LanguageProvider></AuthProvider>);
    expect(screen.queryByTestId("barrido")).not.toBeInTheDocument();
    vista.rerender(<AuthProvider><LanguageProvider><PipelineTimeline stages={DEFAULT_STAGES.slice(0, 6)} stageStates={estados} failed /></LanguageProvider></AuthProvider>);
    expect(screen.queryByTestId("barrido")).not.toBeInTheDocument();
  });
});
