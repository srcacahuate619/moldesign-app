// =====================================================================
// Puente ÚNICO con Tauri
// =====================================================================
//
// POR QUE EXISTE. Habia dos mecanismos distintos para lo mismo: un `import()`
// dinamico de `@tauri-apps/api/core` en `DownloadProvider` y otro en el
// repositorio de casos. Ese import NO ERA RESOLUBLE: `@tauri-apps/api` no esta
// en `node_modules` —solo esta `@tauri-apps/cli`—, asi que en escritorio el
// `catch` se tragaba el fallo y todo degradaba a "Tauri no disponible" sin
// decir por que. Dos mecanismos, y los dos rotos de la misma forma.
//
// COMO SE RESUELVE. `tauri.conf.json` declara `withGlobalTauri: true`, asi que
// el runtime inyecta `window.__TAURI__.core.invoke` en el webview. Se usa ESE, y
// solo ese. No hace falta empaquetar el paquete npm ni resolver nada en build:
// el puente existe en tiempo de ejecucion o no existe, y se puede comprobar.
//
// Si algun dia se quita `withGlobalTauri`, este archivo es el unico sitio que
// hay que cambiar.

/** Forma minima del objeto global que inyecta Tauri v2 con `withGlobalTauri`. */
interface TauriGlobal {
  core?: {
    invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
  };
  event?: {
    listen?: (
      event: string,
      handler: (payload: { payload: unknown }) => void,
    ) => Promise<() => void>;
  };
  // Tauri v1 exponia `invoke` en la raiz. Se acepta como respaldo de lectura
  // para no romper si el runtime es mas viejo de lo esperado.
  invoke?: (cmd: string, args?: Record<string, unknown>) => Promise<unknown>;
}

function tauriGlobal(): TauriGlobal | null {
  if (typeof window === "undefined") return null;
  const candidate = (window as unknown as { __TAURI__?: TauriGlobal }).__TAURI__;
  return candidate ?? null;
}

/**
 * `true` si hay un puente Tauri USABLE, no solo si el runtime esta presente.
 *
 * La distincion importa: `__TAURI_INTERNALS__` puede existir sin que
 * `__TAURI__.core.invoke` lo haga si `withGlobalTauri` estuviera desactivado.
 * Comprobar la funcion que se va a llamar evita prometer una capacidad que
 * despues falla al usarse.
 */
export function isTauriAvailable(): boolean {
  const g = tauriGlobal();
  return typeof g?.core?.invoke === "function" || typeof g?.invoke === "function";
}

/**
 * `true` si el proceso corre dentro del contenedor de escritorio.
 *
 * Mas laxo que `isTauriAvailable`: sirve para decidir mensajes ("estas en la
 * app") pero NO para decidir si se puede invocar.
 */
export function isDesktopRuntime(): boolean {
  if (typeof window === "undefined") return false;
  const w = window as unknown as Record<string, unknown>;
  return "__TAURI_INTERNALS__" in w || "__TAURI__" in w;
}

export class TauriBridgeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TauriBridgeError";
  }
}

/** Invoca un comando Rust. Lanza `TauriBridgeError` si no hay puente. */
export async function invoke<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const g = tauriGlobal();
  const fn = g?.core?.invoke ?? g?.invoke;
  if (typeof fn !== "function") {
    throw new TauriBridgeError(
      `El puente de escritorio no está disponible (comando \`${cmd}\`). ` +
        "Esta función requiere la aplicación de escritorio.",
    );
  }
  return (await fn(cmd, args)) as T;
}

/** Suscripcion a eventos Rust. Devuelve un `unlisten` inerte si no hay puente. */
export async function listen(
  event: string,
  handler: (payload: { payload: unknown }) => void,
): Promise<() => void> {
  const g = tauriGlobal();
  const fn = g?.event?.listen;
  if (typeof fn !== "function") return () => {};
  try {
    return await fn(event, handler);
  } catch {
    return () => {};
  }
}

/**
 * Comprobacion de humo del puente, invocable desde la app real.
 *
 * Llama a un comando barato y devuelve un diagnostico legible. Existe para que
 * "el puente funciona" sea algo que se PRUEBA desde el webview en vez de algo
 * que se supone: es lo que fallaba antes sin que nadie se enterara.
 */
export async function tauriBridgeSmokeTest(): Promise<{
  available: boolean;
  desktop: boolean;
  invoked: boolean;
  detail: string;
}> {
  const desktop = isDesktopRuntime();
  const available = isTauriAvailable();
  if (!available) {
    return {
      available,
      desktop,
      invoked: false,
      detail: desktop
        ? "Runtime de escritorio detectado pero `window.__TAURI__.core.invoke` no existe: revisa `withGlobalTauri` en tauri.conf.json."
        : "Entorno web: no hay puente de escritorio, y es lo esperado.",
    };
  }
  try {
    const cases = await invoke<unknown[]>("case_list_authorized");
    return {
      available,
      desktop,
      invoked: true,
      detail: `Puente operativo. \`case_list_authorized\` devolvió ${Array.isArray(cases) ? cases.length : 0} caso(s) autorizado(s).`,
    };
  } catch (error) {
    return {
      available,
      desktop,
      invoked: false,
      detail: `El puente existe pero la invocación falló: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}
