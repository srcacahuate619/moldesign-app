// =====================================================================
// Tests del modelo de CASO: creación, validación, versionado y nombres
// =====================================================================
//
// La regla que estos tests defienden es una sola: un manifiesto invalido NUNCA
// produce un caso parcial. Rellenar huecos con valores por defecto convertiria
// un archivo corrupto en un caso que PARECE sano, y ese es el modo de fallo
// que este producto no se puede permitir — el dossier acabaria afirmando cosas
// sobre un caso que nadie escribio.
//
// Cubre:
// - creacion con lo minimo (nombre, tipo, almacenamiento) y estado inicial
// - las preguntas cientificas NO bloquean la creacion
// - round-trip serializar → parsear
// - rechazo de manifiesto corrupto, campo a campo
// - rechazo de version no soportada (mayor y menor)
// - saneamiento de nombres inseguros: traversal, absolutos, reservados
// - conteo de contexto pendiente

import { describe, expect, it } from "vitest";

import {
  createCaseRecord,
  generateCaseId,
  isSafeFolderName,
  migrateManifest,
  parseCaseManifest,
  parseCaseManifestText,
  sanitizeFolderName,
  serializeCaseManifest,
  touchCase,
} from "../schema";
import {
  CASE_SCHEMA_VERSION,
  CaseError,
  normalizeCaseView,
  summarizePendingContext,
  type CaseRecord,
} from "../types";

const NOW = "2026-08-23T12:00:00.000Z";

function validRecord(): CaseRecord {
  return createCaseRecord({
    ownerUserId: "test-owner",
    name: "Serie A",
    studyKind: "compare-series",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    now: NOW,
    id: "11111111-2222-4333-8444-555555555555",
  });
}

describe("createCaseRecord — la creación pide lo mínimo", () => {
  it("crea un caso en `draft`, en Evaluación y sin responder nada", () => {
    const record = validRecord();
    expect(record.schemaVersion).toBe(CASE_SCHEMA_VERSION);
    expect(record.status).toBe("draft");
    // Evaluation-first: un caso nuevo NO aterriza en un cuestionario.
    expect(record.activeView).toBe("evaluation");
    expect(record.archived).toBe(false);
    expect(record.createdAt).toBe(NOW);
    expect(record.updatedAt).toBe(NOW);
    expect(record.lastOpenedAt).toBe(NOW);
    // Solo el tipo de estudio; ninguna pregunta cientifica respondida.
    expect(record.context).toEqual({ studyKind: "compare-series" });
  });

  it("no exige ninguna pregunta científica para poder crear", () => {
    const record = validRecord();
    const pending = summarizePendingContext(record.context);
    expect(pending.total).toBeGreaterThan(0);
    // Y aun asi el caso existe y es valido.
    expect(() => parseCaseManifest(JSON.parse(serializeCaseManifest(record)))).not.toThrow();
  });

  it("rechaza un nombre vacío", () => {
    expect(() =>
      createCaseRecord({
        ownerUserId: "test-owner",
        name: "   ",
        studyKind: "review-pose",
        storage: { mode: "browser", label: "Guardado en este navegador" },
      }),
    ).toThrowError(CaseError);
  });

  it("rechaza en modo carpeta un nombre que no puede ser carpeta", () => {
    expect(() =>
      createCaseRecord({
        ownerUserId: "test-owner",
        name: "..",
        studyKind: "review-pose",
        storage: { mode: "folder", path: "/tmp/x" },
      }),
    ).toThrowError(/no puede|reservado|utilizables/i);
  });
});

describe("serialización y round-trip", () => {
  it("parsea de vuelta lo que serializa, sin pérdida", () => {
    const record = touchCase(validRecord(), {
      context: { studyKind: "compare-series", question: "¿Discrimina la serie?" },
      status: "qualifying",
    }, NOW);
    const parsed = parseCaseManifestText(serializeCaseManifest(record));
    expect(parsed).toEqual(record);
  });

  it("termina en salto de línea, para diffs limpios en disco", () => {
    expect(serializeCaseManifest(validRecord()).endsWith("\n")).toBe(true);
  });

  it("`touchCase` no permite mover id ni createdAt", () => {
    const record = validRecord();
    const later = touchCase(record, { status: "ready" }, "2026-08-24T00:00:00.000Z");
    expect(later.id).toBe(record.id);
    expect(later.createdAt).toBe(record.createdAt);
    expect(later.updatedAt).toBe("2026-08-24T00:00:00.000Z");
  });
});

