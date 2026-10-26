import { getApiUrl, resetApiUrl } from "./config";

// Incidente 2026-10-07: sólo request() de api.ts recuperaba un puerto obsoleto.
// Preflight de Evaluación, visores, PRO, MolChat y otros clientes hacían fetch
// directo y podían quedarse en «Failed to fetch» aunque el motor ya estuviera
// en otro puerto. Todos usan ahora este transporte; config.ts sigue siendo
// el único dueño de la dirección y siempre consulta a Rust en escritorio.
// Ver docs/auditorias/arranque_idioma_ipc_2026-10-07.md.
let revalidation: Promise<string | null> | null = null;

async function revalidateBackend(failedBase: string): Promise<string | null> {
  // Otra petición puede haber recuperado ya el puerto mientras ésta fallaba.
  const current = await getApiUrl().catch(() => null);
  if (current && current !== failedBase) return current;
  if (!revalidation) {
    revalidation = Promise.resolve()
      .then(() => {
        resetApiUrl();
        return getApiUrl();
      })
      .catch(() => null)
      .finally(() => {
        revalidation = null;
      });
  }
  const next = await revalidation;
  return next && next !== failedBase ? next : null;
}

/**
 * Transporte común para REST, preflight, binarios y SSE del backend local.
 * Un error de red revalida el puerto con Rust y sólo reenvía si cambió.
 * Las respuestas HTTP y las cancelaciones nunca disparan esa recuperación.
 * El idioma, la sesión, el cuerpo y la señal siguen siendo del llamador.
 */
export async function fetchBackend(path: string, init?: RequestInit): Promise<Response> {
  const base = await getApiUrl();
  try {
    return await globalThis.fetch(`${base}${path}`, init);
  } catch (error) {
    if (init?.signal?.aborted ||
        ((error instanceof Error || error instanceof DOMException) && error.name === "AbortError")) throw error;
    const next = await revalidateBackend(base);
    // Un error de red no demuestra que un POST no se procesara. No reenviar a
    // ciegas al mismo puerto; una revalidación tampoco ordena reiniciar el motor.
    if (init?.signal?.aborted || !next) throw error;
    return globalThis.fetch(`${next}${path}`, init);
  }
}
