import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { ProDockingTab } from "../ProDockingTab";

describe("ProDockingTab", () => {
  it("abre el detalle de cualquier pose elegida, no sólo de las dos primeras", () => {
    const onSelectPose = vi.fn();
    const view = render(
      <ProDockingTab
        poses={[
          { rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 },
          { rank: 2, affinity: -7.9, rmsd_lb: 1.1, rmsd_ub: 1.4 },
          { rank: 3, affinity: -6.1, rmsd_lb: 2.1, rmsd_ub: 2.8 },
        ]}
        hotspots={[]}
        hotspots_hit={[]}
        activePose={1}
        onSelectPose={onSelectPose}
        poseDetails={<div data-testid="pose-details">detalle de pose</div>}
      />,
    );

    const poseOne = screen.getByRole("button", { name: "Ver controles físicos de la pose #1" });
    const poseThree = screen.getByRole("button", { name: "Ver controles físicos de la pose #3" });
    expect(poseOne).toHaveAttribute("aria-pressed", "true");
    expect(poseThree).toHaveAttribute("aria-pressed", "false");
    const detail = screen.getByTestId("pose-details");
    const items = Array.from(poseOne.parentElement?.children ?? []);
    expect(items.indexOf(detail.parentElement!)).toBe(items.indexOf(poseOne) + 1);
    expect(poseThree).toBeInTheDocument();

    view.rerender(
      <ProDockingTab
        poses={[
          { rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 },
          { rank: 2, affinity: -7.9, rmsd_lb: 1.1, rmsd_ub: 1.4 },
          { rank: 3, affinity: -6.1, rmsd_lb: 2.1, rmsd_ub: 2.8 },
        ]}
        hotspots={[]}
        hotspots_hit={[]}
        activePose={3}
        onSelectPose={onSelectPose}
        poseDetails={<div data-testid="pose-details">detalle de pose</div>}
      />,
    );
    const poseThreeAfter = screen.getByRole("button", { name: "Ver controles físicos de la pose #3" });
    const detailAfter = screen.getByTestId("pose-details");
    const itemsAfter = Array.from(poseThreeAfter.parentElement?.children ?? []);
    expect(itemsAfter.indexOf(detailAfter.parentElement!)).toBe(itemsAfter.indexOf(poseThreeAfter) + 1);
    expect(screen.getByRole("button", { name: "Ver controles físicos de la pose #1" })).toBeInTheDocument();

    fireEvent.click(poseThreeAfter);
    expect(onSelectPose).toHaveBeenCalledWith(3);
  });
});

// ── Qué residuos de referencia USÓ la corrida (decisión del 2026-10-04) ────────────────
//
// El panel pintaba los residuos del CATÁLOGO como si fueran los usados: una corrida sin residuos de
// referencia decía «puntos calientes: 15». Ahora lee lo que la corrida selló.

const CATALOGO = [
  { name: "A:R1", importance: 1 },
  { name: "A:R2", importance: 0.8 },
  { name: "A:R3", importance: 0.5 },
];

function panel(referenceResidues: React.ComponentProps<typeof ProDockingTab>["referenceResidues"]) {
  return render(
    <ProDockingTab
      poses={[{ rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 }]}
      hotspots={CATALOGO}
      hotspots_hit={["A:R2"]}
      referenceResidues={referenceResidues}
    />,
  );
}

const fila = (nombre: string) => screen.getByText(nombre).closest("[data-usado]") as HTMLElement;

describe("residuos de referencia usados", () => {
  it("declara el contacto con texto y distingue ausencia de una medición", () => {
    const view = panel({ source: "catalog", residues: ["A:R1", "A:R2", "A:R3"], count: 3, catalog_count: 3 });
    expect(within(fila("A:R2")).getByText("contactado")).toBeInTheDocument();
    expect(within(fila("A:R1")).getByText("sin contacto")).toBeInTheDocument();
    view.rerender(<ProDockingTab poses={[]} hotspots={CATALOGO} hotspots_hit={null} />);
    expect(within(fila("A:R1")).getByText("contacto no registrado")).toBeInTheDocument();
    expect(screen.queryByText("sin contacto")).toBeNull();
  });
  it("si se heredó el catálogo, los dice y marca todos como usados", () => {
    panel({ source: "catalog", residues: ["A:R1", "A:R2", "A:R3"], count: 3, catalog_count: 3 });
    expect(screen.getByTestId("residuos-usados")).toHaveTextContent("3 residuos de referencia: los del catálogo");
    expect(screen.getByText(/puntos calientes: 3/)).toBeTruthy();
    for (const n of ["A:R1", "A:R2", "A:R3"]) expect(fila(n).dataset.usado).toBe("si");
    expect(screen.queryByText("no usado")).toBeNull();
  });

  it("si la persona eligió un subconjunto, dice cuántos de cuántos y marca los que no se usaron", () => {
    panel({ source: "selected", residues: ["A:R2"], count: 1, catalog_count: 3 });
    expect(screen.getByTestId("residuos-usados")).toHaveTextContent("1 residuos de referencia, elegidos de los 3 del catálogo");
    expect(screen.getByText(/puntos calientes: 1/)).toBeTruthy();
    expect(fila("A:R2").dataset.usado).toBe("si");
    expect(fila("A:R1").dataset.usado).toBe("no");
    expect(fila("A:R3").dataset.usado).toBe("no");
    expect(screen.getAllByText("no usado")).toHaveLength(2);
  });

  it("si decidió no usar ninguno, lo dice y NINGÚN residuo del catálogo figura como usado", () => {
    panel({ source: "none", residues: [], count: 0, catalog_count: 3 });
    expect(screen.getByTestId("residuos-usados")).toHaveTextContent("no se usó ningún residuo de referencia");
    expect(screen.getByText(/puntos calientes: 0/)).toBeTruthy();
    for (const n of ["A:R1", "A:R2", "A:R3"]) expect(fila(n).dataset.usado).toBe("no");
    // Ni siquiera un residuo que aparecía en `hotspots_hit` cuenta como tocado si no se usó.
    expect(screen.getAllByText("no usado")).toHaveLength(3);
  });

  it("una corrida anterior al sellado no inventa: enseña el catálogo y dice que no sabe", () => {
    panel(null);
    expect(screen.getByTestId("residuos-usados")).toHaveTextContent("no registró qué residuos de referencia usó");
    for (const n of ["A:R1", "A:R2", "A:R3"]) expect(fila(n).dataset.usado).toBe("si");
    expect(screen.queryByText("no usado")).toBeNull();
  });

  it("un residuo elegido fuera del catálogo también aparece", () => {
    panel({ source: "selected", residues: ["A:R1", "B:X99"], count: 2, catalog_count: 3 });
    expect(fila("B:X99").dataset.usado).toBe("si");
    expect(fila("A:R2").dataset.usado).toBe("no");
  });
});
