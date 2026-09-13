// =====================================================================
// MOLDEX-SCI-003 + MOLDEX-SCI-004 — el comparador
// =====================================================================
//
// SCI-003: `MolecularComparison` hacía `?? 0` en logP, MW, TPSA y score, y
// calculaba la columna DIFERENCIA contra esos ceros, coloreada en verde o rojo.
// Es el mismo defecto que EVAL-SCI-012 retiró de SAR y que sobrevivió aquí
// porque ninguna prueba cubría este componente.
//
// SCI-004: no comprobaba nada antes de restar. Dos moléculas dockeadas contra
// receptores distintos, con cajas o protocolos distintos, se comparaban igual y
// la interfaz pintaba la diferencia como si significara algo. Un docking rígido
// y uno flexible no son comparables: la penalización torsional basta para
// invertir el orden de dos candidatos.

import { describe, expect, it } from "vitest";

import {
  compararMoleculas,
  filaComparativa,
  type MoldexMolecule,
} from "../moldex";

function molecula(overrides: {
  pdb_id?: string;
  receptor_sha256?: string | null;
  docking_protocol?: Record<string, unknown> | null;
  metrics?: Partial<MoldexMolecule["metrics"]>;
}): MoldexMolecule {
  return {
    id: "id",
    name: "Ligando",
    smiles: "CCO",
    smiles_hash: "b".repeat(64),
    created_at: "2026-08-01T00:00:00+00:00",
    evaluated_at: "2026-08-30T00:00:00+00:00",
    target: {
      pdb_id: overrides.pdb_id ?? "7E2Y",
      name: "5-HT1A",
      family: "GPCR",
      hotspots: [],
      spearman_rho: null,
    },
    metrics: {
      affinity: -8.2,
      log_p: 2.1,
      mw: 310.4,
      tpsa: 64.2,
      score: 88,
      gnn_score: null,
      lipinski_pass: null,
      veber_pass: null,
      ...overrides.metrics,
    },
    provenance: {
      task_id: "t",
      receptor_sha256:
        overrides.receptor_sha256 === undefined
          ? "c".repeat(64)
          : overrides.receptor_sha256,
      engine_version: "1.2.5",
      random_seed: 73,
      docking_protocol:
        overrides.docking_protocol === undefined
          ? { engine: "vina", exhaustiveness: 8 }
          : overrides.docking_protocol,
    },
    scientific_warnings: [],
    hotspots_hit: [],
    blockchain: {
      certified: false,
      tx_signature: null,
      certified_task_id: null,
      certified_total_score: null,
      matches_current_run: null,
    },
  };
}

// ── SCI-004: compatibilidad ──────────────────────────────────────────────────

describe("compatibilidad antes de comparar", () => {
  it("dos corridas del mismo receptor y protocolo son comparables", () => {
    const veredicto = compararMoleculas(molecula({}), molecula({}));

    expect(veredicto.comparable).toBe(true);
    expect(veredicto.motivos).toEqual([]);
  });

  it("rechaza dos targets distintos", () => {
    const veredicto = compararMoleculas(
      molecula({ pdb_id: "7E2Y" }),
      molecula({ pdb_id: "1ABC" }),
    );

    expect(veredicto.comparable).toBe(false);
    expect(veredicto.motivos.join(" ")).toMatch(/target/i);
  });

  it("rechaza dos receptores distintos aunque el target coincida", () => {
    // Mismo PDB ID, preparaciones distintas: caja, protonación o variante
    // privada. Los scores no son comparables.
    const veredicto = compararMoleculas(
      molecula({ receptor_sha256: "c".repeat(64) }),
      molecula({ receptor_sha256: "d".repeat(64) }),
    );

    expect(veredicto.comparable).toBe(false);
    expect(veredicto.motivos.join(" ")).toMatch(/receptor/i);
  });

  it("rechaza protocolos de docking distintos", () => {
    const veredicto = compararMoleculas(
      molecula({ docking_protocol: { engine: "vina", exhaustiveness: 8 } }),
      molecula({ docking_protocol: { engine: "vina", exhaustiveness: 32 } }),
    );

    expect(veredicto.comparable).toBe(false);
    expect(veredicto.motivos.join(" ")).toMatch(/protocolo/i);
  });

  it("rechaza cuando la procedencia no consta, en vez de suponerla", () => {
    // Una corrida heredada sin hash de receptor no puede declararse compatible:
    // no se sabe contra qué se midió.
    const veredicto = compararMoleculas(
      molecula({ receptor_sha256: null }),
      molecula({}),
    );

    expect(veredicto.comparable).toBe(false);
    expect(veredicto.motivos.join(" ")).toMatch(/no consta|procedencia/i);
  });

  it("acumula todos los motivos, no sólo el primero", () => {
    const veredicto = compararMoleculas(
      molecula({ pdb_id: "7E2Y", receptor_sha256: "c".repeat(64) }),
      molecula({ pdb_id: "1ABC", receptor_sha256: "d".repeat(64) }),
    );

    expect(veredicto.motivos.length).toBeGreaterThanOrEqual(2);
  });
});

// ── SCI-003: semántica nula ──────────────────────────────────────────────────

describe("semántica nula en la tabla comparativa", () => {
  it("no convierte una métrica ausente en cero", () => {
    const fila = filaComparativa("LOG P", null, 2.1);

    expect(fila.valorA).toBeNull();
    expect(fila.textoA).toBe("—");
    expect(fila.textoA).not.toBe("0.00");
  });

  it("no calcula delta si falta cualquiera de los dos lados", () => {
    expect(filaComparativa("LOG P", null, 2.1).delta).toBeNull();
    expect(filaComparativa("LOG P", 2.1, null).delta).toBeNull();
    expect(filaComparativa("LOG P", null, null).delta).toBeNull();
  });

  it("conserva el cero realmente medido y sí calcula su delta", () => {
    // El cero medido es un valor, no un faltante. Distinguirlo es el punto.
    const fila = filaComparativa("TPSA", 0, 64.2);

    expect(fila.valorA).toBe(0);
    expect(fila.textoA).toBe("0.00");
    expect(fila.delta).toBeCloseTo(64.2);
  });

  it("calcula el delta normal cuando ambos lados existen", () => {
    const fila = filaComparativa("SCORE", 88, 91);

    expect(fila.delta).toBeCloseTo(3);
    expect(fila.textoDelta).toBe("+3.00");
  });

  it("muestra un guion en el delta ausente, no un cero", () => {
    expect(filaComparativa("SCORE", null, 91).textoDelta).toBe("—");
  });
});
