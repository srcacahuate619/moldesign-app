import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

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
