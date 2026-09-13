/**
 * Traspaso del invitado a una cuenta registrada — lado cliente.
 *
 * El backend ya sabe mover el trabajo: `POST /auth/traspaso` es selectivo,
 * transaccional, idempotente y en un solo sentido. Lo que faltaba es esto:
 *
 * 1. **Recordar de quién se viene.** `moldesign_auth` se sobrescribe al
 *    registrarse, así que la identidad del invitado desaparecía en el mismo acto
 *    que hacía falta para recuperarla.
 * 2. **Saber qué hay que ofrecer.** Una cuenta registrada NO puede listar el
 *    trabajo del invitado —el aislamiento entre cuentas lo impide, y así debe
 *    ser—. Quien sí lo sabe es este equipo: los casos viven en el cliente,
 *    guardados bajo el id de su dueño, y cada corrida conserva su `moleculeId`.
 * 3. **Mover los casos.** El traspaso del backend mueve moléculas y cohortes.
 *    Los casos son del cliente y se quedaban atrás: el investigador recuperaba
 *    los resultados sin la hipótesis que los explicaba.
 *
 * ORDEN DELIBERADO: primero el backend, después los casos. Si el backend falla,
 * los casos siguen siendo del invitado y el ofrecimiento vuelve a aparecer. Al
 * revés quedarían casos de una cuenta apuntando a moléculas de otra, que es
 * exactamente el estado a medias que el endpoint evita con su transacción.
 *
 * Lo que este módulo NO hace, y lo declara en vez de fingirlo: no enumera las
 * cohortes del invitado —no hay registro local de cribados—, así que el Batch
 * del invitado se traspasa desde su propia pestaña cuando exista ese inventario.
 */

import type { CaseIndexEntry, CaseRecord } from "./cases/types";
import type { CaseRepository } from "./cases/repository";

/** Identidad de la cuenta invitada de esta máquina, recordada al salir de ella. */
export interface IdentidadInvitada {
  readonly user_id: string;
  readonly username?: string;
  readonly email?: string;
  /** Cuándo se registró el paso por la cuenta invitada. Sólo informativo. */
  readonly desde?: string;
}

export const CLAVE_INVITADO = "moldesign_invitado";

function almacen(): Storage | null {
  try {
    if (typeof window === "undefined" || !window.localStorage) return null;
    return window.localStorage;
  } catch {
    return null;
  }
}

/**
 * Registra que esta sesión es la del invitado.
 *
 * Lo llama el auto-login de escritorio, que es el ÚNICO sitio donde se entra
 * como invitado. No se deduce del email ni del nombre: deducir la identidad de
 * una cuenta por su texto es como se acaba tratando a un usuario real de
 * invitado.
 */
export function recordarInvitado(identidad: IdentidadInvitada): void {
  const store = almacen();
  if (!store || !identidad.user_id) return;
  try {
    store.setItem(
      CLAVE_INVITADO,
      JSON.stringify({ ...identidad, desde: identidad.desde ?? new Date().toISOString() }),
    );
  } catch {
    // Sin almacenamiento no hay ofrecimiento. El trabajo del invitado sigue
    // intacto en el backend: se pierde la comodidad, no los datos.
  }
}

export function invitadoRecordado(): IdentidadInvitada | null {
  const store = almacen();
  if (!store) return null;
  try {
    const raw = store.getItem(CLAVE_INVITADO);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as IdentidadInvitada;
    return typeof parsed?.user_id === "string" && parsed.user_id.trim() ? parsed : null;
  } catch {
    return null;
  }
}

export function olvidarInvitado(): void {
  const store = almacen();
  if (!store) return;
  try {
    store.removeItem(CLAVE_INVITADO);
  } catch {}
}

/**
 * ¿Hay algo que ofrecer a `usuarioActual`?
 *
 * `null` cuando no se viene del invitado, o cuando la sesión actual ES la del
 * invitado: ofrecerle traspasarse a sí mismo sería un bucle, y el backend lo
 * rechaza con 403 precisamente por eso.
 */
export function invitadoPendienteDeTraspaso(usuarioActual: string | null): IdentidadInvitada | null {
  const invitado = invitadoRecordado();
  if (!invitado || !usuarioActual) return null;
  return invitado.user_id === usuarioActual ? null : invitado;
}

