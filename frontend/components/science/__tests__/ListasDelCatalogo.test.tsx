import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { catalogo } from "@/context/traducciones/catalogo";
import type { Target } from "@/lib/api";
import { getEvaluationResult } from "@/lib/api";
import type { EvaluationResult } from "@/lib/types";
import type { MoldexMolecule } from "@/lib/moldex";
import type { EvidenceMolecule } from "@/lib/cohorts";
import { verificacionDePrueba } from "@/lib/__tests__/fixtures/verificacionReceptor";
import MoldexCard from "@/components/MoldexCard";
import { BatchRowResult } from "@/components/evaluation/BatchRowResult";

vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => [{ pdb_id: "8HFI", seccion_catalogo: "verificado", verificacion: verificacionDePrueba } as Target] }));
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ locale: "es", t: (key: string, params: Record<string, string | number> = {}) => (catalogo.es[key] ?? key).replace(/\{(\w+)\}/g, (_, name) => String(params[name] ?? `{${name}}`)) }), Translated: ({ id }: { id: string }) => id }));
vi.mock("@/lib/backendFetch", () => ({ fetchBackend: vi.fn().mockRejectedValue(new Error("sin imagen en esta prueba")) }));
vi.mock("@/lib/api", () => ({ getEvaluationResult: vi.fn().mockResolvedValue({ affinity_kcal: -7, docking_poses: [], docking_protocol: { seed: 43 } }) }));

describe("listas y detalles del catálogo", () => {
  it("Moldex pasa el hash de la procedencia de su corrida a la insignia compacta", () => {
    const molecule = { id: "m", entry_id: "corrida", name: "Ligando", smiles: "CCO", smiles_hash: "abcdef", target: { pdb_id: "8HFI" }, metrics: { score: null }, provenance: { receptor_sha256: "otro" } } as unknown as MoldexMolecule;
    render(<MoldexCard molecule={molecule} onClick={() => {}} isSelected={false} onCompareToggle={() => {}} isComparing={false} />);
    expect(screen.getByRole("note").title).toContain(catalogo.es.cat_receptor_distinto);
    expect(screen.queryByText(catalogo.es.cat_receptor_distinto)).toBeNull();
  });
  it("la ficha de Moldex muestra sólo la etiqueta y conserva las condiciones de su corrida", () => {
    const molecule = { id: "m", entry_id: "corrida", name: "Ligando", smiles: "CCO", smiles_hash: "abcdef", target: { pdb_id: "8HFI" }, metrics: { score: null }, provenance: { docking_protocol: { exhaustiveness: 32 } } } as unknown as MoldexMolecule;
    render(<MoldexCard molecule={molecule} onClick={() => {}} isSelected={false} onCompareToggle={() => {}} isComparing={false} />);
    const badge = screen.getByRole("note");
    expect(badge.textContent).toBe(catalogo.es.cat_verificado_compacta_no_describe);
    expect(badge.title).toContain(catalogo.es.cat_parametros_distintos);
    expect(screen.queryByText(catalogo.es.cat_cond_serie)).toBeNull();
  });
  it("la fila del lote es compacta y el resultado expandido conserva el sello completo", async () => {
    const row = { molecule_id: "m", task_id: "exacta" } as EvidenceMolecule;
    const view = render(<BatchRowResult row={row} pdbId="8HFI" />);
    expect(screen.getByRole("note").textContent).toBe(catalogo.es.cat_verificado_compacta_comprobando);
    expect(screen.getByRole("note").title).not.toContain(catalogo.es.cat_receptor_sin_declarar);
    expect(screen.getByRole("note").title).not.toContain(catalogo.es.cat_parametros_sin_declarar);
    fireEvent.click(screen.getByRole("button", { name: "lo_view_run_result" }));
    expect(await screen.findByText(catalogo.es.cat_cond_serie)).toBeVisible();
    const full = screen.getAllByRole("note").find((note) => within(note).queryByText("Verificado"));
    expect(full).toBeTruthy();
    expect(within(full!).getByText(catalogo.es.cat_parametros_distintos)).toBeVisible();
    expect(view.container.textContent).toContain("-7.00 kcal/mol");
    expect(getEvaluationResult).toHaveBeenCalledWith("m", "exacta");
  });
  it("la fila descarta el sello confirmado de la corrida anterior al cambiar de task_id", async () => {
    vi.mocked(getEvaluationResult).mockResolvedValueOnce({ affinity_kcal: -7, receptor_sha256: verificacionDePrueba.receptor_sha256, docking_protocol: { exhaustiveness: 8, num_poses: 9, seed: 42 } } as EvaluationResult)
      .mockImplementationOnce(() => new Promise(() => {}));
    const view = render(<BatchRowResult row={{ molecule_id: "m", task_id: "old" } as EvidenceMolecule} pdbId="8HFI" />);
    fireEvent.click(screen.getByRole("button", { name: "lo_view_run_result" }));
    expect(await screen.findByText("Verificado · ρ = 0.41")).toBeVisible();
    view.rerender(<BatchRowResult row={{ molecule_id: "m", task_id: "new" } as EvidenceMolecule} pdbId="8HFI" />);
    expect(screen.queryByText("Verificado · ρ = 0.41")).toBeNull();
    expect(screen.getByRole("note").title).toBe(catalogo.es.cat_verificado_compacta_comprobando);
    expect(screen.queryByText("-7.00 kcal/mol")).toBeNull();
    expect(getEvaluationResult).toHaveBeenCalledWith("m", "new");
  });
});
