import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import type { Target } from "@/lib/api";
import type { CaseRun, CaseStructuralSystem } from "@/lib/cases/types";
import CaseRunHistoryModal from "../CaseRunHistoryModal";

vi.mock("@/lib/api", () => ({ getEvaluationResult: vi.fn().mockResolvedValue({ affinity_kcal: -7, docking_poses: [] }), downloadCertificate: vi.fn(), downloadComplexFile: vi.fn() }));
vi.mock("@/hooks/useScrollLock", () => ({ useScrollLock: () => {} }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => [{ pdb_id: "LOCAL", is_private: true } as Target] }));
vi.mock("@/context/LanguageContext", () => {
  const t = (key: string) => catalogo.es[key] ?? key;
  return { useLanguage: () => ({ t }) };
});

const system: CaseStructuralSystem = {
  lockedAt: "2026-10-08T12:00:00Z", sourceRunTaskId: "actual", inputFingerprint: "actual",
  receptor: { pdbId: "LOCAL", chain: "A", origin: "privado" },
  grid: { center: [0, 0, 0], size: [20, 20, 20] }, customHotspots: [],
  dockingEngine: "vina", exhaustiveness: 8, numPoses: 9, conformers: 1,
};

describe("el historial no hereda el receptor de otra hipótesis", () => {
  it.each(["actual", "anterior", undefined])("resuelve la sección sólo con la huella correspondiente: %s", async (inputFingerprint) => {
    const run: CaseRun = { taskId: "corrida", moleculeId: "molecula", executionState: "completed", startedAt: "2026-10-08T12:00:00Z", inputFingerprint };
    render(<CaseRunHistoryModal runs={[run]} structuralSystem={system} currentFingerprint="actual" onClose={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "ca_history_view_result" }));
    await screen.findByText("-7.00 kcal/mol");
    expect(screen.queryByText(catalogo.es.cat_insignia_ayuda) !== null).toBe(inputFingerprint !== "actual");
  });
});
