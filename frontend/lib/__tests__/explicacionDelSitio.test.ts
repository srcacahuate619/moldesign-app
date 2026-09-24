// =====================================================================
// La explicación del sitio: específica por receptor, y sin inventar nada
// =====================================================================
//
// EL FALLO QUE FIJA. Lo que el producto sabe del sitio de un receptor cabía
// entero en el atributo `title` de un chip de 10 px: hay que acertarle con el
// ratón, no existe en táctil y con teclado no se alcanza. La frase que más
// importa —«el ligando acoplará contra parte de la cavidad»— estaba enterrada
// ahí, y aplica a 110 de los 380 receptores del catálogo.
//
// LO QUE SE PRUEBA, en orden de importancia:
//
//   1. Que la advertencia que cambia cómo leer la afinidad SE DICE, y que va
//      antes que la procedencia. Quien sólo lee el primer párrafo tiene que
//      haberla visto.
//   2. Que la evidencia débil se declara débil. 109 receptores no tienen
//      ligando co-cristalizado, y presentarlos igual que los 271 que sí lo
//      tienen sería afirmar de más.
//   3. Que un campo ausente se dice, no se rellena.
//   4. Que el texto es DE ESTE receptor: sus cadenas, sus átomos, su ligando.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { explicarSitio } from "../sitioDelReceptor";

/**
 * El catálogo REAL que viaja en el instalador, no una maqueta.
 *
 * La pregunta que motivó esto era «¿podemos explicarlo para cada uno de los
 * 380?», y sólo se contesta ejecutándolo sobre los 380. Una maqueta de tres
 * receptores demuestra que la función corre, no que el catálogo tenga los datos.
 *
 * Se lee la fuente versionada de la raíz, no la copia de `src-tauri/resources/`.
 * Es el mismo fichero: `scripts/bundle_helper.py` lo copia byte a byte
 * (`shutil.copy2`) al hacer el staging. Pero la copia sólo existe después del
 * staging, y la prueba fallaba en cualquier clon limpio, incluida la CI pública
 * (2026-09-23, canal entre sesiones B→F-006).
 */
const CATALOGO = JSON.parse(
  readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "curated_targets.json"),
    "utf8",
  ),
) as Parameters<typeof explicarSitio>[0][];

/** 1WBM: proteasa del VIH, el caso de libro de una interfaz sin preparar. */
const INTERFAZ = {
  pdb_id: "1WBM",
  name: "HIV-1 PROTEASE",
  organism: "HUMAN IMMUNODEFICIENCY VIRUS 1",
  resolution: 2.0,
  chain: "A",
  site_chains: ["B", "A"],
  site_chain_atoms: { B: 46, A: 45 },
  site_evidence: "cocrystal_ligand" as const,
  site_ligand: "BEA450",
  hotspots: [{ name: "A:ASP29", importance: 1 }, { name: "B:ASP29", importance: 0.97 }],
  hotspots_source: "auto_pocket_top15" as const,
};

const UNA_CADENA = {
  ...INTERFAZ,
  pdb_id: "1ABC",
  site_chains: ["A"],
  site_chain_atoms: { A: 91 },
};

const SIN_CRISTAL = {
  ...UNA_CADENA,
  pdb_id: "2XYZ",
  site_evidence: "box_volume" as const,
  site_ligand: null,
};

function textoEntero(target: Parameters<typeof explicarSitio>[0]): string {
  const e = explicarSitio(target);
  return [e.titular, ...e.secciones.map((s) => `${s.pregunta} ${s.respuesta}`)].join(" ");
}

