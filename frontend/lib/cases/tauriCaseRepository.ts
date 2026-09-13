// =====================================================================
// Repositorio de casos en ESCRITORIO — detrás de la frontera de Rust
// =====================================================================
//
// ESTE ARCHIVO YA NO ENVÍA RUTAS. La versión anterior pasaba `casePath` a los
// comandos y guardaba las rutas en localStorage: cualquiera con acceso al
// webview —un XSS, o la consola del devtools— podía invocar
// `case_read_manifest({ casePath: "C:\\Users\\..." })` y leer lo que quisiera.
//
// Ahora el único punto por el que entra una ruta es el diálogo nativo de Rust,
// que devuelve un `token` de sesión. Todo lo demás va por `case_id`, y Rust
// resuelve la carpeta contra su registro de autorizaciones. El índice de
// ubicaciones vive en Rust y persiste en app data; aquí no se guarda ninguna
// ruta, porque una copia local sería una autoridad paralela que puede mentir.
//
// El manifiesto en disco sigue siendo la fuente de verdad: `case_read` lo lee,
// lo valida en Rust y lo vuelve a validar aquí contra el modelo de TypeScript.

import { parseCaseManifestText, sanitizeFolderName, serializeCaseManifest } from "./schema";
import type {
  CaseRepository,
  CaseRepositoryCapabilities,
  CreateCaseRequest,
  OpenFolderOutcome,
  PickedParentDirectory,
  RegistryHealth,
} from "./repository";
import { sortCaseEntries } from "./repository";
import { invoke, TauriBridgeError } from "../tauri";
import {
  CaseError,
  recoveryActionsFor,
  type CaseIndexEntry,
  type CaseRecord,
  type CaseStudyKind,
} from "./types";

const CAPABILITIES: CaseRepositoryCapabilities = {
  canOpenFolder: true,
  canRevealInFileManager: true,
  storageLabel: "Carpeta en este equipo",
};

/** Respuesta de Rust al abrir/crear un caso. */
interface OpenedCase {
  case_id: string;
  path: string;
  manifest: string;
  recovered_from_backup: boolean;
  conflicting_path: string | null;
}

interface PickedFolder {
  token: string;
  /** Sólo presentación. El token es la autoridad. */
  display_path: string;
  has_manifest: boolean;
}

interface AuthorizedCase {
  case_id: string;
  path: string;
  available: boolean;
  can_repair: boolean;
}

/**
 * Traduce el error de Rust a `CaseError`.
 *
 * Rust devuelve `Err(String)` con prefijo de código (`UNSAFE_NAME: …`). Sin el
 * prefijo, la UI tendría que adivinar por el texto del mensaje, que es como se
 * acaba mostrando "error desconocido" a un usuario que sí tenía una causa.
 */
function toCaseError(error: unknown): CaseError {
  if (error instanceof CaseError) return error;
  if (error instanceof TauriBridgeError) {
    return new CaseError("UNSUPPORTED_OPERATION", error.message);
  }
  const message = error instanceof Error ? error.message : String(error);
  const match = /^([A-Z_]+):\s*(.*)$/s.exec(message);
  if (match) {
    const [, code, rest] = match;
    const known = [
      "INVALID_MANIFEST", "UNSUPPORTED_VERSION", "UNSAFE_NAME", "NOT_FOUND",
      "ALREADY_EXISTS", "IO_ERROR", "UNSUPPORTED_OPERATION", "UNAUTHORIZED",
    ] as const;
    if ((known as readonly string[]).includes(code)) {
      return new CaseError(code as CaseError["code"], rest.trim());
    }
  }
  return new CaseError("IO_ERROR", message);
}

async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  try {
    return await invoke<T>(cmd, args);
  } catch (error) {
    throw toCaseError(error);
  }
}

function recordFrom(opened: OpenedCase): CaseRecord {
  const parsed = parseCaseManifestText(opened.manifest, `${opened.path}/case.json`);
  // La ruta REAL manda sobre la que diga el manifiesto: la carpeta pudo
  // moverse, y el manifiesto no se entera de eso.
  return { ...parsed, storage: { mode: "folder", path: opened.path } };
}

export interface TauriCaseRepositoryOptions {
  readonly ownerUserId: string;
  /** Autoriza reclamar un manifiesto legacy sin propietario. */
  readonly canClaimLegacyCase?: (record: CaseRecord) => Promise<boolean>;
}

/** Traduce la respuesta de abrir por token a un resultado de la UI. */
function outcomeFrom(picked: PickedFolder, opened: OpenedCase): OpenFolderOutcome {
  if (opened.conflicting_path) {
    return {
      kind: "conflict",
      token: picked.token,
      displayPath: picked.display_path,
      registeredPath: opened.conflicting_path,
      record: recordFrom(opened),
    };
  }
  return { kind: "opened", record: recordFrom(opened) };
}

