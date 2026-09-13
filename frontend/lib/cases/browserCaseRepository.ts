// =====================================================================
// Repositorio de casos en NAVEGADOR — localStorage, y lo dice
// =====================================================================
//
// La ruta /evaluation tiene que funcionar sin Tauri. Este repositorio existe
// para eso, y su regla es la honestidad: NO finge que hay una carpeta. La UI
// muestra "Guardado en este navegador" y `openExistingFolder` no existe, asi
// que el boton queda deshabilitado CON su razon en vez de fallar al pulsarlo.
//
// EL INDICE SE RECONSTRUYE ENUMERANDO LAS CLAVES, no leyendo una lista.
// La version anterior guardaba `moldesign_cases_index` y, si esa clave se
// corrompia, TODOS los casos desaparecian del listado aunque sus manifiestos
// siguieran intactos. Ahora el listado se deriva de las claves
// `moldesign_case:*`, que es donde estan los casos de verdad; el indice queda
// como cache de orden y nada mas.
//
// UN CASO ILEGIBLE NO SE OMITE. Se devuelve con `unavailable` y su razon, para
// que la interfaz pueda ofrecer reparar o retirar. Omitirlo hacia que un caso
// desapareciera sin explicacion.

import { parseCaseManifestText, serializeCaseManifest } from "./schema";
import type {
  CaseRepository,
  CaseRepositoryCapabilities,
  CreateCaseRequest,
} from "./repository";
import { sortCaseEntries } from "./repository";
import {
  CaseError,
  recoveryActionsFor,
  type CaseIndexEntry,
  type CaseRecord,
} from "./types";
import { createCaseRecord } from "./schema";

export const CASES_INDEX_KEY = "moldesign_cases_index";
export const CASE_KEY_PREFIX = "moldesign_case:";

const CAPABILITIES: CaseRepositoryCapabilities = {
  canOpenFolder: false,
  canRevealInFileManager: false,
  openFolderUnavailableReason:
    "Abrir una carpeta del disco requiere la aplicación de escritorio. En el navegador los casos se guardan localmente en este equipo.",
  storageLabel: "Guardado en este navegador",
};

function storage(): Storage {
  if (typeof window === "undefined" || !window.localStorage) {
    throw new CaseError("IO_ERROR", "No hay almacenamiento local disponible en este entorno.");
  }
  return window.localStorage;
}

function toIndexEntry(record: CaseRecord): CaseIndexEntry {
  return {
    id: record.id,
    ...(record.ownerUserId ? { ownerUserId: record.ownerUserId } : {}),
    name: record.name,
    status: record.status,
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
    lastOpenedAt: record.lastOpenedAt,
    archived: record.archived,
    storageMode: record.storage.mode,
    ...(record.activeRun ? { activeRun: record.activeRun } : {}),
    // Sin `path` a proposito: en navegador no hay ruta y no se inventa una.
  };
}

/** Entrada mínima para un caso que no se puede leer. Nunca se omite la fila. */
function unavailableEntry(id: string, error: CaseError): CaseIndexEntry {
  return {
    id,
    name: `Caso ${id.slice(0, 8)}`,
    status: "draft",
    createdAt: new Date(0).toISOString(),
    updatedAt: new Date(0).toISOString(),
    lastOpenedAt: new Date(0).toISOString(),
    archived: false,
    storageMode: "browser",
    unavailable: {
      code: error.code,
      message: error.message,
      detail: error.detail,
      actions: recoveryActionsFor(error.code),
    },
  };
}

function asCaseError(error: unknown): CaseError {
  if (error instanceof CaseError) return error;
  return new CaseError("IO_ERROR", error instanceof Error ? error.message : String(error));
}

/** Todos los ids con manifiesto en localStorage. La fuente de verdad. */
function enumerateCaseIds(ownerUserId: string): string[] {
  const store = storage();
  const prefix = `${CASE_KEY_PREFIX}${ownerUserId}:`;
  const ids: string[] = [];
  for (let i = 0; i < store.length; i += 1) {
    const key = store.key(i);
    if (key && key.startsWith(prefix)) {
      ids.push(key.slice(prefix.length));
    }
  }
  return ids;
}

function caseKey(ownerUserId: string, id: string): string {
  return `${CASE_KEY_PREFIX}${ownerUserId}:${id}`;
}

function readRecord(ownerUserId: string, id: string): CaseRecord {
  const raw = storage().getItem(caseKey(ownerUserId, id));
  if (raw === null) {
    throw new CaseError("NOT_FOUND", `No existe un caso con id ${id} en este navegador.`);
  }
  const record = parseCaseManifestText(raw, `localStorage:${caseKey(ownerUserId, id)}`);
  if (record.ownerUserId !== ownerUserId) {
    throw new CaseError("UNAUTHORIZED", "Este caso pertenece a otra cuenta.");
  }
  return record;
}

