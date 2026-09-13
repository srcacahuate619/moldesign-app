/**
 * Construye el repositorio de casos de una cuenta concreta.
 *
 * `CaseContext` ya lo hacía para la sesión activa. El traspaso del invitado
 * necesita lo mismo para DOS cuentas a la vez —la de origen y la de destino—,
 * y copiar la construcción en el componente habría creado una segunda forma de
 * elegir almacenamiento que se desincroniza en cuanto una de las dos cambie.
 *
 * Sin `canClaimLegacyCase` a propósito: reclamar un caso legacy sin propietario
 * es otra decisión, con su propia comprobación contra el backend. Aquí se leen
 * casos que YA declaran dueño.
 */

import { createBrowserCaseRepository } from "./browserCaseRepository";
import { createTauriCaseRepository } from "./tauriCaseRepository";
import { isTauriAvailable, type CaseRepository } from "./repository";

export function crearRepositorioDeCasos(ownerUserId: string): CaseRepository {
  if (!ownerUserId) {
    throw new Error("Un repositorio de casos necesita la identidad de su dueño.");
  }
  if (!isTauriAvailable()) return createBrowserCaseRepository(ownerUserId);
  return createTauriCaseRepository({ ownerUserId });
}
