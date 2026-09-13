// =====================================================================
// Disponibilidad de WebGL, dicha por MolDesign y no por la librería
// =====================================================================
//
// EL FALLO QUE ARREGLA. En una máquina virtual sin aceleración 3D, el visor
// mostraba el mensaje crudo de la librería:
//
//     WebGL does not seem to be available.
//     This can be caused by an outdated browser, graphics card driver issue,
//     or bad weather. Sometimes, just restarting the browser helps.
//
// Ese texto es de Mol*, no nuestro. Habla de navegadores y de «bad weather» a
// alguien que está usando una aplicación de escritorio, no dice qué parte de
// MolDesign sigue funcionando, y deja al investigador sin saber si su análisis
// es válido o si acaba de perder la corrida.
//
// El visor no debe montarse cuando esta comprobación falla: así MolDesign
// sustituye el mensaje interno de la librería por un estado propio que explica
// qué parte del análisis sigue siendo utilizable.

/** Resultado de la comprobación, con el motivo cuando falla. */
export interface EstadoWebGL {
  readonly disponible: boolean;
  /** `null` si está disponible. */
  readonly motivo: string | null;
}

let cache: EstadoWebGL | null = null;

/**
 * Comprueba si el equipo puede crear un contexto WebGL.
 *
 * Se crea un canvas desechable y se descarta de inmediato: crear el contexto es
 * la ÚNICA forma fiable de saberlo. Preguntar por el navegador o por el driver
 * da falsos positivos —una VM anuncia un navegador moderno y aun así no expone
 * aceleración— y ese es justo el caso que hay que detectar.
 *
 * El resultado se memoriza: la capacidad no cambia dentro de una sesión, y
 * crear contextos WebGL de prueba consume recursos de GPU de verdad.
 */
export function comprobarWebGL(): EstadoWebGL {
  if (cache) return cache;
  if (typeof window === "undefined" || typeof document === "undefined") {
    // En render de servidor no se puede saber. Se responde «disponible» para no
    // pintar una advertencia que quizá no corresponde: el cliente lo corregirá.
    return { disponible: true, motivo: null };
  }
  try {
    const canvas = document.createElement("canvas");
    const contexto =
      canvas.getContext("webgl2") ||
      canvas.getContext("webgl") ||
      canvas.getContext("experimental-webgl");
    if (!contexto) {
      cache = {
        disponible: false,
        motivo:
          "este equipo no expone aceleración 3D por hardware. Es lo habitual en " +
          "una máquina virtual sin GPU virtualizada.",
      };
      return cache;
    }
    // Liberar el contexto de prueba en vez de dejarlo colgando: los navegadores
    // limitan cuántos hay vivos a la vez, y el visor real necesita el suyo.
    const perder = (contexto as WebGLRenderingContext).getExtension("WEBGL_lose_context");
    perder?.loseContext();
    cache = { disponible: true, motivo: null };
    return cache;
  } catch (error) {
    cache = {
      disponible: false,
      motivo: `no se pudo crear un contexto WebGL (${String(error).slice(0, 80)}).`,
    };
    return cache;
  }
}

/** Sólo para pruebas: olvida la comprobación memorizada. */
export function reiniciarComprobacionWebGL(): void {
  cache = null;
}