function writeRecord(ownerUserId: string, record: CaseRecord): void {
  if (record.ownerUserId !== ownerUserId) {
    throw new CaseError("UNAUTHORIZED", "No se puede guardar un caso de otra cuenta.");
  }
  storage().setItem(caseKey(ownerUserId, record.id), serializeCaseManifest(record));
  // El indice se mantiene como cache de orden, pero el listado NO depende de el.
  try {
    const ids = enumerateCaseIds(ownerUserId);
    storage().setItem(`${CASES_INDEX_KEY}:${ownerUserId}`, JSON.stringify(ids));
  } catch {
    // Un indice que no se puede escribir no impide nada: se reconstruye.
  }
}

export function createBrowserCaseRepository(ownerUserId: string): CaseRepository {
  return {
    id: "browser",
    capabilities: CAPABILITIES,

    async listCases(): Promise<CaseIndexEntry[]> {
      const entries: CaseIndexEntry[] = [];
      for (const id of enumerateCaseIds(ownerUserId)) {
        try {
          entries.push(toIndexEntry(readRecord(ownerUserId, id)));
        } catch (error) {
          // NO se omite: se muestra como no disponible, con su razon y sus
          // acciones. Un caso que desaparece sin explicacion es peor que uno
          // que aparece roto.
          entries.push(unavailableEntry(id, asCaseError(error)));
        }
      }
      return sortCaseEntries(entries);
    },

    async createCase(request: CreateCaseRequest): Promise<CaseRecord> {
      const record = createCaseRecord({
        name: request.name,
        studyKind: request.studyKind,
        storage: { mode: "browser", label: "Guardado en este navegador" },
        ownerUserId,
      });
      writeRecord(ownerUserId, record);
      return record;
    },

    async readCase(id: string): Promise<CaseRecord> {
      return readRecord(ownerUserId, id);
    },

    async openCase(id: string): Promise<CaseRecord> {
      const record = readRecord(ownerUserId, id);
      // Abrir NO es editar: se toca `lastOpenedAt` y se deja `updatedAt` como
      // estaba. Si abrir moviera `updatedAt`, la columna "última actualización"
      // dejaria de significar "última vez que cambió algo".
      const opened: CaseRecord = { ...record, lastOpenedAt: new Date().toISOString() };
      writeRecord(ownerUserId, opened);
      return opened;
    },

    async adoptCase(record: CaseRecord): Promise<CaseRecord> {
      // Traspaso del invitado. `writeRecord` sigue exigiendo que el manifiesto
      // declare a ESTE dueno, asi que un caso ajeno no entra por descuido: el
      // llamador tiene que haber reescrito `ownerUserId` a proposito.
      writeRecord(ownerUserId, record);
      return record;
    },

    async updateCase(record: CaseRecord): Promise<CaseRecord> {
      // Comprueba que existe antes de escribir: `updateCase` no debe crear.
      readRecord(ownerUserId, record.id);
      writeRecord(ownerUserId, record);
      return record;
    },

    async setArchived(id: string, archived: boolean): Promise<CaseRecord> {
      const record = readRecord(ownerUserId, id);
      const updated: CaseRecord = { ...record, archived, updatedAt: new Date().toISOString() };
      writeRecord(ownerUserId, updated);
      return updated;
    },

    // Sin `pickParentDirectory`, `repairCase` ni `acceptRelocation` a proposito:
    // en navegador no hay carpetas ni copia de seguridad de la que restaurar.
    // Declarar los metodos y hacerlos fallar seria peor que no tenerlos: la UI
    // pregunta por su existencia para decidir que ofrece.

    async forgetCase(id: string): Promise<void> {
      // Retira del INDICE. El manifiesto se conserva: este sprint no borra.
      const ids = enumerateCaseIds(ownerUserId).filter((known) => known !== id);
      storage().setItem(`${CASES_INDEX_KEY}:${ownerUserId}`, JSON.stringify(ids));
      // En navegador el listado se deriva de las claves, asi que "retirar" sin
      // borrar la clave no tendria efecto visible. Se mueve a una clave
      // apartada para que deje de listarse SIN perder el contenido.
      const raw = storage().getItem(caseKey(ownerUserId, id));
      if (raw !== null) {
        storage().setItem(`moldesign_case_retirado:${ownerUserId}:${id}`, raw);
        storage().removeItem(caseKey(ownerUserId, id));
      }
    },
  };
}
