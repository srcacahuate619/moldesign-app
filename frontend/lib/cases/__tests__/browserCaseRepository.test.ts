// =====================================================================
// Tests del repositorio de casos en NAVEGADOR (localStorage)
// =====================================================================
//
// Este repositorio es el fallback web, y su virtud tiene que ser la honestidad:
// no finge carpetas, no expone `openExistingFolder`, y declara por que.
//
// Cubre:
// - crear un caso y recuperarlo tras "recargar" (repositorio nuevo, mismo store)
// - persistencia real: el manifiesto queda en localStorage y se vuelve a parsear
// - abrir marca `lastOpenedAt` y NO mueve `updatedAt`
// - archivar y desarchivar: reversible, sin borrar nada
// - un manifiesto corrupto NO se convierte en un caso parcial
// - el listado omite lo ilegible en vez de ofrecer un caso que no abre
// - capacidades honestas: no hay carpeta, y la razon esta escrita

import { beforeEach, describe, expect, it } from "vitest";

import {
  CASES_INDEX_KEY,
  CASE_KEY_PREFIX,
  createBrowserCaseRepository,
} from "../browserCaseRepository";
import { CASE_SCHEMA_VERSION, CaseError } from "../types";

function repo() {
  return createBrowserCaseRepository("test-owner");
}

const caseKey = (id: string) => `${CASE_KEY_PREFIX}test-owner:${id}`;

describe("browserCaseRepository — capacidades honestas", () => {
  it("declara que no puede abrir carpetas y explica por qué", () => {
    const r = repo();
    expect(r.id).toBe("browser");
    expect(r.capabilities.canOpenFolder).toBe(false);
    expect(r.capabilities.openFolderUnavailableReason).toMatch(/escritorio/i);
    expect(r.capabilities.storageLabel).toBe("Guardado en este navegador");
  });

  it("no expone la operación de carpeta en absoluto", () => {
    // Mejor ausente que presente-y-lanzando: la UI puede preguntar por ella.
    expect(repo().openExistingFolder).toBeUndefined();
    expect(repo().revealInFileManager).toBeUndefined();
  });
});

describe("crear y recuperar", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("crea un caso y lo devuelve en el listado", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Caso A", studyKind: "explore-hypothesis" });
    expect(created.name).toBe("Caso A");
    expect(created.storage.mode).toBe("browser");

    const list = await r.listCases();
    expect(list).toHaveLength(1);
    expect(list[0].id).toBe(created.id);
    // En navegador NO se inventa una ruta.
    expect(list[0].path).toBeUndefined();
  });

  it("sobrevive a una recarga: un repositorio nuevo ve los mismos casos", async () => {
    const created = await repo().createCase({ name: "Persistente", studyKind: "review-pose" });
    // Simula recargar la pagina: instancia nueva, mismo localStorage.
    const afterReload = repo();
    const list = await afterReload.listCases();
    expect(list.map((c) => c.id)).toEqual([created.id]);
    const read = await afterReload.readCase(created.id);
    expect(read.name).toBe("Persistente");
    expect(read.context.studyKind).toBe("review-pose");
  });

  it("escribe el manifiesto en localStorage bajo su propia clave", async () => {
    const created = await repo().createCase({ name: "Con clave", studyKind: "compare-series" });
    const raw = window.localStorage.getItem(caseKey(created.id));
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw as string).schemaVersion).toBe(CASE_SCHEMA_VERSION);
  });

  it("`readCase` de un id inexistente da NOT_FOUND", async () => {
    await expect(repo().readCase("no-existe")).rejects.toMatchObject({ code: "NOT_FOUND" });
  });
});

describe("abrir, actualizar y archivar", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("abrir marca `lastOpenedAt` sin mover `updatedAt`", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Abrible", studyKind: "explore-hypothesis" });
    await new Promise((resolve) => setTimeout(resolve, 5));
    const opened = await r.openCase(created.id);
    // Abrir NO es editar: si moviera `updatedAt`, la columna "última
    // actualización" dejaria de significar "última vez que cambió algo".
    expect(opened.updatedAt).toBe(created.updatedAt);
    expect(Date.parse(opened.lastOpenedAt)).toBeGreaterThanOrEqual(Date.parse(created.lastOpenedAt));
  });

  it("`updateCase` persiste el contexto editado", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Editable", studyKind: "explore-hypothesis" });
    await r.updateCase({ ...created, context: { ...created.context, question: "¿Funciona?" } });
    const reread = await repo().readCase(created.id);
    expect(reread.context.question).toBe("¿Funciona?");
  });

  it("`updateCase` no crea un caso que no existía", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Base", studyKind: "explore-hypothesis" });
    await expect(r.updateCase({ ...created, id: "otro-id" })).rejects.toMatchObject({
      code: "NOT_FOUND",
    });
  });

  it("archivar es reversible y no borra nada", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Archivable", studyKind: "prepare-evidence" });

    const archived = await r.setArchived(created.id, true);
    expect(archived.archived).toBe(true);
    // Sigue existiendo: archivar NO es borrar.
    expect(await r.readCase(created.id)).toMatchObject({ archived: true });
    let list = await r.listCases();
    expect(list).toHaveLength(1);

    const restored = await r.setArchived(created.id, false);
    expect(restored.archived).toBe(false);
    list = await r.listCases();
    expect(list[0].archived).toBe(false);
  });

  it("ordena los archivados al final", async () => {
    const r = repo();
    const a = await r.createCase({ name: "A", studyKind: "explore-hypothesis" });
    await r.createCase({ name: "B", studyKind: "explore-hypothesis" });
    await r.setArchived(a.id, true);
    const list = await r.listCases();
    expect(list.map((c) => c.name)).toEqual(["B", "A"]);
  });
});

