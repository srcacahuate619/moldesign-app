// =====================================================================
// Guardia: ninguna petición lleva el puerto escrito a mano
// =====================================================================
//
// EL FALLO QUE VIGILA. Rust elige el primer puerto libre del rango 8000-8019.
// En este equipo 8000 ya está ocupado por otro producto, así que el backend
// arranca en 8001 de manera rutinaria. Cualquier `http://127.0.0.1:8000`
// escrito a mano en el frontend deja de responder ese día, y el fallo aparece
// lejos de su causa: «la evaluación no funciona», sin más.
//
// Es un test estático a propósito. Un test de comportamiento sólo cubre el
// camino que ejercita; esto cubre el árbol entero, incluido el archivo que
// alguien añada mañana.

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import { describe, expect, it } from "vitest";

const ROOT = join(__dirname, "..", "..");

const SCANNED_DIRS = ["app", "components", "context", "hooks", "lib"];

/**
 * `lib/config.ts` es el ÚNICO sitio donde puede aparecer el valor por defecto:
 * es la abstracción que resuelve la dirección y su respaldo para navegador.
 * Todo lo demás tiene que pedírselo a ella.
 */
const ALLOWED = new Set(["lib" + sep + "config.ts"]);

const FORBIDDEN = /(?:https?:\/\/)?(?:127\.0\.0\.1|localhost):80\d\d/;

function* sourceFiles(dir: string): Generator<string> {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      if (entry === "node_modules" || entry === "__tests__" || entry === ".next") continue;
      yield* sourceFiles(full);
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry)) continue;
    if (/\.test\.tsx?$/.test(entry)) continue;
    yield full;
  }
}

describe("dirección del backend", () => {
  it("ningún módulo del frontend escribe el puerto a mano", () => {
    const offenders: string[] = [];

    for (const dir of SCANNED_DIRS) {
      for (const file of sourceFiles(join(ROOT, dir))) {
        const relativePath = relative(ROOT, file);
        if (ALLOWED.has(relativePath)) continue;
        const contents = readFileSync(file, "utf8");
        contents.split("\n").forEach((line, index) => {
          // Un comentario que MENCIONE el puerto no es una petición.
          const code = line.split("//")[0];
          if (FORBIDDEN.test(code)) {
            offenders.push(`${relativePath}:${index + 1}: ${line.trim()}`);
          }
        });
      }
    }

    expect(
      offenders,
      "Estos módulos fijan el puerto en vez de pedírselo a `getApiUrl()`:\n" +
        offenders.join("\n"),
    ).toEqual([]);
  });
});
