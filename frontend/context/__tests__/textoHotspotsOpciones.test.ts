// =====================================================================
// SOL-09 — el texto de Opciones no puede prometer lo que el motor no hace
// =====================================================================
//
// La auditoría inspeccionó la invocación real de Vina: recibe receptor,
// ligando, caja, exhaustividad, poses, CPU y semilla. NINGÚN restraint ni
// mapa derivado de los hotspots. Decir que «definen qué residuos guían la
// búsqueda» hacia creer que desmarcar un residuo cambia el espacio
// explorado — cuando la región la define la caja y los hotspots sólo son
// referencias para describir el sitio y analizar los contactos de las
// poses.
//
// Este archivo fija el texto del diccionario en los dos idiomas: la clave
// `op_hotspots_explicacion` es una ADVERTENCIA CIENTÍFICA (el propio
// módulo lo dice), y su corrección no puede depender de que nadie la
// reescriba por accidente.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { opciones } from "../traducciones/opciones";

const es = opciones.es.op_hotspots_explicacion;
const en = opciones.en.op_hotspots_explicacion;

describe("SOL-09: op_hotspots_explicacion dice la verdad", () => {
  it("en español: la única mención de guía de búsqueda es la negada", () => {
    // El texto viejo la AFIRMABA («Define qué residuos… guían la búsqueda»).
    // El honesto la niega y dice qué son: referencias; la caja manda.
    const menciones = es.match(/gu[ií]an la b[uú]squeda/gi) ?? [];
    const negadas = es.match(/no gu[ií]an la b[uú]squeda/gi) ?? [];
    expect(menciones.length).toBe(negadas.length);
    expect(es).toMatch(/la caja/i);
    expect(es).toMatch(/referencia/i);
  });

  it("en inglés: la misma honestidad, no una traducción blanda", () => {
    const menciones = en.match(/guide (?:the|Vina's) search/gi) ?? [];
    const negadas = en.match(/do not guide/gi) ?? [];
    expect(menciones.length).toBe(negadas.length);
    expect(en).toMatch(/box/i);
    expect(en).toMatch(/reference/i);
  });

  it("el modal sigue pintando la clave, no una copia suelta", () => {
    const source = readFileSync(
      resolve(process.cwd(), "components/interfaces/pro/ProOptionsModal.tsx"),
      "utf8",
    );
    expect(source).toContain('t("op_hotspots_explicacion")');
  });
});