describe("manifiesto corrupto — nunca un caso parcial", () => {
  const base = () => JSON.parse(serializeCaseManifest(validRecord())) as Record<string, unknown>;

  it("rechaza lo que no es un objeto", () => {
    for (const bad of [null, 42, "texto", [1, 2]]) {
      expect(() => parseCaseManifest(bad)).toThrowError(CaseError);
    }
  });

  it("rechaza JSON malformado con INVALID_MANIFEST", () => {
    try {
      parseCaseManifestText("{ esto no es json");
      expect.unreachable("debería haber lanzado");
    } catch (error) {
      expect(error).toBeInstanceOf(CaseError);
      expect((error as CaseError).code).toBe("INVALID_MANIFEST");
    }
  });

  it.each(["id", "name", "createdAt", "updatedAt", "lastOpenedAt"])(
    "rechaza si falta `%s`",
    (field) => {
      const manifest = base();
      delete manifest[field];
      expect(() => parseCaseManifest(manifest)).toThrowError(CaseError);
    },
  );

  it("rechaza una fecha que no es una fecha", () => {
    const manifest = base();
    manifest.updatedAt = "ayer por la tarde";
    expect(() => parseCaseManifest(manifest)).toThrowError(/fecha/i);
  });

  it("rechaza un `status` desconocido en vez de caer en uno por defecto", () => {
    const manifest = base();
    manifest.status = "casi-listo";
    expect(() => parseCaseManifest(manifest)).toThrowError(CaseError);
  });

  it("rechaza `archived` ausente o de tipo incorrecto en vez de normalizarlo", () => {
    for (const bad of [undefined, null, "false", 0, 1]) {
      const manifest = base();
      if (bad === undefined) delete manifest.archived;
      else manifest.archived = bad;
      expect(() => parseCaseManifest(manifest)).toThrowError(CaseError);
    }
  });

  it("rechaza un `storage` sin ruta en modo carpeta", () => {
    const manifest = base();
    manifest.storage = { mode: "folder" };
    expect(() => parseCaseManifest(manifest)).toThrowError(CaseError);
  });

  it("NO convierte un contexto corrupto en «No definido»", () => {
    // Silenciarlo confundiría «nunca se respondió» con «la respuesta se
    // perdió», y el dossier acabaría declarando lo primero.
    for (const corrupt of [{ question: 42 }, { notes: ["a"] }, { studyKind: "inventado" }, "texto"]) {
      const manifest = base();
      manifest.context = corrupt;
      expect(() => parseCaseManifest(manifest)).toThrowError(CaseError);
    }
  });

  it("un contexto vacío o ausente sí es válido: la ausencia es un estado legítimo", () => {
    const manifest = base();
    manifest.context = {};
    expect(parseCaseManifest(manifest).context).toEqual({});
    delete manifest.context;
    expect(parseCaseManifest(manifest).context).toEqual({});
  });

  it("una cadena en blanco se normaliza a ausente, que es lo que produce borrar el campo", () => {
    const manifest = base();
    manifest.context = { question: "   " };
    expect(parseCaseManifest(manifest).context).toEqual({});
  });
});

describe("versionado", () => {
  it("rechaza una versión más nueva y lo dice sin ambigüedad", () => {
    const manifest = JSON.parse(serializeCaseManifest(validRecord()));
    manifest.schemaVersion = CASE_SCHEMA_VERSION + 1;
    try {
      parseCaseManifest(manifest);
      expect.unreachable("debería haber lanzado");
    } catch (error) {
      expect((error as CaseError).code).toBe("UNSUPPORTED_VERSION");
      expect((error as CaseError).message).toMatch(/más nueva/i);
    }
  });

  it("rechaza una `schemaVersion` que no es un entero >= 1", () => {
    for (const bad of [0, -1, 1.5, "1", null, undefined]) {
      const manifest = JSON.parse(serializeCaseManifest(validRecord()));
      manifest.schemaVersion = bad;
      expect(() => parseCaseManifest(manifest)).toThrowError(CaseError);
    }
  });

  it("`migrateManifest` es la identidad en la versión actual", () => {
    const manifest = JSON.parse(serializeCaseManifest(validRecord()));
    expect(migrateManifest(manifest, CASE_SCHEMA_VERSION)).toBe(manifest);
  });

  it("`migrateManifest` se niega si no hay ruta desde esa versión", () => {
    expect(() => migrateManifest({}, 99)).toThrowError(/migración/i);
  });
});

