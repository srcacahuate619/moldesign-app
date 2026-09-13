import { describe, it, expect } from "vitest";
import { describirSitio, avisoDeEvidencia, describirHotspots } from "../sitioDelReceptor";

// Los casos NO son inventados: son receptores reales del catálogo, con los
// números que midió `scripts/anotar_sitio_en_catalogo.py` sobre el PDB del
// RCSB. Si la anotación cambia, estas pruebas tienen que cambiar con ella.

describe("describirSitio", () => {
  it("nombra la cadena cuando el sitio lo forma una sola (1AJ6)", () => {
    const s = describirSitio({
      chain: "A",
      site_chains: ["A"],
      site_chain_atoms: { A: 43 },
      site_evidence: "cocrystal_ligand",
      site_ligand: "NOV",
    });
    expect(s.etiqueta).toBe("Cadena A");
    expect(s.tono).toBe("neutro");
    expect(s.interfazNoPreparada).toBe(false);
    expect(s.detalle).toContain("NOV");
  });

  it("dice «interfaz» y avisa cuando el sitio lo forman dos y se prepara una (1TW7)", () => {
    // La proteasa del VIH-1: homodímero con el sitio activo EN la interfaz.
    // Es el caso de libro del doc 71, y el que justifica el color ámbar.
    const s = describirSitio({
      chain: "A",
      site_chains: ["B", "A"],
      site_chain_atoms: { B: 316, A: 309 },
      site_evidence: "cocrystal_ligand",
      site_ligand: "TL3",
    });
    expect(s.etiqueta).toBe("Interfaz B·A");
    expect(s.tono).toBe("aviso");
    expect(s.interfazNoPreparada).toBe(true);
    expect(s.detalle).toContain("sólo 'A'");
  });

  it("cuenta en vez de nombrar cuando son muchas (9RAW, anillo de diez)", () => {
    const cadenas = ["C", "D", "E", "F", "G", "H", "I", "B", "J", "A"];
    const s = describirSitio({
      chain: "A",
      site_chains: cadenas,
      site_chain_atoms: Object.fromEntries(cadenas.map((c) => [c, 60])),
      site_evidence: "box_volume",
      site_ligand: null,
    });
    expect(s.etiqueta).toBe("Interfaz de 10 cadenas");
    expect(s.tono).toBe("aviso");
  });

  it("declara la evidencia débil en el detalle, sin teñir el chip", () => {
    // El color avisa de que el NÚMERO va a salir mal. La evidencia débil dice
    // cuánto fiarse de la ANOTACIÓN: son dos cosas y no comparten canal.
    const s = describirSitio({
      chain: "A",
      site_chains: ["A"],
      site_chain_atoms: { A: 200 },
      site_evidence: "box_volume",
      site_ligand: null,
    });
    expect(s.tono).toBe("neutro");
    expect(s.detalle).toContain("Sin ligando co-cristalizado");
  });

  it("no supone monómero cuando falta la medida", () => {
    // Un receptor subido por el usuario no trae anotación. Decir «Cadena A»
    // ahí sería afirmar algo que nadie midió: exactamente el defecto que el
    // doc 71 encontró en el catálogo curado.
    const s = describirSitio({ chain: "A", site_chains: null, site_chain_atoms: null,
      site_evidence: null, site_ligand: null });
    expect(s.etiqueta).toBe("Sitio sin medir");
    expect(s.tono).toBe("sin_medir");
    expect(s.etiqueta).not.toContain("Cadena A");
  });
});

describe("avisoDeEvidencia", () => {
  it("avisa sólo cuando la evidencia es el volumen", () => {
    expect(avisoDeEvidencia({ site_evidence: "box_volume" })).toBe("Sin ligando co-cristalizado");
    expect(avisoDeEvidencia({ site_evidence: "cocrystal_ligand" })).toBeNull();
    // Sin medida no se afirma que falte el ligando: no se sabe.
    expect(avisoDeEvidencia({ site_evidence: null })).toBeNull();
  });
});

describe("describirHotspots", () => {
  it("nunca presenta los hotspots como anotación del RCSB", () => {
    // Ninguno del catálogo lo es: los generó `recure_targets.py`. Decir lo
    // contrario —o callarlo— engaña al usuario en una de las dos direcciones.
    for (const source of ["auto_pocket_top15", "box_ligand_contacts", null] as const) {
      const h = describirHotspots({ hotspots_source: source, site_ligand: "REA" });
      expect(h.detalle).toContain("Ningún hotspot de este catálogo procede del RCSB");
    }
  });

  it("marca visiblemente sólo los re-derivados", () => {
    expect(describirHotspots({ hotspots_source: "box_ligand_contacts", site_ligand: "REA" }).etiqueta)
      .toBe("Hotspots re-derivados");
    expect(describirHotspots({ hotspots_source: "auto_pocket_top15", site_ligand: null }).etiqueta)
      .toBeNull();
  });

  it("nombra el ligando del que se re-derivaron (2VE3: la caja está en el REA, no en el HEMO)", () => {
    const h = describirHotspots({ hotspots_source: "box_ligand_contacts", site_ligand: "REA" });
    expect(h.detalle).toContain("REA");
    expect(h.detalle).toContain("otro bolsillo");
  });
});