/** Lo que el invitado dejó en este equipo, y que puede moverse. */
export interface InventarioInvitado {
  readonly casos: readonly CaseIndexEntry[];
  /** Moléculas referidas por las corridas de esos casos, sin repetir. */
  readonly moleculeIds: readonly string[];
  /**
   * Casos cuya corrida no llegó a dejar `moleculeId`. Se cuentan aparte porque
   * el caso sí se mueve y la molécula no existe: decir «3 casos, 1 molécula» es
   * más honesto que insinuar que hay tres resultados esperando.
   */
  readonly casosSinResultado: number;
}

export async function inventarioDelInvitado(
  repoInvitado: CaseRepository,
): Promise<InventarioInvitado> {
  const casos = await repoInvitado.listCases();
  const ids = new Set<string>();
  let sinResultado = 0;
  for (const caso of casos) {
    const molecula = caso.activeRun?.moleculeId;
    if (molecula) ids.add(molecula);
    else sinResultado += 1;
  }
  return { casos, moleculeIds: [...ids], casosSinResultado: sinResultado };
}

export interface ResultadoTraspaso {
  readonly moleculasTraspasadas: number;
  readonly cohortesTraspasadas: number;
  readonly casosMovidos: number;
  /**
   * Casos que el backend aceptó pero que no se pudieron reescribir en el
   * cliente. No se ocultan: el trabajo científico ya es de la cuenta nueva y el
   * caso sigue en el invitado, y eso hay que poder decirlo.
   */
  readonly casosNoMovidos: readonly string[];
}

export interface PeticionTraspaso {
  readonly destinoUserId: string;
  readonly repoInvitado: CaseRepository;
  readonly repoDestino: CaseRepository;
  readonly moleculeIds: readonly string[];
  /** Ejecuta `POST /auth/traspaso`. Se inyecta para poder probar sin red. */
  readonly llamarBackend: (payload: {
    molecule_ids: string[];
    cohort_ids: string[];
  }) => Promise<{ moleculas_traspasadas: number; cohortes_traspasadas: number }>;
}

/**
 * Mueve el trabajo del invitado a la cuenta actual. Sólo se llama con
 * consentimiento explícito: no hay traspaso automático en ninguna ruta.
 */
export async function ejecutarTraspaso(peticion: PeticionTraspaso): Promise<ResultadoTraspaso> {
  const { destinoUserId, repoInvitado, repoDestino, moleculeIds, llamarBackend } = peticion;

  // 1. Backend primero. Si lanza, no se ha tocado ningún caso y el ofrecimiento
  //    sigue en pie: reintentar es seguro porque el endpoint es idempotente.
  const respuesta = await llamarBackend({
    molecule_ids: [...moleculeIds],
    cohort_ids: [],
  });

  // 2. Casos. Cada uno por separado: que uno falle no puede impedir el resto.
  const casos = await repoInvitado.listCases();
  let movidos = 0;
  const noMovidos: string[] = [];
  for (const entrada of casos) {
    try {
      const record: CaseRecord = await repoInvitado.readCase(entrada.id);
      await adoptarCaso(repoDestino, { ...record, ownerUserId: destinoUserId });
      await repoInvitado.forgetCase(entrada.id);
      movidos += 1;
    } catch {
      noMovidos.push(entrada.id);
    }
  }

  // 3. El ofrecimiento no vuelve a aparecer aunque algún caso se quedara atrás:
  //    repetirlo mandaría al backend una lista ya traspasada y enseñaría un
  //    inventario que ya no describe nada.
  olvidarInvitado();

  return {
    moleculasTraspasadas: respuesta.moleculas_traspasadas,
    cohortesTraspasadas: respuesta.cohortes_traspasadas,
    casosMovidos: movidos,
    casosNoMovidos: noMovidos,
  };
}

/**
 * Escribe el caso bajo la cuenta de destino.
 *
 * `updateCase` no vale: comprueba que el caso YA existe para no crear por
 * accidente, y aquí el destino todavía no lo tiene. `adoptCase` es la operación
 * explícita del repositorio cuando existe; si no, se declara y el caso se queda
 * donde está en vez de perderse a medio camino.
 */
async function adoptarCaso(repo: CaseRepository, record: CaseRecord): Promise<void> {
  const adoptar = (repo as CaseRepository & {
    adoptCase?: (r: CaseRecord) => Promise<CaseRecord>;
  }).adoptCase;
  if (!adoptar) {
    throw new Error("Este almacenamiento no sabe adoptar un caso de otra cuenta.");
  }
  await adoptar.call(repo, record);
}
