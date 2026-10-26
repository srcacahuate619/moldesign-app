import { Suspense, lazy, type ComponentType } from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ruta = vi.hoisted(() => ({ actual: "/molcy" }));
vi.mock("next/navigation", () => ({ usePathname: () => ruta.actual }));
// `next/dynamic` con ssr:false carga aparte; aquí basta con un lazy de React sobre las páginas simuladas.
vi.mock("next/dynamic", () => ({
  default: (cargar: () => Promise<{ default: ComponentType }>) => {
    const Pagina = lazy(cargar);
    return function Dinamica() { return <Suspense fallback={null}><Pagina /></Suspense>; };
  },
}));

// Cada página es una sonda: cuenta sus montajes, guarda un estado propio y enseña lo que le dice `KeepAliveContext`.
vi.mock("../../app/evaluation/page", async () => ({ default: (await import("./sondaKeepAlive")).sonda("evaluation") }));
vi.mock("../../app/evaluation/batch/page", async () => ({ default: (await import("./sondaKeepAlive")).sonda("batch") }));
vi.mock("../../app/moldex/page", async () => ({ default: (await import("./sondaKeepAlive")).sonda("moldex") }));
vi.mock("../../app/history/page", async () => ({ default: (await import("./sondaKeepAlive")).sonda("history") }));
vi.mock("../../app/molcy/page", async () => ({ default: (await import("./sondaKeepAlive")).sonda("molcy") }));
vi.mock("../../app/preparacion/page", async () => ({ default: (await import("./sondaKeepAlive")).sonda("preparacion") }));

import { KEEP_ALIVE_ROUTES, PersistentKeepAliveLayout } from "../PersistentKeepAliveLayout";
import { montajes } from "./sondaKeepAlive";

function Arbol() {
  return <PersistentKeepAliveLayout><p>contenido de la ruta</p></PersistentKeepAliveLayout>;
}

async function ir(rerender: (ui: React.ReactElement) => void, destino: string) {
  ruta.actual = destino;
  await act(async () => { rerender(<Arbol />); });
}

describe("pestañas que no se desmontan", () => {
  beforeEach(() => {
    ruta.actual = "/molcy";
    for (const clave of Object.keys(montajes)) delete montajes[clave];
  });

  it("Molcy y Preparación son de ellas (decisión del propietario, 2026-10-10)", () => {
    expect(KEEP_ALIVE_ROUTES).toEqual(expect.arrayContaining(["/molcy", "/preparacion", "/evaluation", "/evaluation/batch", "/moldex", "/history"]));
  });

  it("al salir de Molcy y volver no se vuelve a montar y conserva lo que tenía", async () => {
    const { rerender } = render(<Arbol />);
    fireEvent.click(await screen.findByRole("button", { name: "molcy: 0" }));
    expect(screen.getByRole("button", { name: "molcy: 1" })).toBeInTheDocument();

    await ir(rerender, "/evaluation");
    await screen.findByRole("button", { name: "evaluation: 0" });
    const molcy = document.querySelector('[data-keep-alive="/molcy"]') as HTMLElement;
    expect(molcy.style.display).toBe("none");
    expect(molcy).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByTestId("activa-molcy")).toHaveTextContent("false");

    await ir(rerender, "/molcy");
    expect(screen.getByRole("button", { name: "molcy: 1" })).toBeVisible();
    expect(screen.getByTestId("activa-molcy")).toHaveTextContent("true");
    expect(montajes.molcy).toBe(1);
  });

  it("Moldex e Historial también saben si están a la vista (antes valía siempre «true»)", async () => {
    ruta.actual = "/moldex";
    const { rerender } = render(<Arbol />);
    await screen.findByRole("button", { name: "moldex: 0" });
    expect(screen.getByTestId("activa-moldex")).toHaveTextContent("true");

    await ir(rerender, "/history");
    await screen.findByRole("button", { name: "history: 0" });
    expect(screen.getByTestId("activa-moldex")).toHaveTextContent("false");
    expect(screen.getByTestId("activa-history")).toHaveTextContent("true");

    await ir(rerender, "/moldex");
    expect(screen.getByTestId("activa-moldex")).toHaveTextContent("true");
    expect(screen.getByTestId("activa-history")).toHaveTextContent("false");
    expect(montajes.moldex).toBe(1);
    expect(montajes.history).toBe(1);
  });

  it("una pestaña no se carga hasta la primera visita, y las demás rutas se pintan aparte", async () => {
    ruta.actual = "/";
    const { rerender } = render(<Arbol />);
    expect(screen.getByText("contenido de la ruta")).toBeInTheDocument();
    expect(document.querySelector("[data-keep-alive]")).toBeNull();

    await ir(rerender, "/molcy");
    await screen.findByRole("button", { name: "molcy: 0" });
    expect(screen.queryByText("contenido de la ruta")).not.toBeInTheDocument();
    expect(document.querySelectorAll("[data-keep-alive]")).toHaveLength(1);
  });
});
