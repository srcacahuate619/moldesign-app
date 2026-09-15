// =====================================================================
// Tests del adapter SAR (mapSarAnalog) — ProSarTab.tsx
// =====================================================================
//
// El backend devuelve similarity 0-1 (Tanimoto) y el adapter la convierte
// a 0-100 (x100) con null-safety: si similarity es null/undefined/NaN →
// null (el tab muestra "—"), nunca un número inválido.
//
// Tests cubren:
// - conversión 0-1 → 0-100 (números y strings numéricos)
// - null-safety: null, undefined, NaN → null
// - edge case similarity = 0 → 0 (no null)
// - fallbacks de id (raw.id ?? raw.molecule_id ?? index), smiles, deltas
// - passthrough de qed y lipinski_pass (true/false/null)

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, it, expect } from "vitest";

import { mapSarAnalog } from "../interfaces/pro/ProSarTab";

describe("mapSarAnalog — adapter SAR (null-safe)", () => {
  it("convierte similarity 0-1 (Tanimoto) a escala 0-100", () => {
    const analog = mapSarAnalog({ similarity: 0.923 }, 0);
    // 0.923 * 100 = 92.30000000000001 (float) — el UI lo muestra con toFixed(1)
    expect(analog.similarity).toBeCloseTo(92.3, 10);
  });

  it("convierte strings numéricos igual que números", () => {
    const analog = mapSarAnalog({ similarity: "0.85" }, 0);
    expect(analog.similarity).toBe(85);
  });

  it("similarity = 0 → 0 (no null: el 0 es un valor válido de Tanimoto)", () => {
    const analog = mapSarAnalog({ similarity: 0 }, 0);
    expect(analog.similarity).toBe(0);
  });

  it("similarity null → null (fallback visual '—', no mock)", () => {
    const analog = mapSarAnalog({ similarity: null }, 0);
    expect(analog.similarity).toBeNull();
  });

  it("similarity undefined → null", () => {
    const analog = mapSarAnalog({}, 0);
    expect(analog.similarity).toBeNull();
  });

  it("similarity no-numérico (NaN) → null", () => {
    const analog = mapSarAnalog({ similarity: "abc" }, 0);
    expect(analog.similarity).toBeNull();
  });

  it("id: usa raw.id, si no raw.molecule_id, si no el índice", () => {
    expect(mapSarAnalog({ id: 7 }, 2).id).toBe(7);
    expect(mapSarAnalog({ molecule_id: 9 }, 2).id).toBe(9);
    expect(mapSarAnalog({}, 2).id).toBe(2);
  });

  it("smiles con fallback a '—'", () => {
    expect(mapSarAnalog({ smiles: "CCO" }, 0).smiles).toBe("CCO");
    expect(mapSarAnalog({}, 0).smiles).toBe("—");
  });

  it("deltas ausentes permanecen null: nunca se fabrican ceros", () => {
    expect(mapSarAnalog({}, 0).delta_score).toBeNull();
    expect(mapSarAnalog({}, 0).delta_affinity).toBeNull();
    expect(mapSarAnalog({ delta_score: "abc", delta_affinity: Number.NaN }, 0).delta_score).toBeNull();
    expect(mapSarAnalog({ delta_score: "abc", delta_affinity: Number.NaN }, 0).delta_affinity).toBeNull();
    expect(mapSarAnalog({ delta_score: 1.5, delta_affinity: -0.8 }, 0).delta_score).toBe(1.5);
    expect(mapSarAnalog({ delta_score: 1.5, delta_affinity: -0.8 }, 0).delta_affinity).toBe(-0.8);
  });

  it("qed: null-safe con conversión numérica", () => {
    expect(mapSarAnalog({ qed: 0.87 }, 0).qed).toBe(0.87);
    expect(mapSarAnalog({ qed: null }, 0).qed).toBeNull();
    expect(mapSarAnalog({ qed: "no calculado" }, 0).qed).toBeNull();
    expect(mapSarAnalog({}, 0).qed).toBeNull();
  });

  it("lipinski: true/false/null según lipinski_pass", () => {
    expect(mapSarAnalog({ lipinski_pass: true }, 0).lipinski).toBe(true);
    expect(mapSarAnalog({ lipinski_pass: false }, 0).lipinski).toBe(false);
    expect(mapSarAnalog({ lipinski_pass: null }, 0).lipinski).toBeNull();
    expect(mapSarAnalog({}, 0).lipinski).toBeNull();
  });

  it("highlight con fallback a '—'", () => {
    expect(mapSarAnalog({ highlight: "N-metilación" }, 0).highlight).toBe("N-metilación");
    expect(mapSarAnalog({}, 0).highlight).toBe("—");
  });

  it("no conserva análogos ficticios ni lenguaje de modo demo", () => {
    const source = readFileSync(
      resolve(process.cwd(), "components/interfaces/pro/ProSarTab.tsx"),
      "utf8",
    );
    expect(source).not.toContain("MOCK_ANALOGS");
    expect(source).not.toContain("modo demo/mock");
    expect(source).toContain('t("auto_51a229f168ca")');
  });
});
