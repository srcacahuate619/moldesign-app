// =====================================================================
// CaseRepository — la frontera entre la UI y el almacenamiento
// =====================================================================
//
// La UI NO debe saber si un caso vive en localStorage o en una carpeta del
// disco. Sin esta frontera, cada componente acabaria con un `if (isTauri)`
// dentro y el fallback web se degradaria por accidente en vez de por diseno.
//
// Dos implementaciones:
//   browserCaseRepository  localStorage, honesto sobre lo que es
//   tauriCaseRepository    carpeta real en disco via comandos Rust
//
// `capabilities` existe para que la UI pueda deshabilitar acciones CON su razon
// en vez de ofrecer un boton que falla al pulsarlo.

import type { CaseIndexEntry, CaseRecord, CaseStudyKind } from "./types";

export interface CaseRepositoryCapabilities {
  /** Puede abrir una carpeta existente del sistema de archivos. */
  readonly canOpenFolder: boolean;
  /** Puede revelar la carpeta del caso en el explorador. */
  readonly canRevealInFileManager: boolean;
  /** Razon por la que `canOpenFolder` es false. Obligatoria si lo es. */
  readonly openFolderUnavailableReason?: string;
  /** Etiqueta honesta del almacenamiento, para la cabecera del caso. */
  readonly storageLabel: string;
}

export interface CreateCaseRequest {
  readonly name: string;
  readonly studyKind: CaseStudyKind;
  /**
   * Carpeta CONTENEDORA elegida por el usuario. El repositorio crea dentro una
   * carpeta hija con el nombre saneado del caso. Solo en modo carpeta.
   */
  readonly parentDirectory?: string;
}

/**
 * Resultado de inspeccionar una carpeta que el usuario eligio abrir.
 *
 * `empty` NO importa nada en silencio: la UI debe presentar una decision
 * explicita —inicializar o cancelar—. Importar una carpeta ajena sin preguntar
 * es como se pierde el rastro de que era esa carpeta antes.
 */
export type OpenFolderOutcome =
  | { readonly kind: "opened"; readonly record: CaseRecord }
  /**
   * La carpeta no tiene `case.json`. `token` es la autoridad para inicializarla
   * y `displayPath` es SÓLO para enseñar: nunca se muestra el token como
   * ubicación, que es lo que acababa poniendo un UUID donde iba una ruta.
   */
  | { readonly kind: "empty"; readonly token: string; readonly displayPath: string }
  /**
   * El caso de esa carpeta YA está registrado en otra ubicación. No se ha
   * cambiado nada: hace falta una decisión explícita.
   */
  | {
      readonly kind: "conflict";
      readonly token: string;
      readonly displayPath: string;
      readonly registeredPath: string;
      readonly record: CaseRecord;
    }
  | { readonly kind: "cancelled" };

/**
 * Salud del índice de casos al arrancar.
 *
 * `first_run` y `corrupted` producen los dos una lista vacía, y por eso hay que
 * distinguirlos: quien acaba de instalar y quien ha perdido todos sus casos no
 * pueden ver lo mismo.
 */
export type RegistryHealth =
  | { readonly state: "first_run" }
  | { readonly state: "ok" }
  | { readonly state: "recovered_from_backup"; readonly detail: string }
  | { readonly state: "corrupted"; readonly detail: string };

/** Carpeta contenedora elegida para crear un caso nuevo. */
export interface PickedParentDirectory {
  /** Autoridad opaca. Se devuelve tal cual a `createCase`; no se interpreta. */
  readonly token: string;
  /** Sólo presentación. No sirve para acceder a nada. */
  readonly displayPath: string;
}

export interface CaseRepository {
  readonly id: "browser" | "tauri";
  readonly capabilities: CaseRepositoryCapabilities;

  /** Casos conocidos, nuevos primero por fecha de creacion. Cache de ubicaciones. */
  listCases(): Promise<CaseIndexEntry[]>;

  createCase(request: CreateCaseRequest): Promise<CaseRecord>;

  /** Lee el manifiesto. Fuente de verdad; el indice puede estar stale. */
  readCase(id: string): Promise<CaseRecord>;

  /** Lee y marca `lastOpenedAt`. Es `readCase` + registro de acceso. */
  openCase(id: string): Promise<CaseRecord>;

  updateCase(record: CaseRecord): Promise<CaseRecord>;

