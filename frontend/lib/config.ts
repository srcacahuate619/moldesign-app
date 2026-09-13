// =====================================================================
// Dirección del backend — UNA sola abstracción, un solo dueño del puerto
// =====================================================================
//
// EL FALLO QUE ARREGLA. Este archivo fijaba `http://127.0.0.1:8000` como una
// constante de módulo. Rust, en cambio, elige el primer puerto libre del rango
// 8000-8019 y arranca ahí el backend. Con 8000 ocupado por cualquier otro
// proceso, el backend quedaba en 8001 y TODA la aplicación —REST, SSE,
// descargas, PDF, previews— seguía llamando a 8000, que no contestaba. La
// evaluación fallaba sin ninguna causa visible, y el arranque «funcionaba».
//
// EL CONTRATO:
//
//   getApiUrl()      → Promise<string>. Es EL accesor para hacer peticiones.
//                      En escritorio espera a que Rust diga en qué puerto está
//                      el backend; ese valor manda sobre cualquier otro.
//   apiUrlSnapshot() → string | null. Sólo para enlaces EN RENDER. En Tauri no
//                      fabrica `:8000` mientras Rust todavía no ha confirmado
//                      el puerto: devuelve null y el control permanece inerte.
//   subscribeApiUrl()→ avisa cuando el valor cambia, para que esos enlaces se
//                      vuelvan a pintar. `hooks/useApiUrl.ts` lo envuelve.
//
// NO hay una constante `API_URL` exportada. Existía junto a `getApiUrl()` y era
// exactamente la mezcla que produce el fallo: la constante se congela al cargar
// el módulo —antes de que Rust haya elegido puerto— y quien la importe nunca se
// entera del puerto real.
//
// PRECEDENCIA:
//   1. El puerto que devuelve Rust (`ensure_backend`). Manda en escritorio.
//   2. `NEXT_PUBLIC_API_URL`. Override útil para navegador, tests y desarrollo
//      web contra un backend remoto.
//   3. `http://127.0.0.1:8000`. Último recurso; el mismo puerto por defecto que
//      intenta Rust primero.

import { invoke, isDesktopRuntime, isTauriAvailable } from "./tauri";

export const DEFAULT_API_URL = "http://127.0.0.1:8000";

/** Forma del estado del backend que devuelve Rust. Ver `src-tauri/src/backend.rs`. */
export interface BackendStatusPayload {
  readonly state:
    | "idle"
    | "starting"
    | "ready"
    | "not_installed"
    | "spawn_failed"
    | "health_failed";
  readonly port: number | null;
  readonly detail: string | null;
}

function envOverride(): string | null {
  const value = process.env.NEXT_PUBLIC_API_URL;
  return value && value.length > 0 ? value : null;
}

let resolved: string | null = null;
let pending: Promise<string> | null = null;
// Invalida resoluciones asíncronas de un arranque anterior. Sin este contador,
// una llamada lenta a `ensure_backend` podía publicar el puerto viejo después
// de que el usuario ya hubiera pulsado «Reintentar».
let resolutionGeneration = 0;
const listeners = new Set<(url: string | null) => void>();

function publish(url: string | null): void {
  if (resolved === url) return;
  resolved = url;
  for (const listener of listeners) listener(url);
}

/**
 * Pregunta a Rust por el puerto y espera a que el backend esté listo.
 *
 * `ensure_backend` es IDEMPOTENTE por contrato: varias llamadas concurrentes
 * devuelven el mismo proceso. Aun así aquí se memoriza la promesa en vuelo, que
 * es lo que evita una tormenta de invocaciones cuando media aplicación arranca
 * a la vez.
 */
async function resolveFromDesktop(): Promise<string> {
  const status = await invoke<BackendStatusPayload | number>("ensure_backend");
  // Se acepta el número suelto además del objeto: si alguien ejecuta un binario
  // viejo del contenedor, la aplicación degrada en vez de romperse.
  const port = typeof status === "number" ? status : status?.port ?? null;
  if (typeof port !== "number" || port <= 0) {
    throw new Error(
      typeof status === "object" && status?.detail
        ? status.detail
        : "El motor no devolvió un puerto utilizable.",
    );
  }
  return `http://127.0.0.1:${port}`;
}

