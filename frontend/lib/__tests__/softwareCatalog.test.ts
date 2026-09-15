import { describe, expect, it } from "vitest";

import { LICENSE_HIGHLIGHTS, SOFTWARE_SECTIONS } from "../softwareCatalog";

describe("softwareCatalog", () => {
  it("mantiene nombres únicos y clasifica adaptadores pesados como servicios externos", () => {
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    expect(new Set(cards.map((card) => card.name)).size).toBe(cards.length);
    for (const name of ["DiffDock", "ColabFold", "RFdiffusion"]) {
      expect(cards.find((card) => card.name === name)?.availability).toBe("Servicio externo");
    }
  });

  it("declara el catálogo de receptores con sus dos fuentes y obligaciones separadas", () => {
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    const rcsb = LICENSE_HIGHLIGHTS.find((item) => item.name === "RCSB Protein Data Bank / wwPDB");
    const uniprot = LICENSE_HIGHLIGHTS.find((item) => item.name === "UniProtKB");
    const catalog = cards.find((card) => card.name === "Catálogo MolDesign");

    expect(rcsb?.license).toBe("CC0 1.0");
    expect(rcsb?.version).toBe("380 estructuras");
    expect(rcsb?.role).toContain("380 receptores curados");
    expect(rcsb?.attention).toBeUndefined();
    expect(uniprot?.license).toBe("CC BY 4.0");
    expect(uniprot?.attention).toBe("attribution");
    expect(uniprot?.role).toContain("Fuente: UniProtKB;");
    expect(uniprot?.role).toContain("traducción/adaptación al español: MolDesign");
    expect(catalog?.version).toBe("380 receptores curados");
    expect(catalog?.description).toContain("hotspots");
    expect(catalog?.credit).toContain("RCSB y UniProt no certifican");
  });
  it("conserva las atribuciones y licencias de distribución críticas", () => {
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    expect(cards.find((card) => card.name === "TabPFN")?.credit).toBe("Built with PriorLabs-TabPFN");
    expect(cards.some((card) => card.name === "llama.cpp")).toBe(true);
    expect(LICENSE_HIGHLIGHTS.find((item) => item.name === "RTMScore")?.license).toBe("MIT");
  });

  // ── Open Babel: la pantalla decía algo que no era verdad ────────────────
  //
  // Declaraba `GPL-2.0-or-later`. Open Babel dice «GNU General Public License,
  // versión 2», sin la coletilla «o posterior». Ese "or-later" concedía un
  // permiso que sus autores no dieron y, de paso, hacía desaparecer del informe
  // la incompatibilidad entre GPL-2.0-only y la familia GPL-3 (AGPL-3.0
  // incluida) — que es exactamente la razón por la que este componente se
  // ejecuta como programa aparte. Ver docs/79_ADR_FRONTERA_OPEN_BABEL.md.
  it("declara Open Babel como GPL-2.0-only y como programa independiente", () => {
    const openBabel = LICENSE_HIGHLIGHTS.find((item) => item.name === "Open Babel");
    expect(openBabel).toBeDefined();
    expect(openBabel?.license).toBe("GPL-2.0-only");
    expect(openBabel?.version).toBe("3.1.1.23");
    expect(openBabel?.attention).toBe("copyleft");
    expect(openBabel?.linkage).toBe("subproceso");
    expect(openBabel?.role).toContain("3.1.0");
  });

  it("ningún componente vuelve a declararse GPL-2.0-or-later", () => {
    // Guarda de regresión sobre TODA la lista, no sólo sobre Open Babel: la
    // forma equivocada se copia con facilidad.
    for (const item of LICENSE_HIGHLIGHTS) {
      expect(item.license).not.toBe("GPL-2.0-or-later");
    }
  });

  it("la ficha de Open Babel describe la invocación real, no una genérica", () => {
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    const ficha = cards.find((card) => card.name === "Open Babel");
    expect(ficha?.description).toContain("línea de órdenes");
    expect(ficha?.description).toContain("No se enlaza");
    expect(ficha?.description).toContain("3.1.0");
  });
});