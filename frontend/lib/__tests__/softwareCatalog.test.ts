import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { CARD_TRANSLATION_KEYS } from "@/components/ui/AboutModal";
import { TEXTOS_DE_LA_FILA } from "@/components/ui/LegalModal";
import { legal } from "@/context/traducciones/legal";
import { paneles } from "@/context/traducciones/paneles";

import { LICENSE_HIGHLIGHTS, SOFTWARE_SECTIONS } from "../softwareCatalog";

describe("softwareCatalog", () => {
  it("mantiene nombres únicos y no enseña lo que 1.0.2 no tiene", () => {
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    expect(new Set(cards.map((card) => card.name)).size).toBe(cards.length);
    // El menú de motores dejó de ofrecerlos el 2026-10-07 (frontend/lib/motores.ts) y faster-whisper no viaja en el
    // runtime: una ficha «Servicio externo» o «Incluido» decía que estaban (2026-10-11).
    for (const name of ["DiffDock", "ColabFold", "RFdiffusion", "faster-whisper"]) {
      expect(cards.some((card) => card.name === name)).toBe(false);
    }
  });

  it("cada ficha y cada fila de licencias tiene su texto en los dos idiomas", () => {
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    for (const card of cards) {
      const claves = CARD_TRANSLATION_KEYS[card.name];
      expect(claves, card.name).toBeDefined();
      for (const clave of Object.values(claves ?? {})) {
        expect(paneles.es[clave], clave).toBeTruthy();
        expect(paneles.en[clave], clave).toBeTruthy();
      }
    }
    for (const item of LICENSE_HIGHLIGHTS) {
      const textos = TEXTOS_DE_LA_FILA[item.name];
      expect(textos, item.name).toBeDefined();
      for (const clave of Object.values(textos ?? {})) {
        expect(legal.es[clave], clave).toBeTruthy();
        expect(legal.en[clave], clave).toBeTruthy();
      }
      // En castellano, el texto traducido es el mismo que guarda el catálogo.
      expect(legal.es[textos!.rol]).toBe(item.role);
    }
  });

  it("declara Molcy, Blender y Molecular Nodes con su GPL y como programas aparte", () => {
    const manifiesto = JSON.parse(readFileSync(resolve(__dirname, "../../../tools/molcy/molcy-manifest.json"), "utf-8"));
    const commit = String(manifiesto.fuente.commit).slice(0, 7);
    const cards = SOFTWARE_SECTIONS.flatMap((section) => section.cards);
    for (const nombre of ["Motor Molcy", "Blender", "Molecular Nodes"]) {
      const fila = LICENSE_HIGHLIGHTS.find((item) => item.name === nombre);
      expect(fila?.license, nombre).toBe("GPL-3.0-or-later");
      expect(fila?.attention, nombre).toBe("copyleft");
      expect(fila?.linkage, nombre).toBe("subproceso");
      expect(cards.some((card) => card.name === nombre), nombre).toBe(true);
    }
    // La copia del motor que viaja es la del manifiesto: la ficha no puede nombrar otro commit.
    expect(LICENSE_HIGHLIGHTS.find((item) => item.name === "Motor Molcy")?.version).toBe(commit);
    expect(cards.find((card) => card.name === "Motor Molcy")?.version).toBe(commit);
    // Blender y Molecular Nodes no viajan en el instalador: se descargan a petición.
    expect(cards.find((card) => card.name === "Blender")?.availability).toBe("Opcional");
    expect(cards.find((card) => card.name === "Molecular Nodes")?.availability).toBe("Opcional");
  });

  it("nombra las bibliotecas con copyleft del runtime que el SBOM inventaría", () => {
    for (const [nombre, licencia] of [
      ["Meeko", "LGPL-2.1-or-later"],
      ["MDAnalysis", "LGPL-3.0-or-later"],
      ["GridDataFormats", "LGPL-3.0-or-later"],
      ["paramiko", "LGPL-2.1"],
      ["gemmi", "MPL-2.0"],
    ]) {
      const fila = LICENSE_HIGHLIGHTS.find((item) => item.name === nombre);
      expect(fila?.license, nombre).toBe(licencia);
      expect(fila?.attention, nombre).toBe("copyleft");
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
  it("reconoce a MolTalk como método adaptado, con su aviso MIT y sin decir que viaja su código", () => {
    // Junto a Ketcher y los visores: es de la visualización, no una fuente de datos.
    const plataforma = SOFTWARE_SECTIONS.find((section) => section.id === "platform")!;
    const ficha = plataforma.cards.find((card) => card.name === "MolTalk");
    const fila = LICENSE_HIGHLIGHTS.find((item) => item.name === "MolTalk");
    // Ni «Incluido» ni «biblioteca»: no se distribuye código suyo, se reimplementa su método.
    expect(ficha?.availability).toBe("Método adaptado");
    expect(ficha?.credit).toContain("Dominic Fico");
    expect(fila?.license).toBe("MIT");
    expect(fila?.linkage).toBe("metodo");
    expect(fila?.sourceUrl).toBe("https://github.com/DomFico/moltalk");
    // La MIT pide conservar su aviso al adaptar su código: el índice legal lo lleva íntegro.
    const avisos = readFileSync(resolve(__dirname, "../../public/legal/THIRD_PARTY_NOTICES.md"), "utf-8");
    expect(avisos).toContain("## MolTalk — método adaptado, MIT");
    expect(avisos).toContain("Copyright (c) 2026 Dominic Fico");
    expect(avisos).toContain("The above copyright notice and this permission notice shall be included");
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