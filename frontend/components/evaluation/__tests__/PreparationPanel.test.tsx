import { fireEvent, render, screen } from "@testing-library/react";

import { AuthProvider } from "../../../lib/auth";
import { LanguageProvider } from "../../../context/LanguageContext";

// El componente avisa —con razón— cuando se monta fuera del proveedor de
// idioma y cae al diccionario en castellano. Montarlo como lo monta la
// aplicacion quita ese aviso Y prueba el arbol real, no uno degradado.
function montar(elemento: React.ReactElement) {
  // `LanguageProvider` lee la sesión para recordar el idioma por cuenta, así
  // que el árbol real lleva los dos. Montar sólo uno era lo que producía el
  // aviso «useLanguage fuera de LanguageProvider» en la salida de la suite.
  // El árbol real: `LanguageProvider` lee la sesión para recordar el idioma por
  // cuenta, así que sin `AuthProvider` encima lanza. Este archivo no mockeaba
  // `lib/auth`, de modo que aquí se monta el proveedor de verdad.
  return render(
    <AuthProvider>
      <LanguageProvider>{elemento}</LanguageProvider>
    </AuthProvider>,
  );
}
import { describe, expect, it, vi } from "vitest";

import type { PreflightReport } from "../../../lib/preflight";
import { PreparationPanel } from "../PreparationPanel";

const report: PreflightReport = {
  schema_version: 3,
  generated_at: "2026-08-29T23:30:00Z",
  execution_route: "docking_vina",
  input_fingerprint: `sha256:${"a".repeat(64)}`,
  input_document: "{}",
  receptor: {
    reference: "ref",
    pdb_id: "1RKP",
    chain: "A",
    origin: "curado",
    source_available: true,
    source_sha256: `sha256:${"b".repeat(64)}`,
    prepared_available: false,
    prepared_sha256: null,
    prepared_compatible: null,
    prepared_chains: [],
  },
  ligand: {
    input_smiles: "CCO",
    canonical_smiles: "CCO",
    smiles_hash: "hash",
    molecular_formula: "C2H6O",
    heavy_atom_count: 3,
    error: null,
    vina_atom_compatibility: { evaluated: true, supported: true, unsupported_elements: [] },
  },
  effective_config: {
    grid_center: [43.8, 15.6, 48.4],
    grid_size: [30, 30, 30],
    grid_center_origin: "catalogo_target",
    grid_size_origin: "catalogo_target",
    derived_box: null,
    hotspots: [],
    hotspots_origin: "ninguno",
    docking_engine: "vina",
    exhaustiveness: 8,
    num_poses: 9,
    seed: 42,
    heteroatom_policy: {
      route: "docking_vina",
      waters: "eliminadas",
      metals: "conservados_solo_whitelist",
      organic_cofactors: "conservados_lista_producto",
      organic_cofactors_kept: ["FAD", "HEM", "NAD"],
      cofactors_whitelist_declared: [],
      cofactors_whitelist_applied: true,
      source: "preparer.filter_pdb_content · vina_service.run_docking",
    },
  },
  preparation_diff: {
    state: "evaluado",
    reason: "La fuente incluye 1 cadena; se conserva A.",
    source: {
      atom_records: 2522,
      hetatm_records: 151,
      waters: 133,
      metals: 2,
      organic_cofactors: 0,
      other_hetatm: 16,
      chains: ["A"],
    },
    route_input: {
      atom_records: 2522,
      hetatm_records: 0,
      waters: 0,
      metals: 0,
      organic_cofactors: 0,
      other_hetatm: 0,
      chains: ["A"],
    },
    removed: { waters: 133, metals: 2, organic_cofactors: 0, other_hetatm: 16 },
    removed_species: [
      { residue_code: "HOH", atom_count: 133, category: "water" },
      { residue_code: "ZN", atom_count: 2, category: "metal" },
      { residue_code: "LIG", atom_count: 16, category: "other_heteroatom" },
    ],
    preserved: { atom_records: 2522, organic_cofactors: 0, metals: 0, waters: 0 },
  },
  controls: [
    {
      code: "METALES_ELIMINADOS",
      state: "advertencia",
      title: "Metales del receptor",
      observation: "Se eliminan 2 átomos metálicos antes del acoplamiento: ZN (2 átomos).",
      reason: "En una metaloenzima el metal puede formar parte del sitio catalítico.",
      provenance: "preparer.filter_pdb_content · METAL_COFACTORS",
    },
  ],
  technical_blockers: [],
  warnings: ["METALES_ELIMINADOS"],
  not_evaluated: [],
};

describe("legibilidad y lenguaje público del preflight", () => {
  it("eleva el contraste y no expone constantes ni rutas internas", async () => {
    montar(
      <PreparationPanel
        report={report}
        loading={false}
        error={null}
        stale={false}
        canCheck
        missingInputs={null}
        onCheck={vi.fn()}
        decisions={[]}
        onAcknowledge={vi.fn()}
      />,
    );

    // El texto ya no está en el componente: viene del módulo de traducción, y en
    // jsdom `navigator.language` es `en-US`, así que el panel se sirve EN INGLÉS.
    // Lo que esta prueba mide es el CONTRASTE, no el idioma, así que se busca por
    // el valor traducido en lugar de por una cadena castellana fija —que es
    // justamente lo que se quitó—.
    const { pro } = await import("../../../context/traducciones/pro");
    expect(screen.getByText(pro.en.pr_preparacion_explicacion)).toHaveClass(
      "text-zinc-300",
      "font-medium",
    );

    fireEvent.click(screen.getByRole("button", { name: /ver detalle/i }));

    expect(screen.getByText("Acoplamiento molecular con AutoDock Vina")).toBeInTheDocument();
    expect(screen.getByText("ZN")).toBeInTheDocument();
    expect(screen.getAllByText(/2 átomos/).length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("docking_vina")).not.toBeInTheDocument();
    expect(screen.queryByText("conservados_solo_whitelist")).not.toBeInTheDocument();
    expect(screen.queryByText("METALES_ELIMINADOS")).not.toBeInTheDocument();
    expect(screen.queryByText(/preparer\.filter_pdb_content/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Procedencia:/i)).not.toBeInTheDocument();
  });
});