  /**
   * Escribe un caso que TODAVIA no pertenece a este repositorio.
   *
   * Existe solo para el traspaso del invitado, y separada de `updateCase` a
   * proposito: aquella comprueba que el caso ya existe para no crear por
   * accidente, y esto es exactamente crear —con el dueno cambiado— a peticion
   * explicita del investigador. Tenerla aparte impide que un `updateCase`
   * distraido acabe moviendo casos entre cuentas sin que nadie lo pidiera.
   *
   * El `record` debe venir ya con `ownerUserId` del destino: quien decide de
   * quien pasa a ser el caso es quien llama, no el almacenamiento.
   */
  adoptCase(record: CaseRecord): Promise<CaseRecord>;

  /** Reversible por diseno: archivar NO borra nada. */
  setArchived(id: string, archived: boolean): Promise<CaseRecord>;

  /**
   * Retira un caso del INDICE sin borrar su contenido.
   *
   * Es la salida para un caso irrecuperable: deja de estorbar en la lista y su
   * manifiesto sigue en disco por si alguien quiere rescatarlo a mano.
   */
  forgetCase(id: string): Promise<void>;

  /**
   * Abre una carpeta del sistema. Solo si `capabilities.canOpenFolder`.
   * Devuelve `cancelled` si el usuario cierra el selector.
   */
  openExistingFolder?(): Promise<OpenFolderOutcome>;

  /**
   * Elige la carpeta CONTENEDORA donde crear un caso nuevo.
   *
   * Separado de `openExistingFolder` a propósito: significan cosas distintas y
   * mezclarlos hacía que la interfaz enseñara un token como si fuera una ruta.
   */
  pickParentDirectory?(): Promise<PickedParentDirectory | null>;

  /**
   * Restaura el manifiesto desde su copia de seguridad.
   *
   * Sólo existe donde hay copia de la que restaurar. Un «Reparar» que no repara
   * nada es peor que no ofrecerlo.
   */
  repairCase?(id: string): Promise<CaseRecord>;

  /**
   * Confirma mover el registro de `expectedCaseId` a la carpeta del `token`.
   *
   * El id esperado es OBLIGATORIO: sin él, confirmar sería «acepta lo que haya
   * ahí», que es exactamente lo que no se puede hacer.
   */
  acceptRelocation?(token: string, expectedCaseId: string): Promise<CaseRecord>;

  /**
   * Vuelve a autorizar la carpeta de un caso que se movió o perdió permiso.
   *
   * La comprobación de identidad vive en RUST, no aquí: se le pasa el
   * `expectedCaseId` y sólo toca el registro si la carpeta contiene ese caso.
   * Comprobarlo en el frontend sería saltable llamando al comando a mano.
   */
  relocateCase?(id: string): Promise<OpenFolderOutcome>;

  /**
   * Cómo se cargó el índice de casos. La UI lo consume para poder avisar de un
   * registro recuperado o corrupto en vez de enseñar una lista vacía.
   */
  registryHealth?(): Promise<RegistryHealth>;

  /** Inicializa `case.json` en la carpeta autorizada por `token`. */
  initializeFolder?(token: string, name: string, studyKind: CaseStudyKind): Promise<CaseRecord>;

  revealInFileManager?(id: string): Promise<void>;
}

/**
 * Orden estable por fecha de creacion; los archivados al final.
 *
 * Abrir, editar o evaluar un caso no debe mover su fila. La actividad se
 * comunica dentro de la fila, no reordenando el mapa mental del usuario.
 */
export function sortCaseEntries(entries: readonly CaseIndexEntry[]): CaseIndexEntry[] {
  return [...entries].sort((a, b) => {
    if (a.archived !== b.archived) return a.archived ? 1 : -1;
    const byCreation = sortableTimestamp(b.createdAt) - sortableTimestamp(a.createdAt);
    if (byCreation !== 0) return byCreation;
    return a.id.localeCompare(b.id);
  });
}

function sortableTimestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

/** Filtro de busqueda: nombre y estado, sin distinguir mayusculas ni acentos. */
export function filterCaseEntries(
  entries: readonly CaseIndexEntry[],
  query: string,
): CaseIndexEntry[] {
  const needle = normalizeForSearch(query);
  if (needle.length === 0) return [...entries];
  return entries.filter((entry) => normalizeForSearch(entry.name).includes(needle));
}

function normalizeForSearch(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

// La deteccion de runtime vive en `lib/tauri.ts`, que es el puente unico.
export { isDesktopRuntime, isTauriAvailable } from "../tauri";