describe("la advertencia que cambia el número", () => {
  it("dice que el ligando acoplará contra parte de la cavidad", () => {
    const texto = textoEntero(INTERFAZ);
    expect(texto).toMatch(/parte de la cavidad/i);
    expect(texto).toMatch(/conserva sólo la cadena 'A'/i);
  });

  it("va ANTES que la procedencia: quien lea poco tiene que haberla visto", () => {
    const secciones = explicarSitio(INTERFAZ).secciones;
    const consecuencia = secciones.findIndex((s) => /tu resultado/i.test(s.pregunta));
    const evidencia = secciones.findIndex((s) => /cómo lo sabemos/i.test(s.pregunta));
    expect(consecuencia).toBeGreaterThanOrEqual(0);
    expect(consecuencia).toBeLessThan(evidencia);
  });

  it("la marca como aviso, no como texto corrido", () => {
    const seccion = explicarSitio(INTERFAZ).secciones
      .find((s) => /tu resultado/i.test(s.pregunta));
    expect(seccion?.tono).toBe("aviso");
  });

  it("NO la inventa cuando el sitio cabe en una cadena", () => {
    const secciones = explicarSitio(UNA_CADENA).secciones;
    expect(secciones.some((s) => /tu resultado/i.test(s.pregunta))).toBe(false);
    expect(textoEntero(UNA_CADENA)).not.toMatch(/parte de la cavidad/i);
  });
});

describe("la evidencia se declara por lo que es", () => {
  it("con cristal: nombra el ligando que lo demuestra y la distancia medida", () => {
    const texto = textoEntero(INTERFAZ);
    expect(texto).toContain("BEA450");
    expect(texto).toMatch(/4,5 Å/);
  });

  it("sin cristal: lo llama pista, no medida, y lo marca como aviso", () => {
    const evidencia = explicarSitio(SIN_CRISTAL).secciones
      .find((s) => /cómo lo sabemos/i.test(s.pregunta));
    expect(evidencia?.respuesta).toMatch(/no es una medida|no una medida|pista razonable/i);
    expect(evidencia?.tono).toBe("aviso");
    // Y no se cuela un código de ligando que esta estructura no tiene.
    expect(evidencia?.respuesta).not.toContain("BEA450");
  });

  it("sin evidencia registrada, lo dice en vez de suponer la fuerte", () => {
    const sinNada = { ...UNA_CADENA, site_evidence: null, site_ligand: null };
    const evidencia = explicarSitio(sinNada).secciones
      .find((s) => /cómo lo sabemos/i.test(s.pregunta));
    expect(evidencia?.respuesta).toMatch(/no registra|no podemos decirte/i);
    expect(evidencia?.tono).toBe("aviso");
  });
});

describe("el texto es de ESTE receptor", () => {
  it("nombra sus cadenas y el reparto de átomos que se midió", () => {
    const texto = textoEntero(INTERFAZ);
    expect(texto).toMatch(/'B' aporta 46 átomos/);
    expect(texto).toMatch(/'A' aporta 45 átomos/);
  });

  it("nombra su entrada del PDB, su organismo y su resolución", () => {
    const texto = textoEntero(INTERFAZ);
    expect(texto).toContain("1WBM");
    expect(texto).toContain("HUMAN IMMUNODEFICIENCY VIRUS 1");
    expect(texto).toContain("2.0 Å");
  });

  it("explica que en resolución MENOS es mejor: nadie lo adivina", () => {
    expect(textoEntero(INTERFAZ)).toMatch(/cuanto MENOR/);
  });

  it("no confunde un receptor con otro", () => {
    expect(textoEntero(UNA_CADENA)).toContain("1ABC");
    expect(textoEntero(UNA_CADENA)).not.toContain("1WBM");
  });
});

describe("un sitio sin medir no se lee como una sola cadena", () => {
  const sinMedir = { ...UNA_CADENA, site_chains: null, site_chain_atoms: null };

  it("lo declara y avisa", () => {
    const seccion = explicarSitio(sinMedir).secciones[0];
    expect(seccion.respuesta).toMatch(/no lo hemos medido/i);
    expect(seccion.tono).toBe("aviso");
  });

  it("no afirma que la cadena declarada sea la única del hueco", () => {
    expect(textoEntero(sinMedir)).toMatch(/no podemos afirmar que sea la única/i);
  });
});

