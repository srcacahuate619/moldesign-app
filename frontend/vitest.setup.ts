// Setup global para tests de Vitest.
//
// Carga:
// 1. @testing-library/jest-dom matchers (toBeInTheDocument, toHaveValue, etc.)
// 2. Mock de Tauri: mockeamos el modulo completo `@tauri-apps/api/core`
//    con vi.mock factory. Usamos un patrón de "holder" compartido: la factory
//    y el export usan LA MISMA referencia mockTauriInvoke (definida una vez).
//    Esto resuelve la dualidad: los tests configuran el export, y la factory
//    del mock lo usa directamente porque es el mismo objeto.
// 3. Mock de `fetch` global. Default: rechaza todo. Cada test overridea con
//    `mockFetch.mockResolvedValueOnce(...)`. Fuerza explicitud.
// 4. `localStorage` cleanup entre tests (jsdom lo persiste, contamina state).
// 5. Cleanup de RTL después de cada test.

import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, vi } from "vitest";
import { cleanup } from "@testing-library/react";

// 1. Matchers jest-dom: cargados via import arriba.

// 2. Mock de Tauri — patrón holder compartido.
//    Definimos mockTauriInvoke UNA VEZ antes del vi.mock. La factory del
//    vi.mock y el export usan LA MISMA referencia. Así los tests configuran
//    el export y el módulo mockeado ve los cambios.
export const mockTauriInvoke = vi.fn(async (cmd: string, _args?: Record<string, unknown>): Promise<unknown> => {
  throw new Error(`Unmocked Tauri invoke: ${cmd}. Configure mockTauriInvoke.mockImplementation in your test.`);
});

/**
 * `openUrl` de `tauri-plugin-opener`.
 *
 * Por defecto resuelve: abrir un enlace es una accion normal, no algo que haya
 * que autorizar en cada prueba. Los tests que quieran comprobar QUE se llamo
 * inspeccionan este mock.
 */
export const mockOpenUrl = vi.fn(async (_url: string): Promise<void> => {});

vi.mock("@tauri-apps/plugin-opener", () => ({
  openUrl: (url: string) => mockOpenUrl(url),
}));

vi.mock("@tauri-apps/api/core", () => ({
  invoke: (cmd: string, args?: Record<string, unknown>) => mockTauriInvoke(cmd, args),
  // Algunas versiones de @tauri-apps/api exportan listen, emit, etc.
  listen: vi.fn(async () => () => {}), // retorna un unlisten stub
  emit: vi.fn(),
  // Metadata que algunas versiones chequean
  metadata: {
    currentWindow: { label: "main" },
    currentWebview: { label: "main", windowLabel: "main" },
  },
}));

// Mock de @tauri-apps/api/event — DownloadProvider importa listen desde aquí.
vi.mock("@tauri-apps/api/event", () => ({
  listen: vi.fn(async (_event: string, _handler: (e: any) => void) => () => {}), // unlisten stub
  emit: vi.fn(),
}));

// 3. Mock de fetch global: default rechaza. Cada test overridea.
export const mockFetch = vi.fn(async (): Promise<Response> => {
  throw new Error("fetch called without mock. Configure mockFetch.mockResolvedValueOnce in your test.");
});

global.fetch = mockFetch as unknown as typeof fetch;

// 3b. Helpers de entorno Tauri para tests.
// DownloadProvider.tsx tiene dos guards distintos:
//   - isTauri()  → solo window.__TAURI__
//   - invoke() local → window.__TAURI__ || window.__TAURI_INTERNALS__
// Por defecto, jsdom no tiene ninguno (entorno dev/no-Tauri).
// Los tests que simulan Tauri llaman setTauriEnv(true).
export function setTauriEnv(enabled: boolean): void {
  if (typeof window === "undefined") return;
  if (enabled) {
    // ACTUALIZADO con el puente unico (`lib/tauri.ts`). La app ya no importa
    // `@tauri-apps/api` —el paquete no esta instalado y ese import nunca se
    // resolvia—: usa `window.__TAURI__.core.invoke`, que es lo que inyecta el
    // runtime porque `tauri.conf.json` declara `withGlobalTauri: true`.
    //
    // Por eso el global de prueba tiene que TENER esa forma. Un `__TAURI__`
    // vacio simulaba un entorno que no existe en ninguna parte, y los tests
    // habrian pasado contra un puente que en produccion no funciona.
    (window as any).__TAURI__ = {
      core: {
        invoke: (cmd: string, args?: Record<string, unknown>) => mockTauriInvoke(cmd, args),
      },
      event: {
        listen: async (_event: string, _handler: (e: any) => void) => () => {},
      },

    };
    (window as any).__TAURI_INTERNALS__ = {};
  } else {
    delete (window as any).__TAURI__;
    delete (window as any).__TAURI_INTERNALS__;
  }
}

// 4 + 5. Reset entre tests.

beforeEach(() => {
  // Limpia localStorage (jsdom lo persiste entre tests).
  if (typeof window !== "undefined" && window.localStorage) {
    window.localStorage.clear();
  }
});

// 6. Errores ESPERADOS que las pruebas provocan a propósito.
//
// Varias suites comprueban justamente el camino de error —«un fallo de red se
// declara como tal», «el catálogo caído no bloquea la entrada manual»— y para
// eso tienen que provocar el fallo. `lib/api.ts` lo registra con
// `console.error`, y el resultado eran decenas de líneas rojas en una salida
// verde: ruido que entrena a no mirar, y donde un error NUEVO pasaría
// desapercibido.
//
// Se silencian SÓLO los mensajes que el producto emite al fallar una petición,
// por su prefijo. Cualquier otro `console.error` sigue viéndose, que es el que
// hay que leer.
const errorReal = console.error;
const ESPERADOS = [/^Fetch error on /];

beforeEach(() => {
  console.error = ((...args: unknown[]) => {
    const primero = typeof args[0] === "string" ? args[0] : "";
    if (ESPERADOS.some((patron) => patron.test(primero))) return;
    errorReal(...(args as Parameters<typeof console.error>));
  }) as typeof console.error;
});

afterEach(() => {
  console.error = errorReal;
  // Desmonta componentes renderizados con render/renderHook.
  cleanup();
  // Limpia historial de llamadas de TODOS los mocks (sin destruir la impl).
  // NOTA: NO usamos vi.restoreAllMocks() porque restaura el vi.mock factory
  // de Tauri y rompe el mock en tests siguientes. clearAllMocks preserva
  // las implementaciones custom que cada test setea en beforeEach.
  vi.clearAllMocks();
  // Restablece el mock de fetch al default (rechaza todo).
  mockFetch.mockImplementation(async () => {
    throw new Error("fetch called without mock after cleanup.");
  });
  // Restablece mockTauriInvoke al default (rechaza todo).
  mockTauriInvoke.mockImplementation(async (cmd: string) => {
    throw new Error(`Unmocked Tauri invoke: ${cmd}. Configure mockTauriInvoke.mockImplementation in your test.`);
  });
  // `clearAllMocks` borra el historial pero tambien la implementacion por
  // defecto de `mockOpenUrl`; sin restaurarla, la segunda prueba que abra un
  // enlace recibiria `undefined` en vez de una promesa.
  mockOpenUrl.mockImplementation(async () => {});
  // Restablece entorno Tauri a no-Tauri (default jsdom).
  setTauriEnv(false);
});