describe("sanitizeFolderName — frontera de seguridad", () => {
  it("acepta nombres corrientes y normaliza el ruido", () => {
    expect(sanitizeFolderName("Serie A")).toBe("Serie A");
    expect(sanitizeFolderName("  caso   01  ")).toBe("caso 01");
    expect(sanitizeFolderName("caso/01")).toBe("caso-01");
  });

  it.each([
    ["..", "traversal"],
    [".", "punto"],
    ["../../etc", "traversal profundo"],
    ["   ", "solo espacios"],
    ["...", "solo puntos"],
  ])("neutraliza o rechaza %s (%s)", (input) => {
    let result: string | null = null;
    try {
      result = sanitizeFolderName(input);
    } catch (error) {
      expect(error).toBeInstanceOf(CaseError);
      return;
    }
    // Si no lanzó, lo importante es que YA NO sea capaz de escapar.
    expect(result).not.toContain("/");
    expect(result).not.toContain("\\");
    expect(result).not.toBe("..");
    expect(result).not.toBe(".");
  });

  it("no deja rutas absolutas ni letras de unidad utilizables", () => {
    const windows = sanitizeFolderName("C:\\Windows\\System32");
    expect(windows).not.toContain(":");
    expect(windows).not.toContain("\\");
    const unix = sanitizeFolderName("/etc/passwd");
    expect(unix).not.toContain("/");
  });

  it("rechaza los nombres reservados de Windows", () => {
    for (const reserved of ["CON", "con", "PRN", "nul", "com1", "LPT9"]) {
      expect(() => sanitizeFolderName(reserved)).toThrowError(/reservado/i);
      expect(isSafeFolderName(reserved)).toBe(false);
    }
  });

  it("quita el punto o espacio final que Windows recortaría en silencio", () => {
    expect(sanitizeFolderName("caso.")).toBe("caso");
    expect(sanitizeFolderName("caso ")).toBe("caso");
  });

  it("recorta a un largo manejable", () => {
    expect(sanitizeFolderName("x".repeat(300)).length).toBeLessThanOrEqual(64);
  });
});

describe("generateCaseId", () => {
  it("produce identificadores distintos con forma de UUID", () => {
    const a = generateCaseId();
    const b = generateCaseId();
    expect(a).not.toBe(b);
    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i);
  });
});

describe("summarizePendingContext", () => {
  it("cuenta advertencias y opcionales por separado", () => {
    const empty = summarizePendingContext({});
    expect(empty.warnings).toBe(5);
    expect(empty.info).toBe(2);
    expect(empty.total).toBe(7);
  });

  it("una respuesta en blanco sigue contando como pendiente", () => {
    const blank = summarizePendingContext({ question: "   " });
    expect(blank.warnings).toBe(5);
  });

  it("llega a cero cuando todo está respondido", () => {
    const full = summarizePendingContext({
      question: "q", decision: "d", systemRationale: "s",
      controls: "c", assumptions: "a", uncertainties: "u", notes: "n",
    });
    expect(full.total).toBe(0);
  });
});

// =====================================================================
// Migración v1 → v2: de siete secciones a dos modos
// =====================================================================
//
// El esquema v1 guardaba `activeSection` con siete valores, cinco de ellos
// destinos que nunca hicieron nada. v2 guarda `activeView` con los dos modos
// reales. Lo que NO puede pasar es que un caso guardado con el nombre viejo
// desaparezca de la lista o abra en una pantalla vacía.

function v1Manifest(activeSection: string): Record<string, unknown> {
  return {
    schemaVersion: 1,
    id: "11111111-2222-4333-8444-555555555555",
    name: "Caso heredado",
    createdAt: "2026-08-01T10:00:00.000Z",
    updatedAt: "2026-08-01T10:00:00.000Z",
    lastOpenedAt: "2026-08-01T10:00:00.000Z",
    status: "draft",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    activeSection,
    context: { studyKind: "explore-hypothesis" },
    archived: false,
  };
}

