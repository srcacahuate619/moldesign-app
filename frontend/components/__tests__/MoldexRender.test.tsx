// =====================================================================
// Gate de Moldex — la ausencia se pinta como ausencia
// =====================================================================
//
// MOLDEX-SCI-014 corrigió el fallo en el código: la guarda era
// `score !== undefined`, que un `null` atraviesa, así que una molécula **sin
// score** se etiquetaba `D-Tier` — el peor rango. Emitir un juicio a partir de
// un dato que no existe es la forma más cara de este error, porque parece un
// resultado.
//
// Lo que faltaba era la prueba de render. El expediente de Moldex lo declaraba:
// `MoldexCard` no tenía ninguna. Sin ella, la corrección vive hasta que alguien
// vuelva a escribir `score || 0` en un refactor.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import MoldexCard from "../MoldexCard";
import type { MoldexMetrics, MoldexMolecule } from "../../lib/moldex";

vi.mock("../../lib/config", () => ({
  getApiUrl: async () => "http://backend.test",
}));

const METRICAS_VACIAS: MoldexMetrics = {
  affinity: null,
  log_p: null,
  mw: null,
  tpsa: null,
  score: null,
  gnn_score: null,
  lipinski_pass: null,
  veber_pass: null,
};

function molecula(metrics: Partial<MoldexMetrics> = {}): MoldexMolecule {
  return {
    id: "mol-1",
    name: "aspirina",
    smiles: "CC(=O)Oc1ccccc1C(=O)O",
    smiles_hash: "abcdef0123456789",
    created_at: "2026-08-31T00:00:00Z",
    evaluated_at: "2026-08-31T00:00:00Z",
    target: {
      pdb_id: "7E2Y",
      name: "5-HT1A",
      family: "gpcr",
      hotspots: [],
      spearman_rho: null,
    },
    metrics: { ...METRICAS_VACIAS, ...metrics },
    provenance: {
      receptor_sha256: null,
      engine_version: null,
      random_seed: null,
      docking_protocol: null,
    },
    scientific_warnings: [],
    hotspots_hit: [],
    blockchain: {
      certified: false,
      tx_signature: null,
      certified_task_id: null,
      certified_total_score: null,
      cubre_la_corrida_mostrada: null,
    },
  } as unknown as MoldexMolecule;
}

const RESTO = {
  onClick: () => {},
  isSelected: false,
  onCompareToggle: () => {},
  isComparing: false,
};

describe("una molécula con score se pinta con su score", () => {
  it("muestra el número, no un guion", () => {
    render(<MoldexCard molecule={molecula({ score: 71.4 })} {...RESTO} />);

    expect(screen.getByText("71.4")).toBeInTheDocument();
  });
});

describe("una molécula SIN score no recibe un juicio", () => {
  it("no la etiqueta D-Tier", () => {
    render(<MoldexCard molecule={molecula()} {...RESTO} />);

    expect(screen.queryByText(/D-Tier/)).toBeNull();
  });

  it("no la pinta como cero", () => {
    const { container } = render(<MoldexCard molecule={molecula()} {...RESTO} />);

    expect(container.textContent).not.toMatch(/\b0\.0\b/);
  });

  it("declara la ausencia con un guion", () => {
    render(<MoldexCard molecule={molecula()} {...RESTO} />);

    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("un score de cero SÍ es un cero, no una ausencia", () => {
    // El contraste que hace útil a la prueba: cero es una medida.
    render(<MoldexCard molecule={molecula({ score: 0 })} {...RESTO} />);

    expect(screen.getByText("0.0")).toBeInTheDocument();
  });
});

describe("el sello", () => {
  it("una molécula sin sellar no se presenta como certificada", () => {
    const { container } = render(<MoldexCard molecule={molecula()} {...RESTO} />);

    expect(container.textContent).not.toMatch(/certificad/i);
  });
});
