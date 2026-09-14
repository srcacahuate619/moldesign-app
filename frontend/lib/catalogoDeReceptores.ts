// =====================================================================
// catalogoDeReceptores — el catálogo se pide una vez, no una por caso
// =====================================================================
//
// QUÉ PROBLEMA RESUELVE, MEDIDO.
//
// `CaseEvaluationRunner` pide el catálogo en un `useEffect` de montaje, y
// `CaseWorkspace` lo monta con `key={activeCase.id}`. Ese `key` es deliberado
// —es el aislamiento entre casos— pero tiene un efecto que nadie eligió:
// **cada cambio de caso vuelve a bajar el catálogo entero**.
//
// Y el catálogo entero, medido sobre el runtime que viaja en el instalador:
//
//     1 225 608 bytes · 380 receptores · 44 campos cada uno
//     primera llamada   2 486 ms   (siembra el catálogo en el backend)
//     siguientes          339 ms   (mediana de 8, máquina de desarrollo)
//
// En la máquina donde una evaluación tarda cinco minutos, eso no son 339 ms.
//
// LO QUE ESTE MÓDULO NO HACE. No cambia el aislamiento entre casos: el
// catálogo es GLOBAL —los mismos 380 receptores para todos los casos—, así que
// compartirlo no comparte nada que pertenezca a un caso. Lo que se comparte es
// la respuesta de un endpoint de sólo lectura, no el estado de una evaluación.
//
// TRES COSAS QUE PROTEGE:
//
// 1. **No sirve el catálogo de otra cuenta.** El endpoint declara que «deriva
//    los receptores privados de la cuenta autenticada», así que la entrada
//    guardada lleva la identidad con la que se pidió. Si cambia, la caché no
//    se reutiliza: se vuelve a pedir. Servir receptores privados de otro sería
//    peor que la lentitud que esto arregla.
//
// 2. **Dos montajes simultáneos hacen UNA petición.** Al cambiar de caso, el
//    runner nuevo puede montarse antes de que el viejo termine de desmontarse.
//    Sin compartir la promesa en vuelo eso son dos descargas de 1,2 MB.
//
// 3. **Un catálogo que cambia se nota.** Subir un receptor propio invalida la
//    caché, y hay un tiempo de vida para que una edición hecha fuera de la app
//    no quede escondida para siempre.

import { getTargets, type Target } from "./api";

/**
 * Cuánto se considera fresco el catálogo sin volver a preguntar.
 *
 * No es un número de rendimiento, es cuánto tiempo se acepta enseñar un
 * catálogo que podría haber cambiado por fuera. Cinco minutos: más corto no
 * ahorra en una sesión de trabajo normal y más largo esconde una edición
 * externa durante demasiado tiempo.
 */
export const VIDA_DEL_CATALOGO_MS = 5 * 60 * 1000;

interface Entrada {
  readonly identidad: string;
  readonly recibidoEn: number;
  readonly receptores: readonly Target[];
}

let entrada: Entrada | null = null;
let enVuelo: { identidad: string; promesa: Promise<readonly Target[]> } | null = null;

/**
 * Con qué credencial se está pidiendo.
 *
 * Se usa el token y no el id de usuario porque es lo que el backend ve: si el
 * token cambia, lo que el backend devuelve puede cambiar, y eso basta para no
 * reutilizar la respuesta anterior. Sin sesión, la identidad es `anonimo`.
 */
function identidadActual(): string {
  if (typeof window === "undefined") return "sin-ventana";
  try {
    const guardado = window.localStorage.getItem("moldesign_auth");
    if (!guardado) return "anonimo";
    const { token } = JSON.parse(guardado) as { token?: string };
    return token ? `sesion:${token}` : "anonimo";
  } catch {
    return "anonimo";
  }
}

/** Olvida lo guardado. Lo llama quien sabe que el catálogo ya no es el mismo. */
export function invalidarCatalogo(): void {
  entrada = null;
  enVuelo = null;
}

/**
 * El catálogo de receptores, de la caché si sigue siendo válido.
 *
 * `forzar` salta la caché: es lo que debe usar un botón de «recargar», que
 * existe para volver a preguntar de verdad.
 */
export async function obtenerCatalogo(
  opciones: { readonly forzar?: boolean } = {},
): Promise<readonly Target[]> {
  const identidad = identidadActual();
  const ahora = Date.now();

  if (!opciones.forzar && entrada &&
      entrada.identidad === identidad &&
      ahora - entrada.recibidoEn < VIDA_DEL_CATALOGO_MS) {
    return entrada.receptores;
  }

  // Una petición en vuelo con la MISMA identidad se comparte. Con otra
  // identidad no: sería devolverle a esta cuenta lo que pidió la anterior.
  if (!opciones.forzar && enVuelo && enVuelo.identidad === identidad) {
    return enVuelo.promesa;
  }

  const promesa = getTargets()
    .then((receptores) => {
      entrada = { identidad, recibidoEn: Date.now(), receptores };
      return entrada.receptores;
    })
    .finally(() => {
      if (enVuelo?.promesa === promesa) enVuelo = null;
    });

  enVuelo = { identidad, promesa };
  return promesa;
}

/** Lo que hay guardado ahora mismo, sin pedir nada. `null` si no sirve. */
export function catalogoEnMemoria(): readonly Target[] | null {
  if (!entrada) return null;
  if (entrada.identidad !== identidadActual()) return null;
  if (Date.now() - entrada.recibidoEn >= VIDA_DEL_CATALOGO_MS) return null;
  return entrada.receptores;
}