describe("migración del manifiesto v1 → v2", () => {
  it.each(["context", "system", "site", "ligands", "evaluate", "evidence", "report"])(
    "normaliza `activeSection: %s` a un modo que existe",
    (section) => {
      const record = parseCaseManifest(v1Manifest(section));
      expect(record.schemaVersion).toBe(CASE_SCHEMA_VERSION);
      expect(record.activeView).toBe("evaluation");
    },
  );

  it("el `report` de v1 tampoco restaura un informe: no acredita evidencia", () => {
    // En v1, «Informe» era una pestaña inerte que no se podía seleccionar. Un
    // manifiesto con ese valor no prueba que exista un resultado recuperable,
    // así que abrir ahí sería prometer algo sin haberlo comprobado.
    expect(parseCaseManifest(v1Manifest("report")).activeView).toBe("evaluation");
  });

  it("una `activeSection` corrupta no impide abrir el caso", () => {
    // El caso NO desaparece por un valor que este build no reconoce: se
    // normaliza. Perder el caso sería un desenlace mucho peor que perder la
    // preferencia de qué pestaña estaba abierta.
    const record = parseCaseManifest(v1Manifest("una-seccion-inventada"));
    expect(record.activeView).toBe("evaluation");
    expect(record.name).toBe("Caso heredado");
  });

  it("lo demás del caso v1 se conserva intacto", () => {
    const record = parseCaseManifest({
      ...v1Manifest("context"),
      context: { studyKind: "compare-series", question: "¿Discrimina la serie?" },
      activeRun: {
        taskId: "task-de-antes",
        executionState: "completed",
        startedAt: "2026-08-01T10:05:00.000Z",
      },
    });
    expect(record.context.question).toBe("¿Discrimina la serie?");
    expect(record.context.studyKind).toBe("compare-series");
    // El vínculo con la evidencia sobrevive a la migración: es lo único que
    // permite recuperar el resultado y revelar el informe.
    expect(record.activeRun?.taskId).toBe("task-de-antes");
  });

  it("al reescribirlo se guarda en la versión actual y sin la clave vieja", () => {
    const record = parseCaseManifest(v1Manifest("evaluate"));
    const serialized = JSON.parse(serializeCaseManifest(record)) as Record<string, unknown>;
    expect(serialized.schemaVersion).toBe(CASE_SCHEMA_VERSION);
    expect(serialized.activeView).toBe("evaluation");
    // Dos nombres para lo mismo obligarían a decidir cuál gana en cada lectura.
    expect(serialized.activeSection).toBeUndefined();
  });

  it("un v2 con `activeView: report` se lee tal cual", () => {
    const record = parseCaseManifest({
      ...v1Manifest("context"),
      schemaVersion: 2,
      activeSection: undefined,
      activeView: "report",
    });
    expect(record.activeView).toBe("report");
  });

  it("una versión más nueva se rechaza en vez de leerse a medias", () => {
    expect(() => parseCaseManifest({ ...v1Manifest("context"), schemaVersion: 99 })).toThrowError(
      /versión más nueva|no está soportado/i,
    );
  });

  it("`normalizeCaseView` es total: cualquier basura da un modo válido", () => {
    for (const raw of [undefined, null, 42, "", "context", {}, []]) {
      expect(normalizeCaseView(raw)).toBe("evaluation");
    }
    expect(normalizeCaseView("report")).toBe("report");
    expect(normalizeCaseView("evaluation")).toBe("evaluation");
  });
});

// =====================================================================
// Migración v2 → v3: aparecen los inputs del caso
// =====================================================================
//
// La garantía que no se puede perder: ningún caso guardado por un build
// anterior queda inaccesible, y ninguno gana inputs que nadie declaró.

function v2Manifest(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schemaVersion: 2,
    id: "22222222-3333-4444-8555-666666666666",
    name: "Caso v2",
    createdAt: "2026-08-10T10:00:00.000Z",
    updatedAt: "2026-08-10T10:00:00.000Z",
    lastOpenedAt: "2026-08-10T10:00:00.000Z",
    status: "review",
    storage: { mode: "browser", label: "Guardado en este navegador" },
    activeView: "evaluation",
    context: { studyKind: "explore-hypothesis" },
    archived: false,
    ...extra,
  };
}

