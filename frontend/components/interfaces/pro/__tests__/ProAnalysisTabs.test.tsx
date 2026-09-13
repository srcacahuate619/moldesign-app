import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

vi.mock("../ProParametersTab", () => ({ ProParametersTab: () => <div>parámetros reales</div> }));
vi.mock("../ProAlertsTab", () => ({ ProAlertsTab: () => <div>alertas reales</div> }));
vi.mock("../ProXaiTab", () => ({ ProXaiTab: () => <div>explicabilidad real</div> }));
vi.mock("../ProSelectivityPanel", () => ({ ProSelectivityPanel: () => <div>selectividad real</div> }));
vi.mock("../ProSarTab", () => ({ ProSarTab: () => <div>SAR existente</div> }));
vi.mock("../ProDockingTab", () => ({
  ProDockingTab: ({ activePose, onSelectPose, poseDetails }: { activePose?: number; onSelectPose?: (rank: number) => void; poseDetails?: ReactNode }) => (
    <div>
      <div>poses y hotspots</div>
      <div>pose activa #{activePose ?? "—"}</div>
      <button type="button" onClick={() => onSelectPose?.(3)}>seleccionar pose 3</button>
      {poseDetails}
    </div>
  ),
}));
vi.mock("../StructuralEvidencePanel", () => ({
  PosePhysicalDetails: ({ rank }: { rank: number | null }) => <div>detalle físico #{rank ?? "—"}</div>,
  StructuralEvidencePanel: ({ onOpenPoseDetails }: { onOpenPoseDetails?: (rank: number | null) => void }) => (
    <div>
      expediente estructural
      <button type="button" onClick={() => onOpenPoseDetails?.(2)}>abrir detalle de pose 2</button>
    </div>
  ),
}));

import { ProAnalysisTabs } from "../ProAnalysisTabs";

const RESULT = {
  scientific_warnings: ["FUERA_DE_DOMINIO"],
  docking_poses: [
    { rank: 1, affinity: -8.3, rmsd_lb: 0, rmsd_ub: 0 },
    { rank: 2, affinity: -7.9, rmsd_lb: 1.1, rmsd_ub: 1.4 },
    { rank: 3, affinity: -6.1, rmsd_lb: 2.1, rmsd_ub: 2.8 },
  ],
  structural_evidence: {
    stage_status: "passed",
    poses_produced: 3,
    poses_evaluated: 3,
    poses: [
      { rank: 1, status: "passed", checks: [] },
      { rank: 2, status: "passed", checks: [] },
      { rank: 3, status: "passed", checks: [] },
    ],
  },
  pose_selection: {
    status: "selected",
    vina_top1_rank: 1,
    selected_pose_rank: 2,
    pose_scores: [
      { rank: 1, score: 0.11 },
      { rank: 2, score: 0.52 },
      { rank: 3, score: 0.09 },
    ],
  },
};

describe("ProAnalysisTabs", () => {
  it("separa cinco áreas y conserva las acciones post-docking reales", () => {
    const onRequestMmgbsa = vi.fn();
    const onComparePoses = vi.fn();
    render(
      <ProAnalysisTabs
        status={{ result: RESULT } as any}
        selectivityResult={null}
        moleculeId="mol-1"
        onRequestMmgbsa={onRequestMmgbsa}
        onComparePoses={onComparePoses}
      />,
    );

    for (const label of [
      "Estructura y evidencia",
      "Propiedades",
      "Comparar poses",
      "Evidencia estructural",
      "Análisis avanzado",
    ]) {
      expect(screen.getByRole("tab", { name: new RegExp(label) })).toBeInTheDocument();
    }
    expect(screen.getAllByRole("tab").slice(0, 5).map((tab) => tab.id)).toEqual([
      "analysis-tab-structure",
      "analysis-tab-properties",
      "analysis-tab-compare",
      "analysis-tab-evidence",
      "analysis-tab-advanced",
    ]);
    expect(screen.getByText("poses y hotspots")).toBeInTheDocument();
    expect(screen.getByText("detalle físico #1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "seleccionar pose 3" }));
    expect(screen.getByText("detalle físico #3")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Comparar poses" }));
    fireEvent.change(screen.getByLabelText("Pose B"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /Abrir comparación 3D/i }));
    expect(onComparePoses).toHaveBeenCalledWith(1, 3);

    fireEvent.click(screen.getByRole("tab", { name: "Evidencia estructural" }));
    expect(screen.getByText("expediente estructural")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "abrir detalle de pose 2" }));
    expect(screen.getByText("detalle físico #2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /^Análisis avanzado/ }));
    expect(screen.getByText("selectividad real")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /^MM-GBSA:/i }));
    fireEvent.click(screen.getByRole("button", { name: /Configurar MM-GBSA/i }));
    expect(onRequestMmgbsa).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("tab", { name: /^SAR:/i }));
    expect(screen.getByText("SAR existente")).toBeInTheDocument();
    expect(screen.getByText(/no genera actividad/i)).toBeInTheDocument();
  });
});