describe("forma del texto", () => {
  it("toda sección tiene pregunta y respuesta no vacías", () => {
    for (const target of [INTERFAZ, UNA_CADENA, SIN_CRISTAL]) {
      for (const s of explicarSitio(target).secciones) {
        expect(s.pregunta.trim().length).toBeGreaterThan(0);
        expect(s.respuesta.trim().length).toBeGreaterThan(20);
      }
    }
  });

  it("una interfaz de muchas cadenas se cuenta en vez de enumerarse", () => {
    const diez = {
      ...INTERFAZ,
      site_chains: ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
      site_chain_atoms: Object.fromEntries("ABCDEFGHIJ".split("").map((c) => [c, 60])),
    };
    expect(explicarSitio(diez).titular).toMatch(/10 cadenas/);
  });

  it("el titular no promete lo que el detalle luego matiza", () => {
    // Un titular tranquilo en un receptor con aviso sería el peor resultado:
    // quien no abra el detalle se lleva la impresión contraria.
    const e = explicarSitio(INTERFAZ);
    expect(e.titular).toMatch(/juntura|interfaz/i);
  });
});

describe("los 380 receptores del catálogo que viaja", () => {
  it("son 380 y todos producen una explicación", () => {
    expect(CATALOGO.length).toBe(380);
    for (const target of CATALOGO) {
      const e = explicarSitio(target);
      expect(e.titular.length).toBeGreaterThan(10);
      expect(e.secciones.length).toBeGreaterThanOrEqual(4);
    }
  });

  it("cada explicación nombra SU receptor: 380 titulares, ningún hueco", () => {
    for (const target of CATALOGO) {
      const texto = explicarSitio(target).secciones.map((s) => s.respuesta).join(" ");
      expect(texto).toContain(target.pdb_id);
      // Un `undefined` interpolado es la forma en que un campo ausente se
      // convierte en una frase sin sentido. No debe aparecer ni una vez.
      expect(texto).not.toMatch(/undefined|null|NaN|\[object/);
    }
  });

  it("los 110 de interfaz sin preparar llevan su advertencia; los 270 no", () => {
    let conAviso = 0;
    let multicadena = 0;
    for (const target of CATALOGO) {
      const cadenas = new Set((target.site_chains ?? []).filter(Boolean));
      const avisa = explicarSitio(target).secciones
        .some((s) => /tu resultado/i.test(s.pregunta));
      if (cadenas.size > 1) {
        multicadena += 1;
        // Éste es el invariante que importa: NINGÚN receptor de interfaz puede
        // quedarse sin decir que el acoplamiento ve media cavidad.
        expect(avisa).toBe(true);
      } else {
        expect(avisa).toBe(false);
      }
      if (avisa) conAviso += 1;
    }
    expect(multicadena).toBe(110);
    expect(conAviso).toBe(110);
  });

  it("los 109 sin ligando co-cristalizado declaran su evidencia más débil", () => {
    let debiles = 0;
    for (const target of CATALOGO) {
      const evidencia = explicarSitio(target).secciones
        .find((s) => /cómo lo sabemos/i.test(s.pregunta));
      if (target.site_evidence === "box_volume") {
        debiles += 1;
        expect(evidencia?.tono).toBe("aviso");
      } else if (target.site_evidence === "cocrystal_ligand") {
        expect(evidencia?.tono).toBeUndefined();
        // La evidencia fuerte nombra el ligando que la sostiene.
        if (target.site_ligand) expect(evidencia?.respuesta).toContain(target.site_ligand);
      }
    }
    expect(debiles).toBe(109);
  });

  it("ninguno se queda sin decir de dónde salen sus residuos marcados", () => {
    for (const target of CATALOGO) {
      const hs = explicarSitio(target).secciones
        .find((s) => /residuos marcados/i.test(s.pregunta));
      expect(hs?.respuesta).toMatch(/Ninguno viene del Protein Data Bank/);
    }
  });
});
