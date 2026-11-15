import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

const language = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("../../../../context/LanguageContext", async () => {
  const real = await vi.importActual<typeof import("../../../../context/LanguageContext")>("../../../../context/LanguageContext");
  const t = (key: string, values?: Readonly<Record<string, string | number>>) => real.interpolar(real.TRANSLATIONS[language.locale][key] ?? key, values);
  return { ...real, useLanguage: () => ({ locale: language.locale, t }) };
});
beforeEach(() => { language.locale = "es"; });
afterEach(cleanup);

vi.mock("../ProParametersTab", () => ({ ProParametersTab: ({ abrirAdmet = 0 }: { abrirAdmet?: number }) => <div>parámetros reales · abrirAdmet={abrirAdmet}</div> }));
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
  it("separa cuatro áreas y conserva las acciones post-docking reales", () => {
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
      "Poses y controles",
      "Propiedades y estado químico",
      "Análisis",
      "Procedencia y datos",
    ]) {
      expect(screen.getByRole("tab", { name: new RegExp(label) })).toBeInTheDocument();
    }
    const areas = screen.getByRole("tablist", { name: "Áreas del resultado" });
    expect(within(areas).getAllByRole("tab")).toHaveLength(4);
    expect(within(areas).getAllByRole("tab").map(tab => tab.id.split("-").at(-1))).toEqual([
      "structure", "properties", "advanced", "provenance",
    ]);
    expect(screen.getByText("poses y hotspots")).toBeInTheDocument();
    expect(screen.getByText("detalle físico #1")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "seleccionar pose 3" }));
    expect(screen.getByText("detalle físico #3")).toBeInTheDocument();

    const compareSummary = screen.getAllByText("Comparar poses").find(element => element.tagName === "SUMMARY")!;
    fireEvent.click(compareSummary);
    fireEvent.change(screen.getByLabelText("Pose B"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: /Abrir comparación 3D/i }));
    expect(onComparePoses).toHaveBeenCalledWith(1, 3);

    const physicalSummary = screen.getAllByText("Evidencia estructural").find(element => element.tagName === "SUMMARY")!;
    fireEvent.click(physicalSummary);
    expect(screen.getByText("expediente estructural")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "abrir detalle de pose 2" }));
    expect(screen.getByText("detalle físico #2")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /^Análisis$/ }));
    expect(screen.getByText("selectividad real")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: /^MM-GBSA:/i }));
    expect(screen.getByText(/parametrización legacy no supera la guardia/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "No disponible" })).toBeDisabled();
    expect(onRequestMmgbsa).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: /^SAR:/i }));
    expect(screen.getByText("SAR existente")).toBeInTheDocument();
    expect(screen.getByText(/no genera actividad/i)).toBeInTheDocument();
  });
});

describe("Análisis · pestaña «Modelos»", () => {
  const abrirAnalisis = (result: Record<string, unknown>) => {
    render(<ProAnalysisTabs status={{ result } as any} selectivityResult={null} moleculeId="mol-1" />);
    fireEvent.click(screen.getByRole("tab", { name: /^Análisis$/ }));
    return within(screen.getByRole("tablist", { name: "Métodos de análisis avanzado" }));
  };

  it("N01 va entre SAR y Explicabilidad y abre las fichas de la corrida, no el mapa de contactos", () => {
    const metodos = abrirAnalisis({ ...RESULT, ml_pki: 6.3, xgb_score: 0.05, in_applicability_domain: true });
    expect(metodos.getAllByRole("tab").map(tab => tab.id.replace("advanced-tab-", ""))).toEqual([
      "selectivity", "mmgbsa", "admet", "sar", "models", "xai",
    ]);
    fireEvent.click(metodos.getByRole("tab", { name: /^Modelos:/ }));
    expect(screen.getByRole("tabpanel", { name: /Modelos/ })).toBeInTheDocument();
    expect(screen.getByText("XGBoost · regresión del pKi")).toBeInTheDocument();
    expect(screen.getByText("XGBoost · clasificador de binder")).toBeInTheDocument();
    expect(screen.queryByText("explicabilidad real")).not.toBeInTheDocument();
  });

  it("N04 con ADMET calculado, «Ver resultados» lleva a Propiedades; sin ADMET no hay botón", () => {
    const con = abrirAnalisis({ ...RESULT, blood_viability_score: 0.5 });
    fireEvent.click(con.getByRole("tab", { name: /^ADMET:/ }));
    fireEvent.click(screen.getByRole("button", { name: "Ver resultados" }));
    expect(screen.getByRole("tab", { name: /Propiedades y estado químico/ })).toHaveAttribute("aria-selected", "true");
    // Además pide abrir la sección «Predicciones ADMET», no sólo la pestaña.
    expect(screen.getByText(/abrirAdmet=1/)).toBeInTheDocument();
    // Salir y volver a mano no repite la petición.
    fireEvent.click(screen.getByRole("tab", { name: /Poses y controles/ }));
    fireEvent.click(screen.getByRole("tab", { name: /Propiedades y estado químico/ }));
    expect(screen.getByText(/abrirAdmet=0/)).toBeInTheDocument();
    cleanup();
    const sin = abrirAnalisis({ ...RESULT });
    fireEvent.click(sin.getByRole("tab", { name: /^ADMET:/ }));
    expect(screen.queryByRole("button", { name: "Ver resultados" })).toBeNull();
  });

  it("N02 «Modelos» dice «Con resultado» sólo si algún modelo guardó salida", () => {
    const con = abrirAnalisis({ ...RESULT, xgb_score: 0.4 });
    expect(con.getByRole("tab", { name: /^Modelos: Con resultado/ })).toBeInTheDocument();
    cleanup();
    const sin = abrirAnalisis({ docking_poses: RESULT.docking_poses, ml_pki: null, xgb_score: null, clgnn_score: null, shap_values: null });
    expect(sin.getByRole("tab", { name: /^Modelos: Sin resultado guardado/ })).toBeInTheDocument();
  });

  it("N03 el SHAP ya no enciende «Explicabilidad»: sólo lo hacen las poses de las que sale el mapa", () => {
    const conShapSinPoses = abrirAnalisis({ docking_poses: [], shap_values: { mw: 0.1 }, ml_pki: 6 });
    expect(conShapSinPoses.getByRole("tab", { name: /^Explicabilidad: Sin resultado guardado/ })).toBeInTheDocument();
    expect(conShapSinPoses.getByRole("tab", { name: /^Modelos: Con resultado/ })).toBeInTheDocument();
    cleanup();
    const conPoses = abrirAnalisis({ ...RESULT });
    expect(conPoses.getByRole("tab", { name: /^Explicabilidad: Con resultado/ })).toBeInTheDocument();
  });
});

describe.each(["es", "en"] as const)("abrir controles físicos en %s", locale => {
  it("conserva el recuento y abre el detalle desde una pose fallida", () => {
    language.locale = locale;
    const result = { ...RESULT, structural_evidence: { ...RESULT.structural_evidence, stage_status: "failed", poses: [
      { rank: 1, status: "failed", checks: [{ check: "internal_energy", estado: "FALLA" }, { check: "bond_lengths", estado: "FALLA" }] },
    ] } };
    render(<ProAnalysisTabs status={{ result } as any} selectivityResult={null} moleculeId="mol-1" />);
    const label = locale === "es" ? "Ver los 2 controles que fallan" : "View failed checks (2)";
    const button = screen.getByRole("button", { name: label });
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(screen.getByText("expediente estructural")).toBeVisible();
  });
});
