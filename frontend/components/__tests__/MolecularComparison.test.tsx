import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, within, cleanup, waitFor } from "@testing-library/react";
import type { MoldexMolecule } from "../../lib/moldex";
const idioma = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../context/LanguageContext")>();
  const t = (key: string, values?: Record<string, string | number>) => actual.interpolar(actual.TRANSLATIONS[idioma.locale][key] ?? key, values);
  return { ...actual, useLanguage: () => ({ t, locale: idioma.locale }), Translated: ({ id }: { id: string }) => <>{t(id)}</> };
});
vi.mock("../MoleculeViewer3D", () => ({ MoleculeViewer3D: () => null }));
vi.mock("../../lib/api", () => ({ getPoseFile: vi.fn(async () => "pose"), getProteinFile: vi.fn(async () => "protein") }));
import MolecularComparison from "../MolecularComparison";
import { getPoseFile, getProteinFile } from "../../lib/api";
function ficha(score: number, cal?: string): MoldexMolecule {
  return {
    id: String(score), entry_id: String(score), name: "Ligando", smiles: "CCO", smiles_hash: "hash",
    created_at: "2026-10-20", evaluated_at: null,
    target: { pdb_id: "NET", name: null, family: null, hotspots: [], spearman_rho: null },
    metrics: { affinity: -8, score, log_p: 2, mw: 300, tpsa: 60, gnn_score: null, lipinski_pass: null, veber_pass: null },
    provenance: { task_id: "t", receptor_sha256: "hash", engine_version: "1.2.7", random_seed: 42,
      docking_protocol: { engine: "vina", seed: 42 },
      protocolo: { calibracion_ranking: cal ?? null } as NonNullable<MoldexMolecule["provenance"]["protocolo"]> },
    scientific_warnings: [], hotspots_hit: [], blockchain: { certified: false, tx_signature: null, certified_task_id: null, certified_total_score: null, matches_current_run: null },
  };
}
// La fila se rotula «heredado» en el idioma de la interfaz (SUP-02-TOTAL-SCORE); antes quedaba en castellano también en inglés.
const filaIndice = () => screen.getByRole("row", {
  name: idioma.locale === "es" ? /ÍNDICE COMPUESTO HEREDADO \(0-100\)/ : /LEGACY COMPOSITE INDEX \(0-100\)/,
});
describe("SCI-A-013: resta del índice", () => {
  it.each(["es", "en"] as const)("conserva valores y explica los tres faltantes en %s", (locale) => {
    idioma.locale = locale;
    for (const [a, b] of [[undefined, "M4"], ["M4", undefined], [undefined, undefined]]) {
      render(<MolecularComparison molA={ficha(80, a)} molB={ficha(86, b)} onClose={() => {}} />);
      const cells = within(filaIndice()).getAllByRole("cell");
      expect(cells[0]).toHaveTextContent("80.00"); expect(cells[2]).toHaveTextContent("86.00");
      expect(cells[1]).toHaveTextContent("—"); expect(cells[1]).not.toHaveTextContent("+6.00");
      expect(cells[1].querySelector("span")).not.toHaveAttribute("title", locale === "es"
        ? "Falta el valor en al menos una de las dos moléculas"
        : "The value in at least one of the two molecules is missing");
      expect(cells[1]).toHaveTextContent(locale === "es"
        ? "No consta la calibración del ranking de al menos una corrida."
        : "The ranking calibration is not recorded for at least one run.");
      cleanup();
    }
  });
});


