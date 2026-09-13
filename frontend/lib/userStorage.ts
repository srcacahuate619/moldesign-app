/**
 * Almacenamiento local particionado por la identidad autenticada.
 *
 * `localStorage` pertenece al perfil del sistema operativo, no a la cuenta de
 * MolDesign. Usar claves globales mezcla preferencias y borradores cuando dos
 * investigadores comparten el mismo equipo. Estas funciones no escriben nada
 * si no existe una sesión autenticada y nunca reutilizan una clave legacy.
 */

interface StoredAuth {
  readonly user?: { readonly user_id?: unknown };
}

export function currentUserId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem("moldesign_auth");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredAuth;
    const id = parsed.user?.user_id;
    return typeof id === "string" && id.trim() ? id : null;
  } catch {
    return null;
  }
}

export function userStorageKey(baseKey: string, userId = currentUserId()): string | null {
  return userId ? `${baseKey}:user:${userId}` : null;
}

export function getUserItem(baseKey: string, userId = currentUserId()): string | null {
  const key = userStorageKey(baseKey, userId);
  if (!key || typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function setUserItem(
  baseKey: string,
  value: string,
  userId = currentUserId(),
): boolean {
  const key = userStorageKey(baseKey, userId);
  if (!key || typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch {
    return false;
  }
}

export function removeUserItem(baseKey: string, userId = currentUserId()): void {
  const key = userStorageKey(baseKey, userId);
  if (!key || typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {}
}
