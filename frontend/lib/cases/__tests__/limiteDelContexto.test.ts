// AMP-06. El límite que el formulario enseña tiene que ser el que el dossier
// acepta: se lee de `ContextoCientifico` en el backend y falla si se separan.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import {
  CASE_CONTEXT_FIELDS,
  CASE_CONTEXT_MAX_CHARS,
  CASE_CONTEXT_SPECS,
  contextOverLimit,
} from "../types";

const SCHEMAS = resolve(__dirname, "..", "..", "..", "..", "backend", "services", "dossier", "schemas.py");

function limitesDelBackend(): Record<string, number> {
  // Con `core.autocrlf=true` (lo habitual en Windows) un clon o un worktree deja
  // `schemas.py` en CRLF, y las expresiones de abajo buscan dos saltos LF: la
  // prueba fallaba en cualquier copia nueva y sólo pasaba donde eran LF.
  const fuente = readFileSync(SCHEMAS, "utf-8").replace(/\r\n/g, "\n");
  const bloque = /class ContextoCientifico\(_Base\):([\s\S]*?)\n\nclass /.exec(fuente)?.[1];
  if (!bloque) throw new Error("schemas.py ya no define ContextoCientifico");
  const limites: Record<string, number> = {};
  for (const m of bloque.matchAll(/^\s{4}(\w+): str \| None = Field\(default=None, max_length=(\d+)\)/gm)) {
    limites[m[1]] = Number(m[2]);
  }
  return limites;
}

describe("límite de texto del contexto: formulario = dossier", () => {
  it("cada texto libre del contexto tiene en el backend el mismo máximo que el formulario", () => {
    const backend = limitesDelBackend();
    for (const field of CASE_CONTEXT_FIELDS) {
      const clave = field.replace(/[A-Z]/g, (l) => `_${l.toLowerCase()}`);
      expect(backend[clave], `${clave} sin max_length en el backend`).toBe(CASE_CONTEXT_MAX_CHARS);
    }
  });

  it("el guardián ve: sin el bloque del contrato falla en voz alta", () => {
    expect(() => {
      const vacio = "";
      if (!/class ContextoCientifico/.exec(vacio)) throw new Error("schemas.py ya no define ContextoCientifico");
    }).toThrow(/ya no define/);
  });

  it("contextOverLimit nombra campo, longitud y exceso; 4000 exactos caben", () => {
    expect(contextOverLimit({ question: "a".repeat(4000) })).toEqual([]);
    expect(contextOverLimit({ question: "a".repeat(4366), notes: "b".repeat(4001) })).toEqual([
      { field: "question", length: 4366, excess: 366 },
      { field: "notes", length: 4001, excess: 1 },
    ]);
  });

  it("las notas declaran que aparecen en el dossier (AMP-05)", () => {
    const notas = CASE_CONTEXT_SPECS.find((spec) => spec.field === "notes");
    expect(notas?.hint).toContain("Aparece en el dossier");
    expect(notas?.hint).not.toMatch(/^Contexto libre\. No entra/);
  });
});