describe("SCI-A-012: descriptores independientes del docking", () => {
  it.each(["es", "en"] as const)("compara descriptores y abstiene índice con receptor o protocolo distinto (%s)", (locale) => {
    idioma.locale = locale;
    for (const incompatibilidad of ["receptor", "protocolo", "calibracion"] as const) {
      const a = ficha(80, "M4"), b = ficha(86, "M4");
      b.metrics = { ...b.metrics, log_p: 3, mw: 310, tpsa: 65 };
      if (incompatibilidad === "receptor") b.provenance.receptor_sha256 = "otro";
      if (incompatibilidad === "protocolo") b.provenance.docking_protocol = { engine: "vina", seed: 43 };
      if (incompatibilidad === "calibracion") b.provenance.protocolo!.calibracion_ranking = "M5";
      render(<MolecularComparison molA={a} molB={b} onClose={() => {}} />);
      for (const [nombre, delta] of [[/LOG P/, "+1.00"], [/PESO MOL|MOL. WEIGHT/, "+10.00"], [/TPSA/, "+5.00"]] as const) {
        const cells = within(screen.getByRole("row", { name: nombre })).getAllByRole("cell");
        expect(cells[1]).toHaveTextContent(delta);
        expect(cells[1].querySelector("span")).toHaveClass("text-slate-300");
      }
      const cells = within(filaIndice()).getAllByRole("cell");
      expect(cells[0]).toHaveTextContent("80.00"); expect(cells[2]).toHaveTextContent("86.00");
      expect(cells[1]).toHaveTextContent("—");
      expect(screen.getByRole("alert")).toHaveTextContent(locale === "es"
        ? "Comparación del docking limitada" : "Docking comparison is limited");
      expect(screen.getByRole("alert")).toHaveTextContent(locale === "es"
        ? "Los descriptores fisicoquímicos sí se comparan"
        : "Physicochemical descriptors can be compared");
      expect(screen.getByRole("alert")).toHaveTextContent(locale === "es"
        ? "el índice y las afinidades" : "the index and affinities");
      cleanup();
    }
  });
  it.each(["es", "en"] as const)("muestra cuatro filas, faltante real y diferencias neutras (%s)", (locale) => {
    idioma.locale = locale;
    const a = ficha(80, "M4"), b = ficha(86, "M4");
    a.metrics.log_p = null; b.metrics.mw = 290; b.metrics.tpsa = 70;
    render(<MolecularComparison molA={a} molB={b} onClose={() => {}} />);
    expect(screen.getAllByRole("row")).toHaveLength(5);
    expect(within(screen.getByRole("row", { name: /LOG P/ })).getAllByRole("cell")[1]).toHaveTextContent("—");
    expect(within(filaIndice()).getAllByRole("cell")[1]).toHaveTextContent("+6.00");
    for (const name of [/PESO MOL|MOL. WEIGHT/, /TPSA/]) {
      expect(within(screen.getByRole("row", { name })).getAllByRole("cell")[1].querySelector("span")).toHaveClass("text-slate-300");
    }
  });
});


describe("identidad de recursos del comparador de Moldex", () => {
  it("pide pose y receptor por corrida aunque ambas fichas sean de la misma molécula", async () => {
    vi.mocked(getPoseFile).mockClear(); vi.mocked(getProteinFile).mockClear();
    const a = ficha(80, "M4"), b = ficha(86, "M4");
    a.id = b.id = "misma-mol";
    a.provenance.task_id = "run-A"; b.provenance.task_id = "run-B";
    render(<MolecularComparison molA={a} molB={b} onClose={() => {}} />);
    await waitFor(() => expect(getProteinFile).toHaveBeenCalledWith("misma-mol", "run-B"));
    expect(getPoseFile).toHaveBeenCalledWith("misma-mol", "run-A");
    expect(getProteinFile).toHaveBeenCalledWith("misma-mol", "run-A");
    expect(getPoseFile).toHaveBeenCalledWith("misma-mol", "run-B");
  });

  it("sin identidad de corrida declara ausencia y no pide la proyección actual", async () => {
    idioma.locale = "es";
    vi.mocked(getPoseFile).mockClear(); vi.mocked(getProteinFile).mockClear();
    const a = ficha(80), b = ficha(86);
    a.provenance.task_id = b.provenance.task_id = null;
    render(<MolecularComparison molA={a} molB={b} onClose={() => {}} />);
    await waitFor(() => expect(screen.getAllByText(/La ficha no identifica una corrida/)).toHaveLength(2));
    expect(getPoseFile).not.toHaveBeenCalled();
    expect(getProteinFile).not.toHaveBeenCalled();
  });
});

it.each(["es", "en"] as const)("conserva nombres del investigador aunque empiecen con Ligando (%s)", async locale => {
  idioma.locale = locale;
  const a = ficha(80, "M4"), b = ficha(86, "M4");
  a.name = "Ligando de mi ensayo"; b.name = "My sample";
  const before = JSON.stringify([a,b]);
  render(<MolecularComparison molA={a} molB={b} onClose={() => {}} />);
  await waitFor(() => expect(screen.getByText(a.name, { exact: true })).toBeVisible());
  await waitFor(() => expect(screen.getByText(b.name, { exact: true })).toBeVisible());
  expect(JSON.stringify([a,b])).toBe(before);
});
