import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CpuControls } from "../CpuControls";
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ t: (key: string, values?: unknown) => `${key} ${values ? JSON.stringify(values) : ""}` }) }));
const renderer = { disponible: true, motivo: null, cpu_hilos: 4, cpu_hilos_disponibles: 8, cpu_hilos_maximos: 6, cpu_uso_actual_pct: 12 };
afterEach(cleanup);

describe("Controles CPU Molcy (fotos con Cycles en CPU)", () => {
  it("limita los hilos al máximo con margen y dice la carga actual", () => {
    render(<CpuControls renderer={renderer} threads={4} onThreads={vi.fn()} busy={false} />);
    expect(screen.getByRole("slider")).toHaveAttribute("max", "6");
    expect(screen.getByText(/cy_cpu_safe_limit/)).toBeVisible();
    expect(screen.getByText(/cy_cpu_load /)).toBeVisible();
  });
  it("ofrece volver a la recomendación y bloquea ajustes durante el render", () => {
    const onThreads = vi.fn();
    const view = render(<CpuControls renderer={renderer} threads={2} onThreads={onThreads} busy={false} />);
    fireEvent.click(screen.getByRole("button", { name: /cy_cpu_threads_recommended/ }));
    expect(onThreads).toHaveBeenCalledWith(4);
    view.rerender(<CpuControls renderer={renderer} threads={4} onThreads={onThreads} busy />);
    expect(screen.getByRole("slider")).toBeDisabled();
    expect(screen.getByText(/cy_cpu_busy/)).toBeTruthy();
  });
  it("ya no estima el vídeo por CPU: ese camino se retiró", () => {
    render(<CpuControls renderer={renderer} threads={4} onThreads={vi.fn()} busy={false} />);
    expect(screen.queryByText(/cy_cpu_estimate/)).toBeNull();
  });
});
