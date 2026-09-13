// =====================================================================
// EVAL-INT — cobertura campo a campo del resultado de evaluación
// =====================================================================
//
// El plan de cierre (docs/61 §5, EVAL-INT) pide una prueba «que detecte campos
// backend omitidos o renombrados en TypeScript». Ésta es. Compara dos fuentes
// que hoy nadie obliga a coincidir:
//
//   backend  docs/api/openapi-current.json → EvaluationResultRead
//            (snapshot generado desde `api.main.app`, verificado en CI con
//            `scripts/generate_openapi_contract.py --check`)
//   frontend lib/types.ts → EvaluationResult
//
// Un campo que el backend renombra y el tipo no sigue no rompe la compilación:
// TypeScript no conoce el JSON que llega. Se convierte en `undefined` en una
// tarjeta, y eso —en un producto que afirma procedencia— es peor que un error.
//
// Las dos listas de excepción son deliberadamente incómodas de ampliar: cada
// entrada declara POR QUÉ un campo vive en un solo lado. Sólo deberían
// encogerse.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "..", "..", "..");

/**
 * Campos que el backend envía y el tipo NO declara, con su motivo.
 *
 * Todos son hallazgos abiertos del expediente, no decisiones cerradas: el
 * producto persiste procedencia que su propia interfaz todavía no puede leer.
 */
const SOLO_BACKEND: Record<string, string> = {
};

/**
 * Campos que el tipo declara y el backend NO envía nunca.
 *
 * Son `undefined` en tiempo de ejecución. Se conservan sólo mientras vivan sus
 * consumidores muertos (ProResults, EvaluationContext), y están marcados como
 * obsoletos en `lib/types.ts`.
 */
const SOLO_FRONTEND: Record<string, string> = {
};

function camposDelBackend(): Set<string> {
  const snapshot = JSON.parse(
    readFileSync(resolve(repoRoot, "docs/api/openapi-current.json"), "utf-8"),
  ) as {
    components: { schemas: Record<string, { properties?: Record<string, unknown> }> };
  };
  const esquema = snapshot.components.schemas.EvaluationResultRead;
  expect(esquema, "EvaluationResultRead debe existir en el snapshot OpenAPI").toBeDefined();
  return new Set(Object.keys(esquema.properties ?? {}));
}

function camposDelTipo(): Set<string> {
  const fuente = readFileSync(resolve(repoRoot, "frontend/lib/types.ts"), "utf-8");
  const inicio = fuente.indexOf("export type EvaluationResult = {");
  expect(inicio, "EvaluationResult debe seguir declarado en lib/types.ts").toBeGreaterThan(-1);
  const fin = fuente.indexOf("\n};", inicio);
  const bloque = fuente
    .slice(inicio, fin)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/\/\/.*/g, "");
  const campos = new Set<string>();
  for (const linea of bloque.split("\n")) {
    const coincidencia = /^ {2}([A-Za-z_][A-Za-z0-9_]*)\??:/.exec(linea);
    if (coincidencia) campos.add(coincidencia[1]);
  }
  return campos;
}

describe("contrato EvaluationResult backend ↔ frontend", () => {
  it("no hay campos científicos del backend fuera del tipo sin declararlo", () => {
    const backend = camposDelBackend();
    const frontend = camposDelTipo();

    const ausentes = [...backend].filter(
      (campo) => !frontend.has(campo) && !(campo in SOLO_BACKEND),
    );

    expect(
      ausentes,
      "Campos que el backend envía y el cliente ya no sabe leer. Añádelos a " +
        "lib/types.ts, o documenta la omisión en SOLO_BACKEND con su motivo.",
    ).toEqual([]);
  });

  it("el tipo no promete campos que el backend nunca envía", () => {
    const backend = camposDelBackend();
    const frontend = camposDelTipo();

    const inventados = [...frontend].filter(
      (campo) => !backend.has(campo) && !(campo in SOLO_FRONTEND),
    );

    expect(
      inventados,
      "Campos declarados en el tipo que llegan siempre como `undefined`.",
    ).toEqual([]);
  });

  it("las excepciones documentadas siguen siendo reales", () => {
    const backend = camposDelBackend();
    const frontend = camposDelTipo();

    // Una excepción que deja de aplicar es deuda resuelta: hay que borrarla de
    // la lista para que no encubra un hueco nuevo con el mismo nombre.
    for (const campo of Object.keys(SOLO_BACKEND)) {
      expect(backend.has(campo), `${campo} ya no lo envía el backend`).toBe(true);
      expect(frontend.has(campo), `${campo} ya está en el tipo: retira la excepción`).toBe(
        false,
      );
    }
    for (const campo of Object.keys(SOLO_FRONTEND)) {
      expect(frontend.has(campo), `${campo} ya no está en el tipo`).toBe(true);
      expect(backend.has(campo), `${campo} ya lo envía el backend: retira la excepción`).toBe(
        false,
      );
    }
  });

  it("los campos que sostienen la procedencia de una corrida están tipados", () => {
    const frontend = camposDelTipo();

    // Lo que permite decir «esto se calculó así»: motor, semilla, advertencias,
    // evidencia física y selección de pose. Si alguno se cae del tipo, la
    // interfaz deja de poder condicionar la conclusión.
    for (const campo of [
      "vina_version",
      "vina_random_seed",
      "scientific_warnings",
      "structural_evidence",
      "pose_selection",
      "receptor_path",
      "receptor_sha256",
      "docking_protocol",
      "task_id",
      "evaluated_at",
    ]) {
      expect(frontend.has(campo), `falta ${campo} en EvaluationResult`).toBe(true);
    }
  });
});