describe("migración del manifiesto v2 → v3", () => {
  it("un caso v2 abre y queda en la versión actual", () => {
    const record = parseCaseManifest(v2Manifest());
    expect(record.schemaVersion).toBe(CASE_SCHEMA_VERSION);
    expect(record.activeView).toBe("evaluation");
    expect(record.name).toBe("Caso v2");
  });

  it("NO se inventan inputs que el manifiesto nunca guardó", () => {
    // Rellenar receptor o ligando con un valor por defecto afirmaría una
    // hipótesis que nadie declaró. Quedan ausentes y la interfaz los pide.
    const record = parseCaseManifest(v2Manifest());
    expect(record.inputs).toBeUndefined();
    expect(record.preflight).toBeUndefined();
    expect(record.decisions).toBeUndefined();
  });

  it("una corrida v2 conserva su taskId y NO gana un fingerprint", () => {
    // Sin fingerprint, `runMatchesInputs` la declara «desconocida» en vez de
    // atribuirla a la hipótesis actual. Inventarle uno sería justo lo
    // contrario.
    const record = parseCaseManifest(
      v2Manifest({
        activeRun: {
          taskId: "task-de-v2",
          executionState: "completed",
          startedAt: "2026-08-10T10:05:00.000Z",
        },
      }),
    );
    expect(record.activeRun?.taskId).toBe("task-de-v2");
    expect(record.activeRun?.inputFingerprint).toBeUndefined();
  });

  it("un caso v1 llega hasta v3 en un solo paso de lectura", () => {
    const record = parseCaseManifest(v1Manifest("ligands"));
    expect(record.schemaVersion).toBe(CASE_SCHEMA_VERSION);
    expect(record.activeView).toBe("evaluation");
    expect(record.inputs).toBeUndefined();
  });

  it("los inputs v3 sobreviven al ciclo de escritura y lectura", () => {
    const original = parseCaseManifest(
      v2Manifest({
        schemaVersion: 3,
        inputs: {
          receptor: { pdbId: "7E2Y", chain: "A", origin: "curado", targetId: "t-1" },
          ligand: { inputSmiles: "OCC", canonicalSmiles: "CCO" },
          grid: { center: [1, 2, 3], size: [20, 20, 20] },
          customHotspots: ["TYR123"],
          dockingEngine: "vina",
        },
        preflight: {
          fingerprint: "sha256:abc",
          inputDocument: "{}",
          generatedAt: "2026-08-10T10:10:00.000Z",
          schemaVersion: 1,
          executionRoute: "docking_vina",
          blockers: [],
          warnings: ["METALES_ELIMINADOS"],
          notEvaluated: [],
          receptorLabel: "7E2Y · cadena A",
          ligandLabel: "CCO",
          gridLabel: "(1.00, 2.00, 3.00)",
        },
        decisions: [
          {
            controlCode: "METALES_ELIMINADOS",
            fingerprint: "sha256:abc",
            decision: "reconocida",
            at: "2026-08-10T10:11:00.000Z",
          },
        ],
      }),
    );

    const roundTripped = parseCaseManifestText(serializeCaseManifest(original));
    expect(roundTripped.inputs).toEqual(original.inputs);
    expect(roundTripped.preflight).toEqual(original.preflight);
    expect(roundTripped.decisions).toEqual(original.decisions);
  });

  it("unos inputs corruptos NO se leen como «sin receptor»", () => {
    // Leerlos como ausentes dejaría al usuario creyendo que nunca eligió, y el
    // siguiente guardado borraría del disco lo que quedaba de su elección.
    expect(() =>
      parseCaseManifest(v2Manifest({ schemaVersion: 3, inputs: { receptor: { chain: "A" } } })),
    ).toThrowError(CaseError);
    expect(() =>
      parseCaseManifest(v2Manifest({ schemaVersion: 3, inputs: "7E2Y" })),
    ).toThrowError(CaseError);
    expect(() =>
      parseCaseManifest(
        v2Manifest({ schemaVersion: 3, inputs: { grid: { center: [1, 2], size: [20, 20, 20] } } }),
      ),
    ).toThrowError(CaseError);
  });

  it("un preflight sin fingerprint es corrupción, no ausencia", () => {
    expect(() =>
      parseCaseManifest(
        v2Manifest({
          schemaVersion: 3,
          preflight: { generatedAt: "2026-08-10T10:10:00.000Z", inputDocument: "{}" },
        }),
      ),
    ).toThrowError(CaseError);
  });

  it("un fingerprint vacío en la corrida se rechaza", () => {
    expect(() =>
      parseCaseManifest(
        v2Manifest({
          schemaVersion: 3,
          activeRun: {
            taskId: "t",
            executionState: "completed",
            startedAt: "2026-08-10T10:05:00.000Z",
            inputFingerprint: "",
          },
        }),
      ),
    ).toThrowError(CaseError);
  });
});
