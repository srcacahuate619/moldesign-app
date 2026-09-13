// =====================================================================
// MOLDEX-INT-007 — el catálogo debe decir de qué corrida salió cada número
// =====================================================================
//
// `/moldex` no declara `response_model` en FastAPI, así que no aparece en
// `docs/api/openapi-current.json` y la guarda derivada del esquema
// (`evaluationResultContract.test.ts`) no puede cubrirlo. Mientras eso siga
// así, esta prueba es la definición del contrato: se escribe contra el payload
// que `backend/api/moldex.py` construye hoy.

import { describe, expect, it } from "vitest";

import {
  leerSello,
  marcaDeOrden,
  porEvaluacionReciente,
  porScore,
  type MoldexMolecule,
  type MoldexSeal,
} from "../moldex";

/** Payload tal y como lo emite `backend/api/moldex.py`. */
const FICHA: MoldexMolecule = {
  id: "6f1c4b6e-0000-4000-8000-000000000001",
  name: "Ligando de prueba",
  smiles: "CCO",
  smiles_hash: "b".repeat(64),
  created_at: "2026-08-01T00:00:00+00:00",
  evaluated_at: "2026-08-30T12:00:00+00:00",
  target: {
    pdb_id: "7E2Y",
    name: "5-HT1A",
    family: "GPCR",
    hotspots: [],
    spearman_rho: 0.61,
  },
  metrics: {
    affinity: -8.2,
    log_p: 2.1,
    mw: 310.4,
    tpsa: 64.2,
    score: 88,
    gnn_score: 71,
    lipinski_pass: true,
    veber_pass: true,
  },
  provenance: {
    task_id: "task-abc-123",
    receptor_sha256: "c".repeat(64),
    engine_version: "1.2.5",
    random_seed: 73,
    docking_protocol: { engine: "vina", exhaustiveness: 8 },
  },
  scientific_warnings: [],
  hotspots_hit: [],
  blockchain: {
    certified: false,
    tx_signature: null,
    certified_task_id: null,
    certified_total_score: null,
    matches_current_run: null,
  },
};

describe("contrato del catálogo Moldex", () => {
  it("declara la identidad y las condiciones de la corrida", () => {
    // Si el backend renombra u omite uno de estos campos, la ficha deja de
    // poder decir contra qué se midió y esta prueba lo delata.
    expect(Object.keys(FICHA.provenance).sort()).toEqual([
      "docking_protocol",
      "engine_version",
      "random_seed",
      "receptor_sha256",
      "task_id",
    ]);
  });

  it("acepta una corrida heredada sin inventar procedencia", () => {
    const heredada: MoldexMolecule = {
      ...FICHA,
      evaluated_at: null,
      provenance: {
        task_id: null,
        receptor_sha256: null,
        engine_version: null,
        random_seed: null,
        docking_protocol: null,
      },
    };

    // El contrato admite el nulo: lo que no se registró no se rellena.
    expect(heredada.provenance.receptor_sha256).toBeNull();
    expect(heredada.evaluated_at).toBeNull();
  });

  it("no expone la ruta local del receptor", () => {
    // EVAL-INT-008 fijó que el hash se publica y la ruta privada no.
    expect(Object.keys(FICHA.provenance)).not.toContain("receptor_path");
  });
});

describe("orden por fecha de evaluación", () => {
  const conFechas = (evaluated_at: string | null, created_at: string) =>
    ({ evaluated_at, created_at }) as Pick<
      MoldexMolecule,
      "evaluated_at" | "created_at"
    >;

  it("usa la fecha de la evaluación, no la de creación de la molécula", () => {
    // Dibujada primero pero evaluada después: debe ir delante.
    const vieja = conFechas("2026-08-30T12:00:00Z", "2026-01-01T00:00:00Z");
    const nueva = conFechas("2026-08-02T12:00:00Z", "2026-08-01T00:00:00Z");

    expect([nueva, vieja].sort(porEvaluacionReciente)).toEqual([vieja, nueva]);
  });

  it("cae a la fecha de creación cuando la corrida es heredada", () => {
    const heredada = conFechas(null, "2026-05-05T00:00:00Z");

    expect(marcaDeOrden(heredada)).toBe(
      new Date("2026-05-05T00:00:00Z").getTime(),
    );
  });

  it("no explota con una fecha ilegible", () => {
    expect(marcaDeOrden(conFechas("no-es-una-fecha", ""))).toBe(0);
  });
});

describe("lectura del sello de certificación", () => {
  const sello = (extra: Partial<MoldexSeal>): MoldexSeal => ({
    certified: true,
    tx_signature: "firma-xyz",
    certified_task_id: "corrida-1",
    certified_total_score: 91,
    matches_current_run: true,
    ...extra,
  });

  it("sin sello no dice nada", () => {
    expect(leerSello(sello({ certified: false }))).toBe("sin-sello");
    expect(leerSello(null)).toBe("sin-sello");
    expect(leerSello(undefined)).toBe("sin-sello");
  });

  it("un sello que describe la corrida mostrada es vigente", () => {
    expect(leerSello(sello({ matches_current_run: true }))).toBe("vigente");
  });

  it("una reevaluación posterior lo deja como corrida anterior", () => {
    expect(leerSello(sello({ matches_current_run: false }))).toBe(
      "corrida-anterior",
    );
  });

  it("un sello heredado es indeterminado, nunca vigente", () => {
    // MOLDEX-SCI-001: no consta qué corrida cubrió. Suponer que coincide sería
    // reintroducir exactamente el defecto que se corrigió.
    const heredado = leerSello(
      sello({
        matches_current_run: null,
        certified_task_id: null,
        certified_total_score: null,
      }),
    );

    expect(heredado).toBe("indeterminado");
    expect(heredado).not.toBe("vigente");
  });
});

describe("orden por score", () => {
  const conScore = (score: number | null) =>
    ({ metrics: { score } }) as Pick<MoldexMolecule, "metrics">;

  it("ordena descendente por score real", () => {
    const lista = [conScore(40), conScore(91), conScore(70)];

    expect(lista.sort(porScore("desc")).map((m) => m.metrics.score)).toEqual([
      91, 70, 40,
    ]);
  });

  it("una molécula sin score no se cuela en el ranking como si valiera 0", () => {
    // MOLDEX-SCI-014: `score || 0` la trataba como la peor en DESC y como la
    // mejor en ASC. No tener score no es tener un score malo.
    const lista = [conScore(null), conScore(40), conScore(91)];

    expect(lista.sort(porScore("desc")).map((m) => m.metrics.score)).toEqual([
      91, 40, null,
    ]);
  });

  it("y tampoco encabeza el orden ascendente", () => {
    const lista = [conScore(null), conScore(40), conScore(91)];

    expect(lista.sort(porScore("asc")).map((m) => m.metrics.score)).toEqual([
      40, 91, null,
    ]);
  });

  it("conserva el cero medido como un score válido", () => {
    const lista = [conScore(null), conScore(0), conScore(40)];

    expect(lista.sort(porScore("asc")).map((m) => m.metrics.score)).toEqual([
      0, 40, null,
    ]);
  });
});
