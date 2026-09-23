import { describe, expect, it } from "vitest";

import { LANGUAGES, TRANSLATIONS, type Locale } from "../../context/LanguageContext";

/**
 * Un idioma ofrecido tiene que estar completo.
 *
 * POR QUÉ EXISTE ESTA PRUEBA. La aplicación llegó a traer trece bloques de
 * idioma. Medidos: español e inglés con 258 claves cada uno, y los otros once
 * con **91** — faltaban 167 por idioma, alrededor del 65 % de la interfaz.
 *
 * No eran alcanzables: `LANGUAGES` sólo listaba `es` y `en`, y ese conjunto se
 * comprueba en los tres puntos donde se elige idioma. Pero viajaban en el
 * bundle y eran una trampa: añadir un código a `LANGUAGES` habría encendido una
 * interfaz traducida a un tercio, sin que nada avisara.
 *
 * Microsoft rechaza por calidad una aplicación cuyos idiomas declarados no están
 * realmente soportados, y con razón: el usuario ve media pantalla en otro
 * idioma. Esta prueba ata las dos cosas que tienen que ir juntas — lo que se
 * OFRECE y lo que está TRADUCIDO — para que no puedan separarse otra vez.
 */

const REFERENCIA: Locale = "es";

/** Claves que legítimamente coinciden entre idiomas: nombres propios y siglas. */
const INTRADUCIBLES = new Set([
  "MolDesign", "Moldex", "MolChat", "AutoDock Vina", "Vina",
  "RDKit", "PDB", "SMILES", "Open Babel", "ESMFold", "TabPFN", "Batch", "Error",
  "PDB ID", "Selector", "Pose", "poses", "Vina top-1", "Vina top-1 (original)",
  "Δ pose 1–2", "Local-First", "Copyleft", "source-available", "Hotspots",
  "Score", "Total", "Target",
]);

/**
 * Un formato o una unidad coincide entre idiomas POR SER CORRECTO.
 *
 * `{n} min` y `kcal/mol` se escriben igual en castellano y en inglés, y
 * «traducirlos» sería inventarse una unidad. Se reconoce por la forma —sólo
 * marcadores, cifras, separadores y símbolos de unidad— en vez de por una lista
 * de valores: una lista hay que ampliarla cada vez que aparece una unidad
 * nueva, y quien la amplía acaba metiendo ahí una frase de verdad para callar
 * la prueba.
 */
const UNIDADES = ["s", "min", "h", "ms", "Å", "kcal/mol", "%", "×", "°C", "pH", "Da"];

export function esFormatoOUnidad(valor: string): boolean {
  // Una unidad entera primero: `kcal/mol` lleva dentro un separador y trocearla
  // daría «kcal» y «mol», que por separado no son unidades de nada.
  if (UNIDADES.includes(valor.trim())) return true;
  if (/^[a-z]{2}-[A-Z]{2}$/.test(valor.trim())) return true;
  const sinMarcadores = valor.replace(/\{\w+\}/g, " ");
  const restos = sinMarcadores
    .split(/[\s,:;·/()–—-]+/)
    .map((parte) => parte.trim())
    .filter((parte) => parte.length > 0 && !/^[\d.]+$/.test(parte));
  return restos.length > 0 && restos.every((parte) => UNIDADES.includes(parte));
}

describe("idiomas de la interfaz", () => {
  it("ofrece al menos español e inglés", () => {
    const codigos = LANGUAGES.map((l) => l.code);
    expect(codigos).toContain("es");
    expect(codigos).toContain("en");
  });

  it("cada idioma ofrecido tiene un bloque de traducción", () => {
    for (const { code } of LANGUAGES) {
      expect(TRANSLATIONS[code], `falta el bloque de ${code}`).toBeDefined();
    }
  });

  it("no hay bloques de traducción que nadie pueda elegir", () => {
    // Un bloque inalcanzable es peso muerto en el bundle y una trampa para
    // quien amplíe LANGUAGES sin mirar si está completo.
    const ofrecidos = new Set(LANGUAGES.map((l) => l.code));
    const conBloque = Object.keys(TRANSLATIONS) as Locale[];
    const huerfanos = conBloque.filter((c) => !ofrecidos.has(c));
    expect(huerfanos, `bloques sin idioma que los ofrezca: ${huerfanos.join(", ")}`)
      .toEqual([]);
  });

  it("cada idioma ofrecido tiene TODAS las claves de la referencia", () => {
    const claves = Object.keys(TRANSLATIONS[REFERENCIA]);
    for (const { code } of LANGUAGES) {
      if (code === REFERENCIA) continue;
      const faltan = claves.filter((k) => !(k in TRANSLATIONS[code]));
      expect(
        faltan,
        `${code} no tiene ${faltan.length} de ${claves.length} claves. ` +
          `Un idioma a medias es un rechazo por calidad: ${faltan.slice(0, 8).join(", ")}`,
      ).toEqual([]);
    }
  });

  it("ningún idioma deja cadenas sin traducir copiadas de la referencia", () => {
    const referencia = TRANSLATIONS[REFERENCIA];
    for (const { code } of LANGUAGES) {
      if (code === REFERENCIA) continue;
      const copiadas = Object.entries(TRANSLATIONS[code])
        .filter(([k, v]) =>
          referencia[k] === v
          && !INTRADUCIBLES.has(v)
          && !esFormatoOUnidad(v)
          && v.length > 3)
        .map(([k]) => k);
      expect(
        copiadas,
        `${code} repite ${copiadas.length} cadenas de ${REFERENCIA} sin traducir: ` +
          copiadas.slice(0, 8).join(", "),
      ).toEqual([]);
    }
  });

  it("ningún texto promete que nada sale del dispositivo", () => {
    // El producto tiene proveedores de IA en la nube opcionales, descargas de
    // Hugging Face y consultas a RCSB PDB. Un absoluto aquí es falso, y además
    // contradice PRIVACY.md.
    const absolutos = [
      /nunca sal\w* de este dispositivo/i,
      /never leaves this device/i,
      /100\s*%\s*local/i,
      /100\s*%\s*offline/i,
    ];
    const infractores: string[] = [];
    for (const [code, bloque] of Object.entries(TRANSLATIONS)) {
      for (const [clave, valor] of Object.entries(bloque)) {
        if (absolutos.some((re) => re.test(valor))) {
          infractores.push(`${code}.${clave}: ${valor}`);
        }
      }
    }
    expect(infractores, `afirmaciones absolutas de privacidad:\n  ${infractores.join("\n  ")}`)
      .toEqual([]);
  });
});