/**
 * Serializa con el ÚNICO serializador del esquema.
 *
 * Antes este archivo tenía su propia copia del orden de claves. Dos
 * serializadores para el mismo formato divergen en cuanto uno cambia: al subir
 * a v2 esta copia habría seguido escribiendo `activeSection` mientras el
 * parseador ya exigía `activeView`, y cada guardado habría producido un
 * manifiesto que el propio build no sabe leer.
 */
function manifestFor(record: CaseRecord): string {
  return serializeCaseManifest(record);
}

export function createTauriCaseRepository(options: TauriCaseRepositoryOptions): CaseRepository {
  const { ownerUserId, canClaimLegacyCase } = options;

  const ensureOwned = async (
    record: CaseRecord,
    { explicitFolderSelection = false }: { explicitFolderSelection?: boolean } = {},
  ): Promise<CaseRecord> => {
    if (record.ownerUserId === ownerUserId) return record;
    if (record.ownerUserId) {
      throw new CaseError("UNAUTHORIZED", "Este caso pertenece a otra cuenta.");
    }
    const authorized = record.activeRun
      ? await canClaimLegacyCase?.(record)
      : explicitFolderSelection;
    if (!authorized) {
      throw new CaseError(
        "UNAUTHORIZED",
        "Este caso legacy todavía no está asignado a tu cuenta.",
      );
    }
    const claimed: CaseRecord = { ...record, ownerUserId };
    await call<void>("case_write", { caseId: claimed.id, contents: manifestFor(claimed), ownerUserId });
    return claimed;
  };

  const readById = async (caseId: string): Promise<CaseRecord> => {
    const opened = await call<OpenedCase>("case_read", { caseId, ownerUserId });
    return ensureOwned(recordFrom(opened));
  };

  const write = async (record: CaseRecord): Promise<CaseRecord> => {
    if (record.ownerUserId !== ownerUserId) {
      throw new CaseError("UNAUTHORIZED", "No se puede guardar un caso de otra cuenta.");
    }
    await call<void>("case_write", { caseId: record.id, contents: manifestFor(record), ownerUserId });
    return record;
  };

  return {
    id: "tauri",
    capabilities: CAPABILITIES,

    async listCases(): Promise<CaseIndexEntry[]> {
      const authorized = await call<AuthorizedCase[]>("case_list_authorized", { ownerUserId });
      const entries: CaseIndexEntry[] = [];
      for (const item of authorized) {
        try {
          const opened = await call<OpenedCase>("case_read", { caseId: item.case_id, ownerUserId });
          const record = await ensureOwned(recordFrom(opened));
          entries.push({
            id: record.id,
            ownerUserId,
            name: record.name,
            status: record.status,
            createdAt: record.createdAt,
            updatedAt: record.updatedAt,
            lastOpenedAt: record.lastOpenedAt,
            archived: record.archived,
            storageMode: "folder",
            path: item.path,
            // Se propaga hasta la fila: un caso salvado del backup se DICE.
            ...(opened.recovered_from_backup ? { recoveredFromBackup: true } : {}),
            ...(record.activeRun ? { activeRun: record.activeRun } : {}),
          });
        } catch (error) {
          const caseError = toCaseError(error);
          // Un caso de otra cuenta no existe para esta sesión. No se filtra
          // después de construir la fila porque incluso el nombre/ruta sería
          // una fuga de metadatos entre investigadores.
          if (caseError.code === "UNAUTHORIZED") continue;
          // NO se omite. Un caso que se movió o cuyo manifiesto está roto sigue
          // siendo un caso conocido, y su fila tiene que decir qué le pasa.
          entries.push({
            id: item.case_id,
            name: item.path.split(/[\\/]/).pop() || `Caso ${item.case_id.slice(0, 8)}`,
            status: "draft",
            createdAt: new Date(0).toISOString(),
            updatedAt: new Date(0).toISOString(),
            lastOpenedAt: new Date(0).toISOString(),
            archived: false,
            storageMode: "folder",
            path: item.path,
            unavailable: {
              code: caseError.code,
              message: caseError.message,
              detail: caseError.detail,
              // `repair` SÓLO si de verdad hay copia de la que restaurar.
              actions: item.can_repair
                ? ["repair", ...recoveryActionsFor(caseError.code)]
                : recoveryActionsFor(caseError.code),
            },
          });
        }
      }
      return sortCaseEntries(entries);
    },

    async createCase(request: CreateCaseRequest): Promise<CaseRecord> {
      if (!request.parentDirectory) {
        throw new CaseError("UNSUPPORTED_OPERATION", "Elige una carpeta donde crear el caso.");
      }
      // `parentDirectory` es aquí un TOKEN, no una ruta: lo devolvió
      // `case_pick_directory` y sólo Rust sabe a qué carpeta corresponde.
      const folderName = sanitizeFolderName(request.name);
      const opened = await call<OpenedCase>("case_create", {
        token: request.parentDirectory,
        folderName,
        name: request.name.trim(),
        studyKind: request.studyKind,
        ownerUserId,
      });
      return ensureOwned(recordFrom(opened));
    },

    async readCase(id: string): Promise<CaseRecord> {
      return readById(id);
    },

    async openCase(id: string): Promise<CaseRecord> {
      const record = await readById(id);
      return write({ ...record, lastOpenedAt: new Date().toISOString() });
    },

    async adoptCase(record: CaseRecord): Promise<CaseRecord> {
      // Traspaso del invitado. `write` sigue exigiendo que el manifiesto declare
      // a ESTE dueno, y Rust lo vuelve a comprobar antes de escribir: la carpeta
      // no cambia de sitio, cambia de propietario declarado.
      return write(record);
    },

    async updateCase(record: CaseRecord): Promise<CaseRecord> {
      return write(record);
    },

    async setArchived(id: string, archived: boolean): Promise<CaseRecord> {
      const record = await readById(id);
      return write({ ...record, archived, updatedAt: new Date().toISOString() });
    },

    async forgetCase(id: string): Promise<void> {
      // Retira del registro de Rust. NO borra la carpeta.
      await call<void>("case_forget", { caseId: id, ownerUserId });
    },

    async openExistingFolder(): Promise<OpenFolderOutcome> {
      const picked = await call<PickedFolder | null>("case_pick_directory");
      if (!picked) return { kind: "cancelled" };
      if (!picked.has_manifest) {
        // NO se importa en silencio: la decisión de inicializar es del usuario.
        // Viajan las DOS cosas por separado: el token autoriza, la ruta se
        // enseña.
        return { kind: "empty", token: picked.token, displayPath: picked.display_path };
      }
      const opened = await call<OpenedCase>("case_open_token", { token: picked.token, ownerUserId });
      const record = await ensureOwned(recordFrom(opened), { explicitFolderSelection: true });
      if (opened.conflicting_path) {
        return {
          kind: "conflict",
          token: picked.token,
          displayPath: picked.display_path,
          registeredPath: opened.conflicting_path,
          record,
        };
      }
      return { kind: "opened", record };
    },

    async pickParentDirectory(): Promise<PickedParentDirectory | null> {
      const picked = await call<PickedFolder | null>("case_pick_parent_directory");
      if (!picked) return null;
      return { token: picked.token, displayPath: picked.display_path };
    },

    async acceptRelocation(token: string, expectedCaseId: string): Promise<CaseRecord> {
      // Rust comprueba la identidad ANTES de tocar el registro. Aquí no se
      // decide nada: se dice qué caso se esperaba y él acepta o rechaza.
      const opened = await call<OpenedCase>("case_relocate", {
        token,
        expectedCaseId,
        ownerUserId,
      });
      return ensureOwned(recordFrom(opened), { explicitFolderSelection: true });
    },

    async registryHealth(): Promise<RegistryHealth> {
      return call<RegistryHealth>("case_registry_health");
    },

    async repairCase(id: string): Promise<CaseRecord> {
      const opened = await call<OpenedCase>("case_repair", { caseId: id, ownerUserId });
      return ensureOwned(recordFrom(opened));
    },

    async relocateCase(id: string): Promise<OpenFolderOutcome> {
      const picked = await call<PickedFolder | null>("case_pick_directory");
      if (!picked) return { kind: "cancelled" };
      if (!picked.has_manifest) {
        return { kind: "empty", token: picked.token, displayPath: picked.display_path };
      }
      // `case_relocate` verifica la identidad EN RUST y sólo entonces registra.
      // La versión anterior abría con `acceptRelocation: true` —o sea, movía el
      // mapping— y comprobaba el id DESPUÉS: si la carpeta era la equivocada,
      // el registro ya había cambiado.
      const opened = await call<OpenedCase>("case_relocate", {
        token: picked.token,
        expectedCaseId: id,
        ownerUserId,
      });
      return { kind: "opened", record: await ensureOwned(recordFrom(opened)) };
    },

    async initializeFolder(
      token: string,
      name: string,
      studyKind: CaseStudyKind,
    ): Promise<CaseRecord> {
      const opened = await call<OpenedCase>("case_initialize", {
        token,
        name: name.trim(),
        studyKind,
        ownerUserId,
      });
      return ensureOwned(recordFrom(opened));
    },

    async revealInFileManager(id: string): Promise<void> {
      await call<void>("case_reveal", { caseId: id, ownerUserId });
    },
  };
}