/**
 * Dirección base del backend. **Es el accesor que deben usar las peticiones.**
 *
 * En navegador usa el override o el puerto por defecto. En Tauri, en cambio,
 * un fallo LANZA: caer a `:8000` podría hablar con otro producto que ocupe ese
 * puerto. «No conozco el backend» nunca se convierte en «prueba con un vecino».
 */
export async function getApiUrl(): Promise<string> {
  if (resolved) return resolved;
  if (!isTauriAvailable()) {
    // El respaldo a :8000 es para el NAVEGADOR. Dentro del contenedor de
    // escritorio nunca se adivina un puerto.
    //
    // EL FALLO QUE ARREGLA. Este archivo ya razonaba que caer a :8000 «podria
    // hablar con otro producto que ocupe ese puerto», pero solo lo evitaba
    // cuando el puente Tauri ESTABA disponible. Si el puente falta —el CSP de
    // produccion bloqueo el script que lo inyecta, el runtime cambio, lo que
    // sea— `isTauriAvailable()` da false y la aplicacion instalada caia por
    // esta rama derecha al vecino. En el equipo del autor, `legaldesk-server`
    // ocupaba el 8000 y contestaba 200 con HTML: los receptores giraban para
    // siempre y no habia ningun error que mirar.
    //
    // `isDesktopRuntime()` es mas laxo a proposito: detecta el contenedor
    // aunque el puente no sirva. Justo lo que hace falta para distinguir «soy
    // un navegador, usa el valor por defecto» de «soy la app y algo va mal».
    if (isDesktopRuntime()) {
      throw new Error(
        "El puente de escritorio no esta disponible, asi que no se puede saber " +
          "en que puerto quedo el backend. No se adivina: otro programa podria " +
          "estar escuchando ahi.",
      );
    }
    const url = envOverride() ?? DEFAULT_API_URL;
    publish(url);
    return url;
  }
  if (!pending) {
    const generation = resolutionGeneration;
    pending = resolveFromDesktop()
      .then((url) => {
        if (generation === resolutionGeneration) publish(url);
        return url;
      })
      .catch((error) => {
        // NO se memoriza el fallo: reintentar el arranque debe poder cambiar
        // esto sin recargar la aplicación.
        if (generation === resolutionGeneration) pending = null;
        throw error;
      });
  }
  return pending;
}

/**
 * Lo mejor que se sabe AHORA, sin esperar. Sólo para enlaces en render.
 *
 * Dispara la resolución si todavía no ha empezado, así que un `href` pintado
 * antes de tiempo se corrige en cuanto llega el puerto real — siempre que quien
 * lo pinta esté suscrito (`useApiUrl`).
 */
export function apiUrlSnapshot(): string | null {
  if (resolved) return resolved;
  if (!isTauriAvailable()) {
    // Mismo criterio que `getApiUrl`: en escritorio no se adivina. Aqui no se
    // puede lanzar —es un render— asi que se devuelve null y el control queda
    // inerte, que es el comportamiento que este archivo ya prometia para
    // cuando el puerto todavia no se conoce.
    if (isDesktopRuntime()) return null;
    const fallback = envOverride() ?? DEFAULT_API_URL;
    publish(fallback);
    return fallback;
  }
  // Un snapshot no puede propagar la promesa. El error lo mostrará el estado
  // del motor; aquí sólo se evita una unhandled rejection.
  void getApiUrl().catch(() => undefined);
  return null;
}

export function subscribeApiUrl(listener: (url: string | null) => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Fija la dirección desde fuera. La usa el proveedor del motor cuando Rust ya
 * le ha dicho el puerto, para que nadie más tenga que volver a preguntarlo.
 */
export function setApiUrlFromPort(port: number): void {
  if (!Number.isInteger(port) || port <= 0) return;
  resolutionGeneration += 1;
  pending = null;
  publish(`http://127.0.0.1:${port}`);
}

/** Olvida lo resuelto. Para tests y para un reintento explícito del motor. */
export function resetApiUrl(): void {
  resolutionGeneration += 1;
  pending = null;
  publish(null);
}
