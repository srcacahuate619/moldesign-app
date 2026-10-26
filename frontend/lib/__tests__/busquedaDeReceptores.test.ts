import { describe, expect, it } from "vitest";

import type { Target } from "../api";
import { palabrasDe, puntuarReceptor } from "../busquedaDeReceptores";

// Los nombres son los REALES que dieron falsos positivos al buscar «ACE» en el catálogo
// (medido el 2026-10-03: 14 resultados y ninguno era la ACE humana).
function r(pdb: string, name: string, organism = "Homo sapiens"): Target {
  return { pdb_id: pdb, name, organism } as unknown as Target;
}

describe("palabrasDe", () => {
  it("minúsculas, sin tildes, y los signos separan", () => {
    expect(palabrasDe("Inhibición de ACE — 9,9,9-TRIFLUORO")).toEqual(["inhibicion", "de", "ace", "9", "9", "9", "trifluoro"]);
    expect(palabrasDe(null)).toEqual([]);
    expect(palabrasDe("  ")).toEqual([]);
  });
});

describe("puntuarReceptor (QA1-004)", () => {
  it("«ace» ya no casa por la mitad de una palabra", () => {
    for (const falso of ["ALCALIGENACEAE", "DEACETYLASE", "ANOACE2 PROTEIN", "Trace amine receptor"]) {
      expect(puntuarReceptor(r("1XXX", falso), "ace"), falso).toBe(0);
    }
  });

  it("control positivo: la palabra exacta y el comienzo de palabra sí casan, la exacta primero", () => {
    const exacta = puntuarReceptor(r("1O86", "ANGIOTENSIN CONVERTING ENZYME (ACE)"), "ace");
    const prefijo = puntuarReceptor(r("1AAA", "ACETYLCHOLINESTERASE"), "ace");
    expect(exacta).toBeGreaterThan(prefijo);
    expect(prefijo).toBeGreaterThan(0);
  });

  it("el nombre vale más que el organismo, y el PDB ID exacto vale como una palabra exacta", () => {
    const porNombre = puntuarReceptor(r("1AAA", "Protein kinase"), "kinase");
    const porOrganismo = puntuarReceptor(r("1BBB", "Other protein", "Kinase bacterium"), "kinase");
    expect(porNombre).toBeGreaterThan(porOrganismo);
    expect(porOrganismo).toBeGreaterThan(0);
    expect(puntuarReceptor(r("4AZY", "BACE1"), "4azy")).toBe(3);
  });

  it("escribir a medias sigue encontrando: «angio» casa con «angiotensin»", () => {
    expect(puntuarReceptor(r("1AAA", "Angiotensin II receptor"), "angio")).toBeGreaterThan(0);
  });

  it("todas las palabras tienen que casar", () => {
    const t = r("1AAA", "Angiotensin II receptor type 1");
    expect(puntuarReceptor(t, "angiotensin receptor")).toBeGreaterThan(0);
    expect(puntuarReceptor(t, "angiotensin kinase")).toBe(0);
  });

  it("ignora tildes y mayúsculas, también en la consulta", () => {
    expect(puntuarReceptor(r("1AAA", "Inhibición de la enzima"), "INHIBICION")).toBeGreaterThan(0);
    expect(puntuarReceptor(r("1AAA", "Inhibicion de la enzima"), "inhibición")).toBeGreaterThan(0);
  });

  it("una consulta vacía o de puros signos casa con todo", () => {
    expect(puntuarReceptor(r("1AAA", "Cualquiera"), "")).toBe(1);
    expect(puntuarReceptor(r("1AAA", "Cualquiera"), " - ")).toBe(1);
  });

  it("la familia entra como dato secundario", () => {
    expect(puntuarReceptor(r("1AAA", "Algo"), "protease", "protease")).toBe(1);
    expect(puntuarReceptor(r("1AAA", "Algo"), "protease", "kinase")).toBe(0);
  });
});