describe("manifiesto corrupto — abstención, no caso parcial", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("`readCase` lanza INVALID_MANIFEST en vez de devolver algo a medias", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Se romperá", studyKind: "review-pose" });
    window.localStorage.setItem(caseKey(created.id), "{ no es json");

    await expect(repo().readCase(created.id)).rejects.toBeInstanceOf(CaseError);
    await expect(repo().readCase(created.id)).rejects.toMatchObject({
      code: "INVALID_MANIFEST",
    });
  });

  it("`readCase` lanza UNSUPPORTED_VERSION si el esquema es más nuevo", async () => {
    const r = repo();
    const created = await r.createCase({ name: "Del futuro", studyKind: "review-pose" });
    const raw = JSON.parse(window.localStorage.getItem(caseKey(created.id)) as string);
    raw.schemaVersion = 99;
    window.localStorage.setItem(caseKey(created.id), JSON.stringify(raw));

    await expect(repo().readCase(created.id)).rejects.toMatchObject({
      code: "UNSUPPORTED_VERSION",
    });
  });

  it("NO omite lo ilegible: lo lista como no disponible, con razón y acciones", async () => {
    const r = repo();
    const bueno = await r.createCase({ name: "Bueno", studyKind: "explore-hypothesis" });
    const malo = await r.createCase({ name: "Malo", studyKind: "explore-hypothesis" });
    window.localStorage.setItem(caseKey(malo.id), "{{{");

    const list = await repo().listCases();
    // Los DOS siguen en la lista. Omitir el roto lo hacía desaparecer sin
    // explicación y sin forma de recuperarlo.
    expect(list.map((c) => c.id).sort()).toEqual([bueno.id, malo.id].sort());
    const broken = list.find((c) => c.id === malo.id);
    expect(broken?.unavailable?.code).toBe("INVALID_MANIFEST");
    expect(broken?.unavailable?.actions).toContain("forget");
    // Y no se borra: este sprint no elimina nada.
    expect(window.localStorage.getItem(caseKey(malo.id))).toBe("{{{");
  });

  it("un índice corrupto NO pierde ningún caso: el listado se reconstruye de las claves", async () => {
    const r = repo();
    const creado = await r.createCase({ name: "Con índice roto", studyKind: "explore-hypothesis" });
    window.localStorage.setItem(`${CASES_INDEX_KEY}:test-owner`, "no-json");
    // Antes esto vaciaba el listado entero. Ahora los casos se enumeran desde
    // `moldesign_case:*`, que es donde están de verdad.
    const list = await repo().listCases();
    expect(list.map((c) => c.id)).toEqual([creado.id]);
  });

  it("`forgetCase` retira del listado sin destruir el contenido", async () => {
    const r = repo();
    const creado = await r.createCase({ name: "Se retira", studyKind: "explore-hypothesis" });
    await r.forgetCase(creado.id);
    await expect(r.listCases()).resolves.toEqual([]);
    // El manifiesto se conserva bajo otra clave: recuperable a mano.
    expect(window.localStorage.getItem(`moldesign_case_retirado:test-owner:${creado.id}`)).toContain("Se retira");
  });

  it("dos cuentas en el mismo navegador no ven ni pueden modificar los casos de la otra", async () => {
    const alice = createBrowserCaseRepository("alice");
    const bob = createBrowserCaseRepository("bob");
    const aliceCase = await alice.createCase({ name: "Privado de Alice", studyKind: "review-pose" });
    const bobCase = await bob.createCase({ name: "Privado de Bob", studyKind: "compare-series" });

    await expect(alice.listCases()).resolves.toMatchObject([{ id: aliceCase.id, ownerUserId: "alice" }]);
    await expect(bob.listCases()).resolves.toMatchObject([{ id: bobCase.id, ownerUserId: "bob" }]);
    await expect(bob.readCase(aliceCase.id)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(bob.updateCase(aliceCase)).rejects.toMatchObject({ code: "NOT_FOUND" });
  });
});
